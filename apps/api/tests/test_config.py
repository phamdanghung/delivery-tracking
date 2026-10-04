from pathlib import Path

from app.config import Settings


def test_example_environment_parses_with_cors_json():
    example = Path(__file__).resolve().parents[3] / ".env.example"
    settings = Settings(_env_file=example)
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.app_env == "local"
