-- Phase 38: the witch study (2026-11-25, Makenna, voice call).
--
-- A witch or warlock goes to the study to learn elemental spells.
-- At first she fights wand-only; once spells are learned, fights
-- use them more than the wand, the wand only backup. Every spell
-- starts at level 1 and can be upgraded infinitely, one level at
-- a time, to do more damage: a cast spell adds +2 damage per level
-- above 1 (level 1 is flavour only — cast line and sound, no extra
-- damage). Costs and times are a PROPOSAL for Makenna to tune:
-- common 25 credits / 15 minutes, uncommon 50 / 30, rare 100 / 60,
-- epic 200 / 120, legendary 400 / 240 (the 4-hour cap). A tier
-- needs the tier below it in the same element learned first.
--
-- Learning acts like quests, NOT like repairs or upgrades: the
-- clock only ticks while the player is in the study. Leaving the
-- study freezes the remaining time (arena_study_pause), coming
-- back resumes it (arena_study_start on the same spell). The
-- server never completes a study on its own — apply_timers leaves
-- it alone — and the game calls arena_study_complete when its time
-- is up in the study. One spell at a time, no cancelling, like
-- upgrades. Only a witch or warlock can learn spells (a proposal;
-- Makenna can open it later) — the study quests are open to all.
--
-- Also in this phase: the four witch quest givers (Hazel, Rowan,
-- Wren, Bram) join the hangout with their voices and six quest
-- seeds, the study music track and the three new ambience loops
-- are wired in on the client, and arena_fight / arena_fight_npc
-- cast a random learned spell per hit, with its cast line.
--
-- Follows supabase/README.md: a new file, no old migration edited.
-- Each function below is redefined from its LATEST version, so
-- nothing is reverted: new_fighter and arena_switch_kind from
-- Phase 36, arena_fight and arena_fight_npc from Phase 35,
-- quest_new and quest_board_ensure from Phase 26, quest_giver_voice
-- from Phase 27, quest_giver_gender from the quest migration.
-- Old fighters keep working: missing spells mean nothing learned,
-- missing study means nothing learning, and every new read uses
-- coalesce, never a direct read (the compatibility rule).
-- Kiro's password sign-in, auto-login and anti-cheat are untouched.
-- The magical fight creatures (Makenna, Nov 25, 2026) are NOT in
-- this phase — they are the next piece after the study.


-- ---------------------------------------------------------------
-- Spell helpers (private, Phase 38). The spell names, costs,
-- times and cast lines live in spells.py too: the two copies
-- must stay word-for-word the same, or a fight would sound
-- different online and off.
-- ---------------------------------------------------------------

create or replace function arena_private.spell_name(
  p_element text, p_tier text)
returns text
language sql immutable
set search_path = ''
as $$
  select (case p_element
    when 'fire' then array['Ember Spark', 'Flame Lash', 'Burning Veil', 'Inferno Roar', 'Phoenix Rebirth']
    when 'water' then array['Splash', 'Tide Pull', 'Rushing Torrent', 'Deep Current', 'Ocean''s Wrath']
    when 'ice' then array['Frost Bite', 'Ice Shard', 'Frozen Hold', 'Blizzard Veil', 'Eternal Winter']
    when 'wind' then array['Breeze Cut', 'Gale Rush', 'Storm Gust', 'Cyclone Dance', 'Skybreaker Tempest']
    when 'poison' then array['Sting', 'Venom Drip', 'Toxic Cloud', 'Plague Bloom', 'Thorned Doom']
    when 'light' then array['Glow', 'Sunbeam', 'Radiant Shield', 'Dawn Burst', 'Heaven''s Light']
    when 'shadow' then array['Shade Touch', 'Dark Whisper', 'Shadow Bind', 'Nightmare Veil', 'Eclipse']
    when 'dark' then array['Gloom Bolt', 'Midnight Coil', 'Abyss Call', 'Void Rend', 'Oblivion']
    when 'earth' then array['Pebble Toss', 'Stone Grip', 'Rockslide', 'Mountain Roar', 'Titan''s Awakening']
    when 'lightning' then array['Static Zap', 'Spark Chain', 'Thunder Crack', 'Storm Surge', 'Tempest Crown']
    else null end)
    [case p_tier
      when 'common' then 1 when 'uncommon' then 2 when 'rare' then 3
      when 'epic' then 4 when 'legendary' then 5 else null end]
$$;

