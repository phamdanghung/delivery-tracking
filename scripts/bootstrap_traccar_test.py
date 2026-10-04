"""Initialize and verify a fresh CI Traccar service; never reset an existing account."""

import os
import time

import httpx

base = os.environ["TRACCAR_URL"].rstrip("/")
email = os.environ["TRACCAR_EMAIL"]
password = os.environ["TRACCAR_PASSWORD"]
with httpx.Client(timeout=5, trust_env=False) as client:
    for attempt in range(60):
        try:
            response = client.get(base + "/api/server")
            response.raise_for_status()
            break
        except httpx.HTTPError:
            if attempt == 59:
                raise
            time.sleep(2)
    if response.json().get("newServer") is True:
        created = client.post(
            base + "/api/users",
            json={
                "name": "Isolated CI adapter",
                "email": email,
                "password": password,
            },
        )
        created.raise_for_status()
    verified = client.get(base + "/api/devices", auth=(email, password))
    verified.raise_for_status()
print("Real CI Traccar authentication verified; secrets not printed.")
