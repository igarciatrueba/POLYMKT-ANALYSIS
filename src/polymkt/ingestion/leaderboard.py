from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import TraderRanking

PAGE_SIZE = 50


def fetch_top_traders(client, *, top_n: int, category: str, time_period: str) -> list[dict]:
    traders: list[dict] = []
    offset = 0
    while len(traders) < top_n:
        page = client.get_leaderboard(
            category=category,
            time_period=time_period,
            order_by="PNL",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not page:
            break
        traders.extend(page)
        offset += PAGE_SIZE
    return traders[:top_n]


def ingest_leaderboard(session: Session, client, *, top_n: int, category: str, time_period: str) -> int:
    traders = fetch_top_traders(client, top_n=top_n, category=category, time_period=time_period)
    captured_at = datetime.now(timezone.utc)

    for trader in traders:
        session.add(
            TraderRanking(
                wallet_address=trader["proxyWallet"],
                rank=int(trader["rank"]),
                pnl=trader["pnl"],
                volume=trader["vol"],
                time_period=time_period,
                category=category,
                captured_at=captured_at,
            )
        )
    session.flush()
    return len(traders)
