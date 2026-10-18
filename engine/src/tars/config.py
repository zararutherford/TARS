"""tars.toml: one file holds every model choice, threshold and standing permission.

The data directory is not a config key: the file lives inside it. Override it with the
TARS_DATA_DIR environment variable (see tars.paths).

Profile auto-detect reads hw.memsize once and only sets model names, the escalation band
and the nightly scope. Everything else is the same code on every profile.
"""

from __future__ import annotations

import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Literal

import tomlkit
from pydantic import BaseModel, Field

from tars import paths

GIB = 1024**3


class Profile(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


def profile_for_memory(memsize_bytes: int) -> Profile:
    """Map physical memory to a compute profile. 16 GB is small; 64 GB and above is large."""
    gib = memsize_bytes / GIB
    if gib < 32:
        return Profile.SMALL
    if gib < 64:
        return Profile.MEDIUM
    return Profile.LARGE


def detect_memsize() -> int:
    out = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
    )
    return int(out.stdout.strip())


def detect_profile() -> Profile:
    return profile_for_memory(detect_memsize())


PROFILE_DEFAULTS: dict[Profile, dict[str, object]] = {
    Profile.SMALL: {
        "tier2": "mlx:mlx-community/Qwen3-8B-4bit",
        "drafts": "mlx:mlx-community/Qwen3-8B-4bit",
        "band": [0.40, 0.60],
    },
    Profile.MEDIUM: {
        "tier2": "mlx:mlx-community/Qwen3-30B-A3B-4bit",
        "drafts": "mlx:mlx-community/Qwen3-30B-A3B-4bit",
        "band": [0.35, 0.65],
    },
    Profile.LARGE: {
        "tier2": "mlx:mlx-community/Qwen3-70B-8bit",
        "drafts": "mlx:mlx-community/Qwen3-70B-8bit",
        "band": [0.25, 0.75],
    },
}


class ProfileSection(BaseModel):
    name: Profile = Profile.SMALL


class ModelsSection(BaseModel):
    embedding: str = "BAAI/bge-small-en-v1.5"
    tier1: Literal["heads", "jev"] = "heads"
    tier2: str = "mlx:mlx-community/Qwen3-8B-4bit"
    drafts: str = "mlx:mlx-community/Qwen3-8B-4bit"
    jev_url: str = "http://127.0.0.1:8000"


class LlmSection(BaseModel):
    idle_unload_s: int = 600
    tier2_daily_budget: int = 300
    fallback_p: float = 0.8


class CascadeSection(BaseModel):
    band: tuple[float, float] = (0.40, 0.60)
    vip_always_tier2: bool = True


class NotifySection(BaseModel):
    min_p: float = 0.75
    daily_cap: int = 12
    quiet_hours: tuple[str, str] = ("23:00", "08:00")


class LearningSection(BaseModel):
    reply_fast_minutes: int = 20
    reply_slow_days: int = 3
    maturity_days: int = 14
    example_max_age_days: int = 180
    decay_days: int = 90


class ActiveLearningSection(BaseModel):
    per_day: int = 3


FeatureMode = Literal["off", "shadow", "live"]


class FeaturesSection(BaseModel):
    drafts: FeatureMode = "shadow"
    commitments: FeatureMode = "off"
    booking: FeatureMode = "off"
    shadow_days: int = 14
    graduate_precision: float = 0.85


class DraftsSection(BaseModel):
    sink: Literal["mail", "inbox"] = "mail"


PermissionMode = Literal["confirm", "auto", "off"]


class PermissionsSection(BaseModel):
    calendar_create: PermissionMode = "auto"


class StoreSection(BaseModel):
    encryption: Literal["sqlcipher", "none"] = "none"
    key_source: Literal["keychain", "file"] = "keychain"


class EgressSection(BaseModel):
    proxy_port: int = 8081


class Config(BaseModel):
    profile: ProfileSection = Field(default_factory=ProfileSection)
    models: ModelsSection = Field(default_factory=ModelsSection)
    llm: LlmSection = Field(default_factory=LlmSection)
    cascade: CascadeSection = Field(default_factory=CascadeSection)
    notify: NotifySection = Field(default_factory=NotifySection)
    learning: LearningSection = Field(default_factory=LearningSection)
    active_learning: ActiveLearningSection = Field(default_factory=ActiveLearningSection)
    features: FeaturesSection = Field(default_factory=FeaturesSection)
    drafts: DraftsSection = Field(default_factory=DraftsSection)
    permissions: PermissionsSection = Field(default_factory=PermissionsSection)
    store: StoreSection = Field(default_factory=StoreSection)
    egress: EgressSection = Field(default_factory=EgressSection)


def defaults_for(profile: Profile) -> Config:
    """A Config with the profile's model names and band filled in and everything else default."""
    p = PROFILE_DEFAULTS[profile]
    band = p["band"]
    assert isinstance(band, list)
    return Config(
        profile=ProfileSection(name=profile),
        models=ModelsSection(tier2=str(p["tier2"]), drafts=str(p["drafts"])),
        cascade=CascadeSection(band=(float(band[0]), float(band[1]))),
    )


def load(path: Path | None = None, *, profile: Profile | None = None) -> Config:
    """Load tars.toml. A missing file yields the auto-detected profile's defaults.

    Keys present in the file override the profile defaults; the profile name in the file
    overrides auto-detection.
    """
    path = path or paths.config_path()
    detected = profile or detect_profile()
    if not path.exists():
        return defaults_for(detected)
    doc = tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    chosen = Profile(doc.get("profile", {}).get("name", detected))
    base = defaults_for(chosen).model_dump(mode="json")
    merged = _deep_merge(base, doc)
    return Config.model_validate(merged)


def write_example(path: Path, profile: Profile) -> None:
    """Write tars.toml for the given profile. Used by `make setup` on first run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    doc.add(tomlkit.comment("TARS configuration. Profile is auto-detected from hw.memsize."))
    for section, values in defaults_for(profile).model_dump(mode="json").items():
        table = tomlkit.table()
        for key, value in values.items():
            table.add(key, value)
        doc.add(section, table)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    out = dict(base)
    for key, value in override.items():
        existing = out.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            out[key] = _deep_merge(existing, value)
            continue
        out[key] = value
    return out
