"""Shared pytest fixtures: an isolated project directory and a fake Kaggle download."""

import itertools
from collections.abc import Callable
from pathlib import Path

import kagglehub
import pytest

PLAYERS_CSV = (
    "player_id,name,country_code,market_value_in_eur,date_of_birth,height_in_cm\n"
    "1,Lionel Messi,AR,25000000,1987-06-24,170\n"
    "2,Some Player,NA,,1999-01-01,\n"
    '3,"Comma, Name",,1500000.5,,181\n'
)
CLUBS_CSV = "club_id,club_code,squad_size\n10,fc-barcelona,25\n11,real-madrid,\n"
GAMES_CSV = "game_id,attendance\n1,1000\n2,unknown\n"

MakeDataset = Callable[[dict[str, str | bytes]], Path]
FakeDownload = Callable[[Path], list[str]]


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that reaches the real Kaggle download."""

    def _refuse(*args: object, **kwargs: object) -> str:
        raise AssertionError("tests must not call the real kagglehub.dataset_download")

    monkeypatch.setattr(kagglehub, "dataset_download", _refuse)


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh repo-like root (marked by uv.lock) as the CWD, with no DELPHOS_* env vars set."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "uv.lock").write_text("", encoding="utf-8")
    monkeypatch.chdir(root)
    for name in ("DELPHOS_DATA_DIR", "DELPHOS_KAGGLE_DATASET", "DELPHOS_KAGGLE_DATASET_VERSION"):
        monkeypatch.delenv(name, raising=False)
    return root


@pytest.fixture
def make_dataset(tmp_path: Path) -> MakeDataset:
    """Build a directory that looks like an extracted Kaggle dataset.

    Keys are paths relative to the dataset root; str values are written as UTF-8, bytes as-is.
    """
    counter = itertools.count()

    def _make(files: dict[str, str | bytes]) -> Path:
        source = tmp_path / "kaggle_cache" / f"dataset_{next(counter)}"
        source.mkdir(parents=True)
        for name, content in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = content.encode("utf-8") if isinstance(content, str) else content
            path.write_bytes(data)
        return source

    return _make


@pytest.fixture
def sample_dataset(make_dataset: MakeDataset) -> Path:
    return make_dataset(
        {"players.csv": PLAYERS_CSV, "clubs.csv": CLUBS_CSV, "games.csv": GAMES_CSV}
    )


@pytest.fixture
def fake_download(monkeypatch: pytest.MonkeyPatch) -> FakeDownload:
    """Point kagglehub.dataset_download at a local directory and record the handles it gets."""

    def _install(source: Path) -> list[str]:
        calls: list[str] = []

        def _download(handle: str, *args: object, **kwargs: object) -> str:
            calls.append(handle)
            return str(source)

        monkeypatch.setattr(kagglehub, "dataset_download", _download)
        return calls

    return _install
