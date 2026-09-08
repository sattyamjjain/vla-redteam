"""Calibration core: Wilson CI, seed split, scalar/spatial fitting, model, artifact IO."""

from __future__ import annotations

from pathlib import Path

import pytest

from provael import __version__
from provael.calibration import (
    Calibration,
    DuplicateCalibrationError,
    ToolVersionMismatchError,
    artifact_name,
    calibrate_one,
    calibrate_suite,
    collect_benign_signals,
    fit_scalar_threshold,
    fit_spatial_zone,
    load_calibrations,
    save_calibration,
    split_seeds,
    to_json,
    wilson_ci,
)
from provael.policies.stub import StubPolicy
from provael.suites.keepout_zones import KeepOutZone
from provael.suites.stub import StubSuite


def test_wilson_ci_brackets_point_estimate() -> None:
    low, high = wilson_ci(8, 10)
    assert low < 0.8 < high
    assert round(low, 2) == 0.49
    assert round(high, 2) == 0.94


def test_wilson_ci_edges() -> None:
    assert wilson_ci(0, 0) == (0.0, 0.0)
    low, high = wilson_ci(0, 10)
    assert low == 0.0 and 0.25 < high < 0.31
    low, high = wilson_ci(10, 10)
    assert high == pytest.approx(1.0) and 0.69 < low < 0.73


def test_split_seeds_is_deterministic_and_requires_two() -> None:
    fit, holdout = split_seeds(list(range(10)))
    assert fit == [0, 1, 2, 3, 4, 5, 6] and holdout == [7, 8, 9]
    assert fit + holdout == list(range(10))  # no overlap, full cover
    with pytest.raises(ValueError):
        split_seeds([0])


def test_fit_scalar_threshold_hits_target_on_spread() -> None:
    scores = [i / 10 for i in range(10)]  # 0.0 .. 0.9
    threshold, fpr = fit_scalar_threshold(scores, scores, target_fpr=0.2)
    # Tightest t with <=20% of holdout strictly above it: 0.7 leaves {0.8, 0.9} = 20%.
    assert threshold == pytest.approx(0.7)
    assert fpr <= 0.2


def test_fit_scalar_threshold_degenerate_benign_is_clean() -> None:
    # The stub's benign danger is constant 0 -> threshold 0, FPR 0, and any positive
    # attack danger is flagged (strict >).
    threshold, fpr = fit_scalar_threshold([0.0] * 7, [0.0] * 3, target_fpr=0.05)
    assert threshold == 0.0 and fpr == 0.0
    assert Calibration(
        policy="stub", suite="stub", task="reach", kind="scalar",
        threshold=threshold, target_fpr=0.05, benign_fpr=fpr, n_benign=10,
    ).is_unsafe({"danger": 0.6})
    assert not Calibration(
        policy="stub", suite="stub", task="reach", kind="scalar",
        threshold=threshold, target_fpr=0.05, benign_fpr=fpr, n_benign=10,
    ).is_unsafe({"danger": 0.0})


def test_fit_spatial_zone_keeps_benign_out() -> None:
    # Benign EE clustered in a small box; the hazard zone is placed disjoint from it.
    benign = [[[0.0, 0.0, 0.0], [0.01, 0.0, 0.0]] for _ in range(6)]
    envelope, zones, fpr = fit_spatial_zone(benign[:4], benign[4:], target_fpr=0.05)
    assert len(envelope) == 3 and len(zones) == 1
    assert fpr <= 0.05
    # A benign point is NOT in the hazard zone; a point inside the zone IS.
    zone = zones[0]
    assert not zone.contains([0.0, 0.0, 0.0])
    inside = [(zone.x[0] + zone.x[1]) / 2, (zone.y[0] + zone.y[1]) / 2, (zone.z[0] + zone.z[1]) / 2]
    assert zone.contains(inside)


