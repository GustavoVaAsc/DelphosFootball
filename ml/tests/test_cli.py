import pytest
import typer
from typer.testing import CliRunner

from delphos_ml.config import DEFAULT_KAGGLE_DATASET_VERSION
from delphos_ml.pipeline import cli as cli_module
from delphos_ml.pipeline.cli import app

runner = CliRunner()


def test_top_level_help_lists_ingest_clean_and_all_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Commands" in result.output
    normalized = " ".join(result.output.split())
    assert "Stage commands write their outputs under data/<stage>/" in normalized
    assert "all runs every implemented stage in order." in normalized
    ingest_lines = [line for line in result.output.splitlines() if "ingest" in line]
    clean_lines = [line for line in result.output.splitlines() if "clean" in line]
    all_lines = [line for line in result.output.splitlines() if line.strip().startswith("all")]
    assert ingest_lines, result.output
    assert "Parquet" in ingest_lines[0]
    assert clean_lines, result.output
    assert all_lines, result.output


def test_ingest_help_states_input_and_output() -> None:
    result = runner.invoke(app, ["ingest", "--help"])

    assert result.exit_code == 0
    assert "data/ingest" in result.output
    assert "_snapshot.json" in result.output


def test_ingest_help_shows_defaults_overrides_and_output_location() -> None:
    result = runner.invoke(app, ["ingest", "--help"])

    assert "davidcariboo/player-scores" in result.output
    assert str(DEFAULT_KAGGLE_DATASET_VERSION) in result.output
    for name in ("DELPHOS_KAGGLE_DATASET", "DELPHOS_KAGGLE_DATASET_VERSION", "DELPHOS_DATA_DIR"):
        assert name in result.output


def test_clean_help_states_input_output_and_override() -> None:
    result = runner.invoke(app, ["clean", "--help"])

    assert result.exit_code == 0
    assert "data/ingest" in result.output
    assert "data/clean" in result.output
    assert "_clean.json" in result.output
    assert "DELPHOS_DATA_DIR" in result.output


def test_transform_help_states_input_output_and_parameters() -> None:
    result = runner.invoke(app, ["transform", "--help"])

    assert result.exit_code == 0
    assert "data/clean" in result.output
    assert "data/transform" in result.output
    assert "_transform.json" in result.output
    assert "DELPHOS_DATA_DIR" in result.output


def test_all_runs_every_stage_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli_module, "ingest", lambda: calls.append("ingest"))
    monkeypatch.setattr(cli_module, "clean", lambda: calls.append("clean"))
    monkeypatch.setattr(cli_module, "transform", lambda: calls.append("transform"))

    result = runner.invoke(app, ["all"])

    assert result.exit_code == 0, result.output
    assert calls == ["ingest", "clean", "transform"]


def test_all_stops_at_first_stage_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fail_ingest() -> None:
        calls.append("ingest")
        raise typer.Exit(code=1)

    monkeypatch.setattr(cli_module, "ingest", fail_ingest)
    monkeypatch.setattr(cli_module, "clean", lambda: calls.append("clean"))

    result = runner.invoke(app, ["all"])

    assert result.exit_code == 1
    assert calls == ["ingest"]


def test_all_propagates_second_stage_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fail_clean() -> None:
        calls.append("clean")
        raise typer.Exit(code=1)

    monkeypatch.setattr(cli_module, "ingest", lambda: calls.append("ingest"))
    monkeypatch.setattr(cli_module, "clean", fail_clean)

    result = runner.invoke(app, ["all"])

    assert result.exit_code == 1
    assert calls == ["ingest", "clean"]


def test_all_propagates_third_stage_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fail_transform() -> None:
        calls.append("transform")
        raise typer.Exit(code=1)

    monkeypatch.setattr(cli_module, "ingest", lambda: calls.append("ingest"))
    monkeypatch.setattr(cli_module, "clean", lambda: calls.append("clean"))
    monkeypatch.setattr(cli_module, "transform", fail_transform)

    result = runner.invoke(app, ["all"])

    assert result.exit_code == 1
    assert calls == ["ingest", "clean", "transform"]
