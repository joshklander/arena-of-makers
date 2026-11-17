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
