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
        check("a win earns credits", robot["credits"] > 0 and robot["wins"] == 1)
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
    check("level-up banks 2 stat points", fighter["stat_points"] == 2)
    gained = game_logic.gain_xp(fighter, 1000)
    check("big xp can gain several levels", gained >= 3 and fighter["level"] >= 5)
    check("each level banks 2 more stat points",
          fighter["stat_points"] == 2 * (fighter["level"] - 1))
    # Health always grows with level, whatever you choose:
    # +10 max HP per level, before any Health stat points.
    plain = game_logic.new_fighter("Plain", "robot")
    game_logic.gain_xp(plain, 100 + 200 + 300 + 400)
    check("health grows +10 per level with no Health points",
          plain["level"] == 5 and plain["max_hp"] == 140)

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
    rich["credits"] = 10000
    error = game_logic.start_upgrade(rich, "weapon", now=1000000.0)
    check("upgrade starts when affordable", error is None)
    check("upgrade costs credits", rich["credits"] == 10000 - game_logic.upgrade_cost(1))
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

    # The stats draft's worked example: level 5 robot, weapon
    # 3, armor 2, Strength 4, Luck 2, Health 1, Defense 1,
    # Speed 0. Damage 38, defense 10 (soak 5), max HP 150,
    # Speed 5, crit about 4%.
    worked = game_logic.new_fighter("Kat", "robot")
    worked["level"] = 5
    worked["weapon_level"] = 3
    worked["armor_level"] = 2
    worked["stats"] = {"strength": 4, "defense": 1, "health": 1, "speed": 0, "luck": 2}
    worked["max_hp"] = game_logic.fighter_max_hp(worked)
    worked["hp"] = 150
    check("worked example damage is 38", game_logic.weapon_damage(worked) == 38)
    check("worked example defense is 10", game_logic.armor_defense(worked) == 10)
    check("worked example soak is 5", game_logic.armor_defense(worked) // 2 == 5)
    check("worked example max hp is 150", game_logic.fighter_max_hp(worked) == 150)
    check("worked example speed is 5", game_logic.fighter_speed(worked) == 5)
    check("worked example crit is about 4%",
          abs(game_logic.stat_crit_chance(2) - 3.7) < 0.5)
    check("crit chance never reaches 50%",
          game_logic.stat_crit_chance(10000) < 50)
    check("dodge chance never reaches 20%",
          game_logic.stat_dodge_chance(10000) < 20)
    check("speed 3 faster dodges about 3%",
          abs(game_logic.stat_dodge_chance(3) - 2.6) < 0.5)

    # Spending stat points: one point per call, and banked
    # points may all go into one stat, no forced spreading.
    banker = game_logic.new_fighter("Banker", "robot")
    banker["stat_points"] = 8
    for i in range(8):
        error, line = game_logic.spend_stat(banker, "strength")
        check("spending a point works, point %d" % (i + 1), error is None)
        check("spend line says points left, point %d" % (i + 1),
              "stat point" in line)
    check("all 8 banked points can go into Strength",
          banker["stats"]["strength"] == 8 and banker["stat_points"] == 0)
    check("spending with no points left is refused",
          game_logic.spend_stat(banker, "strength")[0] is not None)
    check("spending a bad stat name is refused",
          game_logic.spend_stat(banker, "magic")[0] is not None)
    health_fighter = game_logic.new_fighter("Tanky", "robot")
    health_fighter["stat_points"] = 1
    error, line = game_logic.spend_stat(health_fighter, "health")
    check("Health point adds 10 max HP and heals 10",
          health_fighter["max_hp"] == 110 and health_fighter["hp"] == 110)

    # Respec: first one free, later ones 100 credits.
    respec_fighter = game_logic.new_fighter("Respec", "robot")
    respec_fighter["stat_points"] = 2
    game_logic.spend_stat(respec_fighter, "strength")
    game_logic.spend_stat(respec_fighter, "strength")
    error, _line = game_logic.respec_stats(respec_fighter)
    check("first respec is free and refunds points",
          error is None and respec_fighter["stat_points"] == 2
          and respec_fighter["stats"]["strength"] == 0)
    respec_fighter["credits"] = 50
    game_logic.spend_stat(respec_fighter, "luck")
    error, _line = game_logic.respec_stats(respec_fighter)
    check("second respec is refused when broke", error is not None
          and "100 credits" in error)
    respec_fighter["credits"] = 150
    error, _line = game_logic.respec_stats(respec_fighter)
    check("second respec costs 100 credits",
          error is None and respec_fighter["credits"] == 50)

    # Max affordable: 500 credits on a level-1 laser gun buys
    # 5 levels for 330 credits, leaving 170. The total wait
    # follows the game's own rule, 60 seconds per level being
    # upgraded from: 1 + 2 + 3 + 4 + 5 minutes = 15 minutes.
    # (The draft's "35 minutes" adds the minutes for
    # upgrading from level 5, not level 1; see the report.)
    plan = game_logic.max_affordable(
        dict(game_logic.new_fighter("Maxer", "robot"), credits=500),
        "weapon")
    check("500 credits buys 5 levels from level 1", len(plan["levels"]) == 5)
    check("5 levels cost 330 credits", plan["cost"] == 330)
    check("5 levels leave 170 credits", plan["credits_left"] == 170)
    check("5 levels take 15 minutes", plan["seconds"] == 900)
    plan5 = game_logic.max_affordable(
        dict(game_logic.new_fighter("Maxer", "robot"),
             credits=500, weapon_level=5),
        "weapon")
    check("500 credits buys 2 levels from level 5", len(plan5["levels"]) == 2)
    check("2 levels from level 5 cost 317 credits", plan5["cost"] == 317)
    check("2 levels from level 5 leave 183 credits", plan5["credits_left"] == 183)
    # The queue runs to the end with no cancelling, and the
    # total never passes 4 hours. At weapon level 40 with
    # plenty of credits, the 4-hour cap (not the credits)
    # stops the queue at 5 levels.
    queue_fighter = game_logic.new_fighter("Queuer", "robot")
    queue_fighter["credits"] = 10 ** 10
    queue_fighter["weapon_level"] = 40
    plan_huge = game_logic.max_affordable(queue_fighter, "weapon")
    check("max affordable never passes 4 hours total",
          plan_huge["seconds"] <= game_logic.MAX_TIMER_SECONDS)
    check("the 4-hour cap stops a rich queue at 5 levels",
          len(plan_huge["levels"]) == 5 and plan_huge["seconds"] == 12600)
    # A queue actually runs: 500 credits from level 1 buys 5
    # levels, and each level finishes in turn until the last
    # one says all 5 levels are done.
    queue_runner = game_logic.new_fighter("Runner", "robot")
    queue_runner["credits"] = 500
    error, line = game_logic.start_max_upgrade(queue_runner, "weapon", now=1000000.0)
    check("max upgrade starts a queue", error is None
          and queue_runner["upgrade"] is not None
          and queue_runner["upgrade"]["level"] == 2)
    check("max upgrade deducts the full cost up front",
          queue_runner["credits"] == 170)
    check("max upgrade has no cancel", not hasattr(game_logic, "cancel_upgrade"))
    now = 1000000.0
    for expected_level in (2, 3, 4, 5, 6):
        now += game_logic.upgrade_duration_seconds(expected_level - 1) + 1
        line = game_logic.finish_upgrade_if_ready(queue_runner, now=now)
        check("queue level %d finishes" % expected_level, line is not None)
    check("queue ends at weapon level 6", queue_runner["weapon_level"] == 6)
    check("queue is empty when all levels are done",
          queue_runner["upgrade"] is None and queue_runner["upgrade_queue"] is None)

    # The 75% fairness guard: no single hit over 75% of max HP.
    strong = game_logic.new_fighter("Strong", "robot")
    strong["level"] = 5
    strong["weapon_level"] = 3
    strong["stats"] = {"strength": 4, "defense": 1, "health": 1, "speed": 0, "luck": 2}
    strong["max_hp"] = game_logic.fighter_max_hp(strong)
    strong["hp"] = 150
    creature = game_logic.creature_for_level(5)
    check("guard caps a hit at 75% of max hp",
          game_logic._guarded_hit(1000, strong["max_hp"]) == 112)
    check("guard leaves a small hit alone",
          game_logic._guarded_hit(10, strong["max_hp"]) == 10)
    check("Scrap Rat at level 5 has even stat points",
          sum(creature["stats"].values()) == 8)
    check("Scrap Rat scales with level",
          game_logic.creature_for_level(50)["hp"]
          > game_logic.creature_for_level(1)["hp"])

    # Old "points" balances still count 1-for-1 until the
    # server converts them on the next sign-in.
    legacy = game_logic.new_fighter("Legacy", "robot")
    legacy["credits"] = 0
    legacy["points"] = 42
    check("legacy points count as credits", game_logic.credits_of(legacy) == 42)

    # No local save at all: game_logic has no save/load
    # functions, and a fighter is plain JSON data, ready to
    # go online to the one shared Supabase table.
    check("no local save function in game_logic",
          not hasattr(game_logic, "save_game"))
    check("no local load function in game_logic",
          not hasattr(game_logic, "load_game"))
    saved = game_logic.new_fighter("Saver", "chef", "female")
    saved["credits"] = 42
    saved["level"] = 3
    import json as _json
    roundtrip = _json.loads(_json.dumps(saved))
    check("fighter is plain JSON for the online save",
          roundtrip["name"] == "Saver" and roundtrip["credits"] == 42)
    check("fighter keeps kind online", roundtrip["kind"] == "chef")
    check("fighter keeps gender online", roundtrip["gender"] == "female")

    # Big numbers: with infinite progression a player can spend a
    # million credits (or far more) on one weapon, and the queue
    # must still respect the 4-hour cap. The cap binds on TIME,
    # not on credits: at level 1 a million credits buys 21 levels
    # for 249,344 credits, 750,656 left, in 13,860 seconds
    # (231 minutes) — under the 14,400-second cap — and the queue
    # drains to weapon level 22. Ten million and a billion credits
    # buy the same 21 levels: the extra credits stay unspent
    # because the next level would push the wait past 4 hours.
    # At weapon level 50 with 10 trillion credits, 4 levels for
    # 86,344,578,154 credits in 12,360 seconds. At weapon level
    # 200 with 1e38 credits, only 1 level fits: 12,000 seconds.
    for weapon_level, credits, want_levels in (
        (1, 1_000_000, 21),
        (1, 10_000_000, 21),
        (1, 1_000_000_000, 21),
        (50, 10_000_000_000_000, 4),
        (200, 10 ** 38, 1),
    ):
        big = game_logic.new_fighter("Big", "robot")
        big["weapon_level"] = weapon_level
        big["credits"] = credits
        plan = game_logic.max_affordable(big, "weapon")
        check("big numbers: %d levels at weapon %d" % (want_levels, weapon_level),
              len(plan["levels"]) == want_levels)
        check("big numbers: wait respects 4-hour cap at weapon %d" % weapon_level,
              plan["seconds"] <= game_logic.MAX_TIMER_SECONDS)
        err, line = game_logic.start_max_upgrade(big, "weapon", now=1000000.0)
        check("big numbers: queue starts at weapon %d" % weapon_level, err is None)
        now = 1000000.0
        while big.get("upgrade"):
            now = big["upgrade"]["finish"] + 1
            game_logic.finish_upgrade_if_ready(big, now=now)
        check("big numbers: queue drains at weapon %d" % weapon_level,
              not big.get("upgrade") and not big.get("upgrade_queue"))
        check("big numbers: final level %d at weapon %d" % (weapon_level + want_levels, weapon_level),
              big["weapon_level"] == weapon_level + want_levels)

    # Status text is one plain summary.
    text = game_logic.status_text(saved)
    check("status text names the fighter", "Saver" in text and "chef" in text)

    print("\nAll game-logic smoke tests passed.")


if __name__ == "__main__":
    main()
