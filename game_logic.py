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

# The longest any upgrade or repair may take: 4 hours.
MAX_TIMER_SECONDS = 4 * 3600

# One starter creature for the skeleton. More creatures come later.
CREATURE_NAME = "Scrap Rat"

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


def creature_for_level(level):
    """The starter creature, scaled to the fighter's level so fights stay
    real as the fighter climbs. There is no top level for either side.

    The Scrap Rat gets the same 2 stat points per level as a
    fighter, split evenly across the 5 stats, so fights stay
    even as the fighter builds stats: its health, damage, soak,
    speed and crit chance all grow with level, using the same
    formulas as a fighter."""
    stats = distribute_points(
        STAT_POINTS_PER_LEVEL * (level - 1),
        [(name, 2) for name in STAT_NAMES],
    )
    return {
        "name": CREATURE_NAME,
        "level": level,
        "hp": 30 + 15 * (level - 1) + 10 * stats["health"],
        "max_hp": 30 + 15 * (level - 1) + 10 * stats["health"],
        "damage": 4 + 2 * (level - 1) + 2 * stats["strength"],
        "soak": stats["defense"],
        "speed": 5 + stats["speed"],
        "crit_chance": stat_crit_chance(stats["luck"]),
        "stats": stats,
    }


def _guarded_hit(hit, target_max_hp):
    """The server fairness guard, mirrored here: no single hit,
    normal or critical, may deal more than 75% of the target's
    max health."""
    return max(1, min(hit, int(FAIRNESS_GUARD * target_max_hp)))


def fight(fighter, rng=None, now=None):
    """Fight one creature. Returns a result dict with plain-words lines.

    The fighter must not be under repair. The result tells the window
    what happened, what was won or lost, and what to say next.

    Stats apply here, with the server's rules mirrored: the faster
    side hits first every round (a tie goes to the fighter), a
    faster side may dodge, Luck may crit for x1.5, and no single
    hit may deal more than 75% of the target's max health.
    """
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

    creature = creature_for_level(fighter["level"])
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

    def creature_hit():
        """One creature hit: damage, maybe a crit, the fighter's
        soak, then the fairness guard. Returns (damage, crit)."""
        hit = creature["damage"] + rng.randint(0, 2)
        crit = rng.random() * 100 < creature_crit
        if crit:
            hit = int(round(hit * 1.5))
        hit = max(1, hit - fighter_soak)
        return _guarded_hit(hit, fighter_max), crit

    while fighter_hp > 0 and creature_hp > 0 and round_no < 20:
        round_no += 1
        for attacker in ("fighter", "creature") if fighter_first else ("creature", "fighter"):
            if fighter_hp <= 0 or creature_hp <= 0:
                break
            if attacker == "fighter":
                if rng.random() * 100 < creature_dodge:
                    lines.append(
                        "Round %d: The %s dodges! Your hit misses."
                        % (round_no, creature["name"])
                    )
                    continue
                hit, crit = fighter_hit()
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
            else:
                if rng.random() * 100 < fighter_dodge:
                    lines.append(
                        "Round %d: %s dodges! The %s's hit misses."
                        % (round_no, fighter["name"], creature["name"])
                    )
                    continue
                hit, crit = creature_hit()
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

    if creature_hp <= 0:
        xp = 20 + 5 * creature["level"]
        credits = 10 + 5 * fighter["level"]
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
