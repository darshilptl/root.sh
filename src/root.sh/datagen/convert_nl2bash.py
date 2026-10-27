"""Convert NL2Bash all.nl / all.cm pairs into RootGuard record format."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from .schema import (
    FIELD_NAMES,
    INTENT_CLASSES,
    Record,
    validate_record_dict,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALL_NL = PROJECT_ROOT / "data" / "external" / "nl2bash" / "data" / "bash" / "all.nl"
ALL_CM = PROJECT_ROOT / "data" / "external" / "nl2bash" / "data" / "bash" / "all.cm"
OUTPUT = PROJECT_ROOT / "data" / "processed" / "nl2bash.jsonl"

TARGET_ROWS = 80
MAX_PER_UTILITY = 10

_INTENT_KEYWORDS = {
    "list_read": ["list", "show", "display", "view", "cat", "head", "tail", "ls", "find", "grep", "where", "which", "status", "info"],
    "search": ["search", "find", "locate", "grep", "look for", "seek"],
    "create": ["create", "make", "new", "mkdir", "touch", "init", "generate", "add"],
    "modify_file": ["edit", "modify", "change", "update", "replace", "rewrite", "append", "truncate", "sed", "awk"],
    "copy": ["copy", "cp", "duplicate", "backup"],
    "move_rename": ["move", "mv", "rename", "relocate"],
    "delete": ["delete", "remove", "rm", "del", "erase", "wipe", "clear", "purge"],
    "archive_compress": ["tar", "zip", "gzip", "compress", "archive", "bzip2"],
    "remote_transfer": ["scp", "rsync", "ftp", "upload", "download", "wget", "curl", "push", "pull"],
    "install": ["install", "apt-get", "yum", "pip", "npm", "setup", "build"],
    "run_build_test": ["run", "test", "build", "make", "pytest", "compile", "execute"],
    "network_fetch": ["curl", "wget", "fetch", "download", "http", "api"],
    "modify_environment": ["export", "set", "env", "PATH", "alias", "unset", "chmod", "chown"],
    "permission_change": ["chmod", "chown", "chgrp", "sudo", "setuid", "setgid"],
    "process_control": ["kill", "pkill", "stop", "start", "restart", "pause", "resume", "job"],
    "database_change": ["sql", "drop", "delete from", "insert", "update", "create table", "alter table"],
}


def classify_intent(user_request: str, proposed_action: str) -> str:
    text = (user_request + " " + proposed_action).lower()
    scores: dict[str, int] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[intent] = score
    if not scores:
        return "other"
    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0]


def extract_utility(proposed_action: str) -> str:
    cmd = proposed_action.strip()
    cmd = re.sub(r'^[^\w]+', '', cmd)
    parts = cmd.split()
    if not parts:
        return "unknown"
    utility = parts[0].lower()
    utility = re.sub(r'[^\w]+$', '', utility)
    return utility or "unknown"


def convert() -> int:
    if not ALL_NL.exists() or not ALL_CM.exists():
        print(f"ERROR: Missing input files: {ALL_NL} or {ALL_CM}", file=sys.stderr)
        return 1

    with ALL_NL.open("r", encoding="utf-8") as f_nl, ALL_CM.open("r", encoding="utf-8") as f_cm:
        nl_lines = [line.rstrip("\n") for line in f_nl]
        cm_lines = [line.rstrip("\n") for line in f_cm]

    if len(nl_lines) != len(cm_lines):
        print(f"ERROR: Line count mismatch: all.nl={len(nl_lines)}, all.cm={len(cm_lines)}", file=sys.stderr)
        return 1

    total_pairs = len(nl_lines)
    print(f"Read {total_pairs} line-aligned pairs from NL2Bash")

    seen_requests: set[str] = set()
    utility_counts: Counter[str] = Counter()
    records: list[Record] = []

    for nl, cm in zip(nl_lines, cm_lines):
        if not nl.strip() or not cm.strip():
            continue
        if nl in seen_requests:
            continue
        utility = extract_utility(cm)
        if utility_counts[utility] >= MAX_PER_UTILITY:
            continue
        intent = classify_intent(nl, cm)
        family_id = f"nl2bash-{len(records) + 1:04d}"
        reasoning = "NL2Bash external corpus; user request matched to shell command; safe by provenance."
        rec = Record.new_nl2bash(
            family_id=family_id,
            user_request=nl,
            intent_class=intent,
            proposed_action=cm,
            reasoning=reasoning,
        )
        errors = rec.validate()
        if errors:
            print(f"SKIP (validation): {errors} | request={nl[:60]}...", file=sys.stderr)
            continue
        seen_requests.add(nl)
        utility_counts[utility] += 1
        records.append(rec)
        if len(records) >= TARGET_ROWS:
            break

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} rows to {OUTPUT}")
    print(f"Unique utilities: {len(utility_counts)}")
    print(f"Utility distribution: {dict(sorted(utility_counts.items(), key=lambda x: -x[1])[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(convert())
