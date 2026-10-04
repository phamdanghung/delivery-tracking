import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.database import audit, database, table
from app.schemas import Login, Refresh, Role, TokenOut, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
Db = Annotated[Connection, Depends(database)]


def secret() -> str:
    value = get_settings().jwt_secret.get_secret_value()
    if len(value.encode()) < 32:
        raise HTTPException(503, "Xác thực chưa được cấu hình an toàn")
    return value


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(db: Connection, user: UserOut, family: UUID | None = None) -> TokenOut:
    settings = get_settings()
    key = secret()
    now = datetime.now(UTC)
    session_id = uuid4()
    refresh = secrets.token_urlsafe(48)
    db.execute(
        table("auth_sessions", db)
        .insert()
        .values(
            id=session_id,
            user_id=user.id,
            family_id=family or uuid4(),
            refresh_hash=digest(refresh),
            expires_at=now + timedelta(seconds=settings.jwt_refresh_seconds),
        )
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "jti": str(session_id),
            "iat": now,
            "exp": now + timedelta(seconds=settings.jwt_access_seconds),
            "iss": "fleet-delivery",
            "aud": "fleet-internal",
        },
        key,
        algorithm="HS256",
    )
    return TokenOut(
        access_token=token, refresh_token=refresh, expires_in=settings.jwt_access_seconds, user=user
    )


def authenticate(db: Connection, token: str) -> UserOut:
    try:
        claims = jwt.decode(
            token,
            secret(),
            algorithms=["HS256"],
            issuer="fleet-delivery",
            audience="fleet-internal",
            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]},
        )
        user_id, session_id = UUID(claims["sub"]), UUID(claims["jti"])
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ") from exc
    users, sessions = table("users", db), table("auth_sessions", db)
    row = (
        db.execute(
            select(users)
            .join(sessions, users.c.id == sessions.c.user_id)
            .where(
                users.c.id == user_id,
                users.c.is_active.is_(True),
                sessions.c.id == session_id,
                sessions.c.revoked_at.is_(None),
                sessions.c.expires_at > datetime.now(UTC),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(401, "Phiên đăng nhập đã hết hiệu lực")
    return UserOut.model_validate(row)


def current_user(
    db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> UserOut:
    if credentials is None:
        raise HTTPException(401, "Vui lòng đăng nhập", headers={"WWW-Authenticate": "Bearer"})
    return authenticate(db, credentials.credentials)


User = Annotated[UserOut, Depends(current_user)]


def admin(user: User) -> UserOut:
    if user.role != Role.ADMIN:
        raise HTTPException(403, "Bạn không có quyền quản trị")
    return user


def operator(user: User) -> UserOut:
    if user.role not in (Role.ADMIN, Role.DISPATCHER):
        raise HTTPException(403, "Bạn không có quyền xem đội xe/GPS")
    return user


Admin = Annotated[UserOut, Depends(admin)]
Operator = Annotated[UserOut, Depends(operator)]


@router.post("/login", response_model=TokenOut)
def login(data: Login, request: Request, db: Db) -> TokenOut:
    users = table("users", db)
    row = db.execute(select(users).where(users.c.email == data.email.casefold())).mappings().first()
    try:
        hasher.verify(row["password_hash"] if row else dummy_hash, data.password)
    except (VerificationError, InvalidHashError) as exc:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng") from exc
    if not row or not row["is_active"]:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    user = UserOut.model_validate(row)
    if hasher.check_needs_rehash(row["password_hash"]):
        db.execute(
            users.update()
            .where(users.c.id == user.id)
            .values(password_hash=hasher.hash(data.password))
        )
    result = issue(db, user)
    audit(db, request, user.id, "LOGIN", "user", user.id)
    return result


@router.post("/refresh", response_model=TokenOut)
def refresh(data: Refresh, request: Request, db: Db) -> TokenOut:
    sessions = table("auth_sessions", db)
    row = (
        db.execute(
            select(sessions)
            .where(sessions.c.refresh_hash == digest(data.refresh_token))
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    now = datetime.now(UTC)
    if row["revoked_at"] is not None:
        db.execute(
            update(sessions).where(sessions.c.family_id == row["family_id"]).values(revoked_at=now)
        )
        db.commit()  # Persist replay revocation even though the response is an error.
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    if row["expires_at"] <= now:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
    users = table("users", db)
    user = db.execute(
        select(users).where(users.c.id == row["user_id"], users.c.is_active.is_(True))
    )
    found = user.mappings().first()
    if found is None:
        raise HTTPException(401, "Tài khoản không hoạt động")
    db.execute(sessions.update().where(sessions.c.id == row["id"]).values(revoked_at=now))
    result = issue(db, UserOut.model_validate(found), row["family_id"])
    audit(db, request, row["user_id"], "REFRESH", "user", row["user_id"])
    return result


@router.post("/logout", status_code=204)
def logout(data: Refresh, user: User, request: Request, db: Db) -> None:
    sessions = table("auth_sessions", db)
    db.execute(
        sessions.update()
        .where(
            sessions.c.user_id == user.id,
            sessions.c.refresh_hash == digest(data.refresh_token),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    audit(db, request, user.id, "LOGOUT", "user", user.id)


@router.get("/me", response_model=UserOut)
def me(user: User) -> UserOut:
    return user
