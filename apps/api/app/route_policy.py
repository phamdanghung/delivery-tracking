import math
from datetime import datetime, timedelta
from typing import Any

from app.config import Settings
from app.route_optimizer import StopWindow


def time_window(
    stop: dict[str, Any], departure: datetime, service: int, settings: Settings
) -> tuple[StopWindow, datetime | None, datetime]:
    if type(service) is not int or service < 0:
        raise ValueError("Service time phải là số giây nguyên không âm")
    lower = None
    match stop["commitment_type"]:
        case "FIXED_TIME":
            tolerance = timedelta(seconds=settings.fixed_time_tolerance_seconds)
            lower, upper = stop["appointment_at"] - tolerance, stop["appointment_at"] + tolerance
        case "TIME_WINDOW":
            lower, upper = stop["window_start"], stop["window_end"]
        case "BEFORE_DEADLINE":
            upper = stop["deadline_at"]
        case _:
            raise ValueError("Cam kết thời gian không hợp lệ")
    if upper is None or (stop["commitment_type"] != "BEFORE_DEADLINE" and lower is None):
        raise ValueError("Thiếu giờ hẹn khách")
    window = StopWindow(
        None if lower is None else math.ceil((lower - departure).total_seconds()),
        math.floor((upper - departure).total_seconds()),
        service,
    )
    window.validate()
    return window, lower, upper
