import json

import pytest

from hazzel import session


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    assert session.save(messages, "sum", [{"tool": "read_file", "detail": "x", "success": True}], "hello", "hi there")
    loaded = session.load()
    assert loaded is not None
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    assert loaded["summary"] == "sum"
    assert loaded["trace"][0]["tool"] == "read_file"
    assert loaded["user_input"] == "hello"
    assert loaded["response"] == "hi there"


def test_system_message_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    session.save([{"role": "system", "content": "sys"}, {"role": "user", "content": "a"}])
    assert all(m["role"] != "system" for m in session.load()["messages"])


def test_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "nope.json")
    assert session.load() is None


def test_corrupt_file_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    monkeypatch.setattr(session, "session_path", lambda root=None: path)
    assert session.load() is None


def test_empty_messages_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"messages": []}))
    monkeypatch.setattr(session, "session_path", lambda root=None: path)
    assert session.load() is None


def test_rejects_bad_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    session.save([{"role": "system", "content": "s"}, {"role": "bogus", "content": "x"}, {"role": "user", "content": "ok"}])
    loaded = session.load()
    assert [m["role"] for m in loaded["messages"]] == ["user"]


def test_caps_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    monkeypatch.setattr(session, "MAX_MESSAGES", 3)
    messages = [{"role": "system", "content": "s"}] + [{"role": "user", "content": f"m{i}"} for i in range(10)]
    session.save(messages)
    assert len(session.load()["messages"]) == 3


def test_clear_removes_file(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    monkeypatch.setattr(session, "session_path", lambda root=None: path)
    session.save([{"role": "system", "content": "s"}, {"role": "user", "content": "a"}])
    assert path.exists()
    session.clear()
    assert not path.exists()
    session.clear()


def test_backup_and_load_backup(tmp_path, monkeypatch):
    main = tmp_path / "s.json"
    prev = tmp_path / "s.prev.json"
    monkeypatch.setattr(session, "session_path", lambda root=None: main)
    monkeypatch.setattr(session, "backup_path", lambda root=None: prev)
    assert session.backup() is False
    assert session.load_backup() is None
    session.save([{"role": "system", "content": "s"}, {"role": "user", "content": "keep me"}])
    assert session.backup() is True
    session.clear()
    assert session.load() is None
    restored = session.load_backup()
    assert [m["content"] for m in restored["messages"]] == ["keep me"]


def test_clear_backup_consumes_archive(tmp_path, monkeypatch):
    main = tmp_path / "s.json"
    prev = tmp_path / "s.prev.json"
    monkeypatch.setattr(session, "session_path", lambda root=None: main)
    monkeypatch.setattr(session, "backup_path", lambda root=None: prev)
    session.save([{"role": "system", "content": "s"}, {"role": "user", "content": "keep me"}])
    assert session.backup() is True
    session.clear_backup()
    assert session.load_backup() is None
    assert session.load() is not None
    session.clear_backup()


def test_backup_path_sits_beside_session(tmp_path):
    main = session.session_path(tmp_path / "proj")
    prev = session.backup_path(tmp_path / "proj")
    assert prev.parent == main.parent
    assert prev != main


def test_per_project_paths_differ(tmp_path):
    a = session.session_path(tmp_path / "proj-a")
    b = session.session_path(tmp_path / "proj-b")
    assert a != b
    assert a.parent == b.parent


# --- named sessions ---


def _msgs(tag):
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": f"hello {tag}"},
        {"role": "assistant", "content": f"hi {tag}"},
    ]


def test_named_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    assert session.save_named("Experiment", _msgs("a"), "sum-a", None, "hello a", "hi a")
    path = tmp_path / "s-experiment.json"
    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600
    loaded = session.load_named("experiment")
    assert loaded is not None
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    assert loaded["summary"] == "sum-a"


def test_named_bad_names(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    for bad in ["", "   ", "a/b", "a\\b", "..", "a..b", "x" * 41]:
        with pytest.raises(ValueError):
            session.save_named(bad, _msgs("x"))
    assert list(tmp_path.iterdir()) == []


def test_named_name_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    session.save_named("  My Experiment  ", _msgs("n"))
    listed = session.list_named()
    assert len(listed) == 1
    assert listed[0]["name"] == "my experiment"
    assert listed[0]["messages"] == 2
    assert listed[0]["saved_at"] > 0


def test_named_per_project_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "_session_dir", lambda: tmp_path)
    root_a, root_b = tmp_path / "projA", tmp_path / "projB"
    session.save_named("exp", _msgs("a"), root=root_a)
    session.save_named("exp", _msgs("b"), root=root_b)
    assert session.load_named("exp", root=root_a)["messages"][0]["content"] == "hello a"
    assert session.load_named("exp", root=root_b)["messages"][0]["content"] == "hello b"
    assert [e["name"] for e in session.list_named(root=root_a)] == ["exp"]
    assert [e["name"] for e in session.list_named(root=root_b)] == ["exp"]


def test_named_list_sorted_counts_and_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    session.save(_msgs("d"))
    session.save_named("beta", _msgs("b"))
    session.save_named("alpha", _msgs("a"))
    (tmp_path / "s-broken.json").write_text("{not json")
    listed = session.list_named()
    assert [(e["name"], e["messages"]) for e in listed] == [("alpha", 2), ("beta", 2)]
    assert all(e["saved_at"] > 0 for e in listed)


def test_named_leaves_default_slot_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    session.save(_msgs("d"))
    before = (tmp_path / "s.json").read_bytes()
    session.save_named("exp", _msgs("n"))
    assert (tmp_path / "s.json").read_bytes() == before
    assert session.load()["messages"][0]["content"] == "hello d"
    assert session.load_named("exp")["messages"][0]["content"] == "hello n"


def test_named_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "session_path", lambda root=None: tmp_path / "s.json")
    assert session.load_named("nope") is None
