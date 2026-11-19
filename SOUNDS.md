# Sounds and music — Arena of Makers

**All 9 sound effects plus the music are in the `sounds/` folder
on GitHub, on main (uploaded 2026-11-18, commit dc3923b), and
SOUNDS.md documents them below.** The game loads them
automatically — no downloading needed, no code change needed. If
a file is missing, the game just skips it and logs one
plain-words line, so it still runs fine but silent.

**One file is not on GitHub yet:** `robot_laser.wav` was replaced
2026-11-18 with a more electric zap (see the table below). Maren's
GitHub tools cannot push binary files, so the new file is in a zip
(`arena-robot-laser-zap1.zip`, in the work folder) waiting for the
browser upload, like the 11 sounds were. Until it is uploaded, a
fresh pull still has the old retro laser.

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
| `ambience_gathering.mp3` | Flea-market ambience, about 1:09, 2.7 MB — conversations, people walking by, general crowd activity | Quest ambience loop for gathering quests (Scrap Run, Market Run) | BigSoundBank, "Flea #1" (sound #130) — https://bigsoundbank.com/flea-1-s0130.html | Joseph Sardin | CC0 |
| `ambience_cleaning.mp3` | Damp cloth cleaning a floor, about 0:49, 1.9 MB | Quest ambience loop for cleaning quests (The Great Oil Spill) | BigSoundBank, "floor cloth" (sound #668) — http://bigsoundbank.com/floor-cloth-s0668.html | Joseph Sardin | CC0 |

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
| gathering | Scrap Run, Market Run | `ambience_gathering.mp3` — **to upload** (see below) |
| cleaning | The Great Oil Spill | `ambience_cleaning.mp3` — **to upload** (see below) |

**To upload through the GitHub website** (Maren's tools cannot
upload audio): the two new files are in
`~/workspace/arena-of-makers-work/sounds-download/` —
`ambience_gathering.mp3` and `ambience_cleaning.mp3`. Upload
them into `sounds/` on main with those exact filenames. Until
they are there, gathering and cleaning quests simply play no
loop — the game carries on silently, and the loops start
working on the next launch after the upload.

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
