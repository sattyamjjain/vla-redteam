# results/hardware — physical-robot runs

**Runs executed to date: 0.** This directory is empty of results and exists anyway, deliberately.

## Why an empty directory is committed

A directory that appears only once results exist is a directory nothing can count. Two things read
this one:

1. `provael coverage` / the pinned public-evidence manifest derive a `hardwareResults` count from
   it, and provael.com renders its sim-to-real claim from that count — so the site stops saying
   "not yet measured" the day a run lands here, rather than waiting on someone to remember a docs
   edit. The website build **fails** if the count moves while the page still asserts "not yet run",
   which is deliberate: a page that half-corrects itself is worse than one that stops.
2. The protocol below is the pre-registration this directory is the destination for. Publishing the
   destination before the result is the same discipline as publishing the protocol before the run.

So: zero runs, said out loud, in the place a reader would look for the first one.

## Status

| | |
| --- | --- |
| Runs executed | **0** |
| Protocol | [`docs/studies/sim-to-real-so101.md`](../../docs/studies/sim-to-real-so101.md) — PRE-REGISTERED 24 July 2026 |
| Blocker | Physical hardware not yet in hand. The software path is installable (see below). |
| What exists | The protocol, the `[hardware]` extra (resolves today), and a dry-run that validates the pipeline end to end against the stub policy. |

## RoboArena, and what a real-robot entry actually needs — assessed 6 September 2026

