"""Tests that the server migrations really run, in order.

Run it with:  python test_migrations.py

Why this exists: on 2026-11-19 one migration (quest_growth) had an
error Postgres refuses ("cannot change name of input parameter").
Supabase stops at the first failing file, so six later migrations
never reached the live game, and nothing in the other test files
could see it, because they only test the Python.

This test builds a throwaway Postgres on your own computer, applies
every file in supabase/migrations/ in order, one transaction per
file, exactly as Supabase does, and stops at the first error. It
then checks that every server function the game calls exists with
the argument names the game sends. No real Supabase project, key or
network is used, and nothing is written outside a temporary folder.

It needs two extra packages that players do NOT need:

    pip install pgserver psycopg2-binary

If they are not installed, this test says so and skips itself.

Limits, said plainly: the throwaway Postgres has no pgcrypto, so
four small stand-in functions (digest, crypt, gen_salt,
gen_random_bytes) are made just so the files can be created. This
proves the SQL is valid and the functions exist. It does not prove
the password hashing, and it does not run the game rules.
"""

import glob
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS = os.environ.get(
    "ARENA_MIGRATIONS_DIR", os.path.join(HERE, "supabase", "migrations"))


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)
    print("ok - " + name)


STAND_INS = """
create schema if not exists extensions;
create function extensions.digest(text, text) returns bytea
  language sql immutable as $$ select decode(md5($1), 'hex') $$;
create function extensions.digest(bytea, text) returns bytea
  language sql immutable as $$ select decode(md5($1), 'hex') $$;
create function extensions.gen_random_bytes(int) returns bytea
  language sql as $$ select decode(repeat('ab', $1), 'hex') $$;
create function extensions.gen_salt(text) returns text
  language sql as $$ select 'salt' $$;
create function extensions.gen_salt(text, int) returns text
  language sql as $$ select 'salt' $$;
create function extensions.crypt(text, text) returns text
  language sql as $$ select md5($1 || $2) $$;
"""


def migration_files():
    return sorted(glob.glob(os.path.join(MIGRATIONS, "*.sql")))


def check_file_names():
    names = [os.path.basename(path) for path in migration_files()]
    check("there are migration files", len(names) > 0)
    pattern = re.compile(r"^\d{14}_[a-z0-9_]+\.sql$")
    check("every file is named UTC-time_short_name.sql",
          all(pattern.match(name) for name in names))
    stamps = [name.split("_")[0] for name in names]
    check("no two files share a timestamp", len(stamps) == len(set(stamps)))


def client_calls():
    """Server function name -> set of argument names the game sends."""
    calls = {}
    source = open(os.path.join(HERE, "online_save.py"),
                  encoding="utf-8").read()
    for match in re.finditer(r"def \w+\(.*?(?=\ndef |\Z)", source, re.S):
        body = match.group(0)
        found = re.search(r'rpc\(\s*config,\s*"(arena_\w+)"', body)
        if not found:
            continue
        args = set(re.findall(r'args\["(p_\w+)"\]', body))
        if "_session_args" in body:
            args.add("p_token")
        calls[found.group(1)] = args
    source = open(os.path.join(HERE, "account.py"), encoding="utf-8").read()
    for match in re.finditer(
            r'rpc\(config,\s*"(arena_\w+)",\s*\{(.*?)\}', source, re.S):
        calls[match.group(1)] = set(re.findall(r'"(p_\w+)"', match.group(2)))
    return calls


