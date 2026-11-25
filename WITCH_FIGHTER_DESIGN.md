# Witch fighter — design draft (Makenna, 2026-11-25)

Status: **DRAFT ONLY. Not coded, not pushed to GitHub.** Written for
Makenna, Josh, and Kiro to review before any build starts.

Decided by Makenna on a voice call, 2026-11-25:
- The witch is a **THIRD playable fighter choice**, alongside robot and
  chef. Still **one fighter per player** — choosing witch does not give
  anyone a second fighter.
- The witch uses the **same narrator voices as now, picked by gender**
  (male voice `en-US-GuyNeural`, female voice `en-US-AriaNeural`) —
  **no separate witch voice**.
- **All elemental spells**: fire, water, ice, wind, poison, light,
  shadow, dark, plus any other elements that fit.
- **Each element gets its own story / voice line when cast**, and its
  **own royalty-free sound effect**.
- **More quest givers for the witch, with more voices**, and more
  quest ambience sounds, like the existing cleaning and gathering
  loops.

## Words about male witches — DECIDED (Makenna, 2026-11-25)

Yes, male witches exist. The common word for a male witch is
**warlock**. Wizard and sorcerer are also used. And "witch"
itself is often used for any gender.

**Decided by Makenna: in the game, if the player is male the
fighter is called a warlock, and if female the fighter is
called a witch.** The kind stored in the data stays `witch`
for everyone — one kind, one set of rules, so nothing in the
server, the save, or the DynamoDB conversion has to learn a
fourth kind. Only the words the player sees and hears change
with gender:

- The create screen offers "Witch fighter" as the third
  choice (with a spoken note that a male witch is called a
  warlock), and once the fighter exists the game calls them by
  gender: the Home tab, the More tab fighter line, and any
  spoken line that names the kind say **"warlock"** for a male
  fighter and **"witch"** for a female fighter.
- Fight lines are first person ("I hit the Scrap Rat for 11"),
  so they need no warlock/witch word at all. Giver lines use
  the fighter's name (Katprincess), not the kind, so they need
  no change either.
- The fighter-switching design is updated for the Nov 25, 2026
  decisions: switching to a witch resets weapon/armor, combat
  level, quest level, quest stats and reputation, and keeps
  Healing; the first switch is free, then 100 credits doubling
  (a proposal Makenna can tune).

## 1. Fighter kind and creation

Today, verified on GitHub main (2026-11-25):

- `game_logic.py`, `new_fighter(name, kind, gender)`: kind must be
  `"robot"` or `"chef"`, or it raises `ValueError("Pick robot or
  chef for your fighter.")`. Robot gets weapon "Laser Blaster" and
  armor "Scrap Plating"; chef gets "Trusty Spatula" and "Chef Apron".
- `main.py` has **two** create screens (first launch, and account
  creation), each with a RadioBox `choices=["Robot fighter",
  "Chef fighter"]`, and the kind is worked out as `"robot" if
  selection == 0 else "chef"`. **That 0-else mapping is a trap:**
  adding a third choice without changing it would make "Witch
  fighter" read as chef. The build must map by the choice itself,
  not by "0 means robot, anything else means chef".
- Server side, `supabase/migrations/20261118045430_baseline.sql`:
  the `players` table has `kind text not null check (kind in
  ('robot', 'chef'))` (line 56); `arena_private.new_fighter`
  picks weapon/armor with `case when p_kind = 'robot' then
  'Laser Blaster' else 'Trusty Spatula' end`; and
  `arena_create_account` rejects any kind not in
  `('robot', 'chef')` (line 568). **All three places must learn
  `'witch'`, in a NEW migration file only — never edit the
  baseline or any old migration.**

What changes for the witch:

- Kind: `"witch"`. Choice on the create screen: "Witch fighter"
  (with a spoken note that a male witch is called a warlock;
  see "Words about male witches" above — male fighter is
  called a warlock, female fighter is called a witch, stored
  kind stays `witch` for both).
- Weapon name (proposal, Makenna to approve): **"Spellbound Wand"**.
  Armor name (proposal): **"Mystic Robe"**.
- Gender still picks the voice only, exactly as now. Kind never
  picks the voice.
- The witch is open to everyone at creation, the same as robot
  and chef. No level, credit, or quest requirement to pick her.

## 2. Base damage — proposed 11

Today, verified on main:

- `game_logic.py`, `weapon_damage(fighter)`: `base = 12 if
  fighter["kind"] == "robot" else 10`. So robot hits for a base
  of 12, chef for 10. The full formula is base + 5 ×
  (weapon level − 1) + 2 × (fighter level − 1) + 2 × Strength.
- Server side, `arena_fight` in the baseline does the same thing:
  `dmg := (case when f ->> 'kind' = 'robot' then 12 else 10 end)`
  (line 830). **Note the same trap as the create screen:** as
  written, any kind that is not robot silently gets 10. A witch
  added without changing this line would silently hit like a
  chef. The build must change both places to an explicit
  three-way mapping.

Proposal: **witch base damage 11** — between robot (12) and chef
(10). Why:

- The witch's strength is variety, not raw power: she can call
  on eight or more elements, while robot and chef each have one
  way of hitting.
