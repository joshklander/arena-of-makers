# Magical creatures — Phase 39 candidate (NOT built yet)

Written Nov 25, 2026, as the next tested piece after the Phase 38
witch study. **Decided by Makenna Nov 25, 2026 (voice call):** add
magical creatures and other witches/warlocks into the pool of
creatures you can fight, alongside the 9 Phase 24 creatures. **Added
the same day:** each new creature also has its own different
**magical attack sound**, distinct from the others — not just an
appear and a hit sound, but three sounds per creature.

**Why this is Phase 39, not Phase 38:** the study build was already
full (spells, Study tab, 4 givers, 6 quest templates, 15 sounds, a
migration, 3 test files). Twelve creatures × 3 sounds each, plus a
migration and new ability code, would overload it. This doc is the
proposal for Makenna to approve; nothing here is built, and no sound
has been uploaded.

## The rules (same as the Phase 24 creatures)

- At the **fighter's own level**, fair matchmaking — a creature is
  a multiplier on the Scrap Rat formulas, so a fight stays fair
  at any level.
- The fight pool picks **at random**: after this lands, manual
  Fight and auto-fight pick from **21 creatures** (9 Phase 24 +
  12 new).
- Each creature has its own **special ability** that fires every
  few rounds, with its own line, exactly like Phase 24.
- **Three sounds per creature**, all different from each other
  and from every other creature's sounds, so you can tell who it
  is — and what it just did — by sound alone:
  - **appear** — when the creature appears;
  - **hit** — when it hits the fighter with a normal hit;
  - **magic** — when its special ability fires (its magical
    attack). The magic sound plays **instead of** the regular
    hit sound on that round. One exception: the Rival Witch's
    magic is a random elemental spell sound (see the table) —
    she casts a real spell, so she sounds like one.

## The 12 creatures (PROPOSAL — Makenna can rename any of them)

Names are Maren's proposals. One per element (all ten), plus a
rival witch and a rival warlock. Multipliers and profiles follow
the Phase 24 pattern (reward 1.1–1.2, profile weights sum to 10).

| # | Creature | Element | Ability (every N rounds) | What it does |
|---|---|---|---|---|
| 1 | Ember Sprite | fire | flare, every 3rd | A burst of flame, 1.5× damage |
| 2 | Tide Wisp | water | sugar_trap, every 4th | A wave soaks the fighter — the next hit is weak (halved) |
| 3 | Frost Faerie | ice | shock, every 3rd | A freezing shock, 1.5× damage |
| 4 | Gale Sylph | wind | dodge, every 5th | Swoops aside — the fighter's hit misses |
| 5 | Bog Toad | poison | shock, every 3rd | A toxic burst, 1.5× damage |
| 6 | Dawn Moth | light | double_hit, every 4th | Flutters in twice |
| 7 | Shade Stalker | shadow | vanish, every 3rd | Melts into shadow — the fighter's hit misses |
| 8 | Void Imp | dark | flare, every 3rd | A void burst, 1.5× damage |
| 9 | Pebble Golem | earth | shield, every 4th | Raises a stone shield — the fighter's hit bounces off |
| 10 | Storm Roc | lightning | shock, every 3rd | A storm shock, 1.5× damage |
| 11 | Rival Witch | witch | **random_spell, every 4th — NEW** | Casts a random elemental spell, 1.5× damage, and the magic sound is that spell's own cast sound (one of the 10 `spell_<element>.ogg` files, picked at random) |
| 12 | Rival Warlock | witch | sugar_trap, every 4th | A curse — the fighter's next hit is weak (halved) |

Ability lines (first person on the client, like Phase 24 — the
server line says "Your hit…", the client line says "My hit…"):

