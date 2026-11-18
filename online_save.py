"""Talking to the Arena of Makers server, in Supabase.

Arena of Makers is exclusively online, and the server is the
only judge of what a fighter has. The game cannot read or
write the players table at all. It can only call the arena_*
functions set up by supabase_schema.sql, and the server runs
every game rule itself: fights, dice rolls, experience,
levels, credits, upgrade costs and timers. The game shows
what the server sends back. That is what stops cheating:
changing the game's code or memory changes nothing on the
server.

Every call carries:
- the publishable key from the player's own .env file, in
  the apikey header and as a Bearer token, as Supabase's
  REST API expects. It is public by design.
- the session token from signing in, in config["session"].
  It lives in memory only, is never written to disk, never
  logged, and ends when the game closes.

Nothing in this module ever logs a key, a session token or
a password. Log lines name only the function called and
what went wrong, in plain words.

There is no local save file at all. If the server cannot be
reached, the game says so in plain words and in
arena_log.txt.
"""

import datetime
import json
import logging
import os
import threading
import urllib.error
import urllib.request


SCHEMA_MISSING = (
    "The game's server is not set up yet. Run supabase_schema.sql "
    "in Supabase, SQL Editor."
)


def _headers(config):
    return {
        "apikey": config["key"],
        "Authorization": "Bearer " + config["key"],
        "Content-Type": "application/json",
    }


def rpc(config, name, args, timeout=15):
    """Call one arena_* server function. Returns (data, error).

    data is the function's JSON answer when it worked, else
    None. error is a plain-words message, else None. A
    plain-words problem the server reports, like "That upgrade
    costs 38 credits", comes back as error, with data still set
    so the caller can see the fighter the server sent along.
    The args, which may hold a password or session token, are
    never logged.
    """
    url = config["url"].rstrip("/") + "/rest/v1/rpc/" + name
    body = json.dumps(args).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    for key, value in _headers(config).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            logging.error("Server call %s failed: Supabase rejected the key (HTTP %d).",
                          name, error.code)
            return None, "Supabase rejected the key."
        if error.code == 404:
            logging.error("Server call %s failed: the function is missing. "
                          "Run supabase_schema.sql.", name)
            return None, SCHEMA_MISSING
        logging.error("Server call %s failed: Supabase answered HTTP %d.",
                      name, error.code)
        return None, "The server answered with an error."
    except Exception as error:
        logging.error("Server call %s failed: could not reach Supabase (%s).",
                      name, type(error).__name__)
        return None, "Could not reach the server. Check your internet connection."
    if isinstance(data, dict) and data.get("error"):
        if data.get("signed_out"):
            logging.warning("Server call %s: the session has ended.", name)
        return data, data["error"]
    return data, None


def _session_args(config):
    return {"p_token": config.get("session") or ""}


def refresh_state(config, timeout=15):
    """Ask the server for the fighter as it is now. The server
    finishes any upgrade or repair whose time is up. Returns
    (fighter, messages, error)."""
    data, error = rpc(config, "arena_state", _session_args(config), timeout)
    if error:
        return None, [], error
    return data.get("fighter"), data.get("messages") or [], None


def fight(config, opponent_code=None, timeout=15):
    """Fight one creature, on the server. Returns (result,
    error). result has won, lines, xp, credits, levels_gained,
    messages and the fighter as the server now has it."""
    args = _session_args(config)
    args["p_opponent_code"] = opponent_code
    data, error = rpc(config, "arena_fight", args, timeout)
    if error:
        return None, error
    return data, None


def start_upgrade(config, slot, timeout=15):
    """Start a timed upgrade of weapon or armor, on the server.
    Returns (fighter, messages, error). On a plain-words
    problem like too few credits, fighter is still the server's
    copy when it sent one."""
    args = _session_args(config)
    args["p_slot"] = slot
    data, error = rpc(config, "arena_start_upgrade", args, timeout)
    data = data or {}
    return data.get("fighter"), data.get("messages") or [], error


