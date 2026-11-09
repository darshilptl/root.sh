"""Staged authorization for the Root.sh defense layer.

The learned score is only one input.  Authorization is a sequence of pure
checks -- safety floor, source/intent authorization, impact ceiling, repeat
detection and finally the score thresholds -- and the most restrictive result
wins.  Every function here is deterministic and side-effect free.

Production callers should use :func:`evaluate_authz`.  :func:`staged_authz` is
kept as a small compatibility wrapper for callers that only have a score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from rootguard.categories import ACTION_CLASSES

Decision = Literal["allow", "confirm", "block"]

ALLOW_THRESHOLD = 0.3
CONFIRM_THRESHOLD = 0.7

#: Classes where an action can destroy state even when it is technically
#: "reversible" in the abstract.
DESTRUCTIVE_CLASSES = frozenset({"delete", "database_change", "permission_change", "process_control"})

#: Classes that modify persistent state.
STATEFUL_CLASSES = frozenset(
    {"delete", "database_change", "permission_change", "process_control", "install", "modify_file"}
)


@dataclass(frozen=True)
class AuthzDecision:
    """Result of staged authorization."""

    decision: Decision
    reason: str
    stage: str


def score_decision(risk_score: float) -> Decision:
    """Map an uncalibrated risk score to a decision.

    ``score < 0.3`` allow; ``0.3 <= score <= 0.7`` confirm; ``score > 0.7``
    block.  Non-finite or out-of-range scores are blocked by the caller.
    """
    if risk_score < ALLOW_THRESHOLD:
        return "allow"
    if risk_score <= CONFIRM_THRESHOLD:
        return "confirm"
    return "block"


def default_deny(reason: str = "default deny") -> AuthzDecision:
    """Return the mandatory fallback decision for errors or unknown input."""
    return AuthzDecision(decision="block", reason=reason, stage="default_deny")


def _validate(
    *,
    risk_score: float,
    action_class: str,
    reversibility: int,
    scope: int,
    privilege: int,
    intent_match: int,
    source_trusted: int,
    target_in_request: float,
    repeat_count: int,
) -> str | None:
    if not math.isfinite(risk_score) or not 0.0 <= risk_score <= 1.0:
        return "risk score is missing, non-finite or outside [0, 1]"
    if action_class not in ACTION_CLASSES:
        return f"unknown action class {action_class!r}"
    if reversibility not in (0, 1):
        return f"invalid reversibility {reversibility!r}"
    if scope not in (0, 1, 2):
        return f"invalid scope {scope!r}"
    if privilege not in (0, 1):
        return f"invalid privilege {privilege!r}"
    if intent_match not in (-1, 0, 1):
        return f"invalid intent_match {intent_match!r}"
    if source_trusted not in (0, 1):
        return f"invalid source_trusted {source_trusted!r}"
    if not -1.0 <= target_in_request <= 1.0:
        return f"invalid target_in_request {target_in_request!r}"
    if repeat_count < 0:
        return f"invalid repeat_count {repeat_count!r}"
    return None


def _floor(
    *,
    action_class: str,
    catastrophic: bool,
    catastrophic_reason: str | None,
) -> AuthzDecision | None:
    if catastrophic:
        return AuthzDecision(
            decision="block",
            reason=f"safety floor: {catastrophic_reason or 'catastrophic action'}",
            stage="safety_floor",
        )
    if action_class == "other":
        return AuthzDecision(
            decision="block",
            reason="unknown command class; refusing to rate an unparsed action as safe",
            stage="safety_floor",
        )
    return None


def _authorization(
    *,
    source_trusted: int,
    intent_match: int,
    target_in_request: float,
    action_class: str,
    reversibility: int,
    scope: int,
) -> AuthzDecision | None:
    if source_trusted == 0 and intent_match != 1:
        return AuthzDecision(
            decision="block",
            reason="instruction does not come from the user and does not match the request",
            stage="authorization",
        )
    if intent_match == 0:
        if reversibility == 1 or scope >= 1:
            return AuthzDecision(
                decision="block",
                reason="action class does not match the requested intent and is not clearly reversible/single-file",
                stage="authorization",
            )
        return AuthzDecision(
            decision="confirm",
            reason="action class does not match the requested intent",
            stage="authorization",
        )
    if target_in_request == 0.0 and scope >= 1 and action_class in DESTRUCTIVE_CLASSES:
        return AuthzDecision(
            decision="block",
            reason="destructive action targets something absent from the request",
            stage="authorization",
        )
    return None


def _impact_ceiling(
    *,
    action_class: str,
    reversibility: int,
    scope: int,
    privilege: int,
    source_trusted: int,
) -> AuthzDecision | None:
    if reversibility == 1 and scope == 2:
        return AuthzDecision(
            decision="block",
            reason="irreversible system-wide action exceeds the impact ceiling",
            stage="impact_ceiling",
        )
    if reversibility == 1 and scope == 1 and action_class in DESTRUCTIVE_CLASSES:
        if source_trusted == 0:
            return AuthzDecision(
                decision="block",
                reason="untrusted source requests an irreversible multi-file action",
                stage="impact_ceiling",
            )
        return AuthzDecision(
            decision="confirm",
            reason="irreversible multi-file action needs explicit confirmation",
            stage="impact_ceiling",
        )
    if privilege == 1 and scope == 2:
        if source_trusted == 0:
            return AuthzDecision(
                decision="block",
                reason="untrusted source requests a privileged system-wide action",
                stage="impact_ceiling",
            )
        return AuthzDecision(
            decision="confirm",
            reason="privileged system-wide action needs explicit confirmation",
            stage="impact_ceiling",
        )
    return None


def _repeat(repeat_count: int) -> AuthzDecision | None:
    if repeat_count >= 3:
        return AuthzDecision(
            decision="block",
            reason=f"action repeated {repeat_count} times in one session",
            stage="repeat",
        )
    if repeat_count >= 1:
        return AuthzDecision(
            decision="confirm",
            reason=f"action repeated {repeat_count} time(s) in one session",
            stage="repeat",
        )
    return None


def evaluate_authz(
    *,
    risk_score: float,
    action_class: str,
    reversibility: int,
    scope: int,
    privilege: int,
    intent_match: int,
    source_trusted: int,
    target_in_request: float,
    catastrophic: bool = False,
    catastrophic_reason: str | None = None,
    repeat_count: int = 0,
) -> AuthzDecision:
    """Run the staged authorization pipeline.

    The most restrictive stage wins: block > confirm > allow.  Invalid or
    inconclusive input is blocked, never allowed.
    """
    invalid = _validate(
        risk_score=risk_score,
        action_class=action_class,
        reversibility=reversibility,
        scope=scope,
        privilege=privilege,
        intent_match=intent_match,
        source_trusted=source_trusted,
        target_in_request=target_in_request,
        repeat_count=repeat_count,
    )
    if invalid:
        return default_deny(f"invalid authorization input: {invalid}")

    candidates: list[AuthzDecision] = []
    floor = _floor(
        action_class=action_class,
        catastrophic=catastrophic,
        catastrophic_reason=catastrophic_reason,
    )
    if floor:
        candidates.append(floor)
    auth = _authorization(
        source_trusted=source_trusted,
        intent_match=intent_match,
        target_in_request=target_in_request,
        action_class=action_class,
        reversibility=reversibility,
        scope=scope,
    )
    if auth:
        candidates.append(auth)
    impact = _impact_ceiling(
        action_class=action_class,
        reversibility=reversibility,
        scope=scope,
        privilege=privilege,
        source_trusted=source_trusted,
    )
    if impact:
        candidates.append(impact)
    repeat = _repeat(repeat_count)
    if repeat:
        candidates.append(repeat)
    candidates.append(
        AuthzDecision(
            decision=score_decision(risk_score),
            reason=f"risk score {risk_score:.3f}",
            stage="score",
        )
    )

    rank = {"allow": 0, "confirm": 1, "block": 2}
    winner = max(candidates, key=lambda candidate: rank[candidate.decision])
    if winner.decision == "block":
        return winner
    if winner.decision == "confirm":
        return winner
    return winner


def staged_authz(risk_score: float, **kwargs: object) -> Decision:
    """Compatibility wrapper returning only the decision string.

    With no action context this is the original score-threshold function.  New
    code should call :func:`evaluate_authz` so the safety floor applies.
    """
    if not kwargs:
        if not math.isfinite(risk_score) or not 0.0 <= risk_score <= 1.0:
            return "block"
        return score_decision(risk_score)
    return evaluate_authz(risk_score=risk_score, **kwargs).decision  # type: ignore[arg-type]


def is_high_risk(risk_score: float) -> bool:
    """True when the score alone would block."""
    return score_decision(risk_score) == "block"


def is_medium_risk(risk_score: float) -> bool:
    """True when the score alone would request confirmation."""
    return score_decision(risk_score) == "confirm"


def is_low_risk(risk_score: float) -> bool:
    """True when the score alone would allow."""
    return score_decision(risk_score) == "allow"
