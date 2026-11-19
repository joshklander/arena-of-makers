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

Rewards, by difficulty and level (a Medium quest pays exactly
what a fight win pays; Hard pays double a fight):
  Easy:   5 + 2 x level credits
  Medium: 10 + 5 x level credits
  Hard:   20 + 10 x level credits

Quest durations: a few minutes to 2-4 hours, never over 4
hours. Easy quests are short (5-15 minutes), Medium longer
(15-45 minutes), Hard longest (1-4 hours).

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
     "description": "The workshop is out of scrap. Fetch three pieces from the scrap yard."},
    {"name": "Tune-Up Time", "difficulty": "Easy", "giver": "Pip",
     "description": "A servo is squeaky. Tune it until it hums right."},
    {"name": "Calm the Haywire Drone", "difficulty": "Medium", "giver": "Dot",
     "description": "A little drone is spinning in circles and beeping in panic. Talk it down."},
    {"name": "The Great Oil Spill", "difficulty": "Hard", "giver": "Bolt",
     "description": "Somebody knocked over the big oil drum. Clean the workshop floor before anyone slips."},
    {"name": "Market Run", "difficulty": "Easy", "giver": "Marge",
     "description": "The kitchen needs three ingredients for tonight's soup. Go to the market and fetch them."},
    {"name": "Perfect the Recipe", "difficulty": "Medium", "giver": "Belle",
     "description": "A cake keeps coming out flat. Taste it and tell the baker what it needs."},
    {"name": "Rescue the Burnt Dish", "difficulty": "Medium", "giver": "Gus",
     "description": "A pan was left on too long. Save dinner before the smoke alarm goes off."},
    {"name": "The Midnight Feast", "difficulty": "Hard", "giver": "Marge",
     "description": "Cook a whole feast for the hangout tonight: soup, main, and dessert, all from scratch."},
    {"name": "The Robot Who Wanted Soup", "difficulty": "Easy", "giver": "Belle",
     "description": "A robot has never tasted soup. Make him a bowl he can actually enjoy."},
    {"name": "Chef's New Helper", "difficulty": "Medium", "giver": "Gus",
     "description": "A chef needs a spare pair of hands. Lend him your servo arm for the afternoon."},
    {"name": "The Broken Oven and the Broken Bot", "difficulty": "Hard", "giver": "Dot",
     "description": "The kitchen oven died, and a repair robot is stuck in a loop. Fix them both."},
    {"name": "The Grand Hangout Fair", "difficulty": "Hard", "giver": "Marge",
     "description": "The whole hangout is holding a fair. Robots and chefs, everyone working together, one big day.",
     "coop": True},
]

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

# Reputation tiers, per giver. Proposed numbers from the design,
# decided by Makenna 2026-11-18 as the tiers to build.
REPUTATION_TIERS = [
    (3, "Helper"),
    (8, "Friend"),
    (15, "Trusted Friend"),
]

HEALING_MAX_LEVEL = 5
HEALING_PERCENTS = {1: 19, 2: 38, 3: 57, 4: 76, 5: 95}


def quest_reward(difficulty, level):
    """Credits a quest pays, before any reputation bonus."""
    level = max(1, int(level))
    if difficulty == "Easy":
        return 5 + 2 * level
    if difficulty == "Hard":
        return 20 + 10 * level
    return 10 + 5 * level


def quest_duration_minutes(difficulty, rng=None):
    """How long a quest takes, in minutes. Never over 4 hours."""
    low, high = DURATION_MINUTES.get(difficulty, (15, 45))
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


def reputation_line(giver, rep_after):
    """One plain-words line for a finished quest: the +1
    reputation gained, the new total with that giver, and
    how far to the next tier — or the top tier, when there
    is no next tier. Spoken by the giver on completion."""
    nxt = next_tier(rep_after)
    if nxt is None:
        return (
            "You gained 1 reputation with %s. You have %s reputation "
            "with %s. That is the top tier, Trusted Friend, and your "
            "reputation keeps building with no cap."
            % (giver, rep_after, giver))
    needed, name = nxt
    return (
        "You gained 1 reputation with %s. You have %s reputation "
        "with %s, %s more to reach %s."
        % (giver, rep_after, giver, needed - rep_after, name))


def reputation_summary(reputation):
    """One plain line per giver, for the hangout list."""
    lines = []
    for giver in GIVERS:
        rep = int((reputation or {}).get(giver["name"], 0) or 0)
        if rep > 0:
            lines.append("%s — %s." % (giver["name"], tier_name(rep)))
    return lines


def generate_quest(rng=None, difficulty=None, existing_ids=None,
                   coop_allowed=True, existing_names=None):
    """Deal one fresh quest, endlessly generated.

    A template name and giver, varied with a random task, item,
    place and helper, so the same quest never repeats exactly.
    existing_ids are never dealt again, and a template name
    already on the board is never dealt twice on the same
    board. Co-op quests (the Grand Hangout Fair) are only
    dealt when coop_allowed is true, so at most one co-op
    quest is ever on the board at once. No quest is ever
    restricted by fighter kind: every quest here is open to
    robots and chefs alike.
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
            "duration_minutes": quest_duration_minutes(
                template["difficulty"], rng),
            "coop": bool(template.get("coop")),
        }
    raise ValueError("could not deal a fresh quest")


def starting_board(rng=None):
    """The starting board of 5: 2 Easy, 2 Medium, 1 Hard.

    Givers are dealt in a shuffled order from all six, so the
    board always holds both male and female givers — three
    male, three female in the full set, never one gender only.
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
                               existing_names=names)
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
