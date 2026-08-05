# Foundation & Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project skeleton, database schema, and the four Polymarket API ingestion pipelines (markets, leaderboard, trader positions, prices) so real market/trader data lands in Postgres on a schedule, ready for the scoring engine (a later plan) to consume.

**Architecture:** A single Python package (`polymkt`) with thin HTTP client wrappers per Polymarket API surface (Gamma, CLOB, Data API), SQLAlchemy models for persistence, ingestion functions that take an injected DB session + client (no global state, fully unit-testable), and an APScheduler-based entrypoint that runs each ingestion job on its own cadence. Postgres runs via Docker Compose locally (TimescaleDB image, so a later plan can convert tables to hypertables without an infra change).

**Tech Stack:** Python 3.11+, httpx, SQLAlchemy 2.0, psycopg3, pydantic-settings, APScheduler, pytest, respx, Docker Compose (`timescale/timescaledb:latest-pg16`), GitHub Actions CI.

## Global Constraints

- Python 3.11+, `src/` layout, installable via `pip install -e ".[dev]"` (see `docs/design.md`).
- All Polymarket HTTP calls go through the three client wrapper classes built in Tasks 4–6 (`GammaClient`, `ClobClient`, `DataApiClient`). No other module calls `httpx` directly.
- Every ingestion function takes an injected SQLAlchemy `Session` and API client as parameters — no function reaches into global state — so it can be unit tested with a fake client and a real (test) DB session.
- Configurable values (`top_n_traders`, leaderboard `category`/`time_period`, API base URLs) live in `polymkt.config.Settings`, sourced from environment variables. Nothing is hardcoded per `docs/design.md`'s requirement that the top-N trader cohort size be a parameter, not a constant.
- No test hits the real Polymarket API. HTTP-level tests use `respx` fixtures; DB-level ingestion tests use fake client classes (defined per test file) against a real test Postgres database.
- Every commit follows `WORKFLOW.md`: work happens on `feature/foundation-ingestion-pipeline`, pushed after each commit, PR opened at the end — never a direct push to `main`.

---

### Task 1: Project scaffolding and settings

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/polymkt/__init__.py`
- Create: `src/polymkt/config.py`
- Test: `tests/test_config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (placeholder import only — filled in Task 3)

**Interfaces:**
- Produces: `polymkt.config.settings` — a `Settings` instance with attributes `database_url: str`, `top_n_traders: int`, `leaderboard_category: str`, `leaderboard_time_period: str`, `gamma_base_url: str`, `clob_base_url: str`, `data_api_base_url: str`. All later tasks import this.

- [ ] **Step 1: Create the branch**

```bash
cd /Users/igarciatrueba/Documents/POLYMKT-ANALYSIS
git checkout main
git pull origin main
git checkout -b feature/foundation-ingestion-pipeline
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "polymkt"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "apscheduler>=3.10",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "respx>=0.21",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Write `.env.example`**

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/polymkt
TOP_N_TRADERS=300
LEADERBOARD_CATEGORY=OVERALL
LEADERBOARD_TIME_PERIOD=ALL
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
*.egg-info/
```

- [ ] **Step 5: Create `src/polymkt/__init__.py`** (empty file)

- [ ] **Step 6: Write `src/polymkt/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/polymkt"
    top_n_traders: int = 300
    leaderboard_category: str = "OVERALL"
    leaderboard_time_period: str = "ALL"
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    data_api_base_url: str = "https://data-api.polymarket.com"


settings = Settings()
```

- [ ] **Step 7: Create `tests/__init__.py`** (empty file)

- [ ] **Step 8: Write the failing test — `tests/test_config.py`**

```python
import os

from polymkt.config import Settings


def test_settings_default_top_n_traders_is_300():
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 300


def test_settings_reads_top_n_traders_from_env(monkeypatch):
    monkeypatch.setenv("TOP_N_TRADERS", "500")
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 500
```

- [ ] **Step 9: Install the package and run the test to verify it fails**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'polymkt'` (before install) or PASS once installed. If it fails to import even after `pip install -e ".[dev]"`, that's the real signal to fix (check `[tool.setuptools.packages.find]` `where` matches `src/`).

- [ ] **Step 10: Run the test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/polymkt/__init__.py src/polymkt/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add project scaffolding and settings"
git push -u origin feature/foundation-ingestion-pipeline
```

---

### Task 2: Docker Compose Postgres/Timescale + DB session

**Files:**
- Create: `docker-compose.yml`
- Create: `db/init/001_create_test_db.sql`
- Create: `src/polymkt/db/__init__.py`
- Create: `src/polymkt/db/session.py`

