# Polymarket Betting Recommender

A recommendation engine for Polymarket that ranks betting opportunities by combining:

- Smart Money Signal (top profitable traders)
- Proprietary Edge Signal (market analytics)

## Project Status

🚧 Phase 2 (MVP) — Ingestion is complete and Smart Money scoring is implemented.

Each scoring cycle aggregates the latest positions held by the current top-N
trader cohort, normalizes capital to a zero-anchored 0-100 score, and stores an
append-only snapshot for both sides of every active binary market.

## Planned Stack

- Python
- FastAPI
- PostgreSQL
- TimescaleDB
- Next.js
- Docker

## Roadmap

- [x] Market ingestion
- [x] Leaderboard ingestion
- [x] Position ingestion
- [x] Price ingestion
- [x] Smart Money scoring
- [ ] Edge scoring
- [ ] Recommendation engine
- [ ] REST API
- [ ] Frontend dashboard
- [ ] Backtesting

See `docs/design.md` for the full design and `WORKFLOW.md` for the git workflow.

## Running locally

```bash
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -v
python -m polymkt.init_db  # creates the schema on the dev database
python -m polymkt.run
```

For an existing development database created before Smart Money scoring, apply
the versioned schema migration once:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d polymkt < db/migrations/002_add_smart_money_scoring.sql
```

Use fail-fast mode when applying it outside Docker as well:

```bash
psql -v ON_ERROR_STOP=1 "postgresql://postgres:postgres@localhost:5432/polymkt" \
  -f db/migrations/002_add_smart_money_scoring.sql
```

The migration is additive and forward-only: rolling the application back leaves
the new tables, columns and indexes in place without deleting historical data.
Concurrent index creation avoids blocking the ingestion tables. If PostgreSQL is
interrupted while building an index, inspect `pg_index.indisvalid`, drop only the
reported invalid index with `DROP INDEX CONCURRENTLY`, and rerun the migration.

At process startup the scheduler immediately bootstraps markets, leaderboard,
positions/scores and prices in dependency order. Missing or partial source data
aborts that score cycle; it is never persisted as a healthy-looking zero signal.
