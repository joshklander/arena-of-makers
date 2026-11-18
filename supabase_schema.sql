-- Arena of Makers: secure server setup.
-- Run once, in Supabase Dashboard, SQL Editor, on the
-- arena-of-makers project. It is safe to run again: tables
-- are only made when missing, and functions are replaced.
--
-- HOW THE SECURITY WORKS
--
-- 1. The tables live in a private schema, arena_private.
--    The publishable key in the game's .env cannot see them,
--    read them, or change them at all.
--
-- 2. The game can only call the arena_* functions below.
--    Each one checks who is signed in, then does one thing.
--    The server runs every game rule itself: fights, dice
--    rolls, experience, levels, credits, upgrade costs and
--    timers, using its own clock. The game only shows what
--    the server sends back, so editing the game cannot
--    change a fighter's stats.
--
-- 3. Passwords are never stored. The server keeps only a
--    bcrypt hash, which cannot be turned back into the
--    password. Five wrong tries lock that account for ten
--    minutes. No function ever returns the hash.
--
-- 4. Signing in gives the game a random session token. The
--    game keeps it in memory only, never on disk. The server
--    stores only a SHA-256 hash of it. A session ends when
--    the game closes, or after 12 hours with no activity.
--
-- 4b. "Keep me signed in" is a separate random token, only
--    made when the player turns it on. The game keeps it in
--    Windows Credential Manager, never in a file. The server
--    stores only its hash. Each launch swaps it for a new one,
--    it stops working after 30 days unused, and turning the
--    setting off deletes it on the server.
--
-- 5. A player code is public: friends use it to look a
--    player up. Looking a player up shows only their
--    username, kind, level, wins, losses and gear. Their
--    game history is only visible to them, through export.
--
-- No key, token or password belongs in this file.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists arena_private;
revoke all on schema arena_private from public;
revoke all on schema arena_private from anon, authenticated;

create table if not exists arena_private.players (
  player_code text primary key,
  username text not null check (char_length(username) between 1 and 30),
  username_key text generated always as (lower(username)) stored unique,
  password_hash text not null,
  gender text not null check (gender in ('male', 'female')),
  kind text not null check (kind in ('robot', 'chef')),
  fighter jsonb not null,
  events jsonb not null default '[]'::jsonb,
  failed_logins integer not null default 0,
  locked_until timestamptz,
  last_fight_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- A player code is exactly 4 digits, like 4827. Leading
-- zeros count, so 0042 is a code too.
alter table arena_private.players
  drop constraint if exists players_player_code_check;
alter table arena_private.players
  add constraint players_player_code_check check (player_code ~ '^[0-9]{4}$');

create table if not exists arena_private.sessions (
  token_hash text primary key,
  player_code text not null
    references arena_private.players (player_code) on delete cascade,
  created_at timestamptz not null default now(),
  last_seen timestamptz not null default now()
);
create index if not exists sessions_player_code_idx
  on arena_private.sessions (player_code);
create index if not exists sessions_last_seen_idx
  on arena_private.sessions (last_seen);

create table if not exists arena_private.remembered (
  token_hash text primary key,
  player_code text not null
    references arena_private.players (player_code) on delete cascade,
  created_at timestamptz not null default now(),
  last_used timestamptz not null default now()
);
create index if not exists remembered_player_code_idx
  on arena_private.remembered (player_code);

revoke all on all tables in schema arena_private from public, anon, authenticated;

-- ---------------------------------------------------------------
-- Private helpers. Not callable by the game.
-- ---------------------------------------------------------------

create or replace function arena_private.now_epoch()
returns double precision
language sql stable
set search_path = ''
as $$ select extract(epoch from now())::double precision $$;

create or replace function arena_private.format_time(p_seconds double precision)
returns text
language plpgsql immutable
set search_path = ''
as $$
declare
  s integer := greatest(0, floor(p_seconds)::integer);
  minutes integer;
  hours double precision;
begin
  if s < 60 then
    return 'less than a minute';
  end if;
  if s < 3600 then
    minutes := round(s / 60.0)::integer;
    if minutes <= 1 then
      return 'about 1 minute';
    end if;
    return format('about %s minutes', minutes);
  end if;
  hours := s / 3600.0;
  if hours < 2 then
    return 'about 1 hour';
  end if;
  return format('about %s hours', round(hours::numeric)::integer);
end;
$$;

create or replace function arena_private.new_fighter(
  p_name text, p_kind text, p_gender text)
returns jsonb
language sql immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'name', p_name,
    'kind', p_kind,
    'gender', p_gender,
    'level', 1,
    'xp', 0,
    'hp', 100,
    'max_hp', 100,
    -- The upgrade currency is called "credits". Fighters
    -- made before the rename carry "points" instead;
    -- apply_timers converts them 1-for-1 on next sign-in.
    'credits', 0,
    'wins', 0,
    'losses', 0,
    'weapon_name', case when p_kind = 'robot' then 'Laser Blaster' else 'Trusty Spatula' end,
    'weapon_level', 1,
    'armor_name', case when p_kind = 'robot' then 'Scrap Plating' else 'Chef Apron' end,
    'armor_level', 1,
    -- The 5 level-up stats, all starting at 0. Unspent
    -- stat points sit in "stat_points": 2 per level-up,
    -- bankable, spendable any time, in any distribution.
    'stats', '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb,
    'stat_points', 0,
    -- New fighters need no migration.
    'stats_migrated', true,
    -- Respecs used: the first is free, later ones cost credits.
    'respecs_used', 0,
    'repair_until', 0,
    'upgrade', null,
    -- Queued levels left for a max-affordable upgrade.
    'upgrade_queue', null,
    'upgrade_total', 0
  )
$$;

-- The fighter as the game sees it: the stored fighter plus
-- the player's code and username.
create or replace function arena_private.fighter_out(
  p_fighter jsonb, p_code text, p_username text)
returns jsonb
language sql immutable
set search_path = ''
as $$
  select p_fighter || jsonb_build_object('player_code', p_code, 'username', p_username)
$$;

-- ---------------------------------------------------------------
-- Stats helpers (STATS_DESIGN.md). The server is the only
-- judge of stats, exactly as it is of fights: the game never
-- decides a stat, it only shows what the server sends back.
-- ---------------------------------------------------------------

