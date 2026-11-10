#!/usr/bin/env python3
"""Check the rewards in Harbor job folders.

    harbor run -p tasks/transit-planner-zero-transfer -a oracle -o jobs/oracle
    harbor run -p tasks/transit-planner-zero-transfer -a nop -o jobs/nop
    python scripts/harbor_rewards.py jobs/oracle=1 jobs/nop=0

Reads every trial result.json under each job folder and prints the trial's
reward. Exit code is 0 when each folder has at least one trial and every
trial earned the expected reward.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def trial_rewards(job_dir: Path) -> list[tuple[str, float | None, str | None]]:
    trials = []
    for path in sorted(job_dir.rglob("result.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "trial_name" not in data:
            continue  # job-level summary
        rewards = (data.get("verifier_result") or {}).get("rewards") or {}
        error = (data.get("exception_info") or {}).get("exception_type")
        trials.append((data["trial_name"], rewards.get("reward"), error))
    return trials


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ok = True
    for arg in sys.argv[1:]:
        folder, expected = arg.rsplit("=", 1)
        trials = trial_rewards(Path(folder))
        if not trials:
            print(f"{folder}: no trial results found")
            ok = False
        for name, reward, error in trials:
            good = reward is not None and float(reward) == float(expected)
            ok = ok and good
            note = f", exception {error}" if error else ""
            print(f"{folder}: {name} reward {reward} (expected {expected}){note} -> {'OK' if good else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
