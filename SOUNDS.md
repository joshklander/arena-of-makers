# Sounds and music — Arena of Makers

**All 9 sound effects plus the music are in the `sounds/` folder
next to `main.py` in Maren's local copy (added 2026-11-17/18), and
SOUNDS.md documents them below. The audio files themselves are not
on GitHub yet — Maren's GitHub connector cannot push binary files —
so until they are uploaded (see PROPOSALS.md Phase 8), a fresh pull
still has only the README in `sounds/`.** Once the audio files land,
the game loads them automatically — no downloading needed, no code
change needed. If a file is missing, the game just skips it and logs
one plain-words line, so it still runs fine but silent.

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
| `robot_laser.wav` | Retro video game sfx - Laser, 0.17 s, 15 KB | Robot fighter hits | https://freesound.org/people/OwlStorm/sounds/404796/ | OwlStorm (credit Ashe Kirk / Owlish Media if you like) | CC0 |
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

## Music — how it works right now, and what is staged

- **Right now** the game only reads `music_loop.mp3` (`sounds.py`,
  `SOUND_FILES["music"]`), and plays it everywhere. That file is
  Jazz Brunch, the cozy café track — it is the hangout track as
  well as the current only track.
- `music_hangout.mp3` and `music_fight.mp3` are **staged, not
  wired in yet**. They are there so the two-track change (Phase 11,
  per-location music) does not need another download round: when
  the code is changed, the hangout plays `music_hangout.mp3`
  (Jazz Brunch) and fights play `music_fight.mp3` (Mesmerizing
  Galaxy Loop). Do not claim the two-track switch works yet — it
  needs a small code change in `sounds.py` + `main.py`.
- **Music start rule (Makenna, 2026-11-17):** music should only
  start when you press Start in the hangout, or when you start
  auto-battling with auto-fight on. It should never start just
  from switching tabs, and never start automatically at launch.
  That rule is not in the code yet either — it belongs with the
  two-track change.

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
- Idle fighting plays no fight sounds and speaks only the
  result line, so it stays short and quiet.
