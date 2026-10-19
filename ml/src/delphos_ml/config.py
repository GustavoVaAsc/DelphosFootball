"""Pipeline settings, read from environment variables and the nearest `.env`.

Input: `DELPHOS_*` environment variables, then the nearest `.env`, then the defaults in `Settings`.
Output: a validated `Settings` object, or `ConfigError` naming each invalid variable.
Responsibility: defines every configuration name and default.

The project root is the nearest directory at or above the working directory that contains
`uv.lock`; a relative `DELPHOS_DATA_DIR` (including the default `data`) resolves against it, and
`~` expands to the home directory. Without a project root, a relative data directory is an error,
so a container must either include `uv.lock` or set an absolute `DELPHOS_DATA_DIR`. `.env` is
looked up separately from the project root: the nearest `.env` at or above the working directory
is read (first hit wins), but the walk stops at the project root's parent (the repository root),
so a `.env` above the repository root is never read; without a project root only the working
directory itself is checked, and when no `.env` is found no env file is loaded. Anchoring on this
file's location (`Path(__file__)`) was rejected because it breaks once the package is installed
outside the source tree.
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


def _find_env_file(start: Path | None = None) -> Path | None:
    """Return the nearest `.env` from `start` (default: CWD) up to the project root's parent.

    With no project root, only `start` itself is checked. Returns None when no `.env` is in
    that range.
    """
    start = (start or Path.cwd()).resolve()
    project_root = find_project_root(start)
    top = project_root.parent if project_root is not None else start
    for candidate in (start, *start.parents):
        env_file = candidate / ".env"
        if env_file.is_file():
            return env_file
        if candidate == top:
            break
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
    """Build `Settings` from the environment and the nearest `.env`.

    Raises `ConfigError`, naming each invalid variable, if a value fails validation.
    """
    try:
        return Settings(_env_file=_find_env_file())
    except ValidationError as exc:
        problems = "; ".join(
            f"{ENV_PREFIX}{'_'.join(str(part) for part in error['loc']).upper()}: "
            f"{error['msg'].removeprefix('Value error, ')}"
            for error in exc.errors()
        )
        raise ConfigError(f"invalid configuration: {problems}") from exc
