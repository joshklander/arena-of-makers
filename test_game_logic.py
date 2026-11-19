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

    # Healing skill (Phase 25, Makenna Nov 18, 2026): bought
    # in the Shop like weapon and armor, max level 5, with
    # its own cost and time curves — NOT the normal upgrade
    # curve. Its name is Second Wind, for robots and chefs.
    check("healing is called Second Wind",
          game_logic.HEALING_NAME == "Second Wind")
    check("healing costs 50, 85, 140, 240, 400",
          [game_logic.healing_cost(level) for level in range(5)]
          == [50, 85, 140, 240, 400])
    check("healing costs 915 in total",
          sum(game_logic.healing_cost(level) for level in range(5)) == 915)
    check("healing times are 12, 24, 36, 48, 60 minutes",
          [game_logic.healing_duration_seconds(level) // 60
           for level in range(5)] == [12, 24, 36, 48, 60])
    check("healing times total about 3 hours",
          sum(game_logic.healing_duration_seconds(level)
              for level in range(5)) == 3 * 3600)
    check("healing has no next cost at level 5",
          game_logic.healing_cost(5) is None)
    check("healing percents are 0, 19, 38, 57, 76, 95",
          [game_logic.healing_percent(level) for level in range(6)]
          == [0, 19, 38, 57, 76, 95])

    # The tag-team heal helper (Phase 25): set by YOUR
    # Healing level, once per jump-in, never past max health.
    # The worked example from the design: a level 5 fighter
    # with 150 max health, level 1 Healing, heals 19% — about
    # 28. At 134 health only 16 of it fits before max health,
    # so the heal stops at 150 and the rest is lost.
    healer = game_logic.new_fighter("Healer", "robot")
    healer["level"] = 5
    healer["stats"] = {"strength": 4, "defense": 1, "health": 1, "speed": 0, "luck": 2}
    healer["max_hp"] = game_logic.fighter_max_hp(healer)
    healer["hp"] = 100
    healer["healing_level"] = 1
    check("level 1 heals 19 percent, about 28 at 150 max",
          game_logic.healing_heal_amount(healer) == 28)
    healer["hp"] = 134
    check("level 1 heal stops at max health, 16 fits",
          game_logic.healing_heal_amount(healer) == 16)
    healer["healing_level"] = 5
    check("level 5 heal also stops at max health",
          game_logic.healing_heal_amount(healer) == 16)
    healer["hp"] = 150
    check("a full fighter heals nothing",
          game_logic.healing_heal_amount(healer) == 0)
    healer["healing_level"] = 0
    healer["hp"] = 100
    check("level 0 heals nothing, the strike still lands",
          game_logic.healing_heal_amount(healer) == 0)

    # Buying Healing: one level at a time, then the cap.
    buyer = game_logic.new_fighter("Buyer", "chef")
    buyer["credits"] = 1000
    error = game_logic.start_upgrade(buyer, "healing", now=1000000.0)
    check("healing upgrade starts when affordable", error is None)
    check("healing costs 50 credits for level 1", buyer["credits"] == 950)
    check("healing upgrade targets healing",
          buyer["upgrade"]["slot"] == "healing"
          and buyer["upgrade"]["name"] == "Second Wind")
    check("healing level 1 takes 12 minutes",
          buyer["upgrade"]["finish"] == 1000000.0 + 12 * 60)
    line = game_logic.finish_upgrade_if_ready(
        buyer, now=1000000.0 + 12 * 60 + 1)
    check("healing finishes at level 1", buyer["healing_level"] == 1)
    # One upgrade set at a time, both directions (Phase 24):
    # a Healing set blocks weapon and armor, and a weapon
    # set blocks Healing.
    error = game_logic.start_upgrade(buyer, "healing", now=1000000.0 + 13 * 60)
    check("second healing level starts after the first", error is None)
    check("weapon is blocked while a healing set runs",
          game_logic.start_upgrade(buyer, "weapon", now=1000000.0 + 13 * 60 + 1) is not None)
    check("max weapon is blocked while a healing set runs",
          game_logic.start_max_upgrade(buyer, "weapon", now=1000000.0 + 13 * 60 + 1)[0] is not None)
    armed = game_logic.new_fighter("Armed", "robot")
    armed["credits"] = 10000
    game_logic.start_upgrade(armed, "weapon", now=1000000.0)
    check("healing is blocked while a weapon set runs",
          game_logic.start_upgrade(armed, "healing", now=1000001.0) is not None)
    check("max healing is blocked while a weapon set runs",
          game_logic.start_max_upgrade(armed, "healing", now=1000001.0)[0] is not None)

    # Hotfix Phase 25b (Makenna Nov 18, 2026): a fighter made
    # before Phase 18 has no healing_level key at all, and the
    # game used to crash on launch building the Shop. Missing
    # means level 0: buying, max-affordable and the level-5
    # rules all still work, and the key appears once the first
    # level finishes.
    old = game_logic.new_fighter("Old", "robot")
    del old["healing_level"]
    old["credits"] = 1000
    check("a pre-Phase-18 fighter has no healing_level key",
          "healing_level" not in old)
    plan = game_logic.max_affordable(old, "healing")
    check("max affordable works without the key, all 5 levels",
          len(plan["levels"]) == 5 and plan["cost"] == 915)
    error = game_logic.start_upgrade(old, "healing", now=1000000.0)
    check("buying healing works without the key", error is None)
    check("first healing level costs 50 without the key",
          old["credits"] == 950)
    game_logic.finish_upgrade_if_ready(old, now=1000000.0 + 12 * 60 + 1)
    check("healing finishes at level 1 without the key",
          old["healing_level"] == 1)
    check("status says the Second Wind level after the first buy",
          "Second Wind level 1" in game_logic.status_text(old))

    # Max affordable Healing: 1000 credits from level 0 buys
    # all 5 levels for 915 credits in about 3 hours, never
    # past level 5; at level 5 there is nothing to buy.
    maxer = game_logic.new_fighter("MaxHeal", "robot")
    maxer["credits"] = 1000
    plan = game_logic.max_affordable(maxer, "healing")
    check("1000 credits buys all 5 healing levels", len(plan["levels"]) == 5)
    check("5 healing levels cost 915 credits", plan["cost"] == 915)
    check("5 healing levels take about 3 hours", plan["seconds"] == 3 * 3600)
    error, line = game_logic.start_max_upgrade(maxer, "healing", now=1000000.0)
    check("max healing starts the queue", error is None and "5 levels" in line
          and "915 credits" in line)
    check("max healing queue is called Second Wind",
          maxer["upgrade"]["name"] == "Second Wind")
    now = 1000000.0
    while maxer.get("upgrade"):
        now = maxer["upgrade"]["finish"] + 1
        game_logic.finish_upgrade_if_ready(maxer, now=now)
    check("max healing queue drains to level 5", maxer["healing_level"] == 5)
    error = game_logic.start_upgrade(maxer, "healing", now=now)
    check("level 5 cannot be bought again",
          error is not None and "at its best" in error)
    check("max affordable at level 5 buys nothing",
          game_logic.max_affordable(maxer, "healing")["levels"] == []
          and game_logic.max_affordable(maxer, "healing")["maxed"] is True)
    check("max upgrade at level 5 is refused",
          game_logic.start_max_upgrade(maxer, "healing", now=now)[0] is not None)

    # Level 5 auto-heal (Phase 25): after every fight the
    # fighter is back to full health, and no repair ever
    # starts. A win at low health heals to full; a loss at
    # 1 health ends at full with no repair, and the first
    # saved repair is announced in full, the next in short.
    full = game_logic.new_fighter("Full", "robot")
    full["healing_level"] = 5
    full["hp"] = 50
    result = game_logic.fight(full, rng=random.Random(3))
    check("level 5 win restores full health",
          result["won"] is True and full["hp"] == full["max_hp"])
    check("level 5 win says Second Wind restored me",
          any("Second Wind restored me to full health" in line
              for line in result["lines"]))
    doomed = game_logic.new_fighter("Doomed", "robot")
    doomed["healing_level"] = 5
    doomed["hp"] = 1
    result = game_logic.fight(doomed, rng=random.Random(3))
    check("level 5 loss ends at full health, no repair",
          result["won"] is False and doomed["hp"] == doomed["max_hp"]
          and doomed["repair_until"] == 0)
    check("first saved repair is announced in full",
          any("never need repairs again" in line for line in result["lines"]))
    doomed["hp"] = 1
    result = game_logic.fight(doomed, rng=random.Random(3))
    check("second saved repair is announced in short",
          any("No repairs needed." in line for line in result["lines"])
          and not any("never need repairs again" in line
                      for line in result["lines"]))
    # Without level 5, a loss at 1 health still repairs.
    plain = game_logic.new_fighter("Plain", "robot")
    plain["hp"] = 1
    result = game_logic.fight(plain, rng=random.Random(3))
    check("a loss without level 5 still needs repairs",
          result["won"] is False and plain["hp"] == 1
          and plain["repair_until"] > 0)
    # Reaching level 5 ends a repair already running.
    mending = game_logic.new_fighter("Mending", "robot")
    mending["credits"] = 1000
    mending["healing_level"] = 4
    mending["hp"] = 20
    mending["repair_until"] = 2000000.0
    game_logic.start_upgrade(mending, "healing", now=1000000.0)
    line = game_logic.finish_upgrade_if_ready(mending, now=1000000.0 + 3601)
    check("reaching level 5 ends a running repair",
          mending["repair_until"] == 0 and mending["hp"] == mending["max_hp"]
          and "No more repairs" in line)

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
