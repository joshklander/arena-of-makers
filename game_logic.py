"""Arena of Makers - game logic.

This module has no wxPython dependency on purpose: the whole game can be
exercised headlessly (fighter creation, one fight, save and load) without a
display or a screen reader. The wxPython window in main.py is only a
front end over these functions.

Design rules from the design note, kept here in code:
- Endless progression: weapon, armor and fighter levels have no cap.
- Every timer is capped at 2 to 4 hours. The longest wait in the game is
  4 hours (MAX_TIMER_SECONDS); early waits are minutes.
- Errors are plain sentences, never codes.
- No secrets or API keys anywhere. The game never saves to a
  local file: there is no arena_save.json, no local JSON at
  all. Fighters live only in the one shared Supabase table.
- Stats (STATS_DESIGN.md): 5 stats, 2 stat points per level-up,
  bankable, no caps. Health always grows with level: every
  level-up gives +10 max HP regardless (gain_xp), and each
  Health point adds +10 max HP on top. Max HP is
  100 + 10 x (level - 1) + 10 x Health. The upgrade currency
  is called "credits", never "points" (stat points keep their
  own name). No single hit may deal more than 75% of the
  target's max health (server fairness guard, mirrored here).
"""

import json
import math
import os
import random
import time

import quests

# The longest any upgrade or repair may take: 4 hours.
MAX_TIMER_SECONDS = 4 * 3600

# One starter creature for the skeleton. More creatures come later.
CREATURE_NAME = "Scrap Rat"

# NPC creatures (Phase 24): the 9 draft NPCs from NPC_DESIGN.md,
# now real fightable opponents. Each is a multiplier on the
# Scrap Rat formulas, so a fight stays fair at any level, plus
# a special ability that fires every few rounds, plus its own
# appear and hit sounds (Makenna's per-creature sound rule,
# Nov 18, 2026: every creature gets its OWN appear and hit
# sounds, different from Scrap Rat and from each other, so you
# can tell who it is by sound alone). "profile" is the NPC's
# stat weights (speed / strength / health / defense / luck),
# the same 2 stat points per level as a fighter, split by the
# profile in STATS_DESIGN.md. The server keeps the same table
# (supabase/migrations/*_npc_creatures.sql) and is the only
# judge of an NPC fight, exactly as for Scrap Rat.
NPCS = {
    "zip_scout": {
        "name": "Zip Scout", "kind": "robot",
        "hp_mult": 0.7, "dmg_mult": 1.4, "reward_mult": 1.2,
        "ability": "double_hit", "ability_every": 3,
        "ability_line": "Zip Scout dashes in twice!",
        "profile": {"speed": 4, "strength": 3, "health": 1,
                    "defense": 1, "luck": 1},
        "appear_sound": "npc_zip_scout_appear",
        "hit_sound": "npc_zip_scout_hit",
    },
    "bulkhead": {
        "name": "Bulkhead", "kind": "robot",
        "hp_mult": 1.8, "dmg_mult": 0.7, "reward_mult": 1.1,
        "ability": "shield", "ability_every": 4,
        "ability_line": "Bulkhead raises its plating shield! "
                        "Your hit bounces off!",
        "profile": {"speed": 1, "strength": 1, "health": 4,
                    "defense": 3, "luck": 1},
        "appear_sound": "npc_bulkhead_appear",
        "hit_sound": "npc_bulkhead_hit",
    },
    "mend_o_matic": {
        "name": "Mend-O-Matic", "kind": "robot",
        "hp_mult": 1.0, "dmg_mult": 0.9, "reward_mult": 1.2,
        "ability": "self_repair", "ability_every": 3,
        "ability_line": "Mend-O-Matic sparks and repairs itself!",
        "profile": {"speed": 2, "strength": 2, "health": 3,
                    "defense": 2, "luck": 1},
        "appear_sound": "npc_mend_o_matic_appear",
        "hit_sound": "npc_mend_o_matic_hit",
    },
    "ghost_drone": {
        "name": "Ghost Drone", "kind": "robot",
        "hp_mult": 0.8, "dmg_mult": 1.2, "reward_mult": 1.2,
        "ability": "vanish", "ability_every": 3,
        "ability_line": "Ghost Drone vanishes! Your hit misses!",
        "profile": {"speed": 4, "strength": 3, "health": 1,
                    "defense": 0, "luck": 2},
        "appear_sound": "npc_ghost_drone_appear",
        "hit_sound": "npc_ghost_drone_hit",
    },
    "chop_chop": {
        "name": "Chop-Chop Chef", "kind": "chef",
        "hp_mult": 0.75, "dmg_mult": 1.3, "reward_mult": 1.2,
        "ability": "double_hit", "ability_every": 4,
        "ability_line": "Chop-Chop Chef chops twice!",
        "profile": {"speed": 4, "strength": 3, "health": 1,
                    "defense": 1, "luck": 1},
        "appear_sound": "npc_chop_chop_appear",
        "hit_sound": "npc_chop_chop_hit",
    },
    "grill_gus": {
        "name": "Grill Master Gus", "kind": "chef",
        "hp_mult": 1.6, "dmg_mult": 0.85, "reward_mult": 1.1,
        "ability": "flare", "ability_every": 3,
        "ability_line": "Grill Master Gus fires up the grill! "
                        "A burst of flame!",
        "profile": {"speed": 1, "strength": 2, "health": 4,
                    "defense": 2, "luck": 1},
        "appear_sound": "npc_grill_gus_appear",
        "hit_sound": "npc_grill_gus_hit",
    },
    "baker_belle": {
        "name": "Baker Belle", "kind": "chef",
        "hp_mult": 1.1, "dmg_mult": 1.0, "reward_mult": 1.2,
        "ability": "sugar_trap", "ability_every": 4,
        "ability_line": "Baker Belle throws a sugar trap! "
                        "Your next hit is sticky and weak!",
        "profile": {"speed": 2, "strength": 2, "health": 3,
                    "defense": 2, "luck": 1},
        "appear_sound": "npc_baker_belle_appear",
        "hit_sound": "npc_baker_belle_hit",
    },
    "zap_fox": {
        "name": "Zap Fox", "kind": "animal",
        "hp_mult": 0.9, "dmg_mult": 1.25, "reward_mult": 1.2,
        "ability": "shock", "ability_every": 3,
        "ability_line": "Zap Fox crackles with static! A shock!",
        "profile": {"speed": 4, "strength": 3, "health": 1,
                    "defense": 0, "luck": 2},
        "appear_sound": "npc_zap_fox_appear",
        "hit_sound": "npc_zap_fox_hit",
    },
    "ember_owl": {
        "name": "Ember Owl", "kind": "animal",
        "hp_mult": 1.3, "dmg_mult": 0.95, "reward_mult": 1.1,
        "ability": "dodge", "ability_every": 5,
        "ability_line": "Ember Owl swoops aside! Your hit misses!",
        "profile": {"speed": 2, "strength": 1, "health": 4,
                    "defense": 2, "luck": 1},
        "appear_sound": "npc_ember_owl_appear",
        "hit_sound": "npc_ember_owl_hit",
    },
}