create or replace function arena_private.spell_cost(p_tier text)
returns integer
language sql immutable
set search_path = ''
as $$
  select case p_tier
    when 'common' then 25 when 'uncommon' then 50 when 'rare' then 100
    when 'epic' then 200 when 'legendary' then 400 else null end
$$;

create or replace function arena_private.spell_seconds(p_tier text)
returns integer
language sql immutable
set search_path = ''
as $$
  select least(case p_tier
    when 'common' then 15 * 60 when 'uncommon' then 30 * 60
    when 'rare' then 60 * 60 when 'epic' then 120 * 60
    when 'legendary' then 240 * 60 else null end, 4 * 3600)
$$;

create or replace function arena_private.spell_tier_index(p_tier text)
returns integer
language sql immutable
set search_path = ''
as $$
  select case p_tier
    when 'common' then 0 when 'uncommon' then 1 when 'rare' then 2
    when 'epic' then 3 when 'legendary' then 4 else -1 end
$$;

create or replace function arena_private.spell_level(
  p_fighter jsonb, p_element text, p_tier text)
returns integer
language sql immutable
set search_path = ''
as $$
  select coalesce(
    (p_fighter -> 'spells' -> p_element ->> p_tier)::integer, 0)
$$;

create or replace function arena_private.spell_cast_line(p_element text)
returns text
language sql immutable
set search_path = ''
as $$
  select case p_element
    when 'fire' then 'I call the fire, and it bursts from my wand!'
    when 'water' then 'I call the water, and it rushes where I point!'
    when 'ice' then 'I call the ice, and the air turns sharp and cold!'
    when 'wind' then 'I call the wind, and it howls around me!'
    when 'poison' then 'I brew the poison, and it curls through the air!'
    when 'light' then 'I call the light, and it shines too bright to face!'
    when 'shadow' then 'I call the shadows, and they gather at my side!'
    when 'dark' then 'I call the dark, and it drinks the light away!'
    when 'earth' then 'I call the earth, and the ground answers me!'
    when 'lightning' then 'I call the lightning, and the sky cracks open!'
    else null end
$$;

-- Pick one learned spell at random for a fight hit. Every
-- learned spell has the same chance, whatever its level.
-- Null when nothing is learned yet, or when the fighter is
-- not a witch at all — a robot or chef never casts.
create or replace function arena_private.spell_pick(p_fighter jsonb)
returns jsonb
language sql stable
set search_path = ''
as $$
  select jsonb_build_object(
    'element', s.element, 'tier', s.tier,
    'name', arena_private.spell_name(s.element, s.tier),
    'level', s.level)
  from (
    select el.element, t.tier, (t.lvl)::text::integer as level
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
  order by random()
  limit 1
$$;

-- new_fighter, redefined from Phase 36: brand-new fighters
-- start with no spells learned and nothing being learned.
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
    'kind_switches', 0,
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
    'quests_gift_pending', null,
    'spells', '{}'::jsonb,
    'study', null
  )
$$;

create or replace function arena_private.quest_giver_voice(p_name text)
returns text
language sql immutable
set search_path = ''
as $$
  select case p_name
    when 'Bolt' then 'en-US-ChristopherNeural'
    when 'Marge' then 'en-US-JennyNeural'
    when 'Pip' then 'en-US-EricNeural'
    when 'Dot' then 'en-US-MichelleNeural'
    when 'Gus' then 'en-US-AndrewNeural'
    when 'Belle' then 'en-US-EmmaNeural'
    when 'Hazel' then 'en-US-AvaNeural'
    when 'Rowan' then 'en-US-RogerNeural'
    when 'Wren' then 'en-US-AnaNeural'
    when 'Bram' then 'en-US-SteffanNeural'
    else 'en-US-ChristopherNeural'
  end
$$;

create or replace function arena_private.quest_giver_gender(p_name text)
returns text
language sql immutable
set search_path = ''
as $$
  select case p_name
    when 'Marge' then 'female'
    when 'Dot' then 'female'
    when 'Belle' then 'female'
    when 'Hazel' then 'female'
    when 'Wren' then 'female'
    else 'male'
  end
$$;

