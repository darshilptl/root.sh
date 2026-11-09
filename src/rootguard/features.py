"""Feature extraction for the Root.sh defense layer.

Exactly six features are produced, in this order:

1. ``source_trusted`` -- 1 if source is ``user_direct``, else 0.
2. ``intent_match`` -- 1 match, 0 mismatch, -1 unknown.
3. ``target_in_request`` -- fraction of action targets present in the request;
   -1 when the action has no meaningful target.
4. ``reversibility`` -- 0 reversible, 1 irreversible.
5. ``scope`` -- 0 single file/process, 1 folder/multi-file, 2 system-wide.
6. ``privilege`` -- 0 user, 1 root.

The action properties come from :mod:`rootguard.categories`, which parses the
command text without executing it.  No feature uses the heldout split and no
feature calls a network service.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from rootguard.categories import ActionInfo, classify_action
from rootguard.intent import INTENT_CLASSES

#: Pairs where one action class can legitimately satisfy another request class.
#: This table is deliberately small; it is a compatibility rule, not a licence
#: to treat every non-matching action as safe.
COMPATIBLE_CLASSES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"list_read", "search"}),
        frozenset({"create", "modify_file"}),
        frozenset({"create", "copy"}),
        frozenset({"copy", "archive_compress"}),
        frozenset({"remote_transfer", "network_fetch"}),
        frozenset({"modify_environment", "permission_change"}),
    }
)

_GENERIC_TARGETS = frozenset({"", "*", "/", ".", "..", "~", "-", "--"})


def source_trusted(source: str) -> int:
    """Return 1 only for a direct user instruction."""
    return 1 if source == "user_direct" else 0


def intent_match(user_request: str, proposed_action: str, intent_class: str) -> int:
    """Compare the request intent with the action class.

    Returns ``1`` for an exact or explicitly compatible match, ``0`` for a
    mismatch, and ``-1`` when either side is unknown.
    """
    if intent_class not in INTENT_CLASSES or intent_class == "other":
        return -1

    action = classify_action(proposed_action)
    if action.action_class == "other":
        return -1

    if action.action_class == intent_class:
        return 1
    if frozenset({action.action_class, intent_class}) in COMPATIBLE_CLASSES:
        return 1
    return 0


def _meaningful_targets(action: ActionInfo) -> list[str]:
    targets: list[str] = []
    for target in action.targets:
        candidate = target.strip().strip("'\"`")
        if candidate.startswith("@"):
            candidate = candidate[1:]
        if candidate in _GENERIC_TARGETS:
            continue
        if candidate.startswith("-"):
            continue
        targets.append(candidate)
    return targets


def _target_present(target: str, request_lower: str) -> float:
    """Return 1.0 for a full target match, 0.75 for a basename match, else 0."""
    target_lower = target.lower().strip().rstrip(".,;:)")
    if not target_lower:
        return 0.0
    if target_lower in request_lower:
        return 1.0

    # Basename match: /etc/app/config.yml -> config.yml
    basename = PurePosixPath(target_lower.replace(":", "/")).name
    if basename and basename != target_lower:
        if re.search(rf"(?<![\w.-]){re.escape(basename)}(?![\w.-])", request_lower):
            return 0.75
    return 0.0


def target_in_request(user_request: str, proposed_action: str) -> float:
    """Fraction of the action's path/target tokens present in the request.

    Returns ``-1.0`` when the action has no meaningful target (for example
    ``ls`` with no path), because absence of a target is not evidence of a
    mismatch.
    """
    action = classify_action(proposed_action)
    targets = _meaningful_targets(action)
    if not targets:
        return -1.0

    request_lower = (user_request or "").lower()
    if not request_lower.strip():
        return 0.0

    values = [_target_present(target, request_lower) for target in targets]
    return sum(values) / len(values)


def reversibility(proposed_action: str) -> int:
    """0 reversible, 1 irreversible."""
    return classify_action(proposed_action).reversibility


def scope(proposed_action: str) -> int:
    """0 single file/process, 1 folder/multi-file, 2 system-wide."""
    return classify_action(proposed_action).scope


def privilege(proposed_action: str) -> int:
    """0 user, 1 root."""
    return classify_action(proposed_action).privilege


def extract_features(
    user_request: str,
    proposed_action: str,
    source: str,
    intent_class: str,
) -> dict[str, int | float]:
    """Extract all six features in the canonical order."""
    action = classify_action(proposed_action)
    targets = _meaningful_targets(action)
    request_lower = (user_request or "").lower()

    if targets and request_lower.strip():
        target_fraction = sum(_target_present(t, request_lower) for t in targets) / len(targets)
    elif targets:
        target_fraction = 0.0
    else:
        target_fraction = -1.0

    if intent_class not in INTENT_CLASSES or intent_class == "other" or action.action_class == "other":
        match = -1
    elif action.action_class == intent_class:
        match = 1
    elif frozenset({action.action_class, intent_class}) in COMPATIBLE_CLASSES:
        match = 1
    else:
        match = 0

    return {
        "source_trusted": source_trusted(source),
        "intent_match": match,
        "target_in_request": target_fraction,
        "reversibility": action.reversibility,
        "scope": action.scope,
        "privilege": action.privilege,
    }


def feature_vector(features: dict[str, int | float]) -> list[float]:
    """Return the six feature values in the canonical order."""
    return [
        float(features["source_trusted"]),
        float(features["intent_match"]),
        float(features["target_in_request"]),
        float(features["reversibility"]),
        float(features["scope"]),
        float(features["privilege"]),
    ]
