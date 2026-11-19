# Arena of Makers — Friends List and Tag Team Fights (DRAFT)

**Status: DRAFT for review only — NOT pushed to GitHub, NOT in the game code.**
Written 2026-11-17 for Makenna, Josh, and Kiro to review. Nothing here
changes `game_logic.py`, `main.py`, or `supabase_schema.sql` yet.

Makenna's idea, 2026-11-17, in her words: a friends list so you can
search for and be friends with other players; and a tag team feature —
it doesn't matter if you're a robot or a chef — where a teammate can
come in and hit the opponent you're fighting. Both players must be
online. It works anywhere — in the hangout or wherever else — not
tied to one location.

**CORRECTED MODEL, per Makenna, Nov 17, 2026 — this is the model
this draft now follows.** Tag team is **automatic, not initiated
mid-fight**. There is no "call a friend" button and no per-fight
request. What IS initiated is a **tag team request**: if somebody
wants to be a team with somebody, they can be in a team with **ONE
other player**, and that person has to accept the request in order to
join the team. In the game, the teammate only comes in when they are
online, and it happens **randomly during a fight** — the server rolls
the dice, and sometimes your teammate just jumps in to help. An
earlier version of this draft had a mid-fight "Call a friend" flow
with a 30-second accept; that flow has been removed entirely.

**SECOND CORRECTION, per Makenna, Nov 17, 2026.** The random join
has **no fixed rate** — it can happen every fight, or every couple
of fights. The server rolls fresh dice every fight, the chance stays
a surprise, and the player never chooses when the teammate comes in.
And the teammate does **ONE strike only**: they drop in, land a
single hit (and a heal, set by **your own Healing skill** — see
"Team healing"), and then they are gone until the next random roll
in a later fight. They do not stay for the remaining rounds. An
earlier version of this draft said "1 fight in 3" and had the
teammate fight for the rest of the fight; both of those have been
removed.

## Where things stand now

Two building blocks already exist on the server, and this draft builds
on them instead of inventing new ones:

- **`arena_lookup_player(p_token, p_player_code)`** — looks a player
  up by their public 4-digit player code. It returns only public
  things: username, player code, gender, fighter kind, fighter name,
  level, wins, losses, weapon name and level, armor name and level.
  It never returns a password hash, a session token, or anything
  private.
- **`arena_list_online(p_token)`** — lists players who are online
  right now (their game has checked in within the last 2 minutes and
  has not signed out). It returns username, player code, fighter kind,
  and level, ordered by username.

There is **no friends list** yet and **no tag-team feature** yet.
Fights are solo: one fighter, turn by turn, up to 20 rounds, against
one NPC (Scrap Rat, or one of the 9 NPCs in NPC_DESIGN.md).

Group tasks in the hangout (HANGOUT_QUESTS_DESIGN.md — co-op quests
with full reward for everyone) are related but **separate**: tag team
is about **fights**, not quests. A friend can help you in a quest
without ever fighting, and a friend can help you in a fight without
ever doing a quest. The two never get mixed up.

## The rules this design must obey (Makenna, 2026-11-17)

- **Both sides must agree.** Nobody gets added to anybody's friends
  list without saying yes. A friend request is a question, not a
  fact. There is no auto-adding, no adding by code alone, and no
  surprise friends.
- **Robot or chef, it doesn't matter.** A robot can tag-team with a
  chef, a chef with a robot, a robot with a robot. The tag team never
  checks fighter kind. Kinds are flavour; friendship is not.
- **One teammate at a time.** You can be in a team with exactly
  ONE other player. Leaving a team, or switching to a different
  teammate, is allowed — but you only ever have one teammate at
  once. A team is formed by a request that must be accepted (see
  Part 2), and both players must already be friends.
- **The teammate only joins when they are online, and only by
  chance — and only for one strike.** When a fight starts, the
  server rolls fresh dice: if your teammate is online, there is a
  random chance they jump in during the fight. There is **no fixed
  rate** — it can happen every fight, or every couple of fights.
  The chance is deliberately not published, so it stays a surprise,
  and the player never chooses when the teammate comes in. If your
  teammate is offline, nothing happens — the fight is solo, and
  nobody is asked anything. Nobody initiates a join mid-fight, and
  nobody has to answer a request mid-fight. And when the teammate
  does jump in, they land **one strike only** — one hit (plus a
  heal, set by **your own Healing skill** — see "Team healing") —
  and then they are gone until the next random roll in a later
  fight. They never stay for the remaining rounds.
- **Being friends is NOT enough to be a team.** A friend who never
  accepted a tag team request can **never** jump into your fights,
  no matter how often you play together, no matter how many quests
  you finish side by side. Tag team is separate from friends: you
  must send an actual tag team request and the other person must
  accept it. Friendship alone never creates a team, and there is no
  automatic teaming from being on each other's friends list.
- **It works anywhere.** The hangout, the fight screen, the shop —
  wherever you are in the game, if you are in a fight and your
  teammate is online, the random join can happen. Tag team is not
  tied to one location, and it is not tied to one button either.
