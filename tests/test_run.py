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
