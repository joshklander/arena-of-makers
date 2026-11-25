-- Phase 39: battle-spell affinities, ranked spell pick, and the
-- 12 magical creatures (Makenna, Nov 25, 2026). Phase 38b is
-- cancelled — its auto-study and no-credit learning move here too
-- (see 20261125233000_study_free_learning.sql, already on main
-- from the 38b authoring), so one phase holds everything and it
-- can all be tested together.
--
-- Affinities (Pokemon-style, chart in MAGICAL_CREATURES_DESIGN.md):
-- strong is double damage, weak is half, and two pairs do no
-- damage at all (lightning against earth, earth against wind).
-- In a fight the game picks the best learned spell against the
-- enemy on its own — most damage (spell level times the
-- affinity), falling back down the ranking when the best is not
-- learned yet, never a spell that does nothing; the wand only
-- when no learned spell does any damage. The 9 Phase 24
-- creatures and the Scrap Rat have no element, so affinities
-- stay neutral against them.
--
-- The 12 magical creatures (one per element, plus a rival witch
-- and a rival warlock) join arena_private.npcs; the fight pool
-- becomes 21 creatures. Their magic sound IS their own
-- element's spell sound (Makenna, Nov 25, 2026), so no separate
-- magic files — the Rival Witch casts a random elemental spell
-- (new ability random_spell), the Rival Warlock keeps his own
-- curse sound. arena_fight_npc returns "creature_magic"
-- (line index -> sound key) for the rounds a special fired, so
-- the client plays the magic sound for exactly those lines.
--
-- Old fighters keep working: a missing element is neutral, a
-- missing spells map means nothing learned — never a crash
-- (compatibility rule, Nov 18, 2026). No old migration edited,
-- no SQL run directly on live.

-- The creature's element (Phase 39): null for the Scrap Rat and
-- the 9 Phase 24 creatures (neutral), one of the ten elements —
-- or 'witch' for the rivals, which is also neutral — for the 12
-- magical creatures. Phase 39 fills it in for the new rows only.
alter table arena_private.npcs
  add column if not exists element text;

-- Affinity table (Phase 39): the multiplier for a spell of one
-- element hitting an enemy of another. No effect (0) is checked
-- first, so it wins over the strong/weak lists (earth is strong
-- against lightning, but lightning does zero to earth, not half).
-- Unknown elements — or no element at all — are neutral (1).
create or replace function arena_private.spell_multiplier(
  p_element text, p_enemy_element text)
returns numeric
language sql immutable
set search_path = ''
as $$
  select case
    when p_element = 'lightning' and p_enemy_element = 'earth' then 0
    when p_element = 'earth' and p_enemy_element = 'wind' then 0
    when p_element = 'fire' and p_enemy_element in ('ice', 'light') then 2
    when p_element = 'water' and p_enemy_element in ('fire', 'earth') then 2
    when p_element = 'ice' and p_enemy_element in ('earth', 'wind') then 2
    when p_element = 'wind' and p_enemy_element = 'poison' then 2
    when p_element = 'poison' and p_enemy_element in ('light', 'water') then 2
    when p_element = 'light' and p_enemy_element = 'dark' then 2
    when p_element = 'shadow' and p_enemy_element in ('shadow', 'ice') then 2
    when p_element = 'dark' and p_enemy_element in ('shadow', 'lightning') then 2
    when p_element = 'earth' and p_enemy_element in ('fire', 'lightning', 'poison') then 2
    when p_element = 'lightning' and p_enemy_element in ('water', 'wind') then 2
    when p_element = 'fire' and p_enemy_element in ('water', 'earth') then 0.5
    when p_element = 'water' and p_enemy_element in ('lightning', 'poison') then 0.5
    when p_element = 'ice' and p_enemy_element in ('fire', 'shadow') then 0.5
    when p_element = 'wind' and p_enemy_element in ('ice', 'lightning') then 0.5
    when p_element = 'poison' and p_enemy_element in ('earth', 'wind') then 0.5
    when p_element = 'light' and p_enemy_element in ('poison', 'fire') then 0.5
    when p_element = 'shadow' and p_enemy_element in ('dark', 'shadow') then 0.5
    when p_element = 'dark' and p_enemy_element = 'light' then 0.5
    when p_element = 'earth' and p_enemy_element in ('water', 'ice') then 0.5
    when p_element = 'lightning' and p_enemy_element = 'dark' then 0.5
    else 1
  end