- **Warning, not a block.** The same fair-matchmaking rule as Phase
  14 in PROPOSALS.md: if a helper is much stronger or much weaker
  than the fight, the game **warns** you in plain words and lets you
  decide. It never blocks you from playing with a friend.
- **Money is called "credits".** Never "points". Credits are what you
  earn from fights and quests and spend on upgrades. Stat points (the
  2-per-level choices in STATS_DESIGN.md) are a different thing and
  keep their own name.
- **One fighter per player, no caps.** A friend helps with their one
  fighter — robot OR chef. There is no level cap, so tag-team rewards
  scale forever, just like solo rewards do.
- **The server is the only judge.** Same rule as the rest of the
  game: the server checks both players are friends and teammates,
  checks the teammate is online, rolls the random join with its own
  dice, and rolls the helper's hit with its own dice. The game on
  your computer never decides a join or a hit by itself.

## Part 1 — The friends list

### How you find someone

A new **Friends tab** in the game. It is a short list, read out one
player at a time in plain words — "Josh, robot, level 5, online" —
never a long table you have to hold in your head.

Two ways to find someone, both using what the server already has:

1. **Search by player code.** You type a 4-digit code (the same code
   you use to look a player up today, e.g. Makenna's planned code
   2169). The server runs `arena_lookup_player` and says, in plain
   words, who that code belongs to: "Katprincess, robot, level 1."
   If no player has that code, it says so plainly: "No player has
   that code. Check the code and try again."
2. **Search by username.** You type a username, or the start of one,
   and the server lists matching players — username, kind, level,
   online or offline. Typing "Jos" finds "Josh". Usernames are public;
   searching by one never reveals anything private.

Either search can start a friend request. You never need both the
code *and* the username — one is enough.

### How friending works — both sides say yes

1. You find someone and choose **"Send friend request"**. The game
   speaks: "Friend request sent to Josh."
2. The other player gets a plain-words request the next time they
   are online (or right away, if they are online now): "Katprincess
   wants to be your friend. Press Y to accept, or N to say no."
   The request waits patiently. It never expires while you are
   playing, and it never nags.
3. **Accept** — you are friends, both ways, at once. Each of you
   sees the other on your Friends tab from then on.
4. **Decline** — nothing happens. No friend is added, no message is
   sent back saying "they said no", and nobody is punished. The
   person who asked simply sees the request is gone. Declining is
   one key and costs nothing.
5. **Unfriend** — either side can remove the friendship at any time,
   from their own Friends tab, with one choice and a plain-words
   confirm: "Stop being friends with Josh? Press Y to confirm."
   The other player is not told why, and is not messaged about it.
   They simply stop seeing you on their list.
6. **Block** — stronger than unfriend. A blocked player cannot send
   you a friend request again, cannot see whether you are online,
   and cannot call you into a fight. Blocking is silent: the blocked
   player is never told they were blocked. Unblocking is a choice on
   your own list, any time.

A player can only send one pending request to the same person at a
time — no spamming the same request ten times. And you cannot send a
friend request to yourself; the game says so kindly if you try.

### What each player sees about the other

A friend sees exactly what `arena_lookup_player` and
`arena_list_online` already show, and nothing more:

- **Username** (e.g. Katprincess, Josh)
- **Fighter kind** — robot or chef
- **Fighter level**
- **Online or offline** — and, if online, that they are in the game
  right now
- **Weapon and armor names and levels** — the same public fighter
  card any player can already look up by code today

A friend **never** sees: your password or password hash, your
session token or remember token, your email, your credits balance,
your stat-point choices, your game history, or anything else the
server keeps private. Friendship opens a door to play together; it
does not open your account. The server enforces this — the friends
functions return the same public fields as the lookup functions, and
no function returns private fields to a friend.

### The Friends tab — simple for VoiceOver

- One short list: each friend is one line — name, kind, level,
  online or offline. "Josh, robot, level 5, online."
- Online friends come first, then offline friends, both in username
  order. Nobody has to remember where anyone is in a long list.
- Each friend has three choices: **"Send tag team request"** (see
  Part 2 — ask this friend to be your one teammate), **"Remove
  friend"**, and **"Block"**. Every choice speaks before it acts,
  and every action confirms in plain words after it happens. There
  is deliberately **no "Call into a fight" choice** — tag-team joins
  are automatic and random, never called for mid-fight.
- Pending requests have their own short list at the top: "Friend
  request from Katprincess. Press Y to accept, N to decline."

## Part 2 — Tag team fights

### The idea in one sentence

You and one friend form a team. Then, in some of your fights, your
teammate just shows up — randomly, automatically — and fights beside
you against the same opponent. You never call them. They never have
to answer anything mid-fight. Sometimes help just arrives.

### Forming a team — the one thing that IS initiated

Team formation is the only part anyone starts on purpose, and it
works exactly like friending: both sides must say yes.

1. **You send a tag team request.** From the Friends tab, you pick
   a friend and choose "Send tag team request". The other player
   must already be your friend — you cannot team up with a stranger.
   You can only have one teammate at a time, so if you are already
   in a team, the game says so plainly: "You are already in a team
   with Josh. Leave that team first if you want a new teammate."
