from pathlib import Path

import pytest

from delphos_ml.config import (
    DEFAULT_KAGGLE_DATASET_VERSION,
    ConfigError,
    _find_env_file,
    load_settings,
)


def test_defaults_resolve_data_dir_against_project_root(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = project_dir / "ml" / "src"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    settings = load_settings()

    assert settings.data_dir == project_dir / "data"
    assert settings.kaggle_dataset == "davidcariboo/player-scores"
    assert settings.kaggle_dataset_version == DEFAULT_KAGGLE_DATASET_VERSION


def test_default_pinned_version_is_a_concrete_version() -> None:
    assert DEFAULT_KAGGLE_DATASET_VERSION >= 1


def test_env_vars_override_defaults(
    project_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(custom))
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET", "someone/other-data")
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "7")

    settings = load_settings()

    assert settings.data_dir == custom
    assert settings.kaggle_dataset == "someone/other-data"
    assert settings.kaggle_dataset_version == 7


def test_relative_data_dir_resolves_against_project_root(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = project_dir / "ml"
    nested.mkdir()
    monkeypatch.chdir(nested)
    monkeypatch.setenv("DELPHOS_DATA_DIR", "scratch/data")

    assert load_settings().data_dir == project_dir / "scratch" / "data"


def test_dotenv_in_an_ancestor_of_the_working_directory_is_read(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project_dir / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    nested = project_dir / "ml"
    nested.mkdir()
    monkeypatch.chdir(nested)

    assert load_settings().kaggle_dataset_version == 42


def test_repo_root_dotenv_is_read_through_load_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    for name in ("DELPHOS_DATA_DIR", "DELPHOS_KAGGLE_DATASET", "DELPHOS_KAGGLE_DATASET_VERSION"):
        monkeypatch.delenv(name, raising=False)

    assert load_settings().kaggle_dataset_version == 42


def test_dotenv_in_the_working_directory_is_read(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = project_dir / "ml"
    cwd.mkdir()
    (cwd / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    assert load_settings().kaggle_dataset_version == 42


def test_nearest_dotenv_wins_over_one_in_an_ancestor(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project_dir / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=1\n", encoding="utf-8")
    cwd = project_dir / "ml"
    cwd.mkdir()
    (cwd / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    assert load_settings().kaggle_dataset_version == 42


def test_nearest_ancestor_dotenv_wins_over_a_farther_one(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project_dir / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=1\n", encoding="utf-8")
    middle = project_dir / "ml"
    middle.mkdir()
    (middle / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    cwd = middle / "src"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    assert load_settings().kaggle_dataset_version == 42


def test_lookup_finds_the_repo_root_dotenv(tmp_path: Path) -> None:
    project = tmp_path / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()

    assert _find_env_file(start=cwd) == tmp_path / ".env"


def test_lookup_finds_the_dotenv_in_the_project_root(tmp_path: Path) -> None:
    project = tmp_path / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    (project / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()

    assert _find_env_file(start=cwd) == project / ".env"


def test_lookup_prefers_the_nearer_dotenv(tmp_path: Path) -> None:
    project = tmp_path / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    (project / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=1\n", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()
    (cwd / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")

    assert _find_env_file(start=cwd) == cwd / ".env"


def test_lookup_ignores_a_dotenv_above_the_repo_root(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    project = repo / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()

    assert _find_env_file(start=cwd) is None


def test_lookup_without_a_project_root_checks_only_the_working_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    cwd = tmp_path / "loose"
    cwd.mkdir()

    assert _find_env_file(start=cwd) is None


def test_lookup_returns_none_when_no_dotenv_is_in_bound(tmp_path: Path) -> None:
    project = tmp_path / "mml"
    project.mkdir()
    (project / "uv.lock").write_text("", encoding="utf-8")
    cwd = project / "src"
    cwd.mkdir()

    assert _find_env_file(start=cwd) is None


def test_no_dotenv_anywhere_falls_back_to_defaults(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project_dir)

    settings = load_settings()

    assert settings.kaggle_dataset == "davidcariboo/player-scores"
    assert settings.kaggle_dataset_version == DEFAULT_KAGGLE_DATASET_VERSION


def test_env_var_wins_over_dotenv(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project_dir / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=42\n", encoding="utf-8")
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "43")

    assert load_settings().kaggle_dataset_version == 43


def test_invalid_value_in_dotenv_is_rejected(project_dir: Path) -> None:
    (project_dir / ".env").write_text("DELPHOS_KAGGLE_DATASET_VERSION=abc\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="DELPHOS_KAGGLE_DATASET_VERSION"):
        load_settings()


@pytest.mark.parametrize("value", ["0", "-1", "latest"])
def test_invalid_version_is_rejected(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", value)

    with pytest.raises(ConfigError, match="DELPHOS_KAGGLE_DATASET_VERSION"):
        load_settings()


@pytest.mark.parametrize(
    "value", ["player-scores", "davidcariboo/player-scores/versions/3", "a/b c"]
)
def test_dataset_must_be_an_unversioned_owner_slug_handle(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET", value)

    with pytest.raises(ConfigError, match="DELPHOS_KAGGLE_DATASET:"):
        load_settings()


def test_relative_data_dir_without_a_project_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loose = tmp_path / "not_a_project"
    loose.mkdir()
    monkeypatch.chdir(loose)
    monkeypatch.delenv("DELPHOS_DATA_DIR", raising=False)

    with pytest.raises(ConfigError, match=r"no uv\.lock found at or above .*DELPHOS_DATA_DIR"):
        load_settings()


def test_absolute_data_dir_works_without_a_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loose = tmp_path / "not_a_project"
    loose.mkdir()
    monkeypatch.chdir(loose)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(tmp_path / "abs data"))

    assert load_settings().data_dir == tmp_path / "abs data"


def test_data_dir_expands_the_home_directory(
    project_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("DELPHOS_DATA_DIR", "~/delphos-data")

    assert load_settings().data_dir == home / "delphos-data"