# The random fight pool: Scrap Rat stays in as the starter,
# and the 9 NPCs join it. Every opponent is always at the
# fighter's own level, so matchmaking stays fair.
NPC_ORDER = [
    "zip_scout", "bulkhead", "mend_o_matic", "ghost_drone",
    "chop_chop", "grill_gus", "baker_belle", "zap_fox", "ember_owl",
]
NPC_POOL = ["scrap_rat"] + NPC_ORDER


def random_npc_id(rng=None):
    """Pick one creature at random from the fight pool:
    Scrap Rat or one of the 9 NPCs, all equally likely."""
    if rng is None:
        rng = random.Random()
    return rng.choice(NPC_POOL)


def npc_by_name(name):
    """The npc_id for a creature's display name, or None.
    Used to find which creature a narration line is about."""
    for npc_id, npc in NPCS.items():
        if npc["name"] == name:
            return npc_id
    return None


def creature_in_line(line):
    """Which creature a narration line is about: an npc_id,
    "scrap_rat", or None when the line names no creature.
    Used to pick the right sound for the line."""
    for npc_id, npc in NPCS.items():
        if npc["name"] in line:
            return npc_id
    if CREATURE_NAME in line:
        return "scrap_rat"
    return None

# Level-up stat choices. No cap on any stat, no cap on level.
STAT_NAMES = ("strength", "defense", "health", "speed", "luck")
STAT_POINTS_PER_LEVEL = 2
# No single hit, normal or critical, may deal more than this
# share of the target's max health. The server is the judge;
# this mirror is only for local testing and for showing the
# player what a point would do.
FAIRNESS_GUARD = 0.75
# A respec (reset all stats) is free the first time, then
# costs this many credits.
RESPEC_COST_CREDITS = 100


