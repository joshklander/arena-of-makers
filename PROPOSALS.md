# Proposals for Josh — Arena of Makers

Written by Makenna (with Maren, her assistant) on 2026-11-17.
This file is for Josh and his Muse to read. It lists a change already
made, and proposals Makenna would like Josh to look at.

## Change already made — 2026-11-17

### Personal save files stay local, not in the public repo

- `arena_save.json` was removed from the repo. That file was Josh's
  personal save — a robot fighter named Freddy, with a Laser Blaster
  and Scrap Plating, 1 win, 25 XP, 15 points.
- It should never have been uploaded. Anyone who downloaded the game
  got Freddy's save instead of being asked to create their own fighter.
  That is why Makenna never got asked whether she wanted to be a robot
  or a chef — the game loaded Freddy and skipped the create screen.
- Josh's copy on his own computer is not touched by this change.
  Before he pulls, he may want to copy his local `arena_save.json`
  somewhere safe, so he does not lose Freddy.
- A `.gitignore` file was added with `arena_save.json` in it, so personal
  saves cannot be pushed again by accident.

### The error log stays public on purpose

- `arena_log.txt` was NOT removed and should stay in the repo.
- It is there so Makenna and Josh (and their assistants) can both see
  if there are errors in the code, and write to that file when needed.
- Personal save data does not belong in the log. Keep saves private,
  keep the log public.

## Proposals — not done yet, for Josh to decide

### 1. Turn-by-turn voice for fights

Right now a fight builds a line for every round, but those lines only
appear in the text log on the Combat tab. The voice only speaks the
last line: "You won! You earned X experience and Y points."
The voice engine is also set up to drop older lines and only keep the
newest one.

Proposal: speak each round in order, with a short pause between rounds,
so the fight feels turn by turn. For example: "Round 1: Freddy hits
the Scrap Rat for 12. Round 1: The Scrap Rat hits Freddy for 3."
Idle fighting should still be allowed to stay short, so it does not
pile up a long backlog of spoken lines.

### 2. Music and sound effects, different for robot and chef fighters

Sound effects are still to come. The code already says they should
only come from Pixabay and freesound.org, using material marked free
to use.

Proposal:
- Robot fighters: laser, metal clank, servo / robot movement sounds.
- Chef fighters: sizzling, chopping, pan clang / spatula sounds.
- Add background music as well.
- Pixabay audio is free to use, but its API only covers images and
  videos, so audio would be picked and downloaded from the Pixabay
  website. Freesound is free with a free API credential, and its sounds
  are Creative Commons — use only CC0 or CC BY sounds, and credit the
  maker when the licence asks for it.
- No sound files have been added yet. Makenna has not picked a robot
  or chef fighter, or a fighter name, yet.

### 3. Make sure every player gets asked to create their own fighter

After the save file is removed, a fresh download should show the
"Create your fighter" screen: pick robot or chef, pick a voice,
and give the fighter a name. If a save file is ever present, the game
should still make it clear whose fighter it is, on the Home tab.

### 4. Multiplayer — later, bigger work

Makenna wants the game to be more multiplayer. Right now there is
no server, no accounts, and the save is a local file on one computer.
The hangout is a placeholder: "Other players will join here when
multiplayer arrives."

This is not a small change. Before building it, Josh and Makenna
need to decide what kind of multiplayer they want, for example:
- Live fights against each other
- Teaming up against creatures together
- A shared hangout where players can see and talk to each other
  while fighting on their own

No multiplayer work has started yet.

## Who is who

- Josh Klander — GitHub `joshklander`, admin on this repo.
- Makenna Conlon — GitHub `Katprincess2169`, write collaborator on
  this repo (read, write, and push access, confirmed 2026-11-17).
- Makenna's other repo, found the same day: `Katprincess2169/monster-paradise`,
  a private Python monster care and training game built with wxPython.

---

## Status update — 2026-11-17 evening (Makenna, with Maren)

This section is the handover note. If anyone's tokens/credits run out — Maren's, Josh's Muse, or Kiro — read this file first, then SOUNDS.md and README.md, to pick up where we left off. Do not overwrite Kiro's work in commit 29ad230.

### What changed on 2026-11-17, after the proposals above

