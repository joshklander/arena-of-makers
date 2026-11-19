-- Hangout quests (Phase 18, 2026-11-18).
--
-- Quests are NOT fights: nobody gets hurt, nobody loses
-- health, and no quest ever turns into a battle. They are
-- jobs, favours and puzzles in the hangout, open to every
-- fighter, robot or chef alike — fighter kind never locks
-- anyone out of a quest. A robot can do chef quests, a chef
-- can do robot quests, and mixed-world quests are open to
-- everyone.
--
-- Six givers, three male and three female, each with their
-- own Edge voice: Bolt (male, Christopher), Marge (female,
-- Jenny), Pip (male, Eric), Dot (female, Michelle), Gus
-- (male, Davis), Belle (female, Sara). The same giver always
-- sounds the same.
--
-- How it works: the game asks for the board, presses Start,
-- and quests run automatically in the hangout loop, one
-- after another, endlessly generated. Pressing Stop stops
-- the loop on the game side; the quest in progress stays
-- saved on the server (started_at / finish_at), and pressing
-- Start again picks it up — it does not restart, and it
-- never completes outside the loop, because only the loop
-- calls arena_complete_quest.
--
-- Rewards, by difficulty and level (Medium pays exactly
-- what a fight win pays; Hard pays double):
--   Easy:   5 + 2 x level credits
--   Medium: 10 + 5 x level credits
--   Hard:   20 + 10 x level credits
-- Durations: Easy 5-15 minutes, Medium 15-45 minutes,
-- Hard 1-4 hours, never over 4 hours.
--
-- Reputation, per giver, +1 each time you finish one of
-- their quests, no cap: 3 = Helper (their quests pay +25%
-- from then on), 8 = Friend (a free weapon OR armor upgrade,
-- your choice, instant — the game asks which one), 15 =
-- Trusted Friend (a free Healing upgrade if you are not
-- already at max Healing level 5, 95%; otherwise another
-- random gift, instant). Gifts are instant: no credits, no
-- time, no queue. The Healing cap is never exceeded.
--
-- The server is the only judge, exactly as for fights: it
-- generates the quests, checks the work, and pays. The game
-- sends only the in-memory session token plus a quest id.
-- arena_complete_quest NEVER checks repairing or
-- repair_until — a fighter mid-repair completes quests and
-- gets paid exactly like a healthy one. That is the whole
-- point of the hangout.
--
-- Co-op: only the Grand Hangout Fair is co-op, full reward
-- per player, at most 1 co-op quest on the board at once.
-- A player only gets paid for it if the server saw them
-- join it (arena_join_quest) and finish their own part.
-- In this first version each joined player does their own
-- stall job (the timed quest) and is paid in full when
-- their part finishes; the fair does not wait for other
-- players to finish theirs.
--
-- New fighters get healing_level 0 and empty quest fields.
-- Older fighters get them on first use (coalesce), so older
-- games keep working: nothing is removed or renamed.

-- ---------------------------------------------------------------
-- Quest helpers (private)
-- ---------------------------------------------------------------

create or replace function arena_private.quest_reward(
  p_difficulty text, p_level integer)
returns integer
language sql immutable
set search_path = ''
as $$
  select case
    when p_difficulty = 'Easy' then 5 + 2 * greatest(1, p_level)
    when p_difficulty = 'Hard' then 20 + 10 * greatest(1, p_level)
    else 10 + 5 * greatest(1, p_level)
  end
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
    when 'Gus' then 'en-US-DavisNeural'
    when 'Belle' then 'en-US-SaraNeural'
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
    else 'male'
  end
$$;