create or replace function arena_private.quest_new(
  p_board jsonb, p_done jsonb, p_difficulty text,
  p_coop_allowed boolean, p_giver text default null,
  p_quest_level integer default 1)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  v_names text[] := array[
    'Scrap Run', 'Tune-Up Time', 'Calm the Haywire Drone',
    'The Great Oil Spill', 'Market Run', 'Perfect the Recipe',
    'Rescue the Burnt Dish', 'The Midnight Feast',
    'The Robot Who Wanted Soup', 'Chef''s New Helper',
    'The Broken Oven and the Broken Bot', 'The Grand Hangout Fair',
    'Gather Moonpetal', 'Brew the Calming Draught',
    'Calm the Storm', 'Charge the Moonstone',
    'Mend the Shadow', 'The Witch''s Fair'];
  v_diffs text[] := array[
    'Easy', 'Easy', 'Medium', 'Hard', 'Easy', 'Medium',
    'Medium', 'Hard', 'Easy', 'Medium', 'Hard', 'Hard',
    'Easy', 'Medium', 'Medium', 'Easy', 'Hard', 'Hard'];
  v_givers text[] := array[
    'Bolt', 'Pip', 'Dot', 'Bolt', 'Marge', 'Belle',
    'Gus', 'Marge', 'Belle', 'Gus', 'Dot', 'Marge',
    'Hazel', 'Hazel', 'Rowan', 'Wren', 'Bram', 'Hazel'];
  v_descs text[] := array[
    'The workshop is out of scrap. Fetch three pieces from the scrap yard.',
    'A servo is squeaky. Tune it until it hums right.',
    'A little drone is spinning in circles and beeping in panic. Talk it down.',
    'Somebody knocked over the big oil drum. Clean the workshop floor before anyone slips.',
    'The kitchen needs three ingredients for tonight''s soup. Go to the market and fetch them.',
    'A cake keeps coming out flat. Taste it and tell the baker what it needs.',
    'A pan was left on too long. Save dinner before the smoke alarm goes off.',
    'Cook a whole feast for the hangout tonight: soup, main, and dessert, all from scratch.',
    'A robot has never tasted soup. Make him a bowl he can actually enjoy.',
    'A chef needs a spare pair of hands. Lend him your servo arm for the afternoon.',
    'The kitchen oven died, and a repair robot is stuck in a loop. Fix them both.',
    'The whole hangout is holding a fair. Robots and chefs, everyone working together, one big day.',
    'Fetch three moonpetal leaves before dawn.',
    'Pick the right herbs in the right order for a calming draught. A wrong herb just gets a kind word and another try.',
    'Talk a little storm cloud down before it soaks the hangout.',
    'Hold the moonstone steady in the moonlight until it glows.',
    'A shadow has torn loose and is frightening the drones. Stitch it back gently, in three steps.',
    'The whole hangout holds a witch fair — potion stall, herb stall, and fortune stall — like the Grand Hangout Fair, full reward for everyone who joins.'];
  v_tasks text[] := array[
    'Fetch', 'Fix', 'Cook', 'Calm', 'Deliver', 'Teach',
    'Clean', 'Rescue', 'Tune', 'Taste', 'Build', 'Find'];
  v_items text[] := array[
    'a copper coil', 'a brass bolt', 'a bent spring',
    'a cracked gear', 'carrots', 'noodles', 'a spice jar',
    'a soup pot', 'a mop', 'a rag', 'a bucket',
    'a heating coil', 'a new dial', 'a cake', 'a pan',
    'a servo arm', 'a spare part', 'a recipe card',
    'a basket of bread', 'a jar of honey'];
  v_places text[] := array[
    'the workshop', 'the kitchen', 'the scrap yard',
    'the market', 'the hangout', 'the garden',
    'the pantry', 'the tool shed'];
  v_helpers text[] := array[
    'Zip Scout', 'Bulkhead', 'Mend-O-Matic', 'Ghost Drone',
    'Chop-Chop Chef', 'Grill Master Gus', 'Baker Belle',
    'Zap Fox', 'Ember Owl', 'Scrap Rat'];
  v_seen jsonb := coalesce(p_board, '[]'::jsonb)
    || coalesce(p_done, '[]'::jsonb);
  v_try integer;
  v_i integer;
  v_giver text;
  v_id text;
  v_minutes integer;
  v_coop boolean;
  v_factor double precision
    := 1 + 0.1 * (greatest(1, p_quest_level) - 1);
  v_low integer;
  v_high integer;