- 11 keeps her fair in a fight against a robot or a chef at the
  same level, weapon level, and Strength. She is not the
  hardest hitter, and she is not the weakest.
- It is one number in two places (client `weapon_damage` and
  server `arena_fight`), so it is easy to tune later if Makenna
  finds her too strong or too weak.

At level 1, weapon level 1, Strength 0, a witch hits for 11.
Makenna to confirm 11, or pick 10 (same as chef) or 12 (same
as robot) instead.

## 3. Stats, upgrades, and switching — the reset rules (DECIDED Nov 25, 2026)

Nothing about the witch changes the shared rules:

- Same 5 stats (strength, defense, health, speed, luck), 2 stat
  points per level, same XP curve, same +10 max HP per level.
- Same upgrade costs and times (25 × 1.5^(level−1) credits,
  60 seconds × level, 4-hour cap), same Healing skill
  (Second Wind, max level 5, 95%), same quest levels and quest
  stats (Charm / Renown / Insight).
- Same reputation tiers per giver (3 Helper, 8 Friend,
  15 Trusted Friend), same quest rewards and durations.

Switching to or from a witch follows the fighter-switching
design (`FIGHTER_SWITCH_DESIGN.md`, DECIDED Nov 25, 2026, built
in Phase 36 — `arena_switch_kind` in migration
`20261125210000_fighter_switching.sql`):

- Still one fighter. Switching to a witch renames weapon/armor
  ("Laser Blaster" → "Spellbound Wand", "Scrap Plating" →
  "Mystic Robe", and back again) and **resets weapon_level and
  armor_level to level 1** — a level 5 laser does NOT become a
  level 5 wand; the new fighter's weapon and armor start fresh
  and must be re-upgraded from scratch. Combat level and combat
  stats reset to level 1 / 0, quest level and quest stats reset
  to level 1 / 0, and reputation with every giver resets to 0.
  **Healing (Second Wind) stays at its current level**, credits
  stay apart from the switch cost, and wins, losses, name,
  gender and voice stay. This supersedes the Nov 18 carry-over
  rule (where upgrades and levels stayed).
- Cost: the FIRST switch is free; after that the first paid switch
  is 100 credits, doubling every switch, with no cap — a proposal
  Makenna can tune. The witch adds a third direction to switch in,
  not a new pricing rule.

## 4. Elemental spells — how they work in a fight

Makenna's list: **fire, water, ice, wind, poison, light,
shadow, dark**, plus any others that fit. Proposed extras:
**earth** and **lightning** — the two most obvious missing
ones, bringing the set to ten. (Light, shadow, and dark are
kept as three separate elements, exactly as Makenna named
them, even though they sound close: light heals and blinds,
shadow hides and chills, dark drains.)

### Phase 1 (this draft): flavour first, same damage

Fights in Arena of Makers are automatic — there is no
per-round choice of what to do, and adding one would change
how every fight plays. So for the first build:

- Each time the witch hits, the game picks **one element at
  random** for that hit, speaks that element's cast line in
  the player's own voice (first person, like all fight lines
  since Phase 28), and plays that element's sound.
- **All elements do the same damage in Phase 1** — the
  weapon_damage number above. No element is stronger or
  weaker than another, so nothing can unbalance a fight and
  nothing needs re-tuning.
- No new stored field is needed in Phase 1: the element is
  picked per hit and not saved. That means **no migration
  field, no compatibility risk, and nothing for an older
  fighter to be missing**.

### Later (not in this build): real elemental effects

Only if Makenna wants it after playing Phase 1:

- Elemental strengths and weaknesses — for example fire
  strong against ice creatures, water strong against fire
  creatures. This needs a small table (element vs. creature
  kind) and would change damage, so it is a separate decision.
- A favourite element the player picks and keeps, stored as a
  plain text field (see §7 for the compatibility shape).
- Element-specific quest bonuses, for example a fire quest
  paying a little extra to a witch who just cast fire. Not
  designed here.

## 5. Cast lines — one per element, first person

Spoken in the player's own voice (Guy or Aria), in first
person like the rest of the fight narration. One line each,
kept short so it never holds up the fight. Makenna can
rewrite any of them — these are starting lines, not final
words.

| Element | Cast line (first person) |
|---|---|
| Fire | "I call the fire, and it bursts from my wand!" |
| Water | "I call the water, and it rushes where I point!" |
| Ice | "I call the ice, and the air turns sharp and cold!" |
| Wind | "I call the wind, and it howls around me!" |
| Poison | "I brew the poison, and it curls through the air!" |
| Light | "I call the light, and it shines too bright to face!" |
| Shadow | "I call the shadows, and they gather at my side!" |
| Dark | "I call the dark, and it drinks the light away!" |
| Earth | "I call the earth, and the ground answers me!" |
| Lightning | "I call the lightning, and the sky cracks open!" |

How it sounds in a fight (example): "I call the fire, and it
bursts from my wand! I hit the Scrap Rat for 11." The cast
line and the hit line are two lines in the same narration,
spoken in order, with the element's sound under the cast
line — the same pattern as a creature appearing, then the
fighter hitting.

## 6. Element sound effects — proposed sources (NOT yet downloaded)

