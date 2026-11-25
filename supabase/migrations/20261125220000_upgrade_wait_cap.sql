-- Phase 37: the upgrade wait cap (2026-11-25, Makenna).
--
-- NEW RULE (Makenna, Nov 25, 2026): how many levels you can buy
-- in one max-affordable upgrade is decided by CREDITS ONLY — no
-- shrinking by level, no time-based cut-off on the count. The
-- WAIT is capped at 4 hours total, no matter how many levels:
-- even a very long upgrade finishes within 4 hours at most. The
-- timer caps the wait, never the number of levels. The 4-hour cap
-- itself stays for upgrades AND quests, and everything else is
-- additive on top of it.
--
-- What changes, in plain words: before this phase, a max-affordable
-- queue stopped adding levels as soon as the next level would push
-- the total wait past 4 hours — so at high levels you got fewer
-- levels per buy, because each level's wait (60 seconds x the level
-- being left) grows. Now the queue buys every level the credits
-- cover, and the waits shrink so the whole queue fits in 4 hours.
-- Each level still finishes one after another, so a long queue's
-- levels come FASTER than the usual one-level wait: with a short
-- queue nothing changes at all (the raw wait already fits in 4
-- hours), and with a long queue each level takes only its share
-- of the 4 hours. The credits cost curve is the real bound on the
-- count — costs grow 25 x 1.5^(level-1), so even a fortune buys
-- only tens of levels at a time.
--
-- How it works: the queue stores one new number on the running
-- upgrade, time_scale — 1 when the raw wait fits in 4 hours, and
-- 4 hours / raw wait when it does not. Every level's wait is its
-- raw wait times that scale, so the whole queue adds up to at most
-- 4 hours. Old queues carry no scale at all: missing means 1, so
-- they run exactly as before (compatibility rule).
--
-- Two more pieces make the 4-hour promise real. First, the queue
-- used to advance only one level per server call or per tick, so
-- a long queue of fast levels would still take one second per
-- level to drain. Now apply_timers (and the game's own
-- finish_upgrade_if_ready) applies every level whose finish has
-- passed in one pass, and says one line for the last level that
-- finished — never one message per level. Second, each next level
-- now starts where the last one was DUE, not at "now": a level's
-- finish is the last level's finish plus that level's (shrunk)
-- wait. The queue keeps its own schedule, so coming back after a
-- long time away finishes everything that was due, instead of
-- restarting the wait from the moment you came back. A single
-- upgrade (not a queue) is unchanged: its wait was already capped
-- at 4 hours per level.
--
-- Healing is untouched in practice: five Healing levels take 12 +
-- 24 + 36 + 48 + 60 minutes = 3 hours raw, so its scale is always
-- 1 and its waits never shrink.
--
-- New migration file only: no old migration is edited. Only
-- apply_timers and arena_max_upgrade are redefined, each
-- byte-identical to the Phase 30 version except the changes
-- noted inline. arena_start_upgrade is unchanged.

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
  -- Phase 37: the queue's time scale (1 when the raw wait fits
  -- in 4 hours, smaller when the queue was shrunk to fit), how
  -- many levels this pass applied, and the last one applied.
  v_scale numeric := 1;
  v_applied integer := 0;
  v_last_level integer;
  v_last_name text;
  v_slot text;
  v_prev_finish double precision;
  v_all_done boolean := false;
  v_healed boolean := false;
  v_broken boolean := false;
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

  -- Phase 37: apply every level whose finish has passed, in one
  -- pass, instead of one level per call. A long queue of fast
  -- levels (a max-affordable queue shrunk to fit in 4 hours)
  -- drains at once; the line names the last level that finished,
  -- never one message per level. Each next level starts where the
  -- last one was DUE (its finish plus that level's shrunk wait),
  -- not at "now", so the queue keeps its own schedule.
  if up is not null and jsonb_typeof(up) = 'object'
     and (up ->> 'finish')::double precision <= p_now then
    v_slot := up ->> 'slot';
    v_last_name := up ->> 'name';
    v_scale := coalesce((up ->> 'time_scale')::numeric, 1);
    if v_scale <= 0 then
      v_scale := 1;
    end if;
    v_total := coalesce((f ->> 'upgrade_total')::integer, 0);
    loop
      exit when up is null or jsonb_typeof(up) <> 'object'
        or (up ->> 'finish')::double precision > p_now;
      v_prev_finish := (up ->> 'finish')::double precision;
      v_last_level := (up ->> 'level')::integer;
      v_applied := v_applied + 1;
      f := jsonb_set(f, array[v_slot || '_level'], up -> 'level');
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
          v_broken := true;
          up := null;
        else
          f := jsonb_set(f, '{upgrade}', jsonb_build_object(
            'slot', v_slot,
            'name', v_last_name,
            'level', v_next,
            'time_scale', v_scale,
            'finish', v_prev_finish + case when v_slot = 'healing'
              then least(720 * v_next, 4 * 3600) * v_scale
              else least(60 * (v_next - 1), 4 * 3600) * v_scale end));
          f := jsonb_set(f, '{upgrade_queue}', v_queue - 0);
          up := f -> 'upgrade';
        end if;
      else
        f := jsonb_set(f, '{upgrade}', 'null'::jsonb);
        f := jsonb_set(f, '{upgrade_queue}', 'null'::jsonb);
        f := jsonb_set(f, '{upgrade_total}', '0'::jsonb);
        v_all_done := true;
        if v_slot = 'healing' and v_last_level >= 5
           and repair > p_now then
          -- Reaching Healing level 5 ends repairs for good: a
          -- fighter still under repair when the skill maxes out
          -- is back to full health at once, with no wait left.
          -- (The line is said after the loop, in the old order.)
          f := f || jsonb_build_object(
            'hp', arena_private.fighter_max_hp(f), 'repair_until', 0);
          v_healed := true;
        end if;
        up := null;
      end if;
    end loop;
    if v_applied > 0 and not v_broken then
      messages := messages || to_jsonb(
        format('My %s is now level %s.', v_last_name, v_last_level));
      if v_all_done and v_total > 1 then
        messages := messages || to_jsonb(
          format('All %s levels are done.', v_total));
      end if;
    end if;
    if v_healed then
      messages := messages || to_jsonb(
        'No more repairs — I''m back to full health.'::text);
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
  -- Phase 37: the queue's time scale (1 when the raw wait fits
  -- in 4 hours, 4 hours / raw wait when it does not) and the
  -- wait after shrinking, capped at 4 hours.
  v_scale numeric := 1;
  v_seconds_capped integer := 0;
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
    -- Phase 37: NO time exit any more. The count is decided by
    -- credits only (Makenna, Nov 25, 2026): the 4-hour cap caps
    -- the wait, never the number of levels. v_seconds below is
    -- the RAW total; the shrink happens after this loop.
    v_levels := v_levels || to_jsonb(v_level + 1);
    v_cost := v_cost + v_c;
    v_seconds := v_seconds + v_s;
    v_level := v_level + 1;
  end loop;
  v_count := jsonb_array_length(v_levels);
  -- Phase 37: the wait after shrinking — the raw total when it
  -- fits in 4 hours, 4 hours when it does not. The shrink factor
  -- rides on the running upgrade as time_scale, and apply_timers
  -- uses it for every level after the first.
  v_scale := case when v_seconds > 4 * 3600
    then (4 * 3600)::numeric / v_seconds else 1 end;
  v_seconds_capped := least(v_seconds, 4 * 3600);
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
      'time_scale', v_scale,
      'finish', arena_private.now_epoch() + case when p_slot = 'healing'
      then least(720 * v_first, 4 * 3600) * v_scale
      else least(60 * (v_first - 1), 4 * 3600) * v_scale end),
    'upgrade_queue', v_levels - 0,
    'upgrade_total', v_count);
  f := f - 'points';
  v_line := format('My %s will go up %s %s for %s credits. All %s %s will be done in %s.',
    v_name, v_count, case when v_count = 1 then 'level' else 'levels' end,
    v_cost, v_count, case when v_count = 1 then 'level' else 'levels' end,
    arena_private.format_time(v_seconds_capped));
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

revoke all on function public.arena_max_upgrade(text, text) from public;
grant execute on function public.arena_max_upgrade(text, text) to anon, authenticated;
