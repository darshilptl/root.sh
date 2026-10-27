"""RootGuard Daemon — FastAPI + uvicorn.

Exposes POST /score endpoint that receives (user_request, proposed_action, source)
and returns allow / confirm / block with risk score and reason.
"""

from __future__ import annotations

# Add src/root.sh/ to path for sibling imports (directory name has a dot)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from authz import default_deny, staged_authz
from features import extract_features
from intent import classify_intent

app = FastAPI(title="RootGuard Defense Layer", version="0.1.0")


class ScoreRequest(BaseModel):
    user_request: str
    proposed_action: str
    source: str


class ScoreResponse(BaseModel):
    decision: str
    risk_score: float
    reason: str
    features: dict
    intent_class: str


@app.post("/score", response_model=ScoreResponse)
async def score(request: ScoreRequest) -> ScoreResponse:
    """Score a proposed command and return allow / confirm / block decision."""
    try:
        # Intent classification
        intent_class = classify_intent(request.user_request)

        # Feature extraction
        feats = extract_features(
            request.user_request,
            request.proposed_action,
            request.source,
            intent_class,
        )

        # Load model and score
        from model.infer import load_model, score_command

        model = load_model()
        feature_cols = [
            "source_trusted",
            "intent_match",
            "target_in_request",
            "reversibility",
            "scope",
            "privilege",
        ]
        X = [[feats[f] for f in feature_cols]]
        risk_score = float(model.predict_proba(X)[0][1])

        # Staged authorization
        decision = staged_authz(risk_score)

        # Reasoning
        reasons = []
        if request.source != "user_direct":
            reasons.append(f"instruction from {request.source}, not user_direct")
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

        return ScoreResponse(
            decision=decision,
            risk_score=risk_score,
            reason=reason,
            features=feats,
            intent_class=intent_class,
        )

    except Exception as e:
        # Default deny on any error
        decision = default_deny()
        feats = {}
        return ScoreResponse(
            decision=decision,
            risk_score=1.0,
            reason=f"Error: {str(e)}",
            features=feats,
            intent_class="other",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "RootGuard Defense Layer", "version": "0.1.0"}
