"""Simple discrete grid prototype, not Gazebo, ROS, or a physics simulator."""
from __future__ import annotations
from dataclasses import dataclass, field
from .intent import IntentClassifier
from .planner import Grid, Coord, astar, rescue_grid

START = (2, 2)
STATIONS = {"water": (6, 5), "medicine": (6, 11)}
SHELTERS = {"A": (21, 11), "B": (21, 5)}
BLOCKAGE = (9, 4)

@dataclass
class Step:
    position: Coord
    stage: str
    event: str
    planned: list[Coord] = field(default_factory=list)

@dataclass
class Run:
    success: bool
    reason: str
    item: str
    shelter: str
    path_length: int
    replans: int
    blockage_inserted: bool
    history: list[Step]
    classifier: str
    confidence: float


def simulate(instruction: str, mode: str = "adaptive", classifier: IntentClassifier | None = None,
             dynamic_obstacle: bool = True, grid: Grid | None = None) -> Run:
    if mode not in ("adaptive", "fixed"):
        raise ValueError("mode must be adaptive or fixed")
    intent = (classifier or IntentClassifier()).classify(instruction)
    graph = grid if grid is not None else rescue_grid()
    # Copy: never mutate the caller's scenario across repeated trials.
    graph = Grid(graph.width, graph.height, set(graph.walls))
    position = START
    history = [Step(position, "start", "mission_assigned")]
    distance = 0
    replans = 0
    blockage_inserted = False

    def result(ok: bool, why: str) -> Run:
        return Run(ok, why, intent.item, intent.shelter, distance, replans,
                   blockage_inserted, history, intent.classifier, intent.confidence)

    for stage, target in (("pickup", STATIONS[intent.item]), ("deliver", SHELTERS[intent.shelter])):
        path = astar(graph, position, target)
        if not path:
            history.append(Step(position, stage, "no_route"))
            return result(False, "no_route")
        history.append(Step(position, stage, "route_planned", path))
        moved = 0
        while position != target:
            if stage == "deliver" and dynamic_obstacle and not blockage_inserted and moved >= 2:
                graph.walls.add(BLOCKAGE)
                blockage_inserted = True
                history.append(Step(position, stage, "dynamic_blockage_added"))
            if len(path) <= 1:
                return result(False, "empty_path")
            following = path[1]
            if not graph.free(following):
                if mode == "fixed":
                    history.append(Step(position, stage, "blocked_fixed_route"))
                    return result(False, "blocked")
                path = astar(graph, position, target)
                replans += 1
                history.append(Step(position, stage, "route_replanned", path))
                if not path:
                    return result(False, "no_detour")
                following = path[1]
            position = following
            path = path[1:]
            moved += 1
            distance += 1
            history.append(Step(position, stage, "moved"))
        history.append(Step(position, stage, "pickup_complete" if stage == "pickup" else "delivery_complete"))
    return result(True, "delivered")
