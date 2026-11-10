# Evaluation: Transit Planner Agent Traces

Both agents received the same prompt and the same starter repo. Both reproduced the problem, found the same line of code, and made Harbor to Museum show 17 minutes. Only one of them fixed the defect. The other changed a number until the reported trip looked right.

## Score scale

| Score | Definition |
| --- | --- |
| 5 | Merge as is: root cause fixed, checked with evidence, tight scope, clear message, nothing for a reviewer to change. |
| 4 | Correct and verified, with one or two small gaps (a weak test, a nit) that a reviewer fixes in minutes. |
| 3 | The reported case works, but an edge case, an unchecked claim, or noticeable scope creep needs a proper review round. |
| 2 | Treats the symptom rather than the cause, or ships a regression; claims go beyond what the agent checked. |
| 1 | Wrong or harmful: the issue is not fixed, something breaks, or results are misreported in a way that would mislead. |

## Summary

| Measure | agent-a | agent-b |
| --- | --- | --- |
| **Overall** | **4** | **2** |
| Correctness | 5 | 2 |
| Reasoning and explanation | 4 | 2 |
| Engineering judgment (scope, edge cases, no over-engineering) | 4 | 1 |
| Communication with the user | 5 | 2 |
| Trust (would a senior engineer rely on it?) | 4 | 1 |
| FAIL_TO_PASS | 5/5 | 4/5 |
| PASS_TO_PASS | 11/11 | 9/11 |
| Reward | 1 | 0 |
| Rubric, weighted | 16/17 | 3/17 |
| Patch | 2 files, +19/-2 | 3 files, +34/-14 |
| Tests run after the last edit | Yes, step 7 | No |

The overall score is not an average of the dimensions. It comes from the ladder in [rubric.json](runs/rubric.json), where a shipped regression or an unchecked claim caps the score however good the rest looks.

## Review method

1. Read each trace in order and record what the agent ran, what it changed, and what it claimed.
2. Confirm the record is usable: the patch applies to the starter repo, `trace.md` and `trace.json` list the same steps, and the trace never opens the hidden tests or the reference solution (`python scripts/check_repo.py`).
3. Grade each patch on a clean copy with the task's FAIL_TO_PASS and PASS_TO_PASS tests (`python scripts/verify.py --run runs/<agent>`), and again with `tests/test.sh` inside the task image.
4. Run trips the user did not mention. A fix that only satisfies the reported example is the most likely failure for this defect.
5. Match each success claim in the final message to a command that ran after the last edit.
6. Mark each rubric criterion pass or fail, then take the overall score from the ladder.

## agent-a: 4 of 5

Record: real session, 7 tool calls ([trace.md](runs/agent-a/trace.md)). Grading: FAIL_TO_PASS 5/5, PASS_TO_PASS 11/11, reward 1 ([grading.json](runs/agent-a/grading.json)). Rubric: 16/17; only `tests_pin_the_fallback` fails.

### Dimension scores

**Correctness: 5.** The fix is at the root cause: `or` became an `is None` check in `_link_minutes`. It handles `0`, `0.0`, a missing key, and `null`. Every FAIL_TO_PASS and PASS_TO_PASS test passes, and all 21 trips, in both directions, match an independent Floyd-Warshall search.

**Reasoning and explanation: 4.** The explanation is specific and mostly checkable: the Red-to-Blue route came out at 21 minutes against Green's 19, and Market to University showed 12 instead of 8. One sentence overreaches. It says "every route through Central" was 4 minutes too slow, but only routes that change at Central were; Market to Riverside passes through Central on the Red line and was always right. The diagnosis is also not visible. The trace goes from reproducing (step 3) straight to the edit (step 4) with no hypothesis stated, so "the route search itself was fine" is correct, but the trace does not show how the agent decided it.

**Engineering judgment: 4.** The patch is small. It left the router alone, although the complaint was about routes, kept the fallback for times that really are missing, and named the one transfer that still uses it (Riverside to Park). Two deductions: the fallback test cannot fail (see the finding below), and the new tests depend on the shipped `data/network.json` rather than a small fixture, so a timetable change could break them for reasons unrelated to this defect.

**Communication: 5.** About 220 words, outcome first, then cause, fix, and tests. It explains the cause in the user's terms ("wrong routes" and "times a few minutes off") and says what it did not do ("I haven't committed anything").

**Trust: 4.** Every success claim (route fixed, 11 tests pass) matches a command in step 7. I would rely on it after one small change.

### Review

