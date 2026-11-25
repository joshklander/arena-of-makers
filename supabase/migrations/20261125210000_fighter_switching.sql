-- Phase 36: fighter switching (2026-11-25, Makenna, voice call).
--
-- A player can switch their ONE fighter to another kind (robot,
-- chef, witch) from the Settings tab. Still one fighter per
-- player; switching never creates a second fighter.
--
-- Price (Makenna, Nov 25, 2026): the FIRST switch is FREE. After
-- that every switch costs credits, exponentially more each time,
-- with NO cap, unlimited switches as long as you can pay. The
-- starting price after the free one (100 credits) and the doubling
-- growth rate are a PROPOSAL — Makenna can tune them. The price
-- never resets (open question; the build grows it forever).
-- The switch count is tracked server-side in the fighter record
-- (kind_switches, 0 for fighters made before this phase), so the
-- price cannot be cheated down. The client never changes kind or
-- credits itself.
--
-- What resets on a switch (Makenna, Nov 25, 2026 — this supersedes
-- the Nov 18 carry-over rule, where weapon/armor levels and stats
-- all stayed): combat level and combat stats (level 1, 0 XP, all
-- five stats 0, no banked stat points, full health 100), quest
-- level and quest stats (quest level 1, 0 quest XP, 0 quest
-- points, Charm/Renown/Insight 0, reputation with every giver 0,
-- no board, no active quest, no finished-quest history, no free
-- gift waiting), weapon and armor upgrades (both back to level 1,
-- the fresh weapon and armor for the new kind, with no upgrades
-- bought), and any upgrade or repair running now (the new fighter
-- starts at full health, so a repair ends; a running upgrade ends
-- with the old weapon and armor). Switching is allowed while
-- repairing or upgrading — the open question from the design draft
-- is answered that way in this build, and the confirm dialog says
-- so when one is running.
-- What stays: Healing (Second Wind) at its current level, credits
-- minus the switch cost (DECIDED Nov 25, 2026: credits STAY with
-- the player, so credits built up before can boost the new
-- fighter's weapon and armor from zero), wins and losses, name,
-- gender and voice.
-- Weapon and armor start at level 1, not level 0: level 1 is the
-- fresh weapon with no upgrades, the same as a brand-new fighter;
-- level 0 is not a state the game ever has (weapon damage would
-- go negative). The confirm dialog says "start over at level 1"
-- in the same plain words.
--
-- New migration file only: no old migration is edited, and
-- Kiro's password sign-in, auto-login and anti-cheat work are
-- untouched. Depends on the Phase 35 migration (the players.kind
-- check must already allow 'witch').

-- new_fighter, redefined from Phase 35: brand-new fighters start
-- with 0 switches, so their first switch is free. Everything
-- else is byte-identical to the Phase 35 version.
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
    'quests_gift_pending', null
  )
$$;

-- ---------------------------------------------------------------
-- arena_switch_kind: switch the signed-in player's fighter to a
-- new kind, charging the price for their switch count and
-- applying the reset rules above. The server is the only judge:
-- the client only calls this and shows what comes back.
-- ---------------------------------------------------------------
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
    'upgrade', null,
    'upgrade_queue', null,
    'upgrade_total', 0,
    'repair_until', 0,
    'credits', v_credits - v_cost,
    'kind_switches', v_switches + 1);
  v_next_cost := 100 * (2::bigint ^ v_switches);
  v_message := format(
    'You are now a %s. Your weapon is the %s and your armor is '
    'the %s. Your Healing stayed at level %s, and your combat '
    'and quest levels started over at level 1. Your next switch '
    'costs %s credits.',
    v_word, v_weapon, v_armor, v_healing, v_next_cost);
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

revoke all on function public.arena_switch_kind(text, text) from public;
grant execute on function public.arena_switch_kind(text, text) to anon, authenticated;
