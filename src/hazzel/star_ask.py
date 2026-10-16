"""One-time star ask, fired at the moment of demonstrated value.

Most people who install Hazzel never star it, and the reason is simple:
nothing in the running program ever asks. This module is that ask, and it
fires at exactly one moment: after the agent lands its **first successful
commit**. The user just watched a diff get read back, a Conventional message
get drafted, and work land — the highest-satisfaction point in the product.

A previous nudge fired after five turns and read as nagging. The trigger was
the bug, not the ask: five turns in, the user is still deciding, which is the
worst possible moment to interrupt. After a successful commit they have
already decided.

Fires once per machine, then stays quiet forever. Opt out with
``HAZZEL_NO_STAR_NAG=1`` (or ``HAZZEL_NO_NAG=1``, the name the old nudge
used). Never called from ``hazzel -p`` — stdout stays clean for scripts.

State lives in ``~/.config/hazzel/star_ask.json``. Every failure path here is
silent: a read-only or broken config dir must never break a commit.
"""

import json
import os
import time

REPO_URL = "https://github.com/mukundzha/hazzel"
DISPLAY_URL = "github.com/mukundzha/hazzel"

STATE_FILENAME = "star_ask.json"
STATE_VERSION = 1

OPT_OUT_ENVS = ("HAZZEL_NO_STAR_NAG", "HAZZEL_NO_NAG")

_TRUTHY = {"1", "true", "yes", "on", "y"}


def opted_out():
    """True if the user asked to never be asked again."""
    for name in OPT_OUT_ENVS:
        raw = os.getenv(name)
        if raw is None:
            continue
        val = raw.strip().lower()
        if not val or val in ("0", "false", "no", "off", "n"):
            continue
        return True
    return False


def _state_path():
    from hazzel import config

    return config.CONFIG_DIR / STATE_FILENAME


def _read_state():
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def already_asked():
    """True once the ask has fired on this machine."""
    if opted_out():
        return True
    state = _read_state()
    if not state:
        return False
    return bool(state.get("asked_at"))


def claim():
    """Return True exactly once — the first successful commit claims the ask.

    Marks the state before returning so a second commit in the same session
    (or a crash mid-print) cannot re-arm it. Never raises.
    """
    try:
        if opted_out() or already_asked():
            return False
        _write_state()
        return True
    except Exception:
        return False


def _write_state():
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STATE_VERSION,
        "asked_at": time.time(),
        "repo": REPO_URL,
    }
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def reset():
    """Forget that the ask fired — re-arms it for the next commit."""
    try:
        path = _state_path()
        if path.exists():
            path.unlink()
    except OSError:
        pass


def message():
    """The one line shown after a successful commit."""
    return (
        "Committed. If Hazzel just earned its keep in your terminal, "
        f"a star helps the next person find it — {DISPLAY_URL}"
    )