-- Deal one fresh quest. p_difficulty is Easy, Medium or Hard,
-- or null for any. p_coop_allowed is false when a co-op quest
-- is already open on the board, so at most one is ever there.
-- p_giver, when given, is who gives it (used to deal the
-- starting board in a shuffled, mixed order); otherwise the
-- template's own giver gives it. p_seen is the ids already
-- on the board or finished, never dealt again.
create or replace function arena_private.quest_new(
  p_board jsonb, p_done jsonb, p_difficulty text,
  p_coop_allowed boolean, p_giver text default null)
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
    'The Broken Oven and the Broken Bot', 'The Grand Hangout Fair'];
  v_diffs text[] := array[
    'Easy', 'Easy', 'Medium', 'Hard', 'Easy', 'Medium',
    'Medium', 'Hard', 'Easy', 'Medium', 'Hard', 'Hard'];
  v_givers text[] := array[
    'Bolt', 'Pip', 'Dot', 'Bolt', 'Marge', 'Belle',
    'Gus', 'Marge', 'Belle', 'Gus', 'Dot', 'Marge'];
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
    'The whole hangout is holding a fair. Robots and chefs, everyone working together, one big day.'];
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
begin
  for v_try in 1..100 loop
    v_i := 1 + floor(random() * 12)::integer;
    if p_difficulty is not null and v_diffs[v_i] <> p_difficulty then
      continue;
    end if;
    -- A template name already on the board is never dealt
    -- twice on the same board.
    if exists (select 1 from jsonb_array_elements(coalesce(p_board, '[]'::jsonb)) q
               where q ->> 'name' = v_names[v_i]) then
      continue;
    end if;
    v_coop := (v_names[v_i] = 'The Grand Hangout Fair');
    if v_coop and not p_coop_allowed then
      continue;
    end if;
    v_giver := coalesce(p_giver, v_givers[v_i]);
    v_id := 'q_' || lower(replace(v_names[v_i], ' ', '_'))
      || '_' || floor(random() * 900000 + 100000)::text;
    if v_seen @> to_jsonb(v_id) then
      continue;
    end if;
    v_minutes := case v_diffs[v_i]
      when 'Easy' then 5 + floor(random() * 11)::integer
      when 'Medium' then 15 + floor(random() * 31)::integer
      else 60 + floor(random() * 181)::integer
    end;
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
-- Givers are dealt in a shuffled order from all six, so the
-- board always holds both male and female givers. Returns
-- the fighter with the board in place.
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
begin
  if jsonb_typeof(v_board) = 'array' and jsonb_array_length(v_board) > 0 then
    return f;
  end if;
  select array_agg(g) into v_givers
  from (select unnest(array['Bolt', 'Marge', 'Pip', 'Dot', 'Gus', 'Belle']) as g
        order by random()) s;
  v_board := '[]'::jsonb;
  for v_i in 1..5 loop
    v_coop := not exists (
      select 1 from jsonb_array_elements(v_board) q
      where coalesce((q ->> 'coop')::boolean, false));
    v_quest := arena_private.quest_new(
      v_board, v_done, v_diffs[v_i], v_coop, v_givers[v_i]);
    v_board := v_board || v_quest;
  end loop;
  f := f || jsonb_build_object('quests_board', v_board);
  return f;
end;
$$;

-- One quest off the board, by id, or null.
create or replace function arena_private.quest_on_board(
  p_board jsonb, p_quest_id text)
returns jsonb
language sql
set search_path = ''
as $$
  select q from jsonb_array_elements(coalesce(p_board, '[]'::jsonb)) q
  where q ->> 'id' = p_quest_id
  limit 1
$$;

-- The board with one quest id taken off it.
create or replace function arena_private.quest_board_without(
  p_board jsonb, p_quest_id text)
returns jsonb
language sql
set search_path = ''
as $$
  select coalesce(jsonb_agg(q), '[]'::jsonb)
  from jsonb_array_elements(coalesce(p_board, '[]'::jsonb)) q
  where q ->> 'id' <> p_quest_id
$$;

