# Sounds and music — Arena of Makers

**All 9 sound effects plus the music are in the `sounds/` folder
on GitHub, on main (uploaded 2026-11-18, commit dc3923b), and
SOUNDS.md documents them below.** The game loads them
automatically — no downloading needed, no code change needed. If
a file is missing, the game just skips it and logs one
plain-words line, so it still runs fine but silent.

**One file was replaced after the first upload:**
`robot_laser.wav` was replaced 2026-11-18 with a more electric
zap (see the table below), uploaded through the GitHub website
the same evening (commit 7c3f772).

The Freesound picks from the first version of this file did not all
work out: only the 3 robot sounds could be downloaded from Freesound
(the other 6 kept returning HTTP 403 / AccessDenied). The missing
sounds were replaced with the picks below, all royalty-free and
checked on their own source pages. Do not use a different file from
the same pages without checking its licence first.

## Licences, in plain words

- **CC0 (Creative Commons 0)** — the maker gave the sound to the
  public domain. You can copy, change, share and use it, even for
  commercial purposes, without asking permission. No credit is
  required, but the makers are credited here anyway.
- **Pixabay Content License** — free to use for personal and
  commercial purposes, no attribution required. You may not sell
  or give away the sound file on its own, as a sound. Using it
  inside the game is fine.
- **Mixkit Sound Effects Free License** — free for commercial and
  personal projects, including games, no attribution required.
  (Mixkit *music* is NOT allowed in games — only its sound
  effects are used here.)
- **CC-BY 4.0 (Incompetech / Kevin MacLeod)** — free for
  commercial games, but a credit line is required. The credit
  lines are at the bottom of this file and must stay with the
  game (for example in the credits screen or here in SOUNDS.md).
- **Soundimage (Eric Matyas)** — free for commercial use,
  including games, but **attribution is required in the actual
  game**: "Music by Eric Matyas www.soundimage.org". (A paid
  non-attribution licence costs $30 per track and is NOT used
  here — the game uses attribution, so the cost is $0.)
- **DailySounds** — free for personal and commercial use, no
  sign-up, no credit required.

All Freesound sounds below are CC0. No CC BY-NC (non-commercial)
sound is used anywhere.

## The files in `sounds/`