-- The fighter's spendable balance. Credits first; fighters
-- made before the rename may still carry "points", which
-- count 1-for-1 until apply_timers converts them. A zero
-- credits balance still falls through to points, so a
-- fighter that has not been converted yet is never read
-- as broke.
create or replace function arena_private.credits_of(p_fighter jsonb)
returns numeric
language sql immutable
set search_path = ''
as $$
  select case
    when coalesce((p_fighter ->> 'credits')::numeric, 0) > 0
      then (p_fighter ->> 'credits')::numeric
    else coalesce((p_fighter ->> 'points')::numeric, 0)
  end
$$;

-- One of the 5 stats, or 0 when the fighter has no stats yet.
create or replace function arena_private.stat_value(p_fighter jsonb, p_stat text)
returns integer
language sql immutable
set search_path = ''
as $$
  select coalesce((p_fighter -> 'stats' ->> p_stat)::integer, 0)
$$;

-- Max health: 100, plus 10 for every level above 1 (health
-- always grows with level, no matter what the player
-- chooses), plus 10 for every Health point on top.
create or replace function arena_private.fighter_max_hp(p_fighter jsonb)
returns integer
language sql immutable
set search_path = ''
as $$
  select 100 + 10 * ((p_fighter ->> 'level')::integer - 1)
       + 10 * arena_private.stat_value(p_fighter, 'health')
$$;

-- Critical-hit chance in percent, diminishing returns, never
-- a cap: 50 x Luck / (Luck + 25).
create or replace function arena_private.crit_chance(p_luck integer)
returns numeric
language sql immutable
set search_path = ''
as $$
  select case when coalesce(p_luck, 0) <= 0 then 0::numeric
         else 50.0 * p_luck / (p_luck + 25) end
$$;

-- Dodge chance in percent when faster than the enemy,
-- diminishing returns, never reaching 20 percent:
-- 20 x advantage / (advantage + 20).
create or replace function arena_private.dodge_chance(p_advantage integer)
returns numeric
language sql immutable
set search_path = ''
as $$
  select case when coalesce(p_advantage, 0) <= 0 then 0::numeric
         else 20.0 * p_advantage / (p_advantage + 20) end
$$;

-- Split stat points by fixed weights, largest remainder,
-- ties broken in the order the weights are given. Weights
-- are (strength, defense, health, speed, luck).
create or replace function arena_private.distribute_points(
  p_total integer, p_strength integer, p_defense integer,
  p_health integer, p_speed integer, p_luck integer)
returns jsonb
language plpgsql immutable
set search_path = ''
as $$
declare
  v_sum integer := greatest(1, p_strength + p_defense + p_health + p_speed + p_luck);
  v_total integer := greatest(0, coalesce(p_total, 0));
  v_names text[] := array['strength', 'defense', 'health', 'speed', 'luck'];
  v_weights integer[] := array[p_strength, p_defense, p_health, p_speed, p_luck];
  v_base integer[] := array[0, 0, 0, 0, 0];
  v_frac numeric[] := array[0, 0, 0, 0, 0];
  v_given integer := 0;
  v_left integer;
  v_exact numeric;
  i integer;
  j integer;
  v_out jsonb := '{}'::jsonb;
begin
  for i in 1..5 loop
    v_exact := v_total * v_weights[i]::numeric / v_sum;
    v_base[i] := floor(v_exact)::integer;
    v_frac[i] := v_exact - v_base[i];
    v_given := v_given + v_base[i];
  end loop;
  v_left := v_total - v_given;
  -- Hand the leftover points to the largest fractions, in
  -- order when fractions tie (earliest first).
  while v_left > 0 loop
    j := 1;
    for i in 2..5 loop
      if v_frac[i] > v_frac[j] then
        j := i;
      end if;
    end loop;
    v_base[j] := v_base[j] + 1;
    v_frac[j] := -1;
    v_left := v_left - 1;
  end loop;
  for i in 1..5 loop
    v_out := v_out || jsonb_build_object(v_names[i], v_base[i]);
  end loop;
  return v_out;
end;
$$;

-- The Scrap Rat's stats: the same 2 points per level as a
-- fighter, split evenly across the 5 stats, so fights stay
-- even as the fighter builds stats.
create or replace function arena_private.creature_stats(p_level integer)
returns jsonb
language sql immutable
set search_path = ''
as $$
  select arena_private.distribute_points(
    2 * (greatest(1, p_level) - 1), 2, 2, 2, 2, 2)
$$;

-- Finish an upgrade or a repair whose time is up.
create or replace function arena_private.apply_timers(
  p_fighter jsonb, p_now double precision,
  out fighter jsonb, out messages jsonb)
language plpgsql immutable
set search_path = ''
as $$
declare
  f jsonb := p_fighter;
  up jsonb := p_fighter -> 'upgrade';
  repair double precision := coalesce((p_fighter ->> 'repair_until')::double precision, 0);
  v_queue jsonb;
  v_next integer;
  v_total integer;
  v_pts numeric;
  v_pts_text text;
  v_level integer;
  v_grant integer;
