from datetime import datetime, timezone

from polymkt.db.models import Position, TraderRanking
from polymkt.ingestion.positions import ingest_positions_for_top_traders


class FakeDataApiClient:
    def __init__(self, positions_by_wallet: dict[str, list[dict]]) -> None:
        self._positions_by_wallet = positions_by_wallet

    def get_positions(self, wallet_address: str, **kwargs) -> list[dict]:
        return self._positions_by_wallet.get(wallet_address, [])


def test_ingest_positions_for_top_traders_stores_positions_for_known_wallets(db_session):
    db_session.add(
        TraderRanking(
            wallet_address="0x111",
            rank=1,
            pnl=500000.0,
            volume=2000000.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    raw_position = {"conditionId": "0xabc", "outcome": "Yes", "size": 1200.0, "currentValue": 540.0}
    client = FakeDataApiClient(positions_by_wallet={"0x111": [raw_position]})

    count = ingest_positions_for_top_traders(db_session, client)

    assert count == 1
    position = db_session.query(Position).one()
    assert position.wallet_address == "0x111"
    assert position.condition_id == "0xabc"


def test_ingest_positions_skips_wallets_with_no_positions(db_session):
    db_session.add(
        TraderRanking(
            wallet_address="0x222",
            rank=2,
            pnl=100.0,
            volume=100.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    client = FakeDataApiClient(positions_by_wallet={})

    count = ingest_positions_for_top_traders(db_session, client)

    assert count == 0
    assert db_session.query(Position).count() == 0
