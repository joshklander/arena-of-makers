-- Phase 35: the witch is a third fighter kind (kind plumbing only).
--
-- Decided by Makenna 2026-11-25 (voice call): witch joins robot and
-- chef as a playable fighter, still one fighter per player. The
-- stored kind stays 'witch' for everyone; a male witch is called a
-- warlock and a female witch is called a witch, in words only.
-- Weapon "Spellbound Wand", armor "Mystic Robe", base damage 11
-- (robot 12, chef 10). No elemental spells, quest givers or
-- ambience in this piece — those are the next small pieces.
--
-- Follows supabase/README.md: a new file, no old migration edited.
-- Each function below is redefined from its LATEST version, so
-- nothing is reverted: new_fighter from Phase 18 (quest fields),
-- arena_create_account from the baseline (never redefined since),
-- arena_fight and arena_fight_npc from Phase 28 (first person).
-- The damage line is the only change in the two fight functions,
-- and it is explicit per kind — never a silent else-10, so an
-- unknown kind can never quietly hit like a chef. Old robot and
-- chef fighters are untouched by every change here, and no new
-- stored field is added.
--
-- Kiro's password sign-in, auto-login and anti-cheat are untouched.

alter table arena_private.players
  drop constraint if exists players_kind_check,
  add constraint players_kind_check check (kind in ('robot', 'chef', 'witch'));

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
    'credits', 0,
    'wins', 0,
    'losses', 0,
    'weapon_name', case p_kind when 'robot' then 'Laser Blaster' when 'chef' then 'Trusty Spatula' when 'witch' then 'Spellbound Wand' end,
    'weapon_level', 1,
    'armor_name', case p_kind when 'robot' then 'Scrap Plating' when 'chef' then 'Chef Apron' when 'witch' then 'Mystic Robe' end,
    'armor_level', 1,
    'stats', '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb,
    'stat_points', 0,
    'stats_migrated', true,
    'respecs_used', 0,
    'repair_until', 0,
    'upgrade', null,
    'upgrade_queue', null,
    'upgrade_total', 0,
    'healing_level', 0,
    'quests_board', '[]'::jsonb,
    'quests_done', '[]'::jsonb,
    'quests_rep', '{}'::jsonb,
    'quests_joined', '[]'::jsonb,
    'quests_active', null,
    'quests_gift_pending', null
  )
$$;

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
  if p_kind is null or p_kind not in ('robot', 'chef', 'witch') then
    return jsonb_build_object('error', 'Pick robot, chef or witch for your fighter.');
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
  dmg := (case f ->> 'kind' when 'robot' then 12 when 'chef' then 10 when 'witch' then 11 end)
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
  dmg := (case f ->> 'kind' when 'robot' then 12 when 'chef' then 10 when 'witch' then 11 end)
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
