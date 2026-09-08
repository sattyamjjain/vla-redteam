"""The `serve` command: the operated/hosted surface, gated on the `hosted` extra."""

from __future__ import annotations

from typing import Annotated

import typer

from provael.cli._shared import _fail, _out, app


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="Bind port.")] = 8000,
) -> None:
    """Run the EXPERIMENTAL reference hosted server (needs the `hosted` extra).

    Not a production signing service: it does not authenticate callers or bind ownership, and every
    signature it produces is the operator's OWN key — untrusted until a verifier adds it to a trust
    store. Disabled by default; set `PROVAEL_ENABLE_EXPERIMENTAL_HOSTED=1` to run it. The free CLI,
    attacks, ASR, SARIF, the Action and local `attest` are never gated.
    """
    try:
        import uvicorn

        from provael.hosted import HostedDisabledError
        from provael.hosted.server import MissingHostedExtraError, create_app
    except ImportError:
        _fail("The hosted server needs the `hosted` extra: pip install 'provael[hosted]'.")
        return
    try:
        application = create_app()
    except (MissingHostedExtraError, HostedDisabledError) as exc:
        _fail(str(exc))
        return
    _out.print(
        f"Provael hosted (EXPERIMENTAL, operator-key-only) on "
        f"[cyan]http://{host}:{port}[/cyan]  —  Ctrl-C to stop"
    )
    uvicorn.run(application, host=host, port=port)
