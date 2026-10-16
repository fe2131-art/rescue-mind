"""Deterministic 4-neighbor A* planner for *offline* grid simulation."""
from __future__ import annotations
import heapq
from dataclasses import dataclass

Coord = tuple[int, int]

@dataclass
class Grid:
    width: int
    height: int
    walls: set[Coord]

    def free(self, point: Coord) -> bool:
        x, y = point
        return 0 <= x < self.width and 0 <= y < self.height and point not in self.walls

    def neighbors(self, point: Coord) -> list[Coord]:
        x, y = point
        return [p for p in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)) if self.free(p)]


def astar(grid: Grid, start: Coord, target: Coord) -> list[Coord]:
    if not grid.free(start) or not grid.free(target):
        return []
    frontier = [(0, 0, start)]
    parent: dict[Coord, Coord | None] = {start: None}
    cost: dict[Coord, int] = {start: 0}
    seq = 0
    while frontier:
        _, _, cell = heapq.heappop(frontier)
        if cell == target:
            path = []
            while cell is not None:
                path.append(cell)
                cell = parent[cell]
            return path[::-1]
        for nxt in grid.neighbors(cell):
            c = cost[cell] + 1
            if c < cost.get(nxt, 10**9):
                cost[nxt] = c
                parent[nxt] = cell
                seq += 1
                priority = c + abs(nxt[0] - target[0]) + abs(nxt[1] - target[1])
                heapq.heappush(frontier, (priority, seq, nxt))
    return []


def rescue_grid() -> Grid:
    w, h = 24, 15
    walls = {(x, 0) for x in range(w)} | {(x, h-1) for x in range(w)}
    walls |= {(0, y) for y in range(h)} | {(w-1, y) for y in range(h)}
    walls |= {(9, y) for y in range(1, 14) if y not in (4, 11)}
    walls |= {(16, y) for y in range(1, 14) if y not in (7, 12)}
    walls |= {(x, 8) for x in range(2, 6)}
    return Grid(w, h, walls)