$$;

-- Pick the best learned spell against an enemy of this element
-- (Phase 39, ranked fallback — replaces the Phase 38 random
-- pick): most damage first (spell level times the affinity), so
-- a 2x spell at a lower level can still lose to a high-level
-- neutral one; ties go to the stronger affinity, then the
-- higher level, then the earlier element in the chart's order.
-- A spell that does no damage against this enemy (0x) is never
-- picked. Null when nothing is learned yet, nothing learned
-- does any damage, or the fighter is not a witch at all.
create or replace function arena_private.spell_pick_best(
  p_fighter jsonb, p_enemy_element text)
returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'element', s.element, 'tier', s.tier,
    'name', arena_private.spell_name(s.element, s.tier),
    'level', s.level,
    'multiplier', s.mult)
  from (
    select el.element, t.tier, (t.lvl)::text::integer as level,
      arena_private.spell_multiplier(el.element, p_enemy_element) as mult
    from (
      select key as element, value as tiers
      from jsonb_each(coalesce(p_fighter -> 'spells', '{}'::jsonb))
    ) el,
    lateral (
      select key as tier, value as lvl
      from jsonb_each(el.tiers)
    ) t
  ) s
  where (p_fighter ->> 'kind') = 'witch'
    and s.level > 0
    and s.mult > 0
  order by s.level * s.mult desc, s.mult desc, s.level desc,
    array_position(array['fire', 'water', 'ice', 'wind', 'poison',
      'light', 'shadow', 'dark', 'earth', 'lightning'], s.element)
  limit 1
$$;

-- The Phase 38 random pick is gone: the ranked pick above is
-- the only spell pick now, so nothing is left calling it.
drop function if exists arena_private.spell_pick(jsonb);

-- The sound key for a creature's special (Phase 39): an
-- elemental's magic is its own element's spell sound, the Rival
-- Warlock's curse is his own file, anything else has no magic
-- sound. The Rival Witch is random_spell — her key is picked
-- fresh each cast, so she is not covered here.
create or replace function arena_private.npc_magic_key(
  p_npc_id text, p_element text)
returns text
language sql immutable
set search_path = ''
as $$
  select case
    when p_npc_id = 'rival_warlock' then 'npc_rival_warlock_magic'
    when p_element is not null then 'spell_' || p_element
    else null
  end
$$;

-- The 12 magical creatures (Phase 39): one per element, plus a
-- rival witch and a rival warlock. Multipliers and profiles
-- follow the Phase 24 pattern. The server ability lines speak
-- second person ("Your hit..."), the client lines first person
-- ("My hit...") — the same split as Phase 24.
insert into arena_private.npcs
  (npc_id, name, kind, element, hp_mult, dmg_mult, reward_mult,
   ability, ability_every, ability_line,
   w_speed, w_strength, w_health, w_defense, w_luck)
