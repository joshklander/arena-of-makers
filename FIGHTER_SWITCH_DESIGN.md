# Fighter switching — DECIDED Nov 25, 2026, built in Phase 36

Status: DECIDED by Makenna (voice call, 2026-11-25) and BUILT as Phase 36,
after the witch kind plumbing (Phase 35). This replaces the Nov 18, 2026
proposal below where it disagrees — the Nov 18 carry-over rule is gone.

## Makenna's rule, in her words (substance)

You should be able to switch fighters if you want — not get a whole new
fighter, not have two or three fighters, but switch the one fighter you
have, for example from a robot to a chef. It costs credits every time, so
people cannot spam it and change every two minutes. They have to pay
credits, and the more you change your play style, the more credits it costs.

## What switching means — DECIDED Nov 25, 2026

- Still ONE fighter per player. Switching changes the existing fighter's
  kind (robot <-> chef <-> witch). It does not create a second fighter.
- **What resets:** combat level and combat stats (level 1, 0 XP, all five
  stats 0, no banked stat points, full health 100), quest level and quest
  stats (quest level 1, 0 quest XP, 0 quest points, Charm / Renown /
  Insight 0, reputation with every giver 0, no board, no active quest,
  no finished-quest history, no free gift waiting), and weapon and armor
  upgrades (both back to level 1 — the fresh weapon and armor for the
  new kind, with no upgrades bought). Any upgrade or repair running now
  ends too: the new fighter starts at full health, so a repair ends, and
  a running upgrade ends with the old weapon and armor.
- **What stays:** Healing (Second Wind) at its current level, credits
  minus the switch cost, wins and losses, name, gender and voice.
- Weapon and armor start at level 1, not level 0: level 1 is the fresh
  weapon with no upgrades, the same as a brand-new fighter; level 0 is
  not a state the game ever has (weapon damage would go negative).
- Why the reset (Makenna, Nov 25, 2026): each character should shine on
  its own, and you can only have one character at a time.
- This SUPERSEDES the Nov 18, 2026 carry-over rule (below), where weapon
  and armor levels, stats, level, XP, reputation and quest level all
  stayed. The old rule is kept in this file for the record only.
- What changes with kind (verified in the Phase 22 code, extended for
  the witch in Phase 35):
  - `kind` itself, stored in the players table (check: kind in
    ('robot', 'chef', 'witch')) and in the fighter record.
  - Weapon and armor names: robot = Laser Blaster / Scrap Plating,
    chef = Trusty Spatula / Chef Apron, witch = Spellbound Wand /
    Mystic Robe (server `new_fighter` logic).
  - Base damage: 12 for robot, 10 for chef, 11 for witch
    (game_logic.py, explicit three-way base, never else-10).
  - Sounds: hit/intro sounds differ by kind already
    (`_play_sound_for_line` picks by kind). A witch falls through to
    the robot sounds until the elements piece adds witch sounds.
  - Voice does NOT change: gender picks the voice, not kind. A male
    witch is called a warlock, a female witch is called a witch;
    the stored kind stays "witch" either way.
- A switch is a deliberate, confirmed choice: the game asks Yes/No first
  (same fixed dialog pattern as the shop), says the cost before you pay,
  lists exactly what resets and what stays, and never switches by accident.

## Cost — escalating, no cap (DECIDED by Makenna, Nov 18, 2026; first switch free, Nov 25, 2026)

- The FIRST switch is FREE. After that, every switch costs credits.
- There is NO cap. Cost is unlimited progression: it keeps getting
  exponentially more expensive the more you switch, forever. The earlier
  1,000-credit cap proposal is dropped.
- Cost grows with how many times that player has switched before.
  Starting price and growth rate are a PROPOSAL in the build, for Makenna
  to tune: first paid switch 100 credits, doubling each time
  (100, 200, 400, 800, ...). The price never resets in the build.
- The switch count is tracked server-side (new field `kind_switches` on
  the fighter record, 0 for fighters made before Phase 36), never trusted
  from the client, so the price cannot be cheated down.
- If the player cannot afford the current price, the game says so in
  plain words and nothing changes. No debt, no negative credits.

## Server side

- New server function `arena_switch_kind`, in a NEW migration file only
  (`20261125210000_fighter_switching.sql`, Phase 36 — never edit an old
  migration). It checks: the player is signed in (session token), the new
  kind is robot, chef or witch and different from the current kind, the
  player can afford the price for their current switch count, then it
  deducts the credits, flips kind, renames weapon/armor to match and
  resets weapon_level / armor_level to 1, resets combat level, XP, stats,
  stat points, health, quest level, quest XP, quest points, quest stats,
  reputation, board, history, active quest and gift, clears any running
  upgrade or repair, leaves Healing untouched, bumps the switch count,
  and returns the updated fighter plus the cost paid and the next switch
  price. `new_fighter` was redefined in the same migration so brand-new
  fighters start with `kind_switches` 0.
- The client never changes kind or credits itself — it only calls the
  function and shows what the server returns. Same anti-cheat rule as
  everything else. The client keeps a mirror of the rules in
  `game_logic.switch_cost` and `game_logic.switched_fighter` for the
  display price and the tests; the server is the judge.

## Where it lives in the game

- A "Change fighter" line in the Settings tab (Makenna, Nov 25, 2026 —
  "in the settings or something"), one line for each kind this fighter
  is not, showing the cost (or "first switch is free"). Enter on one asks
  Yes/No with the cost spoken and the full resets/stays list, then calls
  the server. Switching is allowed while repairing or upgrading: the
  confirm says so when one is running.
- After a switch, the game announces the new kind and the next switch
  price, in plain words, and the Home tab shows the new kind.

## Questions for Makenna (still open)

1. Cost numbers: the build uses first paid switch 100 credits, doubling
   each time, with NO cap. Is that the right starting price and growth
   rate, or should it be tuned?
2. Should the price ever reset (for example back to the starting price
   after a long time without switching), or only ever grow?
3. (Answered in the build, Nov 25, 2026) Should switching be allowed
   while repairing, like quests are, or only when not repairing?
   The build allows it: the new fighter starts at full health, so the
   repair ends, and a running upgrade ends with the old weapon and armor.

## The Nov 18, 2026 proposal (superseded — kept for the record)

- Switching did not reset the fighter: level, XP, stats
  (strength/defense/health/speed/luck), credits (minus the switch cost),
  wins, losses, reputation, quest levels, healing level, upgrades,
  timers/repairs all stayed.
- Upgrade levels CARRIED OVER: if you had a level 5 laser as a robot
  and switched to a chef, those 5 levels went into the chef's weapon
  (Trusty Spatula level 5). Same for armor. The server did this by
  renaming only `weapon_name` / `armor_name` and keeping `weapon_level` /
  `armor_level` untouched.
- The switch lived in the More tab, not the Settings tab.
- Makenna changed all three points on Nov 25, 2026: weapon/armor reset
  to level 1, combat and quest levels reset to level 1, reputation and
  quest stats reset, and the switch moved to the Settings tab.