| File | What it is | Used for | Source | Author | Licence |
| --- | --- | --- | --- | --- | --- |
| `robot_laser.wav` | Electric zap, 1.02 s, 88 KB — converted from OGG, volume 0.9 (the recording is loud) | Robot fighter hits | Kenney Digital Audio pack, `Audio/zap1.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `robot_servo.wav` | Servo 5, 0.75 s, 71 KB | Creature appears, robot fighter | https://freesound.org/s/740243/ | JoontheFloof | CC0 |
| `robot_clank.wav` | snd_metal_smash.wav — a hard metallic crash, 1.67 s, 157 KB | Scrap Rat hits a robot fighter | https://freesound.org/people/gristi/sounds/562198/ | gristi | CC0 |
| `chef_chop.wav` | Knife slice, 0.60 s, 104 KB — converted from OGG | Chef fighter hits | Kenney RPG Audio pack, `Audio/knifeSlice.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `chef_sizzle.wav` | Real frying sizzle, trimmed to the first 2.00 s, 345 KB — converted from MP3 | Creature appears, chef fighter | DailySounds, "Sizzling Eggs" — https://dailysounds.org/sounds/category/household | DailySounds | Free commercial, no credit |
| `pan_clang.wav` | Heavy metal hit, 0.36 s, 62 KB — converted from OGG | Scrap Rat hits a chef fighter (pan clang) | Kenney Impact Sounds pack, `Audio/impactMetal_heavy_001.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `win_jingle.wav` | Saxophone rising fanfare, 0.87 s, 150 KB — converted from OGG, volume raised (the sax recording was quiet: mean −19.5 dB, now −13.0 dB, peak −3.5 dB) | Winning a fight | Kenney Music Jingles pack, `Audio/Sax jingles/jingles_SAX02.ogg` — https://kenney.nl/assets/music-jingles | Kenney | CC0 |
| `loss_sound.wav` | Sad game over trombone, 5.61 s, 967 KB — converted from MP3 | Losing a fight | Mixkit, "Sad game over trombone" — https://mixkit.co/free-sound-effects/discover/trombone/ (preview MP3 `sfx/471`) | Mixkit | Mixkit SFX Free License |
| `music_loop.mp3` | Jazz Brunch, 5:23, 9.9 MB | Background music, loops everywhere for now | Incompetech — https://incompetech.com/music/royalty-free/mp3-royaltyfree/Jazz%20Brunch.mp3 | Kevin MacLeod | CC-BY 4.0 — credit required, see below |
| `music_hangout.mp3` | Jazz Brunch, 5:23, 9.9 MB (same file as `music_loop.mp3`) | **Staged for the future two-track change:** cozy café music for the hangout | Incompetech, same as above | Kevin MacLeod | CC-BY 4.0 — credit required, see below |
| `music_fight.mp3` | Mesmerizing Galaxy Loop, 1:33, 2.9 MB | **Staged for the future two-track change:** sci-fi music for fights | Incompetech — https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mesmerizing%20Galaxy%20Loop.mp3 | Kevin MacLeod | CC-BY 4.0 — credit required, see below |
| `ambience_gathering.mp3` | Outdoor market day ambience, about 2:50, 6.8 MB — market stalls, voices, footsteps | Quest ambience loop for gathering quests (Scrap Run, Market Run) | BigSoundBank, "Outdoor Market #2" (sound #3378) — https://bigsoundbank.com/outdoor-market-2-s3378.html | Joseph Sardin | CC0 |
| `ambience_cleaning.mp3` | Straw broom sweeping, about 1:00, 0.95 MB | Quest ambience loop for cleaning quests (The Great Oil Spill) | BigSoundBank, "Straw broom" (sound #163) — https://bigsoundbank.com/straw-broom-s0163.html | Joseph Sardin | CC0 |
| `npc_zip_scout_appear.ogg` | Quick phase jump up, 0.47 s, 6.7 KB | Zip Scout appears | Kenney Digital Audio pack, `Audio/phaseJump1.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `npc_zip_scout_hit.ogg` | Small laser zap, 0.34 s, 9.0 KB | Zip Scout hits | Kenney Sci-fi Sounds pack, `Audio/laserSmall_002.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `npc_bulkhead_appear.ogg` | Heavy metal plate clang, 0.49 s, 10 KB | Bulkhead appears | Kenney Impact Sounds pack, `Audio/impactPlate_heavy_002.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `npc_bulkhead_hit.ogg` | Heavy metal hit, 0.21 s, 6.2 KB | Bulkhead hits | Kenney Impact Sounds pack, `Audio/impactMetal_heavy_003.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `npc_mend_o_matic_appear.ogg` | Sparking computer noise, 5.00 s — the game plays only the first 2 s, 120 KB | Mend-O-Matic appears | Kenney Sci-fi Sounds pack, `Audio/computerNoise_001.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `npc_mend_o_matic_hit.ogg` | Small metal click (a repair tool), 0.45 s, 14 KB | Mend-O-Matic hits | Kenney RPG Audio pack, `Audio/metalClick.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `npc_ghost_drone_appear.ogg` | Soft descending phaser sweep, 0.47 s, 7.1 KB | Ghost Drone appears | Kenney Digital Audio pack, `Audio/phaserDown1.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `npc_ghost_drone_hit.ogg` | Shimmering force field, 0.96 s, 28 KB | Ghost Drone hits | Kenney Sci-fi Sounds pack, `Audio/forceField_002.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `npc_chop_chop_appear.ogg` | Knife drawn, 0.40 s, 11 KB | Chop-Chop Chef appears | Kenney RPG Audio pack, `Audio/drawKnife1.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `npc_chop_chop_hit.ogg` | Knife slice (a different slice from `chef_chop.wav`), 0.57 s, 15 KB | Chop-Chop Chef hits | Kenney RPG Audio pack, `Audio/knifeSlice2.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `npc_grill_gus_appear.ogg` | Burst of flame (thruster fire), 5.00 s — the game plays only the first 2 s, 201 KB | Grill Master Gus appears | Kenney Sci-fi Sounds pack, `Audio/thrusterFire_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `npc_grill_gus_hit.ogg` | Metal pot clatter, 0.94 s, 22 KB | Grill Master Gus hits | Kenney RPG Audio pack, `Audio/metalPot2.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `npc_baker_belle_appear.ogg` | Sweet little ding, 0.29 s, 9.0 KB | Baker Belle appears | Kenney Interface Sounds pack, `Audio/confirmation_001.ogg` — https://kenney.nl/assets/interface-sounds | Kenney | CC0 |
| `npc_baker_belle_hit.ogg` | Wooden thump (a rolling pin), 0.33 s, 6.6 KB | Baker Belle hits | Kenney Impact Sounds pack, `Audio/impactWood_medium_000.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `npc_zap_fox_appear.ogg` | Two-tone electric zap, 1.31 s, 9.8 KB | Zap Fox appears | Kenney Digital Audio pack, `Audio/zapTwoTone.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `npc_zap_fox_hit.ogg` | Electric zap (a different zap from `robot_laser.wav`), 1.23 s, 9.8 KB | Zap Fox hits | Kenney Digital Audio pack, `Audio/zap2.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `npc_ember_owl_appear.ogg` | Low three-tone hoot, 0.83 s, 7.4 KB | Ember Owl appears | Kenney Digital Audio pack, `Audio/threeTone1.ogg` — https://kenney.nl/assets/digital-audio | Kenney | CC0 |
| `npc_ember_owl_hit.ogg` | Soft cloth rustle (a wing buffet), 0.42 s, 12 KB | Ember Owl hits | Kenney RPG Audio pack, `Audio/cloth2.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `spell_fire.ogg` | Burst of flame, trimmed 5.00 s → 1.50 s, 17 KB | Fire spell cast | Kenney Sci-fi Sounds pack, `Audio/thrusterFire_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_water.ogg` | Wet slime bubble, 0.50 s, 20 KB | Water spell cast | Kenney Sci-fi Sounds pack, `Audio/slime_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_ice.ogg` | Glass shatter, 0.54 s, 8.2 KB | Ice spell cast | Kenney Impact Sounds pack, `Audio/impactGlass_medium_000.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `spell_wind.ogg` | Cloth rustle, 0.66 s, 16 KB | Wind spell cast | Kenney RPG Audio pack, `Audio/cloth1.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `spell_poison.ogg` | Wet slime bubble, trimmed 4.70 s → 1.20 s, 20 KB | Poison spell cast | Kenney Sci-fi Sounds pack, `Audio/slime_001.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_light.ogg` | Small bright laser, 0.24 s, 7.1 KB | Light spell cast; also the shimmer when a creature appears for a witch fighter | Kenney Sci-fi Sounds pack, `Audio/laserSmall_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_shadow.ogg` | Low rumble explosion, 1.00 s, 9.2 KB | Shadow spell cast | Kenney Sci-fi Sounds pack, `Audio/lowFrequency_explosion_001.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_dark.ogg` | Shimmering force field, 0.95 s, 25 KB | Dark spell cast | Kenney Sci-fi Sounds pack, `Audio/forceField_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `spell_earth.ogg` | Rock impact, 0.94 s, 12 KB | Earth spell cast; also the dull thud when the Scrap Rat hits a witch fighter back | Kenney Impact Sounds pack, `Audio/impactMining_000.ogg` — https://kenney.nl/assets/impact-sounds | Kenney | CC0 |
| `spell_lightning.ogg` | Big laser zap, 0.68 s, 25 KB | Lightning spell cast | Kenney Sci-fi Sounds pack, `Audio/laserLarge_000.ogg` — https://kenney.nl/assets/sci-fi-sounds | Kenney | CC0 |
| `wand_swish.ogg` | Knife slice, 0.60 s, 15 KB | Witch/warlock wand hit in fights (the wand is the melee weapon until spells are learned) | Kenney RPG Audio pack, `Audio/knifeSlice.ogg` — https://kenney.nl/assets/rpg-audio | Kenney | CC0 |
| `music_study.mp3` | Spellbound, 3:50, 7.0 MB | Study music track | Incompetech — https://incompetech.com/music/royalty-free/mp3-royaltyfree/Spellbound.mp3 | Kevin MacLeod | CC-BY 4.0 — credit required, see below |
| `ambience_brewing.mp3` | "Spells-a-Brewin", about 1:21, 1.9 MB | Study ambience loop for brewing quests and for learning fire, water and poison spells | soundimage.org — Eric Matyas, "Spells-a-Brewin" | Eric Matyas | Free with attribution — credit required, see below |
| `ambience_moonlight.mp3` | "Moonlight-Flying", about 1:32, 2.1 MB | Study ambience loop for moonlight quests and for learning ice, light, shadow and dark spells | soundimage.org — Eric Matyas, "Moonlight-Flying" | Eric Matyas | Free with attribution — credit required, see below |
| `ambience_storm.mp3` | "Rain and Thunder Outside", about 8:04, 11 MB | Study ambience loop for storm quests and for learning wind, lightning and earth spells | soundimage.org — Eric Matyas, "Rain and Thunder Outside" | Eric Matyas | Free with attribution — credit required, see below |

