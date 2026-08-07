from unittest.mock import patch

from polymkt.config import settings
from polymkt.run import build_scheduler, run_smart_money_scoring


def test_build_scheduler_registers_all_ingestion_jobs_with_expected_intervals():
    scheduler = build_scheduler()

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {
        "market_ingestion",
        "leaderboard_ingestion",
        "position_ingestion",
        "price_ingestion",
        "smart_money_scoring",
    }
    assert jobs["market_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["leaderboard_ingestion"].trigger.interval.total_seconds() == 24 * 60 * 60
    assert jobs["position_ingestion"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["price_ingestion"].trigger.interval.total_seconds() == 3 * 60
    assert jobs["smart_money_scoring"].trigger.interval.total_seconds() == 20 * 60


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
