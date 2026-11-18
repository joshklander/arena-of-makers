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
--    rolls, experience, levels, points, upgrade costs and
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
    'points', 0,
    'wins', 0,
    'losses', 0,
    'weapon_name', case when p_kind = 'robot' then 'Laser Blaster' else 'Trusty Spatula' end,
    'weapon_level', 1,
    'armor_name', case when p_kind = 'robot' then 'Scrap Plating' else 'Chef Apron' end,
    'armor_level', 1,
    'repair_until', 0,
    'upgrade', null
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
begin
  messages := '[]'::jsonb;
  if up is not null and jsonb_typeof(up) = 'object'
     and (up ->> 'finish')::double precision <= p_now then
    f := jsonb_set(f, array[(up ->> 'slot') || '_level'], up -> 'level');
    f := jsonb_set(f, '{upgrade}', 'null'::jsonb);
    messages := messages || to_jsonb(
      format('Your %s is now level %s.', up ->> 'name', up ->> 'level'));
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
-- server's own dice. p_opponent_code is only recorded in the
-- history, when the fight was started from "Fight a player".
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
  c_hp integer;
  c_dmg integer;
  dmg integer;
  def integer;
  f_hp integer;
  round_no integer := 0;
  hit integer;
  hurt integer;
  lines jsonb;
  xp_gain integer;
  pts_gain numeric;
  cur_xp integer;
  new_level integer;
  new_max_hp integer;
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
      'xp', 0, 'points', 0, 'levels_gained', 0,
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;

  lvl := (f ->> 'level')::integer;
  c_hp := 30 + 15 * (lvl - 1);
  c_dmg := 4 + 2 * (lvl - 1);
  dmg := (case when f ->> 'kind' = 'robot' then 12 else 10 end)
         + 5 * ((f ->> 'weapon_level')::integer - 1) + 2 * (lvl - 1);
  def := 2 + 2 * ((f ->> 'armor_level')::integer - 1) + (lvl - 1);
  f_hp := (f ->> 'hp')::integer;
  lines := jsonb_build_array(format('A Scrap Rat appears! Level %s.', lvl));

  while f_hp > 0 and c_hp > 0 and round_no < 20 loop
    round_no := round_no + 1;
    hit := dmg + floor(random() * 4)::integer;
    c_hp := c_hp - hit;
    lines := lines || to_jsonb(format('Round %s: %s hits the Scrap Rat for %s.',
      round_no, v_name, hit));
    exit when c_hp <= 0;
    hurt := greatest(1, c_dmg + floor(random() * 3)::integer - (def / 2));
    f_hp := f_hp - hurt;
    lines := lines || to_jsonb(format('Round %s: The Scrap Rat hits %s for %s.',
      round_no, v_name, hurt));
  end loop;

  if c_hp <= 0 then
    v_won := true;
    xp_gain := 20 + 5 * lvl;
    pts_gain := 10 + 5 * lvl;
    cur_xp := (f ->> 'xp')::integer + xp_gain;
    new_level := lvl;
    new_max_hp := (f ->> 'max_hp')::integer;
    while cur_xp >= 100 * new_level loop
      cur_xp := cur_xp - 100 * new_level;
      new_level := new_level + 1;
      new_max_hp := new_max_hp + 10;
      gained := gained + 1;
    end loop;
    f := f || jsonb_build_object(
      'xp', cur_xp,
      'level', new_level,
      'max_hp', new_max_hp,
      'hp', greatest(1, f_hp),
      'points', (f ->> 'points')::numeric + pts_gain,
      'wins', (f ->> 'wins')::integer + 1);
    lines := lines || to_jsonb(format('You won! You earned %s experience and %s points.',
      xp_gain, pts_gain));
    if gained > 0 then
      lines := lines || to_jsonb(format('You are now level %s!', new_level));
    end if;
  else
    v_won := false;
    xp_gain := 0;
    lost := least((f ->> 'points')::numeric, 5);
    pts_gain := -lost;
    wait := least(300 * lvl, 4 * 3600);
    f := f || jsonb_build_object(
      'points', (f ->> 'points')::numeric - lost,
      'losses', (f ->> 'losses')::integer + 1,
      'hp', 1,
      'repair_until', v_now + wait);
    lines := lines || to_jsonb(format('You lost. Your fighter needs repairs, %s.',
      arena_private.format_time(wait)));
    if lost > 0 then
      lines := lines || to_jsonb(format('You lost %s points.', lost));
    end if;
    lines := lines || to_jsonb('While repairs run, you can still visit the hangout.'::text);
  end if;

  update arena_private.players
  set fighter = f, last_fight_at = now(), updated_at = now()
  where player_code = v_code;

  v_result := jsonb_build_object('won', v_won, 'xp', xp_gain, 'points', pts_gain);
  if v_opp ~ '^[0-9]{4}$' then
    v_result := v_result || jsonb_build_object('opponent_code', v_opp);
  end if;
  perform arena_private.log_event(v_code, 'fight', v_result, 'server');

  return jsonb_build_object(
    'won', v_won,
    'lines', lines,
    'xp', xp_gain,
    'points', pts_gain,
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
  points numeric;
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
  points := (f ->> 'points')::numeric;
  if points < cost then
    return jsonb_build_object(
      'error', format('That upgrade costs %s points and you have %s points.', cost, points),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  f := f || jsonb_build_object(
    'points', points - cost,
    'upgrade', jsonb_build_object(
      'slot', p_slot,
      'name', f ->> (p_slot || '_name'),
      'level', lvl + 1,
      'finish', arena_private.now_epoch() + least(60 * lvl, 4 * 3600)));
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'upgrade_' || p_slot,
    jsonb_build_object('level', lvl + 1, 'cost', cost), 'server');
  return jsonb_build_object(
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
grant execute on function public.arena_set_voice(text, text) to anon, authenticated;
grant execute on function public.arena_lookup_player(text, text) to anon, authenticated;
grant execute on function public.arena_list_online(text) to anon, authenticated;
grant execute on function public.arena_log_action(text, text, jsonb) to anon, authenticated;
grant execute on function public.arena_export(text) to anon, authenticated;
grant execute on function public.arena_remember(text) to anon, authenticated;
grant execute on function public.arena_resume(text) to anon, authenticated;
grant execute on function public.arena_forget(text) to anon, authenticated;

notify pgrst, 'reload schema';
