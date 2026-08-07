# Smart Money Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calculate and persist a normalized Smart Money score for both sides of every known active binary market using only the latest top-trader and position snapshots.

**Architecture:** Add an append-only `SmartMoneyScore` SQLAlchemy model and a focused `calculate_smart_money_scores` service. SQLAlchemy queries select the configured latest leaderboard cohort and aggregate the latest position snapshot; Python completes the zero-anchored normalization and persists one shared-timestamp batch. The existing scheduler invokes the service every 20 minutes after position ingestion.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, PostgreSQL/TimescaleDB, APScheduler, pytest.

## Global Constraints

- Work only on `worktree-smart-money-scoring`; never commit or push directly to `main`.
- Follow strict TDD: add one failing behavior test, run it and observe the expected failure, then add the minimum production code.
- Use only the latest `TraderRanking` snapshot for the configured `category` and `time_period`, ordered by rank and limited to `top_n`.
- Use only the globally latest `Position` snapshot. Historical rows must never inflate current capital.
- Score only active known binary markets and the exact outcomes `"Yes"` and `"No"`.
- Persist coverage-zero rows, use one `captured_at` value per execution, and never upsert historical scores.
- Normalize with `capital_usd / max_capital_in_batch * 100`; if the maximum is zero, every score is zero.
- No HTTP client is involved in scoring.

---

### Task 1: Smart Money Score persistence model

**Files:**
- Modify: `src/polymkt/db/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `polymkt.db.models.SmartMoneyScore`, mapped to `smart_money_scores` with `condition_id`, `outcome`, `capital_usd`, `score`, `has_coverage`, `trader_count`, and `captured_at`.

- [ ] **Step 1: Write a failing round-trip test**

Add a test that inserts a `SmartMoneyScore`, flushes it, reloads it, and asserts all fields including `Decimal("1250.50")`, `Decimal("82.75")`, `True`, trader count `3`, and the supplied timestamp.

- [ ] **Step 2: Verify the test fails for the missing model**

Run: `.venv/bin/pytest tests/test_models.py::test_smart_money_score_round_trip -v`

Expected: collection fails because `SmartMoneyScore` cannot be imported.

- [ ] **Step 3: Implement the mapped model**

Add the model using `BigInteger`, `String(80/16)`, `Numeric(18,2)`, `Numeric(6,2)`, `Boolean`, integer `trader_count`, and timezone-aware `DateTime`, all non-nullable.

- [ ] **Step 4: Verify the model test passes**

Run: `.venv/bin/pytest tests/test_models.py::test_smart_money_score_round_trip -v`

Expected: PASS.

- [ ] **Step 5: Commit the model**

```bash
git add src/polymkt/db/models.py tests/test_models.py
git commit -m "feat: add smart money score model"
```

---

### Task 2: Current-snapshot capital aggregation and persistence

**Files:**
- Create: `src/polymkt/scoring/__init__.py`
- Create: `src/polymkt/scoring/smart_money.py`
- Create: `tests/test_smart_money_scoring.py`

**Interfaces:**
- Consumes: `Session`, `Market`, `TraderRanking`, `Position`, `SmartMoneyScore`.
- Produces: `calculate_smart_money_scores(session: Session, *, top_n: int, category: str, time_period: str) -> int`.

- [ ] **Step 1: Test capital aggregation and both market sides**

Create synthetic active markets, one latest leaderboard cohort, and positions where two current top traders hold `Yes` capital. Assert the function returns two rows per market, sums `value_usd`, counts distinct wallets, and persists an uncovered `No` side.

- [ ] **Step 2: Verify the aggregation test fails**

Run: `.venv/bin/pytest tests/test_smart_money_scoring.py::test_aggregates_current_top_trader_capital_for_both_sides -v`

Expected: collection fails because `polymkt.scoring.smart_money` does not exist.

- [ ] **Step 3: Implement the minimum scoring service**

Create the scoring package. Resolve the latest matching leaderboard timestamp, select its first `top_n` wallet addresses by rank, resolve the maximum position timestamp, query active markets, aggregate matching positions by `(condition_id, outcome)`, and append `SmartMoneyScore` rows for exact `Yes` and `No` outcomes using one UTC timestamp. Return the number of rows added.

- [ ] **Step 4: Verify the aggregation test passes**

Run the test from Step 2 and expect PASS.

- [ ] **Step 5: Test historical snapshot exclusion**

Add old and new leaderboard and position snapshots with deliberately larger old capital. Assert only wallets from the latest matching cohort and positions from the latest position timestamp affect the result.

- [ ] **Step 6: Verify RED, then implement the snapshot filters and verify GREEN**

Run the new test before and after the query change. The first run must fail by reporting old capital or traders; the second must pass.

- [ ] **Step 7: Test scope rules**

Add tests proving inactive markets and unknown `condition_id` values produce no rows, and lowercase/unknown outcomes do not create coverage for exact `Yes`/`No` sides.

- [ ] **Step 8: Verify RED, implement the filters, and verify GREEN**

Run only the new scope tests before and after the minimum filter changes.

- [ ] **Step 9: Commit aggregation behavior**

```bash
git add src/polymkt/scoring tests/test_smart_money_scoring.py
git commit -m "feat: aggregate current smart money capital"
```

---

### Task 3: Zero-anchored normalization and edge cases

**Files:**
- Modify: `src/polymkt/scoring/smart_money.py`
- Modify: `tests/test_smart_money_scoring.py`

**Interfaces:**
- Preserves: `calculate_smart_money_scores(...) -> int`.
- Produces: two-decimal `score` values and exact two-decimal `capital_usd` values compatible with the database schema.

- [ ] **Step 1: Test zero-anchored normalization**

Create two covered sides with capital `$500000` and `$50`. Assert scores are `Decimal("100.00")` and `Decimal("0.01")`, demonstrating this is not min-max normalization.

- [ ] **Step 2: Verify the normalization test fails**

Run the single test and confirm the lower-capital side does not yet produce `0.01`.

- [ ] **Step 3: Implement Decimal-based normalization**

Find the largest capital across the batch and calculate `(capital / maximum) * Decimal("100")`, quantized to `Decimal("0.01")`. Set `has_coverage` from positive capital.

- [ ] **Step 4: Verify normalization passes**

Run the single test and expect PASS.

- [ ] **Step 5: Test the all-zero batch and missing source snapshots**

Assert active markets without positions create zero-score, zero-capital, zero-trader rows without division errors. Assert an empty leaderboard or empty positions table also produces the same complete zero-coverage batch for active markets.

- [ ] **Step 6: Verify RED, implement zero handling, and verify GREEN**

Run the new tests before and after the smallest necessary changes.

- [ ] **Step 7: Run the focused scoring suite**

Run: `.venv/bin/pytest tests/test_smart_money_scoring.py -v`

Expected: all scoring tests PASS.

- [ ] **Step 8: Commit normalization**

```bash
git add src/polymkt/scoring/smart_money.py tests/test_smart_money_scoring.py
git commit -m "feat: normalize smart money scores"
```

---

### Task 4: Scheduler integration

**Files:**
- Modify: `src/polymkt/run.py`
- Modify: `tests/test_run.py`

**Interfaces:**
- Produces: `run_smart_money_scoring() -> None` and scheduler job `smart_money_scoring` at a 20-minute interval.

- [ ] **Step 1: Extend the scheduler test first**

Require the `smart_money_scoring` job and assert its interval is `20 * 60` seconds.

- [ ] **Step 2: Verify the scheduler test fails**

Run: `.venv/bin/pytest tests/test_run.py -v`

Expected: FAIL because the fifth job is absent.

- [ ] **Step 3: Add the runner and scheduler job**

Import `calculate_smart_money_scores`. Add `run_smart_money_scoring()` using `get_session()` and configured top-N/category/time period, log the row count, and register it at 20 minutes. Do not create an HTTP client.

- [ ] **Step 4: Add and verify a runner interaction test**

Patch `get_session` and `calculate_smart_money_scores`, call the runner, and assert the service receives the yielded session and configured values. Observe RED before adding missing wiring, then GREEN.

- [ ] **Step 5: Run scheduler tests**

Run: `.venv/bin/pytest tests/test_run.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit scheduler integration**

