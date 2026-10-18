from __future__ import annotations

from pathlib import Path

from tars import config, paths
from tars.config import Profile

GIB = 1024**3
EXAMPLE = Path(__file__).resolve().parents[2] / "tars.toml.example"


def test_profile_thresholds() -> None:
    assert config.profile_for_memory(8 * GIB) is Profile.SMALL
    assert config.profile_for_memory(16 * GIB) is Profile.SMALL
    assert config.profile_for_memory(32 * GIB) is Profile.MEDIUM
    assert config.profile_for_memory(48 * GIB) is Profile.MEDIUM
    assert config.profile_for_memory(64 * GIB) is Profile.LARGE
    assert config.profile_for_memory(192 * GIB) is Profile.LARGE


def test_detect_profile_on_this_machine_is_valid() -> None:
    assert config.detect_profile() in set(Profile)


def test_missing_file_yields_profile_defaults(tmp_path: Path) -> None:
    cfg = config.load(tmp_path / "absent.toml", profile=Profile.SMALL)
    assert cfg.profile.name is Profile.SMALL
    assert cfg.cascade.band == (0.40, 0.60)
    assert cfg.store.encryption == "none"


def test_file_overrides_defaults_and_profile(tmp_path: Path) -> None:
    path = tmp_path / "tars.toml"
    path.write_text('[profile]\nname = "large"\n\n[notify]\nmin_p = 0.9\n', encoding="utf-8")
    cfg = config.load(path, profile=Profile.SMALL)
    assert cfg.profile.name is Profile.LARGE
    assert cfg.cascade.band == (0.25, 0.75)
    assert cfg.notify.min_p == 0.9
    assert cfg.notify.daily_cap == 12


def test_write_example_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "tars.toml"
    config.write_example(path, Profile.MEDIUM)
    cfg = config.load(path, profile=Profile.SMALL)
    assert cfg.profile.name is Profile.MEDIUM
    assert cfg.models.tier2.startswith("mlx:")


def test_paths_honor_env(isolated_data_dir: Path) -> None:
    assert paths.data_dir() == isolated_data_dir
    assert paths.daemon_socket() == isolated_data_dir / "run" / "daemon.sock"


def test_example_file_matches_small_profile_defaults() -> None:
    assert EXAMPLE.exists()
    assert config.load(EXAMPLE, profile=Profile.LARGE) == config.defaults_for(Profile.SMALL)