2. **They accept or decline.** The other player gets a plain-words
   request the next time they are online (or right away, if they are
   online now): "Katprincess wants you to be her tag team partner.
   Press Y to accept, or N to say no." The request waits patiently,
   like a friend request. It never expires while you are playing,
   and it never nags.
3. **Accept** — you are a team, both ways, at once. Each of you sees
   the other as your teammate from then on. If either of you was
   already in a team with somebody else, that old team ends first —
   one teammate at a time, no exceptions.
4. **Decline** — nothing happens. No team is formed, no message is
   sent back saying "they said no", and nobody is punished. The
   person who asked simply sees the request is gone.
5. **Leaving a team** — either side can leave at any time, from
   their own Friends tab, with one choice and a plain-words confirm:
   "Stop being in a team with Josh? Press Y to confirm." The other
   player is told, plainly and kindly, that the team has ended —
   "Katprincess left your tag team" — because a team affects their
   fights, so they need to know. Leaving a team does **not** end the
   friendship; you stay friends, you just stop being teammates.

### The three conditions for a jump-in — all three must be true

Before the server rolls the dice for any fight, it checks three
things, in this order. **All three must be true, or there is no
roll at all** — the fight is solo, and nothing is announced:

1. **A team exists.** There is an accepted tag team request on
   file for these two players — a row in the `teams` table. Being
   on each other's friends list does **not** count. A friend who
   never accepted a tag team request can never jump into your
   fights, no matter how often you play together.
2. **Both players are online.** Both players have live sessions —
   both games open and signed in, both checked in within the last
   2 minutes. If one person is online but the other is not playing,
   the teammate does **not** come in. No offline help, ever.
3. **Only then, roll the dice.** The server rolls fresh dice, with
   no fixed rate and no published chance.

What the server does **not** check is just as important: it does
not check what the teammate is doing. Your teammate could be in
the hangout, in the shop, in their own fight, anywhere in the game
— as long as they are online, they count. The server checks online
status only, not what screen they are on. That includes a teammate
whose fighter is under repair: the jump-in is a single
server-rolled strike, not the teammate actually fighting, so a
repairing fighter can still land it. **Decided by Makenna, Nov 17,
2026: yes, they can still come in while repairing — they only have
to be actually online, connected to the server — because it is not
them taking on the full fight, they are just coming in for one
strike.** The rule in one line: **you only need full health and to
not be in repair if you are the one fighting. You do not need it if
you are helping one person for one hit.** The caller starting a
fight must be healthy and not repairing; the helper jumping in for
a single strike needs nothing except to be online.

### How a teammate joins a fight — automatic and random

1. **You are fighting.** A normal solo fight is already running —
   turn by turn, up to 20 rounds, against one NPC. You did nothing
   special. You pressed no button. You asked nobody for help.
2. **The server rolls fresh dice when the fight starts.** Behind
   the scenes, at the start of every fight, the server checks two
   things: is your teammate online right now, and has a random roll
   come up in your favour? There is **no fixed rate and no
   published chance** — the roll is different every fight. It can
   happen every fight, or every couple of fights, or not for a
   while. The chance is deliberately not a number the player can
   learn or plan around: winning or losing a fight does not change
   it, and being in trouble does not change it either. It is luck,
   not a rescue button, and that is the point — help arriving feels
   like a surprise, not a tool you spend.
3. **If the roll comes up, the server also picks a random round for
   the jump-in**, and the game announces it when that round begins,
   in plain words: **"Josh jumped in to help!"** There is no
   request, no waiting, no accept. Your teammate drops in, lands
   **one strike** against the opponent (and heals you **once**, by
   your own Healing skill level — see "Team healing" below), and
   then they are gone. They do not stay for the next round. (If the
   fight is already over before the chosen round, the teammate never
   appears, and that fight just counts as one where nobody joined.)
4. **If your teammate is offline, nothing happens.** The server
   checks online first, and an offline teammate is simply skipped —
   no roll, no message, no disappointment. The fight is solo, exactly
   as if you had no teammate at all. Your teammate is never told
   they missed a fight, and you are never told they were offline.
   It just does not happen.
