"""SQLAlchemy 2 models and logging helpers.

SQLite is opened in WAL mode with foreign keys enabled.  Enum-like columns are
constrained in the database itself, so an invalid value is rejected even if a
caller bypasses the Pydantic layer.

The database stores the six features, the decision and the model score for
every call.  ``Outcome`` records what happened after a decision and ``Run``
records evaluation metadata (dataset hash, split, metrics).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from rootguard.categories import ACTION_CLASSES
from rootguard.config import DB_URL
from rootguard.intent import INTENT_CLASSES

SOURCES: tuple[str, ...] = (
    "user_direct",
    "file_content",
    "web_content",
    "tool_output",
    "agent_internal",
)
DECISIONS: tuple[str, ...] = ("allow", "confirm", "block")
LABELS: tuple[str, ...] = ("safe", "risky")
OUTCOME_RESULTS: tuple[str, ...] = ("success", "failure", "blocked", "not_run", "unknown")


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _enum_check(column: str) -> str:
    return f"{column} IS NULL OR {column} IN ({_quoted(SOURCES)})"


class Base(DeclarativeBase):
    """Declarative base for all Root.sh tables."""


class Decision(Base):
    """One scoring decision from the daemon or the CLI."""

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(f"decision IN ({_quoted(DECISIONS)})", name="ck_decisions_decision"),
        CheckConstraint(f"source IS NULL OR source IN ({_quoted(SOURCES)})", name="ck_decisions_source"),
        CheckConstraint(
            f"action_class IS NULL OR action_class IN ({_quoted(ACTION_CLASSES)})",
            name="ck_decisions_action_class",
        ),
        CheckConstraint(
            f"intent_class IS NULL OR intent_class IN ({_quoted(INTENT_CLASSES)})",
            name="ck_decisions_intent_class",
        ),
        CheckConstraint(f"label IS NULL OR label IN ({_quoted(LABELS)})", name="ck_decisions_label"),
        CheckConstraint("risk_score >= 0.0 AND risk_score <= 1.0", name="ck_decisions_risk"),
        CheckConstraint("source_trusted IS NULL OR source_trusted IN (0, 1)", name="ck_decisions_source_trusted"),
        CheckConstraint("intent_match IS NULL OR intent_match IN (-1, 0, 1)", name="ck_decisions_intent_match"),
        CheckConstraint(
            "target_in_request IS NULL OR (target_in_request >= -1.0 AND target_in_request <= 1.0)",
            name="ck_decisions_target_in_request",
        ),
        CheckConstraint("reversibility IS NULL OR reversibility IN (0, 1)", name="ck_decisions_reversibility"),
        CheckConstraint("scope IS NULL OR scope IN (0, 1, 2)", name="ck_decisions_scope"),
        CheckConstraint("privilege IS NULL OR privilege IN (0, 1)", name="ck_decisions_privilege"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    family_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_request: Mapped[str] = mapped_column(Text, default="")
    proposed_action: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str | None] = mapped_column(String(32), index=True)
    action_class: Mapped[str | None] = mapped_column(String(32), index=True)
    intent_class: Mapped[str | None] = mapped_column(String(32), index=True)
    label: Mapped[str | None] = mapped_column(String(16), index=True)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    source_trusted: Mapped[int | None] = mapped_column(Integer)
    intent_match: Mapped[int | None] = mapped_column(Integer)
    target_in_request: Mapped[float | None] = mapped_column(Float)
    reversibility: Mapped[int | None] = mapped_column(Integer)
    scope: Mapped[int | None] = mapped_column(Integer)
    privilege: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Outcome(Base):
    """What happened after a decision was issued."""

    __tablename__ = "outcomes"
    __table_args__ = (
        CheckConstraint(f"result IN ({_quoted(OUTCOME_RESULTS)})", name="ck_outcomes_result"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Run(Base):
    """Evaluation-run metadata and metrics."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("split IN ('train', 'heldout')", name="ck_runs_split"),
        CheckConstraint("accuracy IS NULL OR (accuracy >= 0.0 AND accuracy <= 1.0)", name="ck_runs_accuracy"),
        CheckConstraint("precision IS NULL OR (precision >= 0.0 AND precision <= 1.0)", name="ck_runs_precision"),
        CheckConstraint("recall IS NULL OR (recall >= 0.0 AND recall <= 1.0)", name="ck_runs_recall"),
        CheckConstraint("f1 IS NULL OR (f1 >= 0.0 AND f1 <= 1.0)", name="ck_runs_f1"),
        CheckConstraint("auc_roc IS NULL OR (auc_roc >= 0.0 AND auc_roc <= 1.0)", name="ck_runs_auc"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    split: Mapped[str] = mapped_column(String(16), index=True)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64))
    families_sha256: Mapped[str | None] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer, default=42)
    n_train: Mapped[int | None] = mapped_column(Integer)
    n_heldout: Mapped[int | None] = mapped_column(Integer)
    accuracy: Mapped[float | None] = mapped_column(Float)
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    f1: Mapped[float | None] = mapped_column(Float)
    auc_roc: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def _on_connect(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """Enable WAL and foreign keys for every SQLite connection."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    except Exception:
        # In-memory SQLite and non-SQLite drivers may not support WAL.  The
        # connection is still usable; callers see the real error if one occurs.
        pass


@lru_cache(maxsize=8)
def get_engine(database_url: str = DB_URL) -> Engine:
    """Create (and cache) an engine for *database_url*."""
    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30}
        if database_url.startswith("sqlite")
        else {},
    )
    event.listen(engine, "connect", _on_connect)
    return engine


def init_db(database_url: str = DB_URL) -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=get_engine(database_url))


def get_session(database_url: str = DB_URL) -> Session:
    """Return a new SQLAlchemy session."""
    factory = sessionmaker(bind=get_engine(database_url), expire_on_commit=False, future=True)
    return factory()


def log_decision(
    *,
    decision: str,
    risk_score: float,
    user_request: str = "",
    proposed_action: str = "",
    source: str | None = None,
    action_class: str | None = None,
    intent_class: str | None = None,
    label: str | None = None,
    family_id: str | None = None,
    run_id: str | None = None,
    source_trusted: int | None = None,
    intent_match: int | None = None,
    target_in_request: float | None = None,
    reversibility: int | None = None,
    scope: int | None = None,
    privilege: int | None = None,
    reason: str = "",
    error: str | None = None,
    database_url: str = DB_URL,
) -> Decision:
    """Persist one decision and return the stored row."""
    init_db(database_url)
    row = Decision(
        id=str(uuid.uuid4()),
        run_id=run_id,
        family_id=family_id,
        user_request=user_request,
        proposed_action=proposed_action,
        source=source,
        action_class=action_class,
        intent_class=intent_class,
        label=label,
        decision=decision,
        risk_score=float(risk_score),
        source_trusted=source_trusted,
        intent_match=intent_match,
        target_in_request=target_in_request,
        reversibility=reversibility,
        scope=scope,
        privilege=privilege,
        reason=reason,
        error=error,
        created_at=utcnow(),
    )
    session = get_session(database_url)
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    finally:
        session.close()


def log_outcome(
    *,
    decision_id: str,
    executed: bool,
    result: str = "unknown",
    notes: str | None = None,
    database_url: str = DB_URL,
) -> Outcome:
    """Record an outcome for an existing decision."""
    init_db(database_url)
    row = Outcome(
        id=str(uuid.uuid4()),
        decision_id=decision_id,
        executed=executed,
        result=result,
        notes=notes,
        created_at=utcnow(),
    )
    session = get_session(database_url)
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    finally:
        session.close()


def log_run(
    *,
    run_id: str,
    model_name: str,
    split: str,
    accuracy: float | None = None,
    precision: float | None = None,
    recall: float | None = None,
    f1: float | None = None,
    auc_roc: float | None = None,
    dataset_sha256: str | None = None,
    families_sha256: str | None = None,
    seed: int = 42,
    n_train: int | None = None,
    n_heldout: int | None = None,
    notes: str | None = None,
    database_url: str = DB_URL,
) -> Run:
    """Persist one evaluation-run row."""
    init_db(database_url)
    row = Run(
        id=run_id,
        model_name=model_name,
        split=split,
        dataset_sha256=dataset_sha256,
        families_sha256=families_sha256,
        seed=seed,
        n_train=n_train,
        n_heldout=n_heldout,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        auc_roc=auc_roc,
        notes=notes,
        created_at=utcnow(),
    )
    session = get_session(database_url)
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    finally:
        session.close()
