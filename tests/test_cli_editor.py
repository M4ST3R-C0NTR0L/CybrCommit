"""Tests for the editor-lookup behavior in cybrcommit.cli.edit_message."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from cybrcommit import cli


class _FakeGitVarResult:
    """Stand-in for the `git var GIT_EDITOR` subprocess result (empty stdout)."""

    stdout = ""


def _make_fake_run(recorded_calls):
    """Return a fake subprocess.run that records editor invocations.

    The first call (git var GIT_EDITOR) returns empty stdout so the fallback
    to os.environ is exercised. The second call is the editor launch, which
    we record for assertions.
    """

    def fake_run(argv, *args, **kwargs):
        # git var GIT_EDITOR lookup — return empty so os.environ is consulted
        if argv[:2] == ["git", "var"]:
            return _FakeGitVarResult()
        recorded_calls.append({"argv": argv, "kwargs": kwargs})
        return SimpleNamespace(returncode=0)

    return fake_run


def test_edit_message_uses_editor_env_var_when_set(monkeypatch, tmp_path):
    """When EDITOR is set, it should be used as the editor binary."""
    recorded: list[dict] = []
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setattr(cli.subprocess, "run", _make_fake_run(recorded))

    cli.edit_message("initial message")

    assert len(recorded) == 1, "expected exactly one editor invocation"
    argv = recorded[0]["argv"]
    assert argv[0] == "nano", f"expected 'nano' as editor, got {argv[0]!r}"
    assert len(argv) == 2, "editor should be called with exactly [editor, path]"
    assert recorded[0]["kwargs"].get("check") is False


def test_edit_message_falls_back_to_vim_when_editor_unset(monkeypatch):
    """When EDITOR is not set, the editor should default to vim."""
    recorded: list[dict] = []
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(cli.subprocess, "run", _make_fake_run(recorded))

    cli.edit_message("initial message")

    assert len(recorded) == 1
    argv = recorded[0]["argv"]
    assert argv[0] == "vim", f"expected 'vim' default, got {argv[0]!r}"
    assert len(argv) == 2
