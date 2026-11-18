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
        "points": 0,
        "wins": 0,
        "losses": 0,
        "weapon_name": weapon_name,
        "weapon_level": 1,
        "armor_name": armor_name,
        "armor_level": 1,
        # Epoch seconds when the current repair finishes, or 0.
        "repair_until": 0,
        # Current timed upgrade, or None: {"slot": "weapon"|"armor",
        # "level": new level, "finish": epoch seconds}.
        "upgrade": None,
    }


def xp_to_next_level(level):
    """XP needed to go from this level to the next. Grows, never caps."""
    return 100 * level


def weapon_damage(fighter):
    """Damage per hit. Climbs forever with weapon level and fighter level."""
    base = 12 if fighter["kind"] == "robot" else 10
    return base + 5 * (fighter["weapon_level"] - 1) + 2 * (fighter["level"] - 1)


def armor_defense(fighter):
    """Damage soaked per hit. Climbs forever with armor and fighter level."""
    return 2 + 2 * (fighter["armor_level"] - 1) + (fighter["level"] - 1)


def upgrade_cost(level):
    """Points to raise a weapon or armor from this level to the next.

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
    """Add XP, applying as many level-ups as it earns. Returns new levels."""
    fighter["xp"] += amount
    gained = 0
    while fighter["xp"] >= xp_to_next_level(fighter["level"]):
        fighter["xp"] -= xp_to_next_level(fighter["level"])
        fighter["level"] += 1
        fighter["max_hp"] += 10
        fighter["hp"] = fighter["max_hp"]
        gained += 1
    return gained


def creature_for_level(level):
    """The starter creature, scaled to the fighter's level so fights stay
    real as the fighter climbs. There is no top level for either side."""
    return {
        "name": CREATURE_NAME,
        "level": level,
        "hp": 30 + 15 * (level - 1),
        "max_hp": 30 + 15 * (level - 1),
        "damage": 4 + 2 * (level - 1),
    }


def fight(fighter, rng=None, now=None):
    """Fight one creature. Returns a result dict with plain-words lines.

    The fighter must not be under repair. The result tells the window
    what happened, what was won or lost, and what to say next.
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
            "points": 0,
            "levels_gained": 0,
        }

    creature = creature_for_level(fighter["level"])
    lines = ["A %s appears! Level %d." % (creature["name"], creature["level"])]
    fighter_hp = fighter["hp"]
    creature_hp = creature["hp"]
    round_no = 0
    while fighter_hp > 0 and creature_hp > 0 and round_no < 20:
        round_no += 1
        hit = weapon_damage(fighter) + rng.randint(0, 3)
        creature_hp -= hit
        lines.append(
            "Round %d: %s hits the %s for %d."
            % (round_no, fighter["name"], creature["name"], hit)
        )
        if creature_hp <= 0:
            break
        soak = armor_defense(fighter) // 2
        hurt = max(1, creature["damage"] + rng.randint(0, 2) - soak)
        fighter_hp -= hurt
        lines.append(
            "Round %d: The %s hits %s for %d."
            % (round_no, creature["name"], fighter["name"], hurt)
        )

    if creature_hp <= 0:
        xp = 20 + 5 * creature["level"]
        points = 10 + 5 * fighter["level"]
        levels = gain_xp(fighter, xp)
        fighter["points"] += points
        fighter["wins"] += 1
        fighter["hp"] = max(1, fighter_hp)
        lines.append("You won! You earned %d experience and %d points." % (xp, points))
        if levels:
            lines.append(
                "You are now level %d!" % fighter["level"]
            )
        return {
            "won": True,
            "lines": lines,
            "xp": xp,
            "points": points,
            "levels_gained": levels,
        }

    # Lost (or the 20-round limit ran out, which counts as a loss).
    lost = min(fighter["points"], 5)
    fighter["points"] -= lost
    fighter["losses"] += 1
    fighter["hp"] = 1
    wait = repair_duration_seconds(fighter["level"])
    fighter["repair_until"] = now + wait
    lines.append("You lost. Your fighter needs repairs, %s." % format_time(wait))
    if lost:
        lines.append("You lost %d points." % lost)
    lines.append("While repairs run, you can still visit the hangout.")
    return {
        "won": False,
        "lines": lines,
        "xp": 0,
        "points": -lost,
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
    if fighter["points"] < cost:
        return (
            "That upgrade costs %d points and you have %d points."
            % (cost, fighter["points"])
        )
    fighter["points"] -= cost
    fighter["upgrade"] = {
        "slot": slot,
        "name": fighter[name_key],
        "level": level + 1,
        "finish": now + upgrade_duration_seconds(level),
    }
    return None


def finish_upgrade_if_ready(fighter, now=None):
    """Apply a finished upgrade. Returns its plain-words line, or None."""
    if now is None:
        now = time.time()
    upgrade = fighter.get("upgrade")
    if not upgrade:
        return None
    if now < upgrade["finish"]:
        return None
    fighter[upgrade["slot"] + "_level"] = upgrade["level"]
    fighter["upgrade"] = None
    return "Your %s is now level %d." % (upgrade["name"], upgrade["level"])


def upgrade_status(fighter, now=None):
    """Plain-words line about the running upgrade, or None."""
    if now is None:
        now = time.time()
    upgrade = fighter.get("upgrade")
    if not upgrade:
        return None
    left = max(0, upgrade["finish"] - now)
    return "Upgrading %s to level %d, %s left." % (
        upgrade["name"],
        upgrade["level"],
        format_time(left),
    )


def status_text(fighter, now=None):
    """One plain summary of the fighter, for the Home tab."""
    if now is None:
        now = time.time()
    text = (
        "%s, level %d %s. %d health out of %d. %d points. "
        "%d wins, %d losses. %s level %d, %s level %d."
        % (
            fighter["name"],
            fighter["level"],
            fighter["kind"],
            fighter["hp"],
            fighter["max_hp"],
            fighter["points"],
            fighter["wins"],
            fighter["losses"],
            fighter["weapon_name"],
            fighter["weapon_level"],
            fighter["armor_name"],
            fighter["armor_level"],
        )
    )
    if is_repairing(fighter, now):
        text += " Repairing, %s left." % format_time(
            repair_left_seconds(fighter, now)
        )
    upgrade = upgrade_status(fighter, now)
    if upgrade:
        text += " " + upgrade
    return text
