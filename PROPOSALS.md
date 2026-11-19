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

## Progress tracker — updated 2026-11-18 evening (Phase 20 added)

Read this first. Each phase is Done, In progress, or Not started.
Update this table (and the date) whenever a phase changes, so the next
person — Maren, Josh's Muse, or Kiro — can pick up without getting lost.

| Phase | Status | What it means | Evidence / next step |
| --- | --- | --- | --- |
| 1. Personal save out of the public repo | Done — 2026-11-17 | `arena_save.json` (Josh's Freddy) removed; `.gitignore` added; `arena_log.txt` stays public on purpose | Commits 8a0399e, b3faebf |
| 2. Turn-by-turn voice for fights | Done — 2026-11-17 | Manual fights speak each round, ~1 sec pause, then win/loss; idle fights stay short, result only | Commit f5d876e; confirmed working by Makenna 2026-11-17. Update 2026-11-17 evening: idle fights now also narrate round by round, with fight sounds (commit 17240de) |
| 3. Online-only game, Supabase saves | Done — 2026-11-17 | No local JSON; saves in shared Supabase `players` table; launch key check with plain-words error; account creation (username, gender, player code, robot/chef); own-data export only | Commit f5d876e; project `arena-of-makers`, ref `yurdzzinmibgnoanxtkm` |
| 4. Password sign-in + anti-cheat | Done — 2026-11-17 (Kiro) | Username + 4-digit code + password (min 8 chars, bcrypt hash only, 5 wrong tries lock 10 min); session token in memory only; private `arena_private` schema, game can only call `arena_*` functions | Commit 29ad230 "Kiro made changes." |
| 5. Auto-login ("Keep me signed in") | Done — 2026-11-17 (Kiro) | Remember token in Windows Credential Manager via `keyring`, password never stored; token rotates each launch, expires after 30 days unused | Commit 29ad230; new file `remember.py` |
| 6. Tables created + Josh's account | Done — 2026-11-17 | Josh used Kiro CLI tools to create the tables from the new schema and created his account on his computer | Working live; no SQL Editor run needed |
| 7. Sound effects + music — code | Done — 2026-11-17 | `sounds.py` wired in; robot laser/servo/clank, chef chop/sizzle/pan clang, win/loss, lofi music loop; on by default, turn-offable in Settings | Commit f5d876e; picks in SOUNDS.md, all royalty-free (CC0 / Pixabay) |
| 8. Sound effects + music — files | Done — on GitHub 2026-11-18 | **All 9 effects + music are in `sounds/` on main** (commit dc3923b, uploaded through the GitHub website by Makenna, signed in as Katprincess2169). Robot: Freesound CC0 laser/servo/clank (as before). Chef chop: Kenney RPG knifeSlice; pan clang: Kenney Impact metal hit; win: Kenney sax fanfare (volume raised, it was quiet); loss: Mixkit sad trombone (Kenney has no trombone); sizzle: DailySounds "Sizzling Eggs", a real sizzle (Kenney has none — the pot clink was only a placeholder). Music: Incompetech Jazz Brunch as `music_loop.mp3` (+ `music_hangout.mp3`), Mesmerizing Galaxy Loop as `music_fight.mp3` — CC-BY, credit lines in SOUNDS.md. **Laser swap done:** the robot laser was replaced 2026-11-18 with Kenney's electric zap1 (see Phase 17), and the new `robot_laser.wav` was uploaded to `sounds/` through the GitHub website the same evening (commit 7c3f772) — no sign-in was needed, the earlier sign-in as Katprincess2169 was still remembered. | Done — laser is the new zap on main |
| 9. Makenna pulls the update + creates her account | In progress | Makenna still has to pull commit 29ad230 onto her own computer, install new requirement `keyring`, and create her account (4-digit code + password, robot fighter) | NEXT: pull, run, create account, test turn-by-turn + sign-in |
| 10. Exe build + Release | In progress | Updater ready for exe mode; local PyInstaller build ready (`build_exe.bat`); GitHub Actions workflow file still needs Josh (admin) to add it — Maren got 403 twice | NEXT: test straight Python first, then build exe; Josh adds `.github/workflows/build-exe.yml` |
| 11. Per-location music | Done — 2026-11-18 | Two tracks wired in: hangout plays `music_hangout.mp3` (Jazz Brunch, cafe), fights play `music_fight.mp3` (Mesmerizing Galaxy Loop, sci-fi). `music_loop.mp3` stays as the hangout alias. **Music start rule now in the code:** music never starts at launch or on tab switch — only for the hangout or auto-fighting. | Bug fix, reported by Makenna 2026-11-18: cafe music was starting at launch with no activity. Fixed in `sounds.py` (`start_music(track)`, `current_music_track`) + `main.py` (`_refresh_music`, `_in_hangout`) |
| 12. Music for auto-fighting, effects only for manual | Done — 2026-11-18 | Auto-fighting plays the fight track; a manual fight has sound effects only, no music. Turning music or sound effects off in Settings stops the music. | Same fix as Phase 11; tests in `test_main_smoke.py` (no music at launch, hangout/fight/manual) |
| 13. More creatures / NPCs | Not started | Only Scrap Rat exists now. Randomly create different types of animals and other NPC fighters, including NPC robot fighters and NPC chef fighters, so robots can fight chefs and chefs can fight robots and vice versa. In idle and manual fighting. Opponents must scale with level — health and everything scales proportionally to the player's stats — so fights stay even and fair for everybody, even at really high levels. Note: Scrap Rat already scales a little (hp 30+15 per level, damage 4+2 per level in `game_logic.py`), but new NPCs need the same proportional scaling. | Idea from Makenna, 2026-11-17 |
| 14. Random challenges from online players | Not started | When multiple players are online, they can randomly challenge another online player, in idle and/or manual fighting. **Fair matchmaking (Makenna, 2026-11-17): even with infinite progression and scaling, never match a player against somebody way too high for their level or way too low for their level — opponents must stay near the player's level so fights stay fair. Multiplayer warning, not a block: a player can still attack someone higher than them, but the game must warn them first (e.g. "This player might be too hard for you to beat") if it looks like an unfair match, so it does not block multiplayer.** Note: right now `arena_fight` only fights a Scrap Rat at the player's level; a player code is only recorded, not actually fought as a player yet. | Idea from Makenna, 2026-11-17 |
| 15. Attack notification + counterattack | Not started | If a player is attacked by somebody, on their next launch the game should let them know who attacked them — showing the attacker's username and/or player code — and give them the option to land a counterattack. Example: if Makenna (username Katprincess, player code 2169) attacks Josh, Josh should be told on his next launch that Katprincess / 2169 attacked him. | Idea from Makenna, 2026-11-17 |
| 16. Windows notifications outside the app | Not started | Windows push notifications outside the app, only if the user grants permission, so they arrive when the app is closed. Uses: (1) when somebody attacks you, (2) when a timed upgrade finishes — e.g. a 20-minute upgrade (upgrade time is 60 seconds x level, capped at 4 hours), so you can close the app instead of sitting in the hangout, get notified when it is done, and go back in. Note: no notification code exists yet; closed-app notifications need a background helper / scheduled check, not just in-app toasts, because nothing is running when the app is closed. | Idea from Makenna, 2026-11-17 |
| 17. Bug fixes — 2026-11-18 (music, laser, Yes/No, updater) | Done — 2026-11-18 | **Music:** no auto-start at launch; two tracks wired (Phase 11/12). **Laser:** robot laser replaced with Kenney's electric zap1 (1.02 s, CC0); the new `robot_laser.wav` was uploaded to `sounds/` through the GitHub website 2026-11-18 (commit 7c3f772, no sign-in needed). **Max affordable:** the Yes/No question is now a real dialog with Yes as the default button, Y/N keys, Escape = No — Enter on Yes was heard as No by the old MessageBox, so the game said "Nothing was bought". Server max-upgrade logic, cost formula and 4-hour cap unchanged. **Updater:** a fresh install lands in exactly one "Arena of Makers" folder (no nesting); the updater finds the real install one level down or in the parent and offers "Check for updates"; a fresh install always writes its version note. New headless tests in `test_updater.py`. | Reported by Makenna 2026-11-18, with Josh present; fixed in `main.py`, `sounds.py`, `arena_of_makers_updater.py`, `SOUNDS.md`, `test_main_smoke.py`, `test_updater.py` |
| 18. Hangout quests | Not started — NEXT after the bug fixes | Hangout quests so the hangout actually means something. Design already drafted (`HANGOUT_QUESTS_DESIGN.md` in the work folder): endlessly generated quests, six givers (Bolt, Marge, Pip, Dot, Gus, Belle) each with their own Edge voice, Start/Stop in the hangout, music only on Start, spoken progress update every 5 minutes, quests 2–4 hours max, Stop saves to the server, rewards and reputation with each giver. **Sequencing (Makenna, 2026-11-18): do NOT start quests until the bug fixes above are pushed and she has tested them.** | NEXT: start after Makenna confirms the bug fixes by pulling latest main |
| 19. Update check at launch (in-game prompt) | Done — 2026-11-18 | **The idea was Josh's, approved by Makenna 2026-11-18.** When the game opens it quietly asks GitHub whether main is newer (10-second timeout, before sign-in) and, if so, asks Yes or No with the fixed `_ConfirmDialog` (Yes is the default, Y/N keys, Escape = No): update now, or play this version and be asked again next launch. Never updates without asking; never updates silently. Yes downloads and applies the update, then the game says "Update finished. Close the game and open it again to play the new version" and stops — Python already loaded the old files, so a restart is the safe path. No plays on. GitHub unreachable plays on with a plain-words note, not a crash. A hand-installed copy with no version note is found by `main.py` alone and compared file by file; if it already matches main, the note is written quietly. Exe mode offers the latest Release the same Yes/No way (no exe or Release exists yet, so this is untested live). **The standalone updater is KEPT as the backup, not deleted** — Makenna has had other games where an in-game-only update failed to connect or did not take the new version, so if something goes catastrophically wrong the updater must still be there. **The updater itself is now kept up to date:** its own sync still never replaces its own running code, but the game's launch update refreshes `arena_of_makers_updater.py` (its launcher `.bat` and its state file stay protected always). That is the fix for 2026-11-18 evening, when the fixed updater sat on GitHub but Makenna's computer still ran the old one, so none of the Phase 17 fixes reached her. | **One-time bootstrap still needed:** this new code cannot reach her computer by itself — her copy is old. Josh/Makenna must get it there once first. Two ways: (a) git pull in the game folder, or replace `main.py` + `arena_of_makers_updater.py` from GitHub, then run the game once and say Yes; or (b) clean reinstall, which Makenna prefers — deleting the old game folder is fine and a good idea, including the empty nested "Arena of Makers" folders the old updater made. BUT keep `.env` safe first: copy it somewhere safe, delete the old folder, install the fresh game, then put `.env` back next to the fresh game files before launching, because the game will not start without it. Deleting the folder loses no progress: her fighter and progress live in Supabase, and her sign-in token lives in Windows Credential Manager — none of that is in the game folder. Tests: `test_main_smoke.py` (launch update: up to date / unreachable / No / Yes / failed update / no version note) and `test_updater.py` (standalone sync never touches its own file; game sync refreshes it) |

| 20. Music respects the game state — stops when auto-fight / hangout ends | Done — 2026-11-18 | **Reported by Makenna 2026-11-18 evening, with Josh present:** auto-fighting worked with round-by-round narration and good sound effects, but after she lost a fight the fight music kept playing even though auto-fight had turned off and repairs (about 10–15 minutes) were running. **Cause:** `main.py` has one music rule (`_refresh_music`, driven by `idle_fighting` / `_in_hangout`), but three places turned auto-fighting off without calling it — the tick that stops auto-fight when repairs start, Escape to stop auto-fight by hand, and a server error that ends an idle fight — so the fight track kept looping. **Fix:** all three places now call `_refresh_music()` when auto-fight stops. **Continuous, not per-fight (Makenna's refinement, same evening):** the music stays on for the whole auto-fight session and is never stopped/restarted between fights, at the end of a single won fight, or between rounds — `start_music` already returns at once when the same track is playing, so the loop never jumps. It stops only when the session ends: repairs needed after a loss, manual stop (Escape / toggle), or a failed fight. Hangout works the same way: its music plays from Start until Stop (or leaving the More tab), even while a quest is saved or paused — leaving the hangout already stopped its music, and the hangout has no separate Stop button yet (quests are Phase 18, not started). No new music, no sound-effect changes, no timer or server changes. | Fixed in `main.py` + new headless checks in `test_main_smoke.py` (won idle fight keeps the music; Escape stops it; failed idle fight stops it; repairs stop auto-fight and the music). **Still needs the one-time bootstrap (Phase 19):** Makenna's computer still runs the old game, so this fix only reaches her when she launches and says Yes to the update (or Josh does a pull / reinstall). |

**Next up, in order:** (a) one-time bootstrap: get the Phase 19 code onto Makenna's computer (git pull, or replace `main.py` + `arena_of_makers_updater.py` from GitHub), then launch, say Yes, restart, and confirm the Phase 17 fixes — and the Phase 20 music fix — are finally there, (b) Makenna creates her account (Phase 9), (c) hangout quests (Phase 18), (d) test the exe build (Phase 10).

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

### Sounds — 9 of 9 converted, upload to GitHub still pending (2026-11-17/18)

- `sounds.py` and `SOUNDS.md` are in the repo. The game is wired to play robot laser/servo/metal clank, chef chop/sizzle/pan clang, win jingle, sad trombone loss, and a music loop. Sounds/music are on by default but turn-offable, in Settings.
- **All 9 effects + music are converted and sitting in `sounds/` in Maren's local copy** (verified WAV/MP3, `SoundBank.load()` finds all 9 names). Robot sounds are the Freesound CC0 files as before. The other 6 Freesound files never downloaded (HTTP 403 / AccessDenied), so they were replaced: chef chop = Kenney RPG knifeSlice, pan clang = Kenney Impact metal hit, win = Kenney sax fanfare (volume raised), loss = Mixkit sad trombone, sizzle = DailySounds "Sizzling Eggs" (a real sizzle — Kenney has none), music = Incompetech Jazz Brunch (hangout) + Mesmerizing Galaxy Loop (fights, staged). Full sources and licences are in the updated SOUNDS.md. The two-track music switch is NOT coded yet — the game still only reads `music_loop.mp3`.
- **The audio files are NOT on GitHub yet.** Maren's GitHub connector only pushes text snapshots and cannot push binary WAV/MP3 files (25 MB total); `gh` is not logged in and raw git has no credentials on her side. What is still needed: a git push of `sounds/` (11 audio files) plus the SOUNDS.md/PROPOSALS.md updates, from a machine with GitHub credentials — e.g. Josh's computer. Do not push the text files and claim the sounds are in the repo until the audio files land with them.
- All sounds are royalty-free: Freesound/Kenney CC0, DailySounds free commercial no credit, Mixkit sound effects free for games, Incompetech CC-BY with the credit lines in SOUNDS.md. Do not use a different file without checking its licence first.

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

## Status update — 2026-11-18 (Makenna, with Josh and Maren)

### Four bugs Makenna reported while playing, all fixed

1. **Music started at launch.** The cafe track (Jazz Brunch) played as
   soon as the game opened, with no activity. Cause: `main.py` called
   `start_music()` in `__init__`. Fixed: no music at launch; the two
   tracks are now wired in (`sounds.py` plays `music_hangout.mp3` for
   the hangout and `music_fight.mp3` for fights) and music only starts
   for an activity — entering the hangout, or auto-fighting. A manual
   fight has sound effects only. For now "Visit the hangout" on the
   More tab is the hangout's Start: entering starts the cafe music,
   leaving the More tab (or Escape to Home) stops it. When quests add
   a real Start/Stop, the music will follow that instead.
2. **Robot laser was not electric enough.** The old laser was a 0.17 s
   retro beep. Replaced with Kenney's zap1 (Digital Audio pack, CC0),
   a 1.02 s electric zap, converted to WAV. The new `robot_laser.wav`
   was uploaded to `sounds/` through the GitHub website the same
   evening (commit 7c3f772) — no sign-in was needed.
3. **Max affordable said "Nothing was bought" after Yes.** Makenna
   was told she could afford 3 laser levels, pressed Enter on Yes,
   and the game said nothing was bought. Cause: the question was a
   plain `wx.MessageBox`, whose default button is up to the platform,
   so Enter did not land as Yes. Fixed: a real Yes/No dialog with Yes
   as the default button, Y for yes, N for no, Escape for no. The
   server max-upgrade logic, the cost formula and the 4-hour cap were
   not changed.
4. **Updater: nested folders, and no "Check for updates".** Installing
   wanted Arena of Makers inside Arena of Makers inside Arena of
   Makers, and after reinstalling the updater only offered Install.
   Cause: the default folder added "Arena of Makers" even when the
   updater already sat inside such a folder, and the button only
   checked whether the version note existed in the folder shown — so
   after the nesting mess it looked in the wrong folder. Fixed: the
   folder is normalised to exactly one "Arena of Makers"; the updater
   finds the real install one level down or in the parent and points
   the folder box at it; a fresh install always writes its version
   note. `.env` and the updater's own state file are never touched.
   To test: point the updater at the folder holding the game (or its
   parent) — it should say "Check for updates", not "Install".

### What Makenna decided next

- **She is waiting for these four fixes to be pushed before playing
  any more.** After she pulls latest main and confirms them, the next
  work is hangout quests (Phase 18), so the hangout actually means
  something. Quests were NOT started in this run, on purpose.
- She still has to pull latest main and create her account
  (Katprincess / 2169, robot fighter) — Phase 9.
- **2026-11-18 evening, after the fixes were pushed: none of them
  had reached her computer.** The updater still made an empty nested
  folder, the old beep still played, and there was still no "Check
  for updates" button. Cause: `arena_of_makers_updater.py` is in
  `PROTECTED_FILES`, so the updater never replaces itself — her
  computer still ran the OLD updater. The fixes were on GitHub main
  (verified: 7dc2091 + laser 7c3f772); they just had not landed.
  Josh's idea, approved by Makenna: the game itself checks for a
  newer version at launch and asks Yes or No (Phase 19), so the
  separate updater is no longer the only route — but the standalone
  updater is KEPT as a backup, and the game now refreshes the
  updater's own file so the backup never goes stale again. The
  one-time bootstrap (getting the Phase 19 code onto her computer
  first) is still owed — see Phase 19.
