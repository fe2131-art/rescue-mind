"""I-21 phase 2: a supply-station set of any size k (the arena has k = 2, the relief depot k = 4).

A station is an id with a centre, an approach waypoint and the supply the *inventory* says it holds.  The intent still
asks for 'water' or 'medicine'.  The inventory fixes the candidate order for a request: first the stations listed for
that supply (in id order), then all the others (the supply may have been moved).  The robot visits the candidates in that
order, checks each one on site, and never skips one: the recovery search continues to the next candidate until a check
confirms the supply or all k candidates have been checked (k - 1 more checks at most), then it stops and reports.
Memory / advice may REORDER the candidates (rescuemind.mission_memory, rescuemind.advice); they never remove one.

The default (no 'stations' block in the waypoint config) is the two-station arena with ids 'water' and 'medicine':
water -> [water, medicine], medicine -> [medicine, water], exactly the one-time "check the other station" search.

Per-run configuration format (extends I-17 / Study L --config and --centers; all keys of the old format stay valid):
  waypoints.json : {"initial": [..], "<id>": [wx, wy] for every station id, "B": [..], "physical_pickup": false, ...,
                    "stations": {"ids": ["W1", "M1", "W2", "M2"],
                                 "inventory": {"W1": "water", "M1": "medicine", "W2": "water", "M2": "medicine"}}}
  station_centers.json : {"<id>": [cx, cy] for every station id}
Pure functions: no ROS, no Gazebo.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

SUPPLIES = ('water', 'medicine')
LEGACY_IDS = ('water', 'medicine')
MAX_STATIONS = 8
RESERVED = {'initial', 'B', 'limits', 'physical_pickup', 'meaning', 'reference', 'stations', 'waypoints'}


def _finite_xy(xy) -> bool:
    return (isinstance(xy, (list, tuple)) and len(xy) == 2
            and all(type(v) in (int, float) and math.isfinite(v) for v in xy))


@dataclass(frozen=True)
class StationSet:
    ids: tuple
    inventory: tuple        # ((station id, supply), ...) in the order of `ids`

    # ------------------------------------------------------------ construction
    @staticmethod
    def legacy() -> 'StationSet':
        return StationSet(LEGACY_IDS, tuple((s, s) for s in LEGACY_IDS))

    @staticmethod
    def build(ids, inventory: dict) -> 'StationSet':
        ids = tuple(ids)
        if not (2 <= len(ids) <= MAX_STATIONS) or len(set(ids)) != len(ids):
            raise ValueError('a station set needs 2..%d distinct ids' % MAX_STATIONS)
        for s in ids:
            if not isinstance(s, str) or not s or s in RESERVED or s != s.strip():
                raise ValueError(f'bad station id: {s!r}')
        if not isinstance(inventory, dict) or set(inventory) != set(ids):
            raise ValueError('inventory must list exactly the station ids')
        if any(v not in SUPPLIES for v in inventory.values()):
            raise ValueError('inventory supplies must be water or medicine')
        for item in SUPPLIES:
            if item not in inventory.values():
                raise ValueError(f'inventory lists no station for {item}')
        return StationSet(ids, tuple((s, inventory[s]) for s in ids))

    @staticmethod
    def from_config(cfg: dict | None) -> 'StationSet':
        """From a waypoint config (None / no 'stations' block -> the two-station arena)."""
        block = (cfg or {}).get('stations')
        if block is None:
            return StationSet.legacy()
        if not isinstance(block, dict) or set(block) - {'ids', 'inventory'}:
            raise ValueError("'stations' must have keys ids and inventory")
        ss = StationSet.build(block.get('ids') or (), block.get('inventory'))
        for s in ss.ids:
            if not _finite_xy(cfg.get(s)):
                raise ValueError(f'waypoint of station {s} missing or not a finite [x, y]')
        return ss

    # ------------------------------------------------------------ queries
    @property
    def k(self) -> int:
        return len(self.ids)

    def supply(self, station: str) -> str:
        return dict(self.inventory)[station]

    def is_legacy(self) -> bool:
        return self == StationSet.legacy()

    def default_order(self, item: str) -> list:
        """The inventory's candidate order for `item`: its listed stations first, then every other station."""
        if item not in SUPPLIES:
            raise ValueError('unknown supply')
        listed = [s for s, v in self.inventory if v == item]
        return listed + [s for s in self.ids if s not in listed]

    def catalog(self, item: str) -> str:
        """The station the inventory lists first for `item` (the 'own' station in the arena)."""
        return self.default_order(item)[0]

    def order(self, item: str, first: str | None = None) -> list:
        """Candidate order for `item`; `first` (memory / advice) is moved to the front, the rest keep their order."""
        base = self.default_order(item)
        if first is None:
            return base
        if first not in base:
            raise ValueError(f'unknown station {first}')
        return [first] + [s for s in base if s != first]

    def resolve(self, name: str | None) -> str | None:
        """A station id, or a supply name ('water' / 'medicine', e.g. from the operator's text) -> the id."""
        if name is None or name in self.ids:
            return name
        if name in SUPPLIES:
            return self.catalog(name)
        raise ValueError(f'unknown station {name}')

    def to_block(self) -> dict:
        return {'ids': list(self.ids), 'inventory': dict(self.inventory)}


def next_candidate(order, checked) -> str | None:
    """The next station of `order` that has not been checked yet (None when all were checked).  Strictly the first
    unchecked one: a recovery search can never skip a candidate."""
    done = set(checked)
    for s in order:
        if s not in done:
            return s
    return None


def validate_visits(order, visited) -> None:
    """The stations a recovery run visited, in the order visited, must be a prefix of the candidate order: no skipped
    candidate, no repeat, no station outside the set.  Raises ValueError."""
    order, visited = list(order), list(visited)
    if len(set(visited)) != len(visited):
        raise ValueError('a station was checked twice')
    if visited != order[:len(visited)]:
        raise ValueError(f'visited {visited} is not a prefix of the candidate order {order} (skipped or reordered candidate)')


def max_checks(order) -> int:
    """At most k checks per request (the first one plus k - 1 recovery checks)."""
    return len(list(order))


def check_centers(centers: dict, ss: StationSet) -> None:
    """The per-run centres (rescuemind.camera_aim.station_centers output) must cover exactly the station set."""
    if set(centers) != set(ss.ids):
        raise ValueError(f'station centres {sorted(centers)} do not match the station set {sorted(ss.ids)}')


def plan_order(plan: dict | None, ss: StationSet, item: str) -> list:
    """The candidate order the robot follows: the plan's logged 'order' (k > 2), else the plan's first station moved to
    the front of the inventory order (the arena's logs carry no 'order')."""
    plan = plan or {}
    if plan.get('order'):
        order = list(plan['order'])
        if sorted(order) != sorted(ss.ids):
            raise ValueError('plan order is not a permutation of the station set (a candidate was dropped)')
        return order
    return ss.order(item, plan.get('first_station'))