| Creature | Server line | Client line |
|---|---|---|
| Ember Sprite | Ember Sprite bursts into flame! | Ember Sprite bursts into flame! |
| Tide Wisp | Tide Wisp soaks you! Your next hit is weak! | Tide Wisp soaks me! My next hit is weak! |
| Frost Faerie | Frost Faerie freezes the air! A freezing shock! | Frost Faerie freezes the air! A freezing shock! |
| Gale Sylph | Gale Sylph swoops aside! Your hit misses! | Gale Sylph swoops aside! My hit misses! |
| Bog Toad | Bog Toad bursts with poison! | Bog Toad bursts with poison! |
| Dawn Moth | Dawn Moth flutters in twice! | Dawn Moth flutters in twice! |
| Shade Stalker | Shade Stalker melts into shadow! Your hit misses! | Shade Stalker melts into shadow! My hit misses! |
| Void Imp | Void Imp bursts with void energy! | Void Imp bursts with void energy! |
| Pebble Golem | Pebble Golem raises a stone shield! Your hit bounces off! | Pebble Golem raises a stone shield! My hit bounces off! |
| Storm Roc | Storm Roc crackles with storm! A shock! | Storm Roc crackles with storm! A shock! |
| Rival Witch | The Rival Witch casts a spell! | The Rival Witch casts a spell! |
| Rival Warlock | The Rival Warlock curses you! Your next hit is weak! | The Rival Warlock curses me! My next hit is weak! |

Stat proposals (hp_mult / dmg_mult / reward_mult / profile
speed-strength-health-defense-luck):

| Creature | hp | dmg | reward | Profile |
|---|---|---|---|---|
| Ember Sprite | 0.9 | 1.25 | 1.2 | 3-3-2-1-1 |
| Tide Wisp | 1.1 | 1.0 | 1.2 | 2-2-3-2-1 |
| Frost Faerie | 0.8 | 1.2 | 1.2 | 4-3-1-0-2 |
| Gale Sylph | 0.8 | 1.2 | 1.2 | 4-3-1-0-2 |
| Bog Toad | 1.3 | 0.95 | 1.1 | 1-2-4-2-1 |
| Dawn Moth | 0.75 | 1.3 | 1.2 | 4-3-1-1-1 |
| Shade Stalker | 0.8 | 1.2 | 1.2 | 4-3-1-0-2 |
| Void Imp | 0.9 | 1.25 | 1.2 | 3-3-2-1-1 |
| Pebble Golem | 1.8 | 0.7 | 1.1 | 1-1-4-3-1 |
| Storm Roc | 0.9 | 1.25 | 1.2 | 4-3-1-0-2 |
| Rival Witch | 1.0 | 1.1 | 1.3 | 2-3-2-2-1 |
| Rival Warlock | 1.0 | 1.1 | 1.3 | 2-3-2-2-1 |

The rivals pay a little more (reward 1.3) because fighting
another witch or warlock is the hardest fight in the pool.

## The sounds (PROPOSAL — 35 new files, all Kenney CC0)

