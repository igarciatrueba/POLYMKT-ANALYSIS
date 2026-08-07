import logging
import time

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
            score_count = calculate_smart_money_scores(
                session,
                top_n=settings.top_n_traders,
                category=settings.leaderboard_category,
                time_period=settings.leaderboard_time_period,
            )
        logger.info("ingest_positions_for_top_traders: wrote %d positions", count)
        logger.info("calculate_smart_money_scores: wrote %d scores", score_count)
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
    scheduler.add_job(run_initial_ingestion, "date", id="initial_ingestion")
    scheduler.add_job(run_market_ingestion, "interval", minutes=20, id="market_ingestion")
    scheduler.add_job(run_leaderboard_ingestion, "interval", hours=24, id="leaderboard_ingestion")
    scheduler.add_job(run_position_ingestion, "interval", minutes=20, id="position_ingestion")
    scheduler.add_job(run_price_ingestion, "interval", minutes=3, id="price_ingestion")
    return scheduler


def _run_bootstrap_step(step, *, attempts: int = 3) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            step()
            return True
        except Exception:
            logger.exception(
                "initial ingestion step %s failed (%d/%d)",
                getattr(step, "__name__", step.__class__.__name__),
                attempt,
                attempts,
            )
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    return False


def run_initial_ingestion() -> None:
    """Build a coherent first snapshot without endangering scheduler uptime."""
    for step in (
        run_market_ingestion,
        run_leaderboard_ingestion,
        run_position_ingestion,
    ):
        if not _run_bootstrap_step(step):
            return

    # Prices are independent from the scoring dependency chain.
    _run_bootstrap_step(run_price_ingestion)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = build_scheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
