"""Player accounts for Arena of Makers.

On first launch, after the online key check, the game asks
the player to make an account: a username, and a player code.
The player code is picked by the player, on first launch,
when they make their account. They type their own code, or
press "Make a code for me" and the game suggests one: six
letters and numbers that are easy to read out with a screen
reader, with no confusing characters in it: no 0, no O, no 1,
no I, no L. For example: K7M2Q9. A code is 4 to 8 letters
and numbers, so a player can pick something they will
remember, like their initials and a number.

Friends look a player up by that code, not by their username:
the code is unique, and a username can change. The account
lives only in Supabase, in the one shared players table, so
it is the same account on any computer. The game keeps no
local copy of it: there is no local JSON file at all. Every
launch, the player types their username and player code,
and the game looks the account up online. That is also why
the game cannot start without the key in .env: with no key,
there is nowhere to look the account up, and no local file
to fall back to.

No password is involved. The publishable key in .env is what
lets the game talk to Supabase; the player code is only a
lookup code, not a secret and not a password.
"""

import json
import logging
import os
import random
import string
import urllib.error
import urllib.request

# Easy to read out: no 0/O, no 1/I/L.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6


def generate_player_code(rng=None):
    """Suggest a new six-character player code."""
    if rng is None:
        rng = random.SystemRandom()
    return "".join(rng.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def validate_player_code(code):
    """Plain-words reason a chosen code is not usable, or None
    when it is fine. A code is 4 to 8 letters and numbers."""
    code = (code or "").strip().upper().replace("-", "").replace(" ", "")
    if not code:
        return "a player code is missing"
    if len(code) < 4 or len(code) > 8:
        return "a player code is 4 to 8 letters and numbers"
    if not code.isalnum():
        return "a player code is only letters and numbers"
    return None


def clean_player_code(code):
    return (code or "").strip().upper().replace("-", "").replace(" ", "")


def _headers(config):
    return {
        "apikey": config["key"],
        "Authorization": "Bearer " + config["key"],
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def create_account(config, username, player_code=None, gender=None, kind=None, timeout=15):
    """Create an account online and return (account, error).

    account is {"username": ..., "player_code": ...,
    "gender": ..., "kind": ...} when it worked, else None.
    gender and kind, when given, are stored in the same row
    in the one shared players table, with the username and
    the player code. error is a plain-words message when it
    did not work, else None. A taken username or a taken player
    code is reported in plain words, so the player can pick a
    different one. When no code is given, a code is suggested
    and a taken one is just retried with a new code, up to
    five times.
    """
    username = (username or "").strip()
    if not username:
        return None, "Give yourself a username first."
    if len(username) > 30:
        return None, "Pick a username no longer than 30 letters."
    chosen = clean_player_code(player_code) if player_code else ""
    if player_code:
        code_error = validate_player_code(chosen)
        if code_error:
            return None, "That code does not work: %s." % code_error
    url = config["url"].rstrip("/") + "/rest/v1/players"
    for _attempt in range(5):
        code = chosen or generate_player_code()
        row = {"player_code": code, "username": username,
               "fighter": {}, "events": []}
        if gender:
            row["gender"] = gender
        if kind:
            row["kind"] = kind
        body = json.dumps(row).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        for key, value in _headers(config).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read()
            account = {"username": username, "player_code": code}
            if gender:
                account["gender"] = gender
            if kind:
                account["kind"] = kind
            logging.info(
                "Account created online: username %s, player code %s.",
                username, code,
            )
            return account, None
        except urllib.error.HTTPError as error:
            if error.code == 409:
                # A taken code is retried; a taken username is
                # told to the player. Supabase's message says
                # which column clashed.
                try:
                    detail = error.read().decode("utf-8", "replace")
                except Exception:
                    detail = ""
                if "username" in detail:
                    return None, (
                        "That username is already taken. "
                        "Pick a different username."
                    )
                if "player_code" in detail:
                    if chosen:
                        return None, (
                            "That player code is already taken. "
                            "Pick a different code, or press "
                            "Make a code for me."
                        )
                    continue
                continue
            if error.code in (401, 403):
                return None, "Supabase rejected the key."
            try:
                detail = error.read().decode("utf-8", "replace")
            except Exception:
                detail = ""
            if "players" in detail:
                return None, "The players table is not set up in Supabase yet."
            return None, "Supabase answered with an error while making the account."
        except Exception as error:
            logging.error(
                "Account creation failed: could not reach Supabase (%s: %s).",
                type(error).__name__, error,
            )
            return None, "Could not reach Supabase to make the account."
    return None, "I could not make a free player code. Try again."


def lookup_player(config, player_code, timeout=15):
    """Look a player up by their player code.

    Returns (account, error). account is {"username": ...,
    "player_code": ..., "fighter": ...} when that code exists,
    else None. The fighter is included so a player can see
    the person they found: their level, wins, and losses,
    and can fight them or help them from the same shared row.
    error is a plain-words message when something went wrong,
    else None.
    """
    code = clean_player_code(player_code)
    if not code:
        return None, "Type a player code first."
    url = (
        config["url"].rstrip("/")
        + "/rest/v1/players?select=username,player_code,gender,kind,fighter"
        + "&player_code=eq." + code
        + "&limit=1"
    )
    request = urllib.request.Request(url)
    request.add_header("apikey", config["key"])
    request.add_header("Authorization", "Bearer " + config["key"])
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return None, "Supabase rejected the key."
        return None, "Supabase answered with an error while looking up that code."
    except Exception as error:
        logging.error(
            "Player lookup failed: could not reach Supabase (%s: %s).",
            type(error).__name__, error,
        )
        return None, "Could not reach Supabase to look up that code."
    if not rows:
        return None, "No player has that code. Check the code and try again."
    row = rows[0]
    return {
        "username": row.get("username"),
        "player_code": row.get("player_code"),
        "gender": row.get("gender"),
        "kind": row.get("kind"),
        "fighter": row.get("fighter") or {},
    }, None
