-- Phase 30 hotfix (2026-11-19): the Healing max-upgrade crash.
--
-- What happened: on 2026-11-19 at 08:04 MST, Makenna (Katprincess,
-- player code 2169) stopped her quests and bought max-affordable
-- Healing (Second Wind) 0 -> 5. The game spoke "Your Second Wind
-- will go up levels..." and then crashed, over and over, once a
-- second, and on every launch: game_logic.upgrade_status line 1210,
-- TypeError: %d format needs a real number, not NoneType, because
-- the running upgrade had level null.
--
-- Root cause (proved by replaying the old function in Postgres):
-- the live server was still running the Phase 25 arena_max_upgrade
-- (20261119044306), which reads healing_level as
-- (f ->> 'healing_level')::integer with NO coalesce to 0. Her
-- fighter predates Healing, so the field is missing. With a null
-- level the cost is null, the loop builds a queue of nulls, and
-- the server stores upgrade {level: null, finish: now + 4 hours}
-- and returns a success line with empty counts ("...will go up
-- levels for credits..."). The Phase 25b hotfix (20261119052000)
-- and Phase 28 (20261119070000) both carry the coalesce in the
-- repo, but the live server had not applied them by 08:04 — the
-- server still spoke second-person "Your..." lines and Gus still
-- spoke with the retired Davis voice that morning. So this file
-- re-issues the fixed functions AND repairs the stored fighters,
-- and does not depend on any earlier migration having applied.
--
-- Credits (proved, not guessed): the broken call did NOT deduct
-- the 915 credits for Healing 0 -> 5. It set the stored credits
-- field to JSON null instead, which credits_of() reads as 0 — so
-- Makenna currently shows 0 credits, not her balance minus 915.
-- No Healing levels were granted either: the purchase never
-- completed. Her true pre-crash balance is in no record we can
-- read (the log has no balance line, the server event log keeps
-- only the newest 200 events, and Maren has no Supabase access),
-- so this migration does NOT invent a balance: it stores a real 0
-- where credits is null, so the balance is never null again, and
-- logs a phase30_repair event per fighter repaired. Josh sets the
-- real balance in the Supabase dashboard once Makenna remembers
-- the "leaving X" number from the confirm question she heard
-- ("Your Second Wind can go up 5 levels for 915 credits,
-- leaving X") — her balance was X + 915. See PROPOSALS.md Phase 30.
--
-- What this file does, in a new file only (no old migration edited):
--   (a) fighter_out always returns healing_level, defaulting to 0
--       (Phase 25b body, re-issued so the fix does not depend on
--       that migration having applied live);
--   (b) apply_timers defaults a missing / JSON-null healing_level
--       to 0, and clears any running upgrade whose level or
--       finish is null (plus a null queued level) instead of
--       ever building on it;
--   (c) arena_start_upgrade and arena_max_upgrade keep the
--       Phase 28 first-person wording and the coalesce on the
--       slot-level read, and the max-upgrade "cannot afford it"
--       error path coalesces the weapon/armor level too;
--   (d) a one-time repair pass over every stored fighter:
--       healing_level missing/null -> 0, credits missing/null
--       -> 0 (see the credits note above), a broken upgrade
--       (null level or finish, or a null in the queue) -> cleared.
-- Nothing else changes: same costs, times, cap and messages.
-- Old game versions keep working — they only read the same fields.

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
      format('My balance is now in credits. I have %s credits.',
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
        format('I have %s stat points to spend. Would you like to choose my stats now?',
          v_grant));
    end if;
  end if;

  -- Phase 30 (Nov 19, 2026): fighters made before Healing
  -- have no healing_level key, or a JSON null left by the
  -- broken Nov 19 call. Missing means level 0, never null.
  if not (f ? 'healing_level') or (f -> 'healing_level') = 'null'::jsonb then
    f := f || jsonb_build_object('healing_level', 0);
  end if;

  -- Phase 30: a running upgrade with a null level or a null
  -- finish can never finish and used to crash the game on
  -- every launch and every second (the Nov 19 Healing
  -- crash stored exactly that). Clear it here, so any
  -- server call repairs the fighter, and say so once.
  if up is not null and jsonb_typeof(up) = 'object'
     and ((up -> 'level') is null or (up -> 'level') = 'null'::jsonb
          or (up -> 'finish') is null or (up -> 'finish') = 'null'::jsonb) then
    f := f || jsonb_build_object(
      'upgrade', null, 'upgrade_queue', null, 'upgrade_total', 0);
    messages := messages || to_jsonb(
      'That broken upgrade was cleared. No upgrade is running now.'::text);
    up := null;
  end if;

  if up is not null and jsonb_typeof(up) = 'object'
     and (up ->> 'finish')::double precision <= p_now then
    f := jsonb_set(f, array[(up ->> 'slot') || '_level'], up -> 'level');
    v_queue := f -> 'upgrade_queue';
    if v_queue is not null and jsonb_typeof(v_queue) = 'array'
       and jsonb_array_length(v_queue) > 0 then
      -- A max-affordable queue: start the next level at once.
      -- Phase 30: a null queued level (the Nov 19 crash left
      -- nulls in a queue) can never run, so clear the upgrade
      -- instead of building another broken one.
      v_next := (v_queue ->> 0)::integer;
      if v_next is null then
        f := f || jsonb_build_object(
          'upgrade', null, 'upgrade_queue', null, 'upgrade_total', 0);
        messages := messages || to_jsonb(
          'That broken upgrade was cleared. No upgrade is running now.'::text);
      else
      f := jsonb_set(f, '{upgrade}', jsonb_build_object(
        'slot', up ->> 'slot',
        'name', up ->> 'name',
        'level', v_next,
        'finish', p_now + case when (up ->> 'slot') = 'healing'
          then least(720 * v_next, 4 * 3600)
          else least(60 * (v_next - 1), 4 * 3600) end));
      f := jsonb_set(f, '{upgrade_queue}', v_queue - 0);
      messages := messages || to_jsonb(
        format('My %s is now level %s.', up ->> 'name', up ->> 'level'));
      end if;
    else
      f := jsonb_set(f, '{upgrade}', 'null'::jsonb);
      f := jsonb_set(f, '{upgrade_queue}', 'null'::jsonb);
      v_total := coalesce((f ->> 'upgrade_total')::integer, 0);
      f := jsonb_set(f, '{upgrade_total}', '0'::jsonb);
      messages := messages || to_jsonb(
        format('My %s is now level %s.', up ->> 'name', up ->> 'level'));
      if v_total > 1 then
        messages := messages || to_jsonb(
          format('All %s levels are done.', v_total));
      end if;
      if (up ->> 'slot') = 'healing' and (up ->> 'level')::integer >= 5
         and repair > p_now then
        -- Reaching Healing level 5 ends repairs for good: a
        -- fighter still under repair when the skill maxes out
        -- is back to full health at once, with no wait left.
        f := f || jsonb_build_object(
          'hp', arena_private.fighter_max_hp(f), 'repair_until', 0);
        messages := messages || to_jsonb(
          'No more repairs — I''m back to full health.'::text);
      end if;
    end if;
  end if;
  if repair > 0 and repair <= p_now then
    f := f || jsonb_build_object('hp', f -> 'max_hp', 'repair_until', 0);
    messages := messages || to_jsonb(
      'My repairs are finished. I''m back to full health.'::text);
  end if;
  fighter := f;
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
  -- Phase 30: coalesce is the fix (see arena_max_upgrade
  -- above): without it a missing healing_level makes the
  -- cost, the credits and the upgrade level all null.
  lvl := coalesce((f ->> (p_slot || '_level'))::integer, 0);
  if p_slot = 'healing' then
    -- Healing (Phase 25): its own exponential cost curve
    -- (50, 85, 140, 240, 400), and it stops at level 5 —
    -- the only capped upgrade in the game.
    if lvl >= 5 then
      return jsonb_build_object(
        'error', 'My Second Wind is already at its best, level 5.',
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
      'error', format('That upgrade costs %s credits and I have %s credits.', cost, credits),
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
  -- Phase 30: coalesce is the fix. A fighter made before
  -- Healing has no healing_level key; without this the
  -- level is null, the cost is null, the credits go null,
  -- and the upgrade is stored with a null level — the
  -- Nov 19 crash. Never remove this coalesce.
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
      'error', 'My Second Wind is already at its best, level 5.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  if v_count <= 0 then
    return jsonb_build_object(
      'error', format('My next %s level costs %s credits and I have %s credits.',
        v_name, case when p_slot = 'healing'
          then (array[50, 85, 140, 240, 400])[coalesce((f ->> 'healing_level')::integer, 0) + 1]
          else round(25 * power(1.5::numeric, coalesce((f ->> (p_slot || '_level'))::integer, 1) - 1)) end, v_credits),
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
  v_line := format('My %s will go up %s %s for %s credits. All %s %s will be done in %s.',
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

-- One-time repair of the fighters the broken Nov 19 call left
-- behind. Runs once, when this migration applies. Every branch
-- is written so a healthy fighter is untouched.
do $$
declare
  r record;
  f jsonb;
  changed boolean;
begin
  for r in select player_code, fighter from arena_private.players for update loop
    f := r.fighter;
    changed := false;

    -- Healing level: old fighters have no key, or a JSON null
    -- left by the broken call. Missing means level 0.
    if not (f ? 'healing_level') or (f -> 'healing_level') = 'null'::jsonb then
      f := f || jsonb_build_object('healing_level', 0);
      changed := true;
    end if;

    -- Credits: the broken call stored JSON null instead of
    -- deducting 915. Store a real 0 so the balance is never
    -- null again. The true balance is NOT invented here (see
    -- the header note): Josh sets it in the dashboard once
    -- Makenna remembers the "leaving X" number.
    if not (f ? 'credits') or (f -> 'credits') = 'null'::jsonb then
      f := f || jsonb_build_object('credits', 0);
      changed := true;
    end if;

    -- Broken upgrade: a null level or finish can never finish
    -- and blocks every new upgrade (one set at a time). Clear
    -- it, its queue and its total.
    if jsonb_typeof(f -> 'upgrade') = 'object'
       and ((f -> 'upgrade' -> 'level') is null
            or (f -> 'upgrade' -> 'level') = 'null'::jsonb
            or (f -> 'upgrade' -> 'finish') is null
            or (f -> 'upgrade' -> 'finish') = 'null'::jsonb) then
      f := f || jsonb_build_object(
        'upgrade', null, 'upgrade_queue', null, 'upgrade_total', 0);
      changed := true;
    end if;

    -- A queue holding a null level can never run either.
    if jsonb_typeof(f -> 'upgrade_queue') = 'array'
       and exists (
         select 1 from jsonb_array_elements(f -> 'upgrade_queue') e
         where e = 'null'::jsonb) then
      f := f || jsonb_build_object(
        'upgrade', null, 'upgrade_queue', null, 'upgrade_total', 0);
      changed := true;
    end if;

    if changed then
      update arena_private.players
      set fighter = f, updated_at = now()
      where player_code = r.player_code;
      perform arena_private.log_event(
        r.player_code, 'phase30_repair',
        jsonb_build_object(
          'fixed', 'healing_level, credits, broken upgrade (Phase 30)'),
        'server');
    end if;
  end loop;
end $$;

revoke all on function public.arena_start_upgrade(text, text) from public;
grant execute on function public.arena_start_upgrade(text, text) to anon, authenticated;
revoke all on function public.arena_max_upgrade(text, text) from public;
grant execute on function public.arena_max_upgrade(text, text) to anon, authenticated;
