"""Load the metro network from JSON and expose it as a graph of platforms."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Feeds often leave out the time for a walk between platforms.
# When they do, assume a typical platform-to-platform walk.
DEFAULT_TRANSFER_MINUTES = 4.0


@dataclass(frozen=True)
class Stop:
    id: str
    station: str
    line: str


@dataclass(frozen=True)
class Link:
    origin: str
    target: str
    minutes: float
    kind: str  # "ride" or "transfer"


@dataclass
class Network:
    stops: dict[str, Stop] = field(default_factory=dict)
    _adjacent: dict[str, list[Link]] = field(default_factory=dict)

    def add_stop(self, stop: Stop) -> None:
        self.stops[stop.id] = stop
        self._adjacent.setdefault(stop.id, [])

    def add_link(self, link: Link) -> None:
        for end in (link.origin, link.target):
            if end not in self.stops:
                raise KeyError(f"link references unknown stop {end!r}")
        # Every link in the feed can be travelled in both directions.
        self._adjacent[link.origin].append(link)
        self._adjacent[link.target].append(
            Link(link.target, link.origin, link.minutes, link.kind)
        )

    def links_from(self, stop_id: str) -> list[Link]:
        return self._adjacent.get(stop_id, [])

    def platforms(self, station: str) -> list[str]:
        """Stop ids that belong to a station (case-insensitive)."""
        wanted = station.strip().lower()
        return sorted(s.id for s in self.stops.values() if s.station.lower() == wanted)


def _link_minutes(raw: dict) -> float:
    if raw.get("kind") == "transfer":
        minutes = raw.get("minutes") or DEFAULT_TRANSFER_MINUTES
    else:
        minutes = raw["minutes"]
    minutes = float(minutes)
    if minutes < 0:
        raise ValueError(f"negative time on link {raw.get('from')} -> {raw.get('to')}")
    return minutes


def build_network(data: dict) -> Network:
    network = Network()
    for raw in data["stops"]:
        network.add_stop(Stop(id=raw["id"], station=raw["station"], line=raw["line"]))
    for raw in data["links"]:
        network.add_link(
            Link(
                origin=raw["from"],
                target=raw["to"],
                minutes=_link_minutes(raw),
                kind=raw.get("kind", "ride"),
            )
        )
    return network


def load_network(path: str | Path) -> Network:
    with open(path, encoding="utf-8") as fh:
        return build_network(json.load(fh))
