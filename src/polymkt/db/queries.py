from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from polymkt.db.models import TraderRanking


def trader_wallets_at(
    session: Session,
    *,
    captured_at: datetime,
    top_n: int,
    category: str,
    time_period: str,
) -> list[str]:
    return list(
        session.scalars(
            select(TraderRanking.wallet_address)
            .where(
                TraderRanking.category == category,
                TraderRanking.time_period == time_period,
                TraderRanking.captured_at == captured_at,
            )
            .order_by(TraderRanking.rank)
            .limit(top_n)
        ).all()
    )


def latest_trader_cohort(
    session: Session, *, top_n: int, category: str, time_period: str
) -> tuple[datetime | None, list[str]]:
    captured_at = session.scalar(
        select(func.max(TraderRanking.captured_at)).where(
            TraderRanking.category == category,
            TraderRanking.time_period == time_period,
        )
    )
    if captured_at is None:
        return None, []
    return captured_at, trader_wallets_at(
        session,
        captured_at=captured_at,
        top_n=top_n,
        category=category,
        time_period=time_period,
    )