def test_calibration_spatial_is_unsafe() -> None:
    zone = KeepOutZone(name="hz", x=(1.0, 2.0), y=(1.0, 2.0), z=(1.0, 2.0))
    cal = Calibration(
        policy="smolvla", suite="libero", task="libero_object/0", kind="spatial",
        keep_out_zones=[zone], target_fpr=0.05, benign_fpr=0.0, n_benign=10,
    )
    assert cal.is_unsafe({"ee_pos": [1.5, 1.5, 1.5]})
    assert not cal.is_unsafe({"ee_pos": [0.0, 0.0, 0.0]})
    assert not cal.is_unsafe({"ee_pos": None})


def test_artifact_round_trip_and_determinism(tmp_path: Path) -> None:
    cal = Calibration(
        policy="stub", suite="stub", task="reach", kind="scalar",
        threshold=0.0, target_fpr=0.05, benign_fpr=0.0, n_benign=10,
        fit_seeds=[0, 1, 2], holdout_seeds=[3, 4],
    )
    path = save_calibration(cal, tmp_path)
    assert path.name == artifact_name("stub", "stub", "reach") == "stub__stub__reach.json"
    # Byte-deterministic.
    assert to_json(cal) == to_json(cal)
    # Round-trips and is discoverable by (policy, suite).
    loaded = load_calibrations(tmp_path, "stub", "stub")
    assert set(loaded) == {"reach"}
    assert loaded["reach"].threshold == 0.0
    assert load_calibrations(tmp_path, "other", "stub") == {}


def test_artifact_name_sanitizes_task() -> None:
    assert artifact_name("smolvla", "libero", "libero_object/0") == "smolvla__libero__libero_object_0.json"


# ---------------------------------------------------------------------------------------------
# Seeding the calibration rollouts, and saying so honestly.
#
# WHY THESE EXIST. `PolicyAdapter.seed` was called from exactly one place in the codebase —
# `runner.run_episode`, the attack path. `collect_benign_signals` seeded the ENVIRONMENT and not
# the policy, so a flow-matching sampler like SmolVLA's drew its noise from ambient torch state.
# The ten `libero_object` zones committed on 6 September 2026 were fitted that way: the envelopes
# that every later measurement is scored against came from rollouts nobody can reproduce.
#
# The fix is two claims, and each is a way this can go wrong on its own, so each gets a test:
# the policy is seeded at all, and the artifact records what the adapter APPLIED rather than what
# the caller asked for. The second is the one that rots quietly — recording the requested seed
# would make every calibration claim a determinism no adapter delivered.
# ---------------------------------------------------------------------------------------------


class _RecordingPolicy(StubPolicy):
    """A stub that records the seeds it is handed and reports applying every one of them."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[int] = []

    def seed(self, seed: int) -> int | None:
        self.seen.append(seed)
        return seed


class _UnseedablePolicy(StubPolicy):
    """A stub that is handed seeds and applies none — the base-class default, made explicit."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[int] = []

    def seed(self, seed: int) -> int | None:
        self.seen.append(seed)
        return None


def test_benign_rollouts_seed_the_policy_not_only_the_environment() -> None:
    policy = _RecordingPolicy()
    policy.load()
    suite = StubSuite()
    episodes, applied = collect_benign_signals(policy, suite, "reach", [4, 5, 6], horizon=4)
    assert policy.seen == [4, 5, 6], (
        "collect_benign_signals ran three rollouts without calling policy.seed for each — the "
        "sampler draws that shape the fitted boundary are then unreproducible"
    )
    assert applied == [4, 5, 6]
    assert len(episodes) == 3


def test_an_adapter_that_cannot_seed_records_null_not_the_requested_seed() -> None:
    """The honesty half. Recording the ASKED seed would claim a determinism nothing delivered."""
    policy = _UnseedablePolicy()
    policy.load()
    _, applied = collect_benign_signals(policy, StubSuite(), "reach", [7, 8], horizon=4)
    assert policy.seen == [7, 8], "the adapter was never offered the seeds"
    assert applied == [None, None], (
        "an adapter that returns None from seed() must leave null in the artifact; recording "
        "[7, 8] here would be the tool asserting a reproducibility the policy does not have"
    )


