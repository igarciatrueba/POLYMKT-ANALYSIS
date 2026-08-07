from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from polymkt.db.models import Market, Position, SmartMoneyScore, TraderRanking


def calculate_smart_money_scores(
    session: Session,
    *,
    top_n: int,
    category: str,
    time_period: str,
) -> int:
    latest_ranking_at = session.scalar(
        select(func.max(TraderRanking.captured_at)).where(
            TraderRanking.category == category,
            TraderRanking.time_period == time_period,
        )
    )
    wallets = session.scalars(
        select(TraderRanking.wallet_address)
        .where(
            TraderRanking.category == category,
            TraderRanking.time_period == time_period,
            TraderRanking.captured_at == latest_ranking_at,
        )
        .order_by(TraderRanking.rank)
        .limit(top_n)
    ).all()

    aggregates: dict[tuple[str, str], tuple[Decimal, int]] = {}
    latest_positions_at = session.scalar(select(func.max(Position.captured_at)))
    if wallets and latest_positions_at is not None:
        rows = session.execute(
            select(
                Position.condition_id,
                Position.outcome,
                func.sum(Position.value_usd),
                func.count(func.distinct(Position.wallet_address)),
            )
            .join(Market, Market.condition_id == Position.condition_id)
            .where(
                Position.wallet_address.in_(wallets),
                Position.captured_at == latest_positions_at,
                Position.outcome.in_(("Yes", "No")),
                Market.active.is_(True),
            )
            .group_by(Position.condition_id, Position.outcome)
        ).all()
        aggregates = {
            (condition_id, outcome): (Decimal(capital), trader_count)
            for condition_id, outcome, capital, trader_count in rows
        }

    markets = session.scalars(select(Market).where(Market.active.is_(True))).all()
    max_capital = max(
        (capital for capital, _ in aggregates.values()),
        default=Decimal("0.00"),
    )
    captured_at = datetime.now(timezone.utc)
    scores = []
    for market in markets:
        for outcome in ("Yes", "No"):
            capital, trader_count = aggregates.get(
                (market.condition_id, outcome),
                (Decimal("0.00"), 0),
            )
            scores.append(
                SmartMoneyScore(
                    condition_id=market.condition_id,
                    outcome=outcome,
                    capital_usd=capital,
                    score=(
                        ((capital / max_capital) * Decimal("100")).quantize(
                            Decimal("0.01")
                        )
                        if max_capital > 0
                        else Decimal("0.00")
                    ),
                    has_coverage=capital > 0,
                    trader_count=trader_count,
                    captured_at=captured_at,
                )
            )

    session.add_all(scores)
    session.flush()
    return len(scores)