def main_test():
    check_file_names()

    try:
        import pgserver
        import psycopg2
    except ImportError:
        print("skip - the migration replay needs: "
              "pip install pgserver psycopg2-binary")
        print("\nMigration file-name tests passed. Replay skipped.")
        return

    server = pgserver.get_server(tempfile.mkdtemp())
    connection = psycopg2.connect(server.get_uri())
    connection.autocommit = True
    cursor = connection.cursor()
    for role in ("anon", "authenticated", "service_role"):
        cursor.execute(
            "do $$ begin if not exists (select from pg_roles "
            "where rolname='%s') then create role %s nologin; "
            "end if; end $$;" % (role, role))
    cursor.execute(STAND_INS)

    for path in migration_files():
        name = os.path.basename(path)
        sql = open(path, encoding="utf-8").read()
        # The throwaway Postgres has no pgcrypto; the stand-ins above
        # cover the calls inside the files.
        sql = re.sub(r"create extension if not exists pgcrypto[^;]*;", "",
                     sql, flags=re.I)
        try:
            cursor.execute("begin;\n" + sql + "\ncommit;")
        except Exception as error:
            try:
                cursor.execute("rollback")
            except Exception:
                pass
            first = str(error).strip().splitlines()[0]
            raise AssertionError(
                "FAILED: migration %s does not apply: %s" % (name, first))
        check("migration applies: " + name, True)

    cursor.execute(
        "select p.proname, p.proargnames, p.pronargs, p.pronargdefaults "
        "from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'public' and p.proname like 'arena\\_%'")
    server_functions = {}
    for proname, argnames, nargs, ndefaults in cursor.fetchall():
        names = list(argnames or [])
        required = set(names[:max(0, nargs - ndefaults)])
        server_functions.setdefault(proname, []).append(
            (set(names), required))

    for function, sent in sorted(client_calls().items()):
        check("the server has " + function, function in server_functions)
        fits = any(sent <= known and required <= sent
                   for known, required in server_functions[function])
        check("the game sends the right arguments to " + function, fits)

    # Behaviour: history events carry the balance (Phase 33).
    cursor.execute(
        "insert into arena_private.players (player_code, username, "
        "password_hash, gender, kind, fighter) values "
        "('9001','tester','x','female','robot','{\"credits\": 100}'), "
        "('9002','nocredits','x','female','robot','{\"credits\": null}')")
    cursor.execute(
        "select arena_private.log_event('9001','t','{\"x\": 1}','server')")
    cursor.execute(
        "select arena_private.log_event('9001','t2',"
        "'{\"credits_now\": 5}','server')")
    cursor.execute(
        "select arena_private.log_event('9002','t','{\"x\": 1}','server')")
    cursor.execute(
        "select events from arena_private.players "
        "where player_code in ('9001','9002') order by player_code")
    first, second = [row[0] for row in cursor.fetchall()]
    check("an event keeps its own detail", first[0]["detail"]["x"] == 1)
    check("an event records the balance at that moment",
          first[0]["detail"].get("credits_now") == 100)
    check("an event never overwrites a balance it already has",
          first[1]["detail"]["credits_now"] == 5)
    check("a null balance adds nothing and does not fail",
          second[0]["detail"] == {"x": 1})

    # Behaviour: the witch study (Phase 38). A witch learns
    # spells in real time, pausing outside the study; the
    # server is the judge, and the Python table in spells.py
    # must stay word-for-word the same as the SQL table.
    sys.path.insert(0, HERE)
    import spells

    # The SQL spell table matches spells.py exactly: names,
    # costs, times and cast lines.
    for element in spells.ELEMENTS:
        cursor.execute(
            "select array[%s]" % ", ".join(
                "arena_private.spell_name('%s', '%s')"
                % (element, tier) for tier in spells.TIERS))
        check("the server knows the %s spells" % element,
              cursor.fetchone()[0]
              == list(spells.SPELL_NAMES[element]))
    cursor.execute(
        "select array[%s]" % ", ".join(
            "arena_private.spell_cost('%s')" % tier
            for tier in spells.TIERS))
    check("the server spell costs are 25, 50, 100, 200, 400",
          cursor.fetchone()[0] == [25, 50, 100, 200, 400])
    cursor.execute(
        "select array[%s]" % ", ".join(
            "arena_private.spell_seconds('%s')" % tier
            for tier in spells.TIERS))
    check("the server spell times are 15, 30, 60, 120, 240 minutes",
          cursor.fetchone()[0] == [900, 1800, 3600, 7200, 14400])
    cursor.execute(
        "select array[%s]" % ", ".join(
            "arena_private.spell_cast_line('%s')" % element
            for element in spells.ELEMENTS))
    check("the server cast lines match spells.py",
          cursor.fetchone()[0]
          == [spells.CAST_LINES[element]
              for element in spells.ELEMENTS])

    # spell_level and spell_pick, without any session.
    cursor.execute(
        "select arena_private.spell_level("
        "'{\"spells\": {\"fire\": {\"common\": 2}}}'::jsonb, "
        "'fire', 'common')")
    check("spell_level reads a learned spell",
          cursor.fetchone()[0] == 2)
    cursor.execute(
        "select arena_private.spell_level('{}'::jsonb, 'fire', 'common')")
    check("spell_level is 0 when nothing is learned",
          cursor.fetchone()[0] == 0)
    cursor.execute(
        "select arena_private.spell_pick("
        "'{\"kind\": \"witch\", \"spells\": {\"fire\": {\"common\": 1}, "
        "\"water\": {\"common\": 1}}}'::jsonb)")
    picked = cursor.fetchone()[0]
    check("spell_pick returns one learned spell",
          picked is not None and picked["element"] in ("fire", "water")
          and picked["level"] == 1)
    cursor.execute(
        "select arena_private.spell_pick("
        "'{\"kind\": \"robot\", \"spells\": {\"fire\": {\"common\": 1}}}'::jsonb)")
    check("spell_pick returns nothing for a robot",
          cursor.fetchone()[0] is None)
    cursor.execute(
        "select arena_private.spell_pick("
        "'{\"kind\": \"witch\", \"spells\": {}}'::jsonb)")
    check("spell_pick returns nothing with no spells learned",
          cursor.fetchone()[0] is None)

    # A new witch starts with no spells and no study.
    cursor.execute(
        "select arena_private.new_fighter('Test', 'witch', 'female')")
    fresh = cursor.fetchone()[0]
    check("a new witch starts with no spells and no study",
          fresh["spells"] == {} and fresh["study"] is None)

    # The study RPCs, through real sessions: a player row and
    # a session row, made directly in the throwaway database
    # (the sign-in password path is not what is being tested).
    witch_token = "a" * 64
    cursor.execute(
        "insert into arena_private.players (player_code, username, "
        "password_hash, gender, kind, fighter) values "
        "('9101', 'studytester', 'x', 'female', 'witch', "
        "arena_private.new_fighter('Study', 'witch', 'female') "
        "|| jsonb_build_object('credits', 500))")
    cursor.execute(
        "insert into arena_private.sessions (token_hash, player_code) "
        "values (arena_private.hash_token(%s), '9101')", (witch_token,))
    cursor.execute(
        "select public.arena_study_start(%s, 'water', 'uncommon')",
        (witch_token,))
    check("a tier needs the tier below it first",
          "Splash" in (cursor.fetchone()[0].get("error") or ""))
    cursor.execute(
        "select public.arena_study_start(%s, 'fire', 'common')",
        (witch_token,))
    started = cursor.fetchone()[0]
    check("study_start learns Ember Spark",
          started.get("error") is None
          and started["study"]["name"] == "Ember Spark"
          and started["study"]["tier"] == "common"
          and started["study"]["level"] == 1)
    check("study_start charges 25 credits up front",
          started["fighter"]["credits"] == 475)
    cursor.execute(
        "select public.arena_study_start(%s, 'water', 'common')",
        (witch_token,))
    check("a second spell is blocked while learning",
          "already learning" in (cursor.fetchone()[0].get("error") or ""))
    cursor.execute(
        "select public.arena_study_pause(%s)", (witch_token,))
    paused = cursor.fetchone()[0]
    check("study_pause freezes the remaining time",
          paused["study"]["paused"] is True
          and 0 < paused["study"]["remaining_seconds"] <= 900)
    cursor.execute(
        "select public.arena_study_complete(%s)", (witch_token,))
    check("a paused study never completes",
          "paused" in (cursor.fetchone()[0].get("error") or ""))
    cursor.execute(
        "select public.arena_study_start(%s, 'fire', 'common')",
        (witch_token,))
    resumed = cursor.fetchone()[0]
    check("resuming the same spell is free",
          resumed.get("error") is None
          and resumed["fighter"]["credits"] == 475)
    # Move the finish time into the past, as if 15 minutes
    # had gone by in the study, then complete it.
    cursor.execute(
        "update arena_private.players set fighter = jsonb_set("
        "fighter, '{study,finish_at}', "
        "to_jsonb(arena_private.now_epoch() - 10)) "
        "where player_code = '9101'")
    cursor.execute(
        "select public.arena_study_complete(%s)", (witch_token,))
    done = cursor.fetchone()[0]
    check("completing a study grants level 1",
          done.get("error") is None
          and "I learned Ember Spark!" in (done.get("message") or "")
          and done["fighter"]["spells"] == {"fire": {"common": 1}})
    # A robot cannot learn spells.
    robot_token = "b" * 64
    cursor.execute(
        "insert into arena_private.players (player_code, username, "
        "password_hash, gender, kind, fighter) values "
        "('9102', 'robotester', 'x', 'male', 'robot', "
        "arena_private.new_fighter('Rob', 'robot', 'male') "
        "|| jsonb_build_object('credits', 500))")
    cursor.execute(
        "insert into arena_private.sessions (token_hash, player_code) "
        "values (arena_private.hash_token(%s), '9102')", (robot_token,))
    cursor.execute(
        "select public.arena_study_start(%s, 'fire', 'common')",
        (robot_token,))
    check("a robot cannot learn spells on the server",
          "only a witch" in (cursor.fetchone()[0].get("error") or ""))
    # A study quest comes from a witch giver.
    cursor.execute(
        "select public.arena_new_study_quest(%s)", (witch_token,))
    study_quest = cursor.fetchone()[0]
    check("a study quest comes from a witch giver",
          study_quest.get("error") is None
          and study_quest["quest"]["giver"] in spells.STUDY_GIVERS)

    # The board (Belle rule, server side): 200 boards dealt by
    # quest_board_ensure, and every giver shows up somewhere —
    # no giver is locked out of the board, or out of slot 1.
    all_givers = set()
    first_givers = set()
    boards_ok = True
    for _ in range(200):
        cursor.execute(
            "select arena_private.quest_board_ensure("
            "'{\"quest_level\": 1}'::jsonb)")
        board = cursor.fetchone()[0]["quests_board"]
        if len(board) != 5:
            boards_ok = False
        all_givers.update(quest["giver"] for quest in board)
        first_givers.add(board[0]["giver"])
    check("every starting board has 5 quests", boards_ok)
    check("every giver shows up on the board",
          all_givers
          == {"Bolt", "Marge", "Pip", "Dot", "Gus", "Belle",
              "Hazel", "Rowan", "Wren", "Bram"})
    check("many givers land first on the board",
          len(first_givers) >= 8)

    print("\nAll migration tests passed.")


if __name__ == "__main__":
    main_test()
