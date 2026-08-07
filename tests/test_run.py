from unittest.mock import patch

from polymkt.config import settings
from polymkt.run import build_scheduler, run_position_ingestion, run_smart_money_scoring


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
