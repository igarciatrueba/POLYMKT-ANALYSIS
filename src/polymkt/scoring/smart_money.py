from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from polymkt.db.models import (
    Market,
    Position,
    PositionIngestionBatch,
    SmartMoneyScore,
)
from polymkt.db.queries import trader_wallets_at
from polymkt.domain import BINARY_OUTCOMES


class MissingScoringSourceError(RuntimeError):
    """Raised when a complete source snapshot is unavailable for scoring."""


def calculate_smart_money_scores(
    session: Session,
    *,
    top_n: int,
    category: str,
    time_period: str,
) -> int:
    if not 1 <= top_n <= 1000:
        raise ValueError("top_n must be between 1 and 1000")

    latest_batch = session.execute(
        select(
            PositionIngestionBatch.id,
            PositionIngestionBatch.captured_at,
            PositionIngestionBatch.leaderboard_captured_at,
        )
        .where(
            PositionIngestionBatch.category == category,
            PositionIngestionBatch.time_period == time_period,
            PositionIngestionBatch.top_n == top_n,
            PositionIngestionBatch.leaderboard_captured_at.is_not(None),
        )
        .order_by(PositionIngestionBatch.captured_at.desc())
        .limit(1)
    ).first()
    if latest_batch is None:
        raise MissingScoringSourceError(
            f"No position batch exists for {category}/{time_period}, top_n={top_n}"
        )
    position_batch_id, latest_positions_at, latest_ranking_at = latest_batch

    wallets = trader_wallets_at(
        session,
        captured_at=latest_ranking_at,
        top_n=top_n,
        category=category,
        time_period=time_period,
    )

    if not wallets:
        raise MissingScoringSourceError(
            f"Leaderboard cohort is empty for {category}/{time_period}, top_n={top_n}"
        )

    session.execute(
        select(PositionIngestionBatch.id)
        .where(PositionIngestionBatch.id == position_batch_id)
        .with_for_update()
    )
    already_scored = session.scalar(
        select(func.count()).select_from(SmartMoneyScore).where(
            SmartMoneyScore.position_ingestion_batch_id == position_batch_id
        )
    )
    if already_scored:
        return 0

    active_condition_ids = session.scalars(
        select(Market.condition_id).where(Market.active.is_(True))
    ).all()

    aggregates: dict[tuple[str, str], tuple[Decimal, int]] = {}
    if wallets and latest_positions_at is not None:
        rows = session.execute(
            select(
                Position.condition_id,
                Position.outcome,
                func.sum(Position.value_usd),
                func.count(func.distinct(Position.wallet_address)),
            )
            .where(
                Position.wallet_address.in_(wallets),
                Position.captured_at == latest_positions_at,
                Position.condition_id.in_(active_condition_ids),
                Position.outcome.in_(BINARY_OUTCOMES),
                Position.value_usd > 0,
            )
            .group_by(Position.condition_id, Position.outcome)
        ).all()
        aggregates = {
            (condition_id, outcome): (Decimal(capital), trader_count)
            for condition_id, outcome, capital, trader_count in rows
        }

    max_capital = max(
        (capital for capital, _ in aggregates.values()),
        default=Decimal("0.00"),
    )
    captured_at = latest_positions_at
    scores = []
    for condition_id in active_condition_ids:
        for outcome in BINARY_OUTCOMES:
            capital, trader_count = aggregates.get(
                (condition_id, outcome),
                (Decimal("0.00"), 0),
            )
            scores.append(
                SmartMoneyScore(
                    condition_id=condition_id,
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
                    position_ingestion_batch_id=position_batch_id,
                )
            )

    session.add_all(scores)
    session.flush()
    return len(scores)
