from datetime import datetime, timezone

from sqlalchemy.orm import Session

from polymkt.db.models import Position, TraderRanking


def ingest_positions_for_top_traders(session: Session, client) -> int:
    wallet_addresses = [row[0] for row in session.query(TraderRanking.wallet_address).distinct().all()]
    captured_at = datetime.now(timezone.utc)
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
