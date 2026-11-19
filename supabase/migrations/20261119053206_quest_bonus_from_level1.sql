-- Quest bonus grows right from the start (Makenna
-- 2026-11-18, Phase 26 follow-up): the automatic quest-stat
-- bonus is now quest level x 1% — 1% already at quest level 1,
-- 5% at quest level 5 — instead of (quest level - 1) x 1%,
-- which was 0% at quest level 1. Nothing else about the bonus
-- changes: it still applies to all three quest stats (Charm,
-- Renown, Insight), stacks with spent quest points, and never
-- caps. Only arena_complete_quest is redefined here, copied
-- from 20261119050500_quest_growth.sql with only the bonus
-- formula changed; every older migration is untouched.
-- ---------------------------------------------------------------

-- arena_complete_quest, redefined: quest credits are keyed to
-- the quest level (Phase 26), and the automatic quest-stat
-- bonus (+1% per quest level) stacks with the spent
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

revoke all on function public.arena_complete_quest(text, text) from public;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
