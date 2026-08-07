from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import Position, PositionIngestionBatch
from polymkt.db.queries import latest_trader_cohort


class MissingLeaderboardCohortError(RuntimeError):
    """Raised when positions cannot be tied to a leaderboard snapshot."""


def ingest_positions_for_top_traders(
    session: Session, client, *, top_n: int, category: str, time_period: str
) -> int:
    leaderboard_captured_at, wallet_addresses = latest_trader_cohort(
        session, top_n=top_n, category=category, time_period=time_period
    )
    if leaderboard_captured_at is None:
        raise MissingLeaderboardCohortError(
            f"No leaderboard cohort exists for {category}/{time_period}"
        )
    captured_at = datetime.now(timezone.utc)
    session.add(
        PositionIngestionBatch(
            captured_at=captured_at,
            leaderboard_captured_at=leaderboard_captured_at,
            category=category,
            time_period=time_period,
            top_n=top_n,
        )
    )
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
