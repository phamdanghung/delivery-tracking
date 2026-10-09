import re
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis import Redis

from app.config import get_settings
from app.tracking_security import new_token, rate_limit, token_hash


def test_tracking_tokens_are_256_bit_opaque_credentials_hash_only():
    generated = [new_token() for _ in range(100)]
    assert len({token for token, _ in generated}) == 100
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", token) for token, _ in generated)
    assert all(digest == token_hash(token) and len(digest) == 64 for token, digest in generated)
    assert all(token != digest and token not in digest for token, digest in generated)


@pytest.mark.integration
def test_real_redis_public_rate_limit_is_atomic_and_has_expiry():
    client = Redis.from_url(get_settings().redis_url.get_secret_value(), socket_timeout=5)
    key = "tracking-test:" + uuid4().hex
    try:
        assert client.ping()

        def invoke(_: int) -> int:
            try:
                rate_limit(client, key, 5, window=60)
                return 200
            except HTTPException as exc:
                assert exc.status_code == 429
                assert exc.headers and 1 <= int(exc.headers["Retry-After"]) <= 60
                return exc.status_code

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(invoke, range(20)))
        assert results.count(200) == 5 and results.count(429) == 15
        assert 0 < client.ttl(key) <= 60
    finally:
        client.delete(key)  # Only this run's random key; never flush canonical Redis.
        client.close()