begin
  messages := '[]'::jsonb;

  -- Credits rename, once: a fighter carrying the old
  -- "points" balance gets it copied to "credits" 1-for-1,
  -- and the old key goes away. After the first launch this
  -- does nothing, because credits already exists.
  if (f ? 'points') and not (f ? 'credits') then
    v_pts := coalesce((f ->> 'points')::numeric, 0);
    v_pts_text := case when v_pts = floor(v_pts)
      then floor(v_pts)::bigint::text else v_pts::text end;
    f := (f - 'points') || jsonb_build_object('credits', v_pts);
    messages := messages || to_jsonb(
      format('Your points are now called credits. You have %s credits.',
        v_pts_text));
  end if;

  -- Stats migration, once: fighters made before stats get
  -- 2 banked stat points for every level already earned
  -- above level 1, and a flag so it only happens once.
  -- Weapon and armor levels, wins, losses, credits and XP
  -- are untouched; only the new stats fields are added.
  if not coalesce((f ->> 'stats_migrated')::boolean, false) then
    v_level := coalesce((f ->> 'level')::integer, 1);
    v_grant := 2 * greatest(0, v_level - 1);
    f := f || jsonb_build_object(
      'stats', coalesce(f -> 'stats',
        '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb),
      'stat_points', coalesce((f ->> 'stat_points')::integer, 0) + v_grant,
      'stats_migrated', true,
      'respecs_used', coalesce((f ->> 'respecs_used')::integer, 0),
      'upgrade_queue', coalesce(f -> 'upgrade_queue', 'null'::jsonb),
      'upgrade_total', coalesce((f ->> 'upgrade_total')::integer, 0));
    if v_grant > 0 then
      messages := messages || to_jsonb(
        format('You have %s stat points to spend. Would you like to choose your stats now?',
          v_grant));
    end if;
  end if;

  if up is not null and jsonb_typeof(up) = 'object'
     and (up ->> 'finish')::double precision <= p_now then
    f := jsonb_set(f, array[(up ->> 'slot') || '_level'], up -> 'level');
    v_queue := f -> 'upgrade_queue';
    if v_queue is not null and jsonb_typeof(v_queue) = 'array'
       and jsonb_array_length(v_queue) > 0 then
      -- A max-affordable queue: start the next level at once.
      v_next := (v_queue ->> 0)::integer;
      f := jsonb_set(f, '{upgrade}', jsonb_build_object(
        'slot', up ->> 'slot',
        'name', up ->> 'name',
        'level', v_next,
        'finish', p_now + least(60 * (v_next - 1), 4 * 3600)));
      f := jsonb_set(f, '{upgrade_queue}', v_queue - 0);
      messages := messages || to_jsonb(
        format('Your %s is now level %s.', up ->> 'name', up ->> 'level'));
    else
      f := jsonb_set(f, '{upgrade}', 'null'::jsonb);
      f := jsonb_set(f, '{upgrade_queue}', 'null'::jsonb);
      v_total := coalesce((f ->> 'upgrade_total')::integer, 0);
      f := jsonb_set(f, '{upgrade_total}', '0'::jsonb);
      messages := messages || to_jsonb(
        format('Your %s is now level %s.', up ->> 'name', up ->> 'level'));
      if v_total > 1 then
        messages := messages || to_jsonb(
          format('All %s levels are done.', v_total));
      end if;
    end if;
  end if;
  if repair > 0 and repair <= p_now then
    f := f || jsonb_build_object('hp', f -> 'max_hp', 'repair_until', 0);
    messages := messages || to_jsonb(
      'Repairs finished. Your fighter is back to full health.'::text);
  end if;
  fighter := f;
end;
$$;

-- Add one entry to a player's game history, keeping the
-- newest 200. by is 'server' for things the server did, and
-- 'game' for things the game reported, like key presses.
create or replace function arena_private.log_event(
  p_code text, p_action text, p_detail jsonb, p_by text)
returns void
language sql
set search_path = ''
as $$
  update arena_private.players p
  set events = (
    select coalesce(jsonb_agg(x.e order by x.n), '[]'::jsonb)
    from (
      select t.e, t.n
      from jsonb_array_elements(
        p.events || jsonb_build_array(jsonb_build_object(
          'action', p_action,
          'detail', coalesce(p_detail, '{}'::jsonb),
          'by', p_by,
          'created_at', now()))
      ) with ordinality as t(e, n)
      order by t.n desc
      limit 200
    ) x
  )
  where p.player_code = p_code
$$;

create or replace function arena_private.hash_token(p_token text)
returns text
language sql immutable
set search_path = ''
as $$ select encode(extensions.digest(p_token, 'sha256'), 'hex') $$;

create or replace function arena_private.new_session(p_code text)
returns text
language plpgsql
set search_path = ''
as $$
declare
  v_token text := encode(extensions.gen_random_bytes(32), 'hex');
begin
  insert into arena_private.sessions (token_hash, player_code)
  values (arena_private.hash_token(v_token), p_code);
  -- Tidy up: expired sessions, and more than 5 per player.
  delete from arena_private.sessions
  where last_seen < now() - interval '12 hours';
  delete from arena_private.sessions s
  where s.player_code = p_code
    and s.token_hash not in (
      select s2.token_hash from arena_private.sessions s2
      where s2.player_code = p_code
      order by s2.last_seen desc
      limit 5);
  return v_token;
end;
$$;

-- A new "keep me signed in" token. At most 5 per player.
create or replace function arena_private.new_remember(p_code text)
returns text
language plpgsql
set search_path = ''
as $$
declare
  v_token text := encode(extensions.gen_random_bytes(32), 'hex');
begin
  insert into arena_private.remembered (token_hash, player_code)
  values (arena_private.hash_token(v_token), p_code);
  delete from arena_private.remembered
  where last_used < now() - interval '30 days';
  delete from arena_private.remembered r
  where r.player_code = p_code
    and r.token_hash not in (
      select r2.token_hash from arena_private.remembered r2
      where r2.player_code = p_code
      order by r2.last_used desc
      limit 5);
  return v_token;
end;
$$;

-- The player code for a live session, or null. Marks the
-- session as just seen, which is what "online" means.
create or replace function arena_private.session_player(p_token text)
returns text
language plpgsql
set search_path = ''
as $$
declare
  v_code text;
begin
  if p_token is null or p_token !~ '^[0-9a-f]{64}$' then
    return null;
  end if;
  update arena_private.sessions
  set last_seen = now()
  where token_hash = arena_private.hash_token(p_token)
    and last_seen > now() - interval '12 hours'
  returning player_code into v_code;
  return v_code;
end;
$$;

create or replace function arena_private.signed_out()
returns jsonb
language sql immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'error', 'You are signed out. Close the game and sign in again.',
    'signed_out', true)
$$;

revoke all on all functions in schema arena_private from public, anon, authenticated;

-- ---------------------------------------------------------------
-- Functions the game calls, with the publishable key.
-- Each returns JSON. A plain-words problem comes back as
-- {"error": "..."}, never as a crash.
-- ---------------------------------------------------------------

