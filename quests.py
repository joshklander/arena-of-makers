"""Hangout quests for Arena of Makers (Phase 18).

Quests are NOT fights: nobody gets hurt, nobody loses health,
and no quest ever turns into a battle. They are jobs, favours
and puzzles in the hangout — fetching, fixing, tasting, calming
something down, helping somebody out. A quest is open to every
fighter, robot or chef alike: fighter kind never locks anyone
out of a quest. A robot can do chef quests, a chef can do robot
quests, and mixed-world quests are open to everyone.

Six givers, three male and three female, each with their own
Edge voice (chosen by character, never by the player's gender):
Bolt and Pip and Gus are male; Marge and Dot and Belle are
female. The same giver always sounds the same.

The server is the only judge: it generates the quests, checks
the work and pays the credits (see supabase/migrations/).
This module holds the shared rules — rewards, durations,
reputation tiers, the giver table and the endless generator —
so the game and the headless tests use the same numbers the
server uses. The game never pays itself from here in online
play: it only shows what the server sends back.

Rewards, by difficulty and quest level (Phase 26, Makenna
2026-11-18): a Medium quest pays what a fight win pays only
when the quest level and the fighter level happen to match —
credits are keyed to the quest level now, not the fighter
level, and grow infinitely with no cap, even though quest
timers cap at 4 hours.
  Easy:   5 + 2 x quest level credits
  Medium: 10 + 5 x quest level credits
  Hard:   20 + 10 x quest level credits

Quest durations (Phase 26): a few minutes to 2-4 hours,
never over 4 hours. At quest level 1 the ranges are exactly
as before — Easy 5-15 minutes, Medium 15-45, Hard 60-240 —
and they grow with the quest level from there: the base
range is multiplied by (1 + 0.1 x (quest level - 1)),
capped at 240 minutes.

Reputation, per giver, +1 each time you finish one of their
quests, no cap: 3 = Helper (their quests pay +25% from then
on), 8 = Friend (a free weapon OR armor upgrade, your choice,
instant), 15 = Trusted Friend (a free Healing upgrade, if you
are not already at the max Healing level 5, 95%; otherwise
another random gift, instant). Gifts are instant: no credits,
no time, no queue.

Healing: levels 1-5 heal 19%, 38%, 57%, 76%, 95% — never more
than 95%. The Healing cap is never exceeded.

Quests pause (Phase 22, Makenna 2026-11-18): the quest clock
only runs while the player is in the hangout with quests
started. Stopping — Stop button, leaving the hangout, Escape,
closing the game — freezes the remaining time on the server,
and starting again resumes from it: the quest is never
restarted and never shortened by time away. Repairs and
upgrades still tick down whether the game is open or closed;
only the quest clock freezes. A paused quest never completes.

Quest levels (Phase 23, Makenna 2026-11-18): quests give
quest XP toward a separate quest level, one per player, not
per giver. Easy 10 + 2 x quest level, Medium 20 + 5 x quest
level, Hard 40 + 10 x quest level; 100 x quest level to go
up a quest level. Each quest level-up banks 1 quest point
for Charm (+5% quest credits), Renown (+10% chance of +1
bonus reputation) or Insight (+5% quest XP), each max 10.
Quest levels give no max HP and no combat stat points.

Automatic quest-stat bonus (Phase 26, Makenna 2026-11-18):
like combat's automatic +10 HP per combat level, each quest
level-up also gives a little bit of each of the three quest
stats automatically — +1% per quest level-up to Charm,
Renown and Insight — and the banked quest point a player
spends adds its bigger bonus on top. At quest level 1
nothing has levelled up yet, so the automatic bonus is 0;
at quest level 5 it is 4%. It stacks with spent points and
never caps.
"""

import random

# Givers: name, Edge voice, gender, personality. Three male,
# three female, kept in balance on purpose (Makenna, 2026-11-18).
GIVERS = [
    {"name": "Bolt", "voice": "en-US-ChristopherNeural",
     "gender": "male",
     "personality": "the gruff robot foreman"},
    {"name": "Marge", "voice": "en-US-JennyNeural",
     "gender": "female",
     "personality": "the warm head chef"},
    {"name": "Pip", "voice": "en-US-EricNeural",
     "gender": "male",
     "personality": "the excitable young inventor"},
    {"name": "Dot", "voice": "en-US-MichelleNeural",
     "gender": "female",
     "personality": "the calm repair drone"},
    {"name": "Gus", "voice": "en-US-DavisNeural",
     "gender": "male",
     "personality": "the old grill master"},
    {"name": "Belle", "voice": "en-US-SaraNeural",
     "gender": "female",
     "personality": "the cheerful baker"},
]

