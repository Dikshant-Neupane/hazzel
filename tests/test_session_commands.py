"""REPL wiring for /session save/list/restore (handler lives in __main__)."""

import hazzel.__main__ as main_mod
from hazzel import session, ui


def test_session_save_command_via_repl(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "_session_dir", lambda: tmp_path)
    inputs = iter(["/session save exp"])

    def fake_get_input(messages, prefill=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(ui, "get_input", fake_get_input)
    monkeypatch.setattr(ui, "show_welcome", lambda *args, **kwargs: None)
    saved = list(main_mod.messages)
    try:
        main_mod.messages.append({"role": "user", "content": "hello"})
        main_mod.main(argv=[])
        loaded = session.load_named("exp")
        assert loaded is not None
        assert loaded["messages"][0]["content"] == "hello"
    finally:
        main_mod.messages.clear()
        main_mod.messages.extend(saved)


def test_session_list_and_restore_commands_via_repl(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(session, "_session_dir", lambda: tmp_path)
    session.save_named("exp", [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}])
    inputs = iter(["/session list", "/session restore exp"])

    def fake_get_input(messages, prefill=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(ui, "get_input", fake_get_input)
    monkeypatch.setattr(ui, "show_welcome", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui, "show_history", lambda *args, **kwargs: None)
    saved = list(main_mod.messages)
    try:
        main_mod.main(argv=[])
        assert any(m.get("content") == "hi" for m in main_mod.messages)
    finally:
        main_mod.messages.clear()
        main_mod.messages.extend(saved)
