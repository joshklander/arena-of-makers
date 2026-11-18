"""Supabase online check for Arena of Makers.

Arena of Makers is an exclusively online game: player saves live
in Supabase, and the server runs the game rules. The game never asks for a
key in chat, and it never sends a key to Muse. Each player keeps
their own copy of a small file called .env next to the game, with
two lines in it:

    SUPABASE_URL=https://yurdzzinmibgnoanxtkm.supabase.co
    SUPABASE_PUBLISHABLE_KEY=sb_publishable_...

The project URL is the one for the Arena of Makers project. The
publishable key is the one from Project Settings, then API Keys.
It is NOT the secret key, and it is NOT a personal access token.

This module is the launch gate. Right when the game starts it
looks for that .env file, checks that both lines are there and in
the right shape, and says so in plain words when something is
missing or wrong. It never prints or logs the key itself, not
even part of it: a log line says only whether a key was found
and what shape it had.

A key in the right shape is not proof the server will accept it.
Use test_key.py to ping the server with the key, or watch
arena_log.txt after a save: a bad key is logged there as
"the Supabase key was rejected", never with the key in it.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request

ENV_FILENAME = ".env"
URL_KEY = "SUPABASE_URL"
KEY_KEY = "SUPABASE_PUBLISHABLE_KEY"

# A Supabase project URL is always https://<project-ref>.supabase.co
_URL_RE = re.compile(r"^https://[a-z0-9-]+\.supabase\.co/?$")


def default_env_path():
    """The .env file next to this module, so it sits next to the
    game and next to the exe when the game is bundled."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, ENV_FILENAME)


def load_dotenv(path=None):
    """Read a .env file into a dict. Missing file: empty dict.
    Lines are KEY=VALUE, with optional quotes around the value.
    Blank lines and lines starting with # are skipped."""
    if path is None:
        path = default_env_path()
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'").strip()
            if key:
                values[key] = value
    return values


def _key_shape_error(key):
    """Plain-words reason a publishable key is in the wrong shape,
    or None when the shape looks right. Never echoes the key."""
    if not key:
        return "the publishable key is missing"
    if key.startswith("sb_publishable_"):
        if len(key) < 30:
            return "the publishable key is too short to be a real key"
        return None
    if key.startswith("eyJ"):
        # Legacy anon key: a JWT, three base64 parts.
        if len(key) < 50 or key.count(".") != 2:
            return "the publishable key does not look like a Supabase key"
        return None
    return (
        "the publishable key does not look like a Supabase publishable "
        "key: it should start with sb_publishable_ or with eyJ"
    )


def check_online_config(path=None):
    """Check the .env file at launch.

    Returns (config, error). config is {"url": ..., "key": ...}
    when both lines are present and in the right shape, else None.
    error is a plain-words message for the player when the check
    fails, else None. The key is never in the error, and never
    in the log: the log says only which line was wrong.
    """
    if path is None:
        path = default_env_path()
    if not os.path.exists(path):
        logging.error(
            "Online check failed: no .env file next to the game (%s).",
            path,
        )
        return None, (
            "Arena of Makers is online-only, and I could not find "
            "your .env file next to the game.\n\n"
            "Make a file called .env in the game folder, with two lines:\n"
            "SUPABASE_URL=https://yurdzzinmibgnoanxtkm.supabase.co\n"
            "SUPABASE_PUBLISHABLE_KEY=your publishable key\n\n"
            "Get the publishable key from Supabase, Project Settings, "
            "then API Keys. Do not use the secret key."
        )
    values = load_dotenv(path)
    url = (values.get(URL_KEY) or "").strip()
    key = (values.get(KEY_KEY) or "").strip()
    if not url:
        logging.error("Online check failed: SUPABASE_URL is missing from .env.")
        return None, (
            "Arena of Makers is online-only, and your .env file is "
            "missing SUPABASE_URL.\n\n"
            "Add this line to .env:\n"
            "SUPABASE_URL=https://yurdzzinmibgnoanxtkm.supabase.co"
        )
    if not _URL_RE.match(url):
        logging.error(
            "Online check failed: SUPABASE_URL is not a Supabase project URL."
        )
        return None, (
            "Arena of Makers is online-only, and SUPABASE_URL in your "
            ".env file does not look like a Supabase project URL.\n\n"
            "It should look like this:\n"
            "SUPABASE_URL=https://yurdzzinmibgnoanxtkm.supabase.co"
        )
    shape_error = _key_shape_error(key)
    if shape_error:
        logging.error("Online check failed: %s.", shape_error)
        return None, (
            "Arena of Makers is online-only, and %s.\n\n"
            "In your .env file, set SUPABASE_PUBLISHABLE_KEY to the "
            "publishable key from Supabase, Project Settings, then "
            "API Keys. Do not use the secret key, and do not use a "
            "personal access token here." % shape_error
        )
    logging.info(
        "Online check passed: Supabase URL is a project URL and a "
        "publishable key is present in the right shape."
    )
    return {"url": url.rstrip("/"), "key": key}, None


def test_connection(config, timeout=15):
    """Ping the Arena of Makers server with the key from .env.

    Returns (ok, message). It calls the server's arena_state
    function with no session, which only answers "signed out",
    so it reads and changes nothing. A 401 or 403 means the key
    was rejected. A 404 means the key works but the server
    functions are not set up yet. A network error means the
    game is offline. The key is never in the message or the log.
    """
    url = config["url"].rstrip("/") + "/rest/v1/rpc/arena_state"
    request = urllib.request.Request(
        url, data=json.dumps({"p_token": ""}).encode("utf-8"), method="POST"
    )
    request.add_header("apikey", config["key"])
    request.add_header("Authorization", "Bearer " + config["key"])
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return True, "Supabase answered, the key was accepted, and the game's server is set up."
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            logging.error(
                "Online test failed: Supabase rejected the key "
                "(HTTP %d).", error.code
            )
            return False, (
                "Supabase rejected the key. Check that "
                "SUPABASE_PUBLISHABLE_KEY in .env is the publishable "
                "key from Project Settings, then API Keys, not the "
                "secret key."
            )
        if error.code == 404:
            logging.info(
                "Online test: the key was accepted, but the server "
                "functions are not set up yet."
            )
            return True, (
                "Supabase answered and the key was accepted, but the "
                "game's server is not set up yet. Run "
                "supabase_schema.sql in Supabase, SQL Editor."
            )
        logging.error("Online test: Supabase answered with HTTP %d.", error.code)
        return False, "Supabase answered with an error (HTTP %d)." % error.code
    except Exception as error:
        logging.error(
            "Online test failed: could not reach Supabase (%s: %s).",
            type(error).__name__, error,
        )
        return False, (
            "I could not reach Supabase. Check your internet "
            "connection and try again."
        )
