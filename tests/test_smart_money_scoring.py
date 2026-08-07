from datetime import datetime, timezone
from decimal import Decimal

import pytest

from polymkt.db.models import (
    Market,
    Position,
    PositionIngestionBatch,
    SmartMoneyScore,
    TraderRanking,
)
from polymkt.scoring.smart_money import calculate_smart_money_scores


def test_aggregates_current_top_trader_capital_for_both_sides(db_session):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        Market(
            condition_id="0xmarket",
            slug="market",
            question="Will it happen?",
            category="Politics",
            active=True,
            token_id_yes="yes-token",
            token_id_no="no-token",
        )
    )
    db_session.add_all(
        [
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=1000,
                volume=5000,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            TraderRanking(
                wallet_address="0xbbb",
                rank=2,
                pnl=900,
                volume=4000,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xmarket",
                outcome="Yes",
                size=100,
                value_usd=Decimal("600.25"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xbbb",
                condition_id="0xmarket",
                outcome="Yes",
                size=200,
                value_usd=Decimal("399.75"),
                captured_at=captured_at,
            ),
        ]
    )
    db_session.flush()

    count = calculate_smart_money_scores(
        db_session,
        top_n=300,
        category="OVERALL",
        time_period="ALL",
    )

    assert count == 2
    scores = {
        row.outcome: row
        for row in db_session.query(SmartMoneyScore)
        .filter_by(condition_id="0xmarket")
        .all()
    }
    assert set(scores) == {"Yes", "No"}
    assert scores["Yes"].capital_usd == Decimal("1000.00")
    assert scores["Yes"].trader_count == 2
    assert scores["Yes"].has_coverage is True
    assert scores["No"].capital_usd == Decimal("0.00")
    assert scores["No"].trader_count == 0
    assert scores["No"].has_coverage is False
    assert scores["Yes"].captured_at == scores["No"].captured_at


def test_uses_only_latest_matching_cohort_and_latest_position_snapshot(db_session):
    old = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        Market(
            condition_id="0xmarket",
            slug="market",
            question="Will it happen?",
            active=True,
            token_id_yes="yes-token",
            token_id_no="no-token",
        )
    )
    db_session.add_all(
        [
            TraderRanking(
                wallet_address="0xold",
                rank=1,
                pnl=9999,
                volume=9999,
                time_period="ALL",
                category="OVERALL",
                captured_at=old,
            ),
            TraderRanking(
                wallet_address="0xcurrent",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=current,
            ),
            Position(
                wallet_address="0xold",
                condition_id="0xmarket",
                outcome="Yes",
                size=1000,
                value_usd=Decimal("9000.00"),
                captured_at=old,
            ),
            Position(
                wallet_address="0xcurrent",
                condition_id="0xmarket",
                outcome="Yes",
                size=10,
                value_usd=Decimal("125.00"),
                captured_at=old,
            ),
            Position(
                wallet_address="0xcurrent",
                condition_id="0xmarket",
                outcome="Yes",
                size=20,
                value_usd=Decimal("250.00"),
                captured_at=current,
            ),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session,
        top_n=1,
        category="OVERALL",
        time_period="ALL",
    )

    yes_score = db_session.query(SmartMoneyScore).filter_by(outcome="Yes").one()
    assert yes_score.capital_usd == Decimal("250.00")
    assert yes_score.trader_count == 1


def test_scores_only_known_active_markets(db_session):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xactive",
                slug="active",
                question="Active?",
                active=True,
            ),
            Market(
                condition_id="0xinactive",
                slug="inactive",
                question="Inactive?",
                active=False,
            ),
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xinactive",
                outcome="Yes",
                size=10,
                value_usd=Decimal("500.00"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xunknown",
                outcome="Yes",
                size=10,
                value_usd=Decimal("700.00"),
                captured_at=captured_at,
            ),
        ]
    )
    db_session.flush()

    count = calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    assert count == 2
    assert {
        row.condition_id for row in db_session.query(SmartMoneyScore).all()
    } == {"0xactive"}


def test_requires_exact_yes_and_no_outcome_literals(db_session):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xmarket",
                slug="market",
                question="Will it happen?",
                active=True,
            ),
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xmarket",
                outcome="yes",
                size=10,
                value_usd=Decimal("500.00"),
                captured_at=captured_at,
            ),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    scores = db_session.query(SmartMoneyScore).all()
    assert {row.outcome for row in scores} == {"Yes", "No"}
    assert all(row.has_coverage is False for row in scores)
    assert all(row.capital_usd == Decimal("0.00") for row in scores)


