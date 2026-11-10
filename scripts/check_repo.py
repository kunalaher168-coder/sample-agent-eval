#!/usr/bin/env python3
"""Consistency checks for the task and the recorded runs.

    python scripts/check_repo.py

Checks that the grader files agree with each other, that every recorded
patch applies to the starter repo, that each trace.md and trace.json
describe the same steps, that no trace reads the hidden tests or the
reference solution, that the rubric results match the stored grading, and
that every text file is plain ASCII with no private paths or keys.
Test outcomes themselves are checked by scripts/verify.py --check.

Needs Python 3.11+ and git. Exit code is 0 when every check passes.
"""

from __future__ import annotations

import json
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
RUNS = ROOT / "runs"
RUN_FILES = ["trace.md", "trace.json", "patch.diff", "grading.json"]
TEXT_SUFFIXES = {".md", ".json", ".py", ".sh", ".toml", ".yml", ".patch", ".diff", ".txt", ""}
HIDDEN_MARKERS = ["test_transfers", "test.patch", "solve.sh", "/solution"]
PRIVATE = [re.compile(r"sk-[A-Za-z0-9_-]{16,}"), re.compile(r"[A-Za-z]:\\Users\\"),
           re.compile(r"/Users/[A-Za-z]"), re.compile(r"/home/[A-Za-z]")]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def node_id(name: str) -> str:
    dotted, test = name.split("::")
    module, cls = dotted.rsplit(".", 1)
    return f"{module.replace('.', '/')}.py::{cls}::{test}"


def check_task() -> None:
    required = ["instruction.md", "task.toml", "environment/Dockerfile", "environment/test.patch",
                "environment/problem_statement.md", "environment/prompt_statement.md",
                "environment/requirements.json", "environment/interface.md",
                "solution/solve.sh", "tests/test.sh", "tests/test_metadata.json"]
    missing = [r for r in required if not (TASK / r).is_file() or (TASK / r).stat().st_size == 0]
    check("task: Harbor task files present", not missing, f"missing: {missing}" if missing else "")

    meta = load_json(TASK / "tests" / "test_metadata.json") or {}
    check("task: test_metadata.json and requirements.json are valid JSON",
          bool(meta) and load_json(TASK / "environment" / "requirements.json") is not None)
    test_sh = (TASK / "tests" / "test.sh").read_text(encoding="utf-8")
    inline = re.search(r"<< '__TEST_PATCH__'\n(.*?)^__TEST_PATCH__$", test_sh, re.S | re.M)
    patch = (TASK / "environment" / "test.patch").read_text(encoding="utf-8")
    check("task: test.sh embeds the same test patch as environment/test.patch",
          bool(inline) and inline.group(1) == patch)
    listed = re.findall(r'^  "(tests/[^"]+)"$', test_sh, re.M)
    expected = [node_id(n) for n in meta.get("FAIL_TO_PASS", []) + meta.get("PASS_TO_PASS", [])]
    check("task: test.sh runs exactly the FAIL_TO_PASS and PASS_TO_PASS tests",
          sorted(listed) == sorted(expected) and len(set(listed)) == len(listed),
          f"{len(listed)} in test.sh, {len(expected)} in test_metadata.json")
    solve = (TASK / "solution" / "solve.sh").read_text(encoding="utf-8")
    check("task: solve.sh carries the reference patch", bool(re.search(r"<< '__SOLUTION__'\ndiff --git", solve)))
    copies = re.findall(r"^COPY\s+(\S+)", (TASK / "environment" / "Dockerfile").read_text(encoding="utf-8"), re.M)
    check("task: the image copies only the starter repo", copies == ["repo/"], f"COPY {copies}")


def check_run(run: Path, git: str | None) -> dict:
    name = f"runs/{run.name}"
    missing = [f for f in RUN_FILES if not (run / f).is_file() or (run / f).stat().st_size == 0]
    check(f"{name}: run files present", not missing, f"missing: {missing}" if missing else "")
    if missing:
        return {}

    if git is None:
        check(f"{name}: patch.diff applies to the starter repo", False, "git not found")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            shutil.copytree(STARTER, repo, ignore=shutil.ignore_patterns("__pycache__"))
            applied = subprocess.run([git, "apply", "--check", str((run / "patch.diff").resolve())],
                                     cwd=repo, capture_output=True, text=True)
        check(f"{name}: patch.diff applies to the starter repo", applied.returncode == 0, applied.stderr.strip()[:200])

    trace = load_json(run / "trace.json") or {}
    grading = load_json(run / "grading.json") or {}
    check(f"{name}: trace.json and grading.json are valid JSON", bool(trace) and bool(grading))
    md = (run / "trace.md").read_text(encoding="utf-8")
    steps = [s for s in trace.get("steps", []) if s.get("kind") in ("bash", "edit")]
    headings = re.findall(r"^#### Step (\d+): (Bash|Edit)", md, re.M)
    same = ([int(n) for n, _ in headings] == [s["step"] for s in steps]
            and all((s.get("command") or s.get("file")) in md for s in steps)
            and len(steps) == trace.get("summary", {}).get("tool_calls"))
    check(f"{name}: trace.md and trace.json describe the same steps", same, f"{len(steps)} tool calls")
    text = md + json.dumps(trace)
    leaks = [m for m in HIDDEN_MARKERS if m in text]
    check(f"{name}: the trace never reads the hidden tests or the solution", not leaks,
          f"found: {leaks}" if leaks else "")
    return grading


def check_rubric(gradings: dict[str, dict]) -> None:
    rubric = load_json(RUNS / "rubric.json")
    check("runs: rubric.json is valid JSON", rubric is not None)
    if not rubric:
        return
    weights = {c["id"]: c["weight"] for c in rubric["criteria"]}
    check("runs: rubric weights add up to total_weight", sum(weights.values()) == rubric["total_weight"])
    for agent, grading in gradings.items():
        r = rubric["results"].get(agent, {})
        passed = sum(weights[c] for c in r.get("passed", []))
        ratio = lambda g: f"{g['passed']}/{g['total']}"
        ok = (bool(grading) and set(r.get("passed", [])) | set(r.get("failed", [])) == set(weights)
              and r.get("weighted", "").startswith(f"{passed}/{rubric['total_weight']}")
              and r.get("f2p") == ratio(grading["fail_to_pass"]) and r.get("p2p") == ratio(grading["pass_to_pass"]))
        check(f"runs/{agent}: rubric result agrees with its weights and grading.json", ok)


def check_text() -> None:
    this = Path(__file__).resolve()
    private, non_ascii = [], []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        raw = path.read_bytes()
        rel = path.relative_to(ROOT).as_posix()
        if any(b > 127 for b in raw):
            non_ascii.append(rel)
        if path != this and any(p.search(raw.decode("utf-8", "replace")) for p in PRIVATE):
            private.append(rel)
    check("repo: no API keys or private local paths", not private, f"found in: {private[:5]}" if private else "")
    check("repo: every text file is plain ASCII", not non_ascii, f"non-ASCII: {non_ascii[:5]}" if non_ascii else "")


def main() -> int:
    git = shutil.which("git")
    check_task()
    run_dirs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    check("runs: at least one recorded run", bool(run_dirs), f"{len(run_dirs)} runs")
    gradings = {run.name: check_run(run, git) for run in run_dirs}
    check_rubric(gradings)
    check_text()

    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}".rstrip())
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
