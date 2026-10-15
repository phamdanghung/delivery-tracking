"""Internal, warm, serial API measurement; not a production load acceptance."""

import json
from time import perf_counter

import pytest
from test_m1_api import context as context
from test_m1_api import header
from test_m2_api import create

from app.operational_metrics import p95

pytestmark = pytest.mark.integration


def test_warm_common_api_p95_meets_locked_500ms_target_with_real_data(context):
    client, _, _, tokens = context
    for index in range(7):
        create(context, kind=["FIXED_TIME", "TIME_WINDOW", "BEFORE_DEADLINE"][index % 3])
    results = {}
    for path in ("/api/v1/auth/me", "/api/v1/deliveries", "/api/v1/vehicles"):
        assert client.get(path, headers=header(tokens)).status_code == 200
        samples = []
        for _ in range(20):
            start = perf_counter()
            response = client.get(path, headers=header(tokens))
            samples.append((perf_counter() - start) * 1000)
            assert response.status_code == 200
        percentile = p95(samples)
        results[path] = {"samples": len(samples), "p95_ms": round(percentile, 3)}
        assert percentile < 500, results
    print(json.dumps({"scope": "warm serial TestClient + real PostgreSQL", "routes": results}))
