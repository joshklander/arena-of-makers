# Fighter switching — design draft (Makenna, 2026-11-18)

Status: PROPOSAL ONLY. Not coded, not pushed. To build after Phase 23 (quest levels), in its own phase.

## Makenna's rule, in her words (substance)

You should be able to switch fighters if you want — not get a whole new
fighter, not have two or three fighters, but switch the one fighter you
have, for example from a robot to a chef. It costs credits every time, so
people cannot spam it and change every two minutes. They have to pay
credits, and the more you change your play style, the more credits it costs.

## What switching means

- Still ONE fighter per player. Switching changes the existing fighter's
  kind (robot <-> chef). It does not create a second fighter, and it does
  not reset the fighter.
- Everything else stays: level, XP, stats (strength/defense/health/speed/
  luck), credits (minus the switch cost), wins, losses, reputation,
  quest levels, healing level, upgrades, timers/repairs.
- What changes with kind (verified in the Phase 22 code):
  - `kind` itself, stored in the players table (check: kind in
    ('robot', 'chef')) and in the fighter record.
  - Weapon and armor names: robot = Laser Blaster / Scrap Plating,
    chef = Trusty Spatula / Chef Apron (server `new_fighter` logic).
  - Base damage: 12 for robot, 10 for chef (game_logic.py line 216).
  - Sounds: hit/intro sounds differ by kind already
    (`_play_sound_for_line` picks by kind).
  - Voice does NOT change: gender picks the voice, not kind.
- Upgrade levels CARRY OVER (decided by Makenna, Nov 18, 2026): stats
  stay, and the upgrade levels switch over with you. If you have a
  level 5 laser as a robot and switch to a chef, those 5 levels go
  into the chef's weapon (Trusty Spatula level 5). Same for armor:
  Scrap Plating level becomes Chef Apron level. The server does this
  by renaming only `weapon_name` / `armor_name` and keeping
  `weapon_level` / `armor_level` untouched — the levels are plain
  numbers in the fighter record, independent of kind (verified:
  game_logic.py lines 97-100, server lines 831-832 use the levels
  directly). Nothing is reset or re-bought.
- A switch is a deliberate, confirmed choice: the game asks Yes/No first
  (same fixed dialog pattern as the shop), says the cost before you pay,
  and never switches by accident.

## Cost — escalating, no cap (DECIDED by Makenna, Nov 18, 2026)

- There is NO cap. Cost is unlimited progression: it keeps getting
  exponentially more expensive the more you switch, forever. The earlier
  1,000-credit cap proposal is dropped.
- Cost grows with how many times that player has switched before
  (exact starting price and growth rate still to be decided — see
  questions below).
- The switch count is tracked server-side (new field, e.g.
  `kind_switches` on the player), never trusted from the client, so
  the price cannot be cheated down.
- If the player cannot afford the current price, the game says so in
  plain words and nothing changes. No debt, no negative credits.

## Server side

- New server function, e.g. `arena_switch_kind`, in a NEW migration
  file only (never edit an old migration). It checks: the player is
  signed in (session token), the new kind is robot or chef and different
  from the current kind, the player can afford the price for their
  current switch count, then it deducts the credits, flips kind,
  renames weapon/armor to match while KEEPING weapon_level and
  armor_level exactly as they are (that is how the levels carry over),
  bumps the switch count, and returns the updated fighter plus the
  next switch price.
- The client never changes kind or credits itself — it only calls the
  function and shows what the server returns. Same anti-cheat rule as
  everything else.

## Where it lives in the game

- A "Switch fighter" line in the More tab (next to the other fighter
  options), showing the current kind, the cost of the next switch, and
  how many times you have switched. Enter on it asks Yes/No with the
  cost spoken, then calls the server.
- After a switch, the game announces the new kind and the next switch
  price, in plain words, and the Home tab shows the new kind.

## Questions for Makenna (not answered yet)

1. Cost numbers: starting price and growth rate — for example first
   switch 100 credits, doubling each time, with NO cap (decided: no
   cap, unlimited progression, exponentially more expensive).
2. Should the price ever reset (for example back to the starting price
   after a long time without switching), or only ever grow?
3. Should switching also be allowed while repairing, like quests are, or
   only when not repairing?
