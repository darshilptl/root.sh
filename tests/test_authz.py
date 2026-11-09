"""Tests for staged authorization."""

from __future__ import annotations

from rootguard.authz import Decision, evaluate_authz, staged_authz


def base(
    *,
    risk_score=0.1,
    action_class="list_read",
    reversibility=0,
    scope=0,
    privilege=0,
    intent_match=1,
    source_trusted=1,
    target_in_request=1.0,
    catastrophic=False,
    catastrophic_reason=None,
    repeat_count=0,
):
    return evaluate_authz(
        risk_score=risk_score,
        action_class=action_class,
        reversibility=reversibility,
        scope=scope,
        privilege=privilege,
        intent_match=intent_match,
        source_trusted=source_trusted,
        target_in_request=target_in_request,
        catastrophic=catastrophic,
        catastrophic_reason=catastrophic_reason,
        repeat_count=repeat_count,
    )


def test_allow_low_score():
    assert base().decision == "allow"


def test_block_high_score():
    assert base(risk_score=0.8).decision == "block"


def test_confirm_mid_score():
    assert base(risk_score=0.5).decision == "confirm"


def test_catastrophic_always_block():
    assert (
        base(
            risk_score=0.1,
            action_class="delete",
            catastrophic=True,
            catastrophic_reason="rm -rf /",
        ).decision
        == "block"
    )


def test_unknown_command_always_block():
    assert base(action_class="other", risk_score=0.1).decision == "block"


def test_untrusted_source_and_mismatch_blocks():
    assert (
        base(
            risk_score=0.1,
            source_trusted=0,
            intent_match=0,
            action_class="delete",
            reversibility=1,
        ).decision
        == "block"
    )


def test_untrusted_source_mismatch_reversible_single_confirm():
    # Matched source but mismatched intent, reversible single-file -> confirm.
    assert (
        base(
            risk_score=0.1,
            source_trusted=1,
            intent_match=0,
            action_class="copy",
            reversibility=0,
            scope=0,
        ).decision
        == "confirm"
    )


def test_user_direct_overreach_blocks():
    # The core regression: dangerous user_direct actions must not score safe.
    assert (
        base(
            risk_score=0.05,
            action_class="delete",
            reversibility=1,
            scope=2,
            source_trusted=1,
            intent_match=1,
        ).decision
        == "block"
    )


def test_invalid_risk_blocks():
    assert base(risk_score=float("nan")).decision == "block"
    assert base(risk_score=1.5).decision == "block"


def test_staged_authz_wrapper():
    assert staged_authz(0.1) == "allow"
    assert staged_authz(0.8) == "block"


def test_repeat_three_blocks():
    assert base(repeat_count=3, risk_score=0.1).decision == "block"


def test_repeat_one_confirms():
    assert base(repeat_count=1, risk_score=0.1).decision == "confirm"
