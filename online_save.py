"""Player saves in Supabase for Arena of Makers.

Arena of Makers is exclusively online, and everything lives
in ONE shared table, called players. One row per player, and
all of that player's account data is in that one row:
username, gender, kind (robot or chef), player code, the
whole fighter as JSON, and that player's game actions as a
JSON list. There are no separate fighters or game-events
tables.

The game talks to Supabase with the publishable key from the
player's own .env file, in the apikey header and as a Bearer
token, exactly as Supabase's REST API expects. The key is never
logged, never printed, and never sent anywhere else.

There is no local save file at all: no arena_save.json, no
local JSON of any kind. The Supabase row is the only save.
If the online save fails, the game says so in plain words
and in arena_log.txt, and the fighter stays in memory only
until the game closes. It never writes a local file to cover
for a failed online save.
"""

import datetime
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

TABLE = "players"


def _headers(config):
    return {
        "apikey": config["key"],
        "Authorization": "Bearer " + config["key"],
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _table_missing(error):
    """True when an HTTP error is about a missing table, not a bad key."""
    try:
        body = error.read().decode("utf-8", "replace")
    except Exception:
        return False
    return TABLE in body and ("PGRST" in body or "does not exist" in body)


def _request(config, path, method="GET", body=None):
    url = config["url"].rstrip("/") + "/rest/v1/" + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in _headers(config).items():
        request.add_header(key, value)
    return request


def save_fighter(fighter, config, timeout=15):
    """Save one fighter to that player's row in the shared
    players table. Returns (ok, message). ok is True when
    Supabase stored it. message is a plain-words line for the
    log, never with the key in it."""
    code = fighter.get("player_code")
    if not code:
        return False, "No player code, so the fighter has no row to save to."
    request = _request(
        config,
        TABLE + "?player_code=eq." + urllib.parse.quote(code),
        method="PATCH",
        body={
            "fighter": fighter,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            logging.info(
                "Online save: fighter %s saved to the shared players table.",
                fighter["name"],
            )
            return True, "Saved online to Supabase."
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            logging.error(
                "Online save failed: Supabase rejected the key (HTTP %d).",
                error.code,
            )
            return False, "Supabase rejected the key."
        if _table_missing(error):
            logging.error(
                "Online save failed: the shared players table is not "
                "set up in Supabase yet. Run supabase_schema.sql."
            )
            return False, "The shared players table is not set up in Supabase yet."
        logging.error(
            "Online save failed: Supabase answered HTTP %d.", error.code
        )
        return False, "Supabase answered with an error while saving."
    except Exception as error:
        logging.error(
            "Online save failed: could not reach Supabase (%s: %s).",
            type(error).__name__, error,
        )
        return False, "Could not reach Supabase to save online."


def load_fighter(config, name=None, player_code=None, timeout=15):
    """Load a fighter from that player's row in the shared
    players table. Returns (fighter, error). fighter is the
    fighter dict, or None when there is no online save yet.
    error is a plain-words message when something went wrong,
    else None. With a player code, that player's fighter is
    loaded; otherwise the most recently saved fighter is loaded.
    """
    if player_code:
        query = "?select=fighter&player_code=eq.%s&limit=1" % urllib.parse.quote(
            player_code
        )
    elif name:
        query = "?select=fighter&fighter->>name=eq.%s&limit=1" % urllib.parse.quote(name)
    else:
        query = "?select=fighter&order=updated_at.desc&limit=1"
    request = _request(config, TABLE + query)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            logging.error(
                "Online load failed: Supabase rejected the key (HTTP %d).",
                error.code,
            )
            return None, "Supabase rejected the key."
        if _table_missing(error):
            return None, "The shared players table is not set up in Supabase yet."
        logging.error(
            "Online load failed: Supabase answered HTTP %d.", error.code
        )
        return None, "Supabase answered with an error while loading."
    except Exception as error:
        logging.error(
            "Online load failed: could not reach Supabase (%s: %s).",
            type(error).__name__, error,
        )
        return None, "Could not reach Supabase to load online."
    if not rows:
        return None, None
    fighter = rows[0].get("fighter")
    if not isinstance(fighter, dict) or "name" not in fighter:
        return None, "The online save was not a fighter."
    logging.info(
        "Online load: fighter %s loaded from the shared players table.",
        fighter["name"],
    )
    return fighter, None


def list_players(config, timeout=15):
    """List everyone in the one shared players table, so
    players can look each other up, fight each other, and
    help each other, all from the same place. Returns
    (players, error). Each player is their whole row:
    username, player_code, gender, kind, fighter, and
    when they were last updated. No key is ever in it."""
    request = _request(
        config,
        TABLE + "?select=username,player_code,gender,kind,fighter,updated_at"
        + "&order=updated_at.desc&limit=50",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return None, "Supabase rejected the key."
        if _table_missing(error):
            return None, "The shared players table is not set up in Supabase yet."
        return None, "Supabase answered with an error while listing players."
    except Exception as error:
        logging.error(
            "List players failed: could not reach Supabase (%s: %s).",
            type(error).__name__, error,
        )
        return None, "Could not reach Supabase to list players."
    return rows, None


def log_action(config, fighter_name, action, detail=None, player_code=None, timeout=5):
    """Send one game action to the server, in that player's row
    in the shared players table: the action is added to their
    events list there. action is a short name like "fight",
    "key_press" or "upgrade_weapon". detail is a small dict,
    for example {"key": "f", "tab": "Combat"} or {"won": true}.
    Returns True when the send was started. A failed send
    never raises and never stops the game: it is logged in
    arena_log.txt and the game carries on. The key is never
    in the detail, the log, or the request body."""
    import threading

    def _send():
        if not player_code:
            return
        try:
            with urllib.request.urlopen(
                _request(
                    config,
                    TABLE + "?select=events&player_code=eq."
                    + urllib.parse.quote(player_code) + "&limit=1",
                ),
                timeout=timeout,
            ) as response:
                rows = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            logging.warning(
                "Online action log failed for %s (%s: %s).",
                action, type(error).__name__, error,
            )
            return
        if not rows:
            return
        events = rows[0].get("events") or []
        if not isinstance(events, list):
            events = []
        events.append(
            {
                "action": action,
                "detail": detail or {},
                "fighter_name": fighter_name,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )
        events = events[-200:]
        try:
            with urllib.request.urlopen(
                _request(
                    config,
                    TABLE + "?player_code=eq." + urllib.parse.quote(player_code),
                    method="PATCH",
                    body={"events": events},
                ),
                timeout=timeout,
            ) as response:
                response.read()
        except Exception as error:
            logging.warning(
                "Online action log failed for %s (%s: %s).",
                action, type(error).__name__, error,
            )

    try:
        thread = threading.Thread(target=_send, name="arena-online-log", daemon=True)
        thread.start()
        return True
    except Exception:
        return False


def export_user_data(config, fighter, path=None, timeout=15):
    """Export one player's data to a JSON file on this computer.

    This is the escape hatch if something goes wrong online:
    it fetches that player's whole row from the one shared
    players table — their account, their fighter, and their
    own game actions — and writes it, with the local fighter,
    to a file next to the game, like
    arena_export_Bolt_2026-11-17.json. Only that player's
    row is fetched, never anyone else's. Returns (path, error).
    The key is never written to the export file.
    """
    if path is None:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = "arena_export_%s_%s.json" % (fighter["name"], stamp)
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, filename)
    code = fighter.get("player_code")
    online_row = None
    row_error = None
    if not code:
        row_error = "No player code, so there is no online row to export."
    else:
        request = _request(
            config,
            TABLE + "?select=username,player_code,gender,kind,fighter,events"
            + "&player_code=eq." + urllib.parse.quote(code) + "&limit=1",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                rows = json.loads(response.read().decode("utf-8"))
            online_row = rows[0] if rows else None
            if online_row is None:
                row_error = "No online row for that player code yet."
        except Exception as error:
            row_error = "Could not fetch the online row (%s)." % type(error).__name__
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
