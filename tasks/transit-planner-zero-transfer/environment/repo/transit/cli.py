"""Plan a trip from the command line.

    python -m transit.cli Harbor Museum
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .network import Network, load_network
from .router import NoRouteError, Route, UnknownStationError, plan

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "network.json"


def describe(route: Route, network: Network) -> list[str]:
    """Turn a route into one line per ride segment or change."""
    lines: list[str] = []
    ride: list = []  # consecutive ride legs on the same line

    def flush() -> None:
        if not ride:
            return
        first, last = network.stops[ride[0].origin], network.stops[ride[-1].target]
        total = sum(leg.minutes for leg in ride)
        lines.append(f"  {first.line} line: {first.station} -> {last.station} ({total:g} min)")
        ride.clear()

    for leg in route.legs:
        if leg.kind == "ride":
            ride.append(leg)
            continue
        flush()
        a, b = network.stops[leg.origin], network.stops[leg.target]
        if a.station == b.station:
            lines.append(f"  change at {a.station}: {a.line} -> {b.line} ({leg.minutes:g} min)")
        else:
            lines.append(f"  walk {a.station} -> {b.station} ({leg.minutes:g} min)")
    flush()
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan the fastest metro trip.")
    parser.add_argument("origin")
    parser.add_argument("destination")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="network JSON file")
    args = parser.parse_args(argv)

    network = load_network(args.data)
    try:
        route = plan(network, args.origin, args.destination)
    except UnknownStationError as exc:
        print(f"error: unknown station {exc.args[0]!r}", file=sys.stderr)
        return 1
    except NoRouteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    changes = "change" if route.transfers == 1 else "changes"
    print(f"{args.origin} -> {args.destination}: {route.total_minutes:g} min, "
          f"{route.transfers} {changes}")
    for line in describe(route, network):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
