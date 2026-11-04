"""Create analytics tables, indexes, and constraints matching Parquet outputs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04 00:01:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("analytics",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. model_runs
    op.execute(
        """
        CREATE TABLE analytics.model_runs (
            model_run_id VARCHAR(64) PRIMARY KEY,
            dataset_version INTEGER NOT NULL,
            dataset_snapshot_sha256 VARCHAR(64) NOT NULL,
            transform_manifest_sha256 VARCHAR(64) NOT NULL,
            train_manifest_sha256 VARCHAR(64) NOT NULL,
            evaluate_manifest_sha256 VARCHAR(64) NOT NULL,
            artifact_files_sha256 JSONB NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'staged' CHECK (status IN ('staged', 'active', 'archived')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMPTZ NULL
        );
        CREATE UNIQUE INDEX uq_model_runs_active ON analytics.model_runs ((1)) WHERE status = 'active';
        """
    )

    # 2. dim_players (from clean/players.parquet)
    op.execute(
        """
        CREATE TABLE analytics.dim_players (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            first_name VARCHAR(128) NULL,
            last_name VARCHAR(128) NOT NULL,
            name VARCHAR(256) NOT NULL,
            player_code VARCHAR(128) NOT NULL,
            country_of_birth VARCHAR(128) NULL,
            city_of_birth VARCHAR(128) NULL,
            country_of_citizenship VARCHAR(128) NULL,
            date_of_birth DATE NOT NULL,
            sub_position VARCHAR(64) NULL,
            position VARCHAR(64) NOT NULL,
            foot VARCHAR(32) NULL,
            height_in_cm INTEGER NULL,
            image_url TEXT NULL,
            url TEXT NOT NULL,
            PRIMARY KEY (model_run_id, player_id)
        );
        CREATE INDEX idx_dim_players_name ON analytics.dim_players (model_run_id, name);
        """
    )

    # 3. dim_clubs (from clean/clubs.parquet)
    op.execute(
        """
        CREATE TABLE analytics.dim_clubs (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            club_id INTEGER NOT NULL,
            club_code VARCHAR(128) NOT NULL,
            name VARCHAR(256) NOT NULL,
            domestic_competition_id VARCHAR(32) NOT NULL,
            stadium_name VARCHAR(256) NULL,
            stadium_seats INTEGER NULL,
            url TEXT NOT NULL,
            PRIMARY KEY (model_run_id, club_id)
        );
        """
    )

    # 4. fct_player_seasons (from transform/player_seasons.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_player_seasons (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            as_of_date DATE NOT NULL,
            split VARCHAR(32) NOT NULL,
            club_id INTEGER NOT NULL,
            league_id VARCHAR(32) NOT NULL,
            minutes DOUBLE PRECISION NOT NULL,
            apps DOUBLE PRECISION NOT NULL,
            starts DOUBLE PRECISION NOT NULL,
            captain DOUBLE PRECISION NOT NULL,
            squad_inclusions DOUBLE PRECISION NOT NULL,
            goals DOUBLE PRECISION NOT NULL,
            assists DOUBLE PRECISION NOT NULL,
            yellow_cards DOUBLE PRECISION NOT NULL,
            red_cards DOUBLE PRECISION NOT NULL,
            win_flag DOUBLE PRECISION NOT NULL,
            clean_sheet_flag DOUBLE PRECISION NOT NULL,
            goals_conceded DOUBLE PRECISION NOT NULL,
            uefa_minutes DOUBLE PRECISION NOT NULL,
            starter_ratio DOUBLE PRECISION NOT NULL,
            captain_ratio DOUBLE PRECISION NOT NULL,
            win_rate DOUBLE PRECISION NOT NULL,
            clean_sheet_rate DOUBLE PRECISION NOT NULL,
            goals_conceded_per_match DOUBLE PRECISION NOT NULL,
            uefa_share DOUBLE PRECISION NOT NULL,
            cup_share DOUBLE PRECISION NOT NULL,
            league_position DOUBLE PRECISION NULL,
            league_position_missing BOOLEAN NOT NULL,
            age DOUBLE PRECISION NOT NULL,
            age_sq DOUBLE PRECISION NOT NULL,
            height_in_cm DOUBLE PRECISION NULL,
            foot VARCHAR(32) NULL,
            position VARCHAR(64) NOT NULL,
            sub_position VARCHAR(64) NOT NULL,
            country_group VARCHAR(64) NOT NULL,
            log10_market_value DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (model_run_id, player_id, season)
        );
        CREATE INDEX idx_fct_player_seasons_lookup ON analytics.fct_player_seasons (
            model_run_id, season, league_id
        );
        """
    )

    # 5. fct_player_predictions (from train/player_predictions.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_player_predictions (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            as_of_date DATE NOT NULL,
            split VARCHAR(32) NOT NULL,
            residual_source VARCHAR(64) NOT NULL,
            log10_market_value DOUBLE PRECISION NOT NULL,
            market_value_eur DOUBLE PRECISION NOT NULL,
            linear_log10_pred DOUBLE PRECISION NOT NULL,
            poly_log10_pred DOUBLE PRECISION NOT NULL,
            predicted_log10_value DOUBLE PRECISION NOT NULL,
            fair_value_eur DOUBLE PRECISION NOT NULL,
            residual_log10 DOUBLE PRECISION NOT NULL,
            valuation_status VARCHAR(32) NOT NULL,
            is_undervalued BOOLEAN NOT NULL,
            dt_undervalued_prob DOUBLE PRECISION NOT NULL,
            dt_undervalued_pred BOOLEAN NOT NULL,
            rf_undervalued_prob DOUBLE PRECISION NOT NULL,
            rf_undervalued_pred BOOLEAN NOT NULL,
            PRIMARY KEY (model_run_id, player_id, season)
        );
        CREATE INDEX idx_fct_player_pred_status ON analytics.fct_player_predictions (
            model_run_id, season, valuation_status
        );
        """
    )

    # 6. fct_clusters (from train/clusters.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_clusters (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            split VARCHAR(32) NOT NULL,
            cluster_id INTEGER NOT NULL,
            centroid_distance DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (model_run_id, player_id, season)
        );
        CREATE INDEX idx_fct_clusters_cluster ON analytics.fct_clusters (
            model_run_id, season, cluster_id
        );
        """
    )

    # 7. fct_transfer_predictions (from train/transfer_predictions.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_transfer_predictions (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            split VARCHAR(32) NOT NULL,
            transfer_date DATE NOT NULL,
            club_id INTEGER NOT NULL,
            league_id VARCHAR(32) NOT NULL,
            buyer_league_id VARCHAR(32) NULL,
            transfer_fee DOUBLE PRECISION NOT NULL,
            pre_transfer_market_value DOUBLE PRECISION NOT NULL,
            log10_transfer_fee DOUBLE PRECISION NOT NULL,
            linear_log10_pred DOUBLE PRECISION NOT NULL,
            poly_log10_pred DOUBLE PRECISION NOT NULL,
            fair_value_eur DOUBLE PRECISION NOT NULL,
            fee_minus_fair_log10 DOUBLE PRECISION NOT NULL,
            fee_minus_mv_log10 DOUBLE PRECISION NOT NULL,
            cluster_id INTEGER NOT NULL,
            rf_undervalued_prob DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (model_run_id, player_id, transfer_date)
        );
        """
    )

    # 8. fct_replacement_targets (from evaluate/replacement_targets.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_replacement_targets (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            position VARCHAR(64) NOT NULL,
            cluster_id INTEGER NOT NULL,
            market_value_eur DOUBLE PRECISION NOT NULL,
            elite_mv_threshold_eur DOUBLE PRECISION NOT NULL,
            is_elite_asset BOOLEAN NOT NULL,
            distance_ceiling DOUBLE PRECISION NOT NULL,
            qualifying_count INTEGER NOT NULL,
            shortfall_reason VARCHAR(64) NULL,
            PRIMARY KEY (model_run_id, player_id)
        );
        """
    )

    # 9. fct_replacements (from evaluate/replacements.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_replacements (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            target_player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            candidate_player_id INTEGER NOT NULL,
            cluster_id INTEGER NOT NULL,
            position VARCHAR(64) NOT NULL,
            euclidean_distance DOUBLE PRECISION NOT NULL,
            similarity_score DOUBLE PRECISION NOT NULL,
            target_market_value_eur DOUBLE PRECISION NOT NULL,
            candidate_market_value_eur DOUBLE PRECISION NOT NULL,
            cost_savings_eur DOUBLE PRECISION NOT NULL,
            cost_ratio DOUBLE PRECISION NOT NULL,
            candidate_fair_value_eur DOUBLE PRECISION NOT NULL,
            candidate_residual_log10 DOUBLE PRECISION NOT NULL,
            candidate_valuation_status VARCHAR(32) NOT NULL,
            target_is_elite_asset BOOLEAN NOT NULL,
            PRIMARY KEY (model_run_id, target_player_id, rank),
            FOREIGN KEY (model_run_id, target_player_id)
                REFERENCES analytics.fct_replacement_targets(model_run_id, player_id)
                ON DELETE CASCADE
        );
        """
    )

    # 10. fct_inefficiency_analysis (from evaluate/inefficiency_analysis.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_inefficiency_analysis (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            scope VARCHAR(32) NOT NULL,
            test_id VARCHAR(64) NOT NULL,
            hypothesis TEXT NOT NULL,
            statistic_name VARCHAR(32) NOT NULL,
            statistic DOUBLE PRECISION NOT NULL,
            p_value DOUBLE PRECISION NOT NULL,
            p_value_holm DOUBLE PRECISION NOT NULL,
            alpha DOUBLE PRECISION NOT NULL,
            reject_null BOOLEAN NOT NULL,
            n_primary INTEGER NOT NULL,
            n_secondary INTEGER NULL,
            effect_size_name VARCHAR(32) NOT NULL,
            effect_size DOUBLE PRECISION NOT NULL,
            primary_median_log10 DOUBLE PRECISION NOT NULL,
            secondary_median_log10 DOUBLE PRECISION NULL,
            median_eur_ratio DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (model_run_id, scope, test_id)
        );
        """
    )

    # 11. fct_model_metrics (from evaluate/model_metrics.parquet)
    op.execute(
        """
        CREATE TABLE analytics.fct_model_metrics (
            model_run_id VARCHAR(64) NOT NULL REFERENCES analytics.model_runs(model_run_id) ON DELETE CASCADE,
            scope VARCHAR(32) NOT NULL,
            model VARCHAR(64) NOT NULL,
            metric VARCHAR(64) NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            se DOUBLE PRECISION NULL,
            n_rows INTEGER NOT NULL,
            PRIMARY KEY (model_run_id, scope, model, metric)
        );
        """
    )

    # Grant select to delphos_app_user and full access to delphos_ml_publisher
    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO delphos_ml_publisher;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO delphos_app_user;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analytics.fct_model_metrics CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_inefficiency_analysis CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_replacements CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_replacement_targets CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_transfer_predictions CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_clusters CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_player_predictions CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.fct_player_seasons CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.dim_clubs CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.dim_players CASCADE;")
    op.execute("DROP TABLE IF EXISTS analytics.model_runs CASCADE;")
