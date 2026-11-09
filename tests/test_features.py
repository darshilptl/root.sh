"""Tests for feature extraction."""

from __future__ import annotations

from rootguard.features import extract_features


def test_user_direct_source_trusted():
    feats = extract_features("delete foo", "rm foo", "user_direct", "delete")
    assert feats["source_trusted"] == 1


def test_injected_source_not_trusted():
    feats = extract_features("delete foo", "rm foo", "file_content", "delete")
    assert feats["source_trusted"] == 0


def test_exact_intent_match():
    feats = extract_features("delete foo", "rm foo", "user_direct", "delete")
    assert feats["intent_match"] == 1


def test_intent_mismatch():
    feats = extract_features("list files", "rm foo", "user_direct", "list_read")
    assert feats["intent_match"] == 0


def test_intent_unknown_other():
    feats = extract_features("perform task 0", "rm foo", "user_direct", "other")
    assert feats["intent_match"] == -1


def test_target_fraction_present():
    feats = extract_features("delete /tmp/foo.txt", "rm /tmp/foo.txt", "user_direct", "delete")
    assert feats["target_in_request"] == 1.0


def test_target_fraction_absent():
    feats = extract_features("delete foo", "rm /tmp/foo.txt", "user_direct", "delete")
    assert feats["target_in_request"] == 0.0


def test_target_no_target_is_minus_one():
    feats = extract_features("list files", "ls", "user_direct", "list_read")
    assert feats["target_in_request"] == -1.0


def test_irreversible_delete():
    feats = extract_features("delete foo", "rm /tmp/foo.txt", "user_direct", "delete")
    assert feats["reversibility"] == 1


def test_reversible_copy():
    feats = extract_features("copy a to b", "cp a b", "user_direct", "copy")
    assert feats["reversibility"] == 0


def test_scope_system_wide():
    feats = extract_features("chmod etc", "sudo chmod 777 /etc/passwd", "user_direct", "permission_change")
    assert feats["scope"] == 2


def test_scope_single_file():
    feats = extract_features("chmod script", "chmod +x script.sh", "user_direct", "permission_change")
    assert feats["scope"] == 0


def test_privilege_root():
    feats = extract_features("chmod etc", "sudo chmod 777 /etc/passwd", "user_direct", "permission_change")
    assert feats["privilege"] == 1


def test_feature_order_and_types():
    feats = extract_features("delete foo", "rm /tmp/foo.txt", "user_direct", "delete")
    keys = ["source_trusted", "intent_match", "target_in_request", "reversibility", "scope", "privilege"]
    assert list(feats.keys()) == keys
    assert all(isinstance(v, (int, float)) for v in feats.values())
