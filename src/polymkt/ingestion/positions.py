from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from polymkt.db.models import Position, PositionIngestionBatch, TraderRanking


def _latest_top_trader_wallets(
    session: Session, *, top_n: int, category: str, time_period: str
) -> list[str]:
    latest_captured_at = (
        session.query(func.max(TraderRanking.captured_at))
        .filter(
            TraderRanking.category == category,
            TraderRanking.time_period == time_period,
        )
        .scalar()
    )
    if latest_captured_at is None:
        return []

    rows = (
        session.query(TraderRanking.wallet_address)
        .filter(
            TraderRanking.category == category,
            TraderRanking.time_period == time_period,
            TraderRanking.captured_at == latest_captured_at,
        )
        .order_by(TraderRanking.rank)
        .limit(top_n)
        .all()
    )
    return [row[0] for row in rows]


def ingest_positions_for_top_traders(
    session: Session, client, *, top_n: int, category: str, time_period: str
) -> int:
    wallet_addresses = _latest_top_trader_wallets(
        session, top_n=top_n, category=category, time_period=time_period
    )
    captured_at = datetime.now(timezone.utc)
    session.add(PositionIngestionBatch(captured_at=captured_at))
    total = 0

    for wallet_address in wallet_addresses:
        raw_positions = client.get_positions(wallet_address)
        for raw_position in raw_positions:
            session.add(
                Position(
                    wallet_address=wallet_address,
                    condition_id=raw_position["conditionId"],
                    outcome=raw_position["outcome"],
                    size=raw_position["size"],
                    value_usd=raw_position["currentValue"],
                    captured_at=captured_at,
                )
            )
            total += 1

    session.flush()
    return total
