-- Arena of Makers: one shared table for everything.
-- Run once, in Supabase Dashboard, SQL Editor, on the
-- arena-of-makers project. Then the game can save online.
--
-- ONE table, called players. One row per player. All account
-- data lives in that one row:
--   player_code  the code friends look a player up by
--   username     what friends see; also the fighter's name
--   gender       male or female (picks the voice)
--   kind         robot or chef
--   fighter      the whole fighter, as JSON: name, kind, level,
--                weapon, armor, points, wins, losses, and so on.
--                New fighter fields keep working without
--                changing this table.
--   events       that player's game actions, as a JSON list:
--                fights, upgrades, key presses, setting
--                changes. Each entry is {action, detail,
--                created_at}. No keys, passwords or tokens are
--                ever stored here.
--
-- This is the simple version for a small friends game: the
-- publishable key can read and write players. That is what
-- lets any player fight any other player's fighter. It also
-- means anyone with the publishable key can see players.
-- If the game ever opens to strangers, add Supabase Auth and
-- tighten these policies so each player can only write
-- their own row.
--
-- If you already made the older three tables (players,
-- fighters, game_events) from an earlier version of this
-- file, the two extra tables are dropped here first, so
-- there is only one shared table left. That drops any data
-- in those two tables; they held no live game data yet.

drop table if exists game_events cascade;
drop table if exists fighters cascade;

create table if not exists players (
  player_code text primary key,
  username text unique not null,
  gender text,
  kind text,
  fighter jsonb not null default '{}'::jsonb,
  events jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table players enable row level security;

drop policy if exists "Players can read accounts" on players;
create policy "Players can read accounts"
  on players for select
  to anon
  using (true);

drop policy if exists "Players can make accounts" on players;
create policy "Players can make accounts"
  on players for insert
  to anon
  with check (true);

drop policy if exists "Players can update accounts" on players;
create policy "Players can update accounts"
  on players for update
  to anon
  using (true)
  with check (true);
