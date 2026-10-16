import importlib
import io

import pytest
from rich.console import Console

from hazzel import config, star_ask
from hazzel.tools.git_commit import _finish
from hazzel.ui import _state as _st


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "cfg")
    for name in star_ask.OPT_OUT_ENVS:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(star_ask)


@pytest.fixture
def console():
    prev = _st.console
    buf = io.StringIO()
    _st.console = Console(file=buf, force_terminal=True, width=100)
    yield buf
    _st.console = prev


def test_claim_fires_exactly_once():
    assert star_ask.claim() is True
    assert star_ask.claim() is False
    assert star_ask.claim() is False


def test_already_asked_reflects_state():
    assert star_ask.already_asked() is False
    star_ask.claim()
    assert star_ask.already_asked() is True


def test_reset_rearms():
    star_ask.claim()
    star_ask.reset()
    assert star_ask.already_asked() is False
    assert star_ask.claim() is True


@pytest.mark.parametrize(
    "value,expected",
    [("1", True), ("true", True), ("yes", True), ("on", True),
     ("0", False), ("false", False), ("no", False), ("off", False)],
)
def test_opt_out_env_truthiness(monkeypatch, value, expected):
    monkeypatch.setenv("HAZZEL_NO_STAR_NAG", value)
    assert star_ask.opted_out() is expected


def test_opt_out_suppresses_ask(monkeypatch):
    monkeypatch.setenv("HAZZEL_NO_STAR_NAG", "1")
    assert star_ask.claim() is False
    assert star_ask.already_asked() is True


def test_legacy_opt_out_env_still_honored(monkeypatch):
    monkeypatch.setenv("HAZZEL_NO_NAG", "1")
    assert star_ask.opted_out() is True
    assert star_ask.claim() is False


def test_corrupt_state_file_is_survivable():
    star_ask._state_path().parent.mkdir(parents=True, exist_ok=True)
    star_ask._state_path().write_text("{not json", encoding="utf-8")
    assert star_ask.already_asked() is False
    assert star_ask.claim() is True


def test_finish_fires_ask_on_success(console):
    out = _finish(True, "[main abc123] feat: thing")
    assert out == "[main abc123] feat: thing"
    assert "star" in console.getvalue()
    assert star_ask.already_asked() is True


def test_finish_does_not_fire_on_failure(console):
    out = _finish(False, "fatal: not a git repository")
    assert out == "fatal: not a git repository"
    assert console.getvalue() == ""
    assert star_ask.already_asked() is False


def test_finish_fires_only_once(console):
    _finish(True, "first")
    console.truncate(0)
    console.seek(0)
    _finish(True, "second")
    assert console.getvalue() == ""


def test_finish_silent_in_print_mode(console):
    from hazzel import ui

    prev = ui.is_print_mode()
    ui.set_print_mode(True)
    try:
        out = _finish(True, "[main abc123] feat: thing")
    finally:
        ui.set_print_mode(prev)
    assert out == "[main abc123] feat: thing"
    assert console.getvalue() == ""
    assert star_ask.already_asked() is False


def test_finish_silent_when_opted_out(console, monkeypatch):
    monkeypatch.setenv("HAZZEL_NO_STAR_NAG", "1")
    out = _finish(True, "[main abc123] feat: thing")
    assert out == "[main abc123] feat: thing"
    assert console.getvalue() == ""


def test_ask_renders_clickable_link(console):
    star_ask.claim()
    from hazzel import ui

    ui.show_star_ask()
    out = console.getvalue()
    assert "\x1b]8;" in out
    assert star_ask.REPO_URL in out


def test_ask_respects_no_color(console, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    star_ask.claim()
    from hazzel import ui

    ui.show_star_ask()
    out = console.getvalue()
    assert "\x1b]8;" not in out
    assert star_ask.DISPLAY_URL in out


def test_help_star_line_is_clickable(console):
    from hazzel.ui import help_docs

    console.getvalue()
    _st.console.print(help_docs._star_line())
    out = console.getvalue()
    assert "\x1b]8;" in out
    assert star_ask.REPO_URL in out


def test_help_star_line_plain_under_no_color(console, monkeypatch):
    from hazzel.ui import help_docs

    monkeypatch.setenv("NO_COLOR", "1")
    _st.console.print(help_docs._star_line())
    out = console.getvalue()
    assert "\x1b]8;" not in out
    assert star_ask.DISPLAY_URL in out


def test_message_carries_the_url():
    assert star_ask.DISPLAY_URL in star_ask.message()
