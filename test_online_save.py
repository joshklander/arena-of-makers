"""Tests for the online-only Supabase check, saves and export.

Run it with:  python test_online_save.py
No real Supabase key or network is used: every HTTP call is
stubbed, and the .env files are made in a temporary folder.
The key itself is never printed by these tests, and the export
test proves an export holds only the one player's data, never
everyone's.
"""

import json
import logging
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
    good_key = "sb_publishable_0123456789abcdef0123456789abcdef"

    # No .env at all: plain message, no game.
    config, error = supabase_config.check_online_config(
        os.path.join(folder, ".env"))
    check("missing .env gives a plain message", config is None and ".env" in error)
    check("missing .env never leaks a key", "sb_publishable_0123" not in error)

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

    # Right shape, both kinds: sb_publishable_ and legacy eyJ JWT.
    path = write_env(folder, url=good_url, key=good_key)
    config, error = supabase_config.check_online_config(path)
    check("good sb_publishable_ key passes", config is not None and error is None)
    check("good config keeps the URL", config["url"] == good_url)
    jwt_key = "eyJ" + "a" * 60 + "." + "b" * 40 + "." + "c" * 40
    path = write_env(folder, url=good_url, key=jwt_key)
    config, error = supabase_config.check_online_config(path)
    check("good JWT key passes", config is not None and error is None)

    # From here on, the "server" is a fake urlopen that records
    # every call. No network, no real key, no real password.
    config = {"url": good_url, "key": good_key, "session": "a" * 64}
    calls = []
    answers = {}

    class _Reply:
        def __init__(self, data):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps(self.data).encode("utf-8")

    def _fake_urlopen(request, timeout=15):
        name = request.full_url.rsplit("/", 1)[-1]
        calls.append({
            "url": request.full_url,
            "name": name,
            "apikey": request.get_header("Apikey"),
            "auth": request.get_header("Authorization"),
            "body": json.loads(request.data.decode("utf-8")),
        })
        answer = answers.get(name, {"ok": True})
        if isinstance(answer, Exception):
            raise answer
        return _Reply(answer)

    patch = mock.patch.object(online_save.urllib.request, "urlopen", _fake_urlopen)
    log_lines = []

    class _Catch(logging.Handler):
        def emit(self, record):
            log_lines.append(record.getMessage())

    catcher = _Catch()
    logging.getLogger().addHandler(catcher)
    secret_password = "correct horse battery"

    with patch:
        # Every call goes to an arena_* function, never a table.
        fighter = game_logic.new_fighter("Bolt", "robot")
        answers["arena_fight"] = {
            "won": True, "lines": ["A Scrap Rat appears! Level 1.", "You won!"],
            "xp": 25, "points": 15, "levels_gained": 0, "messages": [],
            "fighter": dict(fighter, wins=1, points=15),
        }
        result, error = online_save.fight(config, opponent_code="5150")
        check("fight runs on the server", error is None and result["won"] is True)
        check("fight calls the arena_fight function",
              calls[-1]["url"] == good_url + "/rest/v1/rpc/arena_fight")
        check("fight sends the session, not a fighter",
              calls[-1]["body"] == {"p_token": "a" * 64, "p_opponent_code": "5150"})
        check("calls send the key in the apikey header",
              calls[-1]["apikey"] == good_key)
        check("calls send the same key as a Bearer token",
              calls[-1]["auth"] == "Bearer " + good_key)
        check("no call ever goes to a table",
              all("/rest/v1/rpc/arena_" in c["url"] for c in calls))
        check("the game has no way left to write a fighter",
              not hasattr(online_save, "save_fighter"))

        # Upgrades: the server's plain-words refusal is passed on,
        # with the fighter the server sent along.
        answers["arena_start_upgrade"] = {
            "error": "That upgrade costs 25 points and you have 15 points.",
            "fighter": dict(fighter, points=15), "messages": [],
        }
        server_fighter, _messages, error = online_save.start_upgrade(config, "weapon")
        check("upgrade refusal comes back in plain words",
              error.startswith("That upgrade costs 25 points"))
        check("upgrade refusal still sends the server's fighter",
              server_fighter["points"] == 15)

        # A dead session is said plainly.
        answers["arena_state"] = {
            "error": "You are signed out. Close the game and sign in again.",
            "signed_out": True,
        }
        _f, _m, error = online_save.refresh_state(config)
        check("a dead session is said plainly", "signed out" in error)

        # Online list.
        answers["arena_list_online"] = {"players": [
            {"username": "Makenna", "player_code": "3333", "kind": "chef", "level": 3},
        ]}
        players, error = online_save.list_online_players(config)
        check("online list returns the online players",
              error is None and players[0]["username"] == "Makenna")

        # Server errors: a rejected key, a missing function, no network.
        answers["arena_state"] = urllib.error.HTTPError(
            good_url, 401, "Unauthorized", {}, None)
        _f, _m, error = online_save.refresh_state(config)
        check("a rejected key is said plainly", "rejected" in error)
        answers["arena_state"] = urllib.error.HTTPError(
            good_url, 404, "Not Found", {}, None)
        _f, _m, error = online_save.refresh_state(config)
        check("missing server functions point to the schema file",
              "supabase_schema.sql" in error)
        answers["arena_state"] = OSError("no network")
        _f, _m, error = online_save.refresh_state(config)
        check("no network is said plainly", "Could not reach" in error)

        # Sign in: the password goes only to arena_sign_in.
        answers["arena_sign_in"] = {
            "token": "b" * 64,
            "account": {"username": "Bolt", "player_code": "4242",
                        "gender": "male", "kind": "robot"},
            "fighter": dict(fighter, player_code="4242", username="Bolt"),
            "messages": [],
        }
        session, error, no_account = account.sign_in(
            config, "42 42", "Bolt", secret_password)
        check("sign in returns a session", session["token"] == "b" * 64)
        check("sign in cleans the code", calls[-1]["body"]["p_player_code"] == "4242")
        answers["arena_sign_in"] = {"no_account": True}
        session, error, no_account = account.sign_in(
            config, "1234", "Josh", secret_password)
        check("an unknown code offers a new account",
              session is None and error is None and no_account is True)
        answers["arena_sign_in"] = {
            "error": "That username, player code and password do not match. "
                     "Check them and try again."}
        session, error, no_account = account.sign_in(
            config, "4242", "Bolt", "wrong password")
        check("a wrong password is said plainly",
              session is None and "do not match" in error)

        # Create account: the client checks the password first.
        before = len(calls)
        session, error = account.create_account(
            config, "Josh", "5150", "short", gender="male", kind="robot")
        check("a short password is refused before any call",
              session is None and "at least 8" in error and len(calls) == before)
        answers["arena_create_account"] = dict(answers["arena_sign_in"])
        answers["arena_create_account"] = {
            "token": "c" * 64,
            "account": {"username": "Josh", "player_code": "5150"},
            "fighter": dict(fighter, name="Josh"), "messages": [],
        }
        session, error = account.create_account(
            config, "Josh", "51-50", secret_password, gender="male", kind="robot")
        check("a new account returns a session", session["token"] == "c" * 64)
        check("a chosen code is cleaned and kept",
              calls[-1]["body"]["p_player_code"] == "5150")

        # Lookup: needs the session, shows public parts only.
        answers["arena_lookup_player"] = {
            "username": "Makenna", "player_code": "3333", "kind": "chef",
            "gender": "female",
            "fighter": {"name": "Makenna", "level": 3, "wins": 2, "losses": 1},
        }
        found, error = account.lookup_player(config, "3333")
        check("player lookup finds the player by code",
              found["username"] == "Makenna" and found["fighter"]["level"] == 3)
        check("player lookup sends the session",
              calls[-1]["body"]["p_token"] == "a" * 64)
        answers["arena_lookup_player"] = {
            "error": "No player has that code. Check the code and try again."}
        found, error = account.lookup_player(config, "9999")
        check("player lookup says plainly when a code has no player",
              found is None and "No player" in error)

        # Export: only what the server sends for this player.
        answers["arena_export"] = {
            "username": "Bolt", "player_code": "4242", "fighter": fighter,
            "events": [{"action": "fight", "detail": {"won": True}, "by": "server"}],
        }
        export_path = os.path.join(folder, "export.json")
        path, error = online_save.export_user_data(config, fighter, path=export_path)
        check("export writes a file", error is None and os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            exported_text = handle.read()
        exported = json.loads(exported_text)
        check("export holds this player's events",
              exported["online_row"]["events"][0]["action"] == "fight")
        check("export never contains the key", good_key not in exported_text)
        check("export never contains the session token", "a" * 64 not in exported_text)

        # Keep me signed in: a remember token signs in with no
        # password, and comes back swapped for a new one.
        answers["arena_resume"] = {
            "token": "d" * 64, "remember_token": "e" * 64,
            "account": {"username": "Bolt", "player_code": "4242"},
            "fighter": dict(fighter), "messages": [],
        }
        session, error, forget = account.resume(config, "f" * 64)
        check("a remember token signs in", session["token"] == "d" * 64)
        check("a remember token comes back swapped",
              session["remember_token"] == "e" * 64)
        check("resume sends only the remember token",
              calls[-1]["body"] == {"p_remember_token": "f" * 64})
        answers["arena_resume"] = {
            "error": "You were signed out on this computer. Please sign in again.",
            "forget": True}
        session, error, forget = account.resume(config, "f" * 64)
        check("a dead remember token says to forget it",
              session is None and forget is True and "sign in again" in error)
        answers["arena_resume"] = OSError("no network")
        session, error, forget = account.resume(config, "f" * 64)
        check("no network does not forget the remember token",
              session is None and forget is False)
        answers["arena_remember"] = {"remember_token": "e" * 64}
        token, error = account.remember_this_computer(config)
        check("turning it on gets a remember token", token == "e" * 64)
        check("turning it on uses the session",
              calls[-1]["body"] == {"p_token": "a" * 64})
        check("turning it off tells the server",
              account.forget_this_computer(config, "e" * 64)
              and calls[-1]["name"] == "arena_forget")

        # Sign out ends the session and forgets the token.
        signed_out_config = dict(config)
        online_save.sign_out(signed_out_config)
        check("sign out calls arena_sign_out", calls[-1]["name"] == "arena_sign_out")
        check("sign out forgets the token", signed_out_config["session"] is None)

    logging.getLogger().removeHandler(catcher)
    all_logs = "\n".join(log_lines)
    check("the password is never logged", secret_password not in all_logs)
    check("the session token is never logged",
          "a" * 64 not in all_logs and "b" * 64 not in all_logs)
    check("the remember token is never logged",
          "e" * 64 not in all_logs and "f" * 64 not in all_logs)

    # The remember token goes in the password store, never a file.
    import remember

    class _FakeKeyring:
        def __init__(self):
            self.store = {}
        def get_password(self, service, name):
            return self.store.get((service, name))
        def set_password(self, service, name, value):
            self.store[(service, name)] = value
        def delete_password(self, service, name):
            del self.store[(service, name)]

    fake_keyring = _FakeKeyring()
    with mock.patch.object(remember, "keyring", fake_keyring):
        check("keep me signed in is offered with a password store",
              remember.available())
        check("nothing is saved at first", remember.load_token(config) is None)
        check("a remember token is saved", remember.save_token(config, "e" * 64))
        check("the saved token reads back", remember.load_token(config) == "e" * 64)
        check("it is saved under the game's name",
              list(fake_keyring.store)[0][0] == "Arena of Makers")
        remember.forget_token(config)
        check("forgetting removes it", remember.load_token(config) is None)
        remember.forget_token(config)
        check("forgetting twice is fine", True)
    with mock.patch.object(remember, "keyring", None):
        check("keep me signed in is not offered without a password store",
              not remember.available() and not remember.save_token(config, "e" * 64))
    remember_source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "remember.py"), encoding="utf-8").read()
    check("remember never opens a file", "open(" not in remember_source)
    check("the key is never logged", good_key not in all_logs)

    # Accounts: codes are exactly 4 digits.
    import random as _random
    codes = {account.generate_player_code(_random.Random(i)) for i in range(50)}
    check("player codes are 4 characters",
          all(len(code) == 4 for code in codes))
    check("player codes are only digits",
          all(code.isdigit() for code in codes))
    check("player codes are not all the same", len(codes) > 40)
    check("a short code is not usable",
          account.validate_player_code("123") is not None)
    check("a long code is not usable",
          account.validate_player_code("12345") is not None)
    check("a code with letters is not usable",
          account.validate_player_code("AB12") is not None)
    check("a code with leading zeros is usable",
          account.validate_player_code("0042") is None)
    check("a code with a space or dash is cleaned first",
          account.validate_player_code("48 27") is None
          and account.validate_player_code("48-27") is None)
    check("a password message never repeats the password",
          "short" not in (account.validate_password("short") or ""))
    check("no local account file in account module",
          not hasattr(account, "load_account") and not hasattr(account, "save_account"))

    print("\nAll online save tests passed.")


if __name__ == "__main__":
    main_test()
