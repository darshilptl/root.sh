"""Staged authorization for RootGuard.

Pure functions that decide allow / confirm / block based on risk score.
No side effects — pure input -> output.
"""

from typing import Literal

# Decision thresholds (from AGENTS.md Section 4)
ALLOW_THRESHOLD = 0.3
CONFIRM_THRESHOLD = 0.7


def staged_authz(risk_score: float) -> Literal["allow", "confirm", "block"]:
    """Staged authorization based on risk score.

    Args:
        risk_score: Float between 0.0 and 1.0 (uncalibrated).

    Returns:
        "allow", "confirm", or "block".
    """
    if risk_score < ALLOW_THRESHOLD:
        return "allow"
    elif risk_score <= CONFIRM_THRESHOLD:
        return "confirm"
    else:
        return "block"


def default_deny() -> Literal["block"]:
    """Default deny for any error, missing model, malformed input."""
    return "block"


def is_high_risk(risk_score: float) -> bool:
    """Check if action is high risk (should be blocked)."""
    return risk_score > CONFIRM_THRESHOLD


def is_medium_risk(risk_score: float) -> bool:
    """Check if action is medium risk (should be confirmed)."""
    return ALLOW_THRESHOLD <= risk_score <= CONFIRM_THRESHOLD


def is_low_risk(risk_score: float) -> bool:
    """Check if action is low risk (should be allowed)."""
    return risk_score < ALLOW_THRESHOLD