-- New fighters start with empty quest fields and no
-- Healing yet. Same inputs and outputs as before, plus
-- the quest fields and healing_level.
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
    'weapon_name', case when p_kind = 'robot' then 'Laser Blaster' else 'Trusty Spatula' end,
    'weapon_level', 1,
    'armor_name', case when p_kind = 'robot' then 'Scrap Plating' else 'Chef Apron' end,
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

revoke all on all functions in schema arena_private from public, anon, authenticated;

-- ---------------------------------------------------------------
-- Functions the game calls, with the publishable key.
-- ---------------------------------------------------------------

create or replace function public.arena_get_quests(p_token text)
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
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := arena_private.quest_board_ensure(t.fighter);
  if f is distinct from r.fighter then
    update arena_private.players
    set fighter = f, updated_at = now()
    where player_code = v_code;
  end if;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quests', coalesce(f -> 'quests_board', '[]'::jsonb),
    'active', f -> 'quests_active',
    'reputation', coalesce(f -> 'quests_rep', '{}'::jsonb),
    'gift_pending', f -> 'quests_gift_pending',
    'messages', t.messages);
end;
$$;

create or replace function public.arena_new_quest(p_token text)
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
  v_quest jsonb;
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
  v_quest := arena_private.quest_new(v_board, v_done, v_diff, v_coop);
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

create or replace function public.arena_start_quest(
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
  v_joined jsonb;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := arena_private.quest_board_ensure(t.fighter);
  if f is distinct from r.fighter then
    update arena_private.players
    set fighter = f, updated_at = now()
    where player_code = v_code;
  end if;
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
  if v_active is not null and jsonb_typeof(v_active) = 'object' then
    if v_active ->> 'id' = p_quest_id then
      -- Pressing Start again after Stop picks up the saved
      -- quest, it does not restart it: same finish time.
      return jsonb_build_object(
        'fighter', arena_private.fighter_out(f, r.player_code, r.username),
        'quest', v_active);
    end if;
    return jsonb_build_object(
      'error', 'You already have a quest going. Finish it first, or stop quests and start it again.');
  end if;
  if coalesce((v_quest ->> 'coop')::boolean, false) then
    v_joined := coalesce(f -> 'quests_joined', '[]'::jsonb);
    if not (v_joined @> to_jsonb(p_quest_id)) then
      return jsonb_build_object(
        'error', 'Join the Grand Hangout Fair first, then start it.');
    end if;
  end if;
  v_quest := v_quest || jsonb_build_object(
    'started_at', v_now,
    'finish_at', v_now + (v_quest ->> 'duration_minutes')::double precision * 60);
  f := f || jsonb_build_object('quests_active', v_quest);
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_quest);
end;
$$;

