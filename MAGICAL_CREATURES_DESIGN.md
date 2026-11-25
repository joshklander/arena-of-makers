# Magical creatures — Phase 39 (authored Nov 25, 2026, NOT tested or pushed yet)

Written Nov 25, 2026, as the next tested piece after the Phase 38
witch study. Built as part of Phase 39 (auto-study + no-credit learning + battle-spell affinities + these 12 creatures, all in one phase, Makenna Nov 25, 2026 — Phase 38b is cancelled/superseded). **Decided by Makenna Nov 25, 2026 (voice call):** add
magical creatures and other witches/warlocks into the pool of
creatures you can fight, alongside the 9 Phase 24 creatures. **Added
the same day:** each new creature also has its own different
**magical attack sound**, distinct from the others — not just an
appear and a hit sound. (SOUND RULE CHANGE, Nov 25, 2026: an
elemental's magic IS its own element's spell sound, already in the
game — see the sounds section — so each creature has two NEW sounds,
not three.)

**Why this is Phase 39, not Phase 38:** the study build was already
full (spells, Study tab, 4 givers, 6 quest templates, 15 sounds, a
migration, 3 test files). Twelve creatures × 3 sounds each, plus a
migration and new ability code, would overload it. The design below is built as Phase 39 (authored
Nov 25, 2026); the tests are not run yet and nothing is pushed, and no
sound has been uploaded.

## Battle spells — DECIDED Nov 25, 2026 (Makenna, voice call)