create or replace function public.arena_create_account(
  p_username text, p_player_code text, p_password text,
  p_gender text, p_kind text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_name text := btrim(coalesce(p_username, ''));
  v_code text := upper(regexp_replace(coalesce(p_player_code, ''), '[[:space:]-]', '', 'g'));
  v_auto boolean;
  v_fighter jsonb;
  v_token text;
  v_try integer;
begin
  v_auto := v_code = '';
  if v_name = '' then
    return jsonb_build_object('error', 'Give yourself a username first.');
  end if;
  if char_length(v_name) > 30 then
    return jsonb_build_object('error', 'Pick a username no longer than 30 letters.');
  end if;
  if p_password is null or char_length(p_password) < 8 then
    return jsonb_build_object('error', 'Pick a password of at least 8 characters.');
  end if;
  if octet_length(p_password) > 72 then
    return jsonb_build_object('error', 'Pick a password no longer than 72 characters.');
  end if;
  if p_gender is null or p_gender not in ('male', 'female') then
    return jsonb_build_object('error', 'Pick male or female for your fighter.');
  end if;
  if p_kind is null or p_kind not in ('robot', 'chef') then
    return jsonb_build_object('error', 'Pick robot or chef for your fighter.');
  end if;
  if not v_auto and v_code !~ '^[0-9]{4}$' then
    return jsonb_build_object('error',
      'That code does not work: a player code is 4 digits, like 4827.');
  end if;
  if exists (select 1 from arena_private.players where username_key = lower(v_name)) then
    return jsonb_build_object('error',
      'That username is already taken. Pick a different username.');
  end if;

  v_fighter := arena_private.new_fighter(v_name, p_kind, p_gender);
  -- There are only 10,000 codes, so a picked code is retried
  -- more times when it is taken.
  for v_try in 1..20 loop
    if v_auto then
      v_code := lpad(floor(random() * 10000)::integer::text, 4, '0');
    end if;
    begin
      insert into arena_private.players
        (player_code, username, password_hash, gender, kind, fighter)
      values
        (v_code, v_name,
         extensions.crypt(p_password, extensions.gen_salt('bf', 10)),
         p_gender, p_kind, v_fighter);
      v_token := arena_private.new_session(v_code);
      perform arena_private.log_event(v_code, 'account_created', '{}'::jsonb, 'server');
      return jsonb_build_object(
        'token', v_token,
        'account', jsonb_build_object(
          'username', v_name, 'player_code', v_code,
          'gender', p_gender, 'kind', p_kind),
        'fighter', arena_private.fighter_out(v_fighter, v_code, v_name),
        'messages', '[]'::jsonb);
    exception when unique_violation then
      if exists (select 1 from arena_private.players where username_key = lower(v_name)) then
        return jsonb_build_object('error',
          'That username is already taken. Pick a different username.');
      end if;
      if not v_auto then
        return jsonb_build_object('error',
          'That player code is already taken. Pick a different code, or press Make a code for me.');
      end if;
    end;
  end loop;
  return jsonb_build_object('error', 'I could not make a free player code. Try again.');
end;
$$;

create or replace function public.arena_sign_in(
  p_player_code text, p_username text, p_password text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := upper(regexp_replace(coalesce(p_player_code, ''), '[[:space:]-]', '', 'g'));
  r arena_private.players%rowtype;
  t record;
  v_token text;
begin
  select * into r from arena_private.players where player_code = v_code for update;
  if not found then
    return jsonb_build_object('no_account', true);
  end if;
  if r.locked_until is not null and r.locked_until > now() then
    return jsonb_build_object('error',
      'Too many wrong tries for this account. Wait ten minutes, then try again.');
  end if;
  if r.username_key <> lower(btrim(coalesce(p_username, '')))
     or r.password_hash <> extensions.crypt(coalesce(p_password, ''), r.password_hash) then
    update arena_private.players
    set failed_logins = case when failed_logins + 1 >= 5 then 0 else failed_logins + 1 end,
        locked_until = case when failed_logins + 1 >= 5
                            then now() + interval '10 minutes' else locked_until end
    where player_code = v_code;
    return jsonb_build_object('error',
      'That username, player code and password do not match. Check them and try again.');
  end if;

  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  update arena_private.players
  set failed_logins = 0, locked_until = null,
      fighter = t.fighter, updated_at = now()
  where player_code = v_code;
  v_token := arena_private.new_session(v_code);
  perform arena_private.log_event(v_code, 'sign_in', '{}'::jsonb, 'server');
  return jsonb_build_object(
    'token', v_token,
    'account', jsonb_build_object(
      'username', r.username, 'player_code', r.player_code,
      'gender', r.gender, 'kind', r.kind),
    'fighter', arena_private.fighter_out(t.fighter, r.player_code, r.username),
    'messages', t.messages);
end;
$$;

create or replace function public.arena_sign_out(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_token is not null and p_token ~ '^[0-9a-f]{64}$' then
    delete from arena_private.sessions
    where token_hash = arena_private.hash_token(p_token);
  end if;
  return jsonb_build_object('ok', true);
end;
$$;

-- Heartbeat and refresh: keeps the player online, finishes
-- upgrades and repairs whose time is up, and returns the
-- fighter as the server has it.
create or replace function public.arena_state(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  if t.fighter is distinct from r.fighter then
    update arena_private.players
    set fighter = t.fighter, updated_at = now()
    where player_code = v_code;
  end if;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(t.fighter, r.player_code, r.username),
    'messages', t.messages);
end;
$$;

-- One fight against a Scrap Rat at the fighter's level. The
-- same rules as game_logic.fight, run on the server with the
-- server's own dice. Stats apply here: the faster side hits
-- first every round (a tie goes to the fighter), a faster
-- side may dodge, Luck may crit for x1.5, and no single hit
-- may deal more than 75% of the target's max health. The
-- Scrap Rat gets the same 2 stat points per level as a
-- fighter, split evenly, so fights stay even. p_opponent_code
-- is only recorded in the history, when the fight was started
-- from "Fight a player".
create or replace function public.arena_fight(
  p_token text, p_opponent_code text default null)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
  f jsonb;
  v_now double precision := arena_private.now_epoch();
  v_name text;
  lvl integer;
  -- Fighter stats.
  v_str integer;
  v_def integer;
  v_hea integer;
  v_spd integer;
  v_luk integer;
  -- Scrap Rat stats (same 2 points per level, even split).
  c_stats jsonb;
  c_str integer;
  c_hea integer;
  c_def integer;
  c_spd integer;
  c_luk integer;
  c_hp integer;
  c_max_hp integer;
  c_dmg integer;
  c_soak integer;
  c_speed integer;
  c_crit numeric;
  c_dodge numeric;
  dmg integer;
  def integer;
  f_max_hp integer;
  f_speed integer;
  f_crit numeric;
  f_dodge numeric;
  f_hp integer;
  fighter_first boolean;
  round_no integer := 0;
  v_turn integer;
  v_fighter_turn boolean;
  hit integer;
  v_crit boolean;
  lines jsonb;
  xp_gain integer;
  cr_gain numeric;
  cur_xp integer;
  new_level integer;
  new_max_hp integer;
  new_stat_points integer;
  gained integer := 0;
  lost numeric;
  wait integer;
  v_opp text := upper(regexp_replace(coalesce(p_opponent_code, ''), '[[:space:]-]', '', 'g'));
  v_won boolean;
  v_result jsonb;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  if r.last_fight_at is not null and r.last_fight_at > now() - interval '2 seconds' then
    return jsonb_build_object('error', 'Slow down a little. Wait a moment, then fight again.');
  end if;
  select * into t from arena_private.apply_timers(r.fighter, v_now);
  f := t.fighter;
  v_name := f ->> 'name';

  if coalesce((f ->> 'repair_until')::double precision, 0) > v_now then
    if f is distinct from r.fighter then
      update arena_private.players set fighter = f, updated_at = now()
      where player_code = v_code;
    end if;
    return jsonb_build_object(
      'won', null,
      'lines', jsonb_build_array(
        format('Your fighter is still repairing. %s left.',
          arena_private.format_time((f ->> 'repair_until')::double precision - v_now)),
        'You can visit the hangout or browse the shop while you wait.'),
      'xp', 0, 'credits', 0, 'levels_gained', 0,
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;

  lvl := (f ->> 'level')::integer;
  v_str := arena_private.stat_value(f, 'strength');
  v_def := arena_private.stat_value(f, 'defense');
  v_hea := arena_private.stat_value(f, 'health');
  v_spd := arena_private.stat_value(f, 'speed');
  v_luk := arena_private.stat_value(f, 'luck');
  c_stats := arena_private.creature_stats(lvl);
  c_str := (c_stats ->> 'strength')::integer;
  c_hea := (c_stats ->> 'health')::integer;
  c_def := (c_stats ->> 'defense')::integer;
  c_spd := (c_stats ->> 'speed')::integer;
  c_luk := (c_stats ->> 'luck')::integer;
  c_max_hp := 30 + 15 * (lvl - 1) + 10 * c_hea;
  c_hp := c_max_hp;
  c_dmg := 4 + 2 * (lvl - 1) + 2 * c_str;
  c_soak := c_def;
  c_speed := 5 + c_spd;
  c_crit := arena_private.crit_chance(c_luk);
  c_dodge := arena_private.dodge_chance(c_speed - (5 + v_spd));
  dmg := (case when f ->> 'kind' = 'robot' then 12 else 10 end)
         + 5 * ((f ->> 'weapon_level')::integer - 1) + 2 * (lvl - 1) + 2 * v_str;
  def := 2 + 2 * ((f ->> 'armor_level')::integer - 1) + (lvl - 1) + 2 * v_def;
  f_max_hp := arena_private.fighter_max_hp(f);
  f_speed := 5 + v_spd;
  f_crit := arena_private.crit_chance(v_luk);
  f_dodge := arena_private.dodge_chance(f_speed - c_speed);
  f_hp := (f ->> 'hp')::integer;
  fighter_first := f_speed >= c_speed;
  lines := jsonb_build_array(format('A Scrap Rat appears! Level %s.', lvl));

  while f_hp > 0 and c_hp > 0 and round_no < 20 loop
    round_no := round_no + 1;
    for v_turn in 1..2 loop
      exit when f_hp <= 0 or c_hp <= 0;
      v_fighter_turn := (fighter_first and v_turn = 1)
        or (not fighter_first and v_turn = 2);
      if v_fighter_turn then
        if random() * 100 < c_dodge then
          lines := lines || to_jsonb(format(
            'Round %s: The Scrap Rat dodges! Your hit misses.', round_no));
        else
          hit := dmg + floor(random() * 4)::integer;
          v_crit := random() * 100 < f_crit;
          if v_crit then
            hit := round(hit * 1.5)::integer;
          end if;
          hit := greatest(1, hit - c_soak);
          hit := least(hit, floor(0.75 * c_max_hp)::integer);
          c_hp := c_hp - hit;
          if v_crit then
            lines := lines || to_jsonb(format(
              'Round %s: Critical hit! %s hits the Scrap Rat for %s.',
              round_no, v_name, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: %s hits the Scrap Rat for %s.',
              round_no, v_name, hit));
          end if;
        end if;
      else
        if random() * 100 < f_dodge then
          lines := lines || to_jsonb(format(
            'Round %s: %s dodges! The Scrap Rat''s hit misses.',
            round_no, v_name));
        else
          hit := c_dmg + floor(random() * 3)::integer;
          v_crit := random() * 100 < c_crit;
          if v_crit then
            hit := round(hit * 1.5)::integer;
          end if;
          hit := greatest(1, hit - (def / 2));
          hit := least(hit, floor(0.75 * f_max_hp)::integer);
          f_hp := f_hp - hit;
          if v_crit then
            lines := lines || to_jsonb(format(
              'Round %s: Critical hit! The Scrap Rat hits %s for %s.',
              round_no, v_name, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: The Scrap Rat hits %s for %s.',
              round_no, v_name, hit));
          end if;
        end if;
      end if;
    end loop;
  end loop;

  if c_hp <= 0 then
    v_won := true;
    xp_gain := 20 + 5 * lvl;
    cr_gain := 10 + 5 * lvl;
    cur_xp := (f ->> 'xp')::integer + xp_gain;
    new_level := lvl;
    -- Health always grows with level: +10 max HP per level,
    -- whatever the player chooses.
    new_max_hp := (f ->> 'max_hp')::integer;
    while cur_xp >= 100 * new_level loop
      cur_xp := cur_xp - 100 * new_level;
      new_level := new_level + 1;
      new_max_hp := new_max_hp + 10;
      gained := gained + 1;
    end loop;
    new_stat_points := coalesce((f ->> 'stat_points')::integer, 0)
      + 2 * gained;
    f := f || jsonb_build_object(
      'xp', cur_xp,
      'level', new_level,
      'max_hp', new_max_hp,
      'hp', greatest(1, f_hp),
      'credits', arena_private.credits_of(f) + cr_gain,
      'stat_points', new_stat_points,
      'wins', (f ->> 'wins')::integer + 1);
    f := f - 'points';
    lines := lines || to_jsonb(format('You won! You earned %s experience and %s credits.',
      xp_gain, cr_gain));
    if gained > 0 then
      lines := lines || to_jsonb(format(
        'You are now level %s! Your health grew to %s. You have %s stat points to spend.',
        new_level, new_max_hp, new_stat_points));
    end if;
  else
    v_won := false;
    xp_gain := 0;
    lost := least(arena_private.credits_of(f), 5);
    cr_gain := -lost;
    wait := least(300 * lvl, 4 * 3600);
    f := f || jsonb_build_object(
      'credits', arena_private.credits_of(f) - lost,
      'losses', (f ->> 'losses')::integer + 1,
      'hp', 1,
      'repair_until', v_now + wait);
    f := f - 'points';
    lines := lines || to_jsonb(format('You lost. Your fighter needs repairs, %s.',
      arena_private.format_time(wait)));
    if lost > 0 then
      lines := lines || to_jsonb(format('You lost %s credits.', lost));
    end if;
    lines := lines || to_jsonb('While repairs run, you can still visit the hangout.'::text);
  end if;

  update arena_private.players
  set fighter = f, last_fight_at = now(), updated_at = now()
  where player_code = v_code;

  v_result := jsonb_build_object('won', v_won, 'xp', xp_gain, 'credits', cr_gain);
  if v_opp ~ '^[0-9]{4}$' then
    v_result := v_result || jsonb_build_object('opponent_code', v_opp);
  end if;
  perform arena_private.log_event(v_code, 'fight', v_result, 'server');

  return jsonb_build_object(
    'won', v_won,
    'lines', lines,
    'xp', xp_gain,
    'credits', cr_gain,
    'levels_gained', gained,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

create or replace function public.arena_start_upgrade(p_token text, p_slot text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
  f jsonb;
  lvl integer;
  cost numeric;
  credits numeric;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if p_slot is null or p_slot not in ('weapon', 'armor') then
    return jsonb_build_object('error', 'Pick weapon or armor to upgrade.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  if f is distinct from r.fighter then
    update arena_private.players set fighter = f, updated_at = now()
    where player_code = v_code;
  end if;
  if f -> 'upgrade' is not null and jsonb_typeof(f -> 'upgrade') = 'object' then
    return jsonb_build_object(
      'error', 'An upgrade is already running. Wait for it to finish first.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  lvl := (f ->> (p_slot || '_level'))::integer;
  cost := round(25 * power(1.5::numeric, lvl - 1));
  credits := arena_private.credits_of(f);
  if credits < cost then
    return jsonb_build_object(
      'error', format('That upgrade costs %s credits and you have %s credits.', cost, credits),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  f := f || jsonb_build_object(
    'credits', credits - cost,
    'upgrade', jsonb_build_object(
      'slot', p_slot,
      'name', f ->> (p_slot || '_name'),
      'level', lvl + 1,
      'finish', arena_private.now_epoch() + least(60 * lvl, 4 * 3600)));
  f := f - 'points';
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'upgrade_' || p_slot,
    jsonb_build_object('level', lvl + 1, 'cost', cost), 'server');
  return jsonb_build_object(
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

-- Spend one banked stat point. The game sends only the
-- in-memory session token plus one stat name. The server
-- checks the session, the stat name, and that a point is
-- available. Banked points may all go into one stat: stay
-- on the line and spend again, one point per call. The
-- spoken line always says how many points are left.
create or replace function public.arena_spend_stat(p_token text, p_stat text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
  f jsonb;
  v_stat text := lower(btrim(coalesce(p_stat, '')));
  v_stats jsonb;
  v_value integer;
  v_points integer;
  v_line text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if v_stat not in ('strength', 'defense', 'health', 'speed', 'luck') then
    return jsonb_build_object('error', 'Pick strength, defense, health, speed or luck.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_points := coalesce((f ->> 'stat_points')::integer, 0);
  if v_points <= 0 then
    return jsonb_build_object(
      'error', 'You have no stat points to spend right now.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_stats := coalesce(f -> 'stats',
    '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb);
  v_value := coalesce((v_stats ->> v_stat)::integer, 0) + 1;
  v_stats := jsonb_set(v_stats, array[v_stat], to_jsonb(v_value));
  f := f || jsonb_build_object('stats', v_stats, 'stat_points', v_points - 1);
  if v_stat = 'health' then
    -- A Health point adds 10 max HP and heals 10 right away.
    f := f || jsonb_build_object(
      'max_hp', arena_private.fighter_max_hp(f),
      'hp', least((f ->> 'hp')::integer + 10, arena_private.fighter_max_hp(f)));
  end if;
  v_line := case v_stat
    when 'strength' then format('Strength is now %s. One more point adds 2 damage.', v_value)
    when 'defense' then format('Defense is now %s. One more point soaks 1 more damage.', v_value)
    when 'health' then format('Health is now %s. One more point adds 10 health.', v_value)
    when 'speed' then format('Speed is now %s. One more point makes you a little faster.', v_value)
    when 'luck' then format('Luck is now %s. One more point adds a little critical chance.', v_value)
  end;
  if v_points - 1 > 0 then
    v_line := v_line || format(' You have %s stat %s left.',
      v_points - 1, case when v_points - 1 = 1 then 'point' else 'points' end);
  else
    v_line := v_line || ' That was your last stat point.';
  end if;
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'spend_stat',
    jsonb_build_object('stat', v_stat), 'server');
  return jsonb_build_object(
    'message', v_line,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

-- Reset all 5 stats, refunding every spent point to unspent
-- stat points. The first respec is free; later ones cost
-- 100 credits. Level, weapon, armor, wins, losses and
-- fighter kind are never touched.
create or replace function public.arena_respec(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
  f jsonb;
  v_stats jsonb;
  v_spent integer;
  v_points integer;
  v_used integer;
  v_cost integer;
  v_new_max_hp integer;
  v_line text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_stats := coalesce(f -> 'stats',
    '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb);
  v_spent := coalesce((v_stats ->> 'strength')::integer, 0)
    + coalesce((v_stats ->> 'defense')::integer, 0)
    + coalesce((v_stats ->> 'health')::integer, 0)
    + coalesce((v_stats ->> 'speed')::integer, 0)
    + coalesce((v_stats ->> 'luck')::integer, 0);
  if v_spent <= 0 then
    return jsonb_build_object(
      'error', 'You have no stat points spent to reset.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_used := coalesce((f ->> 'respecs_used')::integer, 0);
  v_cost := case when v_used <= 0 then 0 else 100 end;
  if v_cost > arena_private.credits_of(f) then
    return jsonb_build_object(
      'error', format('A respec costs %s credits and you have %s credits.',
        v_cost, arena_private.credits_of(f)),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_points := coalesce((f ->> 'stat_points')::integer, 0) + v_spent;
  v_new_max_hp := 100 + 10 * ((f ->> 'level')::integer - 1);
  f := f || jsonb_build_object(
    'stats', '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb,
    'stat_points', v_points,
    'respecs_used', v_used + 1,
    'credits', arena_private.credits_of(f) - v_cost,
    'max_hp', v_new_max_hp,
    'hp', least((f ->> 'hp')::integer, v_new_max_hp));
  f := f - 'points';
  if v_cost > 0 then
    v_line := format('Your stats are reset. You have %s stat points to spend. That respec cost %s credits.',
      v_points, v_cost);
  else
    v_line := format('Your stats are reset. You have %s stat points to spend. Your first respec was free.',
      v_points);
  end if;
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'respec',
    jsonb_build_object('cost', v_cost, 'refunded', v_spent), 'server');
  return jsonb_build_object(
    'message', v_line,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

-- Max affordable: buy as many levels of one slot as the
-- credits AND the 4-hour cap allow, in one go. The server
-- works out the queue itself, deducts the full cost up
-- front, and runs the levels one after another. Once started
-- the queue runs to the end: there is no cancelling, so the
-- game must confirm first (see game_logic.max_affordable).
create or replace function public.arena_max_upgrade(p_token text, p_slot text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  t record;
  f jsonb;
  v_level integer;
  v_credits numeric;
  v_levels jsonb := '[]'::jsonb;
  v_cost numeric := 0;
  v_seconds integer := 0;
  v_c numeric;
  v_s integer;
  v_count integer;
  v_first integer;
  v_name text;
  v_line text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if p_slot is null or p_slot not in ('weapon', 'armor') then
    return jsonb_build_object('error', 'Pick weapon or armor to upgrade.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  if f is distinct from r.fighter then
    update arena_private.players set fighter = f, updated_at = now()
    where player_code = v_code;
  end if;
  if f -> 'upgrade' is not null and jsonb_typeof(f -> 'upgrade') = 'object' then
    return jsonb_build_object(
      'error', 'An upgrade is already running. Wait for it to finish first.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_level := (f ->> (p_slot || '_level'))::integer;
  v_credits := arena_private.credits_of(f);
  v_name := f ->> (p_slot || '_name');
  loop
    v_c := round(25 * power(1.5::numeric, v_level - 1));
    v_s := least(60 * v_level, 4 * 3600);
    exit when v_cost + v_c > v_credits;
    exit when v_seconds + v_s > 4 * 3600;
    v_levels := v_levels || to_jsonb(v_level + 1);
    v_cost := v_cost + v_c;
    v_seconds := v_seconds + v_s;
    v_level := v_level + 1;
  end loop;
  v_count := jsonb_array_length(v_levels);
  if v_count <= 0 then
    return jsonb_build_object(
      'error', format('Your next %s level costs %s credits and you have %s credits.',
        v_name, round(25 * power(1.5::numeric, (f ->> (p_slot || '_level'))::integer - 1)), v_credits),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_first := (v_levels ->> 0)::integer;
  f := f || jsonb_build_object(
    'credits', v_credits - v_cost,
    'upgrade', jsonb_build_object(
      'slot', p_slot,
      'name', v_name,
      'level', v_first,
      'finish', arena_private.now_epoch() + least(60 * (v_first - 1), 4 * 3600)),
    'upgrade_queue', v_levels - 0,
    'upgrade_total', v_count);
  f := f - 'points';
  v_line := format('Your %s will go up %s %s for %s credits. All %s %s will be done in %s.',
    v_name, v_count, case when v_count = 1 then 'level' else 'levels' end,
    v_cost, v_count, case when v_count = 1 then 'level' else 'levels' end,
    arena_private.format_time(v_seconds));
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'max_upgrade_' || p_slot,
    jsonb_build_object('levels', v_count, 'cost', v_cost), 'server');
  return jsonb_build_object(
    'message', v_line,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

-- The voice is a setting, not a stat, so players may change it.
create or replace function public.arena_set_voice(p_token text, p_gender text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
  f jsonb;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if p_gender is null or p_gender not in ('male', 'female') then
    return jsonb_build_object('error', 'Pick male or female for the voice.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  f := r.fighter || jsonb_build_object('gender', p_gender);
  update arena_private.players
  set fighter = f, gender = p_gender, updated_at = now()
  where player_code = v_code;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

create or replace function public.arena_lookup_player(p_token text, p_player_code text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  v_find text := upper(regexp_replace(coalesce(p_player_code, ''), '[[:space:]-]', '', 'g'));
  r arena_private.players%rowtype;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if v_find = '' then
    return jsonb_build_object('error', 'Type a player code first.');
  end if;
  select * into r from arena_private.players where player_code = v_find;
  if not found then
    return jsonb_build_object('error', 'No player has that code. Check the code and try again.');
  end if;
  return jsonb_build_object(
    'username', r.username,
    'player_code', r.player_code,
    'gender', r.gender,
    'kind', r.kind,
    'fighter', jsonb_build_object(
      'name', r.fighter -> 'name',
      'kind', r.fighter -> 'kind',
      'level', r.fighter -> 'level',
      'wins', r.fighter -> 'wins',
      'losses', r.fighter -> 'losses',
      'weapon_name', r.fighter -> 'weapon_name',
      'weapon_level', r.fighter -> 'weapon_level',
      'armor_name', r.fighter -> 'armor_name',
      'armor_level', r.fighter -> 'armor_level'));
end;
$$;

-- Players who are online right now: their game has checked
-- in within the last 2 minutes and has not signed out.
create or replace function public.arena_list_online(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  return jsonb_build_object('players', coalesce((
    select jsonb_agg(jsonb_build_object(
      'username', x.username,
      'player_code', x.player_code,
      'kind', x.kind,
      'level', x.level) order by x.username_key)
    from (
      select p.username, p.username_key, p.player_code, p.kind,
             (p.fighter ->> 'level')::integer as level
      from arena_private.players p
      where p.player_code <> v_code
        and exists (
          select 1 from arena_private.sessions s
          where s.player_code = p.player_code
            and s.last_seen > now() - interval '2 minutes')
      order by p.username_key
      limit 50
    ) x), '[]'::jsonb));
end;
$$;

-- Things the game reports, like key presses and settings.
-- They are kept in the history marked as from the game, and
-- they never change the fighter.
create or replace function public.arena_log_action(
  p_token text, p_action text, p_detail jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if p_action is null or p_action !~ '^[a-z_]{1,40}$' then
    return jsonb_build_object('error', 'That action name is not allowed.');
  end if;
  if p_detail is not null and (jsonb_typeof(p_detail) <> 'object'
                               or octet_length(p_detail::text) > 1000) then
    return jsonb_build_object('error', 'That action detail is too big.');
  end if;
  perform arena_private.log_event(v_code, p_action, p_detail, 'game');
  return jsonb_build_object('ok', true);
end;
$$;

-- Everything the server holds about the signed-in player,
-- except the password hash and lockout counters.
create or replace function public.arena_export(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
  r arena_private.players%rowtype;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code;
  return jsonb_build_object(
    'username', r.username,
    'player_code', r.player_code,
    'gender', r.gender,
    'kind', r.kind,
    'fighter', r.fighter,
    'events', r.events,
    'created_at', r.created_at,
    'updated_at', r.updated_at);
end;
$$;

-- Keep me signed in: swap a live session for a remember token.
create or replace function public.arena_remember(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text := arena_private.session_player(p_token);
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  perform arena_private.log_event(v_code, 'remember_on', '{}'::jsonb, 'server');
  return jsonb_build_object('remember_token', arena_private.new_remember(v_code));
end;
$$;

-- Sign in with a remember token, instead of a password. The
-- old remember token is used up, and a new one comes back
-- with the session, so a copied token stops working the next
-- time the real player starts the game.
create or replace function public.arena_resume(p_remember_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_code text;
  r arena_private.players%rowtype;
  t record;
begin
  if p_remember_token is null or p_remember_token !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('error', 'Please sign in again.', 'forget', true);
  end if;
  delete from arena_private.remembered
  where token_hash = arena_private.hash_token(p_remember_token)
    and last_used > now() - interval '30 days'
  returning player_code into v_code;
  if v_code is null then
    return jsonb_build_object('error',
      'You were signed out on this computer. Please sign in again.',
      'forget', true);
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  update arena_private.players
  set fighter = t.fighter, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'sign_in_remembered', '{}'::jsonb, 'server');
  return jsonb_build_object(
    'token', arena_private.new_session(v_code),
    'remember_token', arena_private.new_remember(v_code),
    'account', jsonb_build_object(
      'username', r.username, 'player_code', r.player_code,
      'gender', r.gender, 'kind', r.kind),
    'fighter', arena_private.fighter_out(t.fighter, r.player_code, r.username),
    'messages', t.messages);
end;
$$;

-- Turn "keep me signed in" off: the token stops working.
create or replace function public.arena_forget(p_remember_token text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_remember_token is not null and p_remember_token ~ '^[0-9a-f]{64}$' then
    delete from arena_private.remembered
    where token_hash = arena_private.hash_token(p_remember_token);
  end if;
  return jsonb_build_object('ok', true);
end;
$$;

-- Only the arena_* functions are callable by the game.
revoke all on function public.arena_create_account(text, text, text, text, text) from public;
revoke all on function public.arena_sign_in(text, text, text) from public;
revoke all on function public.arena_sign_out(text) from public;
revoke all on function public.arena_state(text) from public;
revoke all on function public.arena_fight(text, text) from public;
revoke all on function public.arena_start_upgrade(text, text) from public;
revoke all on function public.arena_spend_stat(text, text) from public;
revoke all on function public.arena_respec(text) from public;
revoke all on function public.arena_max_upgrade(text, text) from public;
revoke all on function public.arena_set_voice(text, text) from public;
revoke all on function public.arena_lookup_player(text, text) from public;
revoke all on function public.arena_list_online(text) from public;
revoke all on function public.arena_log_action(text, text, jsonb) from public;
revoke all on function public.arena_export(text) from public;
revoke all on function public.arena_remember(text) from public;
revoke all on function public.arena_resume(text) from public;
revoke all on function public.arena_forget(text) from public;

grant execute on function public.arena_create_account(text, text, text, text, text) to anon, authenticated;
grant execute on function public.arena_sign_in(text, text, text) to anon, authenticated;
grant execute on function public.arena_sign_out(text) to anon, authenticated;
grant execute on function public.arena_state(text) to anon, authenticated;
grant execute on function public.arena_fight(text, text) to anon, authenticated;
grant execute on function public.arena_start_upgrade(text, text) to anon, authenticated;
grant execute on function public.arena_spend_stat(text, text) to anon, authenticated;
grant execute on function public.arena_respec(text) to anon, authenticated;
grant execute on function public.arena_max_upgrade(text, text) to anon, authenticated;
grant execute on function public.arena_set_voice(text, text) to anon, authenticated;
grant execute on function public.arena_lookup_player(text, text) to anon, authenticated;
grant execute on function public.arena_list_online(text) to anon, authenticated;
grant execute on function public.arena_log_action(text, text, jsonb) to anon, authenticated;
grant execute on function public.arena_export(text) to anon, authenticated;
grant execute on function public.arena_remember(text) to anon, authenticated;
grant execute on function public.arena_resume(text) to anon, authenticated;
grant execute on function public.arena_forget(text) to anon, authenticated;

notify pgrst, 'reload schema';
