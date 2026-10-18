from typer.testing import CliRunner

from delphos_ml.config import DEFAULT_KAGGLE_DATASET_VERSION
from delphos_ml.pipeline.cli import app

runner = CliRunner()


def test_top_level_help_lists_ingest_as_a_subcommand() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Commands" in result.output
    ingest_lines = [line for line in result.output.splitlines() if "ingest" in line]
    assert ingest_lines, result.output
    assert "Parquet" in ingest_lines[0]


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