**Nothing in this section has been downloaded or verified yet.
Each file must be checked on its own source page before it is
used, and uploaded through the GitHub website in the browser,
never through the GitHub tools (they reject audio files).
This is the rule in `SOUNDS.md`: do not use a different file
from the same pages without checking its licence first.**

Filename pattern (proposal, following the existing sounds):
`witch_fire.wav`, `witch_water.wav`, and so on — one file per
element, in `sounds/`, listed in `sounds.py` `SOUND_FILES`
like the other effects. A missing file plays nothing and never
stops the game, exactly like the other sounds.

Proposed sources per element — search term, where to look, and
the licence to check on the page:

| Element | What to look for | Where (licence to check on the page) |
|---|---|---|
| Fire | fire whoosh / fire burst | Freesound, CC0; or Pixabay Content License |
| Water | water splash / rushing water | Freesound, CC0; or Pixabay Content License |
| Ice | ice crack / freezing shimmer | Freesound, CC0; or Kenney CC0 packs |
| Wind | wind howl / gust | Freesound, CC0; or Pixabay Content License |
| Poison | bubbling potion / hiss | Freesound, CC0; or Pixabay Content License |
| Light | bright chime / shimmer | Kenney CC0 (Music Jingles / RPG Audio); or Freesound CC0 |
| Shadow | low whisper / dark swell | Freesound, CC0; or Pixabay Content License |
| Dark | deep drone / draining hum | Freesound, CC0; or Pixabay Content License |
| Earth | rumble / stones shifting | Freesound, CC0; or Kenney Impact Sounds, CC0 |
| Lightning | thunder crack / zap | Kenney CC0 (zap sounds, like the robot laser pick); or Freesound CC0 |

Licences that are fine, as in `SOUNDS.md`: **CC0** (public
domain, no credit needed), **Pixabay Content License** (free
for commercial use, no credit needed, do not sell the file on
its own), **Kenney CC0**, **Mixkit Sound Effects Free License**
(sound effects only — **Mixkit music is banned for games**).
**Not fine:** anything marked CC BY-NC (non-commercial), or any
file whose licence page cannot be found. Incompetech music is
CC-BY 4.0 and needs the Kevin MacLeod credit line — that is
for music, not for these short effects, and no new Incompetech
music is proposed here.

If a good file cannot be found for an element, that element
simply plays no sound until one is found — the cast line still
speaks, and the fight carries on. Never hold the whole witch
build for one missing sound.

## 7. New quest givers for the witch

Today, verified on main (`quests.py`): six givers, three male
and three female, each with their own Edge voice, chosen by
character, never by the player's gender:

- Bolt (male, `en-US-ChristopherNeural`), gruff robot foreman
- Marge (female, `en-US-JennyNeural`), warm head chef
- Pip (male, `en-US-EricNeural`), excitable young inventor
- Dot (female, `en-US-MichelleNeural`), calm repair drone
- Gus (male, `en-US-AndrewNeural`), old grill master
  (Phase 27: Davis was dead, replaced by Andrew)
- Belle (female, `en-US-EmmaNeural`), cheerful baker
  (Phase 27: Sara was dead, replaced by Emma)

Proposal: **four new givers, two male and two female**, so the
hangout becomes ten givers, five male and five female, keeping
the balance Makenna asked for. Makenna said to be creative
with their names — Hazel, Rowan, Wren, and Bram below are the
creative picks in this draft, and she can rename any of them.
Their quests are open to
**every fighter**, robot, chef, and witch alike — fighter kind
never locks anyone out of a quest, the same rule as today.
The new givers simply give the witch-flavoured corner of the
hangout its own people.

| Giver | Voice (proposal) | Personality | Quest types |
|---|---|---|---|
| Hazel, the herb witch | `en-US-AvaNeural` (female) | Warm, knows every plant and what it heals | Herb gathering, drying herbs, making teas |
| Rowan, the storm caller | `en-US-RogerNeural` (male) | Lively, laughs at thunder, calms storms | Calming storms, catching wind, reading clouds |
| Wren, the moonlight enchanter | `en-US-AnaNeural` (female) | Bright, young, up all night, loves the moon | Moonlight rituals, charging crystals, night watch |
| Bram, the old warlock | `en-US-SteffanNeural` (male) | Slow, calm, keeper of shadows, never in a hurry | Mending shadows, keeping dark things friendly, old lore |

**Voices must be tested before use — this is the Phase 27
lesson.** Gus's Davis and Belle's Sara looked fine on paper
and were dead in Microsoft's live voice list. The four voices
above were in the Edge voice list as of 31 October 2026
(Ava, Roger, Ana, Steffan are all listed en-US voices, and
none is already used by a giver or by the player's Guy/Aria
voices), but that is not proof they work through edge-tts
today. The build must run the same live voice check Phase 27
used, and if one is dead, pick another unused en-US voice —
never reuse a giver's voice, or two givers would sound like
the same person.

Reputation works exactly as today, per giver: +1 for each
finished quest, tiers 3 Helper (+25% credits on that giver's
quests), 8 Friend (free weapon or armor upgrade, player's
choice, instant), 15 Trusted Friend (free Healing upgrade if
below max level 5, otherwise another gift, instant). New
givers start at 0 reputation for everyone, like every giver
did.

### Every giver can start a quest — the Belle rule (DECIDED)

