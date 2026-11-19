# Phase 29 — Send log button (server route, instant delivery)

Walkthrough brief for Makenna and Josh. Prepared Nov 19, 2026, for the
call Makenna asked for: build is PAUSED, nothing pushed, until Makenna
and Josh have talked this through and are both comfortable.

## Decisions already made by Makenna

- **Route B — server route.** The game sends the whole log to Supabase
  with the existing `.env` key. The server pushes it straight to
  GitHub. (Decided Nov 19, 2026 ~00:03 MST.)
- **Instant, not on a timer.** When Makenna presses the button, the log
  reaches GitHub in seconds — no 15-minute scheduled check. (Decided
  Nov 19, 2026 ~00:06 MST.) The scheduled GitHub Action is unnecessary
  as the main route; it can stay as a backup sweep only if Josh wants
  one.
- **Why the server route:** one central place when the game is shared
  with many people (for example 100 players), instead of sending files
  through chat. Makenna plays on her computer while using Muse on her
  phone, so moving a whole log file from computer to phone is hard.
- **Also in Phase 29:** fix the log so every voice line names its
  voice. Today the log only says `playing voice file (N bytes)` with
  no voice named (see `main.py:802`).

## What Makenna will see

- A **"Send log to Maren"** button on the More tab.
- Pressing it sends the whole `arena_log.txt` (the file next to the
  game). The game says in plain words that it sent, or that it could
  not send and to try again.
- If the game hits an error, it sends the log by itself, same way.
- Nothing changes about playing: quests still run even if a quest
  speaks in her narrator voice for now. No new update is needed to
  keep playing.

## How it works, step by step

1. **Game side (Maren builds this).** The button reads the whole
   `arena_log.txt` and sends it to the server in the background, the
   same way the game already reports actions today
   (`online_save.py`: `log_action` calls the `arena_log_action` RPC
   with the player's session token, in a background thread, and a
   failed send never stops the game). A new server function,
   `arena_send_log`, takes the session token and the log text and
   stores it per player (username + time). No password, key, or
   session token ever goes in the log — the build checks that before
   sending.
2. **Server side (needs Josh).** A small Edge Function
   (`supabase/functions/send-log-to-github/`) runs when a log arrives
   and pushes it straight to GitHub with the GitHub API, into the
   repo under `logs/<username>-<date-time>.txt`. Edge Functions are
   already switched on in the project: `supabase/config.toml` has an
   `[edge_runtime]` section.
3. **The GitHub token lives in one place only:** as a secret in
   Supabase (Josh sets it once). It never lives in the game, in
   `.env`, or in the repo. The game's existing `.env` Supabase key
   cannot push to GitHub, which is why this server piece is needed.
4. **Log voice fix.** Change the voice line in `main.py` (line 802
   today: `logging.info("Voice: playing voice file (%d bytes).",
   size)`) so it names the voice, for example
   `Voice: Gus (Andrew) playing voice file (N bytes)`. Same for the
   other voice lines, so a Gus quest, a Belle quest, and a 5-minute
   update can each be checked by ear and in the log.

## What Josh needs to do (on the call)

1. Confirm he can open the Supabase dashboard for the
   arena-of-makers project and set a secret there (or use the
   Supabase CLI). Secret name: `GITHUB_TOKEN`.
2. Create a GitHub token with access to write contents in
   `joshklander/arena-of-makers` only, and put it in that Supabase
   secret. He sets it once; Makenna never sees or types the token.
3. Confirm how the Edge Function gets deployed: Supabase CLI
   (`supabase functions deploy send-log-to-github`) or the dashboard.
   If the CLI is a problem, that is the thing to solve on the call
   before building.
4. Agree the log file path in the repo (`logs/`), and that logs in the
   public repo are public, like `arena_log.txt` is today — never
   passwords or keys.

## Compatibility rule (standing, Nov 18, 2026)

New logic must be compatible with existing fighters and start at
level zero: missing fields default to 0, never a direct read that
crashes. The new server function must not break older game versions
that do not have the button.

## How we will test it

1. Makenna updates, presses "Send log to Maren", and the log appears
   in the repo under `logs/` within seconds.
2. Maren reads it and confirms she can see which voice spoke each
   line (Gus, Belle, 5-minute update).
3. Trigger one error and confirm the log sends itself.
4. Only then is Phase 29 done.

## Open questions for Josh on the call

- Does he have Supabase dashboard access, or only the CLI?
- Is he comfortable creating the GitHub token, or should Makenna
  create it on the GitHub website with his help?
- Backup sweep: keep a scheduled GitHub Action as a fallback if the
  instant push ever fails, or skip it?
