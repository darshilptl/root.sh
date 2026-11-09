"""Tests for the SQLite decision-logging models."""

from __future__ import annotations

from rootguard.db.models import (
    Decision,
    Outcome,
    Run,
    get_engine,
    log_decision,
    log_outcome,
    log_run,
)


def _memory_db(monkeypatch):
    import rootguard.db.models as db

    engine = get_engine("sqlite:///:memory:")
    monkeypatch.setattr(db, "get_engine", lambda url="sqlite:///:memory:": engine)
    return engine


def test_log_decision_wal_and_checks(monkeypatch):
    engine = _memory_db(monkeypatch)
    row = log_decision(
        decision="block",
        risk_score=0.9,
        user_request="delete foo",
        proposed_action="rm /tmp/foo",
        source="user_direct",
        action_class="delete",
        intent_class="delete",
        label="risky",
        source_trusted=1,
        intent_match=1,
        target_in_request=1.0,
        reversibility=1,
        scope=0,
        privilege=0,
        reason="irreversible delete",
        database_url="sqlite:///:memory:",
    )
    assert row.id is not None
    assert row.decision == "block"


def test_invalid_enum_rejected(monkeypatch):
    from sqlalchemy.exc import IntegrityError

    import rootguard.db.models as db
    engine = _memory_db(monkeypatch)

    from rootguard.db.models import init_db
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = Session()
    try:
        session.add(
            Decision(
                id="x",
                decision="allow",
                risk_score=0.5,
                source="not-a-source",
            )
        )
        session.commit()
        raise AssertionError("invalid source should be rejected")
    except IntegrityError:
        session.rollback()
    finally:
        session.close()


def test_log_run_and_outcome(monkeypatch):
    run = log_run(
        run_id="run_1",
        model_name="lightgbm",
        split="heldout",
        accuracy=0.9,
        precision=0.9,
        recall=0.9,
        f1=0.9,
        auc_roc=0.9,
        database_url="sqlite:///:memory:",
    )
    assert run.id == "run_1"

    decision = log_decision(
        decision="confirm",
        risk_score=0.5,
        source="user_direct",
        action_class="list_read",
        intent_class="list_read",
        database_url="sqlite:///:memory:",
    )
    outcome = log_outcome(
        decision_id=decision.id,
        executed=False,
        result="blocked",
        notes="user declined",
        database_url="sqlite:///:memory:",
    )
    assert outcome.decision_id == decision.id
    assert outcome.result == "blocked"