**Rule: every giver must be able to start quests, including
being the first quest giver on the starting board.** No giver
may be reachable only in a later slot, only after another
giver, or only through a fresh-quest refresh. This applies to
all ten givers — the six who exist now and the four new witch
givers.

Why this is written down: Kiro told Makenna on the night of
2026-11-24 that **Belle could not start quests / be first on
the board**, and that it is being fixed as part of the AWS
port. The witch build must not repeat that bug, in either
version of the game.

What was checked: on Supabase main (2026-11-25), the code
does **not** exclude Belle. The client, `quests.py`
`starting_board`, shuffles all six givers and deals them in
order (`giver = givers[i % len(givers)]`), so Belle can land
in slot 1. The server,
`20261119020000_add_hangout_quests.sql`
`quest_board_ensure`, shuffles all six names and deals
`v_givers[1..5]`, so Belle can land in slot 1 there too, and
`quest_new`'s rotation array includes Belle twice. So the bug
Kiro found could **not** be verified from the public repo —
it is presumably in the AWS port code, which is not on GitHub
main, or in a path not yet found. That is stated plainly here
so nobody claims the Supabase code was the broken one.

The guard, for the witch build and for the AWS port alike:

- **One giver list, used everywhere.** The board deal and the
  fresh-quest deal must draw from the same list of givers — in
  the client (`quests.py`), in the server SQL, and in the
  DynamoDB / Lambda rewrite. Never a second, shorter list
  somewhere that quietly leaves a giver out.
- **A test that deals many boards.** Deal the starting board
  hundreds of times and assert that **every** giver appears in
  slot 1 at least once, and that every giver appears as a quest
  giver at all. Run the same test in the AWS port. A board of
  5 dealt from 10 givers will always leave some givers off any
  single board — that is fine. What must never happen is a
  giver who can never be first.
- **"Can start a quest" includes "can be heard."** Belle's
  voice was the Phase 27 fix (her Sara voice was dead, replaced
  by Emma). A giver whose lines fail to speak has, for a blind
  player, not really started the quest. The live voice check
  in §7 covers every giver, old and new, before the build is
  called done.

Example new quests (starting seeds, endlessly generated like
the rest — not a fixed list):

- **"Gather Moonpetal"** (Easy, Hazel): fetch three
  moonpetal leaves before dawn. Ambience: gathering.
- **"Brew the Calming Draught"** (Medium, Hazel): pick the
  right herbs in the right order; a wrong herb gets a kind
  "that would make it sneeze, not soothe" and you pick again.
  Ambience: brewing (new).
- **"Calm the Storm"** (Medium, Rowan): talk a little storm
  cloud down before it soaks the hangout. Ambience: storm (new).
- **"Charge the Moonstone"** (Easy, Wren): hold the stone
  steady in the moonlight until it glows. Ambience: moonlight
  (new).
- **"Mend the Shadow"** (Hard, Bram): a shadow has torn loose
  and is frightening the drones; stitch it back gently, in
  three steps. Ambience: moonlight (new).
- **"The Witch's Fair"** (Hard, co-op, Hazel): the whole
  hangout holds a witch fair — potion stall, herb stall, and
  fortune stall — like the Grand Hangout Fair, full reward for
  everyone who joins. Ambience: brewing (new).

## 8. Quest ambience loops

Today, verified on main (`quests.py`, `sounds.py`): four
ambience kinds — cooking (reuses `chef_sizzle`), repair
(reuses `robot_servo`), gathering
(`ambience_gathering.mp3`), cleaning
(`ambience_cleaning.mp3`). A quest whose ambience file is not
in `sounds/` yet is silent, never an error.

Proposed new ambience kinds, one loop file each, same rules
(missing file = silent, upload via the GitHub website):

| Ambience | Sound | Used by | Proposed source (licence to check) |
|---|---|---|---|
| brewing | bubbling potion, soft and steady | Hazel's potion quests, the Witch's Fair | Freesound CC0 ("potion bubbling"); or Pixabay Content License |
| storm | wind and soft rain | Rowan's storm quests | Freesound CC0 ("wind rain loop"); or Pixabay Content License |
| moonlight | quiet night, soft crickets | Wren's and Bram's night quests | Freesound CC0 ("night crickets"); or Pixabay Content License |

Existing ambience kinds are reused where they fit: witch herb
quests use gathering, a witch mending a broken cauldron uses
repair. No new ambience kind is added for a single quest.

Filenames (proposal): `ambience_brewing.mp3`,
`ambience_storm.mp3`, `ambience_moonlight.mp3`, listed in
`sounds.py` `AMBIENCE_SOUNDS` the same way gathering and
cleaning are. All three are loops, so they should be gentle
enough to sit under the music and the giver's voice — the same
"half the effects volume" feel as the music.

## 9. Compatibility — the rule, applied to every touch point

Makenna's standing rule (2026-11-18): new logic must be
compatible with existing fighters and start at level zero —
missing fields default to 0, never a direct read that crashes.
This build touches kind in many places, so the checklist is:

