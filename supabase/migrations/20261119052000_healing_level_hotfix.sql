-- Phase 25b hotfix (2026-11-19): fighters made before Phase 18
-- have no healing_level key in their stored record, and the game
-- crashed on launch building the Shop (KeyError: 'healing_level').
-- Belt and braces on the server, in this new migration only
-- (20261119044306 and every older migration are untouched):
--   (a) fighter_out now always returns healing_level, defaulting
--       to 0 for old fighters, so the client never sees a record
--       without the key;
--   (b) arena_start_upgrade and arena_max_upgrade read the slot
--       level with coalesce(..., 0), and the max-upgrade "you
--       cannot afford it" Healing cost lookup coalesces too, so
--       a missing healing_level can never make a cost NULL.
-- Nothing else changes: the same bodies as 20261119044306, the
-- same costs, times, cap and messages. Old game versions keep
-- working — they never ask for Healing.

create or replace function arena_private.fighter_out(
  p_fighter jsonb, p_code text, p_username text)
returns jsonb
language sql immutable
set search_path = ''
as $$
  select p_fighter || jsonb_build_object(
    'healing_level', coalesce((p_fighter ->> 'healing_level')::integer, 0),
    'player_code', p_code, 'username', p_username)
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
  if p_slot is null or p_slot not in ('weapon', 'armor', 'healing') then
    return jsonb_build_object('error', 'Pick weapon, armor or healing to upgrade.');
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
  lvl := coalesce((f ->> (p_slot || '_level'))::integer, 0);
  if p_slot = 'healing' then
    -- Healing (Phase 25): its own exponential cost curve
    -- (50, 85, 140, 240, 400), and it stops at level 5 —
    -- the only capped upgrade in the game.
    if lvl >= 5 then
      return jsonb_build_object(
        'error', 'Your Second Wind is already at its best, level 5.',
        'messages', t.messages,
        'fighter', arena_private.fighter_out(f, r.player_code, r.username));
    end if;
    cost := (array[50, 85, 140, 240, 400])[lvl + 1];
  else
    cost := round(25 * power(1.5::numeric, lvl - 1));
  end if;
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
      'name', case when p_slot = 'healing' then 'Second Wind'
        else f ->> (p_slot || '_name') end,
      'level', lvl + 1,
      'finish', arena_private.now_epoch() + case when p_slot = 'healing'
        then least(720 * (lvl + 1), 4 * 3600)
        else least(60 * lvl, 4 * 3600) end));
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
  if p_slot is null or p_slot not in ('weapon', 'armor', 'healing') then
    return jsonb_build_object('error', 'Pick weapon, armor or healing to upgrade.');
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
  v_level := coalesce((f ->> (p_slot || '_level'))::integer, 0);
  v_credits := arena_private.credits_of(f);
  v_name := case when p_slot = 'healing' then 'Second Wind'
    else f ->> (p_slot || '_name') end;
  loop
    exit when p_slot = 'healing' and v_level >= 5;
    if p_slot = 'healing' then
      v_c := (array[50, 85, 140, 240, 400])[v_level + 1];
      v_s := least(720 * (v_level + 1), 4 * 3600);
    else
      v_c := round(25 * power(1.5::numeric, v_level - 1));
      v_s := least(60 * v_level, 4 * 3600);
    end if;
    exit when v_cost + v_c > v_credits;
    exit when v_seconds + v_s > 4 * 3600;
    v_levels := v_levels || to_jsonb(v_level + 1);
    v_cost := v_cost + v_c;
    v_seconds := v_seconds + v_s;
    v_level := v_level + 1;
  end loop;
  v_count := jsonb_array_length(v_levels);
  if v_count <= 0 and p_slot = 'healing'
     and coalesce((f ->> 'healing_level')::integer, 0) >= 5 then
    return jsonb_build_object(
      'error', 'Your Second Wind is already at its best, level 5.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  if v_count <= 0 then
    return jsonb_build_object(
      'error', format('Your next %s level costs %s credits and you have %s credits.',
        v_name, case when p_slot = 'healing'
          then (array[50, 85, 140, 240, 400])[coalesce((f ->> 'healing_level')::integer, 0) + 1]
          else round(25 * power(1.5::numeric, (f ->> (p_slot || '_level'))::integer - 1)) end, v_credits),
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
      'finish', arena_private.now_epoch() + case when p_slot = 'healing'
      then least(720 * v_first, 4 * 3600)
      else least(60 * (v_first - 1), 4 * 3600) end),
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