values
  ('ember_sprite', 'Ember Sprite', 'magical', 'fire', 0.9, 1.25, 1.2,
   'flare', 3, 'Ember Sprite bursts into flame!',
   3, 3, 2, 1, 1),
  ('tide_wisp', 'Tide Wisp', 'magical', 'water', 1.1, 1.0, 1.2,
   'sugar_trap', 4, 'Tide Wisp soaks you! Your next hit is weak!',
   2, 2, 3, 2, 1),
  ('frost_faerie', 'Frost Faerie', 'magical', 'ice', 0.8, 1.2, 1.2,
   'shock', 3, 'Frost Faerie freezes the air! A freezing shock!',
   4, 3, 1, 0, 2),
  ('gale_sylph', 'Gale Sylph', 'magical', 'wind', 0.8, 1.2, 1.2,
   'dodge', 5, 'Gale Sylph swoops aside! Your hit misses!',
   4, 3, 1, 0, 2),
  ('bog_toad', 'Bog Toad', 'magical', 'poison', 1.3, 0.95, 1.1,
   'shock', 3, 'Bog Toad bursts with poison!',
   1, 2, 4, 2, 1),
  ('dawn_moth', 'Dawn Moth', 'magical', 'light', 0.75, 1.3, 1.2,
   'double_hit', 4, 'Dawn Moth flutters in twice!',
   4, 3, 1, 1, 1),
  ('shade_stalker', 'Shade Stalker', 'magical', 'shadow', 0.8, 1.2, 1.2,
   'vanish', 3, 'Shade Stalker melts into shadow! Your hit misses!',
   4, 3, 1, 0, 2),
  ('void_imp', 'Void Imp', 'magical', 'dark', 0.9, 1.25, 1.2,
   'flare', 3, 'Void Imp bursts with void energy!',
   3, 3, 2, 1, 1),
  ('pebble_golem', 'Pebble Golem', 'magical', 'earth', 1.8, 0.7, 1.1,
   'shield', 4, 'Pebble Golem raises a stone shield! Your hit bounces off!',
   1, 1, 4, 3, 1),
  ('storm_roc', 'Storm Roc', 'magical', 'lightning', 0.9, 1.25, 1.2,
   'shock', 3, 'Storm Roc crackles with storm! A shock!',
   4, 3, 1, 0, 2),
  ('rival_witch', 'Rival Witch', 'witch', 'witch', 1.0, 1.1, 1.3,
   'random_spell', 4, 'The Rival Witch casts a spell!',
   2, 3, 2, 2, 1),
  ('rival_warlock', 'Rival Warlock', 'witch', 'witch', 1.0, 1.1, 1.3,
   'sugar_trap', 4, 'The Rival Warlock curses you! Your next hit is weak!',
   2, 3, 2, 2, 1)
