from polymkt.db.models import Market, MarketPriceSnapshot
from polymkt.ingestion.prices import ingest_prices


class FakeClobClient:
    def __init__(self, books: list[dict]) -> None:
        self._books = books

    def get_order_books(self, token_ids: list[str]) -> list[dict]:
        return [book for book in self._books if book["asset_id"] in token_ids]


def _add_test_market(db_session) -> None:
    db_session.add(
        Market(
            condition_id="0xabc",
            slug="test-market",
            question="Will X happen?",
            category="Politics",
            active=True,
            token_id_yes="111",
            token_id_no="222",
        )
    )
    db_session.flush()


def test_ingest_prices_stores_snapshot_from_order_book(db_session):
    _add_test_market(db_session)
    books = [
        {"asset_id": "111", "bids": [{"price": "0.40", "size": "10"}], "asks": [{"price": "0.44", "size": "10"}]},
        {"asset_id": "222", "bids": [{"price": "0.55", "size": "10"}], "asks": [{"price": "0.59", "size": "10"}]},
    ]
    client = FakeClobClient(books)

    count = ingest_prices(db_session, client)

    assert count == 2
    yes_snapshot = db_session.query(MarketPriceSnapshot).filter_by(condition_id="0xabc", outcome="Yes").one()
    assert float(yes_snapshot.price) == 0.42
    assert float(yes_snapshot.best_bid) == 0.40
    assert float(yes_snapshot.best_ask) == 0.44


def test_ingest_prices_skips_outcome_with_no_order_book(db_session):
    _add_test_market(db_session)
    client = FakeClobClient(books=[])

    count = ingest_prices(db_session, client)

    assert count == 0
    assert db_session.query(MarketPriceSnapshot).count() == 0
