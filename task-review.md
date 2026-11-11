# Task Review: transit-planner-zero-transfer

A review of the task itself: whether it is fair, solvable, and graded in a way that cannot be gamed. Every check below can be rerun with the commands in [README.md](README.md).

**Result: ready.** Five findings: four fixed, one open and low risk. After the fixes, the starter scores 0, the reference solution 1, agent-a 1 and agent-b 0, with identical per-test results before and after.

## What was checked

| Area | Check | Result |
| --- | --- | --- |
| Configuration | `task.toml` fields, timeouts and limits; `harbor lint --select ALL` (Harbor 0.25.0) | Pass. One rule, `shared-verifier`, is intentionally not met (see Design notes). |
| Environment | Dockerfile contents, base image, user, file modes | Pass after findings 2, 3 and 4 |
| Prompt | Every graded behavior follows from the prompt plus the repo | Pass |
| Tests | How FAIL_TO_PASS and PASS_TO_PASS were chosen; coverage | Pass, with finding 5 open |
| Reference solution | Reward 1 locally, in the task image, and in Harbor | Pass |
| Reward integrity | Five planted shortcuts against the unfixed starter repo | Pass after finding 1 |
| Harbor | `harbor run` with the oracle and a no-op agent | Pass: 1.0 and 0.0 |

## Findings

### 1. The grader could be fooled without fixing the bug (fixed)

**Reproduction.** Plant each file below in the unfixed starter repo and run `tests/test.sh` in the task image.

| Planted in the repo | Before the fix | After the fix |
| --- | --- | --- |
| `conftest.py` that marks every test report as passed, plus a `pytest.ini` | `16 passed`, reward 1 | repo tests `8 passed`, hidden tests `5 failed, 3 passed`, reward 0 |
| `pytest.py` in the repo root that exits 0 | reward 1 | reward 0 |
| `json.py` in the repo root that exits 0 | reward 1 | reward 0 |
| Code in `transit/__init__.py` that switches off `unittest.TestCase.assertEqual` | `16 passed`, reward 1 | reward 0 |
| Code in `transit/__init__.py` that overwrites the hidden tests and `reward.txt` (tried after the fix) | not tried | reward 0 |

Expected: reward 0 in every row, because the bug is still there.

Actual (before): reward 1 in the first four rows. The first was found with the grader's pytest command on a local copy; the other three in the task image.

**Cause and correction.** The grader ran pytest inside the agent's working tree and in the same process as the agent's code, so files in the repo could change pytest's configuration, replace pytest or a standard-library module, or patch the assertions. `tests/test.sh` now:

- runs pytest as `python -P -m pytest --import-mode=append --noconftest -o addopts=`, so files in the repo are never ahead of the standard library on the import path and no agent-written pytest configuration is read;
- copies the hidden tests to a root-owned folder outside the repo and runs them in their own process, which never imports the repo's code: each hidden test sends its queries to a child process that runs the planner as the `agent` user and returns plain data;
- runs the repo's own tests as the `agent` user.

The hidden tests keep their names and expected values. `scripts/verify.py` mirrors the two runs.

### 2. The base image was not pinned (fixed)

**Reproduction.** `harbor lint --select ALL` reported `unpinned-image` for `FROM python:3.12-slim`.

**Cause and correction.** A tag can point to a different image later, so two builds could differ. The Dockerfile now pins the image by its SHA-256 digest; pytest is pinned to 8.4.1.

### 3. The agent ran as root (fixed)

**Reproduction.** `harbor lint --select ALL` reported `root-agent`.

**Cause and correction.** The verifier runs in the agent's container, so a root agent could change the Python install or pytest before grading. The image now adds a non-root `agent` user that owns `/workspace`, and `task.toml` sets `[agent] user = "agent"`. Checked in the image: the `agent` user cannot write to the system site-packages.

### 4. File modes depended on the build host (fixed)

**Reproduction.** Build the image on Windows and apply any patch with `git apply`.

Expected: no warnings.

Actual: `warning: transit/network.py has type 100755, expected 100644`, once per patched file.

**Cause and correction.** Files copied from a Windows checkout were marked executable. The Dockerfile now resets repo files to mode 644.

### 5. The whole-network test reads the shipped data file (open, low)

**Reproduction.** Read `reference_times()` in the hidden tests.

**Cause and recommended correction.** The independent Floyd-Warshall reference is built from the same `data/network.json` the planner loads, so an edit to that file moves both sides of the test. The fixture-based tests do not read the data file, so a data edit alone cannot earn reward 1, but the tests would not flag it either. A frozen copy of the network inside the test file would close this. Until then, reviewers should read any change under `data/` in a diff.

## Design notes

- **The prompt is vague on purpose.** `instruction.md` is a developer's short report: a symptom, one trip, and a hint that points at the router while the defect is in the data loader. Every FAIL_TO_PASS test still follows from it: the reported trip (17 minutes), a listed 0-minute change costing 0 (the data lists 0 at Central), and every trip being the fastest (the repo README says the planner finds the fastest trip). The 4-minute default for a missing time is documented in the comment above `DEFAULT_TRANSFER_MINUTES`.
- **Grader-side files stay out of the image.** `problem_statement.md`, `requirements.json` and `interface.md` describe the expected behavior for reviewers. Giving them to the agent would hand over the diagnosis, so the Dockerfile copies only the starter repo.
- **How the graded tests were chosen.** Both test files were run against the starter and the reference solution. The 5 tests that fail on the starter and pass with the fix are FAIL_TO_PASS; the 11 that pass on both are PASS_TO_PASS.
- **A literal 4 in the hidden tests.** They compare with the number 4, not with the constant, so a fix that changes the constant cannot pass by moving the expectation.
- **Missing tests count as failures.** Tests run by explicit node id, so deleting a test makes pytest exit non-zero.
- **The verifier shares the agent's container.** A grader for a repository bug fix has to test the agent's working tree in place, which is why `shared-verifier` is not met. Finding 1 removed the ways this could be abused through the hidden tests. One limit remains, common to any grader that runs a repository's own tests: the repo's own 8 tests run with the repo's code, so a patch that tampers with the test framework could pass those 8. It cannot affect the 8 hidden tests, which include all 5 FAIL_TO_PASS tests and are required for reward 1, and that kind of tampering is visible in the diff.
- **A crash cannot leave a stale reward.** `test.sh` writes 0 to `reward.txt` before anything runs, and deletes any agent-made `tests/test_transfers.py` before adding the hidden tests.

## Harbor runs

Harbor 0.25.0 with Docker Desktop, 2026-11-09, and again on GitHub Actions on every push:

| Command | Trials | Exceptions | Reward |
| --- | --- | --- | --- |
| `harbor run -p tasks/transit-planner-zero-transfer -a oracle` | 1 | 0 | 1.0 |
| `harbor run -p tasks/transit-planner-zero-transfer -a nop` | 1 | 0 | 0.0 |

In the oracle trial's verifier log, the repo's tests show `8 passed` and the hidden tests `8 passed`. The no-op agent leaves the bug in place, so the hidden tests show `5 failed, 3 passed`.