Creatures use spells in battle too — different spells for different
types of creatures. Each elemental creature casts its own element's
spell; the rivals cast elemental spells as well. **Sound rule:** your
hit sounds like YOUR spell, and their hit sounds like THEIR spell, so
you can hear whose magic is whose. **Your spell is chosen for you:**
when your spells are chosen in battle, the game picks the best spell
against that enemy — type effectiveness, so fire is best against an
ice enemy, and so on. (Makenna's example: fire beats ice.) This is a
general witch battle rule, not only for these 12 creatures.

## Elemental matchup chart — REVISED PROPOSAL (Maren, Nov 25, 2026 — Makenna to approve or change)

Makenna's correction, Nov 25, 2026: water beating fire is the
iconic Pokemon matchup and the first draft missed it — water did
not beat fire at all. She asked for the chart to be researched from
Pokemon's real chart and made similar. Researched Nov 25, 2026 from
Pokemon's type chart (Scarlet/Violet and Go charts agree): Water is
strong against Fire, Ground and Rock and weak to Electric and Grass;
Fire is strong against Ice and weak to Water, Ground and Rock; Ice
is strong against Ground and Flying and weak to Fire; Electric is
strong against Water and Flying and weak to Ground; Ground is strong
against Fire, Electric and Poison and weak to Water and Ice; Poison
is strong against Fairy and weak to Ground; Fairy is strong against
Dark and weak to Poison; Ghost is strong against Ghost and weak to
Dark; Dark is strong against Ghost and weak to Fairy; Flying is
strong against Grass/Fighting/Bug and weak to Electric, Ice and Rock.

Our ten elements map to Pokemon types like this: fire→Fire,
water→Water, ice→Ice, wind→Flying, poison→Poison, light→Fairy,
shadow→Ghost, dark→Dark, earth→Ground, lightning→Electric.
Pokemon links are kept wherever they exist in our set; where
Pokemon has no link (Flying's targets are Grass/Fighting/Bug, none
of which we have; Fairy's other targets are Fighting/Dragon), a
thematic link fills the gap, marked ~. Damage follows Pokemon too:
strong = 2×, weak = ½× (the first draft's 1.5× is replaced).

| Attacker | Strong against (2×) | Weak against (½×) |
|---|---|---|
| Fire | Ice (Pokemon), Light (flames outshine gentle light) ~ | Water (Pokemon), Earth (Pokemon) |
| Water | Fire (Pokemon), Earth (Pokemon) | Lightning (Pokemon), Poison (pollutes the water) ~ |
| Ice | Earth (Pokemon), Wind (Pokemon) | Fire (Pokemon), Shadow (a shadow's touch is freezing) ~ |
| Wind | Poison (blows toxic clouds away) ~ | Ice (Pokemon), Lightning (Pokemon) |
| Poison | Light (Pokemon), Water (pollutes it) ~ | Earth (Pokemon), Wind (blown away) ~ |
| Light | Dark (Pokemon) | Poison (Pokemon), Fire (flames outshine it) ~ |
| Shadow | Shadow (Pokemon), Ice (a shadow's touch is freezing) ~ | Dark (Pokemon), Shadow (Pokemon) |
| Dark | Shadow (Pokemon), Lightning (void swallows sparks) ~ | Light (Pokemon) |
| Earth | Fire (Pokemon), Lightning (Pokemon), Poison (Pokemon) | Water (Pokemon), Ice (Pokemon) |
| Lightning | Water (Pokemon), Wind (Pokemon) | Dark (Pokemon) — plus Earth, NO DAMAGE, 0× (Pokemon: Electric has no effect on Ground) |

Notes: Earth keeps all three of Pokemon Ground's strengths, so it
is the strongest attacking element, just like Ground in Pokemon.
Light has only one strength and Dark only one weakness in this set,
because Pokemon's other links for Fairy and Dark (Fighting, Dragon,
Psychic, Bug) are not elements we have. Lightning has one weakness (Dark) plus the 0× against Earth;
Wind has one strength (Poison) — the wind/lightning link is
one-way, Pokemon-correct (see the correction note below). **No-effect affinities (0×) — DECIDED Nov 25, 2026
(Makenna): there are affinities, so lightning does ZERO damage to
an earth creature, and earth does ZERO damage to a wind creature —
the two Pokemon immunities in our set (Electric has no effect on
Ground; Ground has no effect on Flying). Every other Pokemon
affinity for our ten elements is already in the chart above (2× and
½×). **Wind/lightning correction (builder, Nov 25, 2026 — needs Makenna's confirmation):** the first draft listed Lightning in BOTH Wind's strong and weak lists, and Wind in BOTH Lightning's strong and weak lists — a multiplier cannot be both 2× and ½×. Pokemon is unambiguous (Electric is super effective against Flying; Flying is not very effective against Electric), so the build resolves it Pokemon-correct: wind vs lightning is ½×, lightning vs wind is 2×, and the "scatters the storm" thematic link is dropped. The chart above already shows the corrected version. Makenna can change any link. **Auto-pick rule — DECIDED Nov 25, 2026 (Makenna, refined):** it is
a ranked fallback, not just "strong first". The game picks the BEST
spell you have against that enemy — best meaning the most damage it
would do (spell level × the affinity against that enemy, so a 2×
spell at a lower level can still lose to a high-level neutral one).
If that best spell is not learned yet, it picks the second best, and
so on down the list. It never picks a spell that does no damage (0×)
against that enemy. So against an earth monster it picks water or
ice, never lightning. If no learned spell does any damage, or no
spell is learned yet, the witch fights with her wand, as decided in
Phase 38 — but once you know all the spells, or a lot of them, the
wand is hardly ever used. **Creatures:** an elemental creature
casts its own element's spell (same spell the player would cast —
same name, line and sound); the tier it casts at scales with the
creature's level — exact tier rule is still open for the Phase 39
build. The witch herself has no element, so a creature's spell hits
her at normal damage — affinities are spell-vs-creature-element.
The Rival Witch casts a random elemental spell (as already
proposed); the Rival Warlock's curse stays as his own thing.
**DECIDED Nov 25, 2026 (Makenna) — magic-sound rule change:** each elemental creature's magic IS simply its own element's spell
sound (`spell_<element>.ogg`, already in the game from Phase 38) — NOT a separate magic file. The 35-file proposal below is superseded:
each creature keeps its own appear and hit sounds (24 new files), the magic column is replaced by the element spell sound, and only the Rival
Warlock keeps his own magic file (his curse, `npc_rival_warlock_magic.ogg`). The Rival Witch's magic stays a random `spell_<element>.ogg`.
No new magic files are uploaded for the ten elementals.

## The rules (same as the Phase 24 creatures)

- At the **fighter's own level**, fair matchmaking — a creature is
  a multiplier on the Scrap Rat formulas, so a fight stays fair
  at any level.
- The fight pool picks **at random**: after this lands, manual
  Fight and auto-fight pick from **21 creatures** (9 Phase 24 +
  12 new).
- Each creature has its own **special ability** that fires every
  few rounds, with its own line, exactly like Phase 24.
- **Two new sounds per creature** (appear + hit), all different
  from each other and from every other creature's sounds, so you
  can tell who it is by sound alone — plus the **magic** sound
  when its special ability fires (its magical attack). The magic
  sound plays **instead of** the regular hit sound on that round.
  An elemental's magic IS its own element's spell sound
  (`spell_<element>.ogg`, already in the game — Makenna, Nov 25,
  2026, so your hit sounds like your spell and their hit sounds
  like their spell). The Rival Witch's magic is a random elemental
  spell sound (see the table) — she casts a real spell, so she
  sounds like one. The Rival Warlock's magic is his own curse sound.

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

## The sounds (PROPOSAL — 25 new files, all Kenney CC0)

**SOUND RULE CHANGE, Nov 25, 2026 (Makenna):** the 35-file proposal is superseded. An elemental creature's magic is its own element's spell sound (`spell_<element>.ogg`, already in the game from Phase 38) — no separate magic file for the ten elementals. So this section is now 24 new appear/hit files plus the Rival Warlock's curse file = 25 new files. The magic rows below show the element spell sound instead of a new file.

Every file below is from one of the four Kenney packs already
downloaded for Phase 38 (RPG Audio, Sci-fi Sounds, Impact
Sounds, UI Audio — all CC0, licence on each pack page and in
the zips' License.txt). Durations were measured with ffprobe
from the downloaded files. **Nothing has been copied into
`sounds/` yet and nothing has been uploaded** — the files live
in `phase38-witch-study/sounds-download/` until the build.
Audio goes up only via the GitHub website in the browser,
never via the GitHub tools.

The appear/hit files were picked to be **different from every sound
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
| Ember Sprite | magic | *(no new file — its own element's spell sound, `spell_fire.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Tide Wisp | appear | `npc_tide_wisp_appear.ogg` | Sci-fi `spaceEngineLow_000.ogg` | 5.00 s (first 2 s) |
| Tide Wisp | hit | `npc_tide_wisp_hit.ogg` | Impact `impactSoft_medium_001.ogg` | 0.18 s |
| Tide Wisp | magic | *(no new file — its own element's spell sound, `spell_water.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Frost Faerie | appear | `npc_frost_faerie_appear.ogg` | Impact `impactGlass_light_000.ogg` | 0.21 s |
| Frost Faerie | hit | `npc_frost_faerie_hit.ogg` | Impact `impactGlass_light_002.ogg` | 0.21 s |
| Frost Faerie | magic | *(no new file — its own element's spell sound, `spell_ice.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Gale Sylph | appear | `npc_gale_sylph_appear.ogg` | Sci-fi `spaceEngineSmall_001.ogg` | 5.00 s (first 2 s) |
| Gale Sylph | hit | `npc_gale_sylph_hit.ogg` | RPG `cloth3.ogg` | 0.48 s |
| Gale Sylph | magic | *(no new file — its own element's spell sound, `spell_wind.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Bog Toad | appear | `npc_bog_toad_appear.ogg` | Impact `impactSoft_heavy_000.ogg` | 0.51 s |
| Bog Toad | hit | `npc_bog_toad_hit.ogg` | Impact `impactSoft_medium_002.ogg` | 0.14 s |
| Bog Toad | magic | *(no new file — its own element's spell sound, `spell_poison.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Dawn Moth | appear | `npc_dawn_moth_appear.ogg` | Sci-fi `laserRetro_000.ogg` | 0.24 s |
| Dawn Moth | hit | `npc_dawn_moth_hit.ogg` | Sci-fi `laserRetro_001.ogg` | 0.24 s |
| Dawn Moth | magic | *(no new file — its own element's spell sound, `spell_light.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Shade Stalker | appear | `npc_shade_stalker_appear.ogg` | Sci-fi `spaceEngineLow_001.ogg` | 5.00 s (first 2 s) |
| Shade Stalker | hit | `npc_shade_stalker_hit.ogg` | Impact `impactSoft_heavy_001.ogg` | 0.57 s |
| Shade Stalker | magic | *(no new file — its own element's spell sound, `spell_shadow.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Void Imp | appear | `npc_void_imp_appear.ogg` | Sci-fi `forceField_001.ogg` | 0.95 s |
| Void Imp | hit | `npc_void_imp_hit.ogg` | Sci-fi `forceField_003.ogg` | 0.96 s |
| Void Imp | magic | *(no new file — its own element's spell sound, `spell_dark.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Pebble Golem | appear | `npc_pebble_golem_appear.ogg` | Impact `impactMining_001.ogg` | 0.87 s |
| Pebble Golem | hit | `npc_pebble_golem_hit.ogg` | Impact `impactMining_002.ogg` | 0.80 s |
| Pebble Golem | magic | *(no new file — its own element's spell sound, `spell_earth.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
| Storm Roc | appear | `npc_storm_roc_appear.ogg` | Sci-fi `laserRetro_002.ogg` | 0.26 s |
| Storm Roc | hit | `npc_storm_roc_hit.ogg` | Sci-fi `laserLarge_001.ogg` | 0.72 s |
| Storm Roc | magic | *(no new file — its own element's spell sound, `spell_lightning.ogg`, already in the game from Phase 38)* | Phase 38 spell sound | — |
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
3. **Magic-sound flag (built in Phase 39):** `arena_fight_npc` returns
   `creature_magic` (line index → sound key) on rounds where the
   special ability fired. The client plays that key for the round's
   line instead of the regular hit sound — `"spell:<element>"` for
   an elemental (its own element's spell sound), `"random_spell"`
   for the Rival Witch (a random `spell_<element>.ogg` each cast),
   `"npc_rival_warlock_magic"` for the Warlock's curse. (Matching
   the ability line's text was considered and rejected — text
   matching is fragile if a line is ever reworded, and the server's
   ability lines are second-person while the client's are
   first-person.)
4. **Client (built in Phase 39):** 12 new entries in `game_logic.NPCS` (with
   `appear_sound`, `hit_sound`, `magic_sound` — an elemental's is
   `"spell:<element>"`, the witch's is the special value
   `"random_spell"`, meaning "play a random `spell_<element>.ogg`",
   while the warlock's is his own `npc_rival_warlock_magic` file);
   `sounds.py` gains the 25 new `npc_*` entries (maxtime
   2000 for the 5.00-second files) plus a
   `play_magic_sound(sound_key)` helper (`"spell_<element>"` plays
   that element's cast sound, anything else plays that file);
   `main.py` `_play_sound_for_line` plays the magic sound when the
   round's flag says the special fired, and nothing else for that line.
5. **Tests:** `test_game_logic.py` (the 12 NPCS entries,
   fair scaling at the fighter's level, the magic-sound
   mapping, rivals cast a random spell sound);
   `test_migrations.py` (the 12 rows replay cleanly, the
   pool is 21 creatures, every ability name the rows use
   exists in `arena_fight_npc`); `test_main_smoke.py`
   (a magic round plays the magic sound, a normal round
   plays the hit sound, the rivals' magic plays a spell
   sound).
6. **Upload (NOT in the Phase 39 build task):** the 25 files via the GitHub website, into
   `sounds/` with the exact filenames above. Until they are
   there, a creature with a missing file simply plays no
   sound for that moment — the fight carries on.

## Open for Makenna

- Approve (or rename) the 12 creature names and their
  abilities — especially the Rival Witch and Rival Warlock:
  keep them as "Rival Witch" / "Rival Warlock", or give them
  proper names?
- The rivals' magic: **DECIDED Nov 25, 2026 (Makenna)** — the witch reuses the 10 spell sounds (a random one each cast), and every elemental's magic is its own element's spell sound. The warlock has his own curse sound, `spaceEngineLow_002`.
- Build all 12 at once, or split it (the 10 elementals
  first, the rivals after)? **DECIDED Nov 25, 2026 (Makenna): all 12 at once, in Phase 39, together with the auto-study, the no-credit fix and the battle-spell affinities — easier to test everything.**
