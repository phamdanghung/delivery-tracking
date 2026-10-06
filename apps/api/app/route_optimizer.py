"""OR-Tools core: all stops are mandatory; objectives are solved in strict priority."""

from dataclasses import dataclass
from time import monotonic

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class TravelMatrix:
    # Index 0 is start, indices 1..N are stops, index N+1 is end.
    distances_m: tuple[tuple[int | None, ...], ...]
    durations_s: tuple[tuple[int | None, ...], ...]

    def validate(self, size: int) -> None:
        for values in (self.distances_m, self.durations_s):
            if len(values) != size or any(len(row) != size for row in values):
                raise ValueError("Matrix shape does not match start/stops/end")
            if any(
                value is not None and (type(value) is not int or value < 0)
                for row in values
                for value in row
            ):
                raise ValueError("Matrix values must be nonnegative integer units or unreachable")


@dataclass(frozen=True)
class StopWindow:
    lower_s: int | None
    upper_s: int
    service_s: int

    def validate(self) -> None:
        if self.service_s < 0 or (self.lower_s is not None and self.lower_s > self.upper_s):
            raise ValueError("Invalid service duration or time window")


@dataclass(frozen=True)
class RouteSolution:
    order: tuple[int, ...]
    arrivals_s: tuple[int, ...]  # Same order as input stops, relative to departure.
    violated: tuple[int, ...]
    distance_m: int
    elapsed_s: int
    proven_objectives: tuple[bool, ...]
    solver_seconds: float


class NoRoute(ValueError):
    """No complete route is available; never silently drop a delivery."""


def optimize_route(
    matrix: TravelMatrix, stops: tuple[StopWindow, ...], *, time_limit_s: float
) -> RouteSolution:
    if not stops or time_limit_s <= 0:
        raise ValueError("At least one stop and a positive solver budget are required")
    size = len(stops) + 2
    matrix.validate(size)
    for stop in stops:
        stop.validate()
    durations = [value for row in matrix.durations_s for value in row if value is not None]
    horizon = max(0, *(stop.upper_s for stop in stops)) + sum(s.service_s for s in stops)
    horizon += (size - 1) * max(durations, default=0) + 1
    distances = [value for row in matrix.distances_m for value in row if value is not None]
    if horizon >= 2**60 or (size - 1) * max(distances, default=0) >= 2**60:
        raise ValueError("Input exceeds safe integer solver range")
    model = cp_model.CpModel()
    arrival = [model.new_int_var(0, horizon, f"arrival_{i}") for i in range(size)]
    model.add(arrival[0] == 0)
    arcs = {}
    distance_terms: list[cp_model.LinearExpr] = []
    # Closing arc is bookkeeping only. End/start points may be different coordinates.
    circuit = [(size - 1, 0, model.new_constant(1))]
    for i in range(size - 1):
        for j in range(1, size):
            if i == j or (i == 0 and j == size - 1):
                continue
            duration, distance = matrix.durations_s[i][j], matrix.distances_m[i][j]
            if duration is None or distance is None:
                continue
            arc = model.new_bool_var(f"arc_{i}_{j}")
            arcs[i, j] = arc
            distance_terms.append(distance * arc)
            circuit.append((i, j, arc))
            service = 0 if i == 0 else stops[i - 1].service_s
            model.add(arrival[j] >= arrival[i] + service + duration).only_enforce_if(arc)
    model.add_circuit(circuit)
    violations = []
    for i, stop in enumerate(stops, 1):
        late = model.new_bool_var(f"late_{i}")
        model.add(arrival[i] > stop.upper_s).only_enforce_if(late)
        model.add(arrival[i] <= stop.upper_s).only_enforce_if(late.Not())
        early = model.new_bool_var(f"early_{i}")
        if stop.lower_s is None:
            model.add(early == 0)
        else:
            model.add(arrival[i] < stop.lower_s).only_enforce_if(early)
            model.add(arrival[i] >= stop.lower_s).only_enforce_if(early.Not())
        violated = model.new_bool_var(f"violated_{i}")
        model.add(violated == early + late)
        violations.append(violated)
    distance_cost = cp_model.LinearExpr.sum(distance_terms)
    objectives = (sum(violations), distance_cost, arrival[-1])
    started = monotonic()
    proven = []
    last = None
    for phase, objective in enumerate(objectives):
        remaining = time_limit_s - (monotonic() - started)
        if remaining <= 0:
            break
        model.minimize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining / (len(objectives) - phase)
        solver.parameters.num_search_workers = 1
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if last is None:
                raise NoRoute("No complete route within solver budget or road constraints")
            break
        proven.append(status == cp_model.OPTIMAL)
        next_point = {i: j for (i, j), arc in arcs.items() if solver.value(arc)}
        order = []
        current = next_point[0]
        while current != size - 1:
            order.append(current)
            current = next_point[current]
        if len(order) != len(stops) or len(set(order)) != len(stops):
            raise NoRoute("Solver did not return every stop exactly once")
        last = RouteSolution(
            tuple(order),
            tuple(int(solver.value(v)) for v in arrival[1:-1]),
            tuple(i + 1 for i, v in enumerate(violations) if solver.value(v)),
            int(solver.value(distance_cost)),
            int(solver.value(arrival[-1])),
            tuple(proven),
            monotonic() - started,
        )
        # Never trade an unproven higher-priority objective for distance/time.
        if status != cp_model.OPTIMAL:
            break
        model.add(objective == int(solver.value(objective)))
    if last is None:
        raise NoRoute("Solver budget expired before a complete route")
    return last
