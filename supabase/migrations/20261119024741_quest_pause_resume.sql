-- Hangout quests: pause and resume (Phase 22, 2026-11-19).
--
-- Makenna's correction, 2026-11-18: a hangout quest must NOT
-- tick down when she is not actually in the hangout doing the
-- quest. Repairs and upgrades DO tick down whether the game is
-- open or closed — that stays exactly as it is. But a quest's
-- clock only runs while she is in the hangout with quests
-- started, and a quest never completes while she is away.
--
-- How it works now: when quests stop — Stop button, leaving
-- the More tab / hangout, Escape, or closing the game with a
-- quest active — the game calls arena_pause_quest, which
-- freezes the quest with its REMAINING time saved
-- (remaining_seconds) instead of its finish_at. When she
-- presses Start again, arena_start_quest resumes it from
-- that remaining time: new finish_at = now + remaining. The
-- quest is never restarted and never shortened by time away.
--
-- arena_complete_quest still never checks repairs, exactly
-- as before. It also never completes a paused quest: a
-- paused quest's clock is frozen, so there is nothing to
-- finish until it is resumed and its time runs out in the
-- hangout loop.
--
-- Old game versions keep working: they never call
-- arena_pause_quest, so their quests keep the old behaviour
-- (the timer runs on finish_at). Nothing is removed or
-- renamed, and the two redefined functions below keep their
-- old inputs and return shapes.

-- ---------------------------------------------------------------
-- Pause one quest (new function the game calls).
-- ---------------------------------------------------------------

create or replace function public.arena_pause_quest(p_token text)
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
  v_active jsonb;
  v_remaining double precision;
begin
  if v_code is null then
    return arena_private.signed_out();
  end if;
  select * into r from arena_private.players where player_code = v_code for update;
  select * into t from arena_private.apply_timers(r.fighter, arena_private.now_epoch());
  f := t.fighter;
  v_active := f -> 'quests_active';
  if v_active is null or jsonb_typeof(v_active) <> 'object' then
    -- Nothing running: nothing to freeze.
    return jsonb_build_object(
      'fighter', arena_private.fighter_out(f, r.player_code, r.username),
      'quest', null);
  end if;
  if coalesce((v_active ->> 'paused')::boolean, false) then
    -- Already paused: the frozen time stands.
    return jsonb_build_object(
      'fighter', arena_private.fighter_out(f, r.player_code, r.username),
      'quest', v_active,
      'remaining_seconds',
        coalesce((v_active ->> 'remaining_seconds')::double precision, 0));
  end if;
  v_remaining := greatest(0,
    (v_active ->> 'finish_at')::double precision - v_now);
  v_active := v_active || jsonb_build_object(
    'paused', true,
    'remaining_seconds', v_remaining);
  f := f || jsonb_build_object('quests_active', v_active);
  update arena_private.players
  set fighter = f, updated_at = now()
  where player_code = v_code;
  return jsonb_build_object(
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'quest', v_active,
    'remaining_seconds', v_remaining);
end;
$$;

-- ---------------------------------------------------------------
-- arena_start_quest, redefined: resume a paused quest from
-- its frozen remaining time. Everything else is unchanged
-- from 20261119020000_add_hangout_quests.sql.
-- ---------------------------------------------------------------

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
  v_remaining double precision;
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
      if coalesce((v_active ->> 'paused')::boolean, false) then
        -- Paused (Phase 22): the quest clock was frozen when
        -- quests stopped, so resume from the remaining time
        -- that was saved then, not from the old finish time.
        -- Time spent fighting, away, or with the game closed
        -- never eats into the quest.
        v_remaining := greatest(0,
          coalesce((v_active ->> 'remaining_seconds')::double precision,
                   (v_active ->> 'finish_at')::double precision - v_now));
        v_quest := (v_active - 'remaining_seconds')
          || jsonb_build_object(
            'finish_at', v_now + v_remaining,
            'paused', false);
        f := f || jsonb_build_object('quests_active', v_quest);
        update arena_private.players
        set fighter = f, updated_at = now()
        where player_code = v_code;
        return jsonb_build_object(
          'fighter', arena_private.fighter_out(f, r.player_code, r.username),
          'quest', v_quest);
      end if;
      -- Pressing Start again while the quest is still running
      -- picks up the saved quest, it does not restart it:
      -- same finish time.
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

-- ---------------------------------------------------------------
-- arena_complete_quest, redefined: a paused quest never
-- completes while its clock is frozen. Everything else is
-- unchanged from 20261119020000_add_hangout_quests.sql, and
-- it still never checks repairs.
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

revoke all on function public.arena_pause_quest(text) from public;
revoke all on function public.arena_start_quest(text, text) from public;
revoke all on function public.arena_complete_quest(text, text) from public;
grant execute on function public.arena_pause_quest(text) to anon, authenticated;
grant execute on function public.arena_start_quest(text, text) to anon, authenticated;
grant execute on function public.arena_complete_quest(text, text) to anon, authenticated;
