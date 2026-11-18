# How games auto-update their servers — research notes

Research for Arena of Makers, November 17, 2026. Plain-language write-up of how multiplayer games deploy server-logic updates automatically and securely, and the simplest options for our Supabase setup. Full sources are at the end of this file. This is research, not yet implemented — see the "Recommendations" section for the suggested order of work.

---

# How multiplayer games deploy server-logic updates automatically (and securely)

*Plain-language research report for a two-person indie team. Read 18 November 2026. Supabase docs below were opened and read directly ("verified live"); other sources are from web search results ("index").*

## Summary

**Short answer: stop running one big SQL file by hand. Split it into small, numbered "migration" files, keep them in Git, and let a trusted machine — not a player's game client — apply them automatically whenever you merge to your main branch.**

That is the standard pattern in games and in ordinary apps, and Supabase supports it out of the box, on the free tier. There are two equally simple ways to do it:

1. **Easiest: turn on Supabase's own GitHub integration** — connect your GitHub repo in the Supabase dashboard and switch on "Deploy to production". After that, merging a migration file to `main` applies it to your live database by itself. No workflow file, no secrets to manage yourself.
2. **Almost as easy, more control: a small GitHub Action** (GitHub's free automation runner) that runs `supabase db push` on every push to `main`, using secrets you store in GitHub. This is the exact setup Supabase's own docs describe.

Either one removes the manual step. Neither one changes your anti-cheat design: the game client still only holds the public key and can only call the game-rule functions you allow — it never gets the power to change those rules.

**A second, equally important trick: move tuning numbers out of code and into database tables** (item prices, damage, drop rates, quest rewards). Then changing a number is just editing a row in a table the server functions already read — no deploy, no migration, no new client at all. Big live games do most of their weekly balancing this way.

**What you must not do:** let the game client apply updates at launch using a player's login. A shipped game can be taken apart, so anything inside it — a password, a secret key, an admin token — becomes public. If a player could change server rules, they could give themselves unlimited money, rewrite the rules in their favour, or delete the database. Real games keep rule-changing power on machines only the developers control (their own computers, or GitHub's automation servers), and the client is never trusted.

---

## Findings

### 1. How real multiplayer games push server-side updates

Games separate updates into three kinds, because each kind is shipped differently. Mixing them up is the most common cause of broken deploys.

| Kind of update | What it is | How big and small games ship it |
|---|---|---|
| **(a) Game-server code / logic** — the program that runs the match | New features, bug fixes in the server program (for example a dedicated server, or an "Edge Function", a small server program Supabase runs for you) | **Redeploy the server program.** Big games do a "rolling update": they replace server machines one at a time, draining (gracefully emptying) live matches off the old ones first, so nobody is kicked mid-game; or "blue-green", running the old and new versions side by side and switching new players to the new one. Small games usually just restart/redeploy — a few seconds of downtime is acceptable for a tiny player base. Supabase Edge Functions are deployed with one command, `supabase functions deploy`, and Supabase spreads them worldwide automatically. |
| **(b) Database schema and stored functions** — tables, columns, and the Postgres functions that hold your game rules | Adding a table or column, changing a function such as "buy item" or "finish quest" | **Versioned migrations applied automatically on deploy** (see §2–3). In your case this is the important one: your game rules *are* Postgres functions, so a function change is a migration. A function change normally takes effect instantly — Postgres just swaps in the new function text — with no server restart. The risk is not downtime, it is an old client calling a new function, so keep functions backward-compatible (see §1 note below). |
| **(c) Content / data / tuning** — items, stats, prices, event dates | New sword, cheaper potion, double-XP weekend | **No deploy at all** (see §4). The numbers live in database tables or a config file the server reads each time it runs. You edit the data; the next game action uses the new numbers. |

Sources: rolling/draining and version handling in live games, https://www.teamcoherence.com/live-service-game-backend/ (index); rolling vs "red-green" (two versions in parallel) updates, https://www.gamedeveloper.com/business/how-to-update-your-game-without-impacting-player-experience-or-revenue (index); Edge Function deploy, https://supabase.com/docs/guides/functions/deploy (index).

