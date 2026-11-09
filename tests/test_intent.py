"""Tests for the deterministic intent extractor."""

from __future__ import annotations

from rootguard.intent import INTENT_CLASSES, classify_intent


def test_intent_classes_exactly_seventeen():
    assert len(INTENT_CLASSES) == 17


def test_list_read_intent():
    assert classify_intent("list files") == "list_read"
    assert classify_intent("show me the project files") == "list_read"


def test_delete_intent():
    assert classify_intent("delete temp files") == "delete"
    assert classify_intent("remove the old log") == "delete"


def test_database_intent():
    assert classify_intent("drop the production table") == "database_change"
    assert classify_intent("create table users") == "database_change"


def test_permission_intent_over_run_build():
    # "chmod +x run.sh" is permission_change, not run_build_test ("run").
    assert classify_intent("chmod +x run.sh") == "permission_change"


def test_perform_task_zero_is_other():
    assert classify_intent("perform task 0") == "other"


def test_blacklist_is_list_read_not_search():
    # "blacklist" contains "list" but should not dominate; substring trap.
    assert classify_intent("blacklist file.txt") == "list_read"


def test_empty_intent_is_other():
    assert classify_intent("") == "other"
    assert classify_intent("   ") == "other"
