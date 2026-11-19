-- Phase 28: first-person narration on the server.
-- Re-issues the server functions that speak fight, repair,
-- upgrade, stat and quest lines, with the same wording the
-- client now uses (Phase 28): the player's own lines say
-- "I / me / my", and quest givers address the player by name.
-- No logic, numbers, costs, times or rewards change — only
-- the spoken words. The NPC ability lines are table data,
-- updated below. Follows supabase/README.md: a new file,
-- no old migration edited, old game versions keep working
-- (they only read the same fields).

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
        'finish', p_now + case when (up ->> 'slot') = 'healing'
          then least(720 * v_next, 4 * 3600)
          else least(60 * (v_next - 1), 4 * 3600) end));
      f := jsonb_set(f, '{upgrade_queue}', v_queue - 0);
      messages := messages || to_jsonb(
        format('My %s is now level %s.', up ->> 'name', up ->> 'level'));
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
  v_heal5 boolean;
  v_told boolean;
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
        format('I''m still repairing. %s left.',
          arena_private.format_time((f ->> 'repair_until')::double precision - v_now)),
        'I can visit the hangout or browse the shop while I wait.'),
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
            'Round %s: The Scrap Rat dodges! My hit misses.', round_no));
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
              'Round %s: Critical hit! I hit the Scrap Rat for %s.',
              round_no, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: I hit the Scrap Rat for %s.',
              round_no, hit));
          end if;
        end if;
      else
        if random() * 100 < f_dodge then
          lines := lines || to_jsonb(format(
            'Round %s: I dodge! The Scrap Rat''s hit misses.',
            round_no));
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
              'Round %s: Critical hit! The Scrap Rat hits me for %s.',
              round_no, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: The Scrap Rat hits me for %s.',
              round_no, hit));
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
    v_heal5 := coalesce((f ->> 'healing_level')::integer, 0) >= 5;
    f := f || jsonb_build_object(
      'xp', cur_xp,
      'level', new_level,
      'max_hp', new_max_hp,
      'hp', case when v_heal5 then new_max_hp else greatest(1, f_hp) end,
      'credits', arena_private.credits_of(f) + cr_gain,
      'stat_points', new_stat_points,
      'wins', (f ->> 'wins')::integer + 1);
    f := f - 'points';
    lines := lines || to_jsonb(format('I won! I earned %s experience and %s credits.',
      xp_gain, cr_gain));
    if v_heal5 and f_hp < new_max_hp then
      lines := lines || to_jsonb('My Second Wind restored me to full health.'::text);
    end if;
    if gained > 0 then
      lines := lines || to_jsonb(format(
        'I''m now level %s! My health grew to %s. I have %s stat points to spend.',
        new_level, new_max_hp, new_stat_points));
    end if;
  else
    v_won := false;
    xp_gain := 0;
    lost := least(arena_private.credits_of(f), 5);
    cr_gain := -lost;
    v_heal5 := coalesce((f ->> 'healing_level')::integer, 0) >= 5;
    if v_heal5 then
      -- Level 5 Healing (Phase 25): no repair is ever
      -- needed again. Back to full health at once, and the
      -- game says so — in full the first time it saves a
      -- repair, in short after that.
      v_told := coalesce((f ->> 'healing_full_told')::boolean, false);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', f_max_hp,
        'repair_until', 0,
        'healing_full_told', true);
      f := f - 'points';
      if v_told then
        lines := lines || to_jsonb(
          'I lost, but my Second Wind brought me back to full health. No repairs needed.'::text);
      else
        lines := lines || to_jsonb(
          'I lost, but my Second Wind brought me back to full health. No repairs needed — at Healing level 5, I''ll never need repairs again.'::text);
      end if;
    else
      wait := least(300 * lvl, 4 * 3600);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', 1,
        'repair_until', v_now + wait);
      f := f - 'points';
      lines := lines || to_jsonb(format('I lost. I need repairs, %s.',
        arena_private.format_time(wait)));
      lines := lines || to_jsonb('While I''m repairing, I can still visit the hangout.'::text);
    end if;
    if lost > 0 then
      lines := lines || to_jsonb(format('I lost %s credits.', lost));
    end if;
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

