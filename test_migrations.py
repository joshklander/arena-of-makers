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

    print("\nAll migration tests passed.")


if __name__ == "__main__":
    main_test()
