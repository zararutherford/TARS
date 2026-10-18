from __future__ import annotations

import json

from typer.testing import CliRunner

from tars import __version__
from tars.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_reports_profile() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["profile"] in {"small", "medium", "large"}
    assert "tars-data" in report["data_dir"]
