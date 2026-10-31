"""Command-line entry point for the DelphosFootball offline pipeline.

Input: a stage name on the command line, such as `delphos-pipeline ingest`, or `all`.
Output: whatever that stage writes. This module writes nothing itself.
Responsibility: registers each stage's entry function as a subcommand and wires `all`. Stage logic
lives in the stage modules.

Stage convention: each stage module has one public entry function, and its docstring is the
command's help. A stage reports an expected failure by printing `<stage> failed: <reason>` to
stderr and raising `typer.Exit(1)`. The `all` command calls the entry functions in pipeline order
and stops at the first failure.
"""

import typer

from delphos_ml.pipeline.clean import clean
from delphos_ml.pipeline.ingest import ingest
from delphos_ml.pipeline.transform import transform

# Plain help output: Typer reflows the docstring paragraphs and leaves `<table>` and
# brackets in help text alone (rich and markdown modes would not).
app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def main() -> None:
    """DelphosFootball offline pipeline. Each command runs one stage and writes its output
    under data/<stage>/.
    """


def run_all() -> None:
    """Run every implemented pipeline stage in order: ingest, clean, transform.

    Calls each stage entry function sequentially using the current DELPHOS_* settings and stops at
    the first stage that exits non-zero.
    """
    ingest()
    clean()
    transform()


app.command(name="ingest")(ingest)
app.command(name="clean")(clean)
app.command(name="transform")(transform)
app.command(name="all")(run_all)
