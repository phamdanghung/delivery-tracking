"""Deterministic matrix fixtures test the real OR-Tools solver, not live map accuracy."""

import pytest

from app.route_optimizer import NoRoute, StopWindow, TravelMatrix, optimize_route


def pair_matrix(short_time=10, long_time=1, long_distance=5):
    distances = (
        (0, 1, long_distance, 1),
        (1, 0, 1, long_distance),
        (1, long_distance, 0, 1),
        (1, 1, 1, 0),
    )
    times = (
        (0, short_time, long_time, 1),
        (1, 0, short_time, long_time),
        (1, long_time, 0, short_time),
        (1, 1, 1, 0),
    )
    return TravelMatrix(distances, times)


def test_at04_on_time_before_shorter_distance():
    result = optimize_route(
        pair_matrix(), (StopWindow(None, 100, 0), StopWindow(None, 5, 0)), time_limit_s=2
    )
    assert result.order == (2, 1)
    assert result.violated == ()
    assert result.distance_m == 15  # The 3m alternative violates the second customer's deadline.
    assert result.proven_objectives == (True, True, True)


def test_kilometers_before_faster_route():
    result = optimize_route(
        pair_matrix(long_distance=2), (StopWindow(None, 100, 0),) * 2, time_limit_s=2
    )
    assert result.order == (1, 2)
    assert (result.distance_m, result.elapsed_s) == (3, 30)


def test_duration_breaks_equal_distance_tie():
    result = optimize_route(
        pair_matrix(long_distance=1), (StopWindow(None, 100, 0),) * 2, time_limit_s=2
    )
    assert result.order == (2, 1)
    assert (result.distance_m, result.elapsed_s) == (3, 3)


def test_fixed_window_waiting_and_service_before_next_deadline():
    rows = tuple(tuple(0 if i == j else 1 for j in range(4)) for i in range(4))
    result = optimize_route(
        TravelMatrix(rows, rows),
        (StopWindow(100, 100, 10), StopWindow(111, 112, 0)),
        time_limit_s=2,
    )
    assert result.violated == ()
    assert result.arrivals_s == (100, 111)
    assert result.elapsed_s == 112


def test_impossible_commitments_report_every_stop_instead_of_dropping():
    result = optimize_route(pair_matrix(), (StopWindow(None, -1, 0),) * 2, time_limit_s=2)
    assert set(result.order) == {1, 2}
    assert result.violated == (1, 2)


@pytest.mark.parametrize("fleet_size", [3, 4])
def test_multiple_vehicles_without_fixed_fleet_size(fleet_size):
    # Preserve trip assignments; never move a customer's order to another vehicle implicitly.
    for _ in range(fleet_size):
        result = optimize_route(pair_matrix(), (StopWindow(None, 100, 0),) * 2, time_limit_s=2)
        assert len(result.order) == 2 and result.violated == ()


def test_unreachable_stop_does_not_become_a_silent_partial_route():
    values = ((0, None, None), (None, 0, None), (None, None, 0))
    with pytest.raises(NoRoute):
        optimize_route(TravelMatrix(values, values), (StopWindow(None, 100, 0),), time_limit_s=1)


def test_validate_shape_units_and_windows():
    with pytest.raises(ValueError, match="shape"):
        optimize_route(TravelMatrix(((0,),), ((0,),)), (StopWindow(None, 10, 0),), time_limit_s=1)
    rows = ((0, 1, 1), (1, 0, 1), (1, 1, 0))
    with pytest.raises(ValueError, match="window"):
        optimize_route(TravelMatrix(rows, rows), (StopWindow(20, 10, 0),), time_limit_s=1)