## Quest ambience loops (Phase 23, 2026-11-19)

While a hangout quest runs, a sound matching the kind of work
plays in a loop under the hangout music and the giver's voice,
on its own channel (Channel 3) at a quarter of the effects
volume, so it never interrupts the voice. It starts when the
quest starts and stops when the quest completes, stops,
pauses, or the player leaves the hangout. Turning sound
effects or background music off in Settings stops it too.

| Ambience | Quests | Loop sound |
| --- | --- | --- |
| cooking | Perfect the Recipe, Rescue the Burnt Dish, The Midnight Feast, The Robot Who Wanted Soup, The Grand Hangout Fair | `chef_sizzle.wav` (already in `sounds/`) |
| repair | Tune-Up Time, Calm the Haywire Drone, Chef's New Helper, The Broken Oven and the Broken Bot | `robot_servo.wav` (already in `sounds/`) |
| gathering | Scrap Run, Market Run | `ambience_gathering.mp3` — outdoor market, uploaded 2026-11-19 (commit 01bd111) |
| cleaning | The Great Oil Spill | `ambience_cleaning.mp3` — straw broom, uploaded 2026-11-19 (commit 01bd111) |

**To upload through the GitHub website** (Maren's tools cannot
upload audio): the two ambience files were uploaded that way
2026-11-19, commit 01bd111 — gathering is now the outdoor
market, cleaning is now the straw broom (the old flea-market
and mopping-cloth clips are kept as backups in the work
folder, `ambience_gathering_flea_backup.mp3` and
`ambience_cleaning_mop_backup.mp3`).

