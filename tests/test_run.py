from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from polymkt.config import settings
from polymkt.db.models import Position, PositionIngestionBatch, SmartMoneyScore, TraderRanking
from polymkt.run import (
    build_scheduler,
    run_initial_ingestion,
    run_position_ingestion,
    run_smart_money_scoring,
)


def test_build_scheduler_registers_all_ingestion_jobs_with_expected_intervals():
    scheduler = build_scheduler()

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {
        "initial_ingestion",
        "market_ingestion",
        "leaderboard_ingestion",
        "position_ingestion",
        "price_ingestion",
    }
    assert jobs["initial_ingestion"].trigger.__class__.__name__ == "DateTrigger"
    assert jobs["market_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["leaderboard_ingestion"].trigger.interval.total_seconds() == 24 * 60 * 60
    assert jobs["position_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["price_ingestion"].trigger.interval.total_seconds() == 3 * 60


def test_run_smart_money_scoring_uses_configured_cohort():
    session = object()
    with (
        patch("polymkt.run.get_session") as get_session,
        patch("polymkt.run.calculate_smart_money_scores", return_value=2) as calculate,
    ):
        get_session.return_value.__enter__.return_value = session

        run_smart_money_scoring()

    calculate.assert_called_once_with(
        session,
        top_n=settings.top_n_traders,
        category=settings.leaderboard_category,
        time_period=settings.leaderboard_time_period,
    )


def test_position_ingestion_scores_after_new_positions_are_flushed():
    session = object()
    call_order = []
    with (
        patch("polymkt.run.DataApiClient") as client_class,
        patch("polymkt.run.get_session") as get_session,
        patch("polymkt.run.ingest_positions_for_top_traders") as ingest,
        patch("polymkt.run.calculate_smart_money_scores") as calculate,
    ):
        client = client_class.return_value
        get_session.return_value.__enter__.return_value = session
        ingest.side_effect = lambda *args, **kwargs: call_order.append("ingest") or 4
        calculate.side_effect = lambda *args, **kwargs: call_order.append("score") or 2

        run_position_ingestion()

    assert call_order == ["ingest", "score"]
    client.close.assert_called_once_with()


def test_initial_ingestion_runs_dependency_order_before_intervals_start():
    call_order = []
    with (
        patch(
            "polymkt.run.run_market_ingestion",
            side_effect=lambda: call_order.append("markets"),
        ),
        patch(
            "polymkt.run.run_leaderboard_ingestion",
            side_effect=lambda: call_order.append("leaderboard"),
        ),
        patch(
            "polymkt.run.run_position_ingestion",
            side_effect=lambda: call_order.append("positions_and_scores"),
        ),
        patch(
            "polymkt.run.run_price_ingestion",
            side_effect=lambda: call_order.append("prices"),
        ),
    ):
        run_initial_ingestion()

    assert call_order == ["markets", "leaderboard", "positions_and_scores", "prices"]


def test_initial_ingestion_stops_dependent_steps_after_retries():
    with (
        patch("polymkt.run.time.sleep"),
        patch("polymkt.run.run_market_ingestion", side_effect=RuntimeError("offline")) as markets,
        patch("polymkt.run.run_leaderboard_ingestion") as leaderboard,
        patch("polymkt.run.run_position_ingestion") as positions,
        patch("polymkt.run.run_price_ingestion") as prices,
    ):
        run_initial_ingestion()

    assert markets.call_count == 3
    leaderboard.assert_not_called()
    positions.assert_not_called()
    prices.assert_not_called()


def test_scoring_failure_rolls_back_position_batch_and_closes_client(engine):
    session_factory = sessionmaker(bind=engine, future=True)
    with session_factory.begin() as session:
        session.add(
            TraderRanking(
                wallet_address="0x111",
                rank=1,
                pnl=100,
                volume=100,
                time_period=settings.leaderboard_time_period,
                category=settings.leaderboard_category,
                captured_at=datetime.now(timezone.utc),
            )
        )

    @contextmanager
    def transactional_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with (
        patch("polymkt.run.DataApiClient") as client_class,
        patch("polymkt.run.get_session", side_effect=transactional_session),
        patch(
            "polymkt.run.calculate_smart_money_scores",
            side_effect=RuntimeError("scoring failed"),
        ),
    ):
        client_class.return_value.get_positions.return_value = []

        with pytest.raises(RuntimeError, match="scoring failed"):
            run_position_ingestion()

    client_class.return_value.close.assert_called_once_with()
    with session_factory() as session:
        assert session.query(Position).count() == 0
        assert session.query(PositionIngestionBatch).count() == 0
        assert session.query(SmartMoneyScore).count() == 0
        session.query(TraderRanking).filter_by(wallet_address="0x111").delete()
        session.commit()