[RoboArena](https://robo-arena.github.io/) evaluates generalist robot policies on real DROID cells
and publishes a leaderboard. It is the shortest published route from this project to a real-robot
number, and the count above is the reason to want one. Its September 2026 round has a soft deadline
of 8 September and a hard deadline of 13 September, and this was assessed against it. Recorded here
rather than dropped, because "we looked and here is the gap" is the honest artifact and a
leaderboard row we could not earn is not.

**Three blockers, none of which is time.**

1. **There is no policy server to submit.** RoboArena's form asks for a Server IP and Port and
   whether the server implements their inference API — a `WebsocketPolicyServer` wrapping a
   `BasePolicy`, conditioned on three camera views, returning joint-position action chunks, with
   partial observations rejected. `provael serve` is the reference **attestation** server: it
   exposes `/healthz`, `/attest` and `/assurance-report`, and it has never had anything to do with
   robot inference. Nothing in this repository speaks that API, and answering "yes" to that question
   would be false on a form.

2. **The adapter that would front a π0.5 policy is scaffolding, by our own declaration.**
   `SCAFFOLDING_POLICIES["openpi"]` reads *"also needs a running openpi policy server; not exercised
   here"* — provael is a **client** of a policy server there, not a server. It has never been run
   against a real openpi checkpoint. `provael list-policies` says so, the website now says so, and a
   submission would be the first exercise of a path we publish as unexercised.

3. **The gate has no bounds for a DROID cell, and inventing some is the failure this repo already
   has a number for.** `ActionEnvelopeClamp` defaults to `BENIGN_DANGER_MAX = 0.0` and
   `BENIGN_MOTION_L2_MAX = 0.1`, measured from the CPU fixture's benign envelope in the fixture's
   own action space. DROID is 7-DoF joint position. Those scalars do not mean anything there.
   Picking replacements unexamined is exactly what #136 was, `workspace.py` states in its own
   docstring that the reachable bounds it computes are an observation and **deliberately not** a
   calibrated keep-out zone, and the protocol this directory exists for already fixes the order:
   calibrate from benign rollouts to a stated false-positive target **before** any attack runs.

**What would close it, in order.** A keep-out envelope calibrated from DROID benign trajectories to
a stated FPR — the data is public, so this is work rather than a blocker; a `BasePolicy`
implementation wrapping an openpi client with that envelope at the action layer; a GPU host with a
public IP to serve it. The first is the long pole and is a measurement, not an integration.

**One number that was nearly published wrong, kept here because it is the useful part.** A draft
covering letter for this submission stated that the benign control fires on 5 of 100 episodes. It
does not, and no arm of the committed control run produces that figure:

| Arm | Role | Measured |
| --- | --- | --- |
| `none` | benign control | 3/50 (6%) |
| `benign_reword` | harmless variation | 1/50 (2%) |
| `nonsense_text` | harmless variation | 0/50 (0%) |

The question the letter was reaching for is a good one and survives the correction: **the benign
control fires on 3 of 50 simulated episodes, and nobody knows whether that rate holds on a real
DROID cell.** That is the number a real-robot round would actually buy, and it is worth more than
the leaderboard row.

## The hardware this is written for

| Item | Specification |
| --- | --- |
| Arm | SO-ARM101 (SO-101), the LeRobot-supported low-cost 6-DoF follower arm |
| Policy | SmolVLA (`HuggingFaceVLA/smolvla_libero`), the checkpoint behind the published simulation result |
| Cameras | Two synchronised RGB streams (top + wrist), matching the LeRobot v3.0 dataset convention |
| Host | A CUDA GPU host for policy inference; the arm itself is driven over USB by LeRobot |
| Software | `pip install 'provael[hardware]'` — resolves today, see below |

Nothing in this repository controls a robot. `provael` emits actions and scores outcomes; moving a
physical arm is LeRobot's job, under a human operator with an E-stop. See
[SAFETY.md](../../SAFETY.md).

## The protocol, in one paragraph

The pre-registration fixes the design before the data exists: run the instruction family that
transferred in simulation (`roleplay`, `goal_substitution`, `paraphrase`) plus the benign `none`
control against the same policy on the physical arm, with the keep-out predicate calibrated from
benign rollouts to a stated false-positive target *before* any attack runs. The question is whether
the simulation ASR predicts the physical one — and the honest answer may be no. A null is a result
here and will be published as one.

## What a run in this directory will contain

The same artifact set as every other committed run, so a hardware result is comparable to a
simulation one by construction:

```
results/hardware/<run-id>/
  report.json               the measured rates (no timestamps — determinism contract)
  execution-manifest.json   runtime provenance: started_at, ended_at, hardware, accelerator,
                            precision, dep_lock_digest — RECORDED, not reconstructed
  evidence-manifest.json    the evidence-state ladder for this run
```

The `execution-manifest.json` matters more here than anywhere else. The one existing real-policy run
has a *reconstructed* timestamp, which is why the README badge reads "date reconstructed" — see
[docs/standards/last-measured.md](../../docs/standards/last-measured.md). A hardware run must record
its provenance properly, and the dry-run below asserts the shape.

## Installing the hardware path

```bash
pip install 'provael[hardware]'        # lerobot[smolvla,libero,feetech]==0.5.1
```

`[hardware]` is `[lerobot]` plus LeRobot's own `feetech` extra — the STS3215 servo-bus driver
(`feetech-servo-sdk`) that the SO-101 uses. It is a **separate** extra rather than folded into
`[lerobot]`, because someone installing provael to red-team a policy in simulation should not end up
with a package that can address a motor bus. The sim path never pulls it.

It resolves today, against the same pinned `lerobot==0.5.1` as the policy, and that is the whole
point of wiring it before the arm exists: the alternative is resolving a second environment under
time pressure with a robot on the bench. Installing it adds **no** robot-control code to provael —
provael scores, it does not actuate; the teleop and record steps are LeRobot's own tooling.

Being one `pip install` from a physical run is not evidence of one. The count above stays **0**.

## Before the arm arrives

```bash
provael sim-to-real --dry-run          # validates the whole protocol against the stub policy
```

The dry-run exists so the first physical session is not also the first debugging session. It walks
the same code path a real run takes, against the deterministic CPU stub, and asserts the artifact
shape a real run must produce. It refuses to write into this directory, because this directory is
counted as physical evidence and a dry run must not inflate it.