- **Turn-by-turn voice — DONE, in commit f5d876e.** Manual fights now speak each round in order with about a 1-second pause, then win/loss. Idle fights stay short (result only, no fight sounds), so speech does not pile up. The game window does not freeze while speaking.
- **Online-only multiplayer — DONE, in commit f5d876e.** No local JSON saves at all. Player saves go to one shared Supabase table (`players`), one row per player. On launch the game checks for the `.env` key (project URL + publishable key, kept next to the game, never bundled in an exe) and gives a plain-words error if it cannot find it. Account creation on first launch: username (also fighter name), gender (picks the voice), own player code, robot or chef. Export is per-player only, from the More tab.
- **Passwords and auto-login — DONE by Kiro, in commit 29ad230 "Kiro made changes.", 2026-11-18T02:08:31Z.** Sign-in is now username + exactly 4-digit player code (e.g. 4827) + password (at least 8 characters, hidden box). The server stores only a bcrypt hash, never the password. Five wrong tries lock the account for 10 minutes. Sign-in gives a session token kept in memory only. New file `remember.py`: "Keep me signed in" saves a remember token in Windows Credential Manager (via `keyring`), never the password; the token rotates each launch and stops working after 30 days unused. Turning it off deletes it here and on the server.
- **Anti-cheat — DONE by Kiro, in commit 29ad230.** `supabase_schema.sql` was rewritten (1024 lines): a private `arena_private` schema holds players/sessions/remembered tables, and the game can only call the `arena_*` functions. No direct table access, so a player cannot edit their own data and cheat on the server.
- **Tables and Josh's account — WORKING.** Josh used Kiro CLI tools to create the tables from the new schema and created his own account on his computer. No manual SQL Editor run is needed now.
- **Exe build — ready to test, no Release yet.** Updater updated for exe mode (commit 665d7a7e). Local PyInstaller route added (`build_exe.bat` / `build_exe.py`, commits be227d69 and d9da473d): double-click to build `dist/ArenaOfMakers.exe` and `dist/ArenaOfMakersUpdater.exe`, everything bundled in, `.env` and save untouched. The GitHub Actions workflow file (`.github/workflows/build-exe.yml`) could NOT be pushed by Maren — GitHub returned 403 twice — so Josh (repo admin) still needs to add it himself via the GitHub website or his own computer if they want Releases built automatically. Agreed order: test straight Python first, build the exe only when ready.
- **Makenna's fighter choice: robot.** She has not yet pulled the Kiro update onto her own computer to try it.

### Sounds — code is in, files are NOT downloaded yet (2026-11-17 evening)

- `sounds.py` and `SOUNDS.md` are in the repo. The game is wired to play robot laser/servo/metal clank, chef chop/sizzle/pan clang, win jingle, sad trombone loss, and a calm lofi music loop. Sounds/music are on by default but turn-offable, in Settings.
- **No audio files are in the repo.** `sounds/` contains only a README. The game skips missing files silently, so it runs fine but silent. That is why Makenna hears no sound effects even though turn-by-turn voice works.
- **Download attempt on 2026-11-17 failed: 0 of 9 files.** Maren tried from her work environment: Freesound pages/CDN returned HTTP 403, Pixabay's audio CDN returned AccessDenied. Full Freesound WAV downloads need a free Freesound account/login. This is an environment block, not a problem with the picks.
- **What is still needed (on a home computer, Makenna's or Josh's):** create/log in to a free Freesound account, open each source page in SOUNDS.md, click Download, and save each file into the game's `sounds/` folder next to `main.py` with the exact filename in SOUNDS.md. Download the Pixabay lofi track the same way as `music_loop.mp3`. No code change is needed. A full write-up with all 9 preview/download links is in Maren's local `sounds-download/README.md` (not in the repo yet) — ask Maren for it if needed.
- All sounds are royalty-free: Freesound picks are CC0, music is Pixabay Content License. Do not use a different file without checking its licence first.

### New ideas from Makenna — 2026-11-17 evening, not done yet

1. **Different music for different locations, like Magic Worlds.** Magic Worlds has a different music track for the kitchen and for other places, so you can hear where you are. Arena of Makers should do the same — e.g. a different track for the arena, the hangout, the shop — instead of one lofi loop everywhere.
2. **Music while auto/idle fighting is on; sound effects only when fighting manually.** When idle fighting is on, play a background track. When fighting manually, play just the fight sound effects when the player tells it to fight.
3. **More creatures/NPCs to fight.** Right now the only option is Scrap Rat (`game_logic.py`: "One starter creature for the skeleton. More creatures come later."). Add multiple random NPC creatures, in both idle and manual fighting.
4. **Random challenges from online players.** When multiple players are online, they should be able to randomly challenge another online player — in idle and/or manual fighting — not just fight creatures.
5. **Magic Worlds, for reference.** Makenna and Josh's other game, an Alexa skill in every available region, with three games in one: Monster Paradise (monster trainer, fights, fishing and more), Magic Realms (play as a mage), and Bubble Tycoon (bubble-popping tycoon with fighting and spell learning). Makenna's private repo for Monster Paradise is `Katprincess2169/monster-paradise`.

### How to work on this repo without losing the thread

- Keep writing changes and new ideas in this file, with the date. That is how Josh's Muse, Kiro, or Maren can pick up where the last one left off if tokens/credits run out.
- Do not overwrite Kiro's password/auto-login/anti-cheat work in commit 29ad230. Do not put `.env`, passwords, tokens, or personal save files in the repo. `.env` stays next to the game/exe, never bundled in.
- Supabase project: `arena-of-makers`, ref `yurdzzinmibgnoanxtkm`, region Americas. Makenna owns it; Josh has full read/write developer access.