## NPC creature sounds (Phase 24, 2026-11-19)

Every creature gets its OWN appear sound and its OWN hit sound
— different from Scrap Rat and different from each other — so
you can tell who it is by sound alone (Makenna's per-creature
sound rule, Nov 18, 2026). The 18 files are in the table above,
all Kenney CC0. The fighter's own hit sound does not change:
a robot fighter still hears the laser and a chef fighter still
hears the chop when *they* hit a creature; the creature's own
hit sound plays when *it* hits back.

**To upload through the GitHub website** (Maren's tools cannot
upload audio): the 18 `npc_*.ogg` files are in
`~/workspace/arena-of-makers-work/sounds-download/` — upload
them into `sounds/` on main with those exact filenames. Until
they are there, that creature simply plays no sound — the
fight carries on silently, and the sounds start working on
the next launch after the upload.

## Witch study sounds (Phase 38, 2026-11-25)

The study is the witch's own place, and it sounds like it:
it has its own music track (`music_study.mp3`, "Spellbound"),
its own ambience loops, and one cast sound per element. The
layers stack the same way the hangout does: the study music
plays underneath, and while the player is learning a spell
they hear the ambience loop for that spell's family — brewing
for fire, water and poison; storm for wind, lightning and
earth; moonlight for ice, light, shadow and dark. When a study
quest starts, the quest's own ambience replaces the learning
ambience until the quest ends. When a spell finishes learning,
that spell's own sound plays. The wand swish is the witch's
melee hit sound — a witch attacks only with her wand until
she has learned a spell; once a spell is learned it is cast
instead, and the wand is only backup if a spell does not work.

The 15 Phase 38 files are the 10 `spell_<element>.ogg` files,
`wand_swish.ogg`, `music_study.mp3` and the 3
`ambience_*.mp3` files in the table above — 11 Kenney CC0
sounds (fire and poison trimmed shorter, noted in the table),
1 Kevin MacLeod CC-BY 4.0 track (credit required) and 3 Eric
Matyas loops (attribution required in the game). No Mixkit
music is used anywhere, and no CC BY-NC sound is used
anywhere.