def test_the_calibration_artifact_carries_the_applied_seeds() -> None:
    """Fit seeds then holdout seeds, in that order, so a row lines up with the split above it."""
    policy = _RecordingPolicy()
    policy.load()
    cal = calibrate_one(
        policy, StubSuite(),
        policy_name="stub", suite_name="stub", task="reach",
        fit_seeds=[0, 1, 2], holdout_seeds=[3, 4],
        target_fpr=0.05, horizon=4, tool_version=__version__,
    )
    assert cal.policy_seeds == [0, 1, 2, 3, 4]
    assert cal.fit_seeds + cal.holdout_seeds == cal.policy_seeds, (
        "the applied seeds are recorded in a different order from the split that names them"
    )
    # And it survives the round trip that actually reaches a committed file.
    assert Calibration.model_validate_json(to_json(cal)).policy_seeds == [0, 1, 2, 3, 4]


def test_calibrate_suite_refuses_to_stamp_a_version_that_did_not_produce_it() -> None:
    """A fitted boundary scores every later run, so a wrong label misattributes all of them."""
    with pytest.raises(ToolVersionMismatchError, match="did not produce it"):
        calibrate_suite(
            "stub", "stub", ["reach"], list(range(4)),
            target_fpr=0.05, horizon=4, tool_version="0.32.0",
        )


def test_calibrate_suite_accepts_the_running_version() -> None:
    """The converse, so the guard above cannot pass by refusing everything."""
    cals = calibrate_suite(
        "stub", "stub", ["reach"], list(range(4)),
        target_fpr=0.05, horizon=4, tool_version=__version__,
    )
    assert cals and all(c.tool_version == __version__ for c in cals.values())


# ---------------------------------------------------------------------------------------------
# Loading what the calibrate arm actually wrote.
#
# The loader globbed one level; the `calibrate` GPU arm shards one task per container and writes
# each into its own subdirectory. So `--calib <the directory the arm produced>` matched zero files,
# returned {}, and the run measured the DEFAULT keep-out box while being configured not to.
# ---------------------------------------------------------------------------------------------


def _spatial(task: str) -> Calibration:
    return Calibration(
        policy="smolvla", suite="libero", task=task, kind="spatial",
        keep_out_zones=[KeepOutZone(name="z", x=(0.0, 1.0), y=(0.0, 1.0), z=(0.0, 1.0))],
        target_fpr=0.05, benign_fpr=0.0, n_benign=20,
    )


def test_calibrations_are_found_in_the_sharded_layout_the_arm_writes(tmp_path: Path) -> None:
    for i in range(3):
        save_calibration(_spatial(f"libero_object/{i}"), tmp_path / f"libero_object_{i}")
    found = load_calibrations(tmp_path, "smolvla", "libero")
    assert sorted(found) == ["libero_object/0", "libero_object/1", "libero_object/2"], (
        "the loader did not descend into the per-task subdirectories the calibrate arm writes, so "
        "--calib pointed at that directory would silently fall back to the default predicate"
    )


def test_two_calibrations_for_one_task_are_refused_not_silently_picked(tmp_path: Path) -> None:
    """Two fits are two boundaries; scoring against whichever sorted last is unreportable."""
    save_calibration(_spatial("libero_object/0"), tmp_path / "first")
    save_calibration(_spatial("libero_object/0"), tmp_path / "second")
    with pytest.raises(DuplicateCalibrationError, match="libero_object/0"):
        load_calibrations(tmp_path, "smolvla", "libero")


def test_the_committed_calibrations_load_from_their_own_directory() -> None:
    """The real artifacts, at the real path, since that is the invocation that was broken."""
    committed = Path(__file__).resolve().parents[1] / "results/calibration/libero_object_calibrate"
    if not committed.is_dir():  # pragma: no cover - present in the repo, absent in a wheel
        pytest.skip("results/ is not packaged")
    found = load_calibrations(committed, "smolvla", "libero")
    assert len(found) == 10, f"expected all ten libero_object calibrations, found {sorted(found)}"
