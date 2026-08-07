import os
from pathlib import Path

import psycopg

MIGRATION = (
    Path(__file__).parents[1]
    / "db"
    / "migrations"
    / "002_add_smart_money_scoring.sql"
)


def _execute_script(connection, script: str) -> None:
    # Production runs through psql, where \gexec executes generated recovery SQL.
    # The clean-schema test has no invalid indexes, so executing its SELECT is sufficient.
    script = script.replace("\\gexec", ";")
    for statement in script.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def test_smart_money_migration_upgrades_legacy_schema_and_is_idempotent():
    test_database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/polymkt_test",
    )
    database_url = test_database_url.replace("postgresql+psycopg://", "postgresql://")
    schema = "test_smart_money_migration"

    with psycopg.connect(database_url, autocommit=True) as connection:
        try:
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            connection.execute(f'CREATE SCHEMA "{schema}"')
            connection.execute(f'SET search_path TO "{schema}"')
            connection.execute(
                """
                CREATE TABLE trader_rankings (
                    category VARCHAR(32) NOT NULL,
                    time_period VARCHAR(16) NOT NULL,
                    captured_at TIMESTAMPTZ NOT NULL,
                    rank INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE positions (
                    captured_at TIMESTAMPTZ NOT NULL,
                    wallet_address VARCHAR(42) NOT NULL,
                    condition_id VARCHAR(80) NOT NULL,
                    outcome VARCHAR(16) NOT NULL
                )
                """
            )

            migration = MIGRATION.read_text()
            _execute_script(connection, migration)
            _execute_script(connection, migration)

            batch_columns = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = 'position_ingestion_batches'
                    """,
                    (schema,),
                )
            }
            score_columns = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = 'smart_money_scores'
                    """,
                    (schema,),
                )
            }
            indexes = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = %s
                    """,
                    (schema,),
                )
            }
            invalid_index_count = connection.execute(
                """
                SELECT count(*)
                FROM pg_index index_state
                JOIN pg_class index_class ON index_class.oid = index_state.indexrelid
                JOIN pg_namespace namespace ON namespace.oid = index_class.relnamespace
                WHERE namespace.nspname = %s
                  AND NOT index_state.indisvalid
                """,
                (schema,),
            ).fetchone()[0]
            score_foreign_keys = connection.execute(
                """
                SELECT count(*)
                FROM information_schema.table_constraints
                WHERE constraint_schema = %s
                  AND table_name = 'smart_money_scores'
                  AND constraint_type = 'FOREIGN KEY'
                """,
                (schema,),
            ).fetchone()[0]

            assert {"leaderboard_captured_at", "category", "time_period", "top_n"} <= batch_columns
            assert "position_ingestion_batch_id" in score_columns
            assert {
                "ix_trader_rankings_cohort_snapshot",
                "ix_positions_snapshot_wallet_market",
                "ix_position_batches_cohort_snapshot",
                "ix_smart_money_scores_snapshot_market",
                "ix_smart_money_scores_position_batch",
                "uq_smart_money_score_position_batch_market",
            } <= indexes
            assert invalid_index_count == 0
            assert score_foreign_keys == 1
        finally:
            connection.execute("SET search_path TO public")
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
