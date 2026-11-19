-- Phase 25: the Healing skill — buyable in the Shop,
-- max level 5, called Second Wind.
--
-- New file per change (see supabase/README.md): the baseline,
-- the credits-wording fix and the quest and NPC migrations are
-- untouched. Old game versions keep working: the new slot is
-- opt-in (nobody is forced to buy it), the fight functions
-- return the same fields, and fighters without a Healing
-- level behave exactly as before.
--
-- Healing (Makenna, Nov 18, 2026): bought with credits on the
-- Shop tab, separate from weapon and armor. Cost is
-- exponential, NOT the normal upgrade curve: level 1 = 50,
-- 2 = 85, 3 = 140, 4 = 240, 5 = 400 credits (about 915 in
-- total). Time is slower than normal upgrades: reaching
-- level 1 takes 12 minutes, level 2 takes 24, and so on —
-- 12 minutes times the level being reached (about 3 hours
-- in total), inside the same 4-hour cap. It follows the
-- one-upgrade-set-at-a-time rule (Phase 24): a Healing
-- upgrade cannot start while another set is running, and
-- vice versa. Max level 5 — the ONLY capped upgrade.
--
-- Each level heals 19% of max health on a tag-team jump-in
-- (level 1 = 19%, level 5 = 95%, never more, never past max
-- health). Tag team itself is NOT built yet; the heal
-- amounts are the shared rule the tag-team phase will use.
--
-- Level 5 also works solo (Makenna, Nov 18, 2026): after
-- every fight the fighter is back to FULL health (100%),
-- and no repair timer is ever needed again. The game says so
-- in full the first time it saves a repair, in short after
-- that (flag healing_full_told on the fighter). Reaching
-- level 5 also ends a repair already running at once.
--
-- The server stays the only judge, exactly as for weapon
-- and armor: the game sends only the in-memory session token
-- plus the slot ('healing'). No username, no player code, no
-- password, no .env contents, no key, no personal data.

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
        'finish', p_now + case when (up ->> 'slot') = 'healing'
          then least(720 * v_next, 4 * 3600)
          else least(60 * (v_next - 1), 4 * 3600) end));
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
      if (up ->> 'slot') = 'healing' and (up ->> 'level')::integer >= 5
         and repair > p_now then
        -- Reaching Healing level 5 ends repairs for good: a
        -- fighter still under repair when the skill maxes out
        -- is back to full health at once, with no wait left.
        f := f || jsonb_build_object(
          'hp', arena_private.fighter_max_hp(f), 'repair_until', 0);
        messages := messages || to_jsonb(
          'No more repairs — you are back to full health.'::text);
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
  lvl := (f ->> (p_slot || '_level'))::integer;
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
  v_level := (f ->> (p_slot || '_level'))::integer;
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
          then (array[50, 85, 140, 240, 400])[(f ->> 'healing_level')::integer + 1]
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
    lines := lines || to_jsonb(format('You won! You earned %s experience and %s credits.',
      xp_gain, cr_gain));
    if v_heal5 and f_hp < new_max_hp then
      lines := lines || to_jsonb('Your Second Wind restored you to full health.'::text);
    end if;
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
          'You lost. Your Second Wind brought you back to full health. No repairs needed.'::text);
      else
        lines := lines || to_jsonb(
          'You lost. Your Second Wind brought you back to full health. No repairs needed — at Healing level 5, you never need repairs again.'::text);
      end if;
    else
      wait := least(300 * lvl, 4 * 3600);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', 1,
        'repair_until', v_now + wait);
      f := f - 'points';
      lines := lines || to_jsonb(format('You lost. Your fighter needs repairs, %s.',
        arena_private.format_time(wait)));
      lines := lines || to_jsonb('While repairs run, you can still visit the hangout.'::text);
    end if;
    if lost > 0 then
      lines := lines || to_jsonb(format('You lost %s credits.', lost));
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
            'Round %s: The %s dodges! Your hit misses.', round_no, n.name));
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
              'Round %s: Critical hit! %s hits the %s for %s.',
              round_no, v_name, n.name, hit));
          else
            lines := lines || to_jsonb(format(
              'Round %s: %s hits the %s for %s.',
              round_no, v_name, n.name, hit));
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
              'Round %s: %s dodges! The %s''s hit misses.',
              round_no, v_name, n.name));
          else
            hit := round((c_dmg + floor(random() * 3)::integer) * 1.5)::integer;
            hit := greatest(1, hit - (def / 2));
            hit := least(hit, floor(0.75 * f_max_hp)::integer);
            f_hp := f_hp - hit;
            lines := lines || to_jsonb(format(
              'Round %s: The %s hits %s for %s.',
              round_no, n.name, v_name, hit));
          end if;
        elsif v_ability_round and v_ability = 'sugar_trap' then
          -- A sticky trap: the fighter's NEXT hit deals only
          -- half damage. The creature still hits this round.
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
          v_trap := true;
          if random() * 100 < f_dodge then
            lines := lines || to_jsonb(format(
              'Round %s: %s dodges! The %s''s hit misses.',
              round_no, v_name, n.name));
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
                'Round %s: Critical hit! The %s hits %s for %s.',
                round_no, n.name, v_name, hit));
            else
              lines := lines || to_jsonb(format(
                'Round %s: The %s hits %s for %s.',
                round_no, n.name, v_name, hit));
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
                'Round %s: %s dodges! The %s''s hit misses.',
                round_no, v_name, n.name));
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
                  'Round %s: Critical hit! The %s hits %s for %s.',
                  round_no, n.name, v_name, hit));
              else
                lines := lines || to_jsonb(format(
                  'Round %s: The %s hits %s for %s.',
                  round_no, n.name, v_name, hit));
              end if;
            end if;
          end loop;
        else
          if random() * 100 < f_dodge then
            lines := lines || to_jsonb(format(
              'Round %s: %s dodges! The %s''s hit misses.',
              round_no, v_name, n.name));
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
                'Round %s: Critical hit! The %s hits %s for %s.',
                round_no, n.name, v_name, hit));
            else
              lines := lines || to_jsonb(format(
                'Round %s: The %s hits %s for %s.',
                round_no, n.name, v_name, hit));
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
    lines := lines || to_jsonb(format('You won! You earned %s experience and %s credits.',
      xp_gain, cr_gain));
    if v_heal5 and f_hp < new_max_hp then
      lines := lines || to_jsonb('Your Second Wind restored you to full health.'::text);
    end if;
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
          'You lost. Your Second Wind brought you back to full health. No repairs needed.'::text);
      else
        lines := lines || to_jsonb(
          'You lost. Your Second Wind brought you back to full health. No repairs needed — at Healing level 5, you never need repairs again.'::text);
      end if;
    else
      wait := least(300 * lvl, 4 * 3600);
      f := f || jsonb_build_object(
        'credits', arena_private.credits_of(f) - lost,
        'losses', (f ->> 'losses')::integer + 1,
        'hp', 1,
        'repair_until', v_now + wait);
      f := f - 'points';
      lines := lines || to_jsonb(format('You lost. Your fighter needs repairs, %s.',
        arena_private.format_time(wait)));
      lines := lines || to_jsonb('While repairs run, you can still visit the hangout.'::text);
    end if;
    if lost > 0 then
      lines := lines || to_jsonb(format('You lost %s credits.', lost));
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
revoke all on function public.arena_start_upgrade(text, text) from public;
grant execute on function public.arena_start_upgrade(text, text) to anon, authenticated;
revoke all on function public.arena_max_upgrade(text, text) from public;
grant execute on function public.arena_max_upgrade(text, text) to anon, authenticated;
revoke all on function public.arena_fight(text, text) from public;
grant execute on function public.arena_fight(text, text) to anon, authenticated;
revoke all on function public.arena_fight_npc(text, text) from public;
grant execute on function public.arena_fight_npc(text, text) to anon, authenticated;
