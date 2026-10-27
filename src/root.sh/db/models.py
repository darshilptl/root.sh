"""SQLAlchemy 2 models for SQLite decision logging.

Stores scoring decisions, outcomes, and run metadata for Root.sh.
Per AGENTS.md Rule 12: report only results from eval runs stored in the DB.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = "data/decisions.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Decision(Base):
    """A single scoring decision from the /score endpoint."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_request: Mapped[str] = mapped_column(String(512), index=True)
    proposed_action: Mapped[str] = mapped_column(String(512), index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(16), index=True)  # safe / risky
    decision: Mapped[str] = mapped_column(String(16), index=True)  # allow / confirm / block
    risk_score: Mapped[float] = mapped_column(Float)
    source_trusted: Mapped[int] = mapped_column(Integer)
    intent_match: Mapped[int] = mapped_column(Integer)
    target_in_request: Mapped[float] = mapped_column(Float)
    reversibility: Mapped[int] = mapped_column(Integer)
    scope: Mapped[int] = mapped_column(Integer)
    privilege: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Run(Base):
    """A single eval run (train or heldout evaluation)."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    split: Mapped[str] = mapped_column(String(16), index=True)  # train / heldout
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    auc_roc: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a new database session."""
    return SessionLocal()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