on conflict (npc_id) do nothing;

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
  -- Witch spells (Phase 38/39): the spell cast on this hit,
  -- if any, the extra damage its level adds, and its affinity
  -- against the enemy's element. The Scrap Rat has no element,
  -- so every affinity is neutral.
  v_spell jsonb;
  v_spell_bonus integer := 0;
  v_spell_mult numeric := 1;
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
          -- A witch with learned spells casts the BEST one she
          -- has against this enemy (Phase 39, ranked pick):
          -- the spell's level adds damage, its affinity
          -- against the enemy's element multiplies the whole
          -- hit, and its cast line is spoken before the hit
          -- line. A witch with nothing learned yet — or
          -- nothing that does any damage here — hits with the
          -- wand only, no cast line, no bonus. The Scrap Rat
          -- has no element, so the pick ranks by level alone.
          v_spell := arena_private.spell_pick_best(f, null);
          if v_spell is not null then
            v_spell_bonus := (v_spell ->> 'level')::integer * 2 - 2;
            v_spell_mult := (v_spell ->> 'multiplier')::numeric;
          else
            v_spell_bonus := 0;
            v_spell_mult := 1;
          end if;
          hit := round((dmg + v_spell_bonus + floor(random() * 4)::integer) * v_spell_mult)::integer;
          v_crit := random() * 100 < f_crit;
          if v_crit then
            hit := round(hit * 1.5)::integer;
          end if;
          hit := greatest(1, hit - c_soak);
          hit := least(hit, floor(0.75 * c_max_hp)::integer);
          if v_spell is not null then
            lines := lines || to_jsonb(
              arena_private.spell_cast_line(v_spell ->> 'element'));
          end if;
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
  -- Witch spells (Phase 38/39): the spell cast on this hit,
  -- if any, the extra damage its level adds, and its affinity
  -- against the creature's element (n.element: null for the
  -- Scrap Rat and the 9 Phase 24 creatures, so neutral).
  v_spell jsonb;
  v_spell_bonus integer := 0;
  v_spell_mult numeric := 1;
  -- The creature's magic (Phase 39): line index -> sound key
  -- for the rounds the creature's special fired, so the
  -- client plays the magic sound for exactly those lines.
  v_magic jsonb := '{}'::jsonb;
  v_magic_key text;
  v_magic_element text;
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
          -- The block IS the magic that round, so the ability
          -- line carries the magic sound (a Phase 24 creature
          -- has no magic sound, so nothing is recorded).
          v_magic_key := arena_private.npc_magic_key(n.npc_id, n.element);
          if v_magic_key is not null then
            v_magic := v_magic || jsonb_build_object(
              jsonb_array_length(lines)::text, v_magic_key);
          end if;
          lines := lines || to_jsonb(format(
            'Round %s: %s', round_no, n.ability_line));
        elsif random() * 100 < c_dodge then
          lines := lines || to_jsonb(format(
            'Round %s: The %s dodges! My hit misses.', round_no, n.name));
        else
          -- A witch with learned spells casts the BEST one she
          -- has against this creature (Phase 39, ranked pick):
          -- the spell's level adds damage, its affinity
          -- against the creature's element (n.element)
          -- multiplies the whole hit, and its cast line is
          -- spoken before the hit line. A witch with nothing
          -- learned yet — or nothing that does any damage
          -- against this creature — hits with the wand only,
          -- no cast line, no bonus.
          v_spell := arena_private.spell_pick_best(f, n.element);
          if v_spell is not null then
            v_spell_bonus := (v_spell ->> 'level')::integer * 2 - 2;
            v_spell_mult := (v_spell ->> 'multiplier')::numeric;
          else
            v_spell_bonus := 0;
            v_spell_mult := 1;
          end if;
          hit := round((dmg + v_spell_bonus + floor(random() * 4)::integer) * v_spell_mult)::integer;
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
          if v_spell is not null then
            lines := lines || to_jsonb(
              arena_private.spell_cast_line(v_spell ->> 'element'));
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
        if v_ability_round and v_ability in ('flare', 'shock', 'random_spell') then
          -- A burst of flame / a shock / a random elemental
          -- spell (Rival Witch, Phase 39): this round's hit
          -- deals half as much again, before the fighter's
          -- armor soaks some of it. No crit on top: the burst
          -- is the excitement that round. The hit IS the
          -- magic, so the magic sound goes on the hit line
          -- that follows — an elemental's magic is its own
          -- element's spell sound, the Rival Witch's is a
          -- random spell sound each cast. A Phase 24 creature
          -- has no magic sound, so nothing is recorded.
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
            if v_ability = 'random_spell' then
              v_magic_element := (array['fire', 'water', 'ice', 'wind',
                'poison', 'light', 'shadow', 'dark', 'earth',
                'lightning'])[1 + floor(random() * 10)::integer];
              v_magic := v_magic || jsonb_build_object(
                (jsonb_array_length(lines) - 1)::text,
                'spell_' || v_magic_element);
            else
              v_magic_key := arena_private.npc_magic_key(n.npc_id, n.element);
              if v_magic_key is not null then
                v_magic := v_magic || jsonb_build_object(
                  (jsonb_array_length(lines) - 1)::text, v_magic_key);
              end if;
            end if;
          end if;
        elsif v_ability_round and v_ability = 'sugar_trap' then
          -- A sticky trap: the fighter's NEXT hit deals only
          -- half damage. The creature still hits this round.
          -- The trap is the magic that round, so the ability
          -- line carries the magic sound; the hit after it is
          -- an ordinary hit.
          v_magic_key := arena_private.npc_magic_key(n.npc_id, n.element);
          if v_magic_key is not null then
            v_magic := v_magic || jsonb_build_object(
              jsonb_array_length(lines)::text, v_magic_key);
          end if;
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
          -- creature's normal damage. The double hit is the
          -- magic: the ability line carries the magic sound,
          -- the two hits after it sound like ordinary hits.
          v_magic_key := arena_private.npc_magic_key(n.npc_id, n.element);
          if v_magic_key is not null then
            v_magic := v_magic || jsonb_build_object(
              jsonb_array_length(lines)::text, v_magic_key);
          end if;
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
      -- of its max health, if it is still standing. The
      -- repair is the magic that round.
      v_healed := greatest(1, round(0.15 * c_max_hp)::integer);
      c_hp := least(c_max_hp, c_hp + v_healed);
      v_magic_key := arena_private.npc_magic_key(n.npc_id, n.element);
      if v_magic_key is not null then
        v_magic := v_magic || jsonb_build_object(
          jsonb_array_length(lines)::text, v_magic_key);
      end if;
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
    'creature_magic', v_magic,
    'xp', xp_gain,
    'credits', cr_gain,
    'levels_gained', gained,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username));
end;
$$;
revoke all on function public.arena_fight(text, text) from public;
revoke all on function public.arena_fight_npc(text, text) from public;
grant execute on function public.arena_fight(text, text) to anon, authenticated;
grant execute on function public.arena_fight_npc(text, text) to anon, authenticated;
