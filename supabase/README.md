# The Arena of Makers server

Everything the server does lives in `migrations/`. Supabase's
GitHub integration watches the `main` branch. When a push adds a
new migration file there, Supabase applies it to the live database
by itself, within a few minutes. Nobody runs SQL by hand any more.

Every push to `main` changes the live game, so read these rules
before adding one.

## Rules for every database change

1. **Add a new file. Never edit an old one.** Each change is a new
   file in `migrations/`, named with the UTC time and a short name,
   like `20261119153000_add_quests.sql`. Make it with
   `supabase migration new add_quests`, or by hand in that format.
   A file that has already reached `main` has already run on the
   live database. Editing it does nothing, and it breaks the
   history. To fix a mistake, add another new file.
2. **Never run SQL on the live database directly.** No SQL Editor,
   no Table Editor, no Management API. That skips the history, and
   the next automatic deploy can fail.
3. **Keep older games working.** Players update at different
   times. Never remove a function, rename it, or change its inputs
   or what it returns. Add a new function, or a new input with a
   default, instead.
4. **A file runs all or nothing.** If any line fails, the whole
   file is undone and the live game keeps its old rules. Test it
   first anyway: `python test_online_save.py`,
   `python test_main_smoke.py` and `python test_game_logic.py`.

## Rules that keep the game safe

- The game only has the publishable key, which is public. It can
  call `public.arena_*` functions, and nothing else.
- Tables and helpers go in the `arena_private` schema. The game
  cannot see it.
- Every new `public.arena_*` function must:
  - be `security definer` with `set search_path = ''`, and use
    full names like `arena_private.players`;
  - start with `arena_private.session_player(p_token)`, and return
    `arena_private.signed_out()` when that is null;
  - run the game rules itself, with the server's own random numbers
    and clock. Never take a number from the game for stats, credits,
    levels, damage or times;
  - get `revoke all ... from public` and
    `grant execute ... to anon, authenticated` at the end of the file.
- Never write a function that runs SQL text it is given.
- Never return `password_hash`, a token, or another player's private
  data.
- No key, token or password ever goes in this folder, in the game,
  or in GitHub. Nobody needs one to add a migration: Supabase
  applies it straight from GitHub.

## Files

- `migrations/20261118045430_baseline.sql`: the whole server as of
  November 18, 2026, including the combat stats phase. It is safe
  to run again, so the first automatic deploy can replay it.
- `config.toml`: made by `supabase init`, for running a database on
  your own computer. It has no `[remotes]` section, so it never
  changes the live project's settings.
