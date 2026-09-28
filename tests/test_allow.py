from hazzel import config
from hazzel.tools import approvals as appr
from hazzel.tools import run_command as rc
from hazzel.tools import write_file as wf
from hazzel.tools import edit_file as ef
from hazzel.tools import apply_edits as ae
from hazzel.tools import git_commit as gc


def _tmp_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config, "LEGACY_FILE", tmp_path / "legacy.json")
    monkeypatch.setattr(config, "_allow_rules", {})
    appr.reset_approvals()


def test_allow_roundtrip(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    assert config.get_allow("run_command") == "ask"
    assert config.set_allow("run_command", "always") is True
    assert config.get_allow("run_command") == "always"
    assert config.set_allow("run_command", "ask") is True
    assert config.get_allow("run_command") == "ask"
    assert config.set_allow("run_command", "deny") is True
    assert config.get_allow("run_command") == "deny"
    config.clear_allow()
    assert config.get_allow("run_command") == "ask"


def test_allow_rejects_bad_tool_and_mode(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    assert config.set_allow("nope", "always") is False
    assert config.set_allow("run_command", "sometimes") is False
    assert config.get_allow_rules() == {}


def test_allow_all_fallback(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    config.set_allow("all", "always")
    assert config.get_allow("run_command") == "always"
    assert config.get_allow("edit_file") == "always"
    config.set_allow("edit_file", "deny")
    assert config.get_allow("edit_file") == "deny"
    assert config.get_allow("run_command") == "always"


def test_allow_persists(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    config.set_allow("edit_file", "deny")
    config._allow_rules = {}
    config._load_config()
    assert config.get_allow("edit_file") == "deny"
    config.clear_allow()


def test_check_persistent(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    assert appr.check_persistent("run_command") == "ask"
    config.set_allow("run_command", "deny")
    assert appr.check_persistent("run_command") == "deny"


def test_run_always_skips_confirm(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    config.set_allow("run_command", "always")
    seen = []
    monkeypatch.setattr(rc.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    out = rc.run_command("false")
    assert "Command failed" in out
    assert seen == []


def test_run_deny_never_prompts(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    config.set_allow("run_command", "deny")
    seen = []
    monkeypatch.setattr(rc.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    out = rc.run_command("rm -rf deny_me_xyz")
    assert out.startswith("Command cancelled by user")
    assert seen == []


def test_run_deny_does_not_block_safe(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(rc, "PROJECT_ROOT", tmp_path)
    config.set_allow("run_command", "deny")
    monkeypatch.setattr(rc.ui, "confirm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not prompt")))
    out = rc.run_command("ls")
    assert "cancelled" not in out.lower()


def test_write_always_shows_diff_skips_confirm(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "a.txt"
    target.write_text("orig")
    config.set_allow("write_file", "always")
    seen = []
    diffs = []
    monkeypatch.setattr(wf.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    monkeypatch.setattr(wf.ui, "show_diff", lambda d: diffs.append(d))
    assert wf.write_file(str(target), "new") == "Written."
    assert target.read_text() == "new"
    assert seen == []
    assert len(diffs) == 1


def test_write_deny(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "b.txt"
    target.write_text("orig")
    config.set_allow("write_file", "deny")
    monkeypatch.setattr(wf.ui, "confirm", lambda *a, **k: True)
    assert wf.write_file(str(target), "new").startswith("Write cancelled by user")
    assert target.read_text() == "orig"


def test_edit_allow_all(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "c.txt"
    target.write_text("hello world")
    config.set_allow("all", "always")
    seen = []
    monkeypatch.setattr(ef.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    assert ef.edit_file(str(target), "world", "there") == "Edited."
    assert target.read_text() == "hello there"
    assert seen == []


def test_apply_deny(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "d.txt"
    target.write_text("aaa")
    config.set_allow("apply_edits", "deny")
    monkeypatch.setattr(ae.ui, "confirm", lambda *a, **k: True)
    out = ae.apply_edits([{"path": str(target), "old_text": "aaa", "new_text": "bbb"}])
    assert out.startswith("Edits cancelled by user")
    assert target.read_text() == "aaa"


def test_commit_deny_and_always(monkeypatch, tmp_path):
    _tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(gc.git, "diff_text", lambda *a, **k: (True, "diff body"))
    monkeypatch.setattr(gc.git, "commit", lambda *a, **k: (True, "committed"))
    monkeypatch.setattr(gc.ui, "show_diff", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(gc.ui, "confirm", lambda *a, **k: seen.append(a) or True)
    config.set_allow("git_commit", "deny")
    assert gc.git_commit("msg").startswith("Commit cancelled by user")
    assert seen == []
    config.set_allow("git_commit", "always")
    seen.clear()
    assert gc.git_commit("msg") == "committed"
    assert seen == []