| Place (verified on main, 2026-11-25) | What must change | Compatibility note |
|---|---|---|
| `game_logic.py` `new_fighter` | Accept `"witch"`; weapon "Spellbound Wand", armor "Mystic Robe" | New fighters only; old fighters untouched |
| `game_logic.py` `weapon_damage` | Explicit three-way base: robot 12, chef 10, witch 11 | Never `else 10` — an unknown kind must not silently become a chef |
| `main.py` two create screens | Add "Witch fighter" to both RadioBoxes; map by choice, not by `0 else` | Old saved fighters never pass through this screen |
| `sounds.py` `play_hit` / `play_intro` / `play_creature_hit` | Witch branch: hit = element sound, intro = a soft chime / shimmer (proposal), creature hit = a dull thud that fits any fighter | Missing element file = silence, never a crash (the existing pattern) |
| `main.py` `_play_sound_for_line` | Witch hit lines ("I hit the …") already go through `play_hit(kind)`, so the witch branch above covers them | No new line matching needed |
| Server `players.kind` CHECK | New migration: `check (kind in ('robot', 'chef', 'witch'))` | Old rows are robot/chef and still pass the new check |
| Server `arena_private.new_fighter` | `case` for witch weapon/armor names | New fighters only |
| Server `arena_create_account` | Accept `'witch'` in the kind validation | Rejects anything else, as now |
| Server `arena_fight` damage | Explicit three-way base: robot 12, chef 10, witch 11 | Same as the client — the two must match, or fights would feel different online and off |
| Server `fighter_out` / `apply_timers` | Any new field read with `coalesce(..., 0)` | The Phase 30 lesson: the Healing crash happened because the server read `healing_level` with no coalesce to 0 |
| `quests.py` `GIVERS` | Append the four new givers | Old givers, voices, and reputation counts untouched. **Belle rule:** the board deal and the fresh-quest deal draw from the same single giver list, and a test deals many boards and asserts every giver lands in slot 1 at least once (see §7) |
| `quests.py` `AMBIENCE_SOUNDS` | Add brewing / storm / moonlight | Old ambience kinds untouched |
| Tests | New tests: witch creation, witch damage at level 1, switching robot → witch resets weapon/armor/levels to 1 and keeps Healing, unknown kind rejected, old fighter (no witch fields) loads fine, **every giver appears first on the board across many deals** | Follow the existing test files (`test_game_logic.py`, `test_migrations.py`); all four suites must pass before pushing, as in Phase 30. The same giver-first test must run in the AWS port for the Belle fix |

**New fields:** Phase 1 needs **no new stored field at all**
(element is picked per hit, not saved). If a favourite
element is added later, it is one plain text field, for
example `fighter["element"]`, default `"fire"`, read with
`.get("element") or "fire"` on the client and
`coalesce(...,'fire')` on the server — never a direct read.
The same shape applies to any future witch field: default 0
for numbers, a safe word for text, and the game must work
with the field missing.

**Do-not-touch items:** password sign-in, `remember.py`
auto-login, the private `arena_private` schema rules, and
Kiro's anti-cheat work (commit 29ad230). The witch build
adds a kind and some sounds; it does not change how anyone
signs in.

## 10. DynamoDB / AWS portability — for the later conversion

Makenna's plan (2026-11-25): keep building and playing on
Supabase and the current PC app until everything — player
data, rules, all game data — is converted to DynamoDB for
AWS and the Magic Worlds Alexa skill. The witch design is
kept portable on purpose:

- **Kind is a plain string** (`"robot"`, `"chef"`,
  `"witch"`). No Postgres enum, no database-only type. In
  DynamoDB it is one string attribute, and the same three
  words are the whole allowed set.
- **Elements are plain strings** (`"fire"`, `"water"`, …).
  No table of elements is needed in Phase 1; if one is added
  later, it is a plain list of strings, the same in either
  database.
- **Givers are plain data** — a list of name / voice /
  gender / personality. That list becomes DynamoDB items just
  as easily as it is a Python list today. No giver logic
  lives only in SQL.
- **Sounds are plain filenames** in `sounds/`. The Alexa
  version will need them in the audio format Alexa accepts
  (Alexa rejects audio in the wrong format, unlike a Windows
  computer), and Alexa speech has a hard 8-second limit — so
  the cast lines above are kept to one short sentence each,
  and the element sounds should be kept short (a second or
  two) so they fit inside a spoken turn.
- **The rules live in this document, not only in SQL.** The
  `arena_*` server functions will have to be re-written as
  Lambda / DynamoDB logic in the conversion. Anything this
  draft says only as "the migration does X" should be
  re-checked against this document when Kiro does that
  rewrite, so the witch does not lose a rule in the move.
- **Credit lines travel with the game.** The CC-BY music
  credit (Jazz Brunch and Mesmerizing Galaxy Loop by Kevin
  MacLeod, incompetech.com, CC BY 4.0) is planned for the
  Alexa store description when Arena of Makers joins Magic
  Worlds. The same credit stays in `SOUNDS.md` and in the PC
  game. New witch sounds are CC0 / Pixabay / Kenney, so they
  need no credit line in the store description.

## 11. Build order — small pieces, in this order

1. **Design approval** (this document): Makenna, Josh, and
   Kiro read it; Makenna answers the open questions below.
2. **Kind plumbing:** client + server accept `"witch"`,
   with the new migration, tests, and a push to main. No
   spells yet — just a witch who can be created and who
   fights with the base damage and the wand/robe names.
