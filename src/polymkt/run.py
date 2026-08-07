import logging

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
from polymkt.scoring.smart_money import calculate_smart_money_scores

logger = logging.getLogger(__name__)


def run_market_ingestion() -> None:
    client = GammaClient(base_url=settings.gamma_base_url)
    try:
        with get_session() as session:
            count = ingest_markets(session, client)
            logger.info("ingest_markets: wrote %d markets", count)
    finally:
        client.close()


def run_leaderboard_ingestion() -> None:
    client = DataApiClient(base_url=settings.data_api_base_url)
    try:
        with get_session() as session:
            count = ingest_leaderboard(
                session,
                client,
                top_n=settings.top_n_traders,
                category=settings.leaderboard_category,
                time_period=settings.leaderboard_time_period,
            )
            logger.info("ingest_leaderboard: wrote %d trader rankings", count)
    finally:
        client.close()


def run_position_ingestion() -> None:
    client = DataApiClient(base_url=settings.data_api_base_url)
    try:
        with get_session() as session:
            count = ingest_positions_for_top_traders(
                session,
                client,
                top_n=settings.top_n_traders,
                category=settings.leaderboard_category,
                time_period=settings.leaderboard_time_period,
            )
            logger.info("ingest_positions_for_top_traders: wrote %d positions", count)
    finally:
        client.close()


def run_price_ingestion() -> None:
    client = ClobClient(base_url=settings.clob_base_url)
    try:
        with get_session() as session:
            count = ingest_prices(session, client)
            logger.info("ingest_prices: wrote %d snapshots", count)
    finally:
        client.close()


def run_smart_money_scoring() -> None:
    with get_session() as session:
        count = calculate_smart_money_scores(
            session,
            top_n=settings.top_n_traders,
            category=settings.leaderboard_category,
            time_period=settings.leaderboard_time_period,
        )
        logger.info("calculate_smart_money_scores: wrote %d scores", count)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_market_ingestion, "interval", minutes=20, id="market_ingestion")
    scheduler.add_job(run_leaderboard_ingestion, "interval", hours=24, id="leaderboard_ingestion")
    scheduler.add_job(run_position_ingestion, "interval", minutes=20, id="position_ingestion")
    scheduler.add_job(run_price_ingestion, "interval", minutes=3, id="price_ingestion")
    scheduler.add_job(
        run_smart_money_scoring,
        "interval",
        minutes=20,
        id="smart_money_scoring",
    )
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = build_scheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
