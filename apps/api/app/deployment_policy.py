"""Fail closed on unsafe public production configuration, without claiming deployment readiness."""

import re
from ipaddress import ip_address
from urllib.parse import urlsplit

from app.config import Settings


def public_https(value: str, *, origin: bool = False) -> bool:
    try:
        if any(ord(character) <= 32 or ord(character) == 127 for character in value):
            return False
        url = urlsplit(value)
        host = (url.hostname or "").rstrip(".").lower()
        if (
            url.scheme != "https"
            or not host
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or "*" in host
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
            or (origin and url.path)
        ):
            return False
        port = url.port  # Validate port syntax without exposing the URL in errors.
        if port is not None and port == 0:
            return False
        try:
            return ip_address(host).is_global
        except ValueError:
            host = host.encode("idna").decode("ascii")
            return (
                "." in host
                and re.fullmatch(r"[0-9.]+", host) is None
                and re.search(r"[a-z]", host.split(".")[-1]) is not None
                and all(
                    re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in host.split(".")
                )
            )
    except ValueError:
        return False


def production_config_issues(settings: Settings) -> list[str]:
    issues: list[str] = []
    if len(settings.jwt_secret.get_secret_value().encode()) < 32:
        issues.append("JWT_SECRET_TOO_SHORT")
    if not 0 < settings.jwt_access_seconds < settings.jwt_refresh_seconds:
        issues.append("JWT_LIFETIMES_INVALID")
    if not public_https(settings.tracking_public_base_url, origin=True):
        issues.append("TRACKING_PUBLIC_HTTPS_REQUIRED")
    if not public_https(settings.s3_public_endpoint_url):
        issues.append("STORAGE_PUBLIC_HTTPS_REQUIRED")
    if not settings.cors_origins or not all(
        public_https(o, origin=True) for o in settings.cors_origins
    ):
        issues.append("CORS_EXACT_HTTPS_ORIGINS_REQUIRED")
    if not settings.database_url.get_secret_value():
        issues.append("DATABASE_NOT_CONFIGURED")
    if (
        not settings.s3_access_key.get_secret_value()
        or not settings.s3_secret_key.get_secret_value()
    ):
        issues.append("STORAGE_CREDENTIALS_NOT_CONFIGURED")
    return issues


def enforce_production_config(settings: Settings) -> None:
    if settings.app_env == "production":
        issues = production_config_issues(settings)
        if issues:
            # Codes only: never echo connection strings, credentials, or signed URLs.
            raise RuntimeError("Unsafe production configuration: " + ",".join(issues))
