from datetime import datetime, timezone

from polymkt.db.models import Market, MarketPriceSnapshot, Position, TraderRanking


def test_market_round_trip(db_session):
    db_session.add(
        Market(
            condition_id="0xabc",
            slug="test-market",
            question="Will X happen?",
            category="Politics",
            active=True,
            token_id_yes="111",
            token_id_no="222",
        )
    )
    db_session.flush()

    market = db_session.query(Market).filter_by(condition_id="0xabc").one()
    assert market.slug == "test-market"
    assert market.token_id_yes == "111"


def test_trader_ranking_unique_constraint(db_session):
    captured_at = datetime.now(timezone.utc)
    db_session.add(
        TraderRanking(
            wallet_address="0x111",
            rank=1,
            pnl=1000.0,
            volume=5000.0,
            time_period="ALL",
            category="OVERALL",
            captured_at=captured_at,
        )
    )
    db_session.flush()

    ranking = db_session.query(TraderRanking).one()
    assert ranking.wallet_address == "0x111"


def test_position_and_price_snapshot_round_trip(db_session):
    captured_at = datetime.now(timezone.utc)
    db_session.add(
        Position(
            wallet_address="0x111",
            condition_id="0xabc",
            outcome="Yes",
            size=1200.0,
            value_usd=540.0,
            captured_at=captured_at,
        )
    )
    db_session.add(
        MarketPriceSnapshot(
            condition_id="0xabc",
            outcome="Yes",
            price=0.45,
            best_bid=0.44,
            best_ask=0.46,
            captured_at=captured_at,
        )
    )
    db_session.flush()

    assert db_session.query(Position).count() == 1
    assert db_session.query(MarketPriceSnapshot).count() == 1