GIVER_BY_NAME = {giver["name"]: giver for giver in GIVERS}

# The 12 example quests from the design: starting seeds, not
# the whole list. The generator varies their items, places and
# helpers, so the same quest never repeats exactly.
QUEST_TEMPLATES = [
    {"name": "Scrap Run", "difficulty": "Easy", "giver": "Bolt",
     "ambience": "gathering",
     "description": "The workshop is out of scrap. Fetch three pieces from the scrap yard."},
    {"name": "Tune-Up Time", "difficulty": "Easy", "giver": "Pip",
     "ambience": "repair",
     "description": "A servo is squeaky. Tune it until it hums right."},
    {"name": "Calm the Haywire Drone", "difficulty": "Medium", "giver": "Dot",
     "ambience": "repair",
     "description": "A little drone is spinning in circles and beeping in panic. Talk it down."},
    {"name": "The Great Oil Spill", "difficulty": "Hard", "giver": "Bolt",
     "ambience": "cleaning",
     "description": "Somebody knocked over the big oil drum. Clean the workshop floor before anyone slips."},
    {"name": "Market Run", "difficulty": "Easy", "giver": "Marge",
     "ambience": "gathering",
     "description": "The kitchen needs three ingredients for tonight's soup. Go to the market and fetch them."},
    {"name": "Perfect the Recipe", "difficulty": "Medium", "giver": "Belle",
     "ambience": "cooking",
     "description": "A cake keeps coming out flat. Taste it and tell the baker what it needs."},
    {"name": "Rescue the Burnt Dish", "difficulty": "Medium", "giver": "Gus",
     "ambience": "cooking",
     "description": "A pan was left on too long. Save dinner before the smoke alarm goes off."},
    {"name": "The Midnight Feast", "difficulty": "Hard", "giver": "Marge",
     "ambience": "cooking",
     "description": "Cook a whole feast for the hangout tonight: soup, main, and dessert, all from scratch."},
    {"name": "The Robot Who Wanted Soup", "difficulty": "Easy", "giver": "Belle",
     "ambience": "cooking",
     "description": "A robot has never tasted soup. Make him a bowl he can actually enjoy."},
    {"name": "Chef's New Helper", "difficulty": "Medium", "giver": "Gus",
     "ambience": "repair",
     "description": "A chef needs a spare pair of hands. Lend him your servo arm for the afternoon."},
    {"name": "The Broken Oven and the Broken Bot", "difficulty": "Hard", "giver": "Dot",
     "ambience": "repair",
     "description": "The kitchen oven died, and a repair robot is stuck in a loop. Fix them both."},
    {"name": "The Grand Hangout Fair", "difficulty": "Hard", "giver": "Marge",
     "ambience": "cooking",
     "description": "The whole hangout is holding a fair. Robots and chefs, everyone working together, one big day.",
     "coop": True},
]

TEMPLATE_BY_NAME = {t["name"]: t for t in QUEST_TEMPLATES}

# Quest ambience loops (Phase 23): the kind of work a quest
# is, so the game can play a matching sound in a loop while
# the quest runs, under the music and the giver's voice.
# Each ambience names a sound in sounds.py: cooking reuses
# the chef's sizzle, repair reuses the robot servo, and
# gathering and cleaning have their own loop files
# (ambience_gathering.mp3, ambience_cleaning.mp3 — see
# SOUNDS.md). An ambience whose file is not in sounds/ yet
# is silent, never an error: the game carries on, and the
# loop starts working once the file is uploaded.
AMBIENCES = ("cooking", "repair", "gathering", "cleaning")

AMBIENCE_SOUNDS = {
    "cooking": "chef_sizzle",
    "repair": "robot_servo",
    "gathering": "ambience_gathering",
    "cleaning": "ambience_cleaning",
}


def quest_ambience(quest):
    """The ambience of a quest: the kind of work it is.
    The quest itself may carry it, or it is looked up from
    the quest's name — server-dealt quests only carry the
    name, difficulty and giver, so the name lookup is what
    makes their loops work too. None when unknown."""
    quest = quest or {}
    ambience = quest.get("ambience")
    if ambience in AMBIENCE_SOUNDS:
        return ambience
    template = TEMPLATE_BY_NAME.get(quest.get("name"))
    if template:
        return template.get("ambience")
    return None


def ambience_sound_name(quest):
    """The SoundBank sound name for a quest's ambience
    loop, or None when the quest has no known ambience."""
    ambience = quest_ambience(quest)
    if ambience is None:
        return None
    return AMBIENCE_SOUNDS.get(ambience)