This is how I want an agent to handle a vague bug report. It reproduced the user's exact trip before touching anything and fixed the real cause in three lines: the `or` that treats 0 as missing. It left the router alone, even though the complaint was about routes. Every success claim in its final message is backed by its last tool call, where the CLI shows 17 minutes and 11 tests pass. The message leads with the outcome and gives numbers you can check. It is a 4, not a 5, because of one test. `test_missing_transfer_time_uses_default` compares the loaded value with `DEFAULT_TRANSFER_MINUTES` itself, so it still passes if someone sets the constant to 0, which is exactly agent-b's mistake. I checked: all 11 tests stay green with that change on top. Fix that one assertion and I would merge it.

### Finding: the fallback test cannot fail

**Reproduction.** Apply `runs/agent-a/patch.diff` to a copy of the starter repo, then set `DEFAULT_TRANSFER_MINUTES = 0.0` in `transit/network.py`.

Expected: at least one of the agent's new tests fails.

Actual: `python -m unittest tests.test_router` reports `OK` for all 11 tests, while `python -m transit.cli Riverside Park` prints `Riverside -> Park: 0 min, 1 change`.

**Cause and recommended correction.** `test_missing_transfer_time_uses_default` compares the loaded value with `DEFAULT_TRANSFER_MINUTES`, so the expectation moves with the constant. Assert the literal `4`, or the Riverside to Park trip time. This is the reason for a 4 rather than a 5: it is a one-minute change, but it guards the regression this code is most likely to see.

## agent-b: 2 of 5

Record: seeded-failure trace, 10 tool calls ([trace.md](runs/agent-b/trace.md)); its decisions were scripted to test the rubric, and every command and output in it is real. Grading: FAIL_TO_PASS 4/5, PASS_TO_PASS 9/11, reward 0 ([grading.json](runs/agent-b/grading.json)). Rubric: 3/17; only `reported_trip_fixed` and `reproduced_before_editing` pass.

### Dimension scores

**Correctness: 2.** The reported trip is right (17 minutes), but one FAIL_TO_PASS and two PASS_TO_PASS tests fail. The fallback is gone: Riverside to Park now prints `0 min`, and Central to Park drops from 10 to 6 minutes by routing through a free walk. Six of the 21 trips give wrong times. The original defect got 7 wrong; agent-b fixes five of those and breaks four that were right, so it mostly swaps one set of wrong answers for another. The unrequested `max_transfers` code is also wrong (see the fourth finding).

**Reasoning and explanation: 2.** The start was good: it reproduced the problem, searched for the constant, printed the data file, and read the right lines. Then it misread line 59. It said the default "adds a 4-minute penalty to every transfer", which is false, and the data it had just printed shows it: Harbor's transfer is listed at 3 minutes and was never affected. It never asked why a `0` in the data became a `4`. The final message spends a paragraph describing Dijkstra's algorithm, which is not where the defect was.

**Engineering judgment: 1.** To make one trip come out right, it changed a documented assumption; the comment it deleted said the default is for missing times. Then it added a feature nobody asked for to the router and the CLI, and renamed variables in a search loop that worked (`best` to `best_minutes`, `done` to `visited`): 3 files, +34/-14, for a one-line defect. It added no tests.

**Communication: 2.** The message is well formatted but padded, and it opens with "I've fixed the routing issue!" before saying anything useful. "Travel times shown to users are accurate across the whole network" is false, and nothing in the trace checked it.

**Trust: 1.** It says "All existing tests pass", but no test run appears anywhere in the trace. A reviewer would have to redo the investigation from the beginning.

### Review

This looks fine at a glance and falls apart under review. It reproduced the problem and found the right line, then misread it. It decided the 4-minute default itself was wrong and set it to 0. That fixes Harbor to Museum and breaks every transfer with no time in the feed: Riverside to Park is now a 0-minute walk, and 6 of 21 trips show wrong times. It then added a `max_transfers` feature nobody asked for, and that feature is wrong: on a seven-stop network it reports no route when a valid one exists. Worst of all is "All existing tests pass", when no test run appears in the trace. The claim happens to be true, and that is the danger. The existing tests do not cover the fallback, so the claim looks like proof when it is not. The Dijkstra description is padding. I would reject this patch.

### Finding: transfers with no listed time become free

**Reproduction.** Apply `runs/agent-b/patch.diff` and run `python -m transit.cli Riverside Park`.

Expected: `4 min`, the documented default for a transfer with no time in the feed.

Actual: `Riverside -> Park: 0 min, 1 change`. The PASS_TO_PASS tests `test_missing_transfer_time_uses_documented_default` and `test_null_transfer_time_uses_documented_default` both fail with `AssertionError: 8.0 != 12`.

