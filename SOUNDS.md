# Sounds and music — Arena of Makers

How to add the sounds: download each file from its source page
below (use the **Download** button on that page), and save it in
the `sounds/` folder next to `main.py`, with the filename in the
table. The game runs fine with no sound files at all — a missing
file is just skipped and logged — so add them one at a time and
try them out.

**No audio files are in this repo yet.** Pixabay's site is blocked
in the environment where these picks were made, and Freesound's
full downloads need a free Freesound account, so the files were
**not** downloaded here. Nothing below is faked: every entry was
checked on its own source page, and the licence is the one shown
there. Do not use a different file from the same page without
checking its licence first.

## Licences, in plain words

- **CC0 (Creative Commons 0)** — the maker gave the sound to the
  public domain. You can copy, change, share and use it, even for
  commercial purposes, without asking permission. No credit is
  required, but the makers are credited here anyway.
- **Pixabay Content License** — free to use for personal and
  commercial purposes, no attribution required. You may not sell
  or give away the sound file on its own, as a sound. Using it
  inside the game is fine. For music, avoid any track that shows
  a Content ID shield icon on its Pixabay page.

All Freesound sounds below are CC0. No CC BY-NC (non-commercial)
sound is used anywhere.

## The picks

| File to save as | What it is | Used for | Source page | Author | Licence |
| --- | --- | --- | --- | --- | --- |
| `robot_laser.wav` | Retro video game sfx - Laser, 0.17 s, 14.8 KB | Robot fighter hits | https://freesound.org/people/OwlStorm/sounds/404796/ | OwlStorm (credit Ashe Kirk / Owlish Media if you like) | CC0 |
| `robot_servo.wav` | Servo 5, 0.75 s, 129 KB | Creature appears, robot fighter | https://freesound.org/s/740243/ | JoontheFloof | CC0 |
| `robot_clank.wav` | snd_metal_smash.wav — a hard metallic crash, 1.67 s, 627 KB | Scrap Rat hits a robot fighter | https://freesound.org/people/gristi/sounds/562198/ | gristi | CC0 |
| `chef_chop.wav` | Knife, Chopping — chopping vegetables, 11.79 s, 2.0 MB | Chef fighter hits | https://freesound.org/people/HenKonen/sounds/757214/ | HenKonen | CC0 |
| `chef_sizzle.wav` | frying rice on a wok.wav — food sizzling in a wok, 26.73 s, 4.5 MB | Creature appears, chef fighter | https://freesound.org/people/soundofsong/sounds/679946/ | soundofsong | CC0 |
| `pan_clang.wav` | mb_knuckle-02.wav — metal bottle struck, a clang, 2.97 s, 837 KB | Scrap Rat hits a chef fighter (pan clang) | https://freesound.org/people/newagesoup/sounds/361186/ | newagesoup | CC0 |
| `win_jingle.wav` | WinMutedGuitar.wav — short win jingle, 3.78 s, 978 KB | Winning a fight | https://freesound.org/people/Fupicat/sounds/521646/ | Fupicat | CC0 |
| `loss_sound.wav` | wah wah sad trombone.wav, 5.21 s, 897 KB | Losing a fight | https://freesound.org/people/kirbydx/sounds/175409/ | kirbydx | CC0 |
| `music_loop.mp3` | Lofi Study — Calm Peaceful Chill Hop (Pixabay music) | Calm background music, loops in the arena / hangout | https://pixabay.com/music/beats-lofi-study-calm-peaceful-chill-hop-112191/ | see the Pixabay track page | Pixabay Content License |

## Keeping the size down

The two long Freesound files are played only for their first
moments by the game (`chef_chop` 1.5 seconds, `chef_sizzle`
2 seconds), but the files themselves are still big. Before
committing them, trim them to about 2 seconds each with Audacity
or ffmpeg — that takes the whole set from about 10 MB down to
about 3.5 MB, plus the music track. The music file is an MP3
from Pixabay; a WAV with the same name (`music_loop.wav`) works
too.

## Pixabay alternative for the sizzle

If the Freesound sizzle is too long to trim, this Pixabay pick
is the alternative: "Cooking Frying Sizzling Food Free Kitchen
Sound Effect" by Shut_Up_Ghost, Pixabay Content License,
https://pixabay.com/sound-effects/household-cooking-frying-sizzling-food-free-kitchen-sound-effect-382864/
— save it as `chef_sizzle.wav` (or `.mp3`, and rename the entry
in `sounds.py` if you do). Its length was not verified here
because Pixabay was blocked in the checking environment, so
check the track page before using it.

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