TASK_TYPES = ["Fetch", "Fix", "Cook", "Calm", "Deliver", "Teach",
              "Clean", "Rescue", "Tune", "Taste", "Build", "Find"]
ITEMS = ["a copper coil", "a brass bolt", "a bent spring",
         "a cracked gear", "carrots", "noodles", "a spice jar",
         "a soup pot", "a mop", "a rag", "a bucket",
         "a heating coil", "a new dial", "a cake", "a pan",
         "a servo arm", "a spare part", "a recipe card",
         "a basket of bread", "a jar of honey"]
PLACES = ["the workshop", "the kitchen", "the scrap yard",
          "the market", "the hangout", "the garden",
          "the pantry", "the tool shed"]
HELPERS = ["Zip Scout", "Bulkhead", "Mend-O-Matic", "Ghost Drone",
           "Chop-Chop Chef", "Grill Master Gus", "Baker Belle",
           "Zap Fox", "Ember Owl", "Scrap Rat"]

DIFFICULTIES = ("Easy", "Medium", "Hard")

# Quest duration in minutes, by difficulty. Never over 4 hours.
DURATION_MINUTES = {"Easy": (5, 15), "Medium": (15, 45), "Hard": (60, 240)}

# The quest timer cap (Phase 26): no quest ever takes
# longer than 4 hours, however high the quest level gets.
QUEST_DURATION_CAP_MINUTES = 240

# Reputation tiers, per giver. Proposed numbers from the design,
# decided by Makenna 2026-11-18 as the tiers to build.
REPUTATION_TIERS = [
    (3, "Helper"),
    (8, "Friend"),
    (15, "Trusted Friend"),
]

HEALING_MAX_LEVEL = 5
HEALING_PERCENTS = {1: 19, 2: 38, 3: 57, 4: 76, 5: 95}


def quest_reward(difficulty, quest_level):
    """Credits a quest pays, before any reputation bonus.
    Keyed to the quest level (Phase 26), not the fighter
    level: credits grow infinitely as quests level up."""
    level = max(1, int(quest_level))
    if difficulty == "Easy":
        return 5 + 2 * level
    if difficulty == "Hard":
        return 20 + 10 * level
    return 10 + 5 * level


# Quest levels (Phase 23, Makenna 2026-11-18): separate levels
# per activity, like Magic Worlds. Fighting gives combat XP
# toward the fighter level; quests give quest XP toward a
# separate quest level. Only finishing a quest earns quest XP.
# Scaled like quest credits (Medium mirrors a fight win's XP,
# 20 + 5 x level; Hard pays double a win), keyed to quest
# level, not fighter level.
def quest_xp(difficulty, quest_level):
    """Quest XP a finished quest pays, before the Insight boost."""
    quest_level = max(1, int(quest_level))
    if difficulty == "Easy":
        return 10 + 2 * quest_level
    if difficulty == "Hard":
        return 40 + 10 * quest_level
    return 20 + 5 * quest_level


def quest_xp_to_next(quest_level):
    """Quest XP needed to go from this quest level to the next.
    100 x quest level (100 for level 2, 200 for level 3),
    grows, never caps — mirrors combat XP."""
    return 100 * max(1, int(quest_level))


# Quest stats (Phase 23): one banked quest point per quest
# level-up, spent one point at a time, same Enter-on-the-line
# pattern as combat stats. Each maxes at 10 points. Charm:
# +5% quest credits per point. Renown: +10% chance of +1
# bonus reputation when a quest finishes per point (100% at
# 10 points — every finished quest earns the bonus). Insight:
# +5% quest XP per point. Quest levels give no max HP and no
# combat stat points; those belong to combat levels only.
QUEST_STAT_NAMES = ("charm", "renown", "insight")
QUEST_STAT_MAX = 10


def quest_stats_of(fighter):
    """The fighter's three quest stats, each 0-10."""
    stats = (fighter or {}).get("quest_stats") or {}
    return {name: max(0, min(QUEST_STAT_MAX, int(stats.get(name, 0) or 0)))
            for name in QUEST_STAT_NAMES}


def quest_level_of(fighter):
    """Quest level, 1 for a fighter who has never quested."""
    return max(1, int((fighter or {}).get("quest_level", 1) or 1))


def quest_xp_of(fighter):
    """Quest XP banked toward the next quest level."""
    return max(0, int((fighter or {}).get("quest_xp", 0) or 0))


def quest_points_of(fighter):
    """Banked quest points waiting to be spent."""
    return max(0, int((fighter or {}).get("quest_points", 0) or 0))


