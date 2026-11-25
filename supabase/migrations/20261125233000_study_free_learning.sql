-- Phase 38b (Makenna, Nov 25, 2026): learning spells costs NO
-- credits at all — it is time-based only, not credit-based. The
-- credit cost in Phase 38 (common 25 credits, uncommon 50, rare
-- 100, epic 200, legendary 400) was only ever a builder proposal.
--
-- This migration re-issues arena_study_start from its Phase 38
-- version (20261125230000_witch_study.sql) with the credit charge
-- and the credits check removed, and drops arena_private.spell_cost,
-- which nothing uses any more. Everything else is unchanged: one
-- spell at a time, tier prerequisites (the tier below first),
-- the paused resume with the same remaining time, the 4-hour cap
-- on spell_seconds, and the witch-only rule for learning (study
-- quests stay open to everyone).
--
-- Follows supabase/README.md: a new file, no old migration edited.
-- Kiro's password sign-in, auto-login and anti-cheat are untouched.
-- Old fighters keep working: this changes no stored shape, only
-- stops charging credits that were never meant to be charged.

drop function if exists arena_private.spell_cost(text);

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
      -- nothing charged — learning is free (the quest resume
      -- pattern).
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
  -- No credit charge and no credits check: learning spells is
  -- time-based only (Makenna, Nov 25, 2026).
  v_name := arena_private.spell_name(v_element, v_tier);
  f := f || jsonb_build_object(
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
                       'level', v_level + 1), 'server');
  return jsonb_build_object(
    'message', format('I started learning %s. It will take %s.',
      v_name, arena_private.format_time(arena_private.spell_seconds(v_tier))),
    'messages', t.messages,
    'fighter', arena_private.fighter_out(f, r.player_code, r.username),
    'study', f -> 'study');
end;
$$;
