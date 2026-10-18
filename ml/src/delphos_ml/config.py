"""Pipeline settings, read from environment variables and the repo-root `.env`.

Input: `DELPHOS_*` environment variables, then `.env`, then the defaults in `Settings`.
Output: a validated `Settings` object, or `ConfigError` naming each invalid variable.
Responsibility: defines every configuration name and default.

The repo root is the nearest directory at or above the working directory that contains
`uv.lock`. `.env` is read from there, or from the working directory when no repo root is found.
A relative `DELPHOS_DATA_DIR` (including the default `data`) resolves against the repo root, and
`~` expands to the home directory. Without a repo root, a relative data directory is an error,
so a container must either include `uv.lock` or set an absolute `DELPHOS_DATA_DIR`. Anchoring on
this file's location (`Path(__file__)`) was rejected because it breaks once the package is
installed outside the source tree.
"""

from pathlib import Path

from pydantic import Field, PositiveInt, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_KAGGLE_DATASET = "davidcariboo/player-scores"
# Latest version of davidcariboo/player-scores on 2026-10-17. Bumping it is a deliberate
# data refresh (ADR-010).
DEFAULT_KAGGLE_DATASET_VERSION = 679

ENV_PREFIX = "DELPHOS_"
PROJECT_ROOT_MARKER = "uv.lock"


class ConfigError(Exception):
    """A configuration value is invalid. The message names the offending variables."""


def find_project_root(start: Path | None = None) -> Path | None:
    """Return the nearest directory at or above `start` (default: CWD) holding `uv.lock`."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / PROJECT_ROOT_MARKER).is_file():
            return candidate
    return None


class Settings(BaseSettings):
    """Configuration for the offline pipeline. Each field maps to `DELPHOS_<FIELD NAME>`."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore")

    data_dir: Path = Field(default=Path("data"), validate_default=True)
    kaggle_dataset: str = Field(
        default=DEFAULT_KAGGLE_DATASET, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
    )
    kaggle_dataset_version: PositiveInt = DEFAULT_KAGGLE_DATASET_VERSION

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        try:
            value = value.expanduser()
        except RuntimeError as exc:  # no home directory to expand "~" against
            raise ValueError(str(exc)) from exc
        if value.is_absolute():
            return value
        root = find_project_root()
        if root is None:
            raise ValueError(
                f"no {PROJECT_ROOT_MARKER} found at or above {Path.cwd()}; run from inside the "
                f"project or set an absolute {ENV_PREFIX}DATA_DIR"
            )
        return root / value


def load_settings() -> Settings:
    """Build `Settings` from the environment and `.env`.

    Raises `ConfigError`, naming each invalid variable, if a value fails validation.
    """
    env_file = (find_project_root() or Path.cwd()) / ".env"
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        problems = "; ".join(
            f"{ENV_PREFIX}{'_'.join(str(part) for part in error['loc']).upper()}: "
            f"{error['msg'].removeprefix('Value error, ')}"
            for error in exc.errors()
        )
        raise ConfigError(f"invalid configuration: {problems}") from exc
