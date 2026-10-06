from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.route_policy import time_window
from app.route_schemas import OptimizeInput
from app.routing_provider import RoutingProvider, RoutingUnavailable


def test_fixed_tolerance_config_service_override_and_exact_other_windows():
    departure = datetime(2026, 10, 7, 0, tzinfo=UTC)
    appointment = departure + timedelta(hours=1)
    settings = Settings(_env_file=None)
    fixed = {"commitment_type": "FIXED_TIME", "appointment_at": appointment}
    assert (
        time_window(fixed, departure, settings.default_service_seconds, settings)[0].lower_s == 2700
    )
    assert time_window(fixed, departure, 25, settings)[0].service_s == 25
    settings.fixed_time_tolerance_seconds = 60
    assert time_window(fixed, departure, 25, settings)[0].upper_s == 3660
    window = {
        "commitment_type": "TIME_WINDOW",
        "window_start": appointment,
        "window_end": appointment + timedelta(minutes=30),
    }
    assert time_window(window, departure, 0, settings)[0].lower_s == 3600
    assert time_window(window, departure, 0, settings)[0].upper_s == 5400
    deadline = {"commitment_type": "BEFORE_DEADLINE", "deadline_at": appointment}
    assert time_window(deadline, departure, 0, settings)[0].upper_s == 3600
    assert time_window(deadline, departure, 0, settings)[0].lower_s is None
    with pytest.raises(ValueError):
        time_window(fixed, departure, -1, settings)


def test_explicit_aware_departure_required_no_auto_save_or_override_flag():
    for command in (
        {},
        {"planned_departure_at": "2026-10-07T07:00"},
        {"planned_departure_at": "2026-10-07T07:00+07:00", "override": True},
    ):
        with pytest.raises(ValidationError):
            OptimizeInput.model_validate(command)


def test_provider_requires_configuration_and_dataset(tmp_path):
    with pytest.raises(RoutingUnavailable):
        RoutingProvider(Settings(_env_file=None, osrm_url="", osrm_metadata_path=""))
    provider = RoutingProvider(
        Settings(
            _env_file=None,
            osrm_url="http://127.0.0.1:5000",
            osrm_metadata_path=str(tmp_path / "missing.json"),
        )
    )
    with pytest.raises(RoutingUnavailable, match="metadata"):
        provider.dataset()


def test_unavailable_osrm_is_error_never_straight_line_fallback():
    provider = RoutingProvider(
        Settings(_env_file=None, osrm_url="http://127.0.0.1:1", osrm_timeout_seconds=0.1)
    )
    with pytest.raises(RoutingUnavailable, match="không fallback"):
        provider.matrix([(10.77, 106.69), (10.78, 106.7)])
