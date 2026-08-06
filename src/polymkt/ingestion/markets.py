import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from polymkt.db.models import Market

PAGE_SIZE = 100


def fetch_all_active_markets(client) -> list[dict]:
    markets: list[dict] = []
    offset = 0
    while True:
        page = client.get_active_markets(limit=PAGE_SIZE, offset=offset)
        markets.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return markets


def upsert_market(session: Session, raw_market: dict) -> Market:
    token_ids = json.loads(raw_market.get("clobTokenIds") or "[]")
    token_id_yes = token_ids[0] if len(token_ids) > 0 else None
    token_id_no = token_ids[1] if len(token_ids) > 1 else None

    market = session.scalar(select(Market).where(Market.condition_id == raw_market["conditionId"]))
    if market is None:
        market = Market(condition_id=raw_market["conditionId"])
        session.add(market)

    market.slug = raw_market["slug"]
    market.question = raw_market["question"]
    market.category = raw_market.get("category")
    market.active = bool(raw_market.get("active", True))
    market.token_id_yes = token_id_yes
    market.token_id_no = token_id_no
    return market


def ingest_markets(session: Session, client) -> int:
    raw_markets = fetch_all_active_markets(client)
    for raw_market in raw_markets:
        upsert_market(session, raw_market)
    session.flush()
    return len(raw_markets)