def spend_stat(config, stat, timeout=15):
    """Spend one banked stat point, on the server. The game
    sends only the session token plus one stat name. Returns
    (fighter, message, messages, error). message is the
    plain-words line to speak, with how many stat points are
    left. One point per call: to spend several points, call
    again on the same stat line."""
    args = _session_args(config)
    args["p_stat"] = stat
    data, error = rpc(config, "arena_spend_stat", args, timeout)
    data = data or {}
    return (data.get("fighter"), data.get("message"),
            data.get("messages") or [], error)


def respec_stats(config, timeout=15):
    """Reset all 5 stats on the server, refunding every spent
    point. The first respec is free; later ones cost 100
    credits. Returns (fighter, message, messages, error)."""
    data, error = rpc(config, "arena_respec", _session_args(config), timeout)
    data = data or {}
    return (data.get("fighter"), data.get("message"),
            data.get("messages") or [], error)


def max_upgrade(config, slot, timeout=15):
    """Start a max-affordable upgrade queue on the server: as
    many levels as the credits and the 4-hour cap allow, with
    the full cost deducted up front. The game must confirm
    first (see game_logic.max_affordable). Returns (fighter,
    message, messages, error)."""
    args = _session_args(config)
    args["p_slot"] = slot
    data, error = rpc(config, "arena_max_upgrade", args, timeout)
    data = data or {}
    return (data.get("fighter"), data.get("message"),
            data.get("messages") or [], error)


def set_voice(config, gender, timeout=15):
    """Change the voice setting. Returns (fighter, error)."""
    args = _session_args(config)
    args["p_gender"] = gender
    data, error = rpc(config, "arena_set_voice", args, timeout)
    if error:
        return None, error
    return data.get("fighter"), None


def list_online_players(config, timeout=15):
    """Players who are online right now, other than you.
    Returns (players, error). Each player has username,
    player_code, kind and level."""
    data, error = rpc(config, "arena_list_online", _session_args(config), timeout)
    if error:
        return None, error
    return data.get("players") or [], None


def _in_background(target, thread_name):
    try:
        thread = threading.Thread(target=target, name=thread_name, daemon=True)
        thread.start()
        return True
    except Exception:
        return False


def heartbeat(config, timeout=10):
    """Tell the server, in the background, that this player is
    still online. Never blocks or stops the game."""
    return _in_background(
        lambda: rpc(config, "arena_state", _session_args(config), timeout),
        "arena-heartbeat",
    )


def log_action(config, fighter_name, action, detail=None, player_code=None, timeout=5):
    """Report one game action, like a key press or a setting
    change, in the background. The server keeps it in the
    player's own history, marked as from the game. It never
    changes the fighter. Fights and upgrades are recorded by
    the server itself, so they are not sent from here.
    fighter_name and player_code are accepted for older
    callers; the server knows who is signed in from the
    session. A failed send never stops the game."""
    args = _session_args(config)
    args["p_action"] = action
    args["p_detail"] = detail or {}
    return _in_background(
        lambda: rpc(config, "arena_log_action", args, timeout),
        "arena-online-log",
    )


def sign_out(config, timeout=5):
    """End the session on the server, so this player shows as
    offline at once. Returns True when the server agreed."""
    if not config or not config.get("session"):
        return False
    _data, error = rpc(config, "arena_sign_out", _session_args(config), timeout)
    config["session"] = None
    return error is None


def export_user_data(config, fighter, path=None, timeout=15):
    """Export this player's own data to a JSON file next to
    the game, like arena_export_Bolt_2026-11-17.json.

    It holds what the server has for this player: account,
    fighter and game history. Never the password, its hash,
    the key, or the session token, and never anyone else's
    data. Returns (path, error).
    """
    if path is None:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = "arena_export_%s_%s.json" % (fighter["name"], stamp)
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, filename)
    online_row, row_error = rpc(config, "arena_export", _session_args(config), timeout)
    if row_error:
        online_row = None
        logging.warning("Export: %s", row_error)
    export = {
        "fighter_name": fighter["name"],
        "exported_at": datetime.datetime.now().isoformat(),
        "local_fighter": fighter,
        "online_row": online_row,
        "online_row_error": row_error,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(export, handle, indent=2, sort_keys=True)
    logging.info("Export: user data written to %s.", path)
    return path, None
