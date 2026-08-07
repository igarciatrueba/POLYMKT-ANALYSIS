from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    token_id_yes: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_id_no: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TraderRanking(Base):
    __tablename__ = "trader_rankings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    pnl: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    time_period: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "wallet_address", "time_period", "category", "captured_at",
            name="uq_trader_ranking_snapshot",
        ),
        Index(
            "ix_trader_rankings_cohort_snapshot",
            "category",
            "time_period",
            "captured_at",
            "rank",
        ),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    value_usd: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_positions_snapshot_wallet_market",
            "captured_at",
            "wallet_address",
            "condition_id",
            "outcome",
        ),
    )


class PositionIngestionBatch(Base):
    __tablename__ = "position_ingestion_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), unique=True, nullable=False
    )


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    best_bid: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SmartMoneyScore(Base):
    __tablename__ = "smart_money_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    capital_usd: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    has_coverage: Mapped[bool] = mapped_column(Boolean, nullable=False)
    trader_count: Mapped[int] = mapped_column(nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_smart_money_scores_snapshot_market",
            "captured_at",
            "condition_id",
            "outcome",
        ),
    )
