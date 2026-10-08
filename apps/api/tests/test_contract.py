import json
from pathlib import Path

from app.main import app


def test_current_contract_matches_source() -> None:
    root = Path(__file__).resolve().parents[3]
    expected = json.loads((root / "openapi/m4.openapi.json").read_text(encoding="utf-8"))
    assert app.openapi() == expected


def test_m1_paths_and_schemas_remain_compatible() -> None:
    root = Path(__file__).resolve().parents[3]
    baseline = json.loads((root / "openapi/m1.openapi.json").read_text(encoding="utf-8"))
    current = app.openapi()
    for name, definition in baseline["paths"].items():
        assert current["paths"][name] == definition
    for name, definition in baseline["components"]["schemas"].items():
        assert current["components"]["schemas"][name] == definition


def test_m2_paths_and_schemas_remain_compatible() -> None:
    root = Path(__file__).resolve().parents[3]
    baseline = json.loads((root / "openapi/m2.openapi.json").read_text(encoding="utf-8"))
    current = app.openapi()
    for name, definition in baseline["paths"].items():
        assert current["paths"][name] == definition
    for name, definition in baseline["components"]["schemas"].items():
        assert current["components"]["schemas"][name] == definition


def test_m3_paths_and_schemas_remain_compatible() -> None:
    root = Path(__file__).resolve().parents[3]
    baseline = json.loads((root / "openapi/m3.openapi.json").read_text(encoding="utf-8"))
    current = app.openapi()
    for name, definition in baseline["paths"].items():
        assert current["paths"][name] == definition
    for name, definition in baseline["components"]["schemas"].items():
        assert current["components"]["schemas"][name] == definition