3. **Elements:** cast lines + one sound per element, random
   element per hit. Upload the sounds through the GitHub
   website; any element without a file yet stays silent.
4. **Quest givers:** four new givers, their voices (tested
   live first), their quest seeds, and reputation working
   exactly like the existing six.
5. **Ambience loops:** brewing, storm, moonlight — uploaded
   through the GitHub website, wired into `AMBIENCE_SOUNDS`.
6. **Play-test by ear:** Makenna plays a witch fight, a
   witch quest with each new giver, and a 5-minute update, and
   says whether the voices and sounds feel right — the same
   "confirm by ear" step as Phase 27.
7. **Handover note in PROPOSALS.md** for Kiro, so the
   DynamoDB conversion carries the witch rules over (see §10).

Each piece is pushed to main on its own, with its tests
passing, and the game is played between pieces — Makenna's
test-as-you-go rule from Magic Worlds.

## 12. Open questions for Makenna, Josh, and Kiro

1. **Base damage:** is 11 right for the witch, or should
   she be 10 (same as chef) or 12 (same as robot)?
2. **Weapon and armor names:** "Spellbound Wand" and "Mystic
   Robe" — keep, or different names?
3. **Warlock / witch naming — DECIDED (Makenna, 2026-11-25).**
   Male fighter is called a warlock, female fighter is called
   a witch; stored kind stays `witch` for both. No longer an
   open question — see "Words about male witches" above.
4. **Elements — flavour only, or real effects?** Phase 1
   here is flavour only (same damage, random element per
   hit). Should any element do something different in a fight
   from the start, or wait until after playing Phase 1?
5. **Extra elements:** earth and lightning are proposed as
   the two extras. Keep them, drop them, or add others
   (nature, moon, spirit, storm)?
6. **Cast lines:** rewrite any of the ten lines in §5, or
   keep them as the starting lines?
7. **New givers:** Hazel, Rowan, Wren, Bram — keep the names
   and personalities, or change any? And are the proposed
   voices right, once they are tested live?
8. **Ambience loops:** brewing, storm, moonlight first, or a
   different set? Any loop that should come before the others?
9. **Switching cost:** switching to a witch costs credits
   like any other switch — the FIRST switch is free, then the
   first paid switch is 100 credits, doubling every switch, with
   no cap (a proposal from the Phase 36 build, Nov 25, 2026).
   Is 100 credits doubling the right price, or should it be tuned?
10. **Phase number:** the latest built phase is Phase 33.
    Is the witch the next phase (Phase 34), or should it
    wait behind anything else Kiro has queued?
11. **Belle fix in the AWS port (for Kiro):** the Belle
    "cannot start a quest" bug Kiro found on 2026-11-24 could
    not be verified from the public repo (see §7) — is the fix
    in, and does the port run the every-giver-first test?

## What was checked, and what was not verified

Checked on GitHub main, 2026-11-25 (repo
joshklander/arena-of-makers, branch main): `game_logic.py`
`new_fighter` and `weapon_damage`; `main.py` create screens
and `_play_sound_for_line`; `sounds.py` `SOUND_FILES`,
`play_hit` / `play_intro` / `play_creature_hit`; `quests.py`
`GIVERS`, quest templates, ambience kinds; baseline
migration kind check, `new_fighter`, `arena_create_account`,
and `arena_fight` damage; the 14 migration files on main,
latest `20261119231000_log_credits_in_events.sql`
(Phase 33). The local designs read: `FIGHTER_SWITCH_DESIGN.md`,
`HANGOUT_QUESTS_DESIGN.md`, `QUEST_LEVELS_DESIGN.md`, and
`SOUNDS.md`.

Not verified in this draft: no elemental sound file has been
downloaded or had its licence page checked — §6 is a sourcing
plan, not a sourced list. The four new giver voices have not
been tested live through edge-tts (see §7). The DynamoDB
conversion plan document was added to the repo on 2026-11-20
and removed from the public repo the same day, so its current
contents were not read here. The Belle "cannot start a quest"
bug Kiro reported on 2026-11-24 could not be verified from the
public repo — the Supabase code on main includes Belle in the
shuffled starting-board deal (see §7) — so it is presumably in
the AWS port code, which is not on GitHub main. No code was written and nothing
was pushed for this draft.

## Magical fight creatures — idea (Makenna, Nov 25, 2026)

Add magical creatures and other witches and warlocks into the pool of
creatures you can fight, alongside the 9 Phase 24 creatures. Same rules:
at the fighter's own level, fair matchmaking, each with its own appear
and hit sounds (royalty-free, licence checked, audio via the GitHub
website only). Added Nov 25: each new creature ALSO has its own different
magical attack sound, distinct from the others.

## Spell study — future idea (Makenna, Nov 25, 2026 — NOT building now)

A study where witches and warlocks go to upgrade their spells. The wand
upgrade helps, but on top of it there are timers where you go into the
study to learn spells.

DECIDED Nov 25, 2026: learning spells costs NO credits at all —
it is time-based only, not credit-based. Not decided: which spells
it teaches, how long the timers are, whether the study is
witch-only or open to every fighter, and whether study timers use
the same 4-hour cap as upgrades and quests (the standing rule says
timers cap at 4 hours — confirm when this is built).

