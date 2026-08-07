# Polymarket Betting Recommender

A recommendation engine for Polymarket that ranks betting opportunities by combining:

- Smart Money Signal (top profitable traders)
- Proprietary Edge Signal (market analytics)

## Project Status

🚧 Phase 1 (MVP) — Architecture and data pipeline under development.

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
- [ ] Smart Money scoring
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
python -m polymkt.run
```
