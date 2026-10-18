"""Filesystem locations. Every path TARS reads or writes is named here."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "TARS_DATA_DIR"
DEFAULT_DATA_DIR = Path("~/Library/Application Support/TARS")


def data_dir() -> Path:
    """Return the TARS data directory, honoring TARS_DATA_DIR for tests and dogfooding."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_DATA_DIR.expanduser()


def config_path() -> Path:
    return data_dir() / "tars.toml"


def store_path() -> Path:
    return data_dir() / "store.db"


def run_dir() -> Path:
    return data_dir() / "run"


def daemon_socket() -> Path:
    return run_dir() / "daemon.sock"


def llm_socket() -> Path:
    return run_dir() / "llm.sock"


def log_dir() -> Path:
    return data_dir() / "logs"
