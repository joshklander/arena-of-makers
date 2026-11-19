-- Quest levels — separate levels per activity (Phase 23, 2026-11-19).
--
-- Makenna's idea, 2026-11-18, from Magic Worlds (which already
-- has it; nothing changes there): fighting gives combat XP
-- toward the existing fighter level, quests give separate quest
-- XP toward a separate quest level, and later activities get
-- their own XP and level the same way.
--
-- How it works: only finishing a quest earns quest XP.
-- Starting, stopping, or pausing a quest earns nothing.
-- Easy 10 + 2 x quest level, Medium 20 + 5 x quest level
-- (the same as a fight win's XP, keyed to quest level),
-- Hard 40 + 10 x quest level. The Grand Hangout Fair pays
-- full quest XP to each joined player, like it pays full
-- credits: completing a quest is per player already, so
-- every joined player who finishes gets the full amount.
-- 100 x quest level quest XP to go up a quest level (100
-- for level 2, 200 for level 3), never capped. Each quest
-- level-up banks 1 quest point for Charm (+5% quest credits
-- per point), Renown (+10% chance of +1 bonus reputation
-- when a quest finishes per point; 100% at 10 points),
-- or Insight (+5% quest XP per point), each max 10 points.
-- Quest levels give no max HP and no combat stat points.
-- Renown bonus reputation counts toward the giver's
-- reputation tiers (3 Helper / 8 Friend / 15 Trusted
-- Friend), because it is reputation with that giver.
--
-- The server is the only judge, exactly as for credits:
-- arena_complete_quest awards the quest XP, rolls the
-- Renown chance, and banks the quest points — never the
-- game on the player's computer. The game only shows what
-- the server sends back. Combat XP, combat level, max HP
-- and combat stats are untouched by quests. Quest credits,
-- durations, pause/resume rules, and the hangout loop are
-- unchanged. One fighter per player, one quest level per
-- player, not per giver.
--
-- Old game versions keep working: they never read the new
-- quest-level fields, and arena_complete_quest keeps its
-- old inputs and all its old return fields — the new quest
-- fields are extra. Nothing is removed or renamed.

-- ---------------------------------------------------------------
-- Quest XP helpers (private).
-- ---------------------------------------------------------------

create or replace function arena_private.quest_xp(
  p_difficulty text, p_quest_level integer)
returns integer
language sql immutable
set search_path = ''
as $$
  select case
    when p_difficulty = 'Easy' then 10 + 2 * greatest(1, p_quest_level)
    when p_difficulty = 'Hard' then 40 + 10 * greatest(1, p_quest_level)
    else 20 + 5 * greatest(1, p_quest_level)
  end
$$;

create or replace function arena_private.quest_xp_to_next(
  p_quest_level integer)
returns integer
language sql immutable
set search_path = ''
as $$
  select 100 * greatest(1, p_quest_level)
$$;

-- One of the 3 quest stats, or 0 when the fighter has no
-- quest stats yet.
create or replace function arena_private.quest_stat_value(
  p_fighter jsonb, p_stat text)
returns integer
language sql immutable
set search_path = ''
as $$
  select coalesce((p_fighter -> 'quest_stats' ->> p_stat)::integer, 0)
$$;

-- ---------------------------------------------------------------
-- Spend one banked quest point (new function the game calls).
-- Mirrors arena_spend_stat: the server is the only judge.
-- ---------------------------------------------------------------

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
      'error', 'You have no quest points to spend right now.',
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
    v_line := v_line || format(' You have %s quest %s left.',
      v_points - 1, case when v_points - 1 = 1 then 'point' else 'points' end);
  else
    v_line := v_line || ' That was your last quest point.';
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

-- ---------------------------------------------------------------
-- arena_complete_quest, redefined: award quest XP, roll the
-- Renown bonus, and bank quest points on level-up. Everything
-- else is unchanged from
-- 20261119024741_quest_pause_resume.sql, and it still never
-- checks repairs.
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
  v_qlevel integer;
  v_qxp integer;
  v_qpoints integer;
  v_xp_base integer;
  v_xp_earned integer;
  v_level_ups integer := 0;
  v_bonus_rep integer := 0;
  v_qxp_line text;
  v_qlevel_line text := null;
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
  v_level := coalesce((f ->> 'level')::integer, 1);
  v_giver := v_quest ->> 'giver';
  -- Renown (Phase 23): +10% chance of +1 bonus reputation
  -- per Renown point. The server rolls it; at 10 points
  -- the chance is 100%, so every finished quest earns it.
  if random() < arena_private.quest_stat_value(f, 'renown') * 0.10 then
    v_bonus_rep := 1;
  end if;
  v_rep_before := coalesce((f -> 'quests_rep' ->> v_giver)::integer, 0);
  v_rep_after := v_rep_before + 1 + v_bonus_rep;
  v_base := arena_private.quest_reward(v_quest ->> 'difficulty', v_level);
  if v_rep_before >= 3 then
    -- Helper tier: this giver's quests pay +25% from now on.
    v_base := floor(v_base * 1.25)::integer;
  end if;
  -- Charm (Phase 23): +5% quest credits per Charm point.
  v_base := floor(v_base
    * (1 + 0.05 * arena_private.quest_stat_value(f, 'charm')))::integer;
  v_credits := arena_private.credits_of(f) + v_base;
  f := jsonb_set(f, '{credits}', to_jsonb(v_credits));
  f := jsonb_set(f, '{quests_rep}', (coalesce(f -> 'quests_rep', '{}'::jsonb)
    || jsonb_build_object(v_giver, v_rep_after)));
  -- Quest XP (Phase 23): only finishing a quest earns it.
  -- Insight adds +5% quest XP per Insight point. Quest
  -- levels give no max HP and no combat stat points; each
  -- quest level-up banks 1 quest point to spend.
  v_qlevel := coalesce((f ->> 'quest_level')::integer, 1);
  v_qxp := coalesce((f ->> 'quest_xp')::integer, 0);
  v_qpoints := coalesce((f ->> 'quest_points')::integer, 0);
  v_xp_base := arena_private.quest_xp(v_quest ->> 'difficulty', v_qlevel);
  v_xp_earned := floor(v_xp_base
    * (1 + 0.05 * arena_private.quest_stat_value(f, 'insight')))::integer;
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

revoke all on function public.arena_spend_quest_stat(text, text) from public;
revoke all on function public.arena_complete_quest(text, text) from public;
grant execute on function public.arena_spend_quest_stat(text, text) to anon, authenticated;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
