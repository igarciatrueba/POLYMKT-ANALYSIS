from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import TraderRanking

PAGE_SIZE = 50


class IncompleteLeaderboardSnapshotError(RuntimeError):
    """Raised when the requested cohort cannot be validated as complete."""


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
    cohort = traders[:top_n]
    if len(cohort) != top_n:
        raise IncompleteLeaderboardSnapshotError(
            f"Leaderboard returned {len(cohort)} of {top_n} requested traders"
        )

    ranks = [int(trader["rank"]) for trader in cohort]
    wallets = [trader["proxyWallet"] for trader in cohort]
    if ranks != list(range(1, top_n + 1)) or len(set(wallets)) != top_n:
        raise IncompleteLeaderboardSnapshotError(
            "Leaderboard ranks or wallet addresses are not a complete unique cohort"
        )
    return cohort


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
