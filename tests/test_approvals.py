import pytest

from hazzel import config as _config
from hazzel.tools import approvals as appr
from hazzel.tools import run_command as rc
from hazzel.tools import write_file as wf


@pytest.fixture(autouse=True)
def _force_ask(monkeypatch):
    # Persistent /allow rules live in the real user config file; force the
    # default so a local `allow all=always` can't silence prompts here.
    monkeypatch.setattr(_config, "get_allow", lambda tool: "ask")


def _calls(monkeypatch):
    seen = []
    monkeypatch.setattr(rc.ui, "confirm", lambda *a, **k: seen.append(a) or False)
    return seen


def test_denied_command_never_prompts_twice(monkeypatch, tmp_path):
    appr.reset_approvals()
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    seen = _calls(monkeypatch)
    first = rc.run_command("rm -rf ask_once_target_xyz")
    second = rc.run_command("rm -rf ask_once_target_xyz")
    assert first == "Command cancelled by user"
    assert second.startswith("Command cancelled by user")
    assert second != first  # steers the model off the retry
    assert len(seen) == 1


def test_approved_command_runs_without_second_prompt(monkeypatch, tmp_path):
    appr.reset_approvals()
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    seen = []
    monkeypatch.setattr(rc.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    first = rc.run_command("false")
    second = rc.run_command("false")
    assert "Command failed" in first
    assert "Command failed" in second
    assert len(seen) == 1


def test_different_commands_each_prompt(monkeypatch, tmp_path):
    appr.reset_approvals()
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    seen = _calls(monkeypatch)
    rc.run_command("rm -rf distinct_one_xyz")
    rc.run_command("rm -rf distinct_two_xyz")
    assert len(seen) == 2


def test_reset_clears_decisions(monkeypatch, tmp_path):
    appr.reset_approvals()
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    seen = _calls(monkeypatch)
    rc.run_command("rm -rf reset_me_xyz")
    appr.reset_approvals()
    rc.run_command("rm -rf reset_me_xyz")
    assert len(seen) == 2


def test_denied_overwrite_never_prompts_twice(monkeypatch, tmp_path):
    appr.reset_approvals()
    monkeypatch.setattr(_config, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "note.txt"
    target.write_text("original")
    seen = []
    monkeypatch.setattr(wf.ui, "confirm", lambda *a, **k: seen.append(a) or False)
    first = wf.write_file(str(target), "changed")
    second = wf.write_file(str(target), "changed")
    assert first == "Write cancelled by user"
    assert second.startswith("Write cancelled by user")
    assert second != first
    assert len(seen) == 1
    assert target.read_text() == "original"
