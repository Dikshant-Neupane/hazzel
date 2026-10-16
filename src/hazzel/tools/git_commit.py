from .. import git
from .. import ui
from .approvals import check as _approval_check
from .approvals import check_persistent as _persistent_check
from .approvals import remember as _approval_remember
from .approvals import repeat_denial as _repeat_denial
from .approvals import sha_key


def _persistent_mode():
    try:
        return _persistent_check("git_commit")
    except Exception:
        return "ask"


def _approval_key(message, files):
    scope = ", ".join(files) if files else "all changes"
    return sha_key("git_commit", message or "", scope)


def _finish(ok, out):
    """Return the commit output, firing the one-time star ask on success.

    A landed commit is the one moment the user has already decided Hazzel is
    worth keeping, so that is where the ask goes. ``claim()`` returns True at
    most once per machine and never raises, so this is silent forever after.
    """
    if ok:
        try:
            from .. import ui as _ui

            if _ui.is_print_mode():
                return out
            from .. import star_ask

            if star_ask.claim():
                ui.show_star_ask()
        except Exception:
            pass
    return out


def git_commit(message=None, files=None):
    if isinstance(files, str):
        files = [files] if files.strip() else None
    if files is not None and not isinstance(files, list):
        return "Tool error: files must be a list of paths."
    ok, preview = git.diff_text(False, ".")
    if not ok:
        return preview
    if preview.strip() in ("No changes.", "(clean)"):
        return "Nothing to commit — working tree clean."
    persistent = _persistent_mode()
    if persistent == "deny":
        return _repeat_denial("Commit cancelled by user")
    always = persistent == "always"
    suggest_mode = not (message or "").strip() or (message or "").strip().lower() in ("suggest", "auto")
    if suggest_mode:
        from ..git_suggest import suggest_message

        _, status_out, _ = git.status_porcelain()
        try:
            ui.show_loader("Drafting commit message…")
            suggestion, fallback = suggest_message(preview, status_out)
        finally:
            ui.end_turn()
        ui.show_git_suggest(suggestion, fallback)
        action = ui.prompt_suggest_action()
        if action == "n":
            return "Commit cancelled by user"
        if action == "e":
            edited = ui.prompt_suggest_edit(suggestion)
            if edited is None:
                return "Commit cancelled by user"
            message = edited.strip()
            if not message:
                return "Commit cancelled by user"
            if len(message) > 500:
                return "Tool error: commit message too long (>500 chars)."
            scope = ", ".join(files) if files else "all changes"
            key = _approval_key(message, files)
            if always:
                _approval_remember(key, True)
            else:
                prior = _approval_check(key)
                if prior is False:
                    return _repeat_denial("Commit cancelled by user")
                if prior is None:
                    approved = ui.confirm(f"Commit {scope} with message: {message!r}?")
                    _approval_remember(key, approved)
                    if not approved:
                        return "Commit cancelled by user"
        else:
            message = suggestion
        return _finish(*git.commit(message, files))
    if len(message.strip()) > 500:
        return "Tool error: commit message too long (>500 chars)."
    scope = ", ".join(files) if files else "all changes"
    key = _approval_key(message, files)
    if always:
        ui.show_diff(preview)
        _approval_remember(key, True)
    else:
        prior = _approval_check(key)
        if prior is False:
            return _repeat_denial("Commit cancelled by user")
        if prior is None:
            ui.show_diff(preview)
            approved = ui.confirm(f"Commit {scope} with message: {message!r}?")
            _approval_remember(key, approved)
            if not approved:
                return _repeat_denial("Commit cancelled by user")
    return _finish(*git.commit(message, files))
