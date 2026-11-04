"""Database bulk loading and verification for the publish stage.

Input: psycopg connection, stage Parquet outputs, and publication metadata.
Output: inserted rows in the `analytics` PostgreSQL schema and row counts.
Responsibility: streams Parquet data into analytics tables and updates active model_runs pointer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

TABLE_SPECS: tuple[tuple[str, str], ...] = (
    ("dim_players", "clean/players.parquet"),
    ("dim_clubs", "clean/clubs.parquet"),
    ("fct_player_seasons", "transform/player_seasons.parquet"),
    ("fct_player_predictions", "train/player_predictions.parquet"),
    ("fct_clusters", "train/clusters.parquet"),
    ("fct_transfer_predictions", "train/transfer_predictions.parquet"),
    ("fct_replacement_targets", "evaluate/replacement_targets.parquet"),
    ("fct_replacements", "evaluate/replacements.parquet"),
    ("fct_inefficiency_analysis", "evaluate/inefficiency_analysis.parquet"),
    ("fct_model_metrics", "evaluate/model_metrics.parquet"),
)


def bulk_load_analytics(
    conn: Any,
    model_run_id: str,
    data_dir: Path,
    manifests: dict[str, Any],
    artifact_hashes: dict[str, str],
) -> dict[str, int]:
    """Bulk-load all analytics tables and activate the run inside a transaction."""
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        # 1. Insert model_runs record as staged
        cur.execute(
            """
            INSERT INTO analytics.model_runs (
                model_run_id, dataset_version, dataset_snapshot_sha256,
                transform_manifest_sha256, train_manifest_sha256,
                evaluate_manifest_sha256, artifact_files_sha256, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'staged');
            """,
            (
                model_run_id,
                manifests["dataset_version"],
                manifests["dataset_snapshot_sha256"],
                manifests["transform_manifest_sha256"],
                manifests["train_manifest_sha256"],
                manifests["evaluate_manifest_sha256"],
                json.dumps(artifact_hashes),
            ),
        )

        # 2. Bulk-load each table in streaming batches to bound memory consumption
        for table_name, rel_path in TABLE_SPECS:
            parquet_path = data_dir / rel_path
            parquet_file = pq.ParquetFile(parquet_path)
            num_rows = parquet_file.metadata.num_rows
            counts[table_name] = num_rows

            table_cols = parquet_file.schema.names
            col_names = ["model_run_id", *table_cols]
            cols_str = ", ".join(col_names)

            with cur.copy(f"COPY analytics.{table_name} ({cols_str}) FROM STDIN") as copy:
                for batch in parquet_file.iter_batches(batch_size=5000):
                    batch_dict = batch.to_pydict()
                    for row in zip(*(batch_dict[c] for c in table_cols), strict=True):
                        copy.write_row((model_run_id, *row))

        # 3. Demote active and promote this run
        cur.execute("UPDATE analytics.model_runs SET status = 'archived' WHERE status = 'active';")
        cur.execute(
            """
            UPDATE analytics.model_runs
            SET status = 'active', activated_at = CURRENT_TIMESTAMP
            WHERE model_run_id = %s;
            """,
            (model_run_id,),
        )

    return counts


def verify_published_counts(conn: Any, model_run_id: str, expected_counts: dict[str, int]) -> None:
    """Verify that every analytics table holds the expected row count for model_run_id."""
    with conn.cursor() as cur:
        for table_name, expected in expected_counts.items():
            cur.execute(
                f"SELECT COUNT(*) FROM analytics.{table_name} WHERE model_run_id = %s;",  # noqa: S608
                (model_run_id,),
            )
            (actual,) = cur.fetchone()
            if actual != expected:
                raise ValueError(
                    f"count mismatch on analytics.{table_name}: expected {expected}, got {actual}"
                )
