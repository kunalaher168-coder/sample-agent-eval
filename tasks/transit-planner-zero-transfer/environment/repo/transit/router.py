"""Fastest-route search over a Network (Dijkstra)."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from .network import Link, Network


class UnknownStationError(LookupError):
    pass


class NoRouteError(LookupError):
    pass


@dataclass(frozen=True)
class Leg:
    origin: str
    target: str
    kind: str
    minutes: float


@dataclass(frozen=True)
class Route:
    legs: tuple[Leg, ...]
    total_minutes: float

    @property
    def transfers(self) -> int:
        return sum(1 for leg in self.legs if leg.kind == "transfer")


def plan(network: Network, origin_station: str, destination_station: str) -> Route:
    """Return the fastest route between two stations.

    A station can have several platforms (one per line). The search starts
    from every platform of the origin and stops at the first platform of
    the destination that comes off the queue.
    """
    starts = network.platforms(origin_station)
    goals = set(network.platforms(destination_station))
    if not starts:
        raise UnknownStationError(origin_station)
    if not goals:
        raise UnknownStationError(destination_station)
    if goals.intersection(starts):
        return Route(legs=(), total_minutes=0.0)

    best = {stop: 0.0 for stop in starts}
    came_from: dict[str, Link] = {}
    queue = [(0.0, stop) for stop in starts]
    heapq.heapify(queue)
    done: set[str] = set()

    while queue:
        minutes, stop = heapq.heappop(queue)
        if stop in done:
            continue
        if stop in goals:
            return Route(legs=_walk_back(came_from, stop), total_minutes=minutes)
        done.add(stop)
        for link in network.links_from(stop):
            candidate = minutes + link.minutes
            if candidate < best.get(link.target, float("inf")):
                best[link.target] = candidate
                came_from[link.target] = link
                heapq.heappush(queue, (candidate, link.target))

    raise NoRouteError(f"no route from {origin_station} to {destination_station}")


def _walk_back(came_from: dict[str, Link], stop: str) -> tuple[Leg, ...]:
    legs = []
    while stop in came_from:
        link = came_from[stop]
        legs.append(Leg(link.origin, link.target, link.kind, link.minutes))
        stop = link.origin
    legs.reverse()
    return tuple(legs)
