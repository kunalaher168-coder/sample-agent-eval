# agent-a: Real Session

| Item | Detail |
| --- | --- |
| Agent | A CLI coding agent, run non-interactively with its default settings |
| Input | The prompt in [instruction.md](../../tasks/transit-planner-zero-transfer/instruction.md), run in a fresh copy of the starter repo with a one-commit git history |
| Record | The agent's real session log (JSON) converted to Markdown. Paths are shortened to `~/transit-planner`, outputs longer than 60 lines are cut, and punctuation is converted to plain ASCII. No words are edited, added, or reordered. |
| Run | 7 tool calls, about 26 seconds. The agent wrote no text between tool calls; its only message is the final one. |
| Patch | [patch.diff](patch.diff): `transit/network.py` +4/-1, `tests/test_router.py` +15/-1 |
| Grading | FAIL_TO_PASS 5/5, PASS_TO_PASS 11/11, reward 1 ([grading.json](grading.json)) |
| Score | **4 of 5** (see [evaluation.md](../../evaluation.md)) |

## Prompt

> Got a couple of complaints that the trip planner picks weird routes. Someone going Harbor -> Museum was told to stay on the Green line, and they say that's slower. Times also look a few minutes off sometimes. Can you take a look and fix it?

## Session

#### Step 1: Bash

```bash
git log --oneline | head && find . -type f -not -path './.git/*' | head -50
```

<details><summary>Output</summary>

```
b960aa5 start
./README.md
./transit/cli.py
./transit/__init__.py
./transit/router.py
./transit/network.py
./tests/__init__.py
./tests/test_router.py
./data/network.json
```

</details>


#### Step 2: Bash

```bash
cat README.md transit/*.py tests/test_router.py data/network.json
```

<details><summary>Output</summary>

````
# transit

A small journey planner for a made-up city metro. It loads the network from
`data/network.json` and finds the fastest trip between two stations.

```bash
python -m transit.cli Harbor Museum
python -m unittest
```

No third-party dependencies; Python 3.10+.
"""A small journey planner for a made-up city metro."""

from .network import DEFAULT_TRANSFER_MINUTES, Link, Network, Stop, build_network, load_network
from .router import Leg, NoRouteError, Route, UnknownStationError, plan

__all__ = [
    "DEFAULT_TRANSFER_MINUTES",
    "Leg",
    "Link",
    "Network",
    "NoRouteError",
    "Route",
    "Stop",
    "UnknownStationError",
    "build_network",
    "load_network",
    "plan",
]
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
... (305 more lines)
````

</details>


#### Step 3: Bash

```bash
python -m transit.cli Harbor Museum; python -m transit.cli Market University; python -m unittest 2>&1 | tail -3
```

<details><summary>Output</summary>

```
Harbor -> Museum: 19 min, 0 changes
  Green line: Harbor -> Museum (19 min)
Market -> University: 12 min, 1 change
  Red line: Market -> Central (4 min)
  change at Central: Red -> Blue (4 min)
  Blue line: Central -> University (4 min)
Ran 8 tests in 0.001s

OK
```

</details>


#### Step 4: Edit `~/transit-planner/transit/network.py`

```diff
-         minutes = raw.get("minutes") or DEFAULT_TRANSFER_MINUTES
+         # Only fall back when the time is absent; 0 is a real (same-platform) transfer.
+         minutes = raw.get("minutes")
+         if minutes is None:
+             minutes = DEFAULT_TRANSFER_MINUTES
```


#### Step 5: Edit `~/transit-planner/tests/test_router.py`

```diff
-     def test_same_station_is_an_empty_route(self):
+     def test_harbor_to_museum_prefers_red_blue_over_green(self):
+         # Red 9 + free change at Central + Blue 8 = 17, beats Green's 19.
+         route = plan(self.network, "Harbor", "Museum")
+         self.assertEqual(route.total_minutes, 17)
+         self.assertEqual(route.transfers, 1)
+ 
+     def test_zero_minute_transfer_is_kept(self):
+         route = plan(self.network, "Market", "University")
+         self.assertEqual(route.total_minutes, 8)
+ 
+     def test_missing_transfer_time_uses_default(self):
+         transfers = [l for l in self.network.links_from("riverside_r") if l.kind == "transfer"]
+         self.assertEqual([l.minutes for l in transfers], [DEFAULT_TRANSFER_MINUTES])
+ 
+     def test_same_station_is_an_empty_route(self):
```


#### Step 6: Edit `~/transit-planner/tests/test_router.py`

```diff
- from transit import NoRouteError,
+ from transit import DEFAULT_TRANSFER_MINUTES, NoRouteError,
```


#### Step 7: Bash

```bash
python -m transit.cli Harbor Museum; python -m transit.cli Market University; python -m unittest 2>&1 | tail -3; git diff --stat
```

<details><summary>Output</summary>

```
Harbor -> Museum: 17 min, 1 change
  Red line: Harbor -> Central (9 min)
  change at Central: Red -> Blue (0 min)
  Blue line: Central -> Museum (8 min)
Market -> University: 8 min, 1 change
  Red line: Market -> Central (4 min)
  change at Central: Red -> Blue (0 min)
  Blue line: Central -> University (4 min)
Ran 11 tests in 0.001s

OK
 tests/test_router.py | 16 +++++++++++++++-
 transit/network.py   |  5 ++++-
 2 files changed, 19 insertions(+), 2 deletions(-)
```

</details>


**Agent:**

The planner now picks the faster route. Harbor -> Museum goes Red to Central, changes to Blue, and arrives in **17 min**. Before, it said to stay on Green for **19 min**.

**The cause:** the route search itself was fine; the bug was in how the network file is loaded. A missing transfer time is supposed to default to 4 minutes, but the code (`transit/network.py`) also treated a time of `0` as missing. The Red<->Blue change at Central is listed as 0 minutes, so the planner counted it as 4. That made every route through Central 4 minutes too slow:
- **Wrong routes:** Red->Blue came out at 21 min instead of 17, so the 19-min Green route looked faster.
- **Times a few minutes off:** any trip that does change at Central was shown 4 minutes longer than it is. For example, Market -> University showed 12 min instead of 8.

**The fix:** the 4-minute default now applies only when a transfer has no time at all. A real `0` stays 0. The Riverside -> Park walk has no time in the feed, so it still gets the default.

**Tests:** I added three, covering Harbor -> Museum taking Red/Blue in 17 min, the 0-minute change at Central being kept, and a missing transfer time still getting the default. All 11 tests pass. I haven't committed anything.


---

_Run finished: 8 turns, 7 tool calls, 26s._

