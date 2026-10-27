"""Scoring inference for Root.sh.

Loads trained model.pkl and scores a single (user_request, proposed_action, source)
tuple, returning risk score + decision (allow/confirm/block).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src/root.sh/ to path for imports (directory name has a dot)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib

from db.models import Decision, SessionLocal, init_db
from features import extract_features
from intent import classify_intent

MODEL_PATH = Path("src/root.sh/model/model.pkl")
DB_PATH = Path("data/decisions.db")

# Decision thresholds (from AGENTS.md)
ALLOW_THRESHOLD = 0.3
CONFIRM_THRESHOLD = 0.7


def load_model():
    """Load the trained model from disk."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Train first.")
    return joblib.load(MODEL_PATH)


def score_command(
    user_request: str,
    proposed_action: str,
    source: str,
    save_to_db: bool = True,
) -> dict:
    """Score a proposed command and return decision.

    Returns dict with:
        - risk_score: float (0.0 - 1.0)
        - decision: str (allow / confirm / block)
        - features: dict of six features
        - intent_class: str
        - reason: str
    """
    model = load_model()

    # Intent classification
    intent_class = classify_intent(user_request)

    # Feature extraction
    feats = extract_features(user_request, proposed_action, source, intent_class)

    # Build feature vector in correct order
    feature_cols = [
        "source_trusted", "intent_match", "target_in_request",
        "reversibility", "scope", "privilege",
    ]
    X = [[feats[f] for f in feature_cols]]

    # Predict
    risk_score = float(model.predict_proba(X)[0][1])

    # Decision
    if risk_score < ALLOW_THRESHOLD:
        decision = "allow"
    elif risk_score <= CONFIRM_THRESHOLD:
        decision = "confirm"
    else:
        decision = "block"

    # Reasoning
    reasons = []
    if source != "user_direct":
        reasons.append(f"instruction from {source}, not user_direct")
    if feats["intent_match"] == 0:
        reasons.append("action does not match request intent")
    if feats["reversibility"] == 1:
        reasons.append("irreversible action")
    if feats["scope"] == 2:
        reasons.append("system-wide scope")
    if feats["privilege"] == 1:
        reasons.append("privilege escalation (sudo/chmod)")
    if not reasons:
        reasons.append("action matches request, user_direct source")
    reason = "; ".join(reasons)

    result = {
        "risk_score": risk_score,
        "decision": decision,
        "features": feats,
        "intent_class": intent_class,
        "reason": reason,
    }

    # Log to SQLite
    if save_to_db:
        init_db()
        session = SessionLocal()
        try:
            import uuid
            decision_row = Decision(
                id=str(uuid.uuid4()),
                family_id=None,  # Not available at scoring time
                user_request=user_request,
                proposed_action=proposed_action,
                source=source,
                label="risky" if risk_score > 0.5 else "safe",
                decision=decision,
                risk_score=risk_score,
                source_trusted=feats["source_trusted"],
                intent_match=feats["intent_match"],
                target_in_request=feats["target_in_request"],
                reversibility=feats["reversibility"],
                scope=feats["scope"],
                privilege=feats["privilege"],
            )
            session.add(decision_row)
            session.commit()
        finally:
            session.close()

    return result


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("List project files", "ls -la", "user_direct"),
        ("Delete temp files", "rm -rf /tmp/sandbox-old", "user_direct"),
        ("Drop production table", "DROP TABLE production_db;", "agent_internal"),
        ("Export PATH", "export PATH=/tmp/sandbox-bin:$PATH", "file_content"),
    ]
    for req, action, src in test_cases:
        result = score_command(req, action, src, save_to_db=False)
        print(f"Request: {req[:40]}...")
        print(f"  Action: {action[:40]}...")
        print(f"  Source: {src}")
        print(f"  Risk: {result['risk_score']:.3f} | Decision: {result['decision']}")
        print(f"  Reason: {result['reason']}")
        print()