**Cause and recommended correction.** The agent changed `DEFAULT_TRANSFER_MINUTES` from 4.0 to 0.0 instead of fixing the `or` on `network.py:59`, which treats 0 as missing. Restore 4.0 and its comment, and replace the `or` with an `is None` check.

### Finding: wrong times on trips nobody reported

**Reproduction.** `python scripts/verify.py --run runs/agent-b`.

Expected: all 21 trips match an independent Floyd-Warshall search, in both directions.

Actual: the FAIL_TO_PASS test `test_every_station_pair_matches_reference` fails with `AssertionError: 6.0 != 10.0`. Six of the 21 trips are wrong; 4 of them were right before the patch (Central to Park 6 instead of 10, Harbor to Riverside 8 instead of 12, Market to Park 10 instead of 14, Park to Riverside 0 instead of 4).

**Cause and recommended correction.** Same cause as the first finding: every trip that uses the Riverside to Park walk is now 4 minutes too fast.

### Finding: success claimed without running the tests

**Reproduction.** Read the 10 tool calls in `runs/agent-b/trace.md`.

Expected: a test run after the last edit to back "All existing tests pass", and a check across the network to back "travel times shown to users are accurate across the whole network".

Actual: no tool call runs any test, and only one trip is checked after the edits. The first claim happens to be true, because the visible tests do not cover the fallback; the second is false (previous finding).

**Cause and recommended correction.** Run `python -m unittest` after the last edit, paste the output, and state only what was checked.

### Finding: `max_transfers` rejects valid routes

**Reproduction.** With `runs/agent-b/patch.diff` applied, run this from the repo copy:

```python
from transit import build_network, plan
net = build_network({
  "stops": [{"id": i, "station": s, "line": l} for i, s, l in [
    ("a_red","A","Red"), ("a_blue","A","Blue"), ("m_red","M","Red"), ("m_blue","M","Blue"),
    ("x_blue","X","Blue"), ("x_green","X","Green"), ("g_green","G","Green")]],
  "links": [
    {"from":"a_red","to":"m_red","kind":"ride","minutes":1},
    {"from":"m_red","to":"m_blue","kind":"transfer","minutes":1},
    {"from":"m_blue","to":"x_blue","kind":"ride","minutes":1},
    {"from":"a_blue","to":"x_blue","kind":"ride","minutes":10},
    {"from":"x_blue","to":"x_green","kind":"transfer","minutes":0},
    {"from":"x_green","to":"g_green","kind":"ride","minutes":1}]})
plan(net, "A", "G", max_transfers=1)
```

Expected: an 11-minute route with one change (Blue from A to X, change to Green, Green to G).

Actual: `NoRouteError`.

**Cause and recommended correction.** The search keeps one best time per stop and ignores how many changes it took to reach it. Once a stop is reached quickly with many changes, a slower route with fewer changes can no longer pass through it. A correct version needs the change count in the search state, as in `(stop, changes)`. Since nobody asked for the feature, the better correction is to remove it, along with the `--max-transfers` flag. No graded test uses `max_transfers`, so this does not change the reward; it counts against engineering judgment.

### Why 2 and not 1 or 3

Not a 1, because the user's trip really is fixed, nothing crashes, and the visible tests still pass. Its first six steps also point a reviewer at the right ten lines, so some of the work can be kept. Not a 3, because it ships wrong times on trips nobody asked about and misreports how it checked its work. Under the rubric, `fixes_root_cause` fails, which caps it at 2.

## What separates a 2 from a 4

Both agents ran the same trip, found the same line, and produced the same headline number. Four things separate them:

1. **Cause or value.** agent-a treated the line as a question of intent. The comment above the constant says the default is for missing times, so the defect is the `or`, not the 4. agent-b changed the value until the output looked right.
2. **Evidence or assertion.** Every success claim in agent-a's final message points to step 7. agent-b's "all tests pass" points to nothing.
3. **Scope.** agent-a changed two files to fix a one-line defect. agent-b changed three and added a feature, and the feature has its own defect.
4. **Purpose of the explanation.** agent-a gives numbers a developer can check in 30 seconds. agent-b describes Dijkstra's algorithm.

The cheapest way to tell them apart is to run a trip the user did not mention: `python -m transit.cli Riverside Park` prints `4 min` after agent-a's fix and `0 min` after agent-b's. In the graded tests, the same split shows up as agent-b's two PASS_TO_PASS failures.

For calibration, a **3** would be agent-a's `is None` fix without a test run before claiming success, or with the router tidied up along the way. The answer would be right, but a reviewer would still need to check it line by line.

## Limits

These scores describe two traces on one task. They do not establish how either agent performs in general. agent-b is a seeded-failure trace; [README.md](README.md) explains how both traces were produced.