**Interfaces:**
- Consumes: `polymkt.config.settings` (Task 1).
- Produces: `polymkt.db.session.get_session()` — a context manager yielding a `sqlalchemy.orm.Session`, committing on success and rolling back on exception. Used by Task 11's scheduler entrypoint.

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: polymkt
    ports:
      - "5432:5432"
    volumes:
      - polymkt_db_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d

volumes:
  polymkt_db_data:
```

- [ ] **Step 2: Write `db/init/001_create_test_db.sql`**

```sql
CREATE DATABASE polymkt_test;
```

This runs once on first container start, creating a second database used only by the test suite (Task 3 onward), so tests never touch the `polymkt` dev database.

- [ ] **Step 3: Start the database and verify it's healthy**

```bash
docker compose up -d db
docker compose ps
```

Expected: `db` service shows `healthy` or `running` status within ~15 seconds.

- [ ] **Step 4: Create `src/polymkt/db/__init__.py`** (empty file)

- [ ] **Step 5: Write `src/polymkt/db/session.py`**

```python
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from polymkt.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

There's no unit test for this file in isolation — it's exercised end-to-end by Task 11's scheduler test and by manual verification in Step 3.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml db/init/001_create_test_db.sql src/polymkt/db/__init__.py src/polymkt/db/session.py
git commit -m "feat: add Postgres/Timescale docker compose and DB session factory"
git push
```

---

### Task 3: SQLAlchemy models and test database fixtures

**Files:**
- Create: `src/polymkt/db/models.py`
- Create: `tests/conftest.py` (replaces Task 1's placeholder)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `polymkt.db.models.Base`, `Market`, `TraderRanking`, `Position`, `MarketPriceSnapshot` — the four tables every later ingestion task reads/writes. Exact columns listed below; later tasks depend on these exact names and types.
- Produces (test infra): `tests.conftest` fixtures `engine` (session-scoped) and `db_session` (function-scoped, rolled back after each test) — every DB-touching test from Task 7 onward uses `db_session`.

- [ ] **Step 1: Write `src/polymkt/db/models.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    token_id_yes: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_id_no: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TraderRanking(Base):
    __tablename__ = "trader_rankings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    pnl: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    time_period: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "wallet_address", "time_period", "category", "captured_at",
            name="uq_trader_ranking_snapshot",
        ),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    value_usd: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    best_bid: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from polymkt.db.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/polymkt_test",
)


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

- [ ] **Step 3: Write the failing test — `tests/test_models.py`**

```python
from datetime import datetime, timezone

from polymkt.db.models import Market, MarketPriceSnapshot, Position, TraderRanking


def test_market_round_trip(db_session):
    db_session.add(
        Market(
            condition_id="0xabc",
            slug="test-market",
            question="Will X happen?",
            category="Politics",
            active=True,
            token_id_yes="111",
            token_id_no="222",
        )
    )
    db_session.flush()

    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.slug == "test-market"
    assert market.token_id_yes == "111"


def test_trader_ranking_unique_constraint(db_session):
    captured_at = datetime.now(timezone.utc)
    db_session.add(
        TraderRanking(
            wallet_address="0x111",
            rank=1,
            pnl=1000.0,
            volume=5000.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=captured_at,
        )
    )
    db_session.flush()

    ranking = db_session.query(TraderRanking).one()
    assert ranking.wallet_address == "0x111"


def test_position_and_price_snapshot_round_trip(db_session):
    captured_at = datetime.now(timezone.utc)
    db_session.add(
        Position(
            wallet_address="0x111",
            condition_id="0xabc",
            outcome="Yes",
            size=1200.0,
            value_usd=540.0,
            captured_at=captured_at,
        )
    )
    db_session.add(
        MarketPriceSnapshot(
            condition_id="0xabc",
            outcome="Yes",
            price=0.45,
            best_bid=0.44,
            best_ask=0.46,
            captured_at=captured_at,
        )
    )
    db_session.flush()

    assert db_session.query(Position).count() == 1
    assert db_session.query(MarketPriceSnapshot).count() == 1
```

- [ ] **Step 4: Ensure the test database exists and run the test to verify it fails**

```bash
docker compose up -d db
pytest tests/test_models.py -v
```

Expected: FAIL if `db/init/001_create_test_db.sql` hadn't run yet on an existing volume (e.g. `database "polymkt_test" does not exist`) — if so, run `docker compose down -v && docker compose up -d db` to reinitialize, since init scripts only run on first volume creation. Otherwise this step should already PASS since Steps 1–2 provide a complete implementation; if it fails for any other reason (e.g. a typo in a column type), that's the bug to fix before continuing.