**One warning that applies to all three:** your client and your server will be out of sync for days or weeks — some players update late. Games therefore check versions when a player connects ("version negotiation") and either accept the old client or tell it to update, and they test the *old* client against the *new* server before shipping. For you, the cheap version of this is: never change a function's inputs/outputs in a way that breaks the client you already shipped; add new behaviour in a new function, or in a new optional argument, and keep the old shape working. Source: https://www.teamcoherence.com/live-service-game-backend/ (index).

### 2. The standard pattern for database migrations in production games and apps

**The pattern, in one paragraph.** A "migration" is a small SQL file that moves the database one step forward — "add a column", "create this table", "replace this function". Each file has a timestamp or number in its name so files always run in the same order, lives in a `migrations/` folder in Git next to the code that needs it, and is never edited after it has run on the live database. The migration tool keeps a small tracking table *inside* the database recording which files have already run. On every deploy it compares the files with that table and runs only the new ones. A fresh database plus the full list of files therefore rebuilds exactly what production has. Sources: https://www.saasturf.com/blog/database-migration/ (index); https://www.bytebase.com/blog/top-database-schema-change-tool-evolution/ (index).

**The golden rules everyone repeats:**
- Never edit a migration that has already run on production. If it was wrong, write a *new* migration that fixes it.
- Never change the live database directly (dashboard SQL editor, Table Editor) once you use migrations — that bypasses the tracking table and the next automatic push fails with sync errors. Supabase's docs state this explicitly (see §3).
- Test migrations locally first, and on a staging copy if you have one, before they touch real players' data. Back up before a risky one.

**Concrete tools** — you mostly inherit the tool from your stack; you do not need to learn them all:

| Tool | Who uses it | How it works |
|---|---|---|
| **Supabase CLI migrations** (your stack) | Supabase / Postgres projects | Timestamped `.sql` files in `supabase/migrations/`; `supabase db push` applies the pending ones. See §3. |
| **Flyway** | Java / any SQL-first team | Plain versioned files like `V2__add_orders_table.sql`, run in order, history table records them. Paid undo feature. |
| **Alembic** | Python (FastAPI / SQLAlchemy) | Python scripts with an upgrade/downgrade step, often auto-generated from your data models. |
| **Prisma Migrate** | Node / TypeScript | You edit a schema file; it generates the SQL. In production CI runs `prisma migrate deploy`, which only applies pending migrations. |
| **Liquibase, Atlas, goose, dbmate** | Various | Same idea — ordered changelogs or declarative "desired state" files — with more enterprise features. Overkill for a two-person team. |

Sources: https://www.saasturf.com/blog/database-migration/ (index); https://www.bytebase.com/blog/top-database-schema-change-tool-evolution/ (index).

**How CI/CD fits in** (CI/CD = "continuous integration / continuous deployment": a robot that tests and ships your code whenever you push to Git). The typical flow: on a pull request, the robot starts a throwaway database and replays *all* migrations from scratch to prove they work; on merge to `main`, it runs the migrate command against the live database *before* the new app/server starts. That is exactly what Supabase's GitHub integration and GitHub Actions do for you — see §3.

### 3. Specifically for Supabase: deploying Postgres functions and schema automatically

#### The recommended path, from Supabase's own docs

Supabase's deployment docs describe the workflow as three steps: develop locally with the Supabase CLI, push changes to GitHub, deploy automatically to your Supabase project from your `main` branch — and "this workflow works on all plans and does not require branching". You can automate it with the Supabase GitHub integration (recommended), the Supabase CLI in your own pipeline, or the Terraform provider. Branching (a separate preview database for each pull request) is the only part that needs the Pro plan. Sources, verified live: https://supabase.com/docs/guides/deployment and https://supabase.com/docs/guides/deployment/managing-environments

What gets deployed this way: database migrations in your `supabase/` directory, plus Edge Functions and Storage buckets declared in `supabase/config.toml`. Source: https://supabase.com/docs/guides/deployment (verified live).

#### How migrations work in Supabase