create or replace function public.arena_fight_npc(
  p_token text, p_npc_id text)
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
  v_str integer;
  v_def integer;
  v_hea integer;
  v_spd integer;
  v_luk integer;
  n arena_private.npcs%rowtype;
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
  v_heal5 boolean;
  v_told boolean;
  lost numeric;
  wait integer;
  v_won boolean;
  v_result jsonb;
  v_ability text;
  v_every integer;
  v_ability_round boolean;
  v_trap boolean := false;
  v_healed integer;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into n from arena_private.npcs
  where npc_id = coalesce(p_npc_id, '');
  if not found then
    return jsonb_build_object(
      'error', 'I do not know that creature.');
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
        format('I''m still repairing. %s left.',
          arena_private.format_time((f ->> 'repair_until')::double precision - v_now)),
        'I can visit the hangout or browse the shop while I wait.'),
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
  c_stats := arena_private.distribute_points(
    2 * (greatest(1, lvl) - 1),
    n.w_strength, n.w_defense, n.w_health, n.w_speed, n.w_luck);
  c_str := (c_stats ->> 'strength')::integer;
  c_hea := (c_stats ->> 'health')::integer;
  c_def := (c_stats ->> 'defense')::integer;
  c_spd := (c_stats ->> 'speed')::integer;
  c_luk := (c_stats ->> 'luck')::integer;
  c_max_hp := round((30 + 15 * (lvl - 1)) * n.hp_mult)::integer + 10 * c_hea;
  c_hp := c_max_hp;
  c_dmg := round((4 + 2 * (lvl - 1)) * n.dmg_mult)::integer + 2 * c_str;
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
  v_ability := n.ability;
  v_every := n.ability_every;
  lines := jsonb_build_array(format('A %s appears! Level %s.', n.name, lvl));

  while f_hp > 0 and c_hp > 0 and round_no < 20 loop
    round_no := round_no + 1;
    v_ability_round := v_every > 0 and round_no % v_every = 0;
    for v_turn in 1..2 loop
      exit when f_hp <= 0 or c_hp <= 0;
      v_fighter_turn := (fighter_first and v_turn = 1)
        or (not fighter_first and v_turn = 2);
      if v_fighter_turn then
        if v_ability_round and v_ability in ('shield', 'vanish', 'dodge') then
          -- The fighter's hit is blocked outright this round.
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
        elsif random() * 100 < c_dodge then
          lines := lines || to_jsonb(format(
            'Round %s: The %s dodges! My hit misses.', round_no, n.name));
        else
          hit := dmg + floor(random() * 4)::integer;
          v_crit := random() * 100 < f_crit;
          if v_crit then
            hit := round(hit * 1.5)::integer;
          end if;
          hit := greatest(1, hit - c_soak);
          hit := least(hit, floor(0.75 * c_max_hp)::integer);
          if v_trap then
            -- The sugar trap makes this one hit sticky and weak.
            v_trap := false;
            hit := greatest(1, hit / 2);
          end if;
          c_hp := c_hp - hit;
          if v_crit then
            lines := lines || to_jsonb(format(
              'Round %s: Critical hit! I hit the %s for %s.',
              round_no, n.name, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: I hit the %s for %s.',
              round_no, n.name, hit));
          end if;
        end if;
      else
        if v_ability_round and v_ability in ('flare', 'shock') then
          -- A burst of flame / a shock: this round's hit deals
          -- half as much again, before the fighter's armor
          -- soaks some of it. No crit on top: the burst is
          -- the excitement that round.
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
          if random() * 100 < f_dodge then
            lines := lines || to_jsonb(format(
              'Round %s: I dodge! The %s''s hit misses.',
              round_no, n.name));
          else
            hit := round((c_dmg + floor(random() * 3)::integer) * 1.5)::integer;
            hit := greatest(1, hit - (def / 2));
            hit := least(hit, floor(0.75 * f_max_hp)::integer);
            f_hp := f_hp - hit;
            lines := lines || to_jsonb(format(
              'Round %s: The %s hits me for %s.',
              round_no, n.name, hit));
          end if;
        elsif v_ability_round and v_ability = 'sugar_trap' then
          -- A sticky trap: the fighter's NEXT hit deals only
          -- half damage. The creature still hits this round.
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
          v_trap := true;
          if random() * 100 < f_dodge then
            lines := lines || to_jsonb(format(
              'Round %s: I dodge! The %s''s hit misses.',
              round_no, n.name));
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
                'Round %s: Critical hit! The %s hits me for %s.',
                round_no, n.name, hit));
            else
              lines := lines || to_jsonb(format(
                'Round %s: The %s hits me for %s.',
                round_no, n.name, hit));
            end if;
          end if;
        elsif v_ability_round and v_ability = 'double_hit' then
          -- Two quick hits in one round, each for the
          -- creature's normal damage.
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
          for v_hit in 1..2 loop
            exit when f_hp <= 0 or c_hp <= 0;
            if random() * 100 < f_dodge then
              lines := lines || to_jsonb(format(
                'Round %s: I dodge! The %s''s hit misses.',
                round_no, n.name));
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
                  'Round %s: Critical hit! The %s hits me for %s.',
                  round_no, n.name, hit));
              else
                lines := lines || to_jsonb(format(
                  'Round %s: The %s hits me for %s.',
                  round_no, n.name, hit));
              end if;
            end if;
          end loop;
        else
          if random() * 100 < f_dodge then
            lines := lines || to_jsonb(format(
              'Round %s: I dodge! The %s''s hit misses.',
              round_no, n.name));
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
                'Round %s: Critical hit! The %s hits me for %s.',
                round_no, n.name, hit));
            else
              lines := lines || to_jsonb(format(
                'Round %s: The %s hits me for %s.',
                round_no, n.name, hit));
            end if;
          end if;
        end if;
      end if;
    end loop;
    if c_hp > 0 and v_ability_round and v_ability = 'self_repair' then
      -- The repair bot patches itself up mid-fight, for 15%
      -- of its max health, if it is still standing.
      v_healed := greatest(1, round(0.15 * c_max_hp)::integer);
      c_hp := least(c_max_hp, c_hp + v_healed);
      lines := lines || to_jsonb(format(
        'Round %s: %s', round_no, n.ability_line));
    end if;
  end loop;

  if c_hp <= 0 then
    v_won := true;
    xp_gain := round((20 + 5 * lvl) * n.reward_mult)::integer;
    cr_gain := round((10 + 5 * lvl) * n.reward_mult);
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
    v_heal5 := coalesce((f ->> 'healing_level')::integer, 0) >= 5;
    f := f || jsonb_build_object(
      'xp', cur_xp,
      'level', new_level,
      'max_hp', new_max_hp,
      'hp', case when v_heal5 then new_max_hp else greatest(1, f_hp) end,
      'credits', arena_private.credits_of(f) + cr_gain,
      'stat_points', new_stat_points,
      'wins', (f ->> 'wins')::integer + 1);
    f := f - 'points';
    lines := lines || to_jsonb(format('I won! I earned %s experience and %s credits.',
      xp_gain, cr_gain));
    if v_heal5 and f_hp < new_max_hp then
      lines := lines || to_jsonb('My Second Wind restored me to full health.'::text);
    end if;
    if gained > 0 then
      lines := lines || to_jsonb(format(
        'I''m now level %s! My health grew to %s. I have %s stat points to spend.',
        new_level, new_max_hp, new_stat_points));
    end if;
  else
    v_won := false;
    xp_gain := 0;
    lost := least(arena_private.credits_of(f), 5);
    cr_gain := -lost;
    v_heal5 := coalesce((f ->> 'healing_level')::integer, 0) >= 5;
    if v_heal5 then
      -- Level 5 Healing (Phase 25): no repair is ever
      -- needed again. Back to full health at once, and the
      -- game says so — in full the first time it saves a
      -- repair, in short after that.
      v_told := coalesce((f ->> 'healing_full_told')::boolean, false);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', f_max_hp,
        'repair_until', 0,
        'healing_full_told', true);
      f := f - 'points';
      if v_told then
        lines := lines || to_jsonb(
          'I lost, but my Second Wind brought me back to full health. No repairs needed.'::text);
      else
        lines := lines || to_jsonb(
          'I lost, but my Second Wind brought me back to full health. No repairs needed — at Healing level 5, I''ll never need repairs again.'::text);
      end if;
    else
      wait := least(300 * lvl, 4 * 3600);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', 1,
        'repair_until', v_now + wait);
      f := f - 'points';
      lines := lines || to_jsonb(format('I lost. I need repairs, %s.',
        arena_private.format_time(wait)));
      lines := lines || to_jsonb('While I''m repairing, I can still visit the hangout.'::text);
    end if;
    if lost > 0 then
      lines := lines || to_jsonb(format('I lost %s credits.', lost));
    end if;
  end if;

  update arena_private.players
  set fighter = f, last_fight_at = now(), updated_at = now()
  where player_code = v_code;

  v_result := jsonb_build_object(
    'won', v_won, 'xp', xp_gain, 'credits', cr_gain,
    'npc_id', n.npc_id);
  perform arena_private.log_event(v_code, 'fight_npc', v_result, 'server');

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
      'error', 'I have no stat points to spend right now.',
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
    when 'speed' then format('Speed is now %s. One more point makes me a little faster.', v_value)
    when 'luck' then format('Luck is now %s. One more point adds a little critical chance.', v_value)
  end;
  if v_points - 1 > 0 then
    v_line := v_line || format(' I have %s stat %s left.',
      v_points - 1, case when v_points - 1 = 1 then 'point' else 'points' end);
  else
    v_line := v_line || ' That was my last stat point.';
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
      'error', 'I have no stat points spent to reset.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_used := coalesce((f ->> 'respecs_used')::integer, 0);
  v_cost := case when v_used <= 0 then 0 else 100 end;
  if v_cost > arena_private.credits_of(f) then
    return jsonb_build_object(
      'error', format('A respec costs %s credits and I have %s credits.',
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
    v_line := format('My stats are reset. I have %s stat points to spend. That respec cost %s credits.',
      v_points, v_cost);
  else
    v_line := format('My stats are reset. I have %s stat points to spend. My first respec was free.',
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

create or replace function public.arena_spend_quest_stat(
  p_token text, p_stat text)
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
  if v_stat not in ('charm', 'renown', 'insight') then
    return jsonb_build_object('error', 'Pick charm, renown, or insight.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_points := coalesce((f ->> 'quest_points')::integer, 0);
  if v_points <= 0 then
    return jsonb_build_object(
      'error', 'I have no quest points to spend right now.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_stats := coalesce(f -> 'quest_stats',
    '{"charm": 0, "renown": 0, "insight": 0}'::jsonb);
  v_value := coalesce((v_stats ->> v_stat)::integer, 0);
  if v_value >= 10 then
    return jsonb_build_object(
      'error', format('%s is already at its best, level 10.',
                      initcap(v_stat)),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_value := v_value + 1;
  v_stats := jsonb_set(v_stats, array[v_stat], to_jsonb(v_value));
  f := f || jsonb_build_object('quest_stats', v_stats,
                               'quest_points', v_points - 1);
  v_line := case v_stat
    when 'charm' then format('Charm is now %s. Quests pay %s percent more credits.',
                             v_value, v_value * 5)
    when 'renown' then format('Renown is now %s. %s percent chance of 1 bonus reputation when a quest finishes.',
                              v_value, v_value * 10)
    when 'insight' then format('Insight is now %s. Quests pay %s percent more quest experience.',
                               v_value, v_value * 5)
  end;
  if v_points - 1 > 0 then
    v_line := v_line || format(' I have %s quest %s left.',
      v_points - 1, case when v_points - 1 = 1 then 'point' else 'points' end);
  else
    v_line := v_line || ' That was my last quest point.';
  end if;
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'spend_quest_stat',
    jsonb_build_object('stat', v_stat), 'server');
  return jsonb_build_object(
    'message', v_line,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;

create or replace function public.arena_complete_quest(
  p_token text, p_quest_id text)
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
  v_board jsonb;
  v_done jsonb;
  v_quest jsonb;
  v_active jsonb;
  v_giver text;
  v_rep_before integer;
  v_rep_after integer;
  v_base integer;
  v_credits numeric;
  v_tier_line text := null;
  v_pending jsonb;
  v_heal integer;
  v_roll integer;
  v_message text;
  v_qlevel integer;
  v_qxp integer;
  v_qpoints integer;
  v_xp_base integer;
  v_xp_earned integer;
  v_level_ups integer := 0;
  v_bonus_rep integer := 0;
  v_qxp_line text;
  v_qlevel_line text := null;
  v_auto integer;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := arena_private.quest_board_ensure(t.fighter);
  v_board := coalesce(f -> 'quests_board', '[]'::jsonb);
  v_done := coalesce(f -> 'quests_done', '[]'::jsonb);
  v_quest := arena_private.quest_on_board(v_board, p_quest_id);
  if v_quest is null then
    return jsonb_build_object('error', 'That quest is not on your board.');
  end if;
  if v_done @> to_jsonb(p_quest_id) then
    return jsonb_build_object('error', 'You already finished that quest.');
  end if;
  v_active := f -> 'quests_active';
  if v_active is null or jsonb_typeof(v_active) <> 'object'
     or v_active ->> 'id' <> p_quest_id then
    return jsonb_build_object(
      'error', 'Start that quest in the hangout first.');
  end if;
  if coalesce((v_active ->> 'paused')::boolean, false) then
    -- A paused quest never completes: its clock is frozen
    -- while the player is away from the hangout. Only a
    -- quest with no time left at all may finish.
    if coalesce((v_active ->> 'remaining_seconds')::double precision, 0) > 0 then
      return jsonb_build_object('error', format(
        'That quest is paused. About %s left.',
        arena_private.format_time(
          (v_active ->> 'remaining_seconds')::double precision)));
    end if;
  elsif (v_active ->> 'finish_at')::double precision > v_now then
    return jsonb_build_object('error', format(
      'That quest is not done yet. About %s left.',
      arena_private.format_time(
        (v_active ->> 'finish_at')::double precision - v_now)));
  end if;
  -- A fighter mid-repair completes quests and gets paid
  -- exactly like a healthy one. That is the whole point of
  -- the hangout. (No repair check here, on purpose.)
  if coalesce((v_quest ->> 'coop')::boolean, false) then
    if not (coalesce(f -> 'quests_joined', '[]'::jsonb)
            @> to_jsonb(p_quest_id)) then
      return jsonb_build_object(
        'error', 'You never joined that fair, so there is nothing to finish.');
    end if;
  end if;
  v_giver := v_quest ->> 'giver';
  -- Quest credits (Phase 26) are keyed to the quest level,
  -- not the fighter level: they grow infinitely as quests
  -- level up, even though quest timers cap at 4 hours. A
  -- Medium quest now pays what a fight win pays only when
  -- the quest level and the fighter level happen to match.
  v_qlevel := coalesce((f ->> 'quest_level')::integer, 1);
  -- Automatic bonus (Phase 26, grows right from the start,
  -- Makenna 2026-11-18): +1% per quest level to Charm,
  -- Renown and Insight, like combat's automatic +10 HP per
  -- combat level. The bonus is 1% at quest level 1 and 5%
  -- at quest level 5. It stacks with spent quest points
  -- and never caps.
  v_auto := greatest(0, v_qlevel);
  -- Renown (Phase 23): +10% chance of +1 bonus reputation
  -- per Renown point, plus the automatic bonus (Phase 26).
  -- The server rolls it; at 10 points the chance is 100%,
  -- so every finished quest earns it.
  if random() < least(1.0, arena_private.quest_stat_value(f, 'renown') * 0.10 + v_auto * 0.01) then
    v_bonus_rep := 1;
  end if;
  v_rep_before := coalesce((f -> 'quests_rep' ->> v_giver)::integer, 0);
  v_rep_after := v_rep_before + 1 + v_bonus_rep;
  v_base := arena_private.quest_reward(v_quest ->> 'difficulty', v_qlevel);
  if v_rep_before >= 3 then
    -- Helper tier: this giver's quests pay +25% from now on.
    v_base := floor(v_base * 1.25)::integer;
  end if;
  -- Charm (Phase 23): +5% quest credits per Charm point,
  -- plus the automatic bonus (Phase 26).
  v_base := floor(v_base
    * (1 + 0.05 * arena_private.quest_stat_value(f, 'charm')
       + 0.01 * v_auto))::integer;
  v_credits := arena_private.credits_of(f) + v_base;
  f := jsonb_set(f, '{credits}', to_jsonb(v_credits));
  f := jsonb_set(f, '{quests_rep}', (coalesce(f -> 'quests_rep', '{}'::jsonb)
    || jsonb_build_object(v_giver, v_rep_after)));
  -- Quest XP (Phase 23): only finishing a quest earns it.
  -- Insight adds +5% quest XP per Insight point, plus the
  -- automatic bonus (Phase 26). Quest levels give no max
  -- HP and no combat stat points; each quest level-up banks
  -- 1 quest point to spend.
  v_qxp := coalesce((f ->> 'quest_xp')::integer, 0);
  v_qpoints := coalesce((f ->> 'quest_points')::integer, 0);
  v_xp_base := arena_private.quest_xp(v_quest ->> 'difficulty', v_qlevel);
  v_xp_earned := floor(v_xp_base
    * (1 + 0.05 * arena_private.quest_stat_value(f, 'insight')
       + 0.01 * v_auto))::integer;
  v_qxp := v_qxp + v_xp_earned;
  while v_qxp >= arena_private.quest_xp_to_next(v_qlevel) loop
    v_qxp := v_qxp - arena_private.quest_xp_to_next(v_qlevel);
    v_qlevel := v_qlevel + 1;
    v_qpoints := v_qpoints + 1;
    v_level_ups := v_level_ups + 1;
  end loop;
  f := f || jsonb_build_object(
    'quest_level', v_qlevel,
    'quest_xp', v_qxp,
    'quest_points', v_qpoints);
  v_qxp_line := format(
    'You earned %s quest experience, %s. You have %s quest experience now, '
    '%s more to reach quest level %s.',
    v_xp_earned, f ->> 'name', v_qxp,
    arena_private.quest_xp_to_next(v_qlevel) - v_qxp, v_qlevel + 1);
  if v_level_ups > 0 then
    v_qlevel_line := format(
      'You''re now quest level %s, %s! You have %s quest %s to spend.',
      v_qlevel, f ->> 'name', v_qpoints,
      case when v_qpoints = 1 then 'point' else 'points' end);
  end if;
  f := f || jsonb_build_object(
    'quests_board', arena_private.quest_board_without(v_board, p_quest_id),
    'quests_done', v_done || to_jsonb(p_quest_id),
    'quests_active', null);
  v_message := format('Quest done, %s! Thank you — you earned %s credits.', f ->> 'name', v_base);
  -- Tier crossings, announced by the giver in their own voice.
  if v_rep_before < 3 and v_rep_after >= 3 then
    v_tier_line := format(
      '%s says: Three jobs done, %s, and not one of them sloppy. You''re a helper now, and my quests pay a little extra for you.',
      v_giver, f ->> 'name');
  elsif v_rep_before < 8 and v_rep_after >= 8 then
    v_tier_line := format(
      '%s says: Eight jobs done, %s. You''re a friend now, and friends get looked after. Pick a free upgrade: your weapon or your armor.',
      v_giver, f ->> 'name');
    v_pending := f -> 'quests_gift_pending';
    if v_pending is null or jsonb_typeof(v_pending) <> 'object' then
      f := f || jsonb_build_object('quests_gift_pending',
        jsonb_build_object('giver', v_giver, 'tier', 'Friend'));
    end if;
  elsif v_rep_before < 15 and v_rep_after >= 15 then
    v_heal := coalesce((f ->> 'healing_level')::integer, 0);
    if v_heal < 5 then
      f := jsonb_set(f, '{healing_level}', to_jsonb(v_heal + 1));
      v_tier_line := format(
        '%s says: Fifteen jobs done, %s. You''re family now. Let me patch up that healing skill of yours — on the house. Healing is now level %s.',
        v_giver, f ->> 'name', v_heal + 1);
    else
      -- Healing is maxed: never waste the gift, pick another
      -- one at random instead. The Healing cap is never broken.
      v_roll := floor(random() * 3)::integer;
      if v_roll = 0 then
        f := jsonb_set(f, '{weapon_level}',
          to_jsonb(coalesce((f ->> 'weapon_level')::integer, 1) + 1));
        v_tier_line := format(
          '%s says: Fifteen jobs done. Your healing is already at its best, so here is a free weapon level instead.',
          v_giver);
      elsif v_roll = 1 then
        f := jsonb_set(f, '{armor_level}',
          to_jsonb(coalesce((f ->> 'armor_level')::integer, 1) + 1));
        v_tier_line := format(
          '%s says: Fifteen jobs done. Your healing is already at its best, so here is a free armor level instead.',
          v_giver);
      else
        f := f || jsonb_build_object('credits',
          to_jsonb(arena_private.credits_of(f) + 50));
        v_tier_line := format(
          '%s says: Fifteen jobs done. Your healing is already at its best, so here are 50 extra credits instead.',
          v_giver);
      end if;
    end if;
  end if;
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'quest_completed',
    jsonb_build_object('quest', p_quest_id, 'credits', v_base,
                       'quest_xp', v_xp_earned), 'server');
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_quest,
    'credits', v_base,
    'message', v_message,
    'tier_line', v_tier_line,
    'giver', v_giver,
    'giver_voice', arena_private.quest_giver_voice(v_giver),
    'reputation', coalesce(f -> 'quests_rep', '{}'::jsonb),
    'gift_pending', f -> 'quests_gift_pending',
    'quest_xp_earned', v_xp_earned,
    'quest_level', v_qlevel,
    'quest_xp', v_qxp,
    'quest_xp_to_next',
      arena_private.quest_xp_to_next(v_qlevel) - v_qxp,
    'quest_points', v_qpoints,
    'quest_level_ups', v_level_ups,
    'bonus_reputation', v_bonus_rep,
    'quest_xp_line', v_qxp_line,
    'quest_level_line', v_qlevel_line);
end;
$$;

create or replace function public.arena_choose_quest_gift(
  p_token text, p_slot text)
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
  v_pending jsonb;
  v_giver text;
  v_level integer;
  v_name text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if p_slot not in ('weapon', 'armor') then
    return jsonb_build_object('error', 'Pick weapon or armor for your free gift.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_pending := f -> 'quests_gift_pending';
  if v_pending is null or jsonb_typeof(v_pending) <> 'object' then
    return jsonb_build_object('error', 'No free gift is waiting for you right now.');
  end if;
  v_giver := v_pending ->> 'giver';
  v_level := coalesce((f ->> (p_slot || '_level'))::integer, 1) + 1;
  v_name := f ->> (p_slot || '_name');
  -- Instant gift: no credits, no time, no queue.
  f := jsonb_set(f, array[p_slot || '_level'], to_jsonb(v_level));
  f := f || jsonb_build_object('quests_gift_pending', null);
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'quest_gift',
    jsonb_build_object('slot', p_slot, 'giver', v_giver), 'server');
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'message', format(
      '%s gave you a free %s upgrade. My %s is now level %s.',
      v_giver, p_slot, v_name, v_level));
end;
$$;

-- The NPC ability lines live in the arena_private.npcs
-- table, not in a function: the same four "Your hit" lines
-- the client changed in game_logic.py, so online fights
-- say "My hit" too.
update arena_private.npcs
  set ability_line = 'Bulkhead raises its plating shield! My hit bounces off!'
  where npc_id = 'bulkhead';
update arena_private.npcs
  set ability_line = 'Ghost Drone vanishes! My hit misses!'
  where npc_id = 'ghost_drone';
update arena_private.npcs
  set ability_line = 'Baker Belle throws a sugar trap! My next hit is sticky and weak!'
  where npc_id = 'baker_belle';
update arena_private.npcs
  set ability_line = 'Ember Owl swoops aside! My hit misses!'
  where npc_id = 'ember_owl';

revoke all on function public.arena_start_upgrade(text, text) from public;
grant execute on function public.arena_start_upgrade(text, text) to anon, authenticated;
revoke all on function public.arena_max_upgrade(text, text) from public;
grant execute on function public.arena_max_upgrade(text, text) to anon, authenticated;
revoke all on function public.arena_fight(text, text) from public;
grant execute on function public.arena_fight(text, text) to anon, authenticated;
revoke all on function public.arena_fight_npc(text, text) from public;
grant execute on function public.arena_fight_npc(text, text) to anon, authenticated;
revoke all on function public.arena_spend_stat(text, text) from public;
grant execute on function public.arena_spend_stat(text, text) to anon, authenticated;
revoke all on function public.arena_respec(text) from public;
grant execute on function public.arena_respec(text) to anon, authenticated;
revoke all on function public.arena_spend_quest_stat(text, text) from public;
grant execute on function public.arena_spend_quest_stat(text, text) to anon, authenticated;
revoke all on function public.arena_complete_quest(text, text) from public;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
revoke all on function public.arena_choose_quest_gift(text, text) from public;
grant execute on function public.arena_choose_quest_gift(text, text) to anon, authenticated;