def format_time(seconds):
    """Round a wait to plain words, like the game speaks it."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "less than a minute"
    if seconds < 3600:
        minutes = int(round(seconds / 60.0))
        if minutes <= 1:
            return "about 1 minute"
        return "about %d minutes" % minutes
    hours = seconds / 3600.0
    if hours < 2:
        return "about 1 hour"
    return "about %d hours" % int(round(hours))


def new_fighter(name, kind, gender="male"):
    """Create a level 1 fighter. kind is 'robot' or 'chef',
    gender is 'male' or 'female' (it picks the voice)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Give your fighter a name first.")
    if kind not in ("robot", "chef"):
        raise ValueError("Pick robot or chef for your fighter.")
    if gender not in ("male", "female"):
        raise ValueError("Pick male or female for your fighter.")
    if kind == "robot":
        weapon_name = "Laser Blaster"
        armor_name = "Scrap Plating"
    else:
        weapon_name = "Trusty Spatula"
        armor_name = "Chef Apron"
    return {
        "name": name,
        "kind": kind,
        "gender": gender,
        "level": 1,
        "xp": 0,
        "hp": 100,
        "max_hp": 100,
        # The upgrade currency is called "credits". Older
        # fighters may still carry "points"; credits_of()
        # below reads credits first, points second.
        "credits": 0,
        "wins": 0,
        "losses": 0,
        "weapon_name": weapon_name,
        "weapon_level": 1,
        "armor_name": armor_name,
        "armor_level": 1,
        # The 5 level-up stats, all starting at 0, plus a
        # base Speed of 5 (see fighter_speed). Unspent stat
        # points sit in "stat_points" and can be spent any
        # time, 2 per level-up.
        "stats": {name: 0 for name in STAT_NAMES},
        "stat_points": 0,
        # New fighters need no migration; the server sets
        # this false only for fighters made before stats.
        "stats_migrated": True,
        # How many respecs (full stat resets) this fighter
        # has used: the first is free, later ones cost credits.
        "respecs_used": 0,
        # Epoch seconds when the current repair finishes, or 0.
        "repair_until": 0,
        # Current timed upgrade, or None: {"slot": "weapon"|"armor",
        # "level": new level, "finish": epoch seconds}.
        "upgrade": None,
        # Queued levels left for a max-affordable upgrade, or
        # None: a list of target levels, run one after another.
        "upgrade_queue": None,
        # How many levels the running max-affordable queue had
        # in total, so the game can say when it is all done.
        "upgrade_total": 0,
        # Healing skill, from hangout quest gifts (Phase 18):
        # level 0-5, healing 19%, 38%, 57%, 76%, 95% of health.
        # It never goes past level 5, 95%.
        "healing_level": 0,
        # Quest levels (Phase 23): separate from the combat
        # level. Quests give quest XP toward a separate quest
        # level; each quest level-up banks 1 quest point for
        # Charm, Renown or Insight (see quests.py), each max
        # 10. Quest levels give no max HP and no combat stat
        # points.
        "quest_level": 1,
        "quest_xp": 0,
        "quest_points": 0,
        "quest_stats": {"charm": 0, "renown": 0, "insight": 0},
    }


def stats_of(fighter):
    """The fighter's 5 stats, with 0 for anything missing, so
    fighters made before stats still work."""
    stats = fighter.get("stats") or {}
    return {name: int(stats.get(name) or 0) for name in STAT_NAMES}


def credits_of(fighter):
    """The fighter's spendable balance. Credits first; older
    fighters may still carry "points", which count 1-for-1
    until the server converts them (see apply_timers). A
    zero credits balance still falls through to points, so
    a fighter that has not been converted yet is never read
    as broke."""
    credits = fighter.get("credits")
    if credits:
        return credits
    return fighter.get("points") or 0


def stat_crit_chance(luck):
    """Critical-hit chance in percent, with diminishing
    returns, never a cap: 50 x Luck / (Luck + 25)."""
    luck = max(0, int(luck))
    if luck <= 0:
        return 0.0
    return 50.0 * luck / (luck + 25)


def stat_dodge_chance(advantage):
    """Dodge chance in percent when faster than the enemy,
    with diminishing returns, never reaching 20 percent:
    20 x advantage / (advantage + 20)."""
    advantage = max(0, int(advantage))
    if advantage <= 0:
        return 0.0
    return 20.0 * advantage / (advantage + 20)


def fighter_speed(fighter):
    """Speed: base 5, plus 1 per Speed point."""
    return 5 + stats_of(fighter)["speed"]


def fighter_max_hp(fighter):
    """Max health: 100, plus 10 for every level above 1
    (health always grows with level, no matter what you
    choose), plus 10 for every Health point on top."""
    return 100 + 10 * (fighter["level"] - 1) + 10 * stats_of(fighter)["health"]


def distribute_points(total, weights):
    """Split stat points by fixed weights, largest remainder,
    ties broken in the order given. weights is a list of
    (name, weight); returns {name: points}. Used for the
    Scrap Rat's balanced profile and for NPC profiles later."""
    total = max(0, int(total))
    weight_sum = sum(weight for _name, weight in weights) or 1
    result = {}
    fractions = []
    given = 0
    for order, (name, weight) in enumerate(weights):
        exact = total * weight / float(weight_sum)
        base = int(math.floor(exact))
        result[name] = base
        given += base
        fractions.append((exact - base, -order, name))
    left = total - given
    fractions.sort(reverse=True)
    for _frac, _neg_order, name in fractions:
        if left <= 0:
            break
        result[name] += 1
        left -= 1
    return result


def xp_to_next_level(level):
    """XP needed to go from this level to the next. Grows, never caps."""
    return 100 * level


def weapon_damage(fighter):
    """Damage per hit. Climbs forever with weapon level and fighter level,
    plus 2 per Strength point."""
    base = 12 if fighter["kind"] == "robot" else 10
    return (
        base
        + 5 * (fighter["weapon_level"] - 1)
        + 2 * (fighter["level"] - 1)
        + 2 * stats_of(fighter)["strength"]
    )


def armor_defense(fighter):
    """Damage soaked per hit. Climbs forever with armor and fighter level,
    plus 2 per Defense point (so 1 more damage soaked per hit)."""
    return (
        2
        + 2 * (fighter["armor_level"] - 1)
        + (fighter["level"] - 1)
        + 2 * stats_of(fighter)["defense"]
    )


