-- Phase 33: every history event records the player's credits.
-- On 2026-11-19 Makenna lost her credits to a bad purchase, and
-- nothing in her history said what her balance had been, so the
-- refund could only be a guess. From now on each event written by
-- arena_private.log_event carries "credits_now": the balance in the
-- player's fighter at the moment the event is written.
--
-- The game functions save the fighter first and log the event after,
-- so for a fight, upgrade or quest the number is the balance AFTER
-- that action. Events written before the fighter is saved show the
-- balance before it. Either way a refund can be worked out exactly.
--
-- Follows supabase/README.md: a new file, no old migration edited,
-- same name, inputs and result as before. It is a private helper, so
-- nothing changes for any game version, and no grants change. The
-- 200-event cap is unchanged. The detail is only added when credits
-- is a real number, and never replaces a "credits_now" already
-- there. Old events are left as they are.

create or replace function arena_private.log_event(
  p_code text, p_action text, p_detail jsonb, p_by text)
returns void
language sql
set search_path = ''
as $$
  update arena_private.players p
  set events = (
    select coalesce(jsonb_agg(x.e order by x.n), '[]'::jsonb)
    from (
      select t.e, t.n
      from jsonb_array_elements(
        p.events || jsonb_build_array(jsonb_build_object(
          'action', p_action,
          'detail',
            case
              when jsonb_typeof(coalesce(p_detail, '{}'::jsonb)) = 'object'
                and jsonb_typeof(p.fighter -> 'credits') = 'number'
                and not (coalesce(p_detail, '{}'::jsonb) ? 'credits_now')
              then coalesce(p_detail, '{}'::jsonb)
                || jsonb_build_object('credits_now', p.fighter -> 'credits')
              else coalesce(p_detail, '{}'::jsonb)
            end,
          'by', p_by,
          'created_at', now()))
      ) with ordinality as t(e, n)
      order by t.n desc
      limit 200
    ) x
  )
  where p.player_code = p_code
$$;