Every file below is from one of the four Kenney packs already
downloaded for Phase 38 (RPG Audio, Sci-fi Sounds, Impact
Sounds, UI Audio — all CC0, licence on each pack page and in
the zips' License.txt). Durations were measured with ffprobe
from the downloaded files. **Nothing has been copied into
`sounds/` yet and nothing has been uploaded** — the files live
in `phase38-witch-study/sounds-download/` until the build.
Audio goes up only via the GitHub website in the browser,
never via the GitHub tools.

The files were picked to be **different from every sound
already in the game**: none of them is a Phase 38 spell sound
(`thrusterFire_000`, `slime_000/001`, `impactGlass_medium_000`,
`cloth1`, `laserSmall_000`, `lowFrequency_explosion_001`,
`forceField_000`, `impactMining_000`, `laserLarge_000`,
`knifeSlice`) or a Phase 24 creature sound. Where a pick is a
different take of a sound already used (for example
`thrusterFire_001` next to the fire spell's `thrusterFire_000`),
it is a different recording in the same family — the builder
listens to each file before the upload and swaps it if two
creatures sound too alike. The 5.00-second files play only
their first 2 seconds in the game (maxtime 2000 in
`SOUND_FILES`, the same treatment as `npc_grill_gus_appear`
and `npc_mend_o_matic_appear` in Phase 24).

| Creature | Sound | File in `sounds/` | Source file (Kenney pack) | Length |
|---|---|---|---|---|
| Ember Sprite | appear | `npc_ember_sprite_appear.ogg` | Sci-fi `thrusterFire_001.ogg` | 5.00 s (first 2 s) |
| Ember Sprite | hit | `npc_ember_sprite_hit.ogg` | Sci-fi `explosionCrunch_000.ogg` | 0.78 s |
| Ember Sprite | magic | `npc_ember_sprite_magic.ogg` | Sci-fi `explosionCrunch_002.ogg` | 1.26 s |
| Tide Wisp | appear | `npc_tide_wisp_appear.ogg` | Sci-fi `spaceEngineLow_000.ogg` | 5.00 s (first 2 s) |
| Tide Wisp | hit | `npc_tide_wisp_hit.ogg` | Impact `impactSoft_medium_001.ogg` | 0.18 s |
| Tide Wisp | magic | `npc_tide_wisp_magic.ogg` | Sci-fi `spaceEngineSmall_000.ogg` | 5.00 s (first 2 s) |
| Frost Faerie | appear | `npc_frost_faerie_appear.ogg` | Impact `impactGlass_light_000.ogg` | 0.21 s |
| Frost Faerie | hit | `npc_frost_faerie_hit.ogg` | Impact `impactGlass_light_002.ogg` | 0.21 s |
| Frost Faerie | magic | `npc_frost_faerie_magic.ogg` | Impact `impactGlass_heavy_001.ogg` | 0.43 s |
| Gale Sylph | appear | `npc_gale_sylph_appear.ogg` | Sci-fi `spaceEngineSmall_001.ogg` | 5.00 s (first 2 s) |
| Gale Sylph | hit | `npc_gale_sylph_hit.ogg` | RPG `cloth3.ogg` | 0.48 s |
| Gale Sylph | magic | `npc_gale_sylph_magic.ogg` | Sci-fi `spaceEngine_001.ogg` | 5.00 s (first 2 s) |
| Bog Toad | appear | `npc_bog_toad_appear.ogg` | Impact `impactSoft_heavy_000.ogg` | 0.51 s |
| Bog Toad | hit | `npc_bog_toad_hit.ogg` | Impact `impactSoft_medium_002.ogg` | 0.14 s |
| Bog Toad | magic | `npc_bog_toad_magic.ogg` | Sci-fi `lowFrequency_explosion_000.ogg` | 2.00 s |
| Dawn Moth | appear | `npc_dawn_moth_appear.ogg` | Sci-fi `laserRetro_000.ogg` | 0.24 s |
| Dawn Moth | hit | `npc_dawn_moth_hit.ogg` | Sci-fi `laserRetro_001.ogg` | 0.24 s |
| Dawn Moth | magic | `npc_dawn_moth_magic.ogg` | Sci-fi `laserSmall_001.ogg` | 0.25 s |
| Shade Stalker | appear | `npc_shade_stalker_appear.ogg` | Sci-fi `spaceEngineLow_001.ogg` | 5.00 s (first 2 s) |
| Shade Stalker | hit | `npc_shade_stalker_hit.ogg` | Impact `impactSoft_heavy_001.ogg` | 0.57 s |
| Shade Stalker | magic | `npc_shade_stalker_magic.ogg` | Sci-fi `explosionCrunch_003.ogg` | 1.55 s |
| Void Imp | appear | `npc_void_imp_appear.ogg` | Sci-fi `forceField_001.ogg` | 0.95 s |
| Void Imp | hit | `npc_void_imp_hit.ogg` | Sci-fi `forceField_003.ogg` | 0.96 s |
| Void Imp | magic | `npc_void_imp_magic.ogg` | Sci-fi `explosionCrunch_004.ogg` | 1.98 s |
| Pebble Golem | appear | `npc_pebble_golem_appear.ogg` | Impact `impactMining_001.ogg` | 0.87 s |
| Pebble Golem | hit | `npc_pebble_golem_hit.ogg` | Impact `impactMining_002.ogg` | 0.80 s |
| Pebble Golem | magic | `npc_pebble_golem_magic.ogg` | Impact `impactPlate_heavy_000.ogg` | 0.49 s |
| Storm Roc | appear | `npc_storm_roc_appear.ogg` | Sci-fi `laserRetro_002.ogg` | 0.26 s |
| Storm Roc | hit | `npc_storm_roc_hit.ogg` | Sci-fi `laserLarge_001.ogg` | 0.72 s |
| Storm Roc | magic | `npc_storm_roc_magic.ogg` | Sci-fi `laserLarge_002.ogg` | 0.74 s |
| Rival Witch | appear | `npc_rival_witch_appear.ogg` | RPG `bookOpen.ogg` | 0.15 s |
| Rival Witch | hit | `npc_rival_witch_hit.ogg` | RPG `drawKnife2.ogg` | 0.45 s |
| Rival Witch | magic | *(no new file — a random `spell_<element>.ogg`)* | The 10 Phase 38 spell sounds, picked at random each cast | — |
| Rival Warlock | appear | `npc_rival_warlock_appear.ogg` | RPG `bookFlip1.ogg` | 0.77 s |
| Rival Warlock | hit | `npc_rival_warlock_hit.ogg` | RPG `drawKnife3.ogg` | 0.48 s |
| Rival Warlock | magic | `npc_rival_warlock_magic.ogg` | Sci-fi `spaceEngineLow_002.ogg` | 5.00 s (first 2 s) |

## How the build goes (proposal)

1. **Server, new migration only** (never edit the Phase 24
   migration): insert the 12 rows into `arena_private.npcs`
   (`on conflict (npc_id) do nothing`, like Phase 24). The
   `kind` column takes 'robot' / 'chef' / 'animal' today —
   propose `'magical'` for the ten elementals and `'witch'`
   for the rivals, but the builder checks what `kind` drives
   in `arena_fight_npc` before choosing.
2. **One new ability, `random_spell`, for the Rival Witch**
   (and the Rival Warlock reuses it too if Makenna wants the
   warlock to cast as well — as written he curses instead).
   Every other creature reuses an existing ability
   (`double_hit`, `shield`, `self_repair`, `vanish`, `flare`,
   `sugar_trap`, `shock`, `dodge`), so no other server fight
   code changes.
3. **Magic-sound flag (proposal):** `arena_fight_npc` returns
   a `creature_magic` flag on rounds where the special ability
   fired. The client plays `npc_<id>_magic` for that round's
   hit line instead of the regular hit sound. (Matching the
   ability line's text was considered and rejected — text
   matching is fragile if a line is ever reworded.)
4. **Client:** 12 new entries in `game_logic.NPCS` (with
   `appear_sound`, `hit_sound`, `magic_sound` — the witch's
   `magic_sound` is the special value `"random_spell"`,
   meaning "play a random `spell_<element>.ogg`", while the
   warlock's is his own `npc_rival_warlock_magic` file);
   `sounds.py` gains the 35 new `npc_*` entries (maxtime
   2000 for the 5.00-second files) plus a
   `play_creature_magic(npc_id)` helper; `main.py`
   `_play_sound_for_line` plays the magic sound when the
   round's flag says the special fired.
5. **Tests:** `test_game_logic.py` (the 12 NPCS entries,
   fair scaling at the fighter's level, the magic-sound
   mapping, rivals cast a random spell sound);
   `test_migrations.py` (the 12 rows replay cleanly, the
   pool is 21 creatures, every ability name the rows use
   exists in `arena_fight_npc`); `test_main_smoke.py`
   (a magic round plays the magic sound, a normal round
   plays the hit sound, the rivals' magic plays a spell
   sound).
6. **Upload:** the 35 files via the GitHub website, into
   `sounds/` with the exact filenames above. Until they are
   there, a creature with a missing file simply plays no
   sound for that moment — the fight carries on.

## Open for Makenna

- Approve (or rename) the 12 creature names and their
  abilities — especially the Rival Witch and Rival Warlock:
  keep them as "Rival Witch" / "Rival Warlock", or give them
  proper names?
- The rivals' magic: the witch reuses the 10 spell sounds —
  is that right, or should she have her own magic sound too?
  (The warlock has his own curse sound, `spaceEngineLow_002`.)
- Build all 12 at once, or split it (the 10 elementals
  first, the rivals after)?