- Create a migration with `supabase migration new <name>` — it makes `supabase/migrations/<timestamp>_<name>.sql`. Put your SQL in it. A function change is just a migration containing `CREATE OR REPLACE FUNCTION ...` with the new function body. If you change a function's signature (its inputs or return type), Postgres rejects `CREATE OR REPLACE` — you must `DROP FUNCTION` first in the same migration (a real-world Supabase project documents this gotcha: https://docs.supanet.io/docs/building/deploy, index).
- Supabase tracks what has run in a table called `supabase_migrations.schema_migrations`. When you run `supabase db push`, it compares your local `supabase/migrations/` folder with that table and runs only the ones not yet applied, in timestamp order.
- The golden rule, quoted from the docs: **"never change the remote database directly. Once you're using migrations, all schema changes — even small ones — should go through migration files. Using the Dashboard's SQL editor or Table Editor on your remote database bypasses the migration history, and `db push` will start failing with sync errors."** Source, verified live: https://supabase.com/docs/guides/deployment/database-migrations
- If your current live database was built by hand-running `supabase_schema.sql`, the one-time fix is `supabase db pull`: it captures the current live schema as a first migration file, so the tracking table and your files start in sync. After that, never hand-run the big file again. Source: https://supabase.com/docs/guides/deployment/managing-environments (verified live).

#### The two automatic options

**Option A — Supabase GitHub integration (simplest).** In the Supabase dashboard, connect your GitHub repo and enable "Deploy to production". Merging to `main` then applies new migrations automatically. Supabase's production checklist says exactly this: "Connect your GitHub repository and enable Deploy to production in the integration settings to automate deployments from your `main` branch… This ensures schema changes are deployed consistently and avoids manual `supabase db push --remote` from a local machine." Source: https://supabase.com/docs/guides/deployment/going-into-prod (index). It works on all plans, including free — Supabase announced in April 2026 that "GitHub integration is now available on all plans. Connect your repo on the free tier to deploy migrations from your main branch via CI/CD, no branching required." Source: https://supabase.com/changelog/44713-developer-update-april-2026 (index).

**Option B — Your own GitHub Action running `supabase db push`.** Supabase's "Managing Environments" guide gives this as the recommended production setup: create workflow files in `.github/workflows/`; the release job links the project and runs `supabase db push`, applying all new migration files merged into `supabase/migrations/`. It triggers on pushes to `main` (production) and `develop` (staging, if you have a second project). Source, verified live: https://supabase.com/docs/guides/deployment/managing-environments — and a working example of the same pattern in a real project: https://docs.supanet.io/docs/building/deploy (index), where a GitHub Action runs `supabase db push` whenever a file under `supabase/migrations/` lands on `main`, and "the CLI only applies what's pending… so merging a PR that adds a new migration file applies exactly that file — no manual step, safe to re-run."

#### Secrets: what is needed, and where it must live

| Secret | What it is | Where it lives |
|---|---|---|
| `SUPABASE_ACCESS_TOKEN` | A personal access token (PAT) — your developer login for Supabase's admin API and CLI. Supabase docs: grant it **Project Settings, API Keys, and API Key Secrets, all with Read access**, because the workflow runs `supabase link` first. | GitHub encrypted secrets (repository Settings → Secrets and variables → Actions). Never in Git, never in the game. |
| `SUPABASE_DB_PASSWORD` | Your project's database password (the Postgres password). `db push` connects straight to Postgres, so the token alone is not enough. | Same GitHub encrypted secrets. |
| `SUPABASE_PROJECT_ID` / project ref | The short ID in your dashboard URL. Not a secret, but keep it as a GitHub secret/variable for tidiness. | GitHub secrets/variables. |
| **Service role / secret key (`sb_secret_…`)** | The master key that bypasses Row Level Security (see §6). | **Not needed for migrations at all.** Never put it in GitHub Actions for this job, never in the game client. |
| **Publishable / anon key (`sb_publishable_…`)** | The public key the game client already uses. | Only this one belongs in the client. |

