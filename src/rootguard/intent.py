"""Deterministic, rule-based intent extraction.

The extractor maps a *user request* (never a proposed action) to one of the 17
classes in :data:`INTENT_CLASSES`.  Matching is word-boundary based, not
substring based: ``perform`` must not match ``rm`` and ``blacklist`` must not
match ``list``.

No model, embedding or network call is involved.
"""

from __future__ import annotations

import re

INTENT_CLASSES: tuple[str, ...] = (
    "list_read",
    "search",
    "create",
    "modify_file",
    "copy",
    "move_rename",
    "delete",
    "archive_compress",
    "remote_transfer",
    "install",
    "run_build_test",
    "network_fetch",
    "modify_environment",
    "permission_change",
    "process_control",
    "database_change",
    "other",
)

# Tie-break order.  Explicit, destructive or state-changing requests win over
# generic verbs when scores are equal.  ``chmod +x run.sh`` therefore remains a
# permission request instead of becoming a build request because of ``run``.
_PRIORITY: tuple[str, ...] = (
    "database_change",
    "permission_change",
    "process_control",
    "delete",
    "move_rename",
    "copy",
    "archive_compress",
    "install",
    "remote_transfer",
    "network_fetch",
    "modify_environment",
    "modify_file",
    "create",
    "run_build_test",
    "search",
    "list_read",
    "other",
)

