"""Opaque tracking credentials and Redis rate limits; never persist/log raw tokens."""

import hashlib
import secrets
from typing import cast

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError


def new_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


def rate_limit(client: Redis, key: str, maximum: int, window: int = 60) -> None:
    try:
        value = cast(list[int], client.eval(LIMIT, 1, key, window))
        if not isinstance(value, list) or len(value) != 2:
            raise HTTPException(503, "Theo dõi tạm thời chưa sẵn sàng; vui lòng thử lại")
        count, remaining = value
    except RedisError as exc:
        raise HTTPException(503, "Theo dõi tạm thời chưa sẵn sàng; vui lòng thử lại") from exc
    if int(count) > maximum:
        raise HTTPException(
            429,
            "Quá nhiều yêu cầu theo dõi; vui lòng thử lại sau",
            headers={"Retry-After": str(max(1, int(remaining)))},
        )
