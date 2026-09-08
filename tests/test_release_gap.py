"""The published-measurement window: the staleness signal the age badge cannot see.

WHY A SECOND WINDOW. `STALE_DAYS` asks when ANYTHING was last measured, and a one-episode timing
probe satisfies it. On 8 September 2026 a $0.06 probe put `watch/freshness.json` at "today" while
the published 44/50 headline was still the ten-task suite measured nine minors earlier. A reader
running `provael doctor` saw a green freshness row and had no way to learn that.

www.provael.com has carried this on every page — "the published result was measured with v0.32.0,
9 releases ago" — and the CLI could not say it. These tests pin the rule that makes the two agree.

THE PART THAT IS EASY TO GET WRONG is which record represents "the published measurement". The
newest one is the obvious choice and it is the wrong one, for exactly the reason above.
"""

from __future__ import annotations

from provael.watch import (
    STALE_AFTER_RELEASES,
    MeasurementRecord,
    published_measurement,
    releases_behind,
)


def _rec(version: str, attempts: int, measured_at: str, policy: str = "smolvla") -> MeasurementRecord:
    return MeasurementRecord(
        policy=policy, suite="libero", tool_version=version,
        attempts=attempts, successes=0, asr=0.0,
        measured_at=measured_at, recorded=True, commit="abc1234",
    )


def test_a_tiny_probe_does_not_displace_a_large_campaign() -> None:
    """The regression this exists for, in miniature.

    A 350-episode campaign at 0.32.0 and a 1-episode probe at 0.40.0: the published number rests on
    the campaign, so that is the version a reader needs. Returning the probe's version would report
    0.40.0 and read as reassuring while being useless.
    """
    records = [
        _rec("0.40.0", 1, "2026-09-08T09:28:27Z"),
        *[_rec("0.32.0", 35, f"2026-08-09T09:4{i}:00Z") for i in range(10)],
    ]
    got = published_measurement(records)
    assert got is not None and got.tool_version == "0.32.0"


def test_a_genuinely_larger_run_at_a_newer_version_closes_the_gap() -> None:
    """The converse: the rule must not pin the past. No threshold edit should be needed."""
    records = [
        *[_rec("0.32.0", 35, f"2026-08-09T09:4{i}:00Z") for i in range(10)],
        *[_rec("0.42.0", 50, f"2026-10-01T09:4{i}:00Z") for i in range(10)],
    ]
    got = published_measurement(records)
    assert got is not None and got.tool_version == "0.42.0"


def test_equal_campaigns_break_toward_the_newer_version() -> None:
    """Two equally sized campaigns means the older is no longer the only thing carrying the claim."""
    records = [
        _rec("0.32.0", 100, "2026-08-09T09:40:00Z"),
        _rec("0.41.0", 100, "2026-09-08T09:40:00Z"),
    ]
    got = published_measurement(records)
    assert got is not None and got.tool_version == "0.41.0"


def test_a_fixture_run_is_not_a_published_measurement() -> None:
    """A stub backend executes real attacks in a second; it must never carry a published claim."""
    records = [_rec("0.41.0", 500, "2026-09-08T09:40:00Z", policy="stub"),
               _rec("0.32.0", 35, "2026-08-09T09:40:00Z")]
    got = published_measurement(records)
    assert got is not None and got.tool_version == "0.32.0", (
        "a 500-episode stub run outweighed a real 35-episode one — countsAsMeasurement was not applied"
    )


def test_no_real_measurement_reports_none_rather_than_a_zero_gap() -> None:
    """Nothing measured is not the same as measured-and-current, and zero is the reassuring answer."""
    assert published_measurement([]) is None


def test_release_gap_counts_minors() -> None:
    assert releases_behind("0.32.0", "0.41.0") == 9
    assert releases_behind("0.41.0", "0.41.0") == 0
    assert releases_behind("0.40.0", "0.41.0") == 1


def test_an_unparseable_version_reports_unknown_not_zero() -> None:
    """A gap of zero is the reassuring answer, so it must never be the fallback for a bad input."""
    assert releases_behind("weird", "0.41.0") is None
    assert releases_behind("0.32.0", "") is None


def test_a_measurement_ahead_of_the_release_clamps_to_zero() -> None:
    """Measuring on an unreleased build is ahead, not stale — a negative gap would render absurdly."""
    assert releases_behind("0.42.0", "0.41.0") == 0


def test_the_window_matches_the_one_the_site_publishes() -> None:
    """Two repos hold this threshold. If they drift, the CLI and the site disagree in public.

    The site's copy lives in `src/lib/freshness.ts` as `STALE_AFTER_RELEASES = 2`. There is no
    import across the two, so this is a pinned literal and a stated risk rather than a guarantee —
    see the constant's own note in `watch.py`.
    """
    assert STALE_AFTER_RELEASES == 2


def test_the_committed_ledger_is_past_the_window_today() -> None:
    """The live state, asserted so a re-measurement that closes the gap is noticed rather than assumed."""
    from provael import __version__

    got = published_measurement()
    assert got is not None, "no real measurement is committed"
    gap = releases_behind(got.tool_version, __version__)
    assert gap is not None
    assert gap > STALE_AFTER_RELEASES, (
        f"the published measurement (v{got.tool_version}) is now {gap} release(s) behind "
        f"{__version__}, within the {STALE_AFTER_RELEASES}-release window. If a real re-measurement "
        "landed, update this test and the CHANGELOG — the gap closing is news."
    )