# (compiled pattern, weight).  Patterns are deliberately word-boundary based.
_RULES: dict[str, tuple[tuple[re.Pattern[str], int], ...]] = {
    "list_read": (
        (re.compile(r"\b(list|listing|show|display|view|cat|head|tail|less|more|ls|dir|read|print|inspect|status|info|check|open)\b"), 3),
        (re.compile(r"\b(files?|folder|directory|contents?|logs?|output|tree)\b"), 1),
        (re.compile(r"\bwhat(?:'s| is) in\b"), 4),
        (re.compile(r"\bworking directory\b"), 4),
        (re.compile(r"\bdisk (?:usage|space)\b"), 4),
        (re.compile(r"\brunning (?:processes|services)\b"), 3),
    ),
    "search": (
        (re.compile(r"\b(search|find|locate|grep|seek|scan|query)\b"), 4),
        (re.compile(r"\blook(?:ing)? for\b"), 4),
        (re.compile(r"\b(?:which|where)\b"), 2),
    ),
    "create": (
        (re.compile(r"\b(create|mkdir|touch|init|initialize|generate|scaffold|new)\b"), 4),
        (re.compile(r"\bmake\b"), 1),
        (re.compile(r"\b(add|setup|set up)\b"), 2),
        (re.compile(r"\b(?:directory|folder|project|repository|repo)\b"), 1),
    ),
    "modify_file": (
        (re.compile(r"\b(edit|modify|change|update|replace|rewrite|append|prepend|insert|patch|truncate)\b"), 5),
        (re.compile(r"\b(sed|awk|in-place|in place)\b"), 3),
        (re.compile(r"\b(?:line|text|content|config(?:uration)?) (?:in|of|to)\b"), 2),
    ),
    "copy": (
        (re.compile(r"\b(copy|cp|duplicate|clone)\b"), 5),
        (re.compile(r"\bbackup\b"), 2),
        (re.compile(r"\b(?:to|into) (?:a )?(?:backup|copy)\b"), 3),
    ),
    "move_rename": (
        (re.compile(r"\b(move|mv|rename|relocate)\b"), 5),
        (re.compile(r"\b(?:move|rename) (?:it|them|this|that)\b"), 5),
    ),
    "delete": (
        (re.compile(r"\b(delete|remove|rm|del|erase|wipe|purge|clear|clean|cleanup)\b"), 5),
        (re.compile(r"\b(?:get rid of|throw away|free up)\b"), 5),
    ),
    "archive_compress": (
        (re.compile(r"\b(tar|zip|unzip|gzip|gunzip|compress|decompress|archive|extract|bzip2|xz|7z)\b"), 5),
        (re.compile(r"\b(?:tarball|compressed file)\b"), 3),
    ),
    "remote_transfer": (
        (re.compile(r"\b(scp|rsync|sftp|ftp|upload|push|send|transfer|ssh|remote)\b"), 5),
        (re.compile(r"\b(?:to|from) (?:a )?(?:server|remote host|remote machine|another machine)\b"), 4),
    ),
    "install": (
        (re.compile(r"\b(install|uninstall|reinstall|apt|apt-get|yum|dnf|pacman|pip|npm|package|dependency|dependencies)\b"), 5),
        (re.compile(r"\b(?:set up|setup) (?:a )?(?:package|tool|dependency)\b"), 4),
    ),
    "run_build_test": (
        (re.compile(r"\b(run|execute|test|tests|pytest|unittest|compile|build|make|lint|mvn|gradle|cargo|tox|benchmark|bench)\b"), 3),
        (re.compile(r"\b(?:run|execute) (?:the )?(?:build|tests?|suite|script|program|command)\b"), 6),
        (re.compile(r"\b(?:npm|yarn|pnpm) (?:run|test|start|build)\b"), 6),
    ),
    "network_fetch": (
        (re.compile(r"\b(curl|wget|fetch|download|http|https|api|url|web|website)\b"), 5),
        (re.compile(r"\b(?:get|retrieve) (?:the )?(?:file|page|data|resource) (?:from|at) (?:the )?(?:web|internet|url|endpoint)\b"), 5),
    ),
    "modify_environment": (
        (re.compile(r"\b(export|unset|alias|environment|env|path|shell profile|bashrc|zshrc|profile|ulimit|umask|source|cd|directory context)\b"), 4),
        (re.compile(r"\b(?:set|change|add to|remove from) (?:the )?(?:environment|path|shell)\b"), 6),
        (re.compile(r"\benvironment variable\b"), 6),
    ),
    "permission_change": (
        (re.compile(r"\b(chmod|chown|chgrp|permission|permissions|setuid|setgid|sudoers?|ownership|mode|access rights|privilege|privileges|executable)\b"), 5),
        (re.compile(r"\b(?:make|set) (?:it |the file )?(?:executable|readable|writable)\b"), 5),
        (re.compile(r"\b(?:grant|revoke|change) (?:access|permissions?|ownership)\b"), 5),
    ),
    "process_control": (
        (re.compile(r"\b(kill|pkill|killall|stop|start|restart|pause|resume|service|systemctl|daemon|job|shutdown|reboot)\b"), 5),
        (re.compile(r"\bprocess\b"), 1),
        (re.compile(r"\b(?:background|foreground) (?:process|job)\b"), 4),
    ),
    "database_change": (
        (re.compile(r"\b(database|sql|table|schema|drop|truncate|insert|into|update|alter|rows?|migration)\b"), 4),
        (re.compile(r"\bdelete from\b"), 7),
        (re.compile(r"\b(?:create|drop|alter) (?:a )?(?:database|table|schema|index)\b"), 7),
        (re.compile(r"\b(?:run|execute|apply) (?:a )?(?:query|migration|sql)\b"), 7),
        (re.compile(r"\bselect\b"), 2),
    ),
}


def _score_request(request_lower: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for intent, rules in _RULES.items():
        total = 0
        for pattern, weight in rules:
            if pattern.search(request_lower):
                total += weight
        if total:
            scores[intent] = total
    return scores


def classify_intent(user_request: str) -> str:
    """Classify *user_request* into one of :data:`INTENT_CLASSES`.

    Returns ``"other"`` when no rule matches.  The function is deterministic
    and has no side effects.
    """
    request = (user_request or "").strip().lower()
    if not request:
        return "other"

    scores = _score_request(request)
    if not scores:
        return "other"

    priority = {name: index for index, name in enumerate(_PRIORITY)}
    best = max(
        scores.items(),
        key=lambda item: (item[1], -priority.get(item[0], len(_PRIORITY))),
    )
    return best[0]


def classify_intent_batch(requests: list[str]) -> list[str]:
    """Classify multiple requests at once."""
    return [classify_intent(request) for request in requests]