def upgrade_cost(level):
    """Credits to raise a weapon or armor from this level to the next.

    Costs climb (1.5 times per level, rounded) and never stop, because
    there is no top level.
    """
    return int(round(25 * (1.5 ** (level - 1))))


def upgrade_duration_seconds(level):
    """How long an upgrade to the next level takes, capped at 4 hours."""
    return min(60 * level, MAX_TIMER_SECONDS)


def repair_duration_seconds(level):
    """How long repairs take after losing, capped at 4 hours."""
    return min(300 * level, MAX_TIMER_SECONDS)


def is_repairing(fighter, now=None):
    """True while a repair is still running."""
    if now is None:
        now = time.time()
    return fighter.get("repair_until", 0) > now


def repair_left_seconds(fighter, now=None):
    if now is None:
        now = time.time()
    return max(0, fighter.get("repair_until", 0) - now)


def gain_xp(fighter, amount):
    """Add XP, applying as many level-ups as it earns. Returns new levels.

    Health always grows with level: every level-up gives +10 max HP
    regardless of what the player chooses, and the fighter heals to
    full. Each level-up also banks 2 stat points to spend."""
    fighter["xp"] += amount
    gained = 0
    while fighter["xp"] >= xp_to_next_level(fighter["level"]):
        fighter["xp"] -= xp_to_next_level(fighter["level"])
        fighter["level"] += 1
        fighter["max_hp"] += 10
        fighter["hp"] = fighter["max_hp"]
        fighter["stat_points"] = fighter.get("stat_points", 0) + STAT_POINTS_PER_LEVEL
        gained += 1
    return gained


