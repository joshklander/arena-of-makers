-- Fix the one spoken line that still used the old currency
-- name. The credits rename in apply_timers told a player
-- whose old fighter still carried an old-style balance that
-- the old name was now called credits. That was the only
-- spoken line on the server that used the old name for the
-- currency (every other "points" in the game is "stat points",
-- which stays). It now says the balance is in credits, with
-- the old name not in it at all.
--
-- This replaces arena_private.apply_timers only, with the
-- same inputs, outputs and rules as the baseline
-- (20261118045430): the rename still copies the old balance
-- 1-for-1 to "credits" and drops the old key, once. Nothing
-- else changes. Older games keep working: the function name,
-- inputs and what it returns are all unchanged.
--
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
      format('Your balance is now in credits. You have %s credits.',
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

