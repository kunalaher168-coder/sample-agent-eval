# Coding Agent Evaluation: SWE-bench-Style Task and Trace Review

A SWE-bench-style debugging task packaged in the Harbor task layout (the layout Terminal-Bench 2.0 tasks use), graded with FAIL_TO_PASS and PASS_TO_PASS tests and a 0/1 reward, plus two recorded agent runs scored against a weighted rubric. Every result in this repository can be reproduced with the commands below. All content and formats are original to this repository: nothing is taken from a client prompt, rubric, template, codebase, or trace.

## Task under review

`tasks/transit-planner-zero-transfer` is a 250-line Python journey planner for a city metro network. Users report slower routes and trip times that are a few minutes off. The route search is correct. The defect is one line in the data loader:

```python
minutes = raw.get("minutes") or DEFAULT_TRANSFER_MINUTES
```

The 4-minute default is meant for transfers with no time in the feed. Because `0` is falsy, the free cross-platform change at Central is also charged 4 minutes, and 7 of the 21 trips come out wrong. The report points at the router, the visible tests pass, and the quickest fix (setting the default to 0) corrects the reported trip while breaking every transfer with no listed time.

## Layout

```text
tasks/transit-planner-zero-transfer/   Harbor task
  instruction.md                       What the agent receives
  task.toml                            Metadata, timeouts, resources, agent user
  environment/                         Dockerfile, starter repo, test.patch, grader-side notes
  solution/solve.sh                    Reference patch (oracle)
  tests/                               test.sh (writes reward.txt), test_metadata.json
runs/
  agent-a/, agent-b/                   trace.md, trace.json, patch.diff, grading.json
  rubric.json                          Weighted criteria, score ladder, results
evaluation.md                          Scores, written reviews and findings for both runs
task-review.md                         Review of the task itself, including the fixes made
scripts/                               verify.py, check_repo.py, harbor_rewards.py
.github/workflows/tests.yml            Runs the scripts, test.sh in the task image, and Harbor
```

## How it was built

