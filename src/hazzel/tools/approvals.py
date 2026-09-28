"""Per-turn approval memory: ask once, the decision sticks.

Without this, every model retry of an identical mutating call re-prompts the
user (`Allow? [y/N]` again and again). An approval runs without asking twice;
a denial fails fast with guidance instead of prompting again.

Memory is cleared at the start of every agent turn (a new user request gets a
fresh decision) and on conversation reset.
"""

_approved: set = set()
_denied: set = set()

_RETRY_NOTE = " (already decided — do not retry this; proceed without it or stop)"


def sha_key(kind, *parts):
    """Hashable approval key; long payloads (file contents, edit lists) hash down."""
    import hashlib
    import json

    digest = hashlib.sha1()
    for part in parts:
        if not isinstance(part, str):
            part = json.dumps(part, sort_keys=True, default=str)
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
    return (kind, digest.hexdigest())


def reset_approvals():
    """Clear remembered decisions (new turn / new conversation)."""
    _approved.clear()
    _denied.clear()


def check(key):
    """Return True (approved) / False (denied) / None (undecided)."""
    if key in _approved:
        return True
    if key in _denied:
        return False
    return None


def remember(key, approved):
    """Record the user's decision for this turn."""
    if approved:
        _approved.add(key)
    else:
        _denied.add(key)


def repeat_denial(base_message):
    """Instant denial for a previously denied call — no second prompt."""
    return str(base_message) + _RETRY_NOTE


def check_persistent(tool_name):
    """Persistent /allow rule for a tool: 'always' / 'deny' / 'ask'.

    Specific tool rule wins, then the global 'all' rule. Defaults to 'ask'.
    Lazy config import keeps tools importable without a config cycle.
    """
    try:
        from .. import config as _cfg

        return _cfg.get_allow(tool_name)
    except Exception:
        return "ask"
