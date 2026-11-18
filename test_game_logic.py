"""Headless smoke test for Arena of Makers game logic.

Runs with plain Python, no display and no wxPython needed:
    python test_game_logic.py

Covers: fighter creation (robot and chef), one fight, XP and level-ups,
endless upgrade costs, the 2 to 4 hour timer cap, repairs, and a
save/load roundtrip.
"""

import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_logic


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)
    print("ok - " + name)


def main():
    # Fighter creation.
    robot = game_logic.new_fighter("Bolt", "robot")
    check("robot fighter created", robot["name"] == "Bolt" and robot["kind"] == "robot")
    check("robot starts with Laser Blaster", robot["weapon_name"] == "Laser Blaster")
    check("robot starts with Scrap Plating", robot["armor_name"] == "Scrap Plating")
    check("fighter starts at level 1", robot["level"] == 1 and robot["hp"] == 100)

    chef = game_logic.new_fighter("Sizzle", "chef")
    check("chef fighter created", chef["kind"] == "chef")
    check("chef starts with Trusty Spatula", chef["weapon_name"] == "Trusty Spatula")
    check("chef starts with Chef Apron", chef["armor_name"] == "Chef Apron")

    try:
        game_logic.new_fighter("  ", "robot")
        check("empty name is rejected", False)
    except ValueError as error:
        check("empty name is rejected", "name" in str(error).lower())

    try:
        game_logic.new_fighter("Bolt", "warrior")
        check("bad kind is rejected", False)
    except ValueError:
        check("bad kind is rejected", True)

    # Gender picks the voice. Male is the default, female is the other.
    check("gender defaults to male", robot["gender"] == "male")
    girl = game_logic.new_fighter("Ember", "chef", "female")
    check("female fighter stores female", girl["gender"] == "female")
    check("female chef still gets spatula", girl["weapon_name"] == "Trusty Spatula")

    try:
        game_logic.new_fighter("Bolt", "robot", "other")
        check("bad gender is rejected", False)
    except ValueError:
        check("bad gender is rejected", True)

    # One fight, with a fixed seed so the test is repeatable.
    rng = random.Random(7)
    result = game_logic.fight(robot, rng=rng)
    check("fight returns lines", bool(result["lines"]))
    check("fight has a winner", result["won"] in (True, False))
    if result["won"]:
        check("a win earns points", robot["points"] > 0 and robot["wins"] == 1)
        check("a win earns xp", robot["xp"] >= 0)
    else:
        check("a loss starts repairs", game_logic.is_repairing(robot))
        check("a loss blocks the next fight", game_logic.fight(robot, rng=rng)["won"] is None)
        check("repair wait is plain words", "repairing" in " ".join(
            game_logic.fight(robot, rng=rng)["lines"]).lower())
    print("    fight outcome with seed 7: won=%s" % result["won"])

    # A forced loss: a fighter with 1 health cannot survive round 1.
    doomed = game_logic.new_fighter("Doomed", "robot")
    doomed["hp"] = 1
    lost = game_logic.fight(doomed, rng=random.Random(3), now=2000000.0)
    check("a weak fighter loses", lost["won"] is False)
    check("a loss starts repairs", game_logic.is_repairing(doomed, now=2000001.0))
    check("repair ends after its time",
          not game_logic.is_repairing(doomed, now=2000000.0 + 3600))
    check("a loss blocks the next fight while repairing",
          game_logic.fight(doomed, rng=random.Random(3), now=2000001.0)["won"] is None)
    check("repair wait is plain words", "repairing" in " ".join(
        game_logic.fight(doomed, rng=random.Random(3), now=2000001.0)["lines"]).lower())
    check("a loss heals to 1 health", doomed["hp"] == 1)

    # XP and level-ups: 100 XP takes level 1 to level 2.
    fighter = game_logic.new_fighter("Leveler", "robot")
    gained = game_logic.gain_xp(fighter, 100)
    check("100 xp levels up once", gained == 1 and fighter["level"] == 2)
    check("level-up raises max health", fighter["max_hp"] == 110)
    check("level-up heals to full", fighter["hp"] == 110)
    gained = game_logic.gain_xp(fighter, 1000)
    check("big xp can gain several levels", gained >= 3 and fighter["level"] >= 5)

    # Endless progression: costs keep climbing, no level cap.
    check("upgrade costs climb", game_logic.upgrade_cost(1) < game_logic.upgrade_cost(10)
          < game_logic.upgrade_cost(50) < game_logic.upgrade_cost(100))
    check("no top level on costs", game_logic.upgrade_cost(1000) > game_logic.upgrade_cost(100))
    check("damage climbs with weapon level", game_logic.weapon_damage(
        dict(fighter, weapon_level=50)) > game_logic.weapon_damage(
        dict(fighter, weapon_level=1)))
    check("defense climbs with armor level", game_logic.armor_defense(
        dict(fighter, armor_level=50)) > game_logic.armor_defense(
        dict(fighter, armor_level=1)))

    # Timer cap: no upgrade or repair ever passes 4 hours.
    check("upgrade time capped at 4 hours",
          game_logic.upgrade_duration_seconds(1000) <= game_logic.MAX_TIMER_SECONDS)
    check("upgrade time capped at 4 hours exactly",
          game_logic.upgrade_duration_seconds(10000) == game_logic.MAX_TIMER_SECONDS)
    check("repair time capped at 4 hours",
          game_logic.repair_duration_seconds(1000) <= game_logic.MAX_TIMER_SECONDS)
    check("early upgrade is short", game_logic.upgrade_duration_seconds(1) == 60)
    check("plain-words time", game_logic.format_time(7200) == "about 2 hours")

    # Shop: start an upgrade, pay for it, finish it.
    rich = game_logic.new_fighter("Rich", "chef")
    rich["points"] = 10000
    error = game_logic.start_upgrade(rich, "weapon", now=1000000.0)
    check("upgrade starts when affordable", error is None)
    check("upgrade costs points", rich["points"] == 10000 - game_logic.upgrade_cost(1))
    check("second upgrade is refused while one runs",
          game_logic.start_upgrade(rich, "armor", now=1000001.0) is not None)
    check("upgrade not ready early",
          game_logic.finish_upgrade_if_ready(rich, now=1000001.0) is None)
    line = game_logic.finish_upgrade_if_ready(
        rich, now=1000000.0 + game_logic.upgrade_duration_seconds(1) + 1)
    check("upgrade finishes after its time", line is not None and "level 2" in line)
    check("weapon level rose", rich["weapon_level"] == 2)
    poor = game_logic.new_fighter("Poor", "robot")
    check("upgrade refused when broke",
          game_logic.start_upgrade(poor, "weapon", now=1000000.0) is not None)

    # No local save at all: game_logic has no save/load
    # functions, and a fighter is plain JSON data, ready to
    # go online to the one shared Supabase table.
    check("no local save function in game_logic",
          not hasattr(game_logic, "save_game"))
    check("no local load function in game_logic",
          not hasattr(game_logic, "load_game"))
    saved = game_logic.new_fighter("Saver", "chef", "female")
    saved["points"] = 42
    saved["level"] = 3
    import json as _json
    roundtrip = _json.loads(_json.dumps(saved))
    check("fighter is plain JSON for the online save",
          roundtrip["name"] == "Saver" and roundtrip["points"] == 42)
    check("fighter keeps kind online", roundtrip["kind"] == "chef")
    check("fighter keeps gender online", roundtrip["gender"] == "female")

    # Status text is one plain summary.
    text = game_logic.status_text(saved)
    check("status text names the fighter", "Saver" in text and "chef" in text)

    print("\nAll game-logic smoke tests passed.")


if __name__ == "__main__":
    main()
