"""Tests for the CLI entry point."""

from __future__ import annotations

from rootguard.cli import main


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "root.sh" in out


def test_allow_safe_command(capsys):
    code = main(["list files", "ls -la", "user_direct"])
    assert code == 0
    out = capsys.readouterr().out
    assert "decision=" in out


def test_block_dangerous_command(capsys):
    code = main(["delete everything", "rm -rf /", "user_direct"])
    assert code == 2
    out = capsys.readouterr().out
    assert "decision=block" in out
