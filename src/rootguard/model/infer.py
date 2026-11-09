"""Scoring inference for Root.sh.

One function, :func:`score_command`, is the production scoring service.  The
daemon and CLI both call it, so feature extraction, authorization and logging
cannot drift apart.  Any malformed input, missing model or unexpected model
output raises :class:`ScoringError`; the caller must turn that into ``block``.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from rootguard import __version__
from rootguard.authz import evaluate_authz
from rootguard.categories import classify_action
from rootguard.config import DB_URL, MAX_TEXT_LENGTH, MODEL_PATH
from rootguard.db.models import SOURCES, log_decision
from rootguard.features import extract_features
from rootguard.intent import classify_intent


class ScoringError(RuntimeError):
    """Raised when the scoring service cannot produce a trustworthy result."""


@lru_cache(maxsize=4)
def _load_model_cached(path: str, mtime_ns: int) -> Any:
    del mtime_ns  # part of the cache key, not used by the loader
    return joblib.load(path)


def load_model(model_path: str | Path | None = None) -> Any:
    """Load the model, caching it until the file changes."""
    path = Path(model_path) if model_path is not None else MODEL_PATH
    if not path.exists():
        raise ScoringError(f"model not found at {path}")
    try:
        return _load_model_cached(str(path), path.stat().st_mtime_ns)
    except Exception as exc:  # pragma: no cover - corrupt model is environment-specific
        raise ScoringError(f"could not load model at {path}: {exc}") from exc


def _predict_risk(model: Any, vector: list[list[float]]) -> float:
    try:
        probabilities = model.predict_proba(vector)
        risk = float(probabilities[0][1])
    except Exception as exc:
        raise ScoringError(f"model prediction failed: {exc}") from exc
    if not math.isfinite(risk) or not 0.0 <= risk <= 1.0:
        raise ScoringError(f"model returned an invalid risk score: {risk!r}")
    return risk


def _validate_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ScoringError(f"{field} must be a string")
    if not value.strip():
        raise ScoringError(f"{field} must not be empty")
    if len(value) > MAX_TEXT_LENGTH:
        raise ScoringError(f"{field} exceeds the maximum length of {MAX_TEXT_LENGTH}")
    return value


def _reason(
    *,
    authz_reason: str,
    source: str,
    action_class: str,
    intent_match: int,
    features: dict[str, int | float],
    catastrophic_reason: str | None,
) -> str:
    parts = [authz_reason]
    if catastrophic_reason:
        parts.append(f"catastrophic action: {catastrophic_reason}")
    if source != "user_direct":
        parts.append(f"instruction from {source}, not user_direct")
    if intent_match == 0:
        parts.append(f"{action_class} does not match the requested intent")
    if features["reversibility"] == 1:
        parts.append("irreversible action")
    if features["scope"] == 2:
        parts.append("system-wide scope")
    if features["privilege"] == 1:
        parts.append("privileged action")
    return "; ".join(dict.fromkeys(parts))


def score_command(
    user_request: str,
    proposed_action: str,
    source: str,
    *,
    model_path: str | Path | None = None,
    database_url: str = DB_URL,
    save_to_db: bool = True,
    repeat_count: int = 0,
    label: str | None = None,
) -> dict[str, Any]:
    """Score one proposed action.

    Returns a dictionary with ``decision``, ``risk_score``, ``reason``,
    ``features``, ``intent_class`` and ``action_class``.  Raises
    :class:`ScoringError` rather than returning an unsafe fallback.
    """
    request = _validate_text(user_request, "user_request")
    action_text = _validate_text(proposed_action, "proposed_action")
    if source not in SOURCES:
        raise ScoringError(f"invalid source {source!r}; expected one of {', '.join(SOURCES)}")

    model = load_model(model_path)
    intent_class = classify_intent(request)
    action = classify_action(action_text)
    features = extract_features(request, action_text, source, intent_class)

    vector = [[
        float(features["source_trusted"]),
        float(features["intent_match"]),
        float(features["target_in_request"]),
        float(features["reversibility"]),
        float(features["scope"]),
        float(features["privilege"]),
    ]]
    risk_score = _predict_risk(model, vector)

    authz = evaluate_authz(
        risk_score=risk_score,
        action_class=action.action_class,
        reversibility=action.reversibility,
        scope=action.scope,
        privilege=action.privilege,
        intent_match=int(features["intent_match"]),
        source_trusted=int(features["source_trusted"]),
        target_in_request=float(features["target_in_request"]),
        catastrophic=action.catastrophic,
        catastrophic_reason=action.catastrophic_reason,
        repeat_count=repeat_count,
    )
    reason = _reason(
        authz_reason=authz.reason,
        source=source,
        action_class=action.action_class,
        intent_match=int(features["intent_match"]),
        features=features,
        catastrophic_reason=action.catastrophic_reason,
    )

    result: dict[str, Any] = {
        "decision": authz.decision,
        "risk_score": risk_score,
        "reason": reason,
        "features": features,
        "intent_class": intent_class,
        "action_class": action.action_class,
        "authz_stage": authz.stage,
        "model_version": __version__,
    }

    if save_to_db:
        try:
            row = log_decision(
                decision=authz.decision,
                risk_score=risk_score,
                user_request=request,
                proposed_action=action_text,
                source=source,
                action_class=action.action_class,
                intent_class=intent_class,
                label=label,
                source_trusted=int(features["source_trusted"]),
                intent_match=int(features["intent_match"]),
                target_in_request=float(features["target_in_request"]),
                reversibility=int(features["reversibility"]),
                scope=int(features["scope"]),
                privilege=int(features["privilege"]),
                reason=reason,
                database_url=database_url,
            )
        except Exception as exc:
            # A decision that cannot be logged is not allowed to run.
            raise ScoringError(f"decision could not be logged: {exc}") from exc
        result["decision_id"] = row.id

    return result
