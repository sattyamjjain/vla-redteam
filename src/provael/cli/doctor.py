"""The `doctor` command: everything about this install that changes what a number means."""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from provael import __version__
from provael.cli._shared import _out, app
from provael.watch import (
    STALE_DAYS,
    age_days,
    latest_measurement,
)


@app.command()
def doctor(
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip the PyPI lookup; everything else is local anyway."),
    ] = False,
) -> None:
    """Diagnose this install in one screen: versions, backends, calibration, freshness.

    WHY THIS EXISTS. There were twenty-six top-level commands and not one of them answered "why did
    that not work on my machine". The first-run transcript shows the cold path is twenty seconds, so
    the install is not the problem — the SECOND run is, when someone reaches for `--policy smolvla`
    without the `[lerobot]` extra, or for the keep-out suite without a calibration, and gets an
    import error or a silent default instead of a diagnosis.

    Everything here is read locally except the PyPI version, which `--offline` skips. Nothing is
    inferred: a backend is reported as importable only after actually importing it, and the
    calibration and freshness rows read the same constants the runtime does.
    """

    from provael.policies.registry import POLICIES, SCAFFOLDING_POLICIES
    from provael.suites import SUITES, make_suite
    from provael.suites.keepout_zones import CALIBRATED_ZONES, REQUIRE_CALIBRATED_ENV

    def row(label: str, value: str, note: str = "") -> None:
        suffix = f"  [dim]{escape(note)}[/dim]" if note else ""
        _out.print(f"  [bold]{label:<22}[/bold] {value}{suffix}")

    _out.print("\n[bold]provael doctor[/bold]\n")

    # ── versions ─────────────────────────────────────────────────────────────
    row("python", platform.python_version(), f"{platform.system()} {platform.machine()}")
    row("provael", __version__, "installed")
    if offline:
        row("pypi", "[dim]skipped (--offline)[/dim]")
    else:
        try:
            import urllib.request

            with urllib.request.urlopen(  # noqa: S310 - fixed https host, no user input
                "https://pypi.org/pypi/provael/json", timeout=6
            ) as fh:
                latest = json.loads(fh.read())["info"]["version"]
            if latest == __version__:
                row("pypi", latest, "up to date")
            else:
                row("pypi", f"[yellow]{latest}[/yellow]", f"installed {__version__} — upgrade")
        except Exception as exc:  # noqa: BLE001 - a diagnostic must not fail on a network blip
            row("pypi", "[dim]unavailable[/dim]", f"{type(exc).__name__}; use --offline to skip")

    # ── policy backends ──────────────────────────────────────────────────────
    _out.print("\n[bold]policy backends[/bold]")
    for name in sorted(POLICIES):
        note = SCAFFOLDING_POLICIES.get(name)
        if note:
            # escape(), because the note names extras in brackets — "needs lerobot[groot], which
            # provael[lerobot] does not install". Rich reads [groot] and [lerobot] as style tags
            # and DELETES them, so this line rendered "needs lerobot, which provael does not
            # install": the opposite of true, since provael[lerobot] exists and installs fine.
            #
            # A disclosure that inverts its own meaning is worse than no disclosure. list-policies
            # got this right (see policy_is_ready above); doctor shipped without it.
            _out.print(f"  [yellow]scaffolding[/yellow]  {name:<10} [dim]{escape(note)}[/dim]")
        else:
            _out.print(f"  [green]ready[/green]        {name:<10}")
    _out.print(
        "  [dim]'ready' = registered and constructible, NOT that a checkpoint is present.[/dim]"
    )

    # ── suites ───────────────────────────────────────────────────────────────
    _out.print("\n[bold]suites[/bold]")
    for name in sorted(SUITES):
        try:
            make_suite(name)
            _out.print(f"  [green]importable[/green]   {name}")
        except Exception as exc:  # noqa: BLE001 - reporting the failure IS the job here
            first = str(exc).strip().splitlines()[0][:78]
            # Same class: an exception message is arbitrary text, and any [...] in it would be
            # eaten as markup. An import error that silently loses part of itself is the worst
            # possible thing to print in a diagnostic command.
            _out.print(f"  [red]unavailable[/red]  {name:<10} [dim]{escape(first)}[/dim]")

    # ── the two things that silently change what a number means ──────────────
    _out.print("\n[bold]predicate & freshness[/bold]")
    strict = os.environ.get(REQUIRE_CALIBRATED_ENV)
    if CALIBRATED_ZONES:
        # Adopted zones carry the evidence that earned them, so print it. A count alone is what
        # this row used to be, and a count cannot distinguish a predicate that catches things from
        # one that cannot fire — which is the state the ten libero_object fits were in.
        versions = sorted({c.tool_version for c in CALIBRATED_ZONES.values()})
        weakest = min(c.detection_rate for c in CALIBRATED_ZONES.values())
        colour = "green" if weakest > 0.0 else "red"
        row(
            "calibrated zones",
            f"[{colour}]{len(CALIBRATED_ZONES)} adopted[/{colour}]",
            f"fitted by {', '.join(versions)}; every other task falls back to the DEFAULT box",
        )
        for task, adopted in sorted(CALIBRATED_ZONES.items()):
            hits = round(adopted.detection_rate * adopted.n_adversarial)
            mark = "green" if adopted.detection_rate > 0.0 else "red"
            _out.print(
                f"    [dim]{task:<20}[/dim] face {adopted.face:<3} "
                f"[{mark}]{100.0 * adopted.detection_rate:.0f}%[/{mark}] "
                f"({hits}/{adopted.n_adversarial} attacked flagged)"
            )
    else:
        row(
            "calibrated zones",
            "[yellow]none adopted[/yellow]",
            "every keep-out run uses the DEFAULT box — see issue #136",
        )
        # NOT "not done yet", which is what this row implied for months. Ten fits exist and are
        # committed; they are unadopted because they were measured and caught nothing. Saying that
        # here is the difference between a reader thinking the work is pending and knowing it was
        # done and rejected.
        _out.print(
            "    [dim]ten libero_object fits exist under results/calibration/ and are NOT"
            " adopted:[/dim]\n"
            "    [dim]the fitted hazard face flagged 0/12 attacked episodes on the one task"
            " with[/dim]\n"
            "    [dim]trajectories to check — see studies/keepout_face_selection/[/dim]"
        )
    row(
        REQUIRE_CALIBRATED_ENV,
        f"[green]{strict}[/green]" if strict else "[yellow]unset[/yellow]",
        "set it to 1 to make an uncalibrated predicate a hard error",
    )

    latest_run = latest_measurement(Path("watch"))
    age = age_days(latest_run)
    if age is None:
        row("last measured", "[red]never[/red]", "no measurement recorded")
    elif age > STALE_DAYS:
        row(
            "last measured",
            f"[red]{int(age)} days ago[/red]",
            f"over STALE_DAYS={STALE_DAYS}; see docs/standards/last-measured.md",
        )
    else:
        row("last measured", f"[green]{int(age)} days ago[/green]", f"within {STALE_DAYS}")

    _out.print(
        f"\n[dim]checked {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%SZ')} · "
        f"nothing here is inferred; every row was read from this install.[/dim]\n"
    )