begin
  for v_try in 1..100 loop
    v_i := 1 + floor(random() * 18)::integer;
    if p_difficulty is not null and v_diffs[v_i] <> p_difficulty then
      continue;
    end if;
    -- A template name already on the board is never dealt
    -- twice on the same board.
    if exists (select 1 from jsonb_array_elements(coalesce(p_board, '[]'::jsonb)) q
               where q ->> 'name' = v_names[v_i]) then
      continue;
    end if;
    v_coop := (v_names[v_i] in ('The Grand Hangout Fair', 'The Witch''s Fair'));
    if v_coop and not p_coop_allowed then
      continue;
    end if;
    v_giver := coalesce(p_giver, v_givers[v_i]);
    v_id := 'q_' || lower(replace(v_names[v_i], ' ', '_'))
      || '_' || floor(random() * 900000 + 100000)::text;
    if v_seen @> to_jsonb(v_id) then
      continue;
    end if;
    -- Durations grow with the quest level (Phase 26): the
    -- base range is multiplied by (1 + 0.1 x (quest level
    -- - 1)), capped at 240 minutes (4 hours). At quest
    -- level 1 the factor is 1, so the ranges are exactly
    -- as before: Easy 5-15, Medium 15-45, Hard 60-240.
    v_low := least(240, floor(case v_diffs[v_i]
      when 'Easy' then 5 when 'Medium' then 15 else 60 end
      * v_factor)::integer);
    v_high := least(240, floor(case v_diffs[v_i]
      when 'Easy' then 15 when 'Medium' then 45 else 240 end
      * v_factor)::integer);
    v_minutes := v_low
      + floor(random() * (v_high - v_low + 1))::integer;
    return jsonb_build_object(
      'id', v_id,
      'name', v_names[v_i],
      'description', v_tasks[1 + floor(random() * 12)::integer]
        || ' ' || v_helpers[1 + floor(random() * 10)::integer]
        || ' needs ' || v_items[1 + floor(random() * 20)::integer]
        || ' in ' || v_places[1 + floor(random() * 8)::integer]
        || '. ' || v_descs[v_i],
      'giver', v_giver,
      'giver_voice', arena_private.quest_giver_voice(v_giver),
      'giver_gender', arena_private.quest_giver_gender(v_giver),
      'difficulty', v_diffs[v_i],
      'duration_minutes', v_minutes,
      'coop', v_coop);
  end loop;
  raise exception 'could not deal a fresh quest';
end;
$$;

-- Make sure the fighter has a starting board of 5 (2 Easy,
-- 2 Medium, 1 Hard), dealing one when there is none yet.
-- Givers are dealt in a shuffled order from all ten, so the
-- board always holds both male and female givers — five male,
-- five female in the full set. Every giver can land in slot 1:
-- the Belle rule (Makenna, Nov 25, 2026). The board is dealt
-- at the fighter's quest level (Phase 26), so its durations
-- grow with it.
create or replace function arena_private.quest_board_ensure(
  p_fighter jsonb)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  f jsonb := p_fighter;
  v_board jsonb := coalesce(f -> 'quests_board', '[]'::jsonb);
  v_done jsonb := coalesce(f -> 'quests_done', '[]'::jsonb);
  v_givers text[];
  v_diffs text[] := array['Easy', 'Easy', 'Medium', 'Medium', 'Hard'];
  v_i integer;
  v_quest jsonb;
  v_coop boolean;
  v_qlevel integer := coalesce((p_fighter ->> 'quest_level')::integer, 1);
begin
  if jsonb_typeof(v_board) = 'array' and jsonb_array_length(v_board) > 0 then
    return f;
  end if;
  select array_agg(g) into v_givers
  from (select unnest(array['Bolt', 'Marge', 'Pip', 'Dot', 'Gus', 'Belle', 'Hazel', 'Rowan', 'Wren', 'Bram']) as g
        order by random()) s;
  v_board := '[]'::jsonb;
  for v_i in 1..5 loop
    v_coop := not exists (
      select 1 from jsonb_array_elements(v_board) q
      where coalesce((q ->> 'coop')::boolean, false));
    v_quest := arena_private.quest_new(
      v_board, v_done, v_diffs[v_i], v_coop, v_givers[v_i], v_qlevel);
    v_board := v_board || v_quest;
  end loop;
  f := f || jsonb_build_object('quests_board', v_board);
  return f;
end;
$$;

-- ---------------------------------------------------------------
-- The study (Phase 38): start, pause and complete learning.
-- The clock only ticks while the player is in the study — the
-- quest pause/resume pattern (Phase 22), not the upgrade
-- pattern: leaving the study freezes the remaining time, and
-- coming back resumes it. Repairs and upgrades keep ticking;
-- study learning does not. The server never completes a study
-- on its own: apply_timers leaves it alone, and the game calls
-- arena_study_complete when its time is up in the study.
-- ---------------------------------------------------------------

