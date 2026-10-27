"""Schema definition for RootGuard dataset records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid

INTENT_CLASSES = frozenset({
    "list_read", "search", "create", "modify_file", "copy", "move_rename",
    "delete", "archive_compress", "remote_transfer", "install",
    "run_build_test", "network_fetch", "modify_environment",
    "permission_change", "process_control", "database_change", "other",
})

SOURCES = frozenset({
    "user_direct", "file_content", "web_content", "tool_output", "agent_internal",
})

LABELS = frozenset({"safe", "risky"})

PROVENANCES = frozenset({"seed", "generated", "nl2bash"})

FIELD_NAMES = [
    "id", "family_id", "twin_of", "user_request", "intent_class", "source",
    "injected_text", "proposed_action", "label", "reasoning", "provenance",
    "generator", "split", "reviewed", "created_at",
]


@dataclass
class Record:
    id: str
    family_id: str
    twin_of: Optional[str]
    user_request: str
    intent_class: str
    source: str
    injected_text: Optional[str]
    proposed_action: str
    label: str
    reasoning: str
    provenance: str
    generator: Optional[str]
    split: Optional[str]
    reviewed: bool
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "family_id": self.family_id,
            "twin_of": self.twin_of,
            "user_request": self.user_request,
            "intent_class": self.intent_class,
            "source": self.source,
            "injected_text": self.injected_text,
            "proposed_action": self.proposed_action,
            "label": self.label,
            "reasoning": self.reasoning,
            "provenance": self.provenance,
            "generator": self.generator,
            "split": self.split,
            "reviewed": self.reviewed,
            "created_at": self.created_at,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.intent_class not in INTENT_CLASSES:
            errors.append(f"invalid intent_class: {self.intent_class!r}")
        if self.source not in SOURCES:
            errors.append(f"invalid source: {self.source!r}")
        if self.label not in LABELS:
            errors.append(f"invalid label: {self.label!r}")
        if self.provenance not in PROVENANCES:
            errors.append(f"invalid provenance: {self.provenance!r}")
        if self.split is not None:
            errors.append(f"split must be null, got: {self.split!r}")
        if self.reviewed is not False:
            errors.append(f"reviewed must be false, got: {self.reviewed!r}")
        needs_injected = (
            self.label == "risky"
            and self.source in {"file_content", "web_content", "tool_output"}
        )
        if needs_injected and not self.injected_text:
            errors.append("injected_text required for risky content-source rows")
        if not needs_injected and self.injected_text is not None:
            errors.append("injected_text must be null for non-content-source or safe rows")
        return errors

    @classmethod
    def new_seed(cls, family_id, twin_of, user_request, intent_class, source,
                 proposed_action, label, reasoning, created_at=None):
        return cls(
            id=str(uuid.uuid4()), family_id=family_id, twin_of=twin_of,
            user_request=user_request, intent_class=intent_class, source=source,
            injected_text=None, proposed_action=proposed_action, label=label,
            reasoning=reasoning, provenance="seed", generator=None,
            split=None, reviewed=False,
            created_at=created_at or _now(),
        )

    @classmethod
    def new_generated(cls, family_id, twin_of, user_request, intent_class, source,
                      proposed_action, label, reasoning, generator, created_at=None):
        return cls(
            id=str(uuid.uuid4()), family_id=family_id, twin_of=twin_of,
            user_request=user_request, intent_class=intent_class, source=source,
            injected_text=None, proposed_action=proposed_action, label=label,
            reasoning=reasoning, provenance="generated", generator=generator,
            split=None, reviewed=False,
            created_at=created_at or _now(),
        )

    @classmethod
    def new_nl2bash(cls, family_id, user_request, intent_class, proposed_action,
                    reasoning, created_at=None):
        return cls(
            id=str(uuid.uuid4()), family_id=family_id, twin_of=None,
            user_request=user_request, intent_class=intent_class,
            source="user_direct", injected_text=None, proposed_action=proposed_action,
            label="safe", reasoning=reasoning, provenance="nl2bash", generator=None,
            split=None, reviewed=False, created_at=created_at or _now(),
        )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_record_dict(row: dict) -> list[str]:
    rec = Record(
        id=row.get("id", ""), family_id=row.get("family_id", ""),
        twin_of=row.get("twin_of"), user_request=row.get("user_request", ""),
        intent_class=row.get("intent_class", ""), source=row.get("source", ""),
        injected_text=row.get("injected_text"), proposed_action=row.get("proposed_action", ""),
        label=row.get("label", ""), reasoning=row.get("reasoning", ""),
        provenance=row.get("provenance", ""), generator=row.get("generator"),
        split=row.get("split"), reviewed=row.get("reviewed", True),
        created_at=row.get("created_at", ""),
    )
    return rec.validate()
