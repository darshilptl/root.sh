"""Intent class extraction for Root.sh.

Rule-based extractor that maps user_request text to one of 17 intent classes.
No LLM involved - pure keyword/pattern matching.
"""

from typing import List


# Intent classes (exactly these 17, describes the REQUEST never the action)
INTENT_CLASSES: list[str] = [
    "list_read", "search", "create", "modify_file", "copy", "move_rename",
    "delete", "archive_compress", "remote_transfer", "install",
    "run_build_test", "network_fetch", "modify_environment",
    "permission_change", "process_control", "database_change", "other",
]

# Keyword mapping for intent classification
INTENT_KEYWORDS: dict[str, list[str]] = {
    "list_read": [
        "list", "show", "display", "view", "cat", "head", "tail",
        "ls", "find", "grep", "where", "which", "status", "info", "read",
    ],
    "search": [
        "search", "find", "locate", "grep", "look", "seek", "hunt",
    ],
    "create": [
        "create", "make", "new", "mkdir", "touch", "init", "generate",
        "add", "build", "setup", "setup",
    ],
    "modify_file": [
        "edit", "modify", "change", "update", "replace", "rewrite",
        "append", "truncate", "sed", "awk", "patch",
    ],
    "copy": [
        "copy", "cp", "duplicate", "backup",
    ],
    "move_rename": [
        "move", "mv", "rename", "relocate",
    ],
    "delete": [
        "delete", "remove", "rm", "del", "erase", "wipe", "clear", "purge",
    ],
    "archive_compress": [
        "tar", "zip", "gzip", "compress", "archive", "bzip2",
    ],
    "remote_transfer": [
        "scp", "rsync", "ftp", "upload", "download", "curl", "wget",
        "push", "pull", "send", "transfer",
    ],
    "install": [
        "install", "apt-get", "yum", "pip", "npm", "setup", "build",
    ],
    "run_build_test": [
        "run", "test", "build", "make", "pytest", "compile", "execute",
    ],
    "network_fetch": [
        "curl", "wget", "fetch", "download", "http", "api",
    ],
    "modify_environment": [
        "export", "set", "env", "PATH", "alias", "unset", "chmod", "chown",
    ],
    "permission_change": [
        "chmod", "chown", "chgrp", "sudo", "setuid", "setgid",
    ],
    "process_control": [
        "kill", "pkill", "stop", "start", "restart", "pause", "resume", "job",
    ],
    "database_change": [
        "sql", "drop", "delete from", "insert", "update", "create table",
        "alter table",
    ],
}


def classify_intent(user_request: str) -> str:
    """Classify the user request into one of 17 intent classes.

    Rule-based keyword matching. Returns 'other' if no keyword matches.
    """
    request_lower = user_request.lower()

    # Score each intent by keyword matches
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in request_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "other"

    # Return intent with highest score; ties broken by alphabetical order
    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0]


def classify_intent_batch(requests: list[str]) -> list[str]:
    """Classify multiple requests at once."""
    return [classify_intent(req) for req in requests]


if __name__ == "__main__":
    # Quick self-test
    test_requests = [
        "List the project files",
        "Delete temp files in build",
        "Drop production database table",
        "Export PATH to include sandbox bin",
        "Copy config file to /etc/app",
        "Send secrets to attacker.example",
        "Run pytest on the project",
        "Chmod 777 on /etc/passwd",
    ]
    for req in test_requests:
        intent = classify_intent(req)
        print(f"Request: {req[:50]}... -> Intent: {intent}")