def stat_line(fighter, stat):
    """One plain-words line for a stat, saying its value and what
    one more point does. This is what the Stats list speaks."""
    stats = stats_of(fighter)
    value = stats[stat]
    if stat == "strength":
        return (
            "Strength, %d. One more point adds 2 damage. Your damage is %d."
            % (value, weapon_damage(fighter))
        )
    if stat == "defense":
        return (
            "Defense, %d. One more point soaks 1 more damage. You soak %d."
            % (value, armor_defense(fighter) // 2)
        )
    if stat == "health":
        return (
            "Health, %d. One more point adds 10 health. Your health is %d."
            % (value, fighter_max_hp(fighter))
        )
    if stat == "speed":
        return (
            "Speed, %d. One more point makes you a little faster. You hit "
            "first when you are faster than your enemy."
            % value
        )
    if stat == "luck":
        return (
            "Luck, %d. One more point adds a little critical chance. Your "
            "critical chance is about %d percent. A critical hit deals half "
            "as much damage again."
            % (value, int(round(stat_crit_chance(value))))
        )
    return stat


def spend_stat(fighter, stat):
    """Spend one banked stat point. Returns (error, line): error is
    a plain-words problem, or None when the point was spent. One
    point per call, one stat per call. A Health point also heals
    +10 HP right away, up to the new max."""
    if stat not in STAT_NAMES:
        return "Pick strength, defense, health, speed or luck.", None
    if fighter.get("stat_points", 0) <= 0:
        return "You have no stat points to spend right now.", None
    stats = stats_of(fighter)
    stats[stat] += 1
    fighter["stats"] = stats
    fighter["stat_points"] -= 1
    if stat == "health":
        fighter["max_hp"] = fighter_max_hp(fighter)
        fighter["hp"] = min(fighter["hp"] + 10, fighter["max_hp"])
    # Banked points may all go into one stat: stay on the line
    # and press Enter again for the next point. The line always
    # says how many points are left, so the player knows when
    # the bank is empty.
    left = fighter["stat_points"]
    if left > 0:
        tail = " You have %d stat %s left." % (
            left,
            "point" if left == 1 else "points",
        )
    else:
        tail = " That was your last stat point."
    return None, stat_line(fighter, stat) + tail


def spend_quest_stat(fighter, stat):
    """Spend one banked quest point, offline only (online, the
    server decides, exactly as for combat stats). Returns
    (error, line). One point per call, one stat per call, max
    10 points in any one quest stat. Quest levels give no max
    HP and no combat stat points."""
    if stat not in quests.QUEST_STAT_NAMES:
        return "Pick charm, renown, or insight.", None
    if fighter.get("quest_points", 0) <= 0:
        return "You have no quest points to spend right now.", None
    stats = quests.quest_stats_of(fighter)
    if stats[stat] >= quests.QUEST_STAT_MAX:
        return (
            "%s is already at its best, level %d."
            % (stat.capitalize(), quests.QUEST_STAT_MAX)
        ), None
    stats[stat] += 1
    fighter["quest_stats"] = stats
    fighter["quest_points"] -= 1
    left = fighter["quest_points"]
    if left > 0:
        tail = " You have %d quest %s left." % (
            left,
            "point" if left == 1 else "points",
        )
    else:
        tail = " That was your last quest point."
    return None, quests.quest_stat_line(fighter, stat) + tail


def respec_stats(fighter):
    """Reset all 5 stats, refunding every spent point to unspent
    stat points. The first respec is free; later ones cost
    100 credits. Returns (error, line). Level, weapon, armor,
    wins, losses and fighter kind are never touched."""
    stats = stats_of(fighter)
    spent = sum(stats.values())
    if spent <= 0:
        return "You have no stat points spent to reset.", None
    cost = 0 if fighter.get("respecs_used", 0) <= 0 else RESPEC_COST_CREDITS
    if cost > credits_of(fighter):
        return (
            "A respec costs %d credits and you have %d credits."
            % (cost, credits_of(fighter))
        ), None
    if cost > 0:
        fighter["credits"] = credits_of(fighter) - cost
        fighter.pop("points", None)
    fighter["stats"] = {name: 0 for name in STAT_NAMES}
    fighter["stat_points"] = fighter.get("stat_points", 0) + spent
    fighter["respecs_used"] = fighter.get("respecs_used", 0) + 1
    fighter["max_hp"] = fighter_max_hp(fighter)
    fighter["hp"] = min(fighter["hp"], fighter["max_hp"])
    if cost > 0:
        line = (
            "Your stats are reset. You have %d stat points to spend. "
            "That respec cost %d credits."
            % (fighter["stat_points"], cost)
        )
    else:
        line = (
            "Your stats are reset. You have %d stat points to spend. "
            "Your first respec was free."
            % fighter["stat_points"]
        )
    return None, line


def creature_for_level(level, npc_id="scrap_rat"):
    """A creature scaled to the fighter's level so fights stay
    real as the fighter climbs. There is no top level for either
    side.

    Scrap Rat gets the same 2 stat points per level as a
    fighter, split evenly across the 5 stats. An NPC gets the
    same 2 points per level split by its own profile, and its
    health and damage are the Scrap Rat formulas times its
    multipliers, so fights stay even as the fighter builds
    stats: its health, damage, soak, speed and crit chance all
    grow with level, using the same formulas as a fighter.
    An unknown npc_id falls back to Scrap Rat."""
    if npc_id in NPCS:
        npc = NPCS[npc_id]
        stats = distribute_points(
            STAT_POINTS_PER_LEVEL * (level - 1),
            [(name, npc["profile"].get(name, 0)) for name in STAT_NAMES],
        )
        base_hp = 30 + 15 * (level - 1)
        base_dmg = 4 + 2 * (level - 1)
        hp = int(round(base_hp * npc["hp_mult"])) + 10 * stats["health"]
        dmg = int(round(base_dmg * npc["dmg_mult"])) + 2 * stats["strength"]
        return {
            "npc_id": npc_id,
            "name": npc["name"],
            "kind": npc["kind"],
            "level": level,
            "hp": hp,
            "max_hp": hp,
            "damage": dmg,
            "soak": stats["defense"],
            "speed": 5 + stats["speed"],
            "crit_chance": stat_crit_chance(stats["luck"]),
            "stats": stats,
            "ability": npc["ability"],
            "ability_every": npc["ability_every"],
            "ability_line": npc["ability_line"],
            "reward_mult": npc["reward_mult"],
        }
    stats = distribute_points(
        STAT_POINTS_PER_LEVEL * (level - 1),
        [(name, 2) for name in STAT_NAMES],
    )
    return {
        "npc_id": "scrap_rat",
        "name": CREATURE_NAME,
        "kind": "animal",
        "level": level,
        "hp": 30 + 15 * (level - 1) + 10 * stats["health"],
        "max_hp": 30 + 15 * (level - 1) + 10 * stats["health"],
        "damage": 4 + 2 * (level - 1) + 2 * stats["strength"],
        "soak": stats["defense"],
        "speed": 5 + stats["speed"],
        "crit_chance": stat_crit_chance(stats["luck"]),
        "stats": stats,
        "ability": None,
        "ability_every": 0,
        "ability_line": "",
        "reward_mult": 1.0,
    }


def _guarded_hit(hit, target_max_hp):
    """The server fairness guard, mirrored here: no single hit,
    normal or critical, may deal more than 75% of the target's
    max health."""
    return max(1, min(hit, int(FAIRNESS_GUARD * target_max_hp)))


def fight(fighter, rng=None, now=None, npc_id="scrap_rat"):
    """Fight one creature. Returns a result dict with plain-words lines.

    The fighter must not be under repair. The result tells the window
    what happened, what was won or lost, and what to say next.

    npc_id picks the opponent: "scrap_rat" (the starter) or one of
    the 9 NPCs in NPCS. An unknown id falls back to Scrap Rat.
    Stats apply here, with the server's rules mirrored: the faster
    side hits first every round (a tie goes to the fighter), a
    faster side may dodge, Luck may crit for x1.5, and no single
    hit may deal more than 75% of the target's max health.
    An NPC's special ability fires every few rounds (see NPCS):
    a double hit, a shield/vanish/dodge that blocks the fighter's
    hit, a self-repair, a 1.5x flare/shock, or a sugar trap that
    makes the fighter's next hit deal half damage."""
    if rng is None:
        rng = random.Random()
    if now is None:
        now = time.time()
    if is_repairing(fighter, now):
        return {
            "won": None,
            "lines": [
                "Your fighter is still repairing. %s left."
                % format_time(repair_left_seconds(fighter, now)),
                "You can visit the hangout or browse the shop while you wait.",
            ],
            "xp": 0,
            "credits": 0,
            "levels_gained": 0,
        }

    creature = creature_for_level(fighter["level"], npc_id)
    ability = creature.get("ability")
    ability_every = creature.get("ability_every") or 0
    # Baker Belle's sugar trap: armed on her trap round, spent
    # on the fighter's next hit, which then deals half damage.
    sugar_trap_armed = False
    lines = ["A %s appears! Level %d." % (creature["name"], creature["level"])]
    fighter_hp = fighter["hp"]
    fighter_max = fighter_max_hp(fighter)
    creature_hp = creature["hp"]
    creature_max = creature["max_hp"]
    fighter_crit = stat_crit_chance(stats_of(fighter)["luck"])
    creature_crit = creature["crit_chance"]
    fighter_soak = armor_defense(fighter) // 2
    creature_soak = creature["soak"]
    # The faster side hits first every round; on a tie the
    # fighter hits first. Speeds do not change mid-fight.
    fighter_first = fighter_speed(fighter) >= creature["speed"]
    fighter_dodge = stat_dodge_chance(fighter_speed(fighter) - creature["speed"])
    creature_dodge = stat_dodge_chance(creature["speed"] - fighter_speed(fighter))
    round_no = 0

    def fighter_hit():
        """One fighter hit: damage, maybe a crit, the creature's
        soak, then the fairness guard. Returns (damage, crit)."""
        hit = weapon_damage(fighter) + rng.randint(0, 3)
        crit = rng.random() * 100 < fighter_crit
        if crit:
            hit = int(round(hit * 1.5))
        hit = max(1, hit - creature_soak)
        return _guarded_hit(hit, creature_max), crit

    def creature_hit(power=1.0):
        """One creature hit: damage, maybe a crit, the fighter's
        soak, then the fairness guard. power multiplies the hit
        before the soak (a flare or a shock is 1.5x). A flare
        or shock round never crits as well: the burst is the
        excitement that round, and stacking both would push a
        single hit past the fair band in the NPC design (the
        hardest single round stays near a quarter of the
        fighter's health). Returns (damage, crit)."""
        hit = creature["damage"] + rng.randint(0, 2)
        if power != 1.0:
            hit = int(round(hit * power))
        crit = power == 1.0 and rng.random() * 100 < creature_crit
        if crit:
            hit = int(round(hit * 1.5))
        hit = max(1, hit - fighter_soak)
        return _guarded_hit(hit, fighter_max), crit

    def one_fighter_hit():
        """The fighter's turn: a dodge, a blocked hit, or a
        real hit. Returns True when a hit landed."""
        nonlocal sugar_trap_armed
        if rng.random() * 100 < creature_dodge:
            lines.append(
                "Round %d: The %s dodges! Your hit misses."
                % (round_no, creature["name"])
            )
            return False
        hit, crit = fighter_hit()
        if sugar_trap_armed:
            # The sugar trap makes this one hit sticky and weak.
            sugar_trap_armed = False
            hit = max(1, hit // 2)
        return _apply_fighter_hit(hit, crit)

    def _apply_fighter_hit(hit, crit):
        nonlocal creature_hp
        creature_hp -= hit
        if crit:
            lines.append(
                "Round %d: Critical hit! %s hits the %s for %d."
                % (round_no, fighter["name"], creature["name"], hit)
            )
        else:
            lines.append(
                "Round %d: %s hits the %s for %d."
                % (round_no, fighter["name"], creature["name"], hit)
            )
        return True

    def one_creature_hit(power=1.0):
        """The creature's turn: a dodge, or a real hit."""
        nonlocal fighter_hp
        if rng.random() * 100 < fighter_dodge:
            lines.append(
                "Round %d: %s dodges! The %s's hit misses."
                % (round_no, fighter["name"], creature["name"])
            )
            return False
        hit, crit = creature_hit(power)
        fighter_hp -= hit
        if crit:
            lines.append(
                "Round %d: Critical hit! The %s hits %s for %d."
                % (round_no, creature["name"], fighter["name"], hit)
            )
        else:
            lines.append(
                "Round %d: The %s hits %s for %d."
                % (round_no, creature["name"], fighter["name"], hit)
            )
        return True

    while fighter_hp > 0 and creature_hp > 0 and round_no < 20:
        round_no += 1
        ability_round = bool(ability) and ability_every > 0 \
            and round_no % ability_every == 0
        for attacker in ("fighter", "creature") if fighter_first else ("creature", "fighter"):
            if fighter_hp <= 0 or creature_hp <= 0:
                break
            if attacker == "fighter":
                if ability_round and ability in ("shield", "vanish", "dodge"):
                    # The fighter's hit is blocked outright
                    # this round: a shield, a vanish, a dodge.
                    lines.append(
                        "Round %d: %s" % (round_no, creature["ability_line"])
                    )
                    continue
                one_fighter_hit()
            else:
                if ability_round and ability in ("flare", "shock"):
                    # A burst of flame / a shock: this round's
                    # hit deals half as much again, before the
                    # fighter's armor soaks some of it.
                    lines.append(
                        "Round %d: %s" % (round_no, creature["ability_line"])
                    )
                    one_creature_hit(power=1.5)
                elif ability_round and ability == "sugar_trap":
                    # A sticky trap: the fighter's NEXT hit
                    # deals only half damage.
                    lines.append(
                        "Round %d: %s" % (round_no, creature["ability_line"])
                    )
                    sugar_trap_armed = True
                    one_creature_hit()
                elif ability_round and ability == "double_hit":
                    # Two quick hits in one round, each for
                    # the creature's normal damage.
                    lines.append(
                        "Round %d: %s" % (round_no, creature["ability_line"])
                    )
                    one_creature_hit()
                    if fighter_hp > 0 and creature_hp > 0:
                        one_creature_hit()
                else:
                    one_creature_hit()
        if creature_hp > 0 and ability_round and ability == "self_repair":
            # The repair bot patches itself up mid-fight, for
            # 15% of its max health, if it is still standing.
            healed = max(1, int(round(0.15 * creature_max)))
            creature_hp = min(creature_max, creature_hp + healed)
            lines.append(
                "Round %d: %s" % (round_no, creature["ability_line"])
            )

    if creature_hp <= 0:
        xp = int(round((20 + 5 * creature["level"]) * creature["reward_mult"]))
        credits = int(round((10 + 5 * fighter["level"]) * creature["reward_mult"]))
        levels = gain_xp(fighter, xp)
        fighter["credits"] = credits_of(fighter) + credits
        fighter.pop("points", None)
        fighter["wins"] += 1
        fighter["hp"] = max(1, fighter_hp)
        lines.append("You won! You earned %d experience and %d credits." % (xp, credits))
        if levels:
            lines.append(
                "You are now level %d! Your health grew to %d. "
                "You have %d stat points to spend."
                % (
                    fighter["level"],
                    fighter["max_hp"],
                    fighter.get("stat_points", 0),
                )
            )
        return {
            "won": True,
            "lines": lines,
            "xp": xp,
            "credits": credits,
            "levels_gained": levels,
        }

    # Lost (or the 20-round limit ran out, which counts as a loss).
    lost = min(credits_of(fighter), 5)
    fighter["credits"] = credits_of(fighter) - lost
    fighter.pop("points", None)
    fighter["losses"] += 1
    fighter["hp"] = 1
    wait = repair_duration_seconds(fighter["level"])
    fighter["repair_until"] = now + wait
    lines.append("You lost. Your fighter needs repairs, %s." % format_time(wait))
    if lost:
        lines.append("You lost %d credits." % lost)
    lines.append("While repairs run, you can still visit the hangout.")
    return {
        "won": False,
        "lines": lines,
        "xp": 0,
        "credits": -lost,
        "levels_gained": 0,
    }


def start_upgrade(fighter, slot, now=None):
    """Begin a timed upgrade of 'weapon' or 'armor'.

    Returns a plain-words error, or None when the upgrade started.
    Costs climb forever; the wait is capped at 4 hours.
    """
    if now is None:
        now = time.time()
    if slot not in ("weapon", "armor"):
        return "Pick weapon or armor to upgrade."
    if fighter.get("upgrade"):
        return "An upgrade is already running. Wait for it to finish first."
    level_key = slot + "_level"
    name_key = slot + "_name"
    level = fighter[level_key]
    cost = upgrade_cost(level)
    if credits_of(fighter) < cost:
        return (
            "That upgrade costs %d credits and you have %d credits."
            % (cost, credits_of(fighter))
        )
    fighter["credits"] = credits_of(fighter) - cost
    fighter.pop("points", None)
    fighter["upgrade"] = {
        "slot": slot,
        "name": fighter[name_key],
        "level": level + 1,
        "finish": now + upgrade_duration_seconds(level),
    }
    return None


def max_affordable(fighter, slot):
    """Work out a max-affordable upgrade queue for one slot, without
    spending anything. Returns a dict with the target levels, the
    total cost, the total wait in seconds, the credits left after,
    and the next level's cost (for the "you cannot afford it" line).

    A queue buys the most levels you can afford BY CREDITS AND BY
    TIME: it stops adding levels as soon as the next level would
    cost more credits than are left, or would push the total wait
    past 4 hours. "levels" is empty when even one level is out of
    reach."""
    level = fighter[slot + "_level"]
    credits = credits_of(fighter)
    levels = []
    total_cost = 0
    total_seconds = 0
    while True:
        cost = upgrade_cost(level)
        seconds = upgrade_duration_seconds(level)
        if total_cost + cost > credits:
            break
        if total_seconds + seconds > MAX_TIMER_SECONDS:
            break
        levels.append(level + 1)
        total_cost += cost
        total_seconds += seconds
        level += 1
    return {
        "slot": slot,
        "name": fighter[slot + "_name"],
        "levels": levels,
        "cost": total_cost,
        "seconds": total_seconds,
        "credits_left": credits - total_cost,
        "next_cost": upgrade_cost(level),
        "credits": credits,
    }


def start_max_upgrade(fighter, slot, now=None):
    """Start a max-affordable queue: buy as many levels as the
    credits and the 4-hour cap allow, deduct the full cost up
    front, and run the levels one after another. Returns
    (error, line): the line is the plain-words confirm summary
    the game speaks after the player has said yes. Once started
    the queue runs to the end — there is no cancelling."""
    if now is None:
        now = time.time()
    if slot not in ("weapon", "armor"):
        return "Pick weapon or armor to upgrade.", None
    if fighter.get("upgrade"):
        return "An upgrade is already running. Wait for it to finish first.", None
    plan = max_affordable(fighter, slot)
    if not plan["levels"]:
        return (
            "Your next %s level costs %d credits and you have %d credits."
            % (plan["name"], plan["next_cost"], plan["credits"])
        ), None
    fighter["credits"] = plan["credits_left"]
    fighter.pop("points", None)
    first = plan["levels"][0]
    fighter["upgrade"] = {
        "slot": slot,
        "name": plan["name"],
        "level": first,
        "finish": now + upgrade_duration_seconds(first - 1),
    }
    fighter["upgrade_queue"] = plan["levels"][1:]
    fighter["upgrade_total"] = len(plan["levels"])
    count = len(plan["levels"])
    line = (
        "Your %s will go up %d %s for %d credits. All %d %s will be "
        "done in %s."
        % (
            plan["name"],
            count,
            "level" if count == 1 else "levels",
            plan["cost"],
            count,
            "level" if count == 1 else "levels",
            format_time(plan["seconds"]),
        )
    )
    return None, line


def finish_upgrade_if_ready(fighter, now=None):
    """Apply a finished upgrade. Returns its plain-words line, or None.

    When a max-affordable queue is running, the next level starts
    at once, so the queue runs one level after another until every
    level is done. The last level's line says the whole queue is done."""
    if now is None:
        now = time.time()
    upgrade = fighter.get("upgrade")
    if not upgrade:
        return None
    if now < upgrade["finish"]:
        return None
    fighter[upgrade["slot"] + "_level"] = upgrade["level"]
    line = "Your %s is now level %d." % (upgrade["name"], upgrade["level"])
    queue = list(fighter.get("upgrade_queue") or [])
    if queue:
        nxt = queue.pop(0)
        fighter["upgrade"] = {
            "slot": upgrade["slot"],
            "name": upgrade["name"],
            "level": nxt,
            "finish": now + upgrade_duration_seconds(nxt - 1),
        }
        fighter["upgrade_queue"] = queue
    else:
        total = fighter.get("upgrade_total", 0)
        fighter["upgrade"] = None
        fighter["upgrade_queue"] = None
        fighter["upgrade_total"] = 0
        if total > 1:
            line += " All %d levels are done." % total
    return line


def upgrade_status(fighter, now=None):
    """Plain-words line about the running upgrade, or None. A
    queued upgrade also says how many levels are still queued."""
    if now is None:
        now = time.time()
    upgrade = fighter.get("upgrade")
    if not upgrade:
        return None
    left = max(0, upgrade["finish"] - now)
    text = "Upgrading %s to level %d, %s left." % (
        upgrade["name"],
        upgrade["level"],
        format_time(left),
    )
    queued = len(fighter.get("upgrade_queue") or [])
    if queued:
        text += " %d more %s queued." % (
            queued,
            "level" if queued == 1 else "levels",
        )
    return text


def status_text(fighter, now=None):
    """One plain summary of the fighter, for the Home tab."""
    if now is None:
        now = time.time()
    text = (
        "%s, level %d %s. %d health out of %d. %d credits. "
        "%d wins, %d losses. %s level %d, %s level %d."
        % (
            fighter["name"],
            fighter["level"],
            fighter["kind"],
            fighter["hp"],
            fighter_max_hp(fighter),
            credits_of(fighter),
            fighter["wins"],
            fighter["losses"],
            fighter["weapon_name"],
            fighter["weapon_level"],
            fighter["armor_name"],
            fighter["armor_level"],
        )
    )
    healing = fighter.get("healing_level", 0) or 0
    if healing > 0:
        text += " Healing level %d." % healing
    # Quest level (Phase 23), next to the fighter level: one
    # line, no "points" word here, so the currency wording
    # checks stay clean.
    text += " " + quests.quest_level_line(fighter)
    points = fighter.get("stat_points", 0)
    if points > 0:
        text += " You have %d stat %s to spend." % (
            points,
            "point" if points == 1 else "points",
        )
    if is_repairing(fighter, now):
        text += " Repairing, %s left." % format_time(
            repair_left_seconds(fighter, now)
        )
    upgrade = upgrade_status(fighter, now)
    if upgrade:
        text += " " + upgrade
    return text
