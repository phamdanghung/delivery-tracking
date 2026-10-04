import json
from pathlib import Path

from app.main import app


def test_m1_contract_matches_source() -> None:
    root = Path(__file__).resolve().parents[3]
    expected = json.loads((root / "openapi/m1.openapi.json").read_text(encoding="utf-8"))
    assert app.openapi() == expected