Sources: https://supabase.com/docs/guides/deployment/managing-environments (verified live); https://supabase.com/docs/guides/platform/personal-access-tokens (index); https://docs.supanet.io/docs/building/deploy (index).

**Cost.** The GitHub integration and CLI deployments work on all plans, including free (verified live: https://supabase.com/docs/guides/deployment). GitHub Actions itself is free for public repos on standard runners, and private repos on the free GitHub plan get about 2,000 Linux minutes a month — a migration run takes a minute or two, so this is effectively free for a two-person team. Source for Actions pricing: https://sengi.run/blog/github-actions-free-minutes (index, secondary source — check GitHub's current billing page if cost matters). One free-tier caveat from Supabase's production checklist: free projects may be paused after about 7 days with no activity; Pro removes pausing. Source: https://supabase.com/docs/guides/deployment/going-into-prod (index).

#### Two things that are *not* the deploy mechanism

- **Supabase Management API.** There is an admin API (`api.supabase.com`) with a `POST /v1/projects/<ref>/database/query` endpoint that can run raw SQL with a personal access token. It works, but it is not the recommended deploy path: it has no migration tracking, no version history, and no "only run what's new" logic, so it is easy to run the same change twice or lose track of what is live. It is a fallback for one-off fixes, not a replacement for migrations. Source: https://github.com/gilacoding/trippi/blob/HEAD/.agent/skills/supabase-management-sql-deploy/SKILL.md (index).
- **Database webhooks.** These are *not* for deploying schema. A database webhook fires when a row is inserted/updated/deleted and calls an HTTP endpoint (for example, to notify another service). They cannot create tables or replace functions, and they should not be confused with a deploy trigger.

### 4. Tuning and content changes WITHOUT a deploy at all

This is the "data-driven design" idea: **put numbers in data, not in code.** The game rules (the functions) read the numbers fresh every time they run, so changing a number changes the game immediately.

**Concrete examples from real games:**
- **Unity studio Ares Interactive** built a custom remote-config system with 50+ config areas (players, events, store items, rewards, battle passes). Events, store sales, offers, rewards and matchmaking tuning change "without waiting for a client release or server deployment"; servers pick the changes up within seconds without a restart; everything is versioned and logged, changes can be rolled back, and can be staged against internal test accounts first. Their rule: "If designers want to change it every week, it belongs in a bundle [config]. If it's art or code, it belongs in the build." Source: https://unity.com/blog/ares-interactive-live-service-games (index).
- **Heroic Labs' Satori** (used with the Nakama game server) calls this "remote configuration": shop prices, rewards and event schedules are feature flags (named settings the game reads from the server instead of its own code). "Without remote config, every LiveOps change requires a server or client update… Remote configuration removes it." Source: https://heroiclabs.com/docs/satori/concepts/remote-configuration/ (index).
- **Firebase Remote Config (Unity example):** a developer publishes a parameter such as `move_speed = 7`, the same installed game fetches it on next launch and moves at speed 7; publish `2` and it moves at 2 — no rebuild. It changes values only; it does not download new code. The tutorial also clamps accepted values (1–10) so a typo cannot set speed to 500. Source: https://medium.com/@fahiskkr90/tune-your-unity-game-without-rebuilding-with-firebase-remote-config-87c3af85ce3b (index). A tower-defence developer did the same with Firebase Realtime Database: turret damage, price and range live in the database and editing them changes the live game instantly. Source: https://www.facebook.com/reel/2238672073716018/ (index).
- **LiveOps in general:** the pattern is to move the *decision* of what is active, for whom, and from when onto the server, and leave the client to carry it out — using feature flags (on/off switches evaluated on the server, optionally for only some players), scheduled events stored as a single record, and a rollback plan. Source: https://federicocalo.dev/en/blog/live-operations-liveops-event-systems-feature-flags (index). Feature-flag services such as Flagsmith also carry numeric/JSON values, so a flag can *be* a tuning parameter. Source: https://www.varcore.dev/blog/feature-flags-unleash-flagsmith-and-growthbook-compared/ (index).

**How this maps to your Supabase game (no new service needed):** add tables such as `game_config` (one row per setting: key, value), `items` (id, name, price, damage, …), `quests` / `events` (id, start/end time, reward, enabled). Your existing Postgres functions already read tables — make them read these tables instead of using hard-coded numbers. Then:
- Change an item price → `UPDATE items SET price = …` in the dashboard (or a tiny admin page) → the next player action uses it. No migration, no deploy, no client update.
- Run a weekend event → insert/update one `events` row with start/end times; functions check "is an event active now?".
- Kill-switch a broken feature → flip an `enabled` flag to false; functions check the flag first.
- Safety: keep a `version` / `updated_at` on the config, validate ranges inside the function (reject absurd values), and keep the *code* that interprets the numbers fixed — config can change numbers, never logic. That last point is what keeps this safe: a bad number can unbalance the game, but it cannot rewrite the rules.

### 5. What small indie teams actually do in practice

There is no secret indie-only method — small teams copy the same migration + CI pattern, just with one project instead of staging + production, and often with no staging at all.

- **A real Supabase indie game (Xor0, a browser multiplayer board game):** Supabase Auth, Postgres as the source of truth, all changes through `SECURITY DEFINER` RPCs, clients read-only via RLS, migrations in `supabase/migrations/0001… 0003…`, and a GitHub Action that builds and publishes on push to `main`; Supabase values are injected from GitHub Actions variables, and migrations are applied with `supabase db push`. Source: https://github.com/jonemo/xor0-multiplayer/blob/HEAD/CLAUDE.md (index).
- **A Godot 4.6 MMO (Legends MMO):** one Godot project, a headless authoritative server that holds the service-role key, owns gameplay/economy writes, and uses database functions for currency/item exchanges; schema in `supabase/migrations/*.sql`. Its own architecture review flags "unversioned database deployment state" as a risk — i.e. exactly the manual-file problem you have now. Source: https://github.com/voullume/legends-mmo/blob/HEAD/docs/PROJECT_ARCHITECTURE_2.md (index).
- **A Supabase + Vite project (SupaNet):** schema in sequentially numbered `supabase/migrations/`, a GitHub Action that runs `supabase db push` whenever a migration lands on `main`, and the rule "from then on you never apply migrations by hand". Source: https://docs.supanet.io/docs/building/deploy (index).
- **Godot/Unity indie multiplayer more broadly:** teams that outgrow a pure database backend typically use an open-source authoritative server such as Nakama (free, self-hosted, Go/Lua/TypeScript logic, Docker deploy) or a managed backend such as PlayFab / Unity Gaming Services, which bundle remote config, LiveOps events and A/B testing. Those are a bigger move — new server to host and new code to write — and are *not* needed to solve your problem, which is only the deploy step for functions you already have. Sources: https://www.metaplay.io/comparisons/metaplay-vs-nakama (index); https://www.metaplay.io/comparisons/liveops-platforms-compared (index).

**The setup a two-person team can copy** is therefore the one in §3, Option A or B: Git repo → push to `main` → GitHub applies the migrations. It needs no extra server, no paid plan, and about an hour to set up once (see §7).

### 6. Security: why the game client itself must not apply updates

**The short version:** the client runs on the player's computer, and the player controls that computer. Anything the client can do, a determined player can do — including things you never intended. So the power to change the rules must live somewhere the player cannot reach.

**Why a player's login/session token cannot be the update mechanism:**
- A session token proves *who* the player is ("I am player 123"). It does not prove they are a developer, and it carries no database-admin power. In Supabase, a logged-in player acts as the `authenticated` role, which is still filtered by Row Level Security (RLS — the per-row permission rules on your tables). That role has no `CREATE TABLE`, `ALTER FUNCTION` or `DROP` privilege, and PostgREST (the API the client talks to) does not even offer a "run arbitrary SQL" endpoint to that role.
- The *only* ways to let the client do it would be to (a) ship the database password or a personal access token inside the game, or (b) create a powerful `SECURITY DEFINER` function (a function that runs with its owner's — i.e. admin's — privileges and skips RLS) that any logged-in player can call, e.g. `apply_update(sql_text)`. Both are fatal:
  - (a) A shipped Python/wxPython program can be unpacked and read. The password/token would be public within hours. Anyone could then connect directly to Postgres, change any function, grant themselves items, read other players' data, or drop tables.
  - (b) If any player can call "run this SQL as admin", they do not need the password — they just call your function with *their* SQL. Supabase's own security advisor warns about exactly this shape: a `SECURITY DEFINER` function callable by `anon`/`authenticated` "runs with the privileges of its owner rather than the caller… anyone with the public anon key can call it… and potentially read or modify data that RLS would normally block." Source: https://supabase.com/docs/guides/observability/advisors?lint=0011_performance_security_definer_function (index).

**What would go wrong if a player could change the rules:** unlimited currency/items for themselves, rewriting the damage or reward formulas, deleting or corrupting other players' progress, locking everyone else out, or quietly changing a function to leak data. This is not theoretical — it is the core reason for "server-authoritative" design: "the client only sends intent (inputs, fire requests, etc.), and the server is the one that decides what really happens"; "if players can gain advantage by lying, it should run on the server"; "the game client runs on hardware the player controls. Any data the client holds… can be read and changed." Sources: https://accelbyte.io/blog/server-authoritative-logic-to-prevent-cheating (index); https://300mind.studio/blog/anti-cheat-for-multiplayer-games/ (index); https://www.multiplayguide.com/blog/anti-cheat-multiplayer-game-security/ (index).

**How real games keep rule-changing power away from players while still updating automatically:**
- **Separate identities.** Players authenticate as players (publishable key + their own login). Developers deploy as developers (personal access token + database password), and those credentials live only on developer machines and in the CI system's encrypted secrets — never in a shipped game, never in Git.
- **The deployer is a trusted machine, not a player.** GitHub's runner is a fresh computer owned by GitHub that runs your workflow and then disappears. It is the *only* thing (besides your own laptops) that holds the deploy credentials.
- **The client key is public by design, and that is fine — because RLS is the real lock.** The publishable/anon key "is meant to be public and shipped in your frontend. It is safe to expose *only* because row-level security is supposed to stand between it and your data." The service-role key, by contrast, "bypasses RLS entirely and must never appear in client code, shipped env vars or a public repo" — a leak is "a full compromise of your database". Sources: https://www.codesecure.in/blogs/supabase-anon-key-service-role-key-security (index); https://www.stingrai.io/blog/supabase-powerful-but-one-misconfiguration-away-from-disaster (index).
- **Even the powerful functions are guarded.** Your game-rule functions are `SECURITY DEFINER` by necessity (they need to change data the caller cannot touch directly), so each one must check inside its own body that the caller is who they claim to be (`auth.uid()` — the logged-in player's ID from their token) and that the action is legal for that player, and must pin its `search_path` (the list of schemas it looks in) so it cannot be tricked. Never expose a generic "run SQL" function. Sources: https://supabase.com/docs/guides/observability/advisors?lint=0011_performance_security_definer_function (index); https://scan.testavi.com/blog/supabase-security-definer-functions (index).
- **Review before deploy.** Because a bad migration can break the live game, teams deploy from a reviewed merge to `main` (a second pair of eyes, even in a two-person team), not from an automatic trigger on every player's machine. A GitHub branch-protection rule requiring the other developer's approval on `main` is the free version of this.

### 7. Recommendations: the 2–3 simplest options for this team, ranked by ease

| Rank | Option | What you need | Cost | What it solves | What it does NOT solve |
|---|---|---|---|---|---|
| **1 — Easiest** | **Supabase GitHub integration: "Deploy to production"** | A GitHub repo containing your `supabase/` folder; Supabase dashboard access to connect the repo and switch the toggle on. No workflow file, no secrets to type in. | Free — works on all plans including free (verified live, §3). | The manual step, completely: merge a migration to `main` → it is applied to live. Consistent, repeatable, with a history in Git. | Does not test migrations before they run (add a local `db reset` check before merging); does not deploy non-database config (auth settings etc. are separate); does not make tuning changes deploy-free — that is §4, below. Branching/preview DBs for pull requests need Pro. |
| **2 — Almost as easy, more control** | **Your own GitHub Action running `supabase db push`** | Same GitHub repo; three encrypted GitHub secrets (`SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, project ID); one small workflow file (`.github/workflows/deploy.yml`, using `supabase/setup-cli@v1`, then `supabase link` + `supabase db push`), following Supabase's "Managing Environments" guide. | Free — GitHub Actions free for public repos; ~2,000 free Linux minutes/month for private repos on the free plan. | Same as #1, plus you control exactly when it runs (e.g. only when `supabase/migrations/**` changes), you can add a test step first (replay migrations on a throwaway local DB), and you can later add a second staging project. | Same limits as #1. Slightly more setup and one more thing to maintain. If you pick #1, do not also run #2 against the same project — two deployers will fight over the migration history. |
| **3 — Do alongside 1 or 2, not instead of them** | **Data-driven config tables (+ keep manual `db push` as a fallback while you set up 1/2)** | New tables (`game_config`, `items`, …) added via one migration; change your functions to read numbers from those tables instead of hard-coded values. As a fallback, one developer runs `supabase db push` from their own laptop after merging — still manual, but at least versioned and repeatable, unlike hand-running a file in the dashboard. | Free. | Most day-to-day changes (prices, damage, rewards, events, kill-switches) need **no deploy at all** — just an `UPDATE` in the dashboard. This is where the biggest time saving actually comes from. | Does not deploy new rules/features — a new function or a new table still needs a migration via #1/#2. A bad config value can still unbalance the game, so validate ranges in the functions. |

**Suggested order of work:**
1. **Today:** one-time `supabase db pull` to capture the live schema as your first migration, then split future changes into new timestamped migration files. Stop hand-running the big file in the dashboard.
2. **This week:** turn on Option 1 (GitHub integration). If you prefer to see exactly what runs, do Option 2 instead — pick one, not both.
3. **Next:** move the three or four numbers you change most often into a `game_config` / `items` table (Option 3). Every future tuning change then takes seconds.
4. **Later, only if you need it:** a second (staging) Supabase project on `develop`, and a branch-protection rule requiring the other developer to approve merges to `main`. Both are optional at your size.

---

## Could not verify / open questions

- **Exact current GitHub Actions free-minute figures** were taken from a secondary summary (https://sengi.run/blog/github-actions-free-minutes, index), not from GitHub's own billing docs; GitHub now expresses the allowance as a dollar amount ($12/month on Free ≈ 2,000 Linux minutes). The conclusion — effectively free for this team's usage — does not depend on the exact number, but confirm on GitHub's billing page if you plan heavy CI use.
- **Free-tier pausing** (projects paused after ~7 days of inactivity) is stated in Supabase's production checklist as read via search results, not opened live in this session; treat as "reported in Supabase docs", and check the checklist if uptime matters.
- **No live test was run** against the team's actual Supabase project, repo, or game client — the recommendations are based on the documented patterns, not on trying the deploy against their project. The first `db pull` / `db push` should be tried on a copy or at a quiet time, and a database backup taken before the first automated push.
- **Management API / database-webhook details** are from secondary sources; they are included only to rule them out as deploy mechanisms, and that conclusion (they are not the recommended deploy path) is supported by Supabase's own docs recommending the GitHub integration / CLI instead.

## Sources

*Read 18 November 2026. "Verified live" = opened with the browser and read directly. "Index" = found via web search results.*

**Supabase official docs (verified live unless noted)**
- Deployment & Branching — https://supabase.com/docs/guides/deployment
- Managing Environments (GitHub Actions, secrets, `db push`) — https://supabase.com/docs/guides/deployment/managing-environments
- Deploy database migrations (golden rule, tracking table) — https://supabase.com/docs/guides/deployment/database-migrations
- Production Checklist (GitHub integration, free-plan pausing) — https://supabase.com/docs/guides/deployment/going-into-prod (index)
- Deploy Edge Functions — https://supabase.com/docs/guides/functions/deploy (index)
- Personal Access Tokens (permissions for `supabase link`) — https://supabase.com/docs/guides/platform/personal-access-tokens (index)
- GitHub integration on all plans, April 2026 changelog — https://supabase.com/changelog/44713-developer-update-april-2026 (index)
- Security advisor: `SECURITY DEFINER` functions — https://supabase.com/docs/guides/observability/advisors?lint=0011_performance_security_definer_function (index)

**Migrations & deployment in general (index)**
- Database Migration: A Founder's Guide — https://www.saasturf.com/blog/database-migration/
- Top Database Schema Migration Tools 2026 — https://www.bytebase.com/blog/top-database-schema-change-tool-evolution/
- Zero-Downtime Hotfixes and Client/Server Versioning for Live Multiplayer Games — https://www.teamcoherence.com/live-service-game-backend/
- How to update your game without impacting player experience — https://www.gamedeveloper.com/business/how-to-update-your-game-without-impacting-player-experience-or-revenue

**LiveOps / data-driven tuning (index)**
- How Ares Interactive builds live service games in Unity — https://unity.com/blog/ares-interactive-live-service-games
- Remote configuration (Satori / Heroic Labs) — https://heroiclabs.com/docs/satori/concepts/remote-configuration/
- Game LiveOps: Feature Flags, A/B Tests and Rollback — https://federicocalo.dev/en/blog/live-operations-liveops-event-systems-feature-flags
- Tune Your Unity Game Without Rebuilding with Firebase Remote Config — https://medium.com/@fahiskkr90/tune-your-unity-game-without-rebuilding-with-firebase-remote-config-87c3af85ce3b
- Firebase Realtime Database as live game config (tower defence walkthrough) — https://www.facebook.com/reel/2238672073716018/
- Feature Flags in 2026: Unleash, Flagsmith and GrowthBook Compared — https://www.varcore.dev/blog/feature-flags-unleash-flagsmith-and-growthbook-compared/
- LiveOps Platforms Compared: Metaplay, PlayFab, Satori, Beamable, Unity — https://www.metaplay.io/comparisons/liveops-platforms-compared

**Security / server authority (index)**
- Server-Authoritative Game Logic to Prevent Cheating — https://accelbyte.io/blog/server-authoritative-logic-to-prevent-cheating
- Multiplayer Game Anti-Cheat: Options for Small and Mid-Size Studios — https://300mind.studio/blog/anti-cheat-for-multiplayer-games/
- Anti-Cheat & Multiplayer Security: Protecting Online Games — https://www.multiplayguide.com/blog/anti-cheat-multiplayer-game-security/
- Is the Supabase Anon Key Safe to Expose? — https://www.codesecure.in/blogs/supabase-anon-key-service-role-key-security
- Supabase Anon Key: Is It Safe to Expose? RLS and 2026 Keys — https://www.stingrai.io/blog/supabase-powerful-but-one-misconfiguration-away-from-disaster
- SECURITY DEFINER functions: the Supabase RLS bypass hiding in your RPC endpoints — https://scan.testavi.com/blog/supabase-security-definer-functions

**Indie practice / real examples (index)**
- Xor0 multiplayer (Supabase RPCs + migrations + GitHub Actions) — https://github.com/jonemo/xor0-multiplayer/blob/HEAD/CLAUDE.md
- Legends MMO architecture (Godot + Supabase, service-role server) — https://github.com/voullume/legends-mmo/blob/HEAD/docs/PROJECT_ARCHITECTURE_2.md
- SupaNet deploy docs (GitHub Action running `supabase db push`) — https://docs.supanet.io/docs/building/deploy
- Metaplay vs Nakama — https://www.metaplay.io/comparisons/metaplay-vs-nakama
- Supabase Management API SQL deploy (why it is a fallback, not the path) — https://github.com/gilacoding/trippi/blob/HEAD/.agent/skills/supabase-management-sql-deploy/SKILL.md
- How many GitHub Actions minutes are free? (2026) — https://sengi.run/blog/github-actions-free-minutes

*Working notes: `notes/source-01-supabase-docs.md`, `notes/source-02-migrations-liveops.md`, `notes/source-03-security-indie.md`.*