DECIDED Nov 25, 2026: at first a witch attacks only with her wand, no
spells — the wand is basically like a melee weapon — until she goes to the
study and starts learning spells there. Once she has learned her elemental
spells, the spells are used more than the wand; the wand is barely used
then, basically just backup if a spell does not work.

DECIDED Nov 25, 2026: learning a spell in the study takes real time, like
repairs and upgrades, with the same max of four hours as everything else.
There are different spells for each element, in five tiers — common,
uncommon, rare, epic, legendary — for every element. Makenna said Maren
can come up with the names for all the tiers. The names below are Maren's
PROPOSALS, not decided — Makenna can rename any of them.

| Element | Common | Uncommon | Rare | Epic | Legendary |
|---|---|---|---|---|---|
| Fire | Ember Spark | Flame Lash | Burning Veil | Inferno Roar | Phoenix Rebirth |
| Water | Splash | Tide Pull | Rushing Torrent | Deep Current | Ocean's Wrath |
| Ice | Frost Bite | Ice Shard | Frozen Hold | Blizzard Veil | Eternal Winter |
| Wind | Breeze Cut | Gale Rush | Storm Gust | Cyclone Dance | Skybreaker Tempest |
| Poison | Sting | Venom Drip | Toxic Cloud | Plague Bloom | Thorned Doom |
| Light | Glow | Sunbeam | Radiant Shield | Dawn Burst | Heaven's Light |
| Shadow | Shade Touch | Dark Whisper | Shadow Bind | Nightmare Veil | Eclipse |
| Dark | Gloom Bolt | Midnight Coil | Abyss Call | Void Rend | Oblivion |
| Earth | Pebble Toss | Stone Grip | Rockslide | Mountain Roar | Titan's Awakening |
| Lightning | Static Zap | Spark Chain | Thunder Crack | Storm Surge | Tempest Crown |

DECIDED Nov 25, 2026: learning a spell costs no credits — it is
time-based only. Not decided: how long each tier's timer is
(within the 4-hour max), whether the study is witch-only or open to
every fighter, and whether higher tiers need lower tiers learned first.

DECIDED Nov 25, 2026: study learning acts like quests, not like repairs
and upgrades — a spell is only learned while you are in the study. Leave
the study and the learning clock pauses, resuming with the same remaining
time when you come back (same as the quest clock pausing outside the
hangout). Repairs and upgrades keep ticking while you are away; study
learning does not. Makenna's reasoning, like school: you cannot put
studying down and expect it to get done — you have to sit there and be
willing to do it. Players who do not want to sit and wait have other
paths: a witch can just upgrade her wand endlessly, or play a chef or a
robot, where progress is based on upgrades only, not on waiting and
patience for spells.

DECIDED Nov 25, 2026 (next build, Makenna approved the study as next):
the study is not only for learning spells — it also has quests, from
other witches and warlocks in there, doing stuff for them, with quest
ambience sounds like the hangout quests. The study also gets its own music
track AND ambience, exactly like the hangout and fighting have their own
music (Maren to help find a good royalty-free track, licence checked).
And periodic status updates in the study, like the hangout's 5-minute
updates: spell upgrades, quests, and repairs — it tells you when repairs
are done if you need repairs. CORRECTION Nov 25: the periodic status
updates are TTS in the PLAYER'S voice, not the givers' voices; sound
effects are only for the quest ambience and the study music track. (A
giver's own quest lines stay in that giver's voice, as in the hangout.)

SPELL TRAINER RULE — DECIDED Nov 25, 2026 (Makenna, voice call): when
you learn a spell, it is TAUGHT to you by another warlock or witch — a
trainer — and the teaching lines speak in the TRAINER'S voice, not the
player's voice. DECIDED the same day: the trainer update goes in WITH
the Phase 38 push (not after), so Makenna can test it right away, and
the trainer talks to her DIRECTLY, like the hangout quest givers do —
addressing her by name (Katprincess), with personality and rotating
lines, because that gives it more personality. BUILT in Phase 38
(spells.py, main.py — client-side only, no server change, no new
migration): the trainers are the four study givers, by the same
families the ambience uses — Hazel (Ava) teaches fire, water and
poison; Rowan (Roger) teaches wind, lightning and earth; Wren (Ana)
teaches ice, light, shadow and dark; Bram (Steffan), the old warlock,
teaches spell upgrades, any element, level 2 and up. All four voices
verified alive on Microsoft's live Edge list Nov 25, 2026 (Phase 27
lesson: never assume a voice is alive). Each trainer has three
rotating opening lines (start, and resume of a paused spell) and
three rotating completion lines, plus three Bram upgrade lines
naming the new level; every line is under 25 words for Alexa's
8-second limit, and the same spell always gets the same line
(picked from the spell's name, like a quest variant). The cast line
in a fight stays first-person in the player's voice (it is the
player casting), and the 5-minute study status update stays in the
player's voice; only the teaching is the trainer's. If a trainer
or voice is ever missing, the game falls back to the player's
voice alone, never a crash. Makenna can reassign trainers when
she tests them — only the mapping in spells.py changes.
Study audio, Nov 25: when a spell finishes learning it plays that
spell's actual sound effect. Study quests start about every 10 to 15
minutes. Audio layers over the study music bed: if you are not on a quest
you hear the ambience loop of the spell you are learning; if a quest has
started you hear the quest ambience instead, still over the music.

