from polymkt.db.models import Market
from polymkt.ingestion.markets import ingest_markets

RAW_MARKET = {
    "conditionId": "0xabc",
    "slug": "test-market",
    "question": "Will X happen?",
    "category": "Politics",
    "active": True,
    "clobTokenIds": '["111","222"]',
}


class FakeGammaClient:
    def __init__(self, pages: list[list[dict]]) -> None:
        self._pages = pages

    def get_active_markets(self, limit: int, offset: int) -> list[dict]:
        page_index = offset // limit
        if page_index >= len(self._pages):
            return []
        return self._pages[page_index]


def test_ingest_markets_creates_new_market(db_session):
    client = FakeGammaClient(pages=[[RAW_MARKET]])

    count = ingest_markets(db_session, client)

    assert count == 1
    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.token_id_yes == "111"
    assert market.token_id_no == "222"
    assert market.category == "Politics"


def test_ingest_markets_updates_existing_market_instead_of_duplicating(db_session):
    ingest_markets(db_session, FakeGammaClient(pages=[[RAW_MARKET]]))

    updated_market = dict(RAW_MARKET, question="Updated question?")
    ingest_markets(db_session, FakeGammaClient(pages=[[updated_market]]))

    assert db_session.query(Market).count() == 1
    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.question == "Updated question?"
