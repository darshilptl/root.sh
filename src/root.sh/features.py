"""Feature extraction for Root.sh scoring.

Extracts exactly six features from (user_request, proposed_action, source):

1. source_trusted: 1 if source == user_direct else 0
2. intent_match: 1 match, 0 mismatch, -1 unknown
3. target_in_request: fraction of action path tokens in request; -1 if no target
4. reversibility: 0 reversible, 1 irreversible
5. scope: 0 single file/process, 1 folder/multi-file, 2 system-wide
6. privilege: 0 user, 1 root
"""

from typing import Any


def source_trusted(source: str) -> int:
    """1 if source is user_direct, else 0."""
    return 1 if source == "user_direct" else 0


def intent_match(user_request: str, proposed_action: str, intent_class: str) -> int:
    """1 if intent matches action type, 0 mismatch, -1 unknown."""
    action_lower = proposed_action.lower()
    request_lower = user_request.lower()

    # Simple keyword-based intent-action matching
    intent_keywords = {
        "list_read": ["list", "show", "display", "view", "cat", "head", "tail", "find", "grep", "where", "which", "status"],
        "search": ["search", "find", "locate", "grep", "look", "seek"],
        "create": ["create", "make", "new", "mkdir", "touch", "init", "generate", "add", "build"],
        "modify_file": ["edit", "modify", "change", "update", "replace", "rewrite", "append", "truncate", "sed"],
        "copy": ["copy", "cp", "duplicate", "backup"],
        "move_rename": ["move", "mv", "rename", "relocate"],
        "delete": ["delete", "remove", "rm", "del", "erase", "wipe", "clear", "purge"],
        "archive_compress": ["tar", "zip", "gzip", "compress", "archive", "bzip2"],
        "remote_transfer": ["scp", "rsync", "ftp", "upload", "download", "curl", "wget", "push", "pull"],
        "install": ["install", "apt-get", "yum", "pip", "npm", "setup", "build"],
        "run_build_test": ["run", "test", "build", "make", "pytest", "compile", "execute"],
        "network_fetch": ["curl", "wget", "fetch", "download", "http", "api"],
        "modify_environment": ["export", "set", "env", "PATH", "alias", "unset", "chmod", "chown"],
        "permission_change": ["chmod", "chown", "chgrp", "sudo", "setuid", "setgid"],
        "process_control": ["kill", "pkill", "stop", "start", "restart", "pause", "resume", "job"],
        "database_change": ["sql", "drop", "delete from", "insert", "update", "create table", "alter table"],
    }

    matched_intents = [
        intent for intent, keywords in intent_keywords.items()
        if any(kw in request_lower for kw in keywords)
    ]

    if intent_class not in matched_intents:
        return -1

    # Check if action matches the intent
    if intent_class == "delete" and any(kw in action_lower for kw in ["rm", "delete", "remove", "purge", "clear"]):
        return 1
    if intent_class == "copy" and any(kw in action_lower for kw in ["cp", "copy", "duplicate", "backup"]):
        return 1
    if intent_class == "move_rename" and any(kw in action_lower for kw in ["mv", "move", "rename"]):
        return 1
    if intent_class == "modify_environment" and any(kw in action_lower for kw in ["export", "set", "env", "PATH", "alias", "unset"]):
        return 1
    if intent_class == "permission_change" and any(kw in action_lower for kw in ["chmod", "chown", "chgrp", "sudo", "setuid"]):
        return 1
    if intent_class == "database_change" and any(kw in action_lower for kw in ["sql", "drop", "delete from", "insert", "update", "create table", "alter table"]):
        return 1
    if intent_class == "remote_transfer" and any(kw in action_lower for kw in ["scp", "rsync", "ftp", "upload", "download", "curl", "wget"]):
        return 1
    if intent_class == "install" and any(kw in action_lower for kw in ["install", "apt-get", "yum", "pip", "npm", "setup"]):
        return 1
    if intent_class == "run_build_test" and any(kw in action_lower for kw in ["run", "test", "build", "make", "pytest", "compile", "execute"]):
        return 1
    if intent_class == "list_read" and any(kw in action_lower for kw in ["ls", "list", "cat", "head", "tail", "find", "grep", "show"]):
        return 1
    if intent_class == "search" and any(kw in action_lower for kw in ["find", "grep", "search", "locate"]):
        return 1
    if intent_class == "create" and any(kw in action_lower for kw in ["mkdir", "touch", "create", "make", "init", "generate"]):
        return 1
    if intent_class == "archive_compress" and any(kw in action_lower for kw in ["tar", "zip", "gzip", "compress", "archive", "bzip2"]):
        return 1
    if intent_class == "network_fetch" and any(kw in action_lower for kw in ["curl", "wget", "fetch", "download", "http", "api"]):
        return 1
    if intent_class == "process_control" and any(kw in action_lower for kw in ["kill", "pkill", "stop", "start", "restart", "pause", "resume"]):
        return 1

    return 0