AUTO-STUDY RULE — DECIDED Nov 25, 2026 (Makenna, voice call, after
testing Phase 38): the player does NOT choose which spell to learn.
The Study tab has one button, "Enter study". Pressing it starts the
study: the study music plays, spell learning starts automatically, and
study quests trigger automatically. Spells are learned ONE AT A TIME —
never two at once — picked at RANDOM from all the spells not yet learned,
across all ten elements, so you do not learn all of one element first;
within one element the tiers still go in order (common before uncommon
and so on). When one spell finishes, the next random one starts on its
own, as long as the player is still in the study. Leaving the study
still pauses the learning clock, as before. To build as Phase 39
(authored Nov 25, 2026; tests and push need Makenna's yes).
Phase 38b is CANCELLED — Makenna decided Nov 25, 2026 that the
auto-study, the no-credit fix, the battle-spell matchups and the
12 magical creatures all go together in Phase 39, because then
it is easier to test everything. Do not frame anything as 38b
any more.

BUILT as part of Phase 39 (authored Nov 25, 2026, NOT tested or pushed yet):
the auto-pick itself is client-side only, using the existing
arena_study_start, which already refuses a second spell while
one is learning (the no-credit part of Phase 39 DOES add a new
migration, 20261125233000_study_free_learning.sql — see the
NO-CREDIT RULE below). spells.py
gains next_study_candidates (one next spell per element) and
pick_next_study_spell (random among the first learnings while
any are left; random among the upgrade candidates once all 50
are learned). The Study tab has one button, "Enter study"
(main.py enter_study): it starts the music, starts learning the
picked spell, and starts study quests on their own. The first
spell asks Yes/No once, naming the time (no cost — learning is
free) and that the study will keep teaching on its own while
the player stays here; saying no stops the whole enter. When a
spell finishes, _auto_start_next_study picks the next one on its
own, with no second question. Leaving the tab still pauses the
learning clock. A robot or chef pressing Enter study gets quests,
not spells. Trainers, cast lines, the 5-minute update, music and
ambience layering, the 4-hour cap, and times are all unchanged
from Phase 38.

NO-CREDIT RULE — DECIDED Nov 25, 2026 (Makenna, voice call):
learning spells costs NO credits at all. It is time-based only,
not credit-based. The credit cost was only ever a builder
proposal (common 25 credits … legendary 400) and is removed
entirely — client and server. New migration
20261125233000_study_free_learning.sql re-issues
arena_study_start with no credit charge or check and drops
arena_private.spell_cost; spells.spell_cost and SPELL_COSTS are
gone; game_logic.study_start no longer touches credits; the
Enter-study question names only the time; auto-start after a
spell finishes has no credit check, so being broke never blocks
learning. Times stay as proposed: common 15 minutes, uncommon
30, rare 60, epic 2 hours, legendary 4 hours (the cap); learning
all 50 spells once takes about 77.5 hours of study.

BATTLE SPELLS — DECIDED Nov 25, 2026 (Makenna, voice call),
BUILT as part of Phase 39 (authored Nov 25, 2026, NOT tested or
pushed yet): creatures use spells in battle too, and the game
picks YOUR best spell against that enemy automatically — "your
hit sounds like your spell and their hit sounds like their
spell", so you can hear whose magic is whose. The matchup chart
is Pokemon-style: our elements map fire→Fire, water→Water,
ice→Ice, wind→Flying, poison→Poison, light→Fairy, shadow→Ghost,
dark→Dark, earth→Ground, lightning→Electric; a strong spell does
double damage (2x), a weak one does half (0.5x), neutral is normal
(1x). Two pairs do NO damage at all (0x): lightning does no
damage to an earth creature, and earth does no damage to a wind
creature — the Pokemon immunities (Electric has no effect on
Ground; Ground has no effect on Flying). The chart lives only in
spells.py (STRONG_AGAINST / WEAK_AGAINST / NO_EFFECT_AGAINST plus
spell_multiplier) — no other file hard-codes it. The ranked
auto-pick: best = most damage (the spell's level bonus times the
affinity); if the best is not learned yet it picks the second best,
and so on down the ranking; it NEVER picks a spell that does 0
damage against that enemy; if no learned spell does any damage, or
no spell is learned yet, the witch fights with her wand — the wand
is hardly used once many spells are known. The affinity multiplies
the whole spell hit (client spells.spell_hit_damage, server
arena_fight / arena_fight_npc — the server decides online damage,
so the multiplier lives there too, in migration
20261125234000_battle_spell_affinities.sql, which also drops the old
random spell_pick). Creatures use the SAME spells the player uses
(same names, cast lines and sounds). The witch herself has no
element, so a creature's spell hits her at normal damage; the 9
Phase 24 creatures have no element, so affinities are neutral
against them. CHART CORRECTION (builder, Nov 25, 2026 — needs
Makenna's confirmation): the draft listed Lightning in BOTH Wind's
strong and weak lists, and Wind in BOTH Lightning's strong and weak
lists — a multiplier cannot be both 2x and half. Resolved
Pokemon-correct: wind vs lightning is half, lightning vs wind is
2x, and the "scatters the storm" thematic link is dropped. Makenna
can change any link in the chart.