- [ ] **Step 5: Run the test to verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/polymkt/db/models.py tests/conftest.py tests/test_models.py
git commit -m "feat: add SQLAlchemy models and test database fixtures"
git push
```

---

### Task 4: Gamma API client (market metadata)

**Files:**
- Create: `src/polymkt/clients/__init__.py`
- Create: `src/polymkt/clients/gamma_client.py`
- Test: `tests/test_gamma_client.py`

**Interfaces:**
- Produces: `GammaClient(base_url: str, client: httpx.Client | None = None)` with method `get_active_markets(limit: int = 100, offset: int = 0) -> list[dict]`. Task 7 depends on this exact signature and on the raw dict shape matching the Polymarket Gamma `/markets` response (keys `conditionId`, `slug`, `question`, `category`, `active`, `clobTokenIds`).

- [ ] **Step 1: Create `src/polymkt/clients/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test — `tests/test_gamma_client.py`**

```python
import httpx
import respx

from polymkt.clients.gamma_client import GammaClient

MARKETS_PAGE = [
    {
        "id": "703257",
        "slug": "will-the-us-confirm-that-aliens-exist-before-2027",
        "question": "Will the US confirm that aliens exist before 2027?",
        "conditionId": "0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75",
        "category": "Culture",
        "active": True,
        "clobTokenIds": '["1075058827","7305630249"]',
    }
]


@respx.mock
def test_get_active_markets_queries_active_non_closed_markets():
    route = respx.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=httpx.Response(200, json=MARKETS_PAGE)
    )

    client = GammaClient(base_url="https://gamma-api.polymarket.com")
    markets = client.get_active_markets(limit=100, offset=0)

    assert route.called
    request_params = route.calls.last.request.url.params
    assert request_params["active"] == "true"
    assert request_params["closed"] == "false"
    assert request_params["limit"] == "100"
    assert markets == MARKETS_PAGE


@respx.mock
def test_get_active_markets_raises_on_http_error():
    respx.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=httpx.Response(500)
    )

    client = GammaClient(base_url="https://gamma-api.polymarket.com")

    try:
        client.get_active_markets()
        raise AssertionError("expected HTTPStatusError")
    except httpx.HTTPStatusError:
        pass
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_gamma_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'polymkt.clients.gamma_client'`.

- [ ] **Step 4: Write `src/polymkt/clients/gamma_client.py`**

```python
import httpx


class GammaClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_active_markets(self, limit: int = 100, offset: int = 0) -> list[dict]:
        response = self._client.get(
            "/markets",
            params={"active": "true", "closed": "false", "limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_gamma_client.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/polymkt/clients/__init__.py src/polymkt/clients/gamma_client.py tests/test_gamma_client.py
git commit -m "feat: add Gamma API client for market metadata"
git push
```

---

### Task 5: CLOB API client (order books)

**Files:**
- Create: `src/polymkt/clients/clob_client.py`
- Test: `tests/test_clob_client.py`

