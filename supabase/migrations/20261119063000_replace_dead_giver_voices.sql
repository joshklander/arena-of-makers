-- Replace two dead quest giver voices (Makenna 2026-11-18,
-- Phase 27): Microsoft retired Gus's voice (en-US-DavisNeural)
-- and Belle's voice (en-US-SaraNeural) — neither is in the live
-- Edge voice catalog any more, so their quest lines failed to
-- synthesise and the old voice engine marked the whole voice
-- dead, silencing every later line while the music kept playing.
-- Gus now speaks with en-US-AndrewNeural (male, warm and
-- confident, like the old grill master) and Belle with
-- en-US-EmmaNeural (female, cheerful and clear, like the
-- cheerful baker). Bolt, Marge, Pip and Dot keep their voices.
-- Only arena_private.quest_giver_voice is redefined here, copied
-- from 20261119020000_add_hangout_quests.sql with only those two
-- lines changed; every older migration is untouched, and no fight
-- function is touched. Old game versions keep working — they only
-- ever read the voice the server sends back.
-- ---------------------------------------------------------------

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
    else 'en-US-ChristopherNeural'
  end
$$;