create or replace function public.arena_join_quest(
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
  v_board jsonb;
  v_quest jsonb;
  v_joined jsonb;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := arena_private.quest_board_ensure(t.fighter);
  v_board := coalesce(f -> 'quests_board', '[]'::jsonb);
  v_quest := arena_private.quest_on_board(v_board, p_quest_id);
  if v_quest is null then
    return jsonb_build_object('error', 'That quest is not on your board.');
  end if;
  if not coalesce((v_quest ->> 'coop')::boolean, false) then
    return jsonb_build_object(
      'error', 'That quest is solo. You do not need to join it.');
  end if;
  v_joined := coalesce(f -> 'quests_joined', '[]'::jsonb);
  if not (v_joined @> to_jsonb(p_quest_id)) then
    f := f || jsonb_build_object(
      'quests_joined', v_joined || to_jsonb(p_quest_id));
    update arena_private.players
    set fighter = f, updated_at = now()
    where player_code = v_code;
    perform arena_private.log_event(v_code, 'quest_joined',
      jsonb_build_object('quest', p_quest_id), 'server');
  end if;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_quest,
    'message', 'You joined the Grand Hangout Fair. Pick your stall and do your part.');
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
  v_level integer;
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
  if (v_active ->> 'finish_at')::double precision > v_now then
    return jsonb_build_object('error', format(
      'That quest is not done yet. About %s left.',
      arena_private.format_time(
        (v_active ->> 'finish_at')::double precision - v_now)));
  end if;
  -- Never check repairing or repair_until here. A fighter
  -- mid-repair completes quests and gets paid exactly like
  -- a healthy one. That is the whole point of the hangout.
  if coalesce((v_quest ->> 'coop')::boolean, false) then
    if not (coalesce(f -> 'quests_joined', '[]'::jsonb)
            @> to_jsonb(p_quest_id)) then
      return jsonb_build_object(
        'error', 'You never joined that fair, so there is nothing to finish.');
    end if;
  end if;
  v_level := coalesce((f ->> 'level')::integer, 1);
  v_giver := v_quest ->> 'giver';
  v_rep_before := coalesce((f -> 'quests_rep' ->> v_giver)::integer, 0);
  v_rep_after := v_rep_before + 1;
  v_base := arena_private.quest_reward(v_quest ->> 'difficulty', v_level);
  if v_rep_before >= 3 then
    -- Helper tier: this giver's quests pay +25% from now on.
    v_base := floor(v_base * 1.25)::integer;
  end if;
  v_credits := arena_private.credits_of(f) + v_base;
  f := jsonb_set(f, '{credits}', to_jsonb(v_credits));
  f := jsonb_set(f, '{quests_rep}', (coalesce(f -> 'quests_rep', '{}'::jsonb)
    || jsonb_build_object(v_giver, v_rep_after)));
  f := f || jsonb_build_object(
    'quests_board', arena_private.quest_board_without(v_board, p_quest_id),
    'quests_done', v_done || to_jsonb(p_quest_id),
    'quests_active', null);
  v_message := format('Quest done! You earned %s credits.', v_base);
  -- Tier crossings, announced by the giver in their own voice.
  if v_rep_before < 3 and v_rep_after >= 3 then
    v_tier_line := format(
      '%s says: Three jobs done, and not one of them sloppy. You are a helper now, and my quests pay a little extra for you.',
      v_giver);
  elsif v_rep_before < 8 and v_rep_after >= 8 then
    v_tier_line := format(
      '%s says: Eight jobs done. You are a friend now, and friends get looked after. Pick a free upgrade: your weapon or your armor.',
      v_giver);
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
        '%s says: Fifteen jobs done. You are family now. Let me patch up that healing skill of yours — on the house. Healing is now level %s.',
        v_giver, v_heal + 1);
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
        f := jsonb_set(f, '{credits}',
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
    jsonb_build_object('quest', p_quest_id, 'credits', v_base), 'server');
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_quest,
    'credits', v_base,
    'message', v_message,
    'tier_line', v_tier_line,
    'giver', v_giver,
    'giver_voice', arena_private.quest_giver_voice(v_giver),
    'reputation', coalesce(f -> 'quests_rep', '{}'::jsonb),
    'gift_pending', f -> 'quests_gift_pending');
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
      '%s gave you a free %s upgrade. Your %s is now level %s.',
      v_giver, p_slot, v_name, v_level));
end;
$$;

revoke all on function public.arena_get_quests(text) from public;
revoke all on function public.arena_new_quest(text) from public;
revoke all on function public.arena_start_quest(text, text) from public;
revoke all on function public.arena_join_quest(text, text) from public;
revoke all on function public.arena_complete_quest(text, text) from public;
revoke all on function public.arena_choose_quest_gift(text, text) from public;
grant execute on function public.arena_get_quests(text) to anon, authenticated;
grant execute on function public.arena_new_quest(text) to anon, authenticated;
grant execute on function public.arena_start_quest(text, text) to anon, authenticated;
grant execute on function public.arena_join_quest(text, text) to anon, authenticated;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
grant execute on function public.arena_choose_quest_gift(text, text) to anon, authenticated;
