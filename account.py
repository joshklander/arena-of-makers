"""Player accounts for Arena of Makers.

Every launch, after the online key check, the player signs in
with a username, a player code and a password. When the code
has no account yet, the same details make a new one.

The player code is picked by the player when they make their
account. They type their own code, or press "Make a code for
me" and the game suggests one. A code is exactly 4 digits,
like 4827. Leading zeros count, so 0042 is a code too.

The player code is public. Friends look a player up by it.
The password is what proves who you are.

Password safety:
- The password box hides what is typed, so neither the
  screen nor a screen reader shows it.
- The password goes to the server once, over HTTPS, to sign
  in or make the account, and is then dropped. It is never
  saved on this computer, never logged, and never shown.
- The server never stores the password itself, only a bcrypt
  hash of it, and no server function ever sends that back.
- Five wrong tries lock the account for ten minutes.

Signing in gives back a session token. The game keeps it in
memory only, in config["session"], and it ends when the game
closes.
"""

import random

import online_save

_CODE_DIGITS = "0123456789"
_CODE_LENGTH = 4

PASSWORD_MIN = 8
PASSWORD_MAX = 72


def generate_player_code(rng=None):
    """Suggest a new 4-digit player code."""
    if rng is None:
        rng = random.SystemRandom()
    return "".join(rng.choice(_CODE_DIGITS) for _ in range(_CODE_LENGTH))


def clean_player_code(code):
    return (code or "").strip().upper().replace("-", "").replace(" ", "")


def validate_player_code(code):
    """Plain-words reason a chosen code is not usable, or None
    when it is fine. A code is exactly 4 digits."""
    code = clean_player_code(code)
    if not code:
        return "a player code is missing"
    if len(code) != _CODE_LENGTH or not all(c in _CODE_DIGITS for c in code):
        return "a player code is 4 digits, like 4827"
    return None


def validate_password(password):
    """Plain-words reason a new password is not usable, or None.
    Never repeats the password."""
    password = password or ""
    if len(password) < PASSWORD_MIN:
        return "Pick a password of at least %d characters." % PASSWORD_MIN
    if len(password.encode("utf-8")) > PASSWORD_MAX:
        return "Pick a password no longer than %d characters." % PASSWORD_MAX
    return None


def _session_from(data):
    """The parts of a sign-in answer the game keeps."""
    return {
        "token": data["token"],
        "remember_token": data.get("remember_token"),
        "account": data.get("account") or {},
        "fighter": data.get("fighter"),
        "messages": data.get("messages") or [],
    }


def resume(config, remember_token, timeout=15):
    """Sign in with a saved remember token, with no password.
    Returns (session, error, forget). session also holds a new
    remember_token to save in place of the old one. forget is
    True when the server says the saved token no longer works,
    so it should be removed from this computer."""
    data, error = online_save.rpc(config, "arena_resume", {
        "p_remember_token": remember_token or "",
    }, timeout)
    if error:
        return None, error, bool(data and data.get("forget"))
    return _session_from(data), None, False


def remember_this_computer(config, timeout=15):
    """Turn on keep me signed in, for the signed-in player.
    Returns (remember_token, error)."""
    data, error = online_save.rpc(config, "arena_remember", {
        "p_token": config.get("session") or "",
    }, timeout)
    if error:
        return None, error
    return data.get("remember_token"), None


def forget_this_computer(config, remember_token, timeout=15):
    """Turn off keep me signed in: the token stops working on
    the server. Returns True when the server agreed."""
    if not remember_token:
        return True
    _data, error = online_save.rpc(config, "arena_forget", {
        "p_remember_token": remember_token,
    }, timeout)
    return error is None


def sign_in(config, player_code, username, password, timeout=15):
    """Sign in. Returns (session, error, no_account).

    session is {"token", "account", "fighter", "messages"}
    when it worked, else None. no_account is True when nobody
    has that player code yet, so the caller can offer to make
    the account instead. error is a plain-words message.
    """
    data, error = online_save.rpc(config, "arena_sign_in", {
        "p_player_code": clean_player_code(player_code),
        "p_username": (username or "").strip(),
        "p_password": password or "",
    }, timeout)
    if error:
        return None, error, False
    if data.get("no_account"):
        return None, None, True
    return _session_from(data), None, False


def create_account(config, username, player_code=None, password=None,
                   gender=None, kind=None, timeout=15):
    """Make a new account, with its level 1 fighter, on the
    server. Returns (session, error), like sign_in. When no
    code is given, the server picks a free one."""
    username = (username or "").strip()
    if not username:
        return None, "Give yourself a username first."
    if len(username) > 30:
        return None, "Pick a username no longer than 30 letters."
    code = clean_player_code(player_code) if player_code else None
    if code:
        code_error = validate_player_code(code)
        if code_error:
            return None, "That code does not work: %s." % code_error
    password_error = validate_password(password)
    if password_error:
        return None, password_error
    data, error = online_save.rpc(config, "arena_create_account", {
        "p_username": username,
        "p_player_code": code,
        "p_password": password,
        "p_gender": gender,
        "p_kind": kind,
    }, timeout)
    if error:
        return None, error
    return _session_from(data), None


def lookup_player(config, player_code, timeout=15):
    """Look a player up by their player code. Needs a session.

    Returns (account, error). account is {"username",
    "player_code", "gender", "kind", "fighter"}, where the
    fighter holds only public parts: name, kind, level, wins,
    losses, and gear.
    """
    code = clean_player_code(player_code)
    if not code:
        return None, "Type a player code first."
    data, error = online_save.rpc(config, "arena_lookup_player", {
        "p_token": config.get("session") or "",
        "p_player_code": code,
    }, timeout)
    if error:
        return None, error
    return {
        "username": data.get("username"),
        "player_code": data.get("player_code"),
        "gender": data.get("gender"),
        "kind": data.get("kind"),
        "fighter": data.get("fighter") or {},
    }, None