**To upload through the GitHub website** (Maren's tools
cannot upload audio): the 15 files are prepared in
`~/workspace/arena-of-makers-work/phase38-witch-study/sounds/`
— upload them into `sounds/` on main with those exact
filenames. Until they are there, the study still works: a
missing cast sound just means the cast line speaks without
its sound, and a missing music or ambience file just means
that layer stays silent.

## Music — how it works now (two tracks, wired in 2026-11-18)

- The game now has **two tracks** (`sounds.py`, `SOUND_FILES`):
  the hangout plays `music_hangout.mp3` (Jazz Brunch, cozy café)
  and fights play `music_fight.mp3` (Mesmerizing Galaxy Loop,
  sci-fi). `music_loop.mp3` is the same file as
  `music_hangout.mp3` and stays as an alias, so older code keeps
  working.
- **Music start rule (Makenna, 2026-11-17), now in the code
  (`main.py`, `_refresh_music`):** music only starts for one
  activity at a time — the hangout, or auto-fighting. It never
  starts at launch and never starts just from switching tabs.
  A manual fight has sound effects only, no music.
- **Hangout Start, for now:** the hangout has no Start button
  in the code yet, so "Visit the hangout" on the More tab is
  the hangout's Start: entering the hangout starts the cafe
  music, and leaving the More tab (or pressing Escape, which
  goes Home) stops it. When quests add a real Start/Stop, the
  music will follow that instead.
- **The old laser:** the first robot laser was OwlStorm's
  "Retro video game sfx - Laser" from Freesound
  (https://freesound.org/people/OwlStorm/sounds/404796/, CC0),
  0.17 s, a short beep. Makenna said it was not electric
  enough, so it was replaced 2026-11-18 with Kenney's zap1
  (see the table above). The old file is kept in the work
  folder (`sounds-download/robot_laser_old.wav`) only as a
  backup; it is not in the game.

## Music credits (CC-BY, required — keep these with the game)

- Music: Jazz Brunch by Kevin MacLeod (incompetech.com), CC BY 4.0.
- Music: Mesmerizing Galaxy Loop by Kevin MacLeod (incompetech.com), CC BY 4.0.
- Music: Spellbound by Kevin MacLeod (incompetech.com), CC BY 4.0.
- Study ambience: "Spells-a-Brewin", "Moonlight-Flying" and "Rain and Thunder Outside" — Music by Eric Matyas, www.soundimage.org.

## Notes on the replacements

- **Sizzle:** Kenney has no real sizzling sound at all in any of
  its packs — the first pick was a metal pot clink, not a sizzle.
  The DailySounds "Sizzling Eggs" file is a real sizzle, and its
  first 2 seconds (all the game plays) are loud from the start.
  Other sizzle sources checked and not used: SFXMint has 9 CC0
  frying sizzles, but its direct download asks for an API key
  from this environment; SoundDino's download goes through a
  Google sign-in; Mixkit has no sizzle sound; the Pixabay sizzle
  ("Cooking Frying Sizzling Food" by Shut_Up_Ghost, 0:21,
  https://pixabay.com/sound-effects/household-cooking-frying-sizzling-food-free-kitchen-sound-effect-382864/)
  is a free download with no account, but Pixabay's download
  server was blocked from Maren's environment, so it was not
  downloaded here.
- **Win fanfare:** Kenney's Casino Audio pack has no fanfare at
  all (cards, chips and dice only). The sax jingle was picked as
  the rising fanfare; its volume was raised when converting
  because the recording is quiet.
- **Loss trombone:** no Kenney file sounds like a sad trombone
  (no trombone, no wah-wah in any pack), so the real thing comes
  from Mixkit sound effects instead.
- **Music:** Kenney only has short jingles (all under ~2 s), no
  long loops. Mixkit music is banned for games, so it was not
  used. The Pixabay lofi track from the first version of this
  file was never downloaded (Pixabay's audio server was blocked
  from Maren's environment); the Incompetech tracks above
  replace it.

## Settings in the game

- **Sound effects** (Settings tab) turns all fight sounds on
  or off.
- **Background music** (Settings tab) turns the music loop on
  or off, separately.
- **Volume** (Settings tab) turns voice, effects and music up
  or down together. Music always plays at half the effects
  volume, so it stays under the voice.
- Idle fighting narrates each fight round by round, with
  fight sounds and the sci-fi track, like a manual fight
  (changed 2026-11-17 evening, commit 17240de — before that
  it only spoke the result line).
