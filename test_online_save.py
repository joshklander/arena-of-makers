"""Tests for the online-only Supabase check, saves and export.

Run it with:  python test_online_save.py
No real Supabase key or network is used: every HTTP call is
stubbed, and the .env files are made in a temporary folder.
The key itself is never printed by these tests, and the export
test proves an export holds only the one player's data, never
everyone's.
"""

import json
import os
import sys
import tempfile
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import account
import game_logic
import online_save
import supabase_config


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)
    print("ok - " + name)


def write_env(folder, url=None, key=None):
    path = os.path.join(folder, ".env")
    lines = []
    if url is not None:
        lines.append("SUPABASE_URL=%s" % url)
    if key is not None:
        lines.append("SUPABASE_PUBLISHABLE_KEY=%s" % key)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def main_test():
    folder = tempfile.mkdtemp()
    good_url = "https://yurdzzinmibgnoanxtkm.supabase.co"
    good_key = "sbp_0123456789abcdef0123456789abcdef"

    # No .env at all: plain message, no game.
    config, error = supabase_config.check_online_config(
        os.path.join(folder, ".env"))
    check("missing .env gives a plain message", config is None and ".env" in error)
    check("missing .env never leaks a key", "sbp_" not in error)

    # Missing key line.
    path = write_env(folder, url=good_url)
    config, error = supabase_config.check_online_config(path)
    check("missing key is named", config is None and "publishable key" in error)

    # Wrong URL shape.
    path = write_env(folder, url="https://example.com", key=good_key)
    config, error = supabase_config.check_online_config(path)
    check("wrong URL shape is named", config is None and "SUPABASE_URL" in error)

    # Wrong key shape: a secret key / PAT does not count.
    path = write_env(folder, url=good_url, key="secret-abc")
    config, error = supabase_config.check_online_config(path)
    check("wrong key shape is named", config is None and "publishable key" in error)
    check("wrong key is never echoed", "secret-abc" not in error)

    # Right shape, both kinds: sbp_ and legacy eyJ JWT.
    path = write_env(folder, url=good_url, key=good_key)
    config, error = supabase_config.check_online_config(path)
    check("good sbp_ key passes", config is not None and error is None)
    check("good config keeps the URL", config["url"] == good_url)
    jwt_key = "eyJ" + "a" * 60 + "." + "b" * 40 + "." + "c" * 40
    path = write_env(folder, url=good_url, key=jwt_key)
    config, error = supabase_config.check_online_config(path)
    check("good JWT key passes", config is not None and error is None)

    # Save: a 200 stores the fighter, with the key only in headers.
    fighter = game_logic.new_fighter("Bolt", "robot")
    fighter["player_code"] = "BOLT42"
    config = {"url": good_url, "key": good_key}
    seen = {}

    class _Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b"[]"

    def _fake_urlopen(request, timeout=15):
        seen["url"] = request.full_url
        seen["apikey"] = request.get_header("Apikey")
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _Reply()

    with mock.patch.object(online_save.urllib.request, "urlopen", _fake_urlopen):
        ok, _msg = online_save.save_fighter(fighter, config)
    check("online save succeeds on 200", ok is True)
    check("online save goes to the one shared players table",
          seen["url"].startswith(good_url + "/rest/v1/players"))
    check("online save is an update to that player's row",
          "player_code=eq.BOLT42" in seen["url"])
    check("online save sends the key in the apikey header",
          seen["apikey"] == good_key)
    check("online save sends the same key as a Bearer token",
          seen["auth"] == "Bearer " + good_key)
    check("online save stores the fighter in that player's row",
          seen["body"]["fighter"]["name"] == "Bolt")

    # Save: a 401 is a plain key error, never with the key in it.
    def _fake_401(request, timeout=15):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    with mock.patch.object(online_save.urllib.request, "urlopen", _fake_401):
        ok, msg = online_save.save_fighter(fighter, config)
    check("online save reports a rejected key", ok is False and "rejected" in msg)
    check("rejected-key message never leaks the key", good_key not in msg)

    # Load: one row back becomes the fighter.
    def _fake_load(request, timeout=15):
        seen["load_url"] = request.full_url
        reply = _Reply()
        reply.read = lambda: json.dumps([{"fighter": fighter}]).encode("utf-8")
        return reply

    with mock.patch.object(online_save.urllib.request, "urlopen", _fake_load):
        loaded, error = online_save.load_fighter(config, player_code="BOLT42")
    check("online load returns the fighter",
          loaded is not None and loaded["name"] == "Bolt")
    check("online load asks for that player's row by code",
          "player_code=eq.BOLT42" in seen["load_url"])

    # Export: only this player's fighter and events, never everyone's.
    def _fake_export(request, timeout=15):
        seen.setdefault("export_urls", []).append(request.full_url)
        reply = _Reply()
        reply.read = lambda: json.dumps([{
            "username": "Bolt", "player_code": "BOLT42",
            "fighter": fighter,
            "events": [{"action": "fight", "detail": {"won": True},
                        "created_at": "2026-11-17T00:00:00Z"}],
        }]).encode("utf-8")
        return reply

    export_path = os.path.join(folder, "export.json")
    with mock.patch.object(online_save.urllib.request, "urlopen", _fake_export):
        path, error = online_save.export_user_data(config, fighter, path=export_path)
    check("export writes a file", error is None and os.path.exists(path))
    with open(path, encoding="utf-8") as handle:
        exported = json.load(handle)
    check("export holds this player's fighter",
          exported["online_row"]["fighter"]["name"] == "Bolt")
    check("export holds this player's events only",
          len(exported["online_row"]["events"]) == 1
          and exported["online_row"]["events"][0]["action"] == "fight")
    check("export request is filtered to this player",
          any("player_code=eq.BOLT42" in url for url in seen["export_urls"]))
    check("export never contains the key",
          good_key not in json.dumps(exported))
    check("export never contains another player's name",
          "Freddy" not in json.dumps(exported))

    # Accounts: codes are six easy characters, no 0/O/1/I/L.
    import random as _random
    codes = {account.generate_player_code(_random.Random(i)) for i in range(50)}
    check("player codes are six characters",
          all(len(code) == 6 for code in codes))
    check("player codes avoid confusing characters",
          all(set(code) & set("01OIL") == set() for code in codes))
    check("player codes are not all the same", len(codes) > 40)

    # Account creation: a 200 makes the account online, with
    # the username and the player code, never a key.
    with mock.patch.object(account.urllib.request, "urlopen", _fake_urlopen):
        made, error = account.create_account(config, "Makenna")
    check("account creation succeeds on 200",
          made is not None and error is None)
    check("account keeps the username", made["username"] == "Makenna")
    check("account has a six-character code",
          len(made["player_code"]) == 6)
    # No local account file at all: the account lives
    # only online, and the player signs in every launch.
    check("no local account load in account module",
          not hasattr(account, "load_account"))
    check("no local account save in account module",
          not hasattr(account, "save_account"))

    # A player can pick their own code, and a taken code is
    # reported plainly instead of silently changing it.
    check("a short code is not usable",
          account.validate_player_code("AB") is not None)
    check("a code with a space or dash is cleaned first",
          account.validate_player_code("K7M 2Q9") is None)
    check("a six-letter chosen code is usable",
          account.validate_player_code("MAK3NN") is None)
    with mock.patch.object(account.urllib.request, "urlopen", _fake_urlopen):
        made2, error2 = account.create_account(config, "Josh", "JOSH42")
    check("a chosen code is kept when creating an account",
          made2 is not None and made2["player_code"] == "JOSH42")

    # Lookup: a code finds that player, and only that player.
    def _fake_lookup(request, timeout=15):
        reply = _Reply()
        reply.read = lambda: json.dumps(
            [{"username": "Makenna", "player_code": made["player_code"],
              "fighter": {"name": "Makenna", "kind": "robot", "level": 3,
                          "wins": 2, "losses": 1}}]
        ).encode("utf-8")
        return reply

    with mock.patch.object(account.urllib.request, "urlopen", _fake_lookup):
        found, error = account.lookup_player(config, made["player_code"])
    check("player lookup finds the player by code",
          found is not None and found["username"] == "Makenna")
    check("player lookup shows that player's fighter too",
          found["fighter"]["level"] == 3 and found["fighter"]["wins"] == 2)

    # List players: everyone from the one shared table.
    def _fake_list(request, timeout=15):
        reply = _Reply()
        reply.read = lambda: json.dumps([
            {"username": "Makenna", "player_code": made["player_code"],
             "fighter": {"name": "Makenna", "level": 3}},
            {"username": "Josh", "player_code": "JOSH42",
             "fighter": {"name": "Josh", "level": 2}},
        ]).encode("utf-8")
        return reply

    with mock.patch.object(online_save.urllib.request, "urlopen", _fake_list):
        players, error = online_save.list_players(config)
    check("list players returns everyone in the shared table",
          players is not None and len(players) == 2)
    check("list players shows each player's fighter",
          players[0]["fighter"]["level"] == 3)

    def _fake_lookup_none(request, timeout=15):
        reply = _Reply()
        reply.read = lambda: b"[]"
        return reply

    with mock.patch.object(account.urllib.request, "urlopen", _fake_lookup_none):
        found, error = account.lookup_player(config, "ZZZZZZ")
    check("player lookup says plainly when a code has no player",
          found is None and "No player" in error)

    print("\nAll online save tests passed.")


if __name__ == "__main__":
    main_test()