create or replace function public.arena_study_start(
  p_token text, p_element text, p_tier text)
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
  v_element text := lower(btrim(coalesce(p_element, '')));
  v_tier text := lower(btrim(coalesce(p_tier, '')));
  v_study jsonb;
  v_level integer;
  v_cost integer;
  v_credits numeric;
  v_name text;
  v_remaining double precision;
  v_below text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if v_element not in ('fire', 'water', 'ice', 'wind', 'poison',
      'light', 'shadow', 'dark', 'earth', 'lightning') then
    return jsonb_build_object('error', 'I do not know that spell.');
  end if;
  if v_tier not in ('common', 'uncommon', 'rare', 'epic', 'legendary') then
    return jsonb_build_object('error', 'I do not know that spell.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  if coalesce(f ->> 'kind', 'robot') <> 'witch' then
    -- Only a witch or warlock can learn spells (a proposal
    -- from this build; Makenna can open it later). The study
    -- quests are open to everyone — only the learning is
    -- witch-only.
    return jsonb_build_object(
      'error', 'The study teaches spells, and only a witch or warlock can learn them.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  -- A tier needs the tier below it in the same element
  -- learned first; common has no prerequisite.
  if arena_private.spell_tier_index(v_tier) > 0 then
    v_below := (array['common', 'uncommon', 'rare', 'epic'])
      [arena_private.spell_tier_index(v_tier)];
    if arena_private.spell_level(f, v_element, v_below) <= 0 then
      return jsonb_build_object(
        'error', format('I need to learn %s first, before I can learn %s.',
          arena_private.spell_name(v_element, v_below),
          arena_private.spell_name(v_element, v_tier)),
        'messages', t.messages,
        'fighter', arena_private.fighter_out(f, r.player_code, r.username));
    end if;
  end if;
  v_study := f -> 'study';
  if v_study is not null and jsonb_typeof(v_study) = 'object' then
    if v_study ->> 'element' = v_element
       and v_study ->> 'tier' = v_tier
       and coalesce((v_study ->> 'paused')::boolean, false) then
      -- Resume the same paused spell: same remaining time,
      -- no second charge (the quest resume pattern).
      v_remaining := greatest(0,
        coalesce((v_study ->> 'remaining_seconds')::double precision,
                 (v_study ->> 'finish_at')::double precision - v_now));
      v_study := (v_study - 'remaining_seconds')
        || jsonb_build_object(
          'finish_at', v_now + v_remaining,
          'paused', false);
      f := f || jsonb_build_object('study', v_study);
      update arena_private.players
      set fighter = f, updated_at = now()
      where player_code = v_code;
      return jsonb_build_object(
        'message', format('I picked up learning %s again, %s left.',
          v_study ->> 'name',
          arena_private.format_time(v_remaining)),
        'messages', t.messages,
        'fighter', arena_private.fighter_out(f, r.player_code, r.username),
        'study', v_study);
    end if;
    return jsonb_build_object(
      'error', format('I am already learning %s. Finish it first, in the study.',
        v_study ->> 'name'),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_level := arena_private.spell_level(f, v_element, v_tier);
  v_cost := arena_private.spell_cost(v_tier);
  v_credits := arena_private.credits_of(f);
  if v_credits < v_cost then
    return jsonb_build_object(
      'error', format('Learning %s costs %s credits and I have %s credits.',
        arena_private.spell_name(v_element, v_tier), v_cost, v_credits),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_name := arena_private.spell_name(v_element, v_tier);
  f := f || jsonb_build_object(
    'credits', v_credits - v_cost,
    'study', jsonb_build_object(
      'element', v_element,
      'tier', v_tier,
      'name', v_name,
      'level', v_level + 1,
      'finish_at', v_now + arena_private.spell_seconds(v_tier),
      'paused', false,
      'remaining_seconds', 0));
  f := f - 'points';
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'study_started',
    jsonb_build_object('element', v_element, 'tier', v_tier,
                       'level', v_level + 1, 'cost', v_cost), 'server');
  return jsonb_build_object(
    'message', format('I started learning %s. It will take %s.',
      v_name, arena_private.format_time(arena_private.spell_seconds(v_tier))),
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'study', f -> 'study');
end;
$$;

create or replace function public.arena_study_pause(p_token text)
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
  v_study jsonb;
  v_remaining double precision;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_study := f -> 'study';
  if v_study is null or jsonb_typeof(v_study) <> 'object' then
    -- Nothing learning: nothing to freeze.
    return jsonb_build_object(
      'fighter', arena_private.fighter_out(f, r.player_code, r.username),
      'study', null);
  end if;
  if coalesce((v_study ->> 'paused')::boolean, false) then
    -- Already paused: the frozen time stands.
    return jsonb_build_object(
      'fighter', arena_private.fighter_out(f, r.player_code, r.username),
      'study', v_study,
      'remaining_seconds',
        coalesce((v_study ->> 'remaining_seconds')::double precision, 0));
  end if;
  v_remaining := greatest(0,
    (v_study ->> 'finish_at')::double precision - v_now);
  v_study := v_study || jsonb_build_object(
    'paused', true,
    'remaining_seconds', v_remaining);
  f := f || jsonb_build_object('study', v_study);
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'study', v_study,
    'remaining_seconds', v_remaining);
end;
$$;

create or replace function public.arena_study_complete(p_token text)
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
  v_study jsonb;
  v_element text;
  v_tier text;
  v_level integer;
  v_name text;
  v_spells jsonb;
  v_tiers jsonb;
  v_message text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_study := f -> 'study';
  if v_study is null or jsonb_typeof(v_study) <> 'object' then
    return jsonb_build_object(
      'error', 'I am not learning a spell right now.',
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  if coalesce((v_study ->> 'paused')::boolean, false) then
    -- A paused study never completes while its clock is
    -- frozen — unless its frozen time is already zero.
    if coalesce((v_study ->> 'remaining_seconds')::double precision, 0) > 0 then
      return jsonb_build_object('error', format(
        'That spell is paused. About %s left.',
        arena_private.format_time(
          (v_study ->> 'remaining_seconds')::double precision)),
        'messages', t.messages,
        'fighter', arena_private.fighter_out(f, r.player_code, r.username));
    end if;
  elsif (v_study ->> 'finish_at')::double precision > v_now then
    return jsonb_build_object('error', format(
      'That spell is not learned yet. About %s left.',
      arena_private.format_time(
        (v_study ->> 'finish_at')::double precision - v_now)),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_element := v_study ->> 'element';
  v_tier := v_study ->> 'tier';
  v_level := coalesce((v_study ->> 'level')::integer, 1);
  v_name := coalesce(v_study ->> 'name',
    arena_private.spell_name(v_element, v_tier));
  v_spells := coalesce(f -> 'spells', '{}'::jsonb);
  v_tiers := coalesce(v_spells -> v_element, '{}'::jsonb);
  v_tiers := v_tiers || jsonb_build_object(
    v_tier, greatest(
      coalesce((v_tiers ->> v_tier)::integer, 0), v_level));
  v_spells := v_spells || jsonb_build_object(v_element, v_tiers);
  f := (f || jsonb_build_object('spells', v_spells))
       || jsonb_build_object('study', null);
  if v_level <= 1 then
    v_message := format(
      'I learned %s! It is level 1. My spells hit a little harder as they level up.',
      v_name);
  else
    v_message := format('My %s is now level %s.', v_name, v_level);
  end if;
  update arena_private.players set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'study_completed',
    jsonb_build_object('element', v_element, 'tier', v_tier,
                       'level', v_level), 'server');
  return jsonb_build_object(
    'message', v_message,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'spell', jsonb_build_object(
      'element', v_element, 'tier', v_tier,
      'name', v_name, 'level', v_level));
end;
$$;

-- ---------------------------------------------------------------
-- Study quests: deal one fresh quest from a witch giver
-- (Hazel, Rowan, Wren, Bram) for the study loop. The study and
-- the hangout share one board and one active quest — a quest is
-- a quest — so this only deals from a witch giver; starting,
-- pausing and completing it are the ordinary quest functions.
-- ---------------------------------------------------------------

create or replace function public.arena_new_study_quest(p_token text)
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
  v_board jsonb;
  v_done jsonb;
  v_coop boolean;
  v_roll double precision;
  v_diff text;
  v_giver text;
  v_quest jsonb;
  v_qlevel integer;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := arena_private.quest_board_ensure(t.fighter);
  v_board := coalesce(f -> 'quests_board', '[]'::jsonb);
  v_done := coalesce(f -> 'quests_done', '[]'::jsonb);
  v_coop := not exists (
    select 1 from jsonb_array_elements(v_board) q
    where coalesce((q ->> 'coop')::boolean, false));
  v_roll := random();
  v_diff := case when v_roll < 0.4 then 'Easy'
    when v_roll < 0.8 then 'Medium' else 'Hard' end;
  v_qlevel := coalesce((f ->> 'quest_level')::integer, 1);
  -- A random witch giver: Hazel, Rowan, Wren or Bram. The
  -- quest itself comes from that giver's templates, so a
  -- study quest always sounds like a witch's errand.
  v_giver := (array['Hazel', 'Rowan', 'Wren', 'Bram'])
    [1 + floor(random() * 4)::integer];
  v_quest := arena_private.quest_new(
    v_board, v_done, v_diff, v_coop, v_giver, v_qlevel);
  f := f || jsonb_build_object(
    'quests_board', v_board || v_quest);
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'quest_dealt',
    jsonb_build_object('quest', v_quest ->> 'id'), 'server');
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_quest,
    'quests', f -> 'quests_board');
end;
$$;

-- arena_switch_kind, redefined from Phase 36: switching
-- resets learned spells and any study in progress.
create or replace function public.arena_switch_kind(
  p_token text, p_kind text)
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
  v_kind text := lower(btrim(coalesce(p_kind, '')));
  v_old_kind text;
  v_old_word text;
  v_word text;
  v_switches integer;
  v_cost bigint;
  v_next_cost bigint;
  v_credits bigint;
  v_healing integer;
  v_weapon text;
  v_armor text;
  v_message text;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  if v_kind not in ('robot', 'chef', 'witch') then
    return jsonb_build_object('error', 'Pick robot, chef, or witch.');
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_old_kind := coalesce(f ->> 'kind', 'robot');
  v_old_word := case
    when v_old_kind = 'witch'
      and coalesce(f ->> 'gender', 'male') = 'male' then 'warlock'
    when v_old_kind = 'witch' then 'witch'
    else v_old_kind end;
  if v_kind = v_old_kind then
    return jsonb_build_object(
      'error', format('You are already a %s.', v_old_word),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  -- The switch count is missing (0) on fighters made before
  -- this phase: missing means 0, never a crash (compatibility
  -- rule). The first switch is free; after that the first paid
  -- switch is 100 credits and the price doubles every switch,
  -- with no cap.
  v_switches := coalesce((f ->> 'kind_switches')::integer, 0);
  v_cost := case when v_switches <= 0 then 0
    else 100 * (2::bigint ^ (v_switches - 1)) end;
  v_credits := coalesce((f ->> 'credits')::bigint, 0);
  if v_credits < v_cost then
    return jsonb_build_object(
      'error', format(
        'Changing fighter costs %s credits and you have %s credits.',
        v_cost, v_credits),
      'messages', t.messages,
      'fighter', arena_private.fighter_out(f, r.player_code, r.username));
  end if;
  v_healing := coalesce((f ->> 'healing_level')::integer, 0);
  v_weapon := case v_kind
    when 'robot' then 'Laser Blaster'
    when 'chef' then 'Trusty Spatula'
    when 'witch' then 'Spellbound Wand' end;
  v_armor := case v_kind
    when 'robot' then 'Scrap Plating'
    when 'chef' then 'Chef Apron'
    when 'witch' then 'Mystic Robe' end;
  v_word := case
    when v_kind = 'witch'
      and coalesce(f ->> 'gender', 'male') = 'male' then 'warlock'
    when v_kind = 'witch' then 'witch'
    else v_kind end;
  -- The reset (Makenna, Nov 25, 2026): combat level and stats,
  -- quest level and quest stats, reputation with every giver,
  -- weapon and armor upgrades, and any running upgrade or
  -- repair all start over. Healing stays exactly as it is.
  -- Weapon and armor start at level 1 (the fresh weapon with
  -- no upgrades), not level 0. Credits stay apart from the
  -- switch cost; wins, losses, name, gender and voice stay.
  f := f || jsonb_build_object(
    'kind', v_kind,
    'weapon_name', v_weapon, 'weapon_level', 1,
    'armor_name', v_armor, 'armor_level', 1,
    'level', 1, 'xp', 0,
    'stats', '{"strength": 0, "defense": 0, "health": 0, "speed": 0, "luck": 0}'::jsonb,
    'stat_points', 0,
    'hp', 100, 'max_hp', 100,
    'quest_level', 1, 'quest_xp', 0, 'quest_points', 0,
    'quest_stats', '{"charm": 0, "renown": 0, "insight": 0}'::jsonb,
    'quests_rep', '{}'::jsonb,
    'quests_board', '[]'::jsonb,
    'quests_done', '[]'::jsonb,
    'quests_joined', '[]'::jsonb,
    'quests_active', null,
    'quests_gift_pending', null,
    'spells', '{}'::jsonb,
    'study', null,
    'upgrade', null,
    'upgrade_queue', null,
    'upgrade_total', 0,
    'repair_until', 0,
    'credits', v_credits - v_cost,
    'kind_switches', v_switches + 1);
  v_next_cost := 100 * (2::bigint ^ v_switches);
  -- A witch who had learned spells loses them on a switch:
  -- the study starts from zero, like the quest level. The
  -- confirm dialog in the game says so before Yes.
  if coalesce((f -> 'spells'), '{}'::jsonb) <> '{}'::jsonb then
    v_message := format(
      'You are now a %s. Your weapon is the %s and your armor is '
      'the %s. Your Healing stayed at level %s, and your combat '
      'and quest levels started over at level 1. Your spells '
      'started over too — the study begins again. Your next '
      'switch costs %s credits.',
      v_word, v_weapon, v_armor, v_healing, v_next_cost);
  else
    v_message := format(
      'You are now a %s. Your weapon is the %s and your armor is '
      'the %s. Your Healing stayed at level %s, and your combat '
      'and quest levels started over at level 1. Your next switch '
      'costs %s credits.',
      v_word, v_weapon, v_armor, v_healing, v_next_cost);
  end if;
  update arena_private.players
  set fighter = f, kind = v_kind, updated_at = now()
  where player_code = v_code;
  perform arena_private.log_event(v_code, 'fighter_switched',
    jsonb_build_object('from', v_old_kind, 'to', v_kind,
                       'cost', v_cost), 'server');
  return jsonb_build_object(
    'message', v_message,
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'cost', v_cost,
    'next_cost', v_next_cost,
    'switches', v_switches + 1);
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
  -- Witch spells (Phase 38): the spell cast on this hit, if any,
  -- and the extra damage its level adds.
  v_spell jsonb;
  v_spell_bonus integer := 0;
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
          -- A witch with learned spells casts one at random for
          -- this hit (Phase 38): the spell's level adds damage,
          -- and its cast line is spoken before the hit line.
          -- A witch with nothing learned yet hits with the wand
          -- only, no cast line, no bonus. spell_pick returns
          -- null for any fighter who is not a witch.
          v_spell := arena_private.spell_pick(f);
          if v_spell is not null then
            v_spell_bonus := (v_spell ->> 'level')::integer * 2 - 2;
          else
            v_spell_bonus := 0;
          end if;
          hit := dmg + v_spell_bonus + floor(random() * 4)::integer;
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
  -- Witch spells (Phase 38): the spell cast on this hit, if any,
  -- and the extra damage its level adds.
  v_spell jsonb;
  v_spell_bonus integer := 0;
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
          -- A witch with learned spells casts one at random for
          -- this hit (Phase 38): the spell's level adds damage,
          -- and its cast line is spoken before the hit line.
          -- A witch with nothing learned yet hits with the wand
          -- only, no cast line, no bonus. spell_pick returns
          -- null for any fighter who is not a witch.
          v_spell := arena_private.spell_pick(f);
          if v_spell is not null then
            v_spell_bonus := (v_spell ->> 'level')::integer * 2 - 2;
          else
            v_spell_bonus := 0;
          end if;
          hit := dmg + v_spell_bonus + floor(random() * 4)::integer;
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
revoke all on function public.arena_study_start(text, text, text) from public;
revoke all on function public.arena_study_pause(text) from public;
revoke all on function public.arena_study_complete(text) from public;
revoke all on function public.arena_new_study_quest(text) from public;
revoke all on function public.arena_fight(text, text) from public;
revoke all on function public.arena_fight_npc(text, text) from public;
revoke all on function public.arena_switch_kind(text, text) from public;
grant execute on function public.arena_study_start(text, text, text) to anon, authenticated;
grant execute on function public.arena_study_pause(text) to anon, authenticated;
grant execute on function public.arena_study_complete(text) to anon, authenticated;
grant execute on function public.arena_new_study_quest(text) to anon, authenticated;
grant execute on function public.arena_fight(text, text) to anon, authenticated;
grant execute on function public.arena_fight_npc(text, text) to anon, authenticated;
grant execute on function public.arena_switch_kind(text, text) to anon, authenticated;
