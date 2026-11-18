# arena-of-makers
Arena of Makers — accessible multiplayer arena game: robot fighters and chef fighters battle creatures, upgrade gear, and hang out in an idle social area. Python, wxPython, Edge TTS.

## Playing

Run it with: `python main.py`

- **F** — fight one creature, narrated turn by turn: each round
  is spoken in order, with a short pause between rounds, then
  the win or loss result. The Combat tab still shows every line.
- **Shift+F** — idle fighting on and off. Idle fights stay short:
  only the result line is spoken, and no fight sounds play.
- **U / A** — upgrade weapon / armor in the Shop.
- **R** — hear repair status in More.
- **Settings** — change voice, turn sound effects or background
  music on or off, and raise or lower the volume.

## Sounds

Sound effects and background music are royalty-free only, from
Pixabay and Freesound. See `SOUNDS.md` for the picks, their
authors and licences, and how to download them into `sounds/`.
The game runs fine with no sound files at all.

## Online-only, Supabase

Arena of Makers is exclusively online. On launch the game
checks for a `.env` file next to the game, with:

    SUPABASE_URL=https://yurdzzinmibgnoanxtkm.supabase.co
    SUPABASE_PUBLISHABLE_KEY=your publishable key

If the file is missing, or either line is in the wrong shape,
the game says so in plain words and does not start. Test the
key on your own computer with `python test_key.py` — it prints
OK or what is wrong, and never prints the key.

On first launch you make an account in one go: pick a
username, a gender (which picks the voice), your own player
code (4 to 8 letters and numbers, or press "Make a code for
me"), and whether you are a robot or a chef. Your username is
also your fighter's name. Friends look you up by your player
code, from the More tab. Accounts live only in Supabase, in that same one shared
`players` table (see `supabase_schema.sql`). There is no
local account file: every launch you type your username and
player code, and the game looks you up online. No password
is involved, and `.env` is never pushed to GitHub.

Everything lives in one shared Supabase table, called
`players`: one row per player, holding the account (username,
gender, robot or chef, player code), the fighter, and that
player's game actions. That is what makes it easy for players
to look each other up, fight each other, and help each other:
from the More tab you can look a player up by code, see all
players, and fight a player by code, all from that same one
table. Every game action — fights, upgrades, key presses,
setting changes — is sent to the server, into your own row.
There is no local save file at all: no `arena_save.json`,
no local JSON of any kind. If an online save fails, the game
says so instead of writing a local file.

Export your own data from the More tab: it writes a file
next to the game with only your fighter and your own game
actions, never anyone else's.
