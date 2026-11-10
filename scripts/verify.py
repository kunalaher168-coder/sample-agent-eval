#!/usr/bin/env python3
"""Grade a patch against the transit-planner-zero-transfer task on a clean copy.

This is the local mirror of tasks/<slug>/tests/test.sh. It copies the
starter repo to a temporary folder, applies a patch to the copy, adds the
hidden tests from environment/test.patch, and runs the FAIL_TO_PASS and
PASS_TO_PASS lists from tests/test_metadata.json: the repo's own tests
inside the repo copy, and the hidden tests from a separate copy outside it,
with the same pytest options as test.sh. Unlike test.sh in the task image,
it does not switch to a separate agent user. Nothing in the repository
changes, except runs/<agent>/grading.json with --write.

    python scripts/verify.py                     # summary: starter, oracle, every run
    python scripts/verify.py --target starter    # the repo as given (bug present)
    python scripts/verify.py --target oracle     # the reference fix in solution/solve.sh
    python scripts/verify.py --run runs/agent-b  # one recorded run
    python scripts/verify.py --patch my_fix.diff # any patch made against the starter repo
    python scripts/verify.py --check             # exit 1 if a stored grading.json is out of date
    python scripts/verify.py --write             # rewrite every runs/<agent>/grading.json

Needs Python 3.11+, git, and pytest (pip install pytest==8.4.1).
Exit code is 0 when the target earns reward 1 (or, with --check, when every
stored grading.json matches a fresh run).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = "transit-planner-zero-transfer"
TASK = ROOT / "tasks" / SLUG
STARTER = TASK / "environment" / "repo"
TEST_PATCH = TASK / "environment" / "test.patch"
METADATA = TASK / "tests" / "test_metadata.json"
SOLVE_SH = TASK / "solution" / "solve.sh"
RUNS = ROOT / "runs"
HIDDEN_FILE = "tests/test_transfers.py"
PYTEST_OPTIONS = ["-rA", "-p", "no:cacheprovider", "--noconftest", "-o", "addopts=", "--import-mode=append"]
EXPECTED_REWARD = {"starter": 0, "oracle": 1}


def node_id(name: str) -> str:
    """'tests.test_transfers.Cls::test_x' (test_metadata.json) -> pytest node id."""
    dotted, test = name.split("::")
    module, cls = dotted.rsplit(".", 1)
    return f"{module.replace('.', '/')}.py::{cls}::{test}"


def golden_patch_text() -> str:
    text = SOLVE_SH.read_text(encoding="utf-8")
    match = re.search(r"<< '__SOLUTION__'\n(.*?)^__SOLUTION__$", text, re.S | re.M)
    if not match:
        sys.exit("could not find the patch in solution/solve.sh")
    return match.group(1)


def _git_apply(repo: Path, patch: Path) -> None:
    applied = subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch.resolve())],
                             cwd=repo, capture_output=True, text=True)
    if applied.returncode != 0:
        sys.exit(f"could not apply {patch.name}:\n{applied.stderr}")


def _outcomes(stdout: str) -> dict[str, tuple[str, str | None]]:
    """Read the pytest -rA short summary: 'FAILED <node id> - <message>'."""
    found: dict[str, tuple[str, str | None]] = {}
    for line in stdout.splitlines():
        match = re.match(r"^(PASSED|FAILED|ERROR) (\S+)(?: - (.*))?$", line)
        if match:
            status, node, message = match.groups()
            found[node] = (status.lower(), message.strip() if message else None)
    return found


def grade(patch: Path | None, label: str) -> dict:
    meta = json.loads(METADATA.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(STARTER, repo, ignore=shutil.ignore_patterns("__pycache__"))
        if patch is not None:
            _git_apply(repo, patch)
        (repo / HIDDEN_FILE).unlink(missing_ok=True)  # same reset as tests/test.sh
        _git_apply(repo, TEST_PATCH)
        hidden = Path(tmp) / "hidden"  # same copy outside the repo as tests/test.sh
        (hidden / "tests").mkdir(parents=True)
        (hidden / "tests" / "__init__.py").write_text("", encoding="utf-8")
        shutil.copyfile(repo / HIDDEN_FILE, hidden / HIDDEN_FILE)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", COLUMNS="200", TRANSIT_REPO=str(repo))
        env.pop("TRANSIT_PROBE_PREFIX", None)
        ids = [node_id(n) for n in meta["FAIL_TO_PASS"] + meta["PASS_TO_PASS"]]
        stdout = ""
        for cwd, group in ((repo, [i for i in ids if not i.startswith(HIDDEN_FILE)]),
                           (hidden, [i for i in ids if i.startswith(HIDDEN_FILE)])):
            run = subprocess.run([sys.executable, "-P", "-m", "pytest", *PYTEST_OPTIONS, *group],
                                 cwd=cwd, capture_output=True, text=True, env=env)
            stdout += run.stdout
    found = _outcomes(stdout)

    def group(names: list[str]) -> dict:
        tests = []
        for name in sorted(names, key=node_id):
            outcome, message = found.get(node_id(name), ("missing", "test was not collected"))
            entry = {"id": node_id(name), "outcome": outcome}
            if message:
                entry["message"] = message
            tests.append(entry)
        passed = sum(1 for t in tests if t["outcome"] == "passed")
        return {"passed": passed, "total": len(tests), "tests": tests}

    f2p, p2p = group(meta["FAIL_TO_PASS"]), group(meta["PASS_TO_PASS"])
    resolved = f2p["passed"] == f2p["total"] and p2p["passed"] == p2p["total"]
    return {
        "task": SLUG,
        "target": label,
        "grader": f"tasks/{SLUG}/tests/test.sh (local mirror: scripts/verify.py)",
        "reward": 1 if resolved else 0,
        "fail_to_pass": f2p,
        "pass_to_pass": p2p,
    }


def runs() -> list[Path]:
    return sorted(p for p in RUNS.iterdir() if (p / "patch.diff").is_file())


def grade_run(run: Path) -> dict:
    return grade(run / "patch.diff", f"runs/{run.name}/patch.diff")


def grade_named(target: str) -> dict:
    if target == "starter":
        return grade(None, "starter repo as given")
    with tempfile.TemporaryDirectory() as tmp:
        patch = Path(tmp) / "golden.diff"
        patch.write_text(golden_patch_text(), encoding="utf-8", newline="\n")
        return grade(patch, "solution/solve.sh")


def ratio(group: dict) -> str:
    return f"{group['passed']}/{group['total']}"


def show(result: dict) -> None:
    print(f"\nTarget: {result['target']}")
    for name in ("fail_to_pass", "pass_to_pass"):
        for t in result[name]["tests"]:
            print(f"  {t['outcome'].upper():<7} [{name}] {t['id']}")
            if "message" in t:
                print(f"          {t['message']}")
    print(f"FAIL_TO_PASS {ratio(result['fail_to_pass'])}, PASS_TO_PASS {ratio(result['pass_to_pass'])}, "
          f"reward {result['reward']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--target", choices=["starter", "oracle"])
    target.add_argument("--run", type=Path, help="a runs/<agent> folder")
    target.add_argument("--patch", type=Path, help="any patch made against environment/repo")
    target.add_argument("--check", action="store_true", help="compare stored grading.json with fresh runs")
    target.add_argument("--write", action="store_true", help="rewrite runs/<agent>/grading.json")
    args = parser.parse_args()

    if args.target or args.run or args.patch:
        if args.target:
            result = grade_named(args.target)
        elif args.run:
            result = grade_run(args.run.resolve())
        else:
            result = grade(args.patch, str(args.patch))
        show(result)
        return 0 if result["reward"] == 1 else 1
    if args.write:
        for run in runs():
            path = run / "grading.json"
            path.write_text(json.dumps(grade_run(run), indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
        return 0

    problems, rows = [], []
    for name in ("starter", "oracle"):
        result = grade_named(name)
        rows.append((name, result))
        if result["reward"] != EXPECTED_REWARD[name]:
            problems.append(f"{name}: reward {result['reward']}, expected {EXPECTED_REWARD[name]}")
    for run in runs():
        result = grade_run(run)
        rows.append((f"runs/{run.name}", result))
        path = run / "grading.json"
        stored = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        if result != stored:
            problems.append(f"runs/{run.name}/grading.json does not match a fresh run")

    print(f"{'target':24}{'FAIL_TO_PASS':>14}{'PASS_TO_PASS':>14}{'reward':>8}")
    for label, result in rows:
        print(f"{label:24}{ratio(result['fail_to_pass']):>14}{ratio(result['pass_to_pass']):>14}"
              f"{result['reward']:>8}")
    if args.check:
        for problem in problems:
            print(f"MISMATCH {problem}")
        print("CHECK " + ("FAILED" if problems else "OK"))
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
