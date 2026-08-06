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
