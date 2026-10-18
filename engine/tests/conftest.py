from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every test gets an empty TARS_DATA_DIR. Nothing under ~/Library is touched."""
    data = tmp_path / "tars-data"
    data.mkdir()
    monkeypatch.setenv("TARS_DATA_DIR", str(data))
    yield data