def quest_level_line(fighter):
    """One plain-words line for the quest level, for the Home
    tab next to the fighter level: 'Quest level 3, 40 quest
    experience to level 4.' At quest level 2 and up it also
    says the automatic bonus the quest level adds to all
    three quest stats (Phase 26)."""
    level = quest_level_of(fighter)
    to_next = quest_xp_to_next(level) - quest_xp_of(fighter)
    line = ("Quest level %d, %d quest experience to level %d."
            % (level, to_next, level + 1))
    auto = quest_auto_bonus_percent(fighter)
    if auto > 0:
        line += (" Your quest level adds %d percent to Charm, "
                 "Renown and Insight." % auto)
    return line


def quest_auto_bonus_percent(fighter):
    """The automatic bonus percent the quest level itself
    adds to each of the three quest stats (Phase 26, Makenna
    2026-11-18): +1% per quest level-up, like combat's
    automatic +10 HP per combat level. At quest level 1
    nothing has levelled up yet, so the bonus is 0; at quest
    level 5 it is 4%. It stacks with spent quest points and
    never caps. Makenna can ask for a different rate."""
    return max(0, quest_level_of(fighter) - 1)


def quest_stat_effect_percent(fighter, stat):
    """The full effect of a quest stat, in percent: what the
    spent points give, plus the automatic bonus from the
    quest level (Phase 26). Charm and Insight give 5% per
    spent point, Renown 10% per spent point, and every stat
    gets +1% per quest level-up. Renown's chance can never
    pass 100%."""
    stats = quest_stats_of(fighter)
    auto = quest_auto_bonus_percent(fighter)
    if stat == "charm":
        return stats["charm"] * 5 + auto
    if stat == "renown":
        return min(100, stats["renown"] * 10 + auto)
    if stat == "insight":
        return stats["insight"] * 5 + auto
    return auto


def quest_stat_line(fighter, stat):
    """One plain-words line for a quest stat, saying its value
    and what one more point does. This is what the hangout
    list speaks; Enter on the line spends one banked point.
    The percent shown is the full effect: spent points plus
    the automatic bonus from the quest level (Phase 26). At
    quest level 1 the automatic bonus is 0, so the line
    reads exactly as it did before."""
    stats = quest_stats_of(fighter)
    value = stats[stat]
    auto = quest_auto_bonus_percent(fighter)
    total = quest_stat_effect_percent(fighter, stat)
    if stat == "charm":
        if auto > 0:
            return (
                "Charm, %d. Quests pay %d percent more credits, "
                "%d from your quest level. "
                "One more point adds 5 percent."
                % (value, total, auto)
            )
        return (
            "Charm, %d. Quests pay %d percent more credits. "
            "One more point adds 5 percent."
            % (value, value * 5)
        )
    if stat == "renown":
        if auto > 0:
            return (
                "Renown, %d. %d percent chance of 1 bonus reputation "
                "when a quest finishes, %d from your quest level. "
                "One more point adds 10 percent."
                % (value, total, auto)
            )
        return (
            "Renown, %d. %d percent chance of 1 bonus reputation "
            "when a quest finishes. One more point adds 10 percent."
            % (value, value * 10)
        )
    if stat == "insight":
        if auto > 0:
            return (
                "Insight, %d. Quests pay %d percent more quest "
                "experience, %d from your quest level. "
                "One more point adds 5 percent."
                % (value, total, auto)
            )
        return (
            "Insight, %d. Quests pay %d percent more quest "
            "experience. One more point adds 5 percent."
            % (value, value * 5)
        )
    return stat


def quest_duration_minutes(difficulty, rng=None, quest_level=1):
    """How long a quest takes, in minutes. Grows with the
    quest level (Phase 26, Makenna 2026-11-18): the base
    range is multiplied by (1 + 0.1 x (quest level - 1)),
    never over 4 hours (240 minutes). At quest level 1 the
    ranges are exactly as before: Easy 5-15, Medium 15-45,
    Hard 60-240. The server uses the same rule, so a quest
    dealt on either side takes the same kind of time."""
    low, high = DURATION_MINUTES.get(difficulty, (15, 45))
    factor = 1 + 0.1 * (max(1, int(quest_level)) - 1)
    low = min(QUEST_DURATION_CAP_MINUTES, int(low * factor))
    high = min(QUEST_DURATION_CAP_MINUTES, int(high * factor))
    high = max(low, high)
    rng = rng or random
    return rng.randint(low, high)


def tier_name(reputation):
    """Tier name for a reputation count, or Stranger below 3."""
    name = "Stranger"
    for needed, tier in REPUTATION_TIERS:
        if reputation >= needed:
            name = tier
    return name