def test_normalizes_capital_against_zero_and_batch_maximum(db_session):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xlarge",
                slug="large",
                question="Large?",
                active=True,
            ),
            Market(
                condition_id="0xsmall",
                slug="small",
                question="Small?",
                active=True,
            ),
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xlarge",
                outcome="Yes",
                size=100,
                value_usd=Decimal("500000.00"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xsmall",
                outcome="Yes",
                size=1,
                value_usd=Decimal("50.00"),
                captured_at=captured_at,
            ),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    yes_scores = {
        row.condition_id: row.score
        for row in db_session.query(SmartMoneyScore).filter_by(outcome="Yes").all()
    }
    assert yes_scores == {
        "0xlarge": Decimal("100.00"),
        "0xsmall": Decimal("0.01"),
    }


def test_invalid_positions_do_not_contaminate_normalization_maximum(db_session):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xvalid",
                slug="valid",
                question="Valid?",
                active=True,
            ),
            Market(
                condition_id="0xinactive",
                slug="inactive",
                question="Inactive?",
                active=False,
            ),
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xvalid",
                outcome="Yes",
                size=10,
                value_usd=Decimal("100.00"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xinactive",
                outcome="Yes",
                size=10,
                value_usd=Decimal("1000.00"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xunknown",
                outcome="Yes",
                size=10,
                value_usd=Decimal("2000.00"),
                captured_at=captured_at,
            ),
            Position(
                wallet_address="0xaaa",
                condition_id="0xvalid",
                outcome="yes",
                size=10,
                value_usd=Decimal("3000.00"),
                captured_at=captured_at,
            ),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    valid_yes = db_session.query(SmartMoneyScore).filter_by(
        condition_id="0xvalid", outcome="Yes"
    ).one()
    assert valid_yes.capital_usd == Decimal("100.00")
    assert valid_yes.score == Decimal("100.00")


@pytest.mark.parametrize("missing_source", ["rankings", "positions"])
def test_persists_zero_coverage_when_a_source_snapshot_is_missing(
    db_session, missing_source
):
    captured_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        Market(
            condition_id="0xmarket",
            slug="market",
            question="Will it happen?",
            active=True,
        )
    )
    if missing_source == "rankings":
        db_session.add(
            Position(
                wallet_address="0xaaa",
                condition_id="0xmarket",
                outcome="Yes",
                size=10,
                value_usd=Decimal("500.00"),
                captured_at=captured_at,
            )
        )
    else:
        db_session.add(
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=captured_at,
            )
        )
    db_session.flush()

    count = calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    assert count == 2
    scores = db_session.query(SmartMoneyScore).all()
    assert all(row.capital_usd == Decimal("0.00") for row in scores)
    assert all(row.score == Decimal("0.00") for row in scores)
    assert all(row.has_coverage is False for row in scores)
    assert all(row.trader_count == 0 for row in scores)


def test_latest_empty_position_batch_clears_stale_coverage(db_session):
    old = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xmarket",
                slug="market",
                question="Will it happen?",
                active=True,
            ),
            TraderRanking(
                wallet_address="0xaaa",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=current,
            ),
            PositionIngestionBatch(captured_at=old),
            Position(
                wallet_address="0xaaa",
                condition_id="0xmarket",
                outcome="Yes",
                size=10,
                value_usd=Decimal("500.00"),
                captured_at=old,
            ),
            PositionIngestionBatch(captured_at=current),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    scores = db_session.query(SmartMoneyScore).all()
    assert all(row.capital_usd == Decimal("0.00") for row in scores)
    assert all(row.score == Decimal("0.00") for row in scores)
    assert all(row.has_coverage is False for row in scores)


def test_position_batch_keeps_the_leaderboard_cohort_used_for_ingestion(db_session):
    old_ranking_at = datetime(2026, 8, 6, 8, 0, tzinfo=timezone.utc)
    position_batch_at = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    new_ranking_at = datetime(2026, 8, 7, 12, 1, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                condition_id="0xmarket",
                slug="market",
                question="Will it happen?",
                active=True,
            ),
            TraderRanking(
                wallet_address="0xold-cohort",
                rank=1,
                pnl=100,
                volume=100,
                time_period="ALL",
                category="OVERALL",
                captured_at=old_ranking_at,
            ),
            PositionIngestionBatch(
                captured_at=position_batch_at,
                leaderboard_captured_at=old_ranking_at,
            ),
            Position(
                wallet_address="0xold-cohort",
                condition_id="0xmarket",
                outcome="Yes",
                size=10,
                value_usd=Decimal("500.00"),
                captured_at=position_batch_at,
            ),
            TraderRanking(
                wallet_address="0xnew-cohort",
                rank=1,
                pnl=200,
                volume=200,
                time_period="ALL",
                category="OVERALL",
                captured_at=new_ranking_at,
            ),
        ]
    )
    db_session.flush()

    calculate_smart_money_scores(
        db_session, top_n=300, category="OVERALL", time_period="ALL"
    )

    yes_score = db_session.query(SmartMoneyScore).filter_by(outcome="Yes").one()
    assert yes_score.capital_usd == Decimal("500.00")
    assert yes_score.score == Decimal("100.00")
