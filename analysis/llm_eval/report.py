"""Render the experiment JSONL rows into tables and figures (offline; no server).

Input: `analysis/output/llm/*.jsonl` by default (or `--input`), written by E1–E9 as
`kind=call|score|summary` rows; `--out` selects the output directory (default: the same
`analysis/output/llm/`).
Output: per-experiment `<exp>_calls.csv`, `<exp>_scores.csv`, `<exp>_summaries.csv`, a
`tables.md` of markdown tables for docs/REPORT_NOTES.md, and figures —
`fig_prompt_budget.png` (E3 prompt tokens vs the 8000 budget),
`fig_argument_exact_match.png` (the headline chat metric per experiment and arm),
`fig_cross_seed_similarity.png` (E7, higher = more repeatable) and
`fig_mean_latency_ms.png` (per experiment and arm).
Responsibility: pure offline rendering of whatever has been recorded — no inference
server, no database, no backend imports — so it runs after every partial experiment and
with zero JSONLs it exits with one actionable line instead of a traceback.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from harness import fail, output_dir

PROMPT_BUDGET = 8000


def load_rows(input_dir: Path) -> list[dict[str, Any]]:
    """Every JSONL row under `input_dir`; a truncated final line is skipped, not fatal."""
    rows: list[dict[str, Any]] = []
    paths = sorted(input_dir.glob("*.jsonl"))
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                print(f"warning: skipping malformed line {number} of {path.name}")
    return rows


def _frame(records: list[dict[str, Any]]) -> pd.DataFrame | None:
    return pd.json_normalize(records) if records else None


def _write_csv(frame: pd.DataFrame | None, path: Path, files: list[str]) -> None:
    if frame is not None:
        frame.to_csv(path, index=False)
        files.append(path.name)


def _markdown_section(experiment: str, summaries: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {experiment}", ""]
    for index, summary in enumerate(summaries, start=1):
        title = ", ".join(
            f"{key}={summary[key]}" for key in ("arm", "path", "seed") if key in summary
        )
        lines.append(f"### {experiment} summary {index}" + (f" ({title})" if title else ""))
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        for key, value in summary.items():
            if key in ("experiment", "kind"):
                continue
            rendered = (
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else str(value)
            )
            lines.append(f"| {key} | {rendered} |")
        lines.append("")
    return lines


def _fig_prompt_budget(e3_scores: list[dict], out: Path, files: list[str]) -> None:
    rows = [s for s in e3_scores if s.get("prompt_n") is not None]
    if not rows:
        return
    labels = [str(s.get("case_id", i)) for i, s in enumerate(rows)]
    values = [int(s["prompt_n"]) for s in rows]
    fig, ax = plt.subplots(figsize=(9, 4.2), constrained_layout=True)
    bars = ax.bar(labels, values, color="#1b6ca8", alpha=0.85)
    ax.axhline(PROMPT_BUDGET, color="#d1495b", ls="--", lw=1.5, label=f"budget ({PROMPT_BUDGET})")
    for bar, value in zip(bars, values, strict=True):
        if value > PROMPT_BUDGET:
            bar.set_color("#d1495b")
    ax.set_ylabel("prompt_n tokens")
    ax.set_title("E3: fact-card prompt tokens vs budget")
    ax.legend(fontsize=8.5)
    fig.savefig(out / "fig_prompt_budget.png", dpi=180)
    plt.close(fig)
    files.append("fig_prompt_budget.png")


def _summary_bar(
    rows: list[tuple[str, float]],
    title: str,
    ylabel: str,
    filename: str,
    out: Path,
    files: list[str],
    hline: float | None = None,
) -> None:
    if not rows:
        return
    labels = [label for label, _ in rows]
    values = [value for _, value in rows]
    fig, ax = plt.subplots(figsize=(max(6.0, 0.9 * len(rows)), 4.2), constrained_layout=True)
    ax.bar(labels, values, color="#2a9d8f", alpha=0.85)
    if hline is not None:
        ax.axhline(hline, color="#d1495b", ls="--", lw=1.5, label=f"threshold ({hline})")
        ax.legend(fontsize=8.5)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    fig.savefig(out / filename, dpi=180)
    plt.close(fig)
    files.append(filename)


def render(input_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Render every JSONL into CSVs, `tables.md` and figures; return the summary dict."""
    rows = load_rows(input_dir)
    if not rows:
        fail(
            f"no recorded experiment rows under {input_dir}; run an experiment first "
            "(each script preflights the inference server before writing anything)",
            script="report",
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    experiments = sorted({str(r.get("experiment", "?")) for r in rows})
    markdown: list[str] = ["# LLM experiment tables", ""]
    summary: dict[str, Any] = {"experiments": {}, "files": files}

    for experiment in experiments:
        subset = [r for r in rows if str(r.get("experiment")) == experiment]
        calls = [r for r in subset if r.get("kind") == "call"]
        scores = [r for r in subset if r.get("kind") == "score"]
        summaries = [r for r in subset if r.get("kind") == "summary"]
        _write_csv(_frame(calls), out_dir / f"{experiment}_calls.csv", files)
        _write_csv(_frame(scores), out_dir / f"{experiment}_scores.csv", files)
        _write_csv(_frame(summaries), out_dir / f"{experiment}_summaries.csv", files)
        markdown.extend(_markdown_section(experiment, summaries))
        summary["experiments"][experiment] = {
            "calls": len(calls),
            "scores": len(scores),
            "summaries": len(summaries),
            "summary_rows": summaries,
        }

    (out_dir / "tables.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    files.append("tables.md")

    _fig_prompt_budget(
        [r for r in rows if r.get("kind") == "score" and r.get("experiment") == "e3"],
        out_dir,
        files,
    )
    exact_rows = [
        (f"{r.get('experiment')}/{r.get('arm', '?')}", float(r["argument_exact_match"]))
        for r in rows
        if r.get("kind") == "summary" and r.get("argument_exact_match") is not None
    ]
    _summary_bar(
        exact_rows,
        "Argument exact-match by experiment and arm",
        "exact-match rate",
        "fig_argument_exact_match.png",
        out_dir,
        files,
        hline=0.80,
    )
    similarity_rows = [
        (str(r.get("arm", "?")), float(r["cross_seed_similarity"]))
        for r in rows
        if r.get("kind") == "summary" and r.get("cross_seed_similarity") is not None
    ]
    _summary_bar(
        similarity_rows,
        "E7 cross-seed similarity (higher = more repeatable)",
        "mean Jaccard of fact references",
        "fig_cross_seed_similarity.png",
        out_dir,
        files,
    )
    latency = [
        (
            str(r.get("experiment", "?")) + "/" + str(r.get("arm", "?")),
            float(r.get("latency_ms", 0.0)),
        )
        for r in rows
        if r.get("kind") == "call" and r.get("latency_ms") is not None
    ]
    latency_by_label: dict[str, list[float]] = {}
    for label, value in latency:
        latency_by_label.setdefault(label, []).append(value)
    _summary_bar(
        [(label, sum(values) / len(values)) for label, values in sorted(latency_by_label.items())],
        "Mean latency per call by experiment and arm",
        "latency (ms)",
        "fig_mean_latency_ms.png",
        out_dir,
        files,
    )
    return summary


def main() -> None:
    """Render the recorded experiment JSONLs into CSV tables, markdown and PNG figures.

    `--help` prints this text without contacting a server; the render itself needs only
    the recorded files.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="directory holding the experiment JSONLs (default: analysis/output/llm)",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="output directory (default: same as --input)"
    )
    args = parser.parse_args()
    input_dir = args.input if args.input is not None else output_dir()
    out_dir = args.out if args.out is not None else input_dir
    summary = render(input_dir, out_dir)
    for experiment, stats in summary["experiments"].items():
        print(
            f"{experiment}: {stats['calls']} calls, {stats['scores']} scores, "
            f"{stats['summaries']} summaries"
        )
    print(f"rendered {len(summary['files'])} files into {out_dir}")


if __name__ == "__main__":
    main()
