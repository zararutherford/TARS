"""`tars` command line. Talks to the daemon over its Unix socket; thin by design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from tars import __version__, config, paths

app = typer.Typer(add_completion=False, help="TARS, a local-only assistant.")
console = Console()


def _print_version(value: bool) -> None:
    if not value:
        return
    console.print(__version__)
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_print_version, is_eager=True, help="Print the version."
        ),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command()
def doctor(
    config_file: Annotated[Path | None, typer.Option("--config", help="Path to tars.toml")] = None,
) -> None:
    """Print the detected profile, config path and data directory."""
    cfg = config.load(config_file)
    report = {
        "version": __version__,
        "profile": cfg.profile.name.value,
        "config_path": str(config_file or paths.config_path()),
        "data_dir": str(paths.data_dir()),
        "store": {"encryption": cfg.store.encryption, "key_source": cfg.store.key_source},
        "models": cfg.models.model_dump(),
    }
    console.print_json(json.dumps(report))


def main() -> None:
    app()
