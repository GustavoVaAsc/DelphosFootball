"""Command-line entry point for the DelphosFootball offline pipeline.

Input: a stage name on the command line, such as `delphos-pipeline ingest`.
Output: whatever that stage writes. This module writes nothing itself.
Responsibility: registers each stage's entry function as a subcommand. Stage logic lives in
the stage modules.

Stage convention: each stage module has one public entry function, and its docstring is the
command's help. A stage reports an expected failure by printing `<stage> failed: <reason>` to
stderr and raising `typer.Exit(1)`. The `all` command, added once a second stage exists, will
call the entry functions in pipeline order and stop at the first failure.
"""

import typer

from delphos_ml.pipeline.ingest import ingest

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
    # With a single registered command Typer would otherwise run that command directly;
    # the callback keeps the `delphos-pipeline <stage>` subcommand form.


app.command(name="ingest")(ingest)