def target_in_request(user_request: str, proposed_action: str) -> float:
    """Fraction of action path tokens present in request; -1 if no target."""
    import re

    action_lower = proposed_action.lower()
    request_lower = user_request.lower()

    # Extract path-like tokens from action (paths starting with / or ~)
    path_tokens = re.findall(r'(?:/|~)[\w/.-]*', action_lower)

    # Also extract quoted file paths
    quoted_tokens = re.findall(r'["\']([^"\']+)["\']', action_lower)
    path_tokens.extend([t.lower() for t in quoted_tokens if "/" in t or "~" in t])

    if not path_tokens:
        return -1.0

    # Count how many path tokens appear in the request
    matches = sum(1 for token in path_tokens if token in request_lower)
    return matches / len(path_tokens)


def reversibility(proposed_action: str) -> int:
    """0 reversible, 1 irreversible."""
    action_lower = proposed_action.lower()

    # Destructive/irreversible commands
    irreversible_keywords = [
        "rm ", "rm -rf", "rmdir", "dd ", "mkfs", "format",
        "drop table", "drop database", "truncate",
        "chmod 777", "chmod -R",
        "> ", ">> ",  # redirect overwrite/append
    ]

    if any(kw in action_lower for kw in irreversible_keywords):
        return 1

    return 0


def scope(proposed_action: str) -> int:
    """0 single file/process, 1 folder/multi-file, 2 system-wide."""
    action_lower = proposed_action.lower()

    # System-wide: /etc/, /usr/, /bin/, /lib/, sudo, systemctl
    system_wide_patterns = [
        "/etc/", "/usr/", "/bin/", "/lib/", "/sbin/",
        "sudo", "systemctl", "chmod 777", "setuid", "setgid",
        "/proc/", "/sys/", "/dev/"
    ]
    if any(kw in action_lower for kw in system_wide_patterns):
        return 2

    # Multi-file: *, recursive, directory paths
    multi_file_patterns = [
        "*", "rm -rf", "chmod -R", "chown -R", "find ", "grep -r",
        "~/", "./", "../"
    ]
    if any(kw in action_lower for kw in multi_file_patterns):
        return 1

    return 0


def privilege(proposed_action: str) -> int:
    """0 user, 1 root."""
    action_lower = proposed_action.lower()

    if "sudo" in action_lower or "setuid" in action_lower or "setgid" in action_lower:
        return 1

    return 0


def extract_features(user_request: str, proposed_action: str, source: str, intent_class: str) -> dict[str, int | float]:
    """Extract all six features and return as dict."""
    return {
        "source_trusted": source_trusted(source),
        "intent_match": intent_match(user_request, proposed_action, intent_class),
        "target_in_request": target_in_request(user_request, proposed_action),
        "reversibility": reversibility(proposed_action),
        "scope": scope(proposed_action),
        "privilege": privilege(proposed_action),
    }


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("List project files", "export PATH=/tmp/sandbox-bin:$PATH", "file_content", "list_read"),
        ("Delete temp files", "rm -rf /tmp/sandbox-old", "user_direct", "delete"),
        ("Drop production table", "DROP TABLE production_db;", "agent_internal", "database_change"),
    ]
    for req, action, src, intent in test_cases:
        feats = extract_features(req, action, src, intent)
        print(f"Request: {req[:40]}... | Action: {action[:40]}... | Source: {src}")
        print(f"  Features: {feats}")
        print()
