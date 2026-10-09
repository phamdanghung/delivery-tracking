import json
from pathlib import Path

from app.main import app


def test_current_contract_matches_source() -> None:
    root = Path(__file__).resolve().parents[3]
    expected = json.loads((root / "openapi/m5.openapi.json").read_text(encoding="utf-8"))
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


def test_m4_commands_are_preserved_with_additive_pod_action() -> None:
    root = Path(__file__).resolve().parents[3]
    baseline = json.loads((root / "openapi/m4.openapi.json").read_text(encoding="utf-8"))
    current = app.openapi()
    for name, definition in baseline["paths"].items():
        if name == "/api/v1/driver/actions":
            before = definition["post"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["anyOf"]
            after = current["paths"][name]["post"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["anyOf"]
            assert all(item in after for item in before)
        else:
            assert current["paths"][name] == definition
    for name, definition in baseline["components"]["schemas"].items():
        if name == "OfflineCommand":
            before_action = definition["properties"]["action"]
            after = current["components"]["schemas"][name]
            after_action = after["properties"]["action"]
            assert all(item in after_action["oneOf"] for item in before_action["oneOf"])
            assert (
                before_action["discriminator"]["mapping"].items()
                <= after_action["discriminator"]["mapping"].items()
            )
            for field, value in definition["properties"].items():
                if field != "action":
                    assert after["properties"][field] == value
            assert after["required"] == definition["required"]
        else:
            assert current["components"]["schemas"][name] == definition
