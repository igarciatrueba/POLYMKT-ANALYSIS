import pytest

from polymkt.db.models import TraderRanking
from polymkt.ingestion.leaderboard import (
    IncompleteLeaderboardSnapshotError,
    ingest_leaderboard,
)


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


def test_ingest_leaderboard_rejects_a_partial_snapshot(db_session):
    page = [
        {"rank": str(i), "proxyWallet": f"0x{i}", "pnl": 100.0, "vol": 10.0}
        for i in range(1, 51)
    ]
    client = FakeDataApiClient(pages=[page, []])

    with pytest.raises(IncompleteLeaderboardSnapshotError, match="50 of 60"):
        ingest_leaderboard(
            db_session,
            client,
            top_n=60,
            category="OVERALL",
            time_period="ALL",
        )

    assert db_session.query(TraderRanking).count() == 0


def test_ingest_leaderboard_rejects_duplicate_or_non_contiguous_ranks(db_session):
    page = [
        {"rank": "1", "proxyWallet": "0x111", "pnl": 100.0, "vol": 10.0},
        {"rank": "1", "proxyWallet": "0x222", "pnl": 90.0, "vol": 9.0},
    ]
    client = FakeDataApiClient(pages=[page])

    with pytest.raises(IncompleteLeaderboardSnapshotError, match="ranks"):
        ingest_leaderboard(
            db_session,
            client,
            top_n=2,
            category="OVERALL",
            time_period="ALL",
        )
