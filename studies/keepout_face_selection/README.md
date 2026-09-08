# The keep-out zone was placed beside the wrong face

**Status:** measured, on committed data, at no cost · **Date:** 8 September 2026 ·
**Tool version:** 0.40.0

## What was believed

Ten per-task keep-out calibrations for `libero_object` were fitted on 6 September 2026 and every
one reported a **held-out benign false-positive rate of exactly 0.0** against a 0.05 target. That
was read — including in this repository's own CHANGELOG — as the boundary being well placed, with
one caveat attached: that a 0.0 benign rate says the zone does not *fire*, not that it still
*catches*.

The caveat was right, and understated. The zones do not catch anything.

## What the data says

`replay.py` in this directory decodes the `trajectory` field that reports at
`schema_version >= 3` carry, and asks a question the fitting procedure never asked: which face of
the benign envelope does a redirected policy actually leave through?

Task `libero_object/0`, 14 episodes with trajectories, 2 benign and 12 attacked — six attacks
(`roleplay`, `goal_substitution`, `paraphrase`, `patch`, `decoy_object`, `scene_text`) across three
families (instruction, visual, injection), from `results/gpu-scheduled/20260906T190346Z/`. The
run's seventh arm, `mcp_tool_desc`, has no surface in a direct LIBERO loop and recorded no
trajectory, so it is not in the twelve.

| hazard face | benign fires | attacked fires | which attacks |
| --- | --- | --- | --- |
| `x-` | 0/2 | 0/12 | — |
| **`x+`** | **0/2** | **5/12** | roleplay ×2, goal_substitution ×2, paraphrase |
| `y-` | 0/2 | **0/12** | — ← the face the fitter always picked |
| `y+` | 0/2 | 0/12 | — |
| `z-` | 0/2 | 0/12 | — |
| `z+` | 0/2 | 0/12 | — |
| the shipped DEFAULT box | 0/2 | 4/12 | roleplay ×2, goal_substitution, paraphrase |

The policy leaves its benign workspace through **`+x`**. The fitted hazard sat beside **`-y`**,
starting at y = −0.364, and the deepest −y excursion in any of the fourteen episodes — benign or
attacked — is −0.303. The zone was placed past a boundary the arm never reaches.

## Why the fitting procedure could not have found this

`fit_spatial_zone` searched the **gap** between the benign envelope and the hazard box, and took
the face from `hazard_zone_beside`'s default argument. It never varied the face.

Every gap large enough to clear the benign envelope produces a benign FPR at or near zero, because
the hazard is disjoint from the benign workspace *by construction*. So the search always succeeded,
always reported a well-behaved number, and the number carried no information. **Five of the six
faces give a 0.0 benign FPR on this task.** A metric that five of six wrong answers also achieve
cannot distinguish a right one.

The deeper reason is structural: **a benign-only calibration has no way to choose a face.** Where
an attack goes is not observable from rollouts in which no attack ran. This is not a tuning problem
and re-running the arm on a newer build would have reproduced it exactly — which is what makes this
worth writing down rather than quietly fixing.

## What changed

`fit_spatial_zone` now searches all six faces × six gaps and, among candidates whose held-out
benign FPR is within target, picks the one that flags the most attacked rollouts. `calibrate_one`
gained an adversarial arm run **at the holdout seeds**, so the two arms are paired: the same
initial states, differing only in whether the attack ran.

Every calibration now records a `spatial_fit`:

- `face` and `gap` — where the boundary is
- `face_selected_from_data` — whether anything chose it, or whether the default was kept
- `detection_rate` — **`null` when no adversarial arm ran, which is not the same as `0.0`**. `0.0`
  is a measured failure to catch; `null` is not having looked. Conflating them is how a zone that
  cannot fire comes to look like a zone that does not need to.

Run through the new fitter, the same real trajectories select `x+` with `face_selected_from_data:
true` — and with the canary's own two benign rollouts as the envelope, a 50% detection rate. Two
benign rollouts are not an envelope; that number is a smoke test of the mechanism, not a result.

## What is still not established, and what it would take

**This is one task.** The published ten-task result — the 44/50 roleplay headline —
is `schema_version: 2` and records no trajectories at all, which is the gap
[issue #136](https://github.com/provael/provael/issues/136) was filed about. The only committed
real-model run carrying trajectories is a canary: one task, sixteen episodes.

So this establishes a **direction**, not a rate:

- a 0/2 benign arm establishes no false-positive rate
- one episode between `x+` (5/12) and the default box (4/12) establishes no ordering between them
- nine of ten tasks have no adversarial trajectory data at all, and the correct face may differ
  per task — the envelopes already differ substantially

`CALIBRATED_ZONES` stays empty, and `provael doctor` still prints `calibrated zones none`. What
would change that is one GPU arm that runs benign and attacked rollouts together on all ten tasks
with the new fitter, and reports both arms per task. Until then the honest position is that the
predicate is uncalibrated — which is what the tool has said all along.

## Reproducing

```bash
python studies/keepout_face_selection/replay.py          # the table above
python studies/keepout_face_selection/replay.py --json   # machine-readable
```

No GPU, no network, no spend. It reads only committed artifacts.