def next_tier(reputation):
    """The next reputation tier not yet reached, as
    (needed, name) — or None when the giver is already at
    the top tier, Trusted Friend (15+), where reputation
    keeps building with no cap and no higher tier."""
    for needed, tier in REPUTATION_TIERS:
        if reputation < needed:
            return needed, tier
    return None


def reputation_line(giver, rep_after, gained=1):
    """One plain-words line for a finished quest: the reputation
    gained, the new total with that giver, and how far to the
    next tier — or the top tier, when there is no next tier.
    Spoken by the giver on completion. gained is normally 1;
    Renown (Phase 23) can make it 2 when the bonus lands."""
    nxt = next_tier(rep_after)
    if nxt is None:
        return (
            "You gained %d reputation with %s. You have %s reputation "
            "with %s. That is the top tier, Trusted Friend, and your "
            "reputation keeps building with no cap."
            % (gained, giver, rep_after, giver))
    needed, name = nxt
    return (
        "You gained %d reputation with %s. You have %s reputation "
        "with %s, %s more to reach %s."
        % (gained, giver, rep_after, giver, needed - rep_after, name))


def reputation_summary(reputation):
    """One plain line per giver, for the hangout list."""
    lines = []
    for giver in GIVERS:
        rep = int((reputation or {}).get(giver["name"], 0) or 0)
        if rep > 0:
            lines.append("%s — %s." % (giver["name"], tier_name(rep)))
    return lines


def generate_quest(rng=None, difficulty=None, existing_ids=None,
                   coop_allowed=True, existing_names=None, quest_level=1):
    """Deal one fresh quest, endlessly generated.

    A template name and giver, varied with a random task, item,
    place and helper, so the same quest never repeats exactly.
    existing_ids are never dealt again, and a template name
    already on the board is never dealt twice on the same
    board. Co-op quests (the Grand Hangout Fair) are only
    dealt when coop_allowed is true, so at most one co-op
    quest is ever on the board at once. No quest is ever
    restricted by fighter kind: every quest here is open to
    robots and chefs alike. The quest's duration grows with
    the quest level (Phase 26); at quest level 1 it is the
    plain base range.
    """
    rng = rng or random.Random()
    existing = set(existing_ids or [])
    names = set(existing_names or [])
    templates = [t for t in QUEST_TEMPLATES
                 if coop_allowed or not t.get("coop")]
    if difficulty:
        templates = [t for t in templates
                     if t["difficulty"] == difficulty] or templates
    for _ in range(100):
        template = rng.choice(templates)
        if template["name"] in names:
            continue
        task = rng.choice(TASK_TYPES)
        item = rng.choice(ITEMS)
        place = rng.choice(PLACES)
        helper = rng.choice(HELPERS)
        giver = GIVER_BY_NAME[template["giver"]]
        quest_id = "q_%s_%s" % (
            template["name"].lower().replace(" ", "_").replace("'", ""),
            rng.randrange(100000, 999999))
        if quest_id in existing:
            continue
        description = "%s %s needs %s in %s. %s" % (
            task, helper, item, place, template["description"])
        return {
            "id": quest_id,
            "name": template["name"],
            "description": description,
            "giver": giver["name"],
            "giver_voice": giver["voice"],
            "giver_gender": giver["gender"],
            "difficulty": template["difficulty"],
            "ambience": template["ambience"],
            "duration_minutes": quest_duration_minutes(
                template["difficulty"], rng, quest_level),
            "coop": bool(template.get("coop")),
        }
    raise ValueError("could not deal a fresh quest")


def starting_board(rng=None, quest_level=1):
    """The starting board of 5: 2 Easy, 2 Medium, 1 Hard.

    Givers are dealt in a shuffled order from all six, so the
    board always holds both male and female givers — three
    male, three female in the full set, never one gender only.
    Durations grow with the quest level (Phase 26).
    """
    rng = rng or random.Random()
    givers = list(GIVERS)
    rng.shuffle(givers)
    board = []
    seen = set()
    names = set()
    for i, difficulty in enumerate(
            ["Easy", "Easy", "Medium", "Medium", "Hard"]):
        quest = generate_quest(rng, difficulty, seen,
                               existing_names=names,
                               quest_level=quest_level)
        names.add(quest["name"])
        # Deal the shuffled givers in order, so the board
        # mixes male and female givers instead of leaving
        # the mix to chance.
        giver = givers[i % len(givers)]
        quest["giver"] = giver["name"]
        quest["giver_voice"] = giver["voice"]
        quest["giver_gender"] = giver["gender"]
        board.append(quest)
        seen.add(quest["id"])
    return board
