import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner, Result

from delphos_ml.config import DEFAULT_KAGGLE_DATASET_VERSION
from delphos_ml.pipeline import ingest as ingest_module
from delphos_ml.pipeline.cli import app

runner = CliRunner()

MakeDataset = Callable[[dict[str, str | bytes]], Path]
FakeDownload = Callable[[Path], list[str]]

STAGING_PREFIX = ".ingest-staging-"
RETIRED_PREFIX = ".ingest-retired-"


def invoke_ingest() -> Result:
    return runner.invoke(app, ["ingest"])


def ingest_dir(project_dir: Path) -> Path:
    return project_dir / "data" / "ingest"


def read_rows(path: Path) -> list[dict[str, str | None]]:
    return pq.read_table(path).to_pylist()


@pytest.fixture(autouse=True)
def no_rename_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_module, "_RENAME_RETRY_DELAY_SECONDS", 0)


# --- Faithful copy -------------------------------------------------------------------------


def test_each_csv_becomes_a_parquet_file_with_identical_text(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0, result.output
    out = ingest_dir(project_dir)
    assert sorted(p.name for p in out.glob("*.parquet")) == [
        "clubs.parquet",
        "games.parquet",
        "players.parquet",
    ]
    assert read_rows(out / "players.parquet") == [
        {
            "player_id": "1",
            "name": "Lionel Messi",
            "country_code": "AR",
            "market_value_in_eur": "25000000",
            "date_of_birth": "1987-06-24",
            "height_in_cm": "170",
        },
        {
            "player_id": "2",
            "name": "Some Player",
            "country_code": "NA",
            "market_value_in_eur": None,
            "date_of_birth": "1999-01-01",
            "height_in_cm": None,
        },
        {
            "player_id": "3",
            "name": "Comma, Name",
            "country_code": None,
            "market_value_in_eur": "1500000.5",
            "date_of_birth": None,
            "height_in_cm": "181",
        },
    ]
    assert read_rows(out / "clubs.parquet") == [
        {"club_id": "10", "club_code": "fc-barcelona", "squad_size": "25"},
        {"club_id": "11", "club_code": "real-madrid", "squad_size": None},
    ]
    assert read_rows(out / "games.parquet") == [
        {"game_id": "1", "attendance": "1000"},
        {"game_id": "2", "attendance": "unknown"},
    ]


def test_every_column_is_stored_as_text(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    fake_download(sample_dataset)

    assert invoke_ingest().exit_code == 0

    for parquet in ingest_dir(project_dir).glob("*.parquet"):
        schema = pq.read_schema(parquet)
        assert {str(field.type) for field in schema} == {"string"}, parquet.name


def test_text_survives_exactly_and_only_unquoted_empty_fields_are_null(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(
        make_dataset(
            {
                "values.csv": (
                    "code,flag,fee,country,number,missing,empty_text,note\n"
                    '007,True,700000.000,NA,-,,"","line one\nline two"\n'
                    ' 1 ,false,1e3,null,"""quoted""",,"",N/A\n'
                )
            }
        )
    )

    assert invoke_ingest().exit_code == 0

    assert read_rows(ingest_dir(project_dir) / "values.parquet") == [
        {
            "code": "007",
            "flag": "True",
            "fee": "700000.000",
            "country": "NA",
            "number": "-",
            "missing": None,
            "empty_text": "",
            "note": "line one\nline two",
        },
        {
            "code": " 1 ",
            "flag": "false",
            "fee": "1e3",
            "country": "null",
            "number": '"quoted"',
            "missing": None,
            "empty_text": "",
            "note": "N/A",
        },
    ]


def test_blank_lines_are_skipped(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(make_dataset({"t.csv": "a,b\n1,2\n\n3,4\n"}))

    assert invoke_ingest().exit_code == 0

    assert read_rows(ingest_dir(project_dir) / "t.parquet") == [
        {"a": "1", "b": "2"},
        {"a": "3", "b": "4"},
    ]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param("a\n1\n\n2\n", ["1", None, "2"], id="middle"),
        pytest.param("a\n1\n\n", ["1", None], id="last-row-empty"),
        pytest.param("a\r\n1\r\n\r\n2\r\n", ["1", None, "2"], id="crlf"),
        pytest.param('a\n""\n\n1', ["", None, "1"], id="no-final-newline"),
        pytest.param("a\n1\n", ["1"], id="final-newline-adds-no-row"),
    ],
)
def test_single_column_empty_lines_are_null_rows(
    project_dir: Path,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    content: str,
    expected: list[str | None],
) -> None:
    fake_download(make_dataset({"t.csv": content}))

    assert invoke_ingest().exit_code == 0

    assert [row["a"] for row in read_rows(ingest_dir(project_dir) / "t.parquet")] == expected


def test_utf8_bom_is_stripped_from_the_header(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(make_dataset({"t.csv": b"\xef\xbb\xbfa,b\n1,2\n"}))

    assert invoke_ingest().exit_code == 0

    table = pq.read_table(ingest_dir(project_dir) / "t.parquet")
    assert table.column_names == ["a", "b"]
    assert table.to_pylist() == [{"a": "1", "b": "2"}]


def test_tiny_blocks_keep_multiline_rows_exact(
    project_dir: Path,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ingest_module, "_CSV_BLOCK_BYTES", 64)
    expected = [{"id": str(i), "text": f"line {i}\nsecond, line", "flag": ""} for i in range(50)]
    body = "".join(f'{row["id"]},"{row["text"]}",""\n' for row in expected)
    fake_download(make_dataset({"t.csv": "id,text,flag\n" + body}))

    assert invoke_ingest().exit_code == 0

    parquet = ingest_dir(project_dir) / "t.parquet"
    assert read_rows(parquet) == expected
    assert pq.ParquetFile(parquet).num_row_groups > 1
    snapshot = json.loads((ingest_dir(project_dir) / "_snapshot.json").read_text("utf-8"))
    assert snapshot["tables"]["t"]["rows"] == 50


def test_header_only_csv_becomes_an_empty_table(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(make_dataset({"t.csv": "a,b\n"}))

    assert invoke_ingest().exit_code == 0

    table = pq.read_table(ingest_dir(project_dir) / "t.parquet")
    assert table.column_names == ["a", "b"]
    assert table.num_rows == 0


# --- Kaggle handle and overrides -----------------------------------------------------------


def test_pinned_versioned_handle_is_passed_to_kagglehub(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    calls = fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0
    assert calls == [f"davidcariboo/player-scores/versions/{DEFAULT_KAGGLE_DATASET_VERSION}"]
    assert "overridden" not in result.output


def test_env_overrides_change_the_requested_handle_and_are_announced(
    project_dir: Path,
    sample_dataset: Path,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = fake_download(sample_dataset)
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET", "someone/other-data")
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "7")

    result = invoke_ingest()

    assert result.exit_code == 0
    assert calls == ["someone/other-data/versions/7"]
    assert "using overridden dataset someone/other-data (default davidcariboo/player-scores)" in (
        result.output
    )
    assert f"using overridden version 7 (default {DEFAULT_KAGGLE_DATASET_VERSION})" in (
        result.output
    )


def test_progress_names_the_data_dir_source_and_each_table(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0
    assert str(project_dir / "data") in result.output
    assert str(sample_dataset) in result.output
    assert "reading players (" in result.output
    assert "players: 3 rows x 6 columns in " in result.output


# --- Snapshot ------------------------------------------------------------------------------


def expected_snapshot_hash(source: Path) -> str:
    """Independent restatement of the documented combined-hash definition."""
    lines = []
    for csv in sorted(source.glob("*.csv"), key=lambda p: p.name):
        digest = hashlib.sha256(csv.read_bytes()).hexdigest()
        lines.append(f"{digest}  {csv.name}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def test_snapshot_metadata_describes_the_source(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    fake_download(sample_dataset)

    assert invoke_ingest().exit_code == 0

    snapshot = json.loads((ingest_dir(project_dir) / "_snapshot.json").read_text("utf-8"))
    assert snapshot["dataset"] == "davidcariboo/player-scores"
    assert snapshot["version"] == DEFAULT_KAGGLE_DATASET_VERSION
    assert snapshot["handle"] == (
        f"davidcariboo/player-scores/versions/{DEFAULT_KAGGLE_DATASET_VERSION}"
    )
    assert "downloaded_at" not in snapshot
    ingested_at = datetime.fromisoformat(snapshot["ingested_at"])
    assert ingested_at.utcoffset() is not None
    assert ingested_at.utcoffset().total_seconds() == 0
    assert snapshot["tool_versions"] == {
        "kagglehub": version("kagglehub"),
        "pyarrow": version("pyarrow"),
    }
    assert snapshot["snapshot_sha256"] == expected_snapshot_hash(sample_dataset)
    assert list(snapshot["tables"]) == ["clubs", "games", "players"]
    players_csv = sample_dataset / "players.csv"
    assert snapshot["tables"]["players"] == {
        "source_file": "players.csv",
        "parquet_file": "players.parquet",
        "sha256": hashlib.sha256(players_csv.read_bytes()).hexdigest(),
        "rows": 3,
        "columns": 6,
        "column_names": [
            "player_id",
            "name",
            "country_code",
            "market_value_in_eur",
            "date_of_birth",
            "height_in_cm",
        ],
    }


def test_snapshot_hash_is_deterministic_and_content_sensitive(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    def snapshot_hash(files: dict[str, str | bytes]) -> str:
        fake_download(make_dataset(files))
        assert invoke_ingest().exit_code == 0
        snapshot = json.loads((ingest_dir(project_dir) / "_snapshot.json").read_text("utf-8"))
        return snapshot["snapshot_sha256"]

    first = snapshot_hash({"a.csv": "x\n1\n", "b.csv": "y\n2\n"})
    same_content_other_order = snapshot_hash({"b.csv": "y\n2\n", "a.csv": "x\n1\n"})
    changed = snapshot_hash({"a.csv": "x\n1\n", "b.csv": "y\n3\n"})

    assert first == same_content_other_order
    assert first != changed


# --- Re-runs, leftovers, and ownership -----------------------------------------------------


def test_rerun_removes_stale_files(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(make_dataset({"old_table.csv": "x\n1\n", "kept.csv": "y\n2\n"}))
    assert invoke_ingest().exit_code == 0
    (ingest_dir(project_dir) / "notes.txt").write_text("left behind", encoding="utf-8")

    fake_download(make_dataset({"kept.csv": "y\n3\n"}))
    assert invoke_ingest().exit_code == 0

    assert sorted(p.name for p in ingest_dir(project_dir).iterdir()) == [
        "_snapshot.json",
        "kept.parquet",
    ]
    assert list((project_dir / "data").iterdir()) == [ingest_dir(project_dir)]


def write_previous_output(
    directory: Path, ingested_at: str = "2026-10-01T00:00:00Z", parquet_files: tuple[str, ...] = ()
) -> None:
    """Plant a directory that looks like a complete earlier ingest output."""
    directory.mkdir(parents=True)
    listed = parquet_files or ("previous.parquet",)
    snapshot = {
        "ingested_at": ingested_at,
        "tables": {Path(name).stem: {"parquet_file": name} for name in listed},
    }
    (directory / "_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    (directory / "previous.parquet").write_bytes(b"old")


def test_leftover_staging_and_retired_directories_are_removed(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    data = project_dir / "data"
    write_previous_output(data / "ingest")
    (data / f"{STAGING_PREFIX}x").mkdir()
    write_previous_output(data / f"{RETIRED_PREFIX}x")
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0
    assert list(data.iterdir()) == [data / "ingest"]
    assert f"{RETIRED_PREFIX}x" in result.output


@pytest.mark.parametrize("leftover_name", [f"{STAGING_PREFIX}locked", f"{RETIRED_PREFIX}locked"])
def test_leftover_that_cannot_be_deleted_only_warns(
    project_dir: Path,
    sample_dataset: Path,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
    leftover_name: str,
) -> None:
    data = project_dir / "data"
    write_previous_output(data / "ingest")
    write_previous_output(data / leftover_name)
    original_rmtree = shutil.rmtree

    def stubborn_rmtree(path: str | Path, *args: object, **kwargs: object) -> None:
        if Path(path).name == leftover_name:
            raise PermissionError("a terminal is using it")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", stubborn_rmtree)
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0, result.output
    assert "warning:" in result.output
    assert leftover_name in result.output
    assert (data / leftover_name).is_dir()
    assert (data / "ingest" / "players.parquet").is_file()


def test_newest_complete_retired_copy_is_restored_and_others_discarded(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    data = project_dir / "data"
    write_previous_output(data / f"{RETIRED_PREFIX}older", ingested_at="2026-10-01T00:00:00Z")
    write_previous_output(data / f"{RETIRED_PREFIX}newer", ingested_at="2026-10-02T00:00:00Z")
    fake_download(make_dataset({"README.md": "no tables, so the run fails after recovery"}))

    result = invoke_ingest()

    assert result.exit_code == 1
    assert f"restored {data / 'ingest'} from {RETIRED_PREFIX}newer" in result.output
    assert f"{RETIRED_PREFIX}older" in result.output
    snapshot = json.loads((data / "ingest" / "_snapshot.json").read_text("utf-8"))
    assert snapshot["ingested_at"] == "2026-10-02T00:00:00Z"
    assert list(data.iterdir()) == [data / "ingest"]


def test_incomplete_retired_copy_is_not_restored(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    data = project_dir / "data"
    incomplete = data / f"{RETIRED_PREFIX}broken"
    write_previous_output(incomplete, parquet_files=("previous.parquet", "missing.parquet"))
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 0, result.output
    assert "restored" not in result.output
    assert "warning:" in result.output
    assert incomplete.name in result.output
    assert list(data.iterdir()) == [data / "ingest"]
    assert (data / "ingest" / "players.parquet").is_file()


def test_restore_retries_a_locked_rename(
    project_dir: Path,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = project_dir / "data"
    write_previous_output(data / f"{RETIRED_PREFIX}abc")
    rename = FlakyRename(RETIRED_PREFIX, failures=2)
    monkeypatch.setattr(Path, "rename", rename)
    fake_download(make_dataset({"README.md": "no tables, so the run fails after recovery"}))

    result = invoke_ingest()

    assert rename.attempts == 3
    assert "restored" in result.output
    assert (data / "ingest" / "previous.parquet").is_file()


def test_lone_retired_directory_is_restored_when_ingest_is_missing(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    data = project_dir / "data"
    write_previous_output(data / f"{RETIRED_PREFIX}abc")
    fake_download(make_dataset({"README.md": "no tables, so the run fails after recovery"}))

    result = invoke_ingest()

    assert result.exit_code == 1
    assert "restored" in result.output
    assert sorted(p.name for p in (data / "ingest").iterdir()) == [
        "_snapshot.json",
        "previous.parquet",
    ]
    assert list(data.iterdir()) == [data / "ingest"]


def test_unowned_ingest_directory_is_not_replaced(
    project_dir: Path, sample_dataset: Path, fake_download: FakeDownload
) -> None:
    foreign = ingest_dir(project_dir)
    foreign.mkdir(parents=True)
    (foreign / "my_notes.txt").write_text("keep me", encoding="utf-8")
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 1
    assert "was not written by ingest; refusing to replace it" in result.output
    assert [p.name for p in foreign.iterdir()] == ["my_notes.txt"]


def test_absolute_data_dir_with_a_space_works(
    project_dir: Path,
    tmp_path: Path,
    sample_dataset: Path,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = tmp_path / "my data dir"
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data))
    fake_download(sample_dataset)

    assert invoke_ingest().exit_code == 0

    assert (data / "ingest" / "players.parquet").is_file()
    assert not (project_dir / "data").exists()


# --- Failures ------------------------------------------------------------------------------


@pytest.fixture
def previous_output(
    project_dir: Path, make_dataset: MakeDataset, fake_download: FakeDownload
) -> None:
    fake_download(make_dataset({"previous.csv": "x\n1\n"}))
    assert invoke_ingest().exit_code == 0


def assert_clean_failure(project_dir: Path, result: Result) -> None:
    """Exit 1 with a one-line message, no traceback, and the previous output untouched."""
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit)
    assert "ingest failed: " in result.output
    assert "Traceback" not in result.output
    out = ingest_dir(project_dir)
    assert sorted(p.name for p in out.iterdir()) == ["_snapshot.json", "previous.parquet"]
    assert list((project_dir / "data").iterdir()) == [out]


def test_empty_download_fails_and_keeps_previous_output(
    project_dir: Path,
    previous_output: None,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
) -> None:
    fake_download(make_dataset({"README.md": "no tables here"}))

    result = invoke_ingest()

    assert_clean_failure(project_dir, result)
    assert "no CSV files" in result.output


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(b"", "no header row", id="empty-file"),
        pytest.param(b"a,b,a,c,c\n1,2,3,4,5\n", "duplicate column names 'a', 'c'", id="dup"),
        pytest.param(b"a,,b, \n1,2,3,4\n", "empty column names at positions 2, 4", id="empty"),
        pytest.param(b"a,b\n1\n", "could not convert broken.csv", id="ragged-row"),
        pytest.param(b"a,b\n\xff\xfe,2\n", "could not convert broken.csv", id="bad-utf8-body"),
        pytest.param(b"\xff\n1\n", "could not convert broken.csv", id="bad-utf8-header"),
    ],
)
def test_unreadable_csv_fails_and_keeps_previous_output(
    project_dir: Path,
    previous_output: None,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    content: bytes,
    expected: str,
) -> None:
    fake_download(make_dataset({"good.csv": "x\n1\n", "broken.csv": content}))

    result = invoke_ingest()

    assert_clean_failure(project_dir, result)
    assert "broken.csv" in result.output
    assert expected in result.output


def test_case_insensitive_table_name_collision_fails(
    project_dir: Path,
    previous_output: None,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
) -> None:
    fake_download(make_dataset({"a/Players.csv": "x\n1\n", "b/players.csv": "x\n2\n"}))

    result = invoke_ingest()

    assert_clean_failure(project_dir, result)
    assert "a/Players.csv" in result.output
    assert "b/players.csv" in result.output


def test_download_error_fails_with_the_handle_in_the_message(
    project_dir: Path, previous_output: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kagglehub

    def _boom(handle: str, *args: object, **kwargs: object) -> str:
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(kagglehub, "dataset_download", _boom)

    result = invoke_ingest()

    assert_clean_failure(project_dir, result)
    assert "davidcariboo/player-scores/versions/" in result.output
    assert "403 Forbidden" in result.output


def test_invalid_config_fails_with_a_one_line_message(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "0")

    result = invoke_ingest()

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "DELPHOS_KAGGLE_DATASET_VERSION" in result.output
    assert not ingest_dir(project_dir).exists()


# --- Swap failures -------------------------------------------------------------------------


class FlakyRename:
    """Stand-in for Path.rename that fails `failures` times for sources named `prefix*`."""

    def __init__(self, prefix: str, failures: int) -> None:
        self.prefix = prefix
        self.failures = failures
        self.attempts = 0
        self.original = Path.rename

    def __get__(self, instance: Path, owner: type) -> Callable[[Path], Path]:
        return lambda target: self.rename(instance, target)

    def rename(self, source: Path, target: Path) -> Path:
        if source.name.startswith(self.prefix):
            self.attempts += 1
            if self.attempts <= self.failures:
                raise PermissionError("[WinError 5] Access is denied")
        return self.original(source, target)


def test_staging_rename_succeeds_after_two_locked_attempts(
    project_dir: Path,
    previous_output: None,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rename = FlakyRename(STAGING_PREFIX, failures=2)
    monkeypatch.setattr(Path, "rename", rename)
    fake_download(make_dataset({"fresh.csv": "y\n2\n"}))

    result = invoke_ingest()

    assert result.exit_code == 0, result.output
    assert rename.attempts == 3
    assert sorted(p.name for p in ingest_dir(project_dir).iterdir()) == [
        "_snapshot.json",
        "fresh.parquet",
    ]


def test_locked_target_rolls_back_after_retries(
    project_dir: Path,
    previous_output: None,
    sample_dataset: Path,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_rename = Path.rename
    staging_attempts: list[Path] = []

    def locked_rename(self: Path, target: Path) -> Path:
        if self.name.startswith(STAGING_PREFIX):
            staging_attempts.append(self)
            raise PermissionError("[WinError 5] Access is denied")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", locked_rename)
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert_clean_failure(project_dir, result)
    assert len(staging_attempts) == 3
    assert "close programs or terminals using" in result.output
    assert "Access is denied" in result.output


def test_failed_rollback_names_the_retired_directory(
    project_dir: Path,
    previous_output: None,
    sample_dataset: Path,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_rename = Path.rename

    def locked_rename(self: Path, target: Path) -> Path:
        if self.name.startswith(STAGING_PREFIX):
            raise PermissionError("staging locked")
        if self.name.startswith(RETIRED_PREFIX):
            raise PermissionError("retired locked")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", locked_rename)
    fake_download(sample_dataset)

    result = invoke_ingest()

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    data = project_dir / "data"
    retired = [p for p in data.iterdir() if p.name.startswith(RETIRED_PREFIX)]
    assert len(retired) == 1
    assert sorted(p.name for p in retired[0].iterdir()) == ["_snapshot.json", "previous.parquet"]
    assert str(retired[0]) in result.output
    assert "staging locked" in result.output
    assert "retired locked" in result.output


def test_cleanup_failure_after_swap_warns_but_succeeds(
    project_dir: Path,
    previous_output: None,
    make_dataset: MakeDataset,
    fake_download: FakeDownload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_rmtree = shutil.rmtree

    def stubborn_rmtree(path: str | Path, *args: object, **kwargs: object) -> None:
        if Path(path).name.startswith(RETIRED_PREFIX):
            raise PermissionError("in use")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", stubborn_rmtree)
    fake_download(make_dataset({"fresh.csv": "y\n2\n"}))

    result = invoke_ingest()

    assert result.exit_code == 0, result.output
    assert "warning:" in result.output
    out = ingest_dir(project_dir)
    assert sorted(p.name for p in out.iterdir()) == ["_snapshot.json", "fresh.parquet"]
    leftovers = [p for p in out.parent.iterdir() if p.name.startswith(RETIRED_PREFIX)]
    assert len(leftovers) == 1
    assert str(leftovers[0]) in result.output