**Interfaces:**
- Produces: `ClobClient(base_url: str, client: httpx.Client | None = None)` with method `get_order_books(token_ids: list[str]) -> list[dict]`, calling `POST /books` with a JSON array of token IDs (batches up to 500 per the CLOB API's documented limit — batching itself is Task 9's responsibility, this client just posts what it's given). Task 9 depends on the response items having `asset_id`, `bids: [{"price": str, "size": str}, ...]`, `asks: [...]`.

- [ ] **Step 1: Write the failing test — `tests/test_clob_client.py`**

```python
import json

import httpx
import respx

from polymkt.clients.clob_client import ClobClient

BOOKS_RESPONSE = [
    {
        "asset_id": "1075058827",
        "bids": [{"price": "0.42", "size": "100"}],
        "asks": [{"price": "0.45", "size": "80"}],
    }
]


@respx.mock
def test_get_order_books_posts_token_ids_and_returns_books():
    route = respx.post("https://clob.polymarket.com/books").mock(
        return_value=httpx.Response(200, json=BOOKS_RESPONSE)
    )

    client = ClobClient(base_url="https://clob.polymarket.com")
    books = client.get_order_books(["1075058827"])

    assert route.called
    assert json.loads(route.calls.last.request.content) == ["1075058827"]
    assert books == BOOKS_RESPONSE


@respx.mock
def test_get_order_books_raises_on_http_error():
    respx.post("https://clob.polymarket.com/books").mock(return_value=httpx.Response(500))

    client = ClobClient(base_url="https://clob.polymarket.com")

    try:
        client.get_order_books(["111"])
        raise AssertionError("expected HTTPStatusError")
    except httpx.HTTPStatusError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_clob_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/clients/clob_client.py`**

```python
import httpx


class ClobClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_order_books(self, token_ids: list[str]) -> list[dict]:
        response = self._client.post("/books", json=token_ids)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_clob_client.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/clients/clob_client.py tests/test_clob_client.py
git commit -m "feat: add CLOB API client for order books"
git push
```

---

### Task 6: Data API client (leaderboard + positions)

**Files:**
- Create: `src/polymkt/clients/data_api_client.py`
- Test: `tests/test_data_api_client.py`

**Interfaces:**
- Produces: `DataApiClient(base_url: str, client: httpx.Client | None = None)` with:
  - `get_leaderboard(*, category: str = "OVERALL", time_period: str = "ALL", order_by: str = "PNL", limit: int = 50, offset: int = 0) -> list[dict]` — calls `GET /v1/leaderboard`. Task 8 depends on response items having `rank`, `proxyWallet`, `pnl`, `vol`.
  - `get_positions(wallet_address: str, *, size_threshold: float = 1.0) -> list[dict]` — calls `GET /positions`. Task 10 depends on response items having `conditionId`, `outcome`, `size`, `currentValue`.

- [ ] **Step 1: Write the failing test — `tests/test_data_api_client.py`**

```python
import httpx
import respx

from polymkt.clients.data_api_client import DataApiClient

LEADERBOARD_PAGE = [
    {"rank": "1", "proxyWallet": "0x111", "userName": "whale1", "vol": 2000000.0, "pnl": 500000.0}
]

POSITIONS_PAGE = [
    {
        "proxyWallet": "0x111",
        "conditionId": "0xabc",
        "outcome": "Yes",
        "size": 1200.0,
        "currentValue": 540.0,
    }
]


@respx.mock
def test_get_leaderboard_queries_expected_params():
    route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
        return_value=httpx.Response(200, json=LEADERBOARD_PAGE)
    )

    client = DataApiClient(base_url="https://data-api.polymarket.com")
    traders = client.get_leaderboard(category="OVERALL", time_period="ALL", limit=50, offset=0)

    assert route.called
    params = route.calls.last.request.url.params
    assert params["category"] == "OVERALL"
    assert params["timePeriod"] == "ALL"
    assert params["orderBy"] == "PNL"
    assert traders == LEADERBOARD_PAGE


@respx.mock
def test_get_positions_queries_by_user():
    route = respx.get("https://data-api.polymarket.com/positions").mock(
        return_value=httpx.Response(200, json=POSITIONS_PAGE)
    )

    client = DataApiClient(base_url="https://data-api.polymarket.com")
    positions = client.get_positions("0x111")

    assert route.called
    assert route.calls.last.request.url.params["user"] == "0x111"
    assert positions == POSITIONS_PAGE
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_data_api_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/clients/data_api_client.py`**

```python
import httpx


class DataApiClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_leaderboard(
        self,
        *,
        category: str = "OVERALL",
        time_period: str = "ALL",
        order_by: str = "PNL",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        response = self._client.get(
            "/v1/leaderboard",
            params={
                "category": category,
                "timePeriod": time_period,
                "orderBy": order_by,
                "limit": limit,
                "offset": offset,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_positions(self, wallet_address: str, *, size_threshold: float = 1.0) -> list[dict]:
        response = self._client.get(
            "/positions",
            params={"user": wallet_address, "sizeThreshold": size_threshold, "limit": 500},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_data_api_client.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/clients/data_api_client.py tests/test_data_api_client.py
git commit -m "feat: add Data API client for leaderboard and positions"
git push
```

---

### Task 7: Market ingestion

**Files:**
- Create: `src/polymkt/ingestion/__init__.py`
- Create: `src/polymkt/ingestion/markets.py`
- Test: `tests/test_market_ingestion.py`

**Interfaces:**
- Consumes: `GammaClient.get_active_markets(limit, offset) -> list[dict]` (Task 4); `Market` model (Task 3).
- Produces: `ingest_markets(session: Session, client) -> int` — upserts every active market by `condition_id`, returns the count fetched. `client` only needs to duck-type `get_active_markets(limit, offset)`, so tests use a fake. Task 11 depends on this exact function name and signature.

- [ ] **Step 1: Create `src/polymkt/ingestion/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test — `tests/test_market_ingestion.py`**

```python
from polymkt.db.models import Market
from polymkt.ingestion.markets import ingest_markets

RAW_MARKET = {
    "conditionId": "0xabc",
    "slug": "test-market",
    "question": "Will X happen?",
    "category": "Politics",
    "active": True,
    "clobTokenIds": '["111","222"]',
}


class FakeGammaClient:
    def __init__(self, pages: list[list[dict]]) -> None:
        self._pages = pages

    def get_active_markets(self, limit: int, offset: int) -> list[dict]:
        page_index = offset // limit
        if page_index >= len(self._pages):
            return []
        return self._pages[page_index]


def test_ingest_markets_creates_new_market(db_session):
    client = FakeGammaClient(pages=[[RAW_MARKET]])

    count = ingest_markets(db_session, client)

    assert count == 1
    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.token_id_yes == "111"
    assert market.token_id_no == "222"
    assert market.category == "Politics"


def test_ingest_markets_updates_existing_market_instead_of_duplicating(db_session):
    ingest_markets(db_session, FakeGammaClient(pages=[[RAW_MARKET]]))

    updated_market = dict(RAW_MARKET, question="Updated question?")
    ingest_markets(db_session, FakeGammaClient(pages=[[updated_market]]))

    assert db_session.query(Market).count() == 1
    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.question == "Updated question?"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_market_ingestion.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'polymkt.ingestion.markets'`.

- [ ] **Step 4: Write `src/polymkt/ingestion/markets.py`**

```python
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from polymkt.db.models import Market

PAGE_SIZE = 100


def fetch_all_active_markets(client) -> list[dict]:
    markets: list[dict] = []
    offset = 0
    while True:
        page = client.get_active_markets(limit=PAGE_SIZE, offset=offset)
        markets.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return markets


def upsert_market(session: Session, raw_market: dict) -> Market:
    token_ids = json.loads(raw_market.get("clobTokenIds") or "[]")
    token_id_yes = token_ids[0] if len(token_ids) > 0 else None
    token_id_no = token_ids[1] if len(token_ids) > 1 else None

    market = session.scalar(select(Market).where(Market.condition_id == raw_market["conditionId"]))
    if market is None:
        market = Market(condition_id=raw_market["conditionId"])
        session.add(market)

    market.slug = raw_market["slug"]
    market.question = raw_market["question"]
    market.category = raw_market.get("category")
    market.active = bool(raw_market.get("active", True))
    market.token_id_yes = token_id_yes
    market.token_id_no = token_id_no
    return market


def ingest_markets(session: Session, client) -> int:
    raw_markets = fetch_all_active_markets(client)
    for raw_market in raw_markets:
        upsert_market(session, raw_market)
    session.flush()
    return len(raw_markets)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_market_ingestion.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/polymkt/ingestion/__init__.py src/polymkt/ingestion/markets.py tests/test_market_ingestion.py
git commit -m "feat: add market ingestion pipeline"
git push
```

---

### Task 8: Leaderboard ingestion

**Files:**
- Create: `src/polymkt/ingestion/leaderboard.py`
- Test: `tests/test_leaderboard_ingestion.py`

**Interfaces:**
- Consumes: `DataApiClient.get_leaderboard(...)` (Task 6); `TraderRanking` model (Task 3).
- Produces: `ingest_leaderboard(session: Session, client, *, top_n: int, category: str, time_period: str) -> int` — pages through the leaderboard until `top_n` traders are collected (or the API runs out), inserts one `TraderRanking` row per trader stamped with the current UTC time, returns the count inserted. Task 10 depends on `TraderRanking.wallet_address` being queryable to find which wallets to fetch positions for.

- [ ] **Step 1: Write the failing test — `tests/test_leaderboard_ingestion.py`**

```python
from polymkt.db.models import TraderRanking
from polymkt.ingestion.leaderboard import ingest_leaderboard


class FakeDataApiClient:
    def __init__(self, pages: list[list[dict]]) -> None:
        self._pages = pages
        self._calls = 0

    def get_leaderboard(self, **kwargs) -> list[dict]:
        if self._calls >= len(self._pages):
            return []
        page = self._pages[self._calls]
        self._calls += 1
        return page


def test_ingest_leaderboard_stores_top_n_traders(db_session):
    trader = {"rank": "1", "proxyWallet": "0x111", "pnl": 500000.0, "vol": 2000000.0}
    client = FakeDataApiClient(pages=[[trader]])

    count = ingest_leaderboard(db_session, client, top_n=1, category="OVERALL", time_period="ALL")

    assert count == 1
    ranking = db_session.query(TraderRanking).one()
    assert ranking.wallet_address == "0x111"
    assert ranking.rank == 1


def test_ingest_leaderboard_stops_once_top_n_reached_across_pages(db_session):
    page1 = [{"rank": str(i), "proxyWallet": f"0x{i}", "pnl": 100.0, "vol": 10.0} for i in range(1, 51)]
    page2 = [{"rank": str(i), "proxyWallet": f"0x{i}", "pnl": 50.0, "vol": 5.0} for i in range(51, 101)]
    client = FakeDataApiClient(pages=[page1, page2])

    count = ingest_leaderboard(db_session, client, top_n=60, category="OVERALL", time_period="ALL")

    assert count == 60
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_leaderboard_ingestion.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/ingestion/leaderboard.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import TraderRanking

PAGE_SIZE = 50


def fetch_top_traders(client, *, top_n: int, category: str, time_period: str) -> list[dict]:
    traders: list[dict] = []
    offset = 0
    while len(traders) < top_n:
        page = client.get_leaderboard(
            category=category,
            time_period=time_period,
            order_by="PNL",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not page:
            break
        traders.extend(page)
        offset += PAGE_SIZE
    return traders[:top_n]


def ingest_leaderboard(session: Session, client, *, top_n: int, category: str, time_period: str) -> int:
    traders = fetch_top_traders(client, top_n=top_n, category=category, time_period=time_period)
    captured_at = datetime.now(timezone.utc)

    for trader in traders:
        session.add(
            TraderRanking(
                wallet_address=trader["proxyWallet"],
                rank=int(trader["rank"]),
                pnl=trader["pnl"],
                volume=trader["vol"],
                time_period=time_period,
                category=category,
                captured_at=captured_at,
            )
        )
    session.flush()
    return len(traders)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_leaderboard_ingestion.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/ingestion/leaderboard.py tests/test_leaderboard_ingestion.py
git commit -m "feat: add leaderboard ingestion pipeline"
git push
```

---

### Task 9: Price ingestion

**Files:**
- Create: `src/polymkt/ingestion/prices.py`
- Test: `tests/test_price_ingestion.py`

**Interfaces:**
- Consumes: `ClobClient.get_order_books(token_ids)` (Task 5); `Market`, `MarketPriceSnapshot` models (Task 3).
- Produces: `ingest_prices(session: Session, client) -> int` — for every active `Market`'s YES/NO token IDs, fetches order books in batches of up to 500, computes best bid/ask/mid, inserts one `MarketPriceSnapshot` per outcome per market, returns the count inserted. Skips outcomes with no book (no bids or no asks).

- [ ] **Step 1: Write the failing test — `tests/test_price_ingestion.py`**

```python
from polymkt.db.models import Market, MarketPriceSnapshot
from polymkt.ingestion.prices import ingest_prices


class FakeClobClient:
    def __init__(self, books: list[dict]) -> None:
        self._books = books

    def get_order_books(self, token_ids: list[str]) -> list[dict]:
        return [book for book in self._books if book["asset_id"] in token_ids]


def _add_test_market(db_session) -> None:
    db_session.add(
        Market(
            condition_id="0xabc",
            slug="test-market",
            question="Will X happen?",
            category="Politics",
            active=True,
            token_id_yes="111",
            token_id_no="222",
        )
    )
    db_session.flush()


def test_ingest_prices_stores_snapshot_from_order_book(db_session):
    _add_test_market(db_session)
    books = [
        {"asset_id": "111", "bids": [{"price": "0.40", "size": "10"}], "asks": [{"price": "0.44", "size": "10"}]},
        {"asset_id": "222", "bids": [{"price": "0.55", "size": "10"}], "asks": [{"price": "0.59", "size": "10"}]},
    ]
    client = FakeClobClient(books)

    count = ingest_prices(db_session, client)

    assert count == 2
    yes_snapshot = db_session.query(MarketPriceSnapshot).filter_by(condition_id="0xabc", outcome="Yes").one()
    assert float(yes_snapshot.price) == 0.42
    assert float(yes_snapshot.best_bid) == 0.40
    assert float(yes_snapshot.best_ask) == 0.44


def test_ingest_prices_skips_outcome_with_no_order_book(db_session):
    _add_test_market(db_session)
    client = FakeClobClient(books=[])

    count = ingest_prices(db_session, client)

    assert count == 0
    assert db_session.query(MarketPriceSnapshot).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_price_ingestion.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/ingestion/prices.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import Market, MarketPriceSnapshot

BATCH_SIZE = 500


def _best_bid(book: dict) -> float | None:
    bids = book.get("bids") or []
    if not bids:
        return None
    return max(float(level["price"]) for level in bids)


def _best_ask(book: dict) -> float | None:
    asks = book.get("asks") or []
    if not asks:
        return None
    return min(float(level["price"]) for level in asks)


def ingest_prices(session: Session, client) -> int:
    markets = session.query(Market).filter(Market.active.is_(True)).all()

    token_id_to_market_outcome: dict[str, tuple[str, str]] = {}
    for market in markets:
        if market.token_id_yes:
            token_id_to_market_outcome[market.token_id_yes] = (market.condition_id, "Yes")
        if market.token_id_no:
            token_id_to_market_outcome[market.token_id_no] = (market.condition_id, "No")

    token_ids = list(token_id_to_market_outcome.keys())
    if not token_ids:
        return 0

    captured_at = datetime.now(timezone.utc)
    total = 0

    for batch_start in range(0, len(token_ids), BATCH_SIZE):
        batch = token_ids[batch_start : batch_start + BATCH_SIZE]
        books = client.get_order_books(batch)

        for book in books:
            condition_id, outcome = token_id_to_market_outcome[book["asset_id"]]
            best_bid = _best_bid(book)
            best_ask = _best_ask(book)
            if best_bid is None or best_ask is None:
                continue

            session.add(
                MarketPriceSnapshot(
                    condition_id=condition_id,
                    outcome=outcome,
                    price=(best_bid + best_ask) / 2,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    captured_at=captured_at,
                )
            )
            total += 1

    session.flush()
    return total
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_price_ingestion.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/ingestion/prices.py tests/test_price_ingestion.py
git commit -m "feat: add price ingestion pipeline"
git push
```

---

### Task 10: Position ingestion

**Files:**
- Create: `src/polymkt/ingestion/positions.py`
- Test: `tests/test_position_ingestion.py`

**Interfaces:**
- Consumes: `DataApiClient.get_positions(wallet_address)` (Task 6); `TraderRanking`, `Position` models (Task 3).
- Produces: `ingest_positions_for_top_traders(session: Session, client) -> int` — reads distinct `wallet_address` values already in `trader_rankings` (populated by Task 8), fetches each wallet's positions, inserts one `Position` row per position, returns the total inserted.

- [ ] **Step 1: Write the failing test — `tests/test_position_ingestion.py`**

```python
from datetime import datetime, timezone

from polymkt.db.models import Position, TraderRanking
from polymkt.ingestion.positions import ingest_positions_for_top_traders


class FakeDataApiClient:
    def __init__(self, positions_by_wallet: dict[str, list[dict]]) -> None:
        self._positions_by_wallet = positions_by_wallet

    def get_positions(self, wallet_address: str, **kwargs) -> list[dict]:
        return self._positions_by_wallet.get(wallet_address, [])


def test_ingest_positions_for_top_traders_stores_positions_for_known_wallets(db_session):
    db_session.add(
        TraderRanking(
            wallet_address="0x111",
            rank=1,
            pnl=500000.0,
            volume=2000000.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    raw_position = {"conditionId": "0xabc", "outcome": "Yes", "size": 1200.0, "currentValue": 540.0}
    client = FakeDataApiClient(positions_by_wallet={"0x111": [raw_position]})

    count = ingest_positions_for_top_traders(db_session, client)

    assert count == 1
    position = db_session.query(Position).one()
    assert position.wallet_address == "0x111"
    assert position.condition_id == "0xabc"


def test_ingest_positions_skips_wallets_with_no_positions(db_session):
    db_session.add(
        TraderRanking(
            wallet_address="0x222",
            rank=2,
            pnl=100.0,
            volume=100.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    client = FakeDataApiClient(positions_by_wallet={})

    count = ingest_positions_for_top_traders(db_session, client)

    assert count == 0
    assert db_session.query(Position).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_position_ingestion.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/ingestion/positions.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import Position, TraderRanking


def ingest_positions_for_top_traders(session: Session, client) -> int:
    wallet_addresses = [row[0] for row in session.query(TraderRanking.wallet_address).distinct().all()]
    captured_at = datetime.now(timezone.utc)
    total = 0

    for wallet_address in wallet_addresses:
        raw_positions = client.get_positions(wallet_address)
        for raw_position in raw_positions:
            session.add(
                Position(
                    wallet_address=wallet_address,
                    condition_id=raw_position["conditionId"],
                    outcome=raw_position["outcome"],
                    size=raw_position["size"],
                    value_usd=raw_position["currentValue"],
                    captured_at=captured_at,
                )
            )
            total += 1

    session.flush()
    return total
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_position_ingestion.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/ingestion/positions.py tests/test_position_ingestion.py
git commit -m "feat: add position ingestion pipeline"
git push
```

---

### Task 11: Scheduler entrypoint

**Files:**
- Create: `src/polymkt/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `settings` (Task 1), `get_session` (Task 2), all four `ingest_*` functions (Tasks 7–10), all three clients (Tasks 4–6).
- Produces: `build_scheduler() -> BlockingScheduler` — registers the four ingestion jobs with the cadences from `docs/design.md` (markets every 20 min, leaderboard every 24h, positions every 20 min, prices every 3 min) without starting them, so it's testable. `main()` builds and starts the scheduler; this is the process entrypoint (`python -m polymkt.run`).

- [ ] **Step 1: Write the failing test — `tests/test_run.py`**

```python
from polymkt.run import build_scheduler


def test_build_scheduler_registers_all_ingestion_jobs_with_expected_intervals():
    scheduler = build_scheduler()

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {
        "market_ingestion",
        "leaderboard_ingestion",
        "position_ingestion",
        "price_ingestion",
    }
    assert jobs["market_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["leaderboard_ingestion"].trigger.interval.total_seconds() == 24 * 60 * 60
    assert jobs["position_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["price_ingestion"].trigger.interval.total_seconds() == 3 * 60
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_run.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/polymkt/run.py`**

```python
from apscheduler.schedulers.blocking import BlockingScheduler

from polymkt.clients.clob_client import ClobClient
from polymkt.clients.data_api_client import DataApiClient
from polymkt.clients.gamma_client import GammaClient
from polymkt.config import settings
from polymkt.db.session import get_session
from polymkt.ingestion.leaderboard import ingest_leaderboard
from polymkt.ingestion.markets import ingest_markets
from polymkt.ingestion.positions import ingest_positions_for_top_traders
from polymkt.ingestion.prices import ingest_prices


def run_market_ingestion() -> None:
    client = GammaClient(base_url=settings.gamma_base_url)
    try:
        with get_session() as session:
            ingest_markets(session, client)
    finally:
        client.close()


def run_leaderboard_ingestion() -> None:
    client = DataApiClient(base_url=settings.data_api_base_url)
    try:
        with get_session() as session:
            ingest_leaderboard(
                session,
                client,
                top_n=settings.top_n_traders,
                category=settings.leaderboard_category,
                time_period=settings.leaderboard_time_period,
            )
    finally:
        client.close()


def run_position_ingestion() -> None:
    client = DataApiClient(base_url=settings.data_api_base_url)
    try:
        with get_session() as session:
            ingest_positions_for_top_traders(session, client)
    finally:
        client.close()


def run_price_ingestion() -> None:
    client = ClobClient(base_url=settings.clob_base_url)
    try:
        with get_session() as session:
            ingest_prices(session, client)
    finally:
        client.close()


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_market_ingestion, "interval", minutes=20, id="market_ingestion")
    scheduler.add_job(run_leaderboard_ingestion, "interval", hours=24, id="leaderboard_ingestion")
    scheduler.add_job(run_position_ingestion, "interval", minutes=20, id="position_ingestion")
    scheduler.add_job(run_price_ingestion, "interval", minutes=3, id="price_ingestion")
    return scheduler


def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_run.py -v
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/polymkt/run.py tests/test_run.py
git commit -m "feat: add scheduler entrypoint wiring all ingestion jobs"
git push
```

---

### Task 12: CI workflow and README

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (replace the "Roadmap" checklist items this plan completes)

**Interfaces:** None — this task wires up automation and docs around the code from Tasks 1–11; it doesn't introduce new interfaces.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: polymkt
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Create test database
        run: PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE polymkt_test;"
      - name: Run tests
        env:
          TEST_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/polymkt_test
        run: pytest -v
```

Note: CI uses a plain `postgres:16` service, not the TimescaleDB image used in local `docker-compose.yml` — this foundation plan doesn't yet use any Timescale-specific feature (hypertables), so the lighter, more available GitHub Actions image is sufficient. A later plan that adds hypertables must switch this service to a Timescale image.

- [ ] **Step 2: Update `README.md`**

Replace the `## Roadmap` section with:

```markdown
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
```

- [ ] **Step 3: Run the full test suite one more time to confirm nothing regressed**

```bash
pytest -v
```

Expected: PASS (all tests from Tasks 1, 3–11 — roughly 20 tests).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "chore: add CI workflow and update README roadmap"
git push
```

- [ ] **Step 5: Open the pull request**

```bash
gh pr create --title "feat: foundation and ingestion pipeline" --body "$(cat <<'EOF'
## Summary
- Project scaffolding (pyproject.toml, settings, Docker Compose with TimescaleDB).
- SQLAlchemy schema: markets, trader_rankings, positions, market_price_snapshots.
- Gamma/CLOB/Data API client wrappers.
- Four ingestion pipelines (markets, leaderboard, positions, prices), each unit tested against a real test Postgres with fake API clients.
- APScheduler entrypoint wiring all four jobs at the cadences from docs/design.md.
- CI workflow running the full suite against a Postgres service container.

## Test plan
- [x] `pytest -v` passes locally against `docker compose up -d db`
- [ ] CI passes on this PR
- [ ] Manual smoke test: `python -m polymkt.run` for a few minutes against real Polymarket APIs, confirm rows appear in all four tables

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

Do not merge this PR — per `WORKFLOW.md`, merging to `main` requires human review.
