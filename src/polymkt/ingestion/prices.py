from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import Market, MarketPriceSnapshot

BATCH_SIZE = 500


def _best_bid(book: dict) -> float | None:
    bids = book.get("bids") or []
    if not bids:
        return None
    return max(float(level["price"]) for level in bids)


def _best_ask(book: dict) -> float | None:
    asks = book.get("asks") or []
    if not asks:
        return None
    return min(float(level["price"]) for level in asks)


def ingest_prices(session: Session, client) -> int:
    markets = session.query(Market).filter(Market.active.is_(True)).all()

    token_id_to_market_outcome: dict[str, tuple[str, str]] = {}
    for market in markets:
        if market.token_id_yes:
            token_id_to_market_outcome[market.token_id_yes] = (market.condition_id, "Yes")
        if market.token_id_no:
            token_id_to_market_outcome[market.token_id_no] = (market.condition_id, "No")

    token_ids = list(token_id_to_market_outcome.keys())
    if not token_ids:
        return 0

    captured_at = datetime.now(timezone.utc)
    total = 0

    for batch_start in range(0, len(token_ids), BATCH_SIZE):
        batch = token_ids[batch_start : batch_start + BATCH_SIZE]
        books = client.get_order_books(batch)

        for book in books:
            condition_id, outcome = token_id_to_market_outcome[book["asset_id"]]
            best_bid = _best_bid(book)
            best_ask = _best_ask(book)
            if best_bid is None or best_ask is None:
                continue

            session.add(
                MarketPriceSnapshot(
                    condition_id=condition_id,
                    outcome=outcome,
                    price=(best_bid + best_ask) / 2,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    captured_at=captured_at,
                )
            )
            total += 1

    session.flush()
    return total
