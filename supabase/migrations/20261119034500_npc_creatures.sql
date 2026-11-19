-- Phase 24: NPC creatures — the 9 draft NPCs become real
-- fightable opponents, alongside Scrap Rat.
--
-- New file per change (see supabase/README.md): the baseline
-- and the quest migrations are untouched. Old game versions
-- keep working: arena_fight is unchanged, and this file only
-- adds a table and one new function.
--
-- The server stays the only judge, exactly as for Scrap Rat:
-- the game sends only the in-memory session token plus one
-- creature id (like 'zip_scout'). No username, no player
-- code, no password, no .env contents, no key, no personal
-- data of any kind. The NPC table holds only NPC stats.
--
-- Every NPC is a multiplier on the Scrap Rat formulas, so a
-- fight stays fair at any level, plus a special ability that
-- fires every few rounds, plus the same 2 stat points per
-- level as a fighter, split by the NPC's profile (see
-- STATS_DESIGN.md). A flare or shock round never crits as
-- well: the burst is the excitement that round, and stacking
-- both would push a single hit past the fair band in the NPC
-- design (the hardest single round stays near a quarter of
-- the fighter's health; the 75% fairness guard still binds
-- every single hit).

create table if not exists arena_private.npcs (
  npc_id text primary key,
  name text not null,
  kind text not null,
  hp_mult numeric not null,
  dmg_mult numeric not null,
  reward_mult numeric not null,
  ability text not null,
  ability_every integer not null,
  ability_line text not null,
  w_speed integer not null,
  w_strength integer not null,
  w_health integer not null,
  w_defense integer not null,
  w_luck integer not null
);

revoke all on arena_private.npcs from public, anon, authenticated;

insert into arena_private.npcs
  (npc_id, name, kind, hp_mult, dmg_mult, reward_mult,
   ability, ability_every, ability_line,
   w_speed, w_strength, w_health, w_defense, w_luck)
values
  ('zip_scout', 'Zip Scout', 'robot', 0.7, 1.4, 1.2,
   'double_hit', 3, 'Zip Scout dashes in twice!',
   4, 3, 1, 1, 1),
  ('bulkhead', 'Bulkhead', 'robot', 1.8, 0.7, 1.1,
   'shield', 4, 'Bulkhead raises its plating shield! Your hit bounces off!',
   1, 1, 4, 3, 1),
  ('mend_o_matic', 'Mend-O-Matic', 'robot', 1.0, 0.9, 1.2,
   'self_repair', 3, 'Mend-O-Matic sparks and repairs itself!',
   2, 2, 3, 2, 1),
  ('ghost_drone', 'Ghost Drone', 'robot', 0.8, 1.2, 1.2,
   'vanish', 3, 'Ghost Drone vanishes! Your hit misses!',
   4, 3, 1, 0, 2),
  ('chop_chop', 'Chop-Chop Chef', 'chef', 0.75, 1.3, 1.2,
   'double_hit', 4, 'Chop-Chop Chef chops twice!',
   4, 3, 1, 1, 1),
  ('grill_gus', 'Grill Master Gus', 'chef', 1.6, 0.85, 1.1,
   'flare', 3, 'Grill Master Gus fires up the grill! A burst of flame!',
   1, 2, 4, 2, 1),
  ('baker_belle', 'Baker Belle', 'chef', 1.1, 1.0, 1.2,
   'sugar_trap', 4, 'Baker Belle throws a sugar trap! Your next hit is sticky and weak!',
   2, 2, 3, 2, 1),
  ('zap_fox', 'Zap Fox', 'animal', 0.9, 1.25, 1.2,
   'shock', 3, 'Zap Fox crackles with static! A shock!',
   4, 3, 1, 0, 2),
  ('ember_owl', 'Ember Owl', 'animal', 1.3, 0.95, 1.1,
   'dodge', 5, 'Ember Owl swoops aside! Your hit misses!',
   2, 1, 4, 2, 1)
on conflict (npc_id) do nothing;

-- Fight one NPC creature. A mirror of arena_fight, with the
-- creature's stats, multipliers, reward and ability read from
-- arena_private.npcs. Same session check, same timer and
-- repair checks, same 2-second slowdown, same 20-round cap,
-- same win/loss handling, same level-ups, same repair timer.
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

revoke all on function public.arena_fight_npc(text, text) from public;
grant execute on function public.arena_fight_npc(text, text) to anon, authenticated;