| Step | Artifact | Purpose |
| --- | --- | --- |
| Write the task | [instruction.md](tasks/transit-planner-zero-transfer/instruction.md), [task.toml](tasks/transit-planner-zero-transfer/task.toml) | A developer's short report, with Harbor metadata and limits |
| Package the environment | [environment/](tasks/transit-planner-zero-transfer/environment) | Image pinned by digest, with only the starter repo; the agent runs as a non-root user |
| Write the grader | [tests/test.sh](tasks/transit-planner-zero-transfer/tests/test.sh), [test_metadata.json](tasks/transit-planner-zero-transfer/tests/test_metadata.json) | Adds the hidden tests, runs 5 FAIL_TO_PASS and 11 PASS_TO_PASS tests (the hidden ones in a separate process that the repo's code cannot reach), writes the reward |
| Prove it is solvable | [solution/solve.sh](tasks/transit-planner-zero-transfer/solution/solve.sh) | Reference patch; the oracle earns reward 1 |
| Review the task | [task-review.md](task-review.md) | Fairness, solvability and reward integrity; four reward hacks found and closed |
| Record agent runs | [runs/agent-a](runs/agent-a), [runs/agent-b](runs/agent-b) | Trace, final patch, and clean-copy grading for each run |
| Score the runs | [evaluation.md](evaluation.md), [rubric.json](runs/rubric.json) | Dimension scores, written reviews, findings with reproduction steps, 1-to-5 score |

## Result

| Target | FAIL_TO_PASS | PASS_TO_PASS | Reward | Score |
| --- | --- | --- | --- | --- |
| Starter repo as given | 0/5 | 11/11 | 0 | n/a |
| Oracle (`solution/solve.sh`) | 5/5 | 11/11 | 1 | n/a |
| agent-a | 5/5 | 11/11 | 1 | **4 of 5** |
| agent-b (seeded-failure trace) | 4/5 | 9/11 | 0 | **2 of 5** |

The visible tests pass in every row, which is how the defect reached users.

**agent-a** reproduced the bug first, fixed the cause in three lines, left the router alone, ran the tests, and backed every success claim with output. It is not a 5 because its fallback test compares the loaded value with the constant it is meant to protect, so it would still pass with agent-b's change.

**agent-b** fixed the reported trip by changing the default from 4 to 0. That leaves 6 of the 21 trips wrong, 4 of them newly broken, and fails two PASS_TO_PASS tests; Riverside to Park becomes a 0-minute walk. It also added an unrequested and faulty `max_transfers` option, said all existing tests pass without running them, and padded its message with a description of Dijkstra's algorithm.

## Reproduce

Use Python 3.11 or later, git, and pytest.

```powershell
pip install pytest==8.4.1
python scripts/check_repo.py
python scripts/verify.py
python scripts/verify.py --run runs/agent-b
python scripts/verify.py --patch my_fix.diff
```

`verify.py` copies the starter repo to a temporary folder, applies the patch to the copy, adds the hidden tests, and runs the FAIL_TO_PASS and PASS_TO_PASS lists, so nothing in the repository changes. `--check` also confirms that every stored `grading.json` matches a fresh run.

With Docker, run the grader inside the task image:

```bash
docker build -t transit-task tasks/transit-planner-zero-transfer/environment
docker run --rm -v "$PWD/tasks/transit-planner-zero-transfer/tests:/tests:ro" \
  -v "$PWD/tasks/transit-planner-zero-transfer/solution:/solution:ro" \
  transit-task bash -c 'bash /solution/solve.sh && bash /tests/test.sh; cat /logs/verifier/reward.txt'
```

Run in the task image on 2026-11-09 (Docker Desktop): starter 0, oracle 1, agent-a 1, agent-b 0.

With Docker and Harbor, lint the task and run the oracle and a no-op agent:

```bash
pip install harbor==0.25.0
harbor lint --select ALL --ignore shared-verifier tasks/transit-planner-zero-transfer
harbor run -p tasks/transit-planner-zero-transfer -a oracle -o jobs/oracle
harbor run -p tasks/transit-planner-zero-transfer -a nop -o jobs/nop
python scripts/harbor_rewards.py jobs/oracle=1 jobs/nop=0
```

Run on 2026-11-09 with Harbor 0.25.0 and Docker Desktop: the oracle earned reward 1.0 and the no-op agent 0.0, with no exceptions. `harbor lint` passes every rule except `shared-verifier`, which is by design: a SWE-bench-style verifier grades the agent's working tree in place, and [task-review.md](task-review.md) explains how the grader handles that. [GitHub Actions](.github/workflows/tests.yml) runs all of the above on each push: both scripts, `test.sh` inside the task image for the starter (0), the oracle (1), agent-a (1) and agent-b (0), and the Harbor lint, oracle and no-op runs.

## Review path

1. Read [instruction.md](tasks/transit-planner-zero-transfer/instruction.md) and the two traces ([agent-a](runs/agent-a/trace.md), [agent-b](runs/agent-b/trace.md)), and form your own score before opening the evaluation.
2. Run `python scripts/verify.py` to confirm the result table.
3. Read [evaluation.md](evaluation.md) and compare its scores with the ladder in [rubric.json](runs/rubric.json).
4. Read [task-review.md](task-review.md) for how the task and its grader were checked.

## Trace provenance

agent-a is a real coding-agent session, run non-interactively on a fresh copy of the starter repo. Its JSON log was converted to Markdown with paths shortened, long outputs cut, and punctuation converted to plain ASCII (for example, an arrow in the prompt is shown as `->`); no words were changed. The model behind it was not recorded. A second real session on a smaller model also found the root cause: for a defect like this, current agents usually find the line, so the scores separate on process (reproduction, verification, scope, and honesty).

agent-b is a seeded-failure trace, used to confirm that the rubric and the tests catch the failure modes that matter here: treating the symptom instead of the cause, unrequested changes, claiming success without checking, and a generic explanation. Its decisions and messages were scripted; every command in it was run on a fresh copy of the starter repo, every output is real, and its patch is the real diff of those edits. These results describe two traces on one task. They do not establish how any agent performs in general.
