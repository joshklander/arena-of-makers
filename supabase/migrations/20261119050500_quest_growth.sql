-- Quest growth — durations, credit rewards and the automatic
-- quest-stat bonus all scale with the quest level (Phase 26,
-- Makenna 2026-11-18).
--
-- 1. DURATIONS grow with the quest level. At quest level 1
-- they are exactly as before: Easy 5-15 minutes, Medium
-- 15-45, Hard 60-240. At higher quest levels the base range
-- is multiplied by (1 + 0.1 x (quest level - 1)), capped at
-- 240 minutes (4 hours) — never over 4 hours. quest_new
-- takes the player's quest level now; quest_board_ensure
-- and arena_new_quest pass it in from the fighter.
-- 2. QUEST CREDIT rewards switch from the fighter (combat)
-- level to the quest level: Easy 5 + 2 x quest level,
-- Medium 10 + 5 x quest level, Hard 20 + 10 x quest level,
-- growing infinitely with no cap, even though the timer
-- caps at 4 hours. A Medium quest now pays what a fight
-- win pays only when the quest level and the fighter level
-- happen to match. Quest XP formulas are unchanged — they
-- already scale with the quest level.
-- 3. AUTOMATIC quest-stat bonus, like combat's automatic
-- +10 HP per combat level: each quest level-up gives +1%
-- to all three quest stats (Charm, Renown, Insight), and
-- the banked quest point a player spends adds its bigger
-- bonus on top. At quest level 1 nothing has levelled up
-- yet, so the automatic bonus is 0; at quest level 5 it
-- is 4%. It stacks with spent points and never caps.
--
-- Pause/resume is untouched: a paused quest keeps its
-- frozen remaining time, and starting again resumes from
-- it — durations are fixed when a quest is dealt, so a
-- quest dealt at one quest level keeps its time even if
-- the player levels up mid-quest.
--
-- Old game versions keep working: arena_new_quest and
-- arena_complete_quest keep their old inputs and all their
-- old return fields — the new quest fields are extra, and
-- quest_new's new parameter has a default, so older calls
-- still work. Nothing is removed or renamed.

-- ---------------------------------------------------------------
-- Deal one fresh quest: durations now grow with the quest level.
-- ---------------------------------------------------------------

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
  v_factor double precision
    := 1 + 0.1 * (greatest(1, p_quest_level) - 1);
  v_low integer;
  v_high integer;
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
-- Givers are dealt in a shuffled order from all six, so the
-- board always holds both male and female givers. The
-- board is dealt at the fighter's quest level (Phase 26),
-- so its durations grow with it.
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
  from (select unnest(array['Bolt', 'Marge', 'Pip', 'Dot', 'Gus', 'Belle']) as g
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

-- Quest credits are keyed to the quest level now (Phase 26),
-- not the fighter level. Same amounts as before at quest
-- level 1; they grow infinitely from there, with no cap.
create or replace function arena_private.quest_reward(
  p_difficulty text, p_quest_level integer)
returns integer
language sql immutable
set search_path = ''
as $$
  select case
    when p_difficulty = 'Easy' then 5 + 2 * greatest(1, p_quest_level)
    when p_difficulty = 'Hard' then 20 + 10 * greatest(1, p_quest_level)
    else 10 + 5 * greatest(1, p_quest_level)
  end
$$;

-- Deal one fresh quest, at the player's quest level
-- (Phase 26), so its duration grows with it.
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
  v_quest := arena_private.quest_new(
    v_board, v_done, v_diff, v_coop, null, v_qlevel);
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

-- ---------------------------------------------------------------
-- arena_complete_quest, redefined: quest credits are keyed to
-- the quest level (Phase 26), and the automatic quest-stat
-- bonus (+1% per quest level-up) stacks with the spent
-- points for Charm, Renown and Insight. Everything else is
-- unchanged from 20261119030307_quest_levels.sql, and it
-- still never checks repairs.
-- ---------------------------------------------------------------

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
  -- Automatic bonus (Phase 26): +1% per quest level-up to
  -- Charm, Renown and Insight, like combat's automatic
  -- +10 HP per combat level. At quest level 1 nothing has
  -- levelled up yet, so the bonus is 0. It stacks with
  -- spent quest points and never caps.
  v_auto := greatest(0, v_qlevel - 1);
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
    'You earned %s quest experience. You have %s quest experience, '
    '%s more to reach quest level %s.',
    v_xp_earned, v_qxp,
    arena_private.quest_xp_to_next(v_qlevel) - v_qxp, v_qlevel + 1);
  if v_level_ups > 0 then
    v_qlevel_line := format(
      'You are now quest level %s! You have %s quest %s to spend.',
      v_qlevel, v_qpoints,
      case when v_qpoints = 1 then 'point' else 'points' end);
  end if;
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

revoke all on function public.arena_new_quest(text) from public;
revoke all on function public.arena_complete_quest(text, text) from public;
grant execute on function public.arena_new_quest(text) to anon, authenticated;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