```bash
git add src/polymkt/run.py tests/test_run.py
git commit -m "feat: schedule smart money scoring"
```

---

### Task 5: Documentation and full verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents the completed Phase 1 ingestion foundation and the newly implemented Smart Money scoring phase.

- [ ] **Step 1: Update project status and roadmap**

Mark Smart Money scoring complete, describe the append-only score snapshots briefly, and remove the stale claim that Phase 1 ingestion is still under development.

- [ ] **Step 2: Start the test database**

Run: `docker compose up -d db`

Wait for PostgreSQL to accept connections. If the persisted volume predates `polymkt_test`, create that database explicitly before testing.

- [ ] **Step 3: Run the complete test suite**

Run: `.venv/bin/pytest -v`

Expected: all tests PASS with zero failures.

- [ ] **Step 4: Inspect repository state and diff**

Run: `git status --short && git diff --check && git diff main...HEAD --stat`

Expected: no whitespace errors; only Phase 2 design, plan, model, scoring, tests, scheduler, `.gitignore`, and README changes.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md
git commit -m "docs: mark smart money scoring complete"
```

- [ ] **Step 6: Re-run full verification after the final commit**

Run: `.venv/bin/pytest -v && git diff --check main...HEAD`

Expected: all tests PASS and the diff check exits 0.

- [ ] **Step 7: Publish for review**

Push the feature branch and open a pull request against `main` following `WORKFLOW.md`. Do not merge it.