5. **The fair-matchmaking warning happens when the team is
   formed**, not mid-fight — there is no moment mid-fight to warn
   you, because nobody is choosing anything mid-fight. When the
   other player accepts the team request, the game checks the level
   gap once, for both of you: if your teammate is more than 5
   levels away from you, it says so plainly on the accept screen —
   "Josh is level 20 and you are level 5. He will find your fights
   very easy, and his hits will be much bigger than yours. Team up
   anyway?" — and the warning is **never a block**. If you both say
   yes, you are a team, and the game trusts you. (See "Fair
   matchmaking" below for the full rule.)
6. **The fight stays yours.** The teammate's jump-in is a single
   moment inside your fight, not a second fighter joining it. Your
   turns still go **you, then the opponent** (or the opponent
   first, if it is faster than you — Speed decides who hits first,
   as in STATS_DESIGN.md). The opponent does not get a second turn,
   does not get extra rounds, and does not change its damage because
   a teammate appeared for one strike.
7. **The teammate's single strike uses their own stats.** This is
   the heart of it: your teammate does not hit with *your* weapon.
   They hit with their own Strength, their own weapon level, their
   own Luck — the same formulas as a solo fight (damage = weapon
   damage + 2 × Strength, plus random 0–3; crits ×1.5 with the
   diminishing Luck chance from STATS_DESIGN.md). A strong teammate
   genuinely helps more, because their one hit is genuinely bigger.
   A weak teammate still helps — one extra hit is one extra hit —
   but they cannot carry a fight their stats cannot win. And the
   strike is still bound by the 75% fairness guard: no single hit,
   normal or critical, can deal more than 75% of the target's max
   health.
8. **The opponent can never hit the teammate.** Because the
   teammate is only ever in the fight for one strike, the opponent
   never gets a turn against them — they drop in, hit, heal, and
   are gone before the opponent can answer. Helping costs the
   teammate nothing in health and never starts a repair for them.
   What it costs is one of their 3 automatic joins for the day (see
   "Rewards" below). The heal itself is powered by **your** Healing
   skill, which you bought with your own credits — so the teammate
   gives their time, and you bring the healing. That is what keeps
   it fair, instead of an invisible difficulty knob on the
   opponent.
9. **The fight ends the same way a solo fight ends.** The opponent's
   health reaches zero (you win), or your health reaches zero (you
   lose), or 20 rounds pass. The game speaks every round in turn,
   with each fighter named: "Katprincess hits Zip Scout for 37.
   Zip Scout hits Katprincess for 16." And when the teammate jumps
   in, their line is spoken too: "Josh jumped in to help! Josh
   hits Zip Scout for 29."

### Worked example — checked, 2026-11-17

A level 5 robot and her level 5 chef teammate, against **Zip
Scout, level 5**. Nobody called anybody: the server rolled the
random join, picked round 1, and the game announced "Josh jumped in
to help!" as the fight began. The teammate lands **one strike only**,
then is gone — and that jump-in also heals the caller **once**, by
her own Healing skill: she has bought the Healing skill at level 1,
which heals **19% of her max health** (see "Team healing" below).
Numbers are taken from
the STATS_DESIGN.md worked example and NPC_DESIGN.md: the caller is
the same level 5 robot as that example (damage 38, max HP 150, soak
5, Speed 5), and Zip Scout at level 5 has 73 HP, 21 damage, soak 1,
Speed 8. The chef teammate is level 5 with weapon level 3, Strength
3: damage 30, max HP 150, soak 5. (Chefs hit for 2 less per round
than robots in the NPC_DESIGN.md baseline, which is why the
teammate's damage is 30 and not 38.)

**Round 1** — Zip Scout is fastest (Speed 8), so it hits first:

- Zip Scout hits the caller for 21 − 5 soak = **16**. Caller:
  150 → 134.
- Caller hits Zip Scout for 38 − 1 soak = **37**. Zip Scout:
  73 → 36.
- Teammate jumps in — "Josh jumped in to help!" — and lands his
  one strike for 30 − 1 soak = **29**. Zip Scout: 36 → 7. The
  jump-in also heals the caller **once**, for 19% of her 150 max
  health = **about 28**. Caller: 134 + 28 would be 162 — past her
  150 maximum — so the heal stops at **150**. (That is the
  never-overheal rule working: the extra is simply lost.)

**Round 2** — the teammate is already gone. Just caller and Zip
Scout, as in a solo fight:

- Zip Scout hits the caller for **16**. Caller: 150 → 134.
- Caller hits Zip Scout for **37**. Zip Scout: 7 → dead. **Win.**

**The check:**

- The fight lasts **2 rounds** — the same as the solo fight in
  STATS_DESIGN.md. Without the teammate, the caller wins in 2
  rounds and ends at 116 health (150 − 34). With the teammate's
  one strike and one heal, she ends at **134 health** — the strike
  took 29 health off Zip Scout, and the heal brought her back up
  to full (134 → 150) before Zip Scout's last hit. The teammate's
  help is real, but it is one moment, not a second fighter: the
  caller still had to win the fight herself.
- **No one-shots.** Zip Scout's hardest single hit is 21 damage —
  14% of the caller's 150 max HP. Even its Double Dash ability
  (two hits in one round, every 3rd round) deals 2 × 16 = 32 —
  21% of max HP. The teammate's hardest single hit, a critical
  hit, is 30 × 1.5 = 45 — 62% of Zip Scout's 73 max HP, under
  the **75% fairness guard** from STATS_DESIGN.md (no single hit,
  normal or critical, can deal more than 75% of the target's max
  health). Nobody can one-shot anybody in this fight, from either
  side. The heal is bound the same way: about 28 health is 19% of
  max health, far under the 95% heal cap — and the cap at max
  health meant only 16 of it was actually used (134 → 150), with
  the rest lost to the cap.
- **If the caller had no Healing skill (level 0)**, the strike
  still lands for 29, but there is no heal — the caller would end
  round 2 at 118 health instead of 134. The strike alone is worth
  having; the heal is what makes the skill worth buying.

### Fair matchmaking — warning, not a block

Phase 14 in PROPOSALS.md says: never match a player against somebody
way too high or way too low for their level, and never block a player
from attacking somebody higher — **warn them instead**. Tag team uses
exactly the same rule, for the teammate — but the warning happens
**when the team is formed**, because there is no choice to warn about
mid-fight:

- When a team request is accepted, the game checks the level gap
  once. Teammates **within 5 levels** of each other: no warning,
  the team just forms. Level 5 and level 5: nothing to say.
- If the teammate is **more than 5 levels away** in either direction,
  the game warns both players on the accept screen, in plain words,
  and asks for a yes before the team forms:
  - Teammate much stronger: "Josh is level 20 and you are level 5.
    He will find your fights very easy, and his hits will be much
    bigger than yours. Team up anyway?"
  - Teammate much weaker: "Josh is level 1 and you are level 5.
    He will take big hits in your fights, and he might get knocked
    out. Team up anyway?"
- The warning is **never a block**. If you both say yes, you are a
  team, and the game trusts you. And because the join is random, the
  game also speaks one short line when a much stronger or weaker
  teammate jumps in — "Josh jumped in to help! He is much stronger
  than this fight." — so the surprise is never confusing.
- The 75% fairness guard still applies to every hit, however strong
  the teammate is. A level 50 teammate jumping into a level 5 fight
  cannot one-shot the opponent, because no single hit can deal more
  than 75% of the target's max health. The guard is what keeps a
  strong teammate helpful without making the fight meaningless.

### The trade-off — the opponent does NOT get stronger

This draft picks **one** trade-off, and it is deliberately *not*
making the opponent tougher:

- **The opponent gets no HP boost and no damage boost when a
  teammate jumps in.** Making the opponent stronger just because a
  teammate appeared for one strike would punish the exact thing tag
  team is for — help arriving when you need it. A player whose
  teammate jumps in should feel the fight get easier, not watch the
  opponent grow to match the help.
- **The trade-off is that help is rare, brief, and paid for.** The
  teammate appears only sometimes (the random roll, no fixed rate),
  lands one strike and is gone, can only jump in 3 times a day, and
  the Healing skill that makes a jump-in truly generous costs
  credits to buy and level up — 203 credits in total to reach level
  5 and the full 95%. Help is generous, but it is not reliable, not
  unlimited, and not free. That is what keeps it fair, instead of
  an invisible difficulty knob on the opponent.

### Team healing — the Healing skill (Makenna decided: max 5)

A new skill, bought with credits on the Shop tab, separate from
weapon and armor. It does nothing in a solo fight — it only matters
when your teammate jumps into your fight.

- **What it is.** The **Healing skill** is one **you** buy, like a
  skill level. It is yours, on your fighter. When your teammate
  jumps in for their one strike, they also heal you **once** — one
  hit plus one heal, then gone. The amount healed is set by **your
  own Healing skill level**, not your teammate's: your teammate
  brings the strike, and your skill decides how much healing that
  visit is worth. (An earlier version of this draft said the
  healer's level set the amount. Makenna decided it is the
  recipient's own skill — the player being helped.)
- **The scale — decided: max level 5.** Each level adds **19% of
  your max health** healed:

  | Healing skill level | Heals (one-time, per jump-in) |
  | --- | --- |
  | 1 | 19% of max health |
  | 2 | 38% |
  | 3 | 57% |
  | 4 | 76% |
  | **5** | **95% — the maximum** |

  Five levels, not ten — Makenna picked five ("maybe five would
  be easier"), so the skill is quick to learn and quick to max
  out, with big jumps per level instead of many small ones.
- **The maximum is 95% of max health, at level 5 — and this is the
  ONLY upgrade in the game with a cap.** After level 5 the Healing
  skill cannot go higher. That is deliberate, and it is the
  opposite of every other upgrade: **weapon, armor, and all other
  upgrades are INFINITE — no level cap, no cost cap, they climb
  forever.** Only the Healing skill stops, at 95%. The reason is
  simple: a teammate can never fully restore you. You always keep
  at least 5% of your health to earn back yourself — the help is
  real, but the win is still yours.
- **One-time per jump-in.** The heal happens once, at the moment
  your teammate jumps in, and never again in that fight — even if
  the fight runs long. Your teammate does not stay to heal you a
  second time, and a second jump-in cannot happen in the same
  fight. One strike, one heal, gone.
- **It never overheals.** The heal is capped at your max health.
  If you are at 134 of 150 and the heal is about 28, you go to
  150, not 162 — the extra is simply lost. A heal can never give
  you more health than your maximum.
- **Cost — DECIDED by Makenna, Nov 18, 2026: exponential, NOT the
  normal upgrade curve.** The old draft said Healing cost the same
  25 × 1.5^(level−1) as every other upgrade (203 credits total) — that
  is superseded. Healing changes game progression too much for small
  numbers: if it were cheap, people would get it instantly and it
  would not feel meaningful to upgrade. Decided anchors: it starts at
  **50 credits** for level 1, and level 5 costs **about 400 credits**.
  Fitted curve (proposal, from those two anchors — multiplier about
  ×1.7 per level): level 1 = 50, level 2 = 85, level 3 = 140,
  level 4 = 240, level 5 = 400 credits, about 915 credits in total
  to reach level 5 from scratch.
- **Time — DECIDED by Makenna, Nov 18, 2026: slower than normal.**
  Healing upgrades take longer than the normal 60 seconds × level.
  Decided anchor: the build from level 4 to level 5 takes **at least
  an hour**. Fitted time curve (proposal, from that anchor — 12 minutes
  × level): level 1 = 12 minutes, level 2 = 24, level 3 = 36,
  level 4 = 48, level 5 = 60 minutes, about 3 hours in total to reach
  level 5 from scratch. Inside the same 4-hour total cap as other
  timers.
- **No Healing skill, no heal.** A player who has never bought the
  skill (level 0) still gets their teammate's one strike when the
  teammate jumps in — the strike does not need the skill. They
  just do not get healed. The strike alone is worth having; the
  heal is what makes the skill worth buying.

## Rewards — who gets what

### The rule: full rewards for both fighters

When a tag-team fight is **won**, **both fighters get the full solo
win rewards, scaled to their own level** — exactly as if each of
them had won a solo fight at their own level:

- **Credits: 10 + 5 × level** — so a level 5 win pays 35 credits,
  and a level 10 win pays 60. Each fighter is paid at *their* level,
  not the caller's level and not the opponent's level.
- **XP: 20 + 5 × level** — the same solo win XP, at each fighter's
  own level. (The STATS_DESIGN.md worked example: a level 5 win
  pays 45 XP and 35 credits.)

When a tag-team fight is **lost**, the **caller** takes the usual
small loss: up to 5 credits lost, and a repair timer starts, exactly
as in a solo loss. The **teammate** shares the small credit loss —
up to 5 credits — but only if they actually jumped in, and they
**never** start a repair: the opponent never got a chance to hit
them, so there is nothing to repair. If the teammate never jumped
in, they lose nothing at all.

**Why full rewards, not a split?** The same reason as co-op quests
in HANGOUT_QUESTS_DESIGN.md: splitting punishes playing together. If
two friends won a fight and split 35 credits, each would get 17 or
18 — less than winning a solo fight alone. That would teach players
*not* to help each other, which is the opposite of what tag team is
for. Full rewards say: bringing a friend makes the fight better, and
nobody loses out for it.

### The anti-farming limit — helps per day, not half rewards

Full rewards for both fighters is generous, so it needs a limit that
keeps it from becoming a way to farm credits. This draft considered
two options and **picks one**:

- **Picked: a teammate can jump in a limited number of times per
  day.** Each player can be the helper in **3 automatic tag-team
  joins per day**. After 3 joins, the server stops rolling for them
  until tomorrow, and the game says plainly if you ask: "You have
  used your 3 tag-team joins for today. You can help again
  tomorrow." Three is enough that
  helping a friend in trouble never feels rationed in normal play —
  most days your teammate will jump in once or twice — and small
  enough that a strong player cannot spend all day carrying strangers
  through fights for double rewards. The count resets each morning, like the
  quest board. Being *helped* does not count against your own limit
  — only helping does — so a player who is struggling is never told
  they have used up their joins. And a join only counts if your
  teammate actually jumps in: a fight where the dice said no costs
  nobody anything.
- **Not picked: half credits when the level gap is big.** Cutting the
  helper's pay when they are much stronger or weaker would punish
  exactly the friendships the game wants most — a high-level friend
  helping a new player learn the game. The fair-matchmaking warning
  already tells both players the gap; the pay should not punish them
  for it as well.

One thing the server does **not** guard on: what the teammate is
doing. A teammate in the hangout, in the shop, in the middle of
their own fight, or with their fighter under repair can still jump
in — the server checks online status only, not what screen they are
on. If the dice do not come up for a fight, nobody is told why; the
fight is simply solo that time. The only activity that ever blocks a
jump-in is being offline.

## Server side — key-free, same pattern as the rest

Two new functions for forming a team, plus the random join rolled
inside the fight functions the game already has. The game sends
only the **in-memory session token** plus codes and ids. No username,
no player code, no password, no .env contents, no API key. The server
checks both players are friends, checks the team is real, checks
the teammate is online, and rolls the join and the helper's hits
with its own dice.

**New function — send a tag team request:**

```
arena_team_request(p_token text, p_friend_code text)
```

- The game sends only the requester's session token plus the
  friend's public 4-digit player code.
- The server checks, in order: (1) the requester's session is
  valid, (2) the friend code belongs to a real player, (3) the two
  players are already friends, (4) neither player is already in a
  team with somebody else (one teammate at a time), (5) there is no
  pending team request between them already. If any check fails, it
  returns a plain-words error and nothing happens.
- On success it records a pending team request and returns the
  friend's public fighter card so the requester's game can say who
  was asked. It does **not** send the friend's token, credits, or
  anything private.

**New function — accept the team request (and the level warning):**

```
arena_team_accept(p_token text, p_request_id text)
```

- The friend's game sends only the friend's session token plus the
  request id.
- The server checks, in order: (1) the friend's session is valid,
  (2) the request exists, (3) neither player has joined another team
  since the request was sent. If any check fails, it returns a
  plain-words error ("That team request is no longer open") and
  nothing happens.
- On success it records the team — one row, two player codes — and
  ends any old teams either player was in first, so one teammate at
  a time is enforced on the server, not just in the game. The level
  gap is checked here too: if the two players are more than 5 levels
  apart, the function returns the warning line with the accept, so
  the game can speak it ("Josh is level 20 and you are level 5…
  Team up anyway?") and the warning is never a block.
- A matching `arena_team_decline` (same pattern, token + request id)
  simply deletes the pending request, and `arena_team_leave`
  (token only) ends the team. The player who leaves does not need
  the other player's permission, and the other player is told the
  team has ended.

**The random join — rolled inside the fight, not a new request:**

There is **no** `arena_tagteam_request` / `arena_tagteam_join` /
`arena_tagteam_hit` per fight. Instead, `arena_fight` and
`arena_fight_npc` gain the join roll at the start of every fight:

- The server checks, in order: **(a)** does this player have a
  teammate — an accepted team request on file, not just a
  friendship; **(b)** do **both** players have live sessions right
  now (checked in within the last 2 minutes); **(c)** has the
  teammate used fewer than 3 automatic joins today? If any answer
  is no, the fight runs solo and nothing is said. The server does
  **not** check what the teammate is doing — hangout, shop, their
  own fight, under repair, anywhere: online is online, and that is
  the only activity check.
- If all answers are yes, the server rolls **fresh dice — no fixed
  rate, no published chance**. On a miss, the fight runs solo. On
  a hit, it also rolls the join round, and returns a line for the
  game to speak at that round: "Josh jumped in to help!"
- At the join round, the server rolls **one strike only** from the
  teammate, inside the same fight function, with the same formulas
  as `arena_fight` (damage, crit, dodge) and the same 75% fairness
  guard. The game never decides a hit's size by itself, and no
  separate hit function is needed. In the same moment, the server
  applies the **one-time heal**: it reads the **caller's own
  Healing skill level** from the caller's fighter, works out 19%
  × skill level of the caller's max health (capped at 95% and at
  max health), and adds it to the caller's health once. The
  teammate is then gone — the fight carries on as a solo fight,
  and no further teammate rolls happen in that fight.
- The join counts against the teammate's 3-per-day limit only when
  they actually jump in.

### What happens when someone goes offline mid-fight

- **The teammate goes offline before their strike round:** the
  strike simply does not happen. The server notices the teammate's
  session has gone quiet (no check-in for 2 minutes) and skips the
  jump-in — the fight carries on solo, exactly as if the dice had
  said no, and the teammate uses up **none** of their 3 joins for
  the day, because they never jumped in. Nobody is told anything,
  and nobody is punished for a dropped connection. (Once the strike
  has landed, the teammate is already gone, so going offline after
  that changes nothing.)
- **The caller goes offline:** the fight **ends**. It was the
  caller's fight, and without them there is no fight to help in.
  The teammate is told in plain words: "Katprincess left the fight,
  so the fight is over." If the opponent was already beaten, both
  fighters are paid as a win; otherwise the fight counts as a loss
  for the caller (up to 5 credits, repairs as usual) and the
  teammate simply goes back to whatever they were doing, with no
  loss and no repair — they did not lose, the fight just ended.
- **The teammate is offline when a fight starts:** nothing happens
  at all. The server skips the roll, the fight is solo, and nobody
  is told anything. There is no request to time out, because there
  never was a request.

### Friends data — what the server keeps

A small table in `arena_private`, e.g. `friendships`, holding one row
per friendship: the two player codes, who asked, when it was
accepted, and whether either side has blocked the other. It follows
the same private-schema rule as everything else: the game can only
call the `arena_*` functions, never the table. A second small table,
e.g. `teams`, holds one row per team — the two player codes and when
the team was formed — with the server enforcing one team per player:
forming a new team ends the old one first. A third small table,
e.g. `tagteam_helps`, records each automatic join (helper code, date)
so the server can enforce the 3-per-day limit — one row per join,
counted per helper per day, and nothing else.

## Accessibility — every step is a spoken line

- **Every step is a plain-words line.** "Josh jumped in to help!"
  "Your tag team request was accepted." "Josh left the fight. You
  are fighting alone again." Name, action, result — all of it
  speakable, in order, with no charts, no graphs, and no pictures
  you need to see. There is no line that says "Josh wants to join
  your fight. Press Y" — that line belonged to the old per-fight
  request flow, and it is gone, because nobody is ever asked
  anything in the middle of a fight.
- **No fast reflexes, and nothing to answer mid-fight.** A tag-team
  join is automatic: it happens, the game announces it, and the
  fight carries on turn by turn. Nobody has to answer in a split
  second, nobody's turn is skipped because they were slow, and
  there is no 30-second timer anywhere in tag team. The only
  requests with an answer are the friend request and the team
  request, and both of those wait patiently, like a letter — they
  never expire while you are playing, and they never nag.
- **Declining a team request is one key and never punishes
  anyone.** Press N, and the request is gone. The requester is
  never told who said no, the friend is never named, and no
  friendship is harmed.
- **Leaving a team is one key too**, with a plain-words confirm
  first, and the other player is told kindly that the team ended —
  because a team affects their fights, they need to know, but they
  are never told why.
- **The Friends tab is short.** Online friends first, then offline
  friends, each one line. Nobody has to hold a long list in their
  head, and nobody has to remember a code — the game remembers the
  friendship, and the player just picks a name.

## For Kiro / Josh — what server work is still needed

- A `friendships` table in `arena_private` (two player codes, who
  asked, accepted date, blocked flags), a `teams` table (two player
  codes, formed date — one team per player, enforced on the
  server), and a `tagteam_helps` table (helper code, date) for the
  3-per-day limit. All three follow the private-schema rule: the
  game can only call the `arena_*` functions, never the tables.
- `arena_friend_search`, `arena_friend_request`,
  `arena_friend_accept`, `arena_friend_decline`,
  `arena_friend_remove`, `arena_friend_block` — all following
  `arena_lookup_player` exactly: session token in, public fields
  out, validation on the server, plain-words lines back.
- `arena_team_request`, `arena_team_accept`, `arena_team_decline`,
  and `arena_team_leave`, plus the random join roll inside
  `arena_fight` and `arena_fight_npc` (three checks before every
  roll: team on file, both players online, teammate under the
  3-per-day limit — activity is never checked; fresh random roll
  every fight, no fixed rate; random join round; one strike plus
  one-time heal rolled on the server with the 75% fairness guard,
  the heal set by the caller's own Healing skill level (19% × skill
  level of max health, capped at 95% and at max health). No
  per-fight request or join
  `arena_tagteam_request` / `arena_tagteam_join` /
  `arena_tagteam_hit` design is replaced by this one.
- Game-side: a Friends tab with a "Send tag team request" choice,
  the team-request accept/decline prompt, and the "Josh jumped in
  to help!" announcement line. No "Call a friend" choice on the
  fight screen, and no join-request prompt — those belonged to the
  old model and are gone. All using the plain-words lines and key
  presses the game already has. No new input method, no new
  library.
- Do-not-touch items: password sign-in, `remember.py`, the private
  schema rules, commit 29ad230, and the credits rename (tag-team
  rewards pay credits, and the migration in STATS_DESIGN.md covers
  existing balances). The tag-team functions must also respect the
  fair-matchmaking warning rule (Phase 14) — warn, never block.

## Open questions for Makenna

1. **Healing skill max level — DECIDED: 5.** ~~Max 5 or max 10?~~
   **Decided Nov 17, 2026: max 5** — "maybe five would be easier."
   Each level adds 19% of max health healed (level 1 = 19%, level
   5 = 95%). The max-10 option (about 9.5% per level) is dropped.
   The heal is set by your own Healing skill level, one strike plus
   one-time healing per jump-in, never past max health, 95% ceiling.
2. **How many automatic joins per day?** This draft says **3 joins
   per day per helper** — enough that helping a teammate never feels
   rationed, small enough that nobody can farm credits all day by
   carrying strangers. More, fewer, or unlimited?
3. **Should the opponent get tougher when a teammate jumps in?**
   This draft says **no** — the opponent stays exactly as strong,
   and the trade-off is that help is random, one strike only, and
   limited to 3 joins a day. Would you rather the opponent got a
   small HP boost instead, or as well?
4. **What should friends see about each other?** This draft says
   friends see username, fighter kind, level, online/offline, and
   the public weapon/armor card — the same things any player can
   already look up by code today. Would you like friends to see
   more (say, exact wins and losses), or less (just "online", with
   no level shown at all)?

**Decided, not open:** the random join has **no fixed rate** — the
server rolls fresh dice every fight, the chance stays a surprise,
and there is no number to pick. The teammate does **one strike
plus one-time healing**, then is gone.

### Level 5 Healing also works outside tag teams — no more repairs (Makenna, Nov 18, 2026)

The Healing skill is not only for tag teams. Decided by Makenna, Nov 18,
2026: **if you get Healing to level 5, you do not need repairs anymore.
It automatically heals you after every fight.**

- The 95% cap is for the TAG TEAM heal — the heal your teammate gives
  you when they jump in. That stays capped at 95%: a teammate can never
  fully restore you.
- Your OWN level-5 Healing works outside tag teams too: after every
  fight, it automatically restores your health, so no repair timer is
  needed anymore. Repairs (the wait after losing, 5 minutes per level)
  simply stop happening for a level-5 healer.
- The skill is still bought the same way (credits, Shop tab, same cost
  curve, max level 5), and it still does the tag-team heal at every
  level (19/38/57/76/95%). Level 5 just adds the solo benefit on top.
- Open question — DECIDED by Makenna, Nov 18, 2026: the level-5
  auto-heal after a fight restores you to FULL health (100%), not to
  the 95% cap. The 95% cap applies only to the tag-team heal from a
  teammate. Your own level-5 Healing brings you all the way back after
  every fight, so no repair is ever needed.
