"""Headless smoke test for Arena of Makers game logic.

Runs with plain Python, no display and no wxPython needed:
    python test_game_logic.py

Covers: fighter creation (robot, chef and witch), one fight, XP and level-ups,
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
import quests
import spells


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

    # Witch (Phase 35): a third kind, same rules, base damage 11.
    witch = game_logic.new_fighter("Ember", "witch", "female")
    check("witch fighter created", witch["kind"] == "witch")
    check("witch starts with Spellbound Wand", witch["weapon_name"] == "Spellbound Wand")
    check("witch starts with Mystic Robe", witch["armor_name"] == "Mystic Robe")
    check("witch hits for 11 at level 1", game_logic.weapon_damage(witch) == 11)
    check("robot still hits for 12 at level 1", game_logic.weapon_damage(robot) == 12)
    check("chef still hits for 10 at level 1", game_logic.weapon_damage(chef) == 10)

    warlock = game_logic.new_fighter("Rowan", "witch", "male")
    check("male witch is called a warlock",
          game_logic.kind_word("witch", "male") == "warlock")
    check("female witch is called a witch",
          game_logic.kind_word("witch", "female") == "witch")
    check("robot word is robot either way",
          game_logic.kind_word("robot", "male") == "robot")
    check("status text calls a female witch a witch",
          "witch" in game_logic.status_text(witch))
    check("status text calls a male witch a warlock",
          "warlock" in game_logic.status_text(warlock))

    try:
        game_logic.new_fighter("Bolt", "wizard")
        check("unknown kind is rejected for a witch too", False)
    except ValueError:
        check("unknown kind is rejected for a witch too", True)

    try:
        game_logic.weapon_damage(
            {"kind": "wizard", "weapon_level": 1, "level": 1,
             "stats": {"strength": 0}})
        check("unknown kind never silently hits like a chef", False)
    except ValueError:
        check("unknown kind never silently hits like a chef", True)

    # An old fighter carries no witch fields at all, and must
    # still load and fight exactly as before (compatibility rule).
    old = dict(robot)
    old.pop("healing_level", None)
    check("old fighter with no witch fields still hits for 12",
          game_logic.weapon_damage(old) == 12)
    check("old fighter status still names a robot",
          "robot" in game_logic.status_text(old))

    # Fighter switching (Phase 36, Makenna Nov 25, 2026): first
    # switch free, then 100 credits doubling every switch, no cap.
    check("first switch is free", game_logic.switch_cost(0) == 0)
    check("second switch costs 100", game_logic.switch_cost(1) == 100)
    check("third switch costs 200", game_logic.switch_cost(2) == 200)
    check("fourth switch costs 400", game_logic.switch_cost(3) == 400)
    check("sixth switch costs 1600", game_logic.switch_cost(5) == 1600)
    check("a missing switch count means free",
          game_logic.switch_cost(None) == 0)

    # A levelled robot switching to witch: the reset rules.
    switcher = game_logic.new_fighter("Bolt", "robot")
    switcher["level"] = 5
    switcher["xp"] = 120
    switcher["stats"] = {"strength": 4, "defense": 2, "health": 1,
                         "speed": 1, "luck": 0}
    switcher["stat_points"] = 2
    switcher["weapon_level"] = 3
    switcher["armor_level"] = 2
    switcher["healing_level"] = 2
    switcher["credits"] = 500
    switcher["wins"] = 7
    switcher["losses"] = 3
    switcher["quest_level"] = 3
    switcher["quest_xp"] = 40
    switcher["quest_points"] = 2
    switcher["quest_stats"] = {"charm": 2, "renown": 1, "insight": 0}
    switcher["quests_rep"] = {"Bolt": 5, "Marge": 3}
    switcher["quests_board"] = [{"id": "q1"}]
    switcher["quests_done"] = ["q0"]
    switcher["quests_active"] = {"id": "q2"}
    switched, error = game_logic.switched_fighter(switcher, "witch")
    check("first switch has no error", error is None)
    check("switch changes the kind", switched["kind"] == "witch")
    check("switch renames the weapon",
          switched["weapon_name"] == "Spellbound Wand")
    check("switch renames the armor",
          switched["armor_name"] == "Mystic Robe")
    check("weapon upgrades reset to level 1",
          switched["weapon_level"] == 1)
    check("armor upgrades reset to level 1",
          switched["armor_level"] == 1)
    check("combat level resets to 1", switched["level"] == 1)
    check("combat experience resets to 0", switched["xp"] == 0)
    check("combat stats reset to 0",
          switched["stats"] == {"strength": 0, "defense": 0, "health": 0,
                                "speed": 0, "luck": 0})
    check("banked stat points reset to 0", switched["stat_points"] == 0)
    check("health resets to full 100",
          switched["hp"] == 100 and switched["max_hp"] == 100)
    check("quest level resets to 1", switched["quest_level"] == 1)
    check("quest experience resets to 0", switched["quest_xp"] == 0)
    check("quest points reset to 0", switched["quest_points"] == 0)
    check("quest stats reset to 0",
          switched["quest_stats"] == {"charm": 0, "renown": 0,
                                      "insight": 0})
    check("reputation with every giver resets to empty",
          switched["quests_rep"] == {})
    check("quest board and history reset to empty",
          switched["quests_board"] == [] and switched["quests_done"] == []
          and switched["quests_active"] is None)
    check("Healing stays at its level",
          switched["healing_level"] == 2)
    check("first switch is free, credits stay",
          switched["credits"] == 500)
    check("wins and losses stay",
          switched["wins"] == 7 and switched["losses"] == 3)
    check("switch count goes up by 1",
          switched["kind_switches"] == 1)
    check("the original fighter is untouched",
          switcher["kind"] == "robot" and switcher["level"] == 5)
    check("a switched witch hits for 11",
          game_logic.weapon_damage(switched) == 11)

    # The second switch costs 100: a witch with 150 credits
    # switching to chef pays it and keeps the rest.
    switched["credits"] = 150
    back, error = game_logic.switched_fighter(switched, "chef")
    check("second switch has no error", error is None)
    check("second switch costs 100 credits", back["credits"] == 50)
    check("second switch renames to chef gear",
          back["weapon_name"] == "Trusty Spatula"
          and back["armor_name"] == "Chef Apron")
    check("Healing still stays after the second switch",
          back["healing_level"] == 2)

    # Cannot afford it: nothing changes, and the error says so.
    poor = game_logic.new_fighter("Poor", "robot")
    poor["kind_switches"] = 1
    poor["credits"] = 50
    broke, error = game_logic.switched_fighter(poor, "chef")
    check("a switch you cannot afford is refused",
          broke is None and error is not None
          and "100 credits" in error and "50 credits" in error)
    check("a refused switch leaves the fighter alone",
          poor["kind"] == "robot" and poor["credits"] == 50)

    # Same kind and unknown kind are refused.
    same, error = game_logic.switched_fighter(switcher, "robot")
    check("switching to the same kind is refused",
          same is None and error is not None)
    weird, error = game_logic.switched_fighter(switcher, "wizard")
    check("switching to an unknown kind is refused",
          weird is None and error is not None)

    # An old fighter with no switch count and no quest fields
    # switches fine: missing means 0, never a crash.
    old_switcher = game_logic.new_fighter("Old", "chef")
    old_switcher.pop("kind_switches", None)
    old_switcher.pop("quest_level", None)
    old_switcher.pop("quest_stats", None)
    old_switcher["credits"] = 0
    old_switched, error = game_logic.switched_fighter(
        old_switcher, "witch")
    check("an old fighter switches for free",
          error is None and old_switched["kind"] == "witch")
    check("an old fighter's Healing still stays at 0",
          old_switched["healing_level"] == 0)

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

    # Phase 30 hotfix (Makenna Nov 19, 2026): the Nov 19
    # Healing crash. The server stored a running upgrade with
    # a null level (and a null finish) on her fighter, and the
    # game crashed on every launch and every second in
    # upgrade_status: "%d format needs a real number, not
    # NoneType". A broken upgrade record must never crash
    # anything: it reads as "no upgrade running", and the
    # next tick clears it instead of looping the error.
    broken = game_logic.new_fighter("Broken", "robot")
    broken["credits"] = 1500
    broken["upgrade"] = {
        "slot": "healing", "name": "Second Wind",
        "level": None, "finish": 1000000.0 + 4 * 3600,
    }
    broken["upgrade_queue"] = None
    broken["upgrade_total"] = None
    check("upgrade_status with a null level is None, not a crash",
          game_logic.upgrade_status(broken, now=1000000.0) is None)
    check("a null-level upgrade is not running",
          game_logic.upgrade_is_running(broken) is False)
    check("status_text with a null-level upgrade does not crash",
          "I'm upgrading" not in game_logic.status_text(broken, now=1000000.0)
          and "Second Wind level 0" in game_logic.status_text(broken, now=1000000.0))
    line = game_logic.finish_upgrade_if_ready(broken, now=1000000.0 + 1)
    check("the broken upgrade is cleared on the next tick",
          broken.get("upgrade") is None
          and broken.get("upgrade_queue") is None)
    check("the clearing is said once, in plain words",
          line is not None and "broken upgrade is cleared" in line)
    check("a second tick after clearing says nothing",
          game_logic.finish_upgrade_if_ready(broken, now=1000000.0 + 2) is None)

    broken2 = game_logic.new_fighter("Broken2", "robot")
    broken2["upgrade"] = {
        "slot": "healing", "name": "Second Wind",
        "level": 1, "finish": None,
    }
    check("upgrade_status with a null finish is None, not a crash",
          game_logic.upgrade_status(broken2, now=1000000.0) is None)
    check("a null-finish upgrade is not running",
          game_logic.upgrade_is_running(broken2) is False)

    broken3 = game_logic.new_fighter("Broken3", "robot")
    broken3["upgrade"] = {"slot": "healing"}
    check("upgrade_status with missing level and finish is None",
          game_logic.upgrade_status(broken3, now=1000000.0) is None)

    # The same crash class, one tick away: a JSON-null
    # credits field or repair_until must not crash the
    # status line or the repair checks either.
    nulls = game_logic.new_fighter("Nulls", "robot")
    nulls["credits"] = None
    nulls["repair_until"] = None
    check("status_text with null credits and repair does not crash",
          "0 credits" in game_logic.status_text(nulls, now=1000000.0))
    check("null repair_until means not repairing",
          game_logic.is_repairing(nulls, now=1000000.0) is False)
    check("null repair_until leaves no seconds",
          game_logic.repair_left_seconds(nulls, now=1000000.0) == 0)

    # Max affordable Healing on a fighter with NO
    # healing_level key (the Nov 19 case): all 5 levels for
    # 915 credits, and the buy leaves 585 from 1500.
    no_key = game_logic.new_fighter("NoKey", "robot")
    del no_key["healing_level"]
    no_key["credits"] = 1500
    plan = game_logic.max_affordable(no_key, "healing")
    check("max affordable healing without the key is 5 levels",
          plan["levels"] == [1, 2, 3, 4, 5])
    check("max affordable healing without the key costs 915",
          plan["cost"] == 915)
    error, line = game_logic.start_max_upgrade(no_key, "healing", now=1000000.0)
    check("max healing without the key starts cleanly", error is None)
    check("max healing without the key deducts 915",
          no_key["credits"] == 585)

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
    # total wait never passes 4 hours. At weapon level 40 with
    # plenty of credits, the count is decided by CREDITS ONLY
    # (Phase 37): 8 levels for 9,077,666,704 credits, leaving
    # 922,333,296. The raw wait would be 20,880 seconds, so the
    # queue is shrunk to 4 hours exactly, and each level comes
    # faster than the usual one-level wait.
    queue_fighter = game_logic.new_fighter("Queuer", "robot")
    queue_fighter["credits"] = 10 ** 10
    queue_fighter["weapon_level"] = 40
    plan_huge = game_logic.max_affordable(queue_fighter, "weapon")
    check("a rich queue buys 8 levels at weapon 40",
          len(plan_huge["levels"]) == 8)
    check("8 levels at weapon 40 cost 9077666704 credits",
          plan_huge["cost"] == 9077666704)
    check("8 levels at weapon 40 leave 922333296 credits",
          plan_huge["credits_left"] == 922333296)
    check("max affordable never passes 4 hours total",
          plan_huge["seconds"] == game_logic.MAX_TIMER_SECONDS)
    check("the raw wait is longer than 4 hours",
          plan_huge["raw_seconds"] == 20880)
    check("a shrunk queue carries a scale below 1",
          0 < plan_huge["time_scale"] < 1)
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
    # must still respect the 4-hour wait cap. The cap binds on the
    # WAIT, not on the count (Phase 37): the count is decided by
    # credits only, and the waits shrink so the whole queue fits
    # in 4 hours. At level 1 a million credits buys 24 levels (not
    # the old 21 — the extra levels used to be cut off by the wait),
    # ten million buys 30, a billion buys 41. At weapon level 50
    # with 10 trillion credits, 15 levels; at weapon level 200 with
    # 1e38 credits, 7 levels. Every one of these queues takes
    # exactly 4 hours, with each level coming faster than usual.
    for weapon_level, credits, want_levels in (
        (1, 1_000_000, 24),
        (1, 10_000_000, 30),
        (1, 1_000_000_000, 41),
        (50, 10_000_000_000_000, 15),
        (200, 10 ** 38, 7),
    ):
        big = game_logic.new_fighter("Big", "robot")
        big["weapon_level"] = weapon_level
        big["credits"] = credits
        plan = game_logic.max_affordable(big, "weapon")
        check("big numbers: %d levels at weapon %d" % (want_levels, weapon_level),
              len(plan["levels"]) == want_levels)
        check("big numbers: wait is exactly 4 hours at weapon %d" % weapon_level,
              plan["seconds"] == game_logic.MAX_TIMER_SECONDS)
        check("big numbers: the queue is shrunk at weapon %d" % weapon_level,
              0 < plan["time_scale"] < 1)
        err, line = game_logic.start_max_upgrade(big, "weapon", now=1000000.0)
        check("big numbers: queue starts at weapon %d" % weapon_level, err is None)
        check("big numbers: the stored queue carries the scale at weapon %d"
              % weapon_level,
              big["upgrade"].get("time_scale") == plan["time_scale"])
        now = 1000000.0
        while big.get("upgrade"):
            now = big["upgrade"]["finish"] + 1
            game_logic.finish_upgrade_if_ready(big, now=now)
        check("big numbers: queue drains at weapon %d" % weapon_level,
              not big.get("upgrade") and not big.get("upgrade_queue"))
        check("big numbers: final level %d at weapon %d" % (weapon_level + want_levels, weapon_level),
              big["weapon_level"] == weapon_level + want_levels)

    # A long queue caught up late drains in ONE call: start 8
    # levels at weapon 40, jump past the 4-hour finish, and all
    # 8 land at once, with one line saying all levels are done.
    # (Before Phase 37 this took one call per level.)
    catcher = game_logic.new_fighter("Catcher", "robot")
    catcher["credits"] = 10 ** 10
    catcher["weapon_level"] = 40
    error, line = game_logic.start_max_upgrade(
        catcher, "weapon", now=1000000.0)
    check("catch-up queue starts", error is None)
    check("catch-up queue is shrunk to 4 hours",
          catcher["upgrade"]["finish"] <= 1000000.0
          + game_logic.MAX_TIMER_SECONDS)
    line = game_logic.finish_upgrade_if_ready(
        catcher, now=1000000.0 + game_logic.MAX_TIMER_SECONDS + 1)
    check("one late call drains the whole queue",
          catcher["weapon_level"] == 48
          and catcher.get("upgrade") is None)
    check("one late call says all levels are done",
          line is not None and "All 8 levels are done." in line)
    # A short queue is not shrunk at all: 500 credits from level 1
    # takes the raw 15 minutes, scale 1, one level at a time.
    short = game_logic.new_fighter("Short", "robot")
    short["credits"] = 500
    plan_short = game_logic.max_affordable(short, "weapon")
    check("a short queue is not shrunk",
          plan_short["time_scale"] == 1
          and plan_short["seconds"] == 900
          and plan_short["raw_seconds"] == 900)

    # The witch study (Phase 38, Makenna Nov 25, 2026): the
    # spell table, study learning, casting in fights, the
    # Study-tab lines, and the Belle rule for the board.
    check("there are ten elements", len(spells.ELEMENTS) == 10)
    check("there are five tiers", len(spells.TIERS) == 5)
    all_names = [name for names in spells.SPELL_NAMES.values()
                 for name in names]
    check("there are fifty spells", len(all_names) == 50)
    check("every spell name is different", len(set(all_names)) == 50)
    check("every element has a first-person cast line",
          all(spells.cast_line(element)
              and spells.cast_line(element).startswith("I ")
              and spells.cast_line(element).endswith("!")
              for element in spells.ELEMENTS))
    check("spell costs double each tier",
          [spells.spell_cost(tier) for tier in spells.TIERS]
          == [25, 50, 100, 200, 400])
    check("spell times double each tier",
          [spells.spell_minutes(tier) for tier in spells.TIERS]
          == [15, 30, 60, 120, 240])
    check("learning all fifty spells once costs 7750 credits",
          sum(spells.spell_cost(tier) for tier in spells.TIERS) * 10
          == 7750)
    check("learning all fifty spells once takes 77 and a half hours",
          sum(spells.spell_minutes(tier) for tier in spells.TIERS) * 10
          == 4650)
    check("legendary is the four-hour cap",
          spells.spell_seconds("legendary") == 4 * 3600)
    check("a level 1 spell adds no damage",
          spells.spell_damage_bonus(1) == 0)
    check("a level 2 spell adds 2 damage",
          spells.spell_damage_bonus(2) == 2)
    check("a level 5 spell adds 8 damage",
          spells.spell_damage_bonus(5) == 8)
    check("a cast line names its element",
          spells.element_for_cast_line(
              "I call the fire, and it bursts from my wand!") == "fire")
    check("a hit line names no element",
          spells.element_for_cast_line("I hit the Scrap Rat for 12.")
          is None)

    # The next spell per element, and the tier prerequisite.
    check("a fresh witch's next fire spell is Ember Spark",
          spells.next_spell_for_element(witch, "fire")
          == ("common", "Ember Spark", 0, False))
    check("common has no prerequisite",
          spells.can_learn(witch, "fire", "common") == (True, None))
    check("uncommon needs common first",
          spells.can_learn(witch, "fire", "uncommon")[0] is False
          and "Ember Spark"
          in spells.can_learn(witch, "fire", "uncommon")[1])
    check("an unknown element is refused",
          spells.can_learn(witch, "arcane", "common")[0] is False)
    learned_all_fire = game_logic.new_fighter("Learned", "witch", "female")
    learned_all_fire["spells"] = {"fire": {
        "common": 1, "uncommon": 1, "rare": 1, "epic": 1,
        "legendary": 1}}
    check("after all five fire tiers the next is an upgrade",
          spells.next_spell_for_element(learned_all_fire, "fire")
          == ("common", "Ember Spark", 1, True))

    # Study learning, offline mirror: start, pause, resume,
    # finish, upgrade — and the blocks (kind, prerequisite,
    # one spell at a time, broke).
    student = game_logic.new_fighter("Student", "witch", "female")
    student["credits"] = 500
    check("a new witch has no spells and no study",
          spells.spells_of(student) == {}
          and spells.study_of(student) is None
          and game_logic.study_is_learning(student) is False)
    check("a new fighter starts with no spells and no study",
          game_logic.new_fighter("New", "witch")["spells"] == {}
          and game_logic.new_fighter("New", "witch")["study"] is None)
    check("a robot cannot learn spells",
          "only a witch" in (
              game_logic.study_start(
                  game_logic.new_fighter("Rob", "robot"),
                  "fire", "common") or ""))
    check("a chef cannot learn spells",
          "only a witch" in (
              game_logic.study_start(
                  game_logic.new_fighter("Cook", "chef"),
                  "fire", "common") or ""))
    check("learning starts when affordable",
          game_logic.study_start(student, "fire", "common",
                                 now=1000000.0) is None)
    check("learning costs 25 credits up front",
          student["credits"] == 475)
    check("the study records the spell and its finish",
          student["study"]["element"] == "fire"
          and student["study"]["tier"] == "common"
          and student["study"]["name"] == "Ember Spark"
          and student["study"]["level"] == 1
          and student["study"]["finish_at"] == 1000000.0 + 900)
    check("the study status names the spell and the time",
          "Ember Spark" in (
              game_logic.study_status(student, now=1000000.0) or "")
          and "about 15 minutes" in (
              game_logic.study_status(student, now=1000000.0) or ""))
    check("a second spell is blocked while learning",
          "already learning" in (
              game_logic.study_start(student, "water", "common",
                                     now=1000001.0) or ""))
    check("the study is not ready early",
          game_logic.finish_study_if_ready(student, now=1000000.0 + 60)
          is None)
    check("pausing freezes 14 minutes",
          game_logic.study_pause(student, now=1000000.0 + 60) == 840)
    check("a paused study says paused",
          "paused" in (
              game_logic.study_status(student, now=1000000.0 + 60) or ""))
    check("a paused study never finishes",
          game_logic.finish_study_if_ready(student, now=1000000.0 + 100000)
          is None)
    check("resuming the same spell is free",
          game_logic.study_start(student, "fire", "common",
                                 now=1000000.0 + 120) is None
          and student["credits"] == 475)
    check("resuming keeps the same remaining time",
          student["study"]["finish_at"] == 1000000.0 + 120 + 840)
    line = game_logic.finish_study_if_ready(
        student, now=1000000.0 + 120 + 840 + 1)
    check("the spell finishes after its time",
          line is not None and "I learned Ember Spark!" in line)
    check("finishing grants level 1",
          student["spells"] == {"fire": {"common": 1}}
          and student["study"] is None)
    check("learning the same spell again upgrades it",
          game_logic.study_start(student, "fire", "common",
                                 now=2000000.0) is None
          and student["study"]["level"] == 2
          and student["credits"] == 450)
    line = game_logic.finish_study_if_ready(student, now=2000000.0 + 901)
    check("the upgrade finishes at level 2",
          line is not None and "My Ember Spark is now level 2." in line
          and student["spells"]["fire"]["common"] == 2)
    broke = game_logic.new_fighter("Broke", "witch", "female")
    broke["credits"] = 10
    broke_error = game_logic.study_start(broke, "fire", "common",
                                         now=1000000.0)
    check("a broke witch cannot start learning",
          broke_error is not None
          and "25 credits" in broke_error
          and "10 credits" in broke_error)
    # Spell trainers (Phase 38, Makenna Nov 25, 2026): learning
    # is taught by another warlock or witch, in the trainer's
    # own voice — Hazel for brewing, Rowan for storm, Wren for
    # moonlight, Bram for every upgrade. The voices are the
    # four study givers, all verified alive on Microsoft's live
    # Edge list Nov 25, 2026.
    check("every element has a trainer",
          all(spells.trainer_for_spell(element)[0] is not None
              for element in spells.ELEMENTS))
    check("Hazel teaches fire, water and poison",
          [spells.trainer_for_spell(element)[0]
           for element in ("fire", "water", "poison")]
          == ["Hazel", "Hazel", "Hazel"])
    check("Rowan teaches wind, lightning and earth",
          [spells.trainer_for_spell(element)[0]
           for element in ("wind", "lightning", "earth")]
          == ["Rowan", "Rowan", "Rowan"])
    check("Wren teaches ice, light, shadow and dark",
          [spells.trainer_for_spell(element)[0]
           for element in ("ice", "light", "shadow", "dark")]
          == ["Wren", "Wren", "Wren", "Wren"])
    check("Bram teaches every upgrade, whatever the element",
          all(spells.trainer_for_spell(element, True)
              == ("Bram", "en-US-SteffanNeural")
              for element in spells.ELEMENTS))
    check("the trainer voices are the four study givers' voices",
          set(voice for _trainer, voice in
              [spells.trainer_for_spell(element)
               for element in spells.ELEMENTS]
              + [spells.trainer_for_spell("fire", True)])
          == {"en-US-AvaNeural", "en-US-RogerNeural",
              "en-US-AnaNeural", "en-US-SteffanNeural"})
    check("an unknown element has no trainer, never a crash",
          spells.trainer_for_spell("arcane") == (None, None))
    check("a trainer's opening talks to the player by name",
          "Katprincess" in spells.trainer_opening_line(
              "Hazel", "Katprincess", "Ember Spark")
          and "Ember Spark" in spells.trainer_opening_line(
              "Hazel", "Katprincess", "Ember Spark"))
    check("the opening uses the fighter's real name, not Katprincess",
          "Katprincess" not in spells.trainer_opening_line(
              "Hazel", "Piper", "Ember Spark")
          and "Piper" in spells.trainer_opening_line(
              "Hazel", "Piper", "Ember Spark"))
    check("a trainer's learn line talks to the player by name",
          "Katprincess" in spells.trainer_learn_line(
              "Rowan", "Katprincess", "Gale Rush")
          and "Gale Rush" in spells.trainer_learn_line(
              "Rowan", "Katprincess", "Gale Rush"))
    check("Bram's upgrade line names the spell and its new level",
          "Ember Spark" in spells.trainer_upgrade_line(
              "Katprincess", "Ember Spark", 2)
          and "level 2" in spells.trainer_upgrade_line(
              "Katprincess", "Ember Spark", 2))
    check("the same spell always gets the same trainer line",
          spells.trainer_opening_line("Hazel", "Katprincess",
                                      "Ember Spark")
          == spells.trainer_opening_line("Hazel", "Katprincess",
                                         "Ember Spark"))
    check("every teaching line is short enough for Alexa",
          all(len(line.split()) < 25
              for lines in list(spells.TRAINER_OPENINGS.values())
              + list(spells.TRAINER_LEARN_LINES.values())
              + [spells.TRAINER_UPGRADE_LINES]
              for line in lines))
    check("an unknown trainer has no teaching line",
          spells.trainer_opening_line("Nobody", "Katprincess",
                                      "Ember Spark") is None
          and spells.trainer_learn_line("Nobody", "Katprincess",
                                        "Ember Spark") is None)
    # An old fighter made before the study has no "study" key
    # at all: missing means nothing learning, never a crash.
    old_study = game_logic.new_fighter("OldStudy", "robot")
    del old_study["study"]
    check("an old fighter with no study key is not learning",
          game_logic.study_is_learning(old_study) is False
          and game_logic.finish_study_if_ready(old_study, now=1000000.0)
          is None
          and game_logic.study_pause(old_study, now=1000000.0) is None)
    check("status text with no study key does not crash",
          "OldStudy" in game_logic.status_text(old_study, now=1000000.0))
    # A broken study record (null finish) is cleared on the
    # next tick, like the Phase 30 broken upgrade — never a
    # crash in the once-a-second tick.
    broken_study = game_logic.new_fighter("BrokenStudy", "witch", "female")
    broken_study["study"] = {
        "element": "fire", "tier": "common", "name": "Ember Spark",
        "level": 1, "finish_at": None, "paused": False}
    check("a broken study record is not learning",
          game_logic.study_is_learning(broken_study) is False)
    line = game_logic.finish_study_if_ready(broken_study, now=1000000.0)
    check("a broken study record is cleared, not crashed",
          line is not None and "broken study is cleared" in line
          and broken_study["study"] is None)
    # Switching resets spells and study, like the quest level.
    switcher2 = game_logic.new_fighter("Switcher2", "witch", "female")
    switcher2["spells"] = {"fire": {"common": 3}}
    switcher2["study"] = {
        "element": "fire", "tier": "rare", "name": "Burning Veil",
        "level": 1, "finish_at": 1000000.0 + 3600, "paused": False,
        "remaining_seconds": 0}
    switched2, error = game_logic.switched_fighter(switcher2, "robot")
    check("switching resets spells and study",
          error is None and switched2["spells"] == {}
          and switched2["study"] is None)

    # Casting in fights: a witch with nothing learned fights
    # wand-only, no cast line; a witch with a learned spell
    # casts it, and the cast line comes right before its hit
    # line. A robot never casts.
    wand_only = game_logic.fight(
        game_logic.new_fighter("WandOnly", "witch", "female"),
        rng=random.Random(38))
    check("a witch with no spells fights wand-only",
          not any(line in spells.CAST_LINES.values()
                  for line in wand_only["lines"]))

    def _fresh_caster():
        fighter = game_logic.new_fighter("Caster", "witch", "female")
        fighter["spells"] = {"fire": {"common": 1}}
        return fighter

    cast_lines = []
    cast_fight_lines = []
    for seed in range(20):
        result = game_logic.fight(_fresh_caster(),
                                  rng=random.Random(seed))
        cast_lines = [line for line in result["lines"]
                      if line in spells.CAST_LINES.values()]
        if cast_lines:
            cast_fight_lines = result["lines"]
            break
    check("a witch with a learned spell casts it", bool(cast_lines))
    check("the cast is the fire line",
          bool(cast_lines)
          and cast_lines[0] == spells.cast_line("fire"))
    check("a cast line is followed at once by its hit line",
          any(cast_fight_lines[i] in spells.CAST_LINES.values()
              and "I hit the " in cast_fight_lines[i + 1]
              for i in range(len(cast_fight_lines) - 1)))
    robot_fight = game_logic.fight(
        game_logic.new_fighter("RobFight", "robot"),
        rng=random.Random(7))
    check("a robot never casts",
          not any(line in spells.CAST_LINES.values()
                  for line in robot_fight["lines"]))

    # The Study-tab lines: one per element, cost and time in
    # plain words, and the learning/paused states.
    check("the fire line offers Ember Spark for 25 credits, 15 minutes",
          spells.study_spell_line(
              game_logic.new_fighter("Lister", "witch", "female"), "fire")
          == "Fire: learn Ember Spark, common, 25 credits, "
             "15 minutes (press Enter)")
    liner = game_logic.new_fighter("Liner", "witch", "female")
    liner["credits"] = 500
    game_logic.study_start(liner, "fire", "common", now=1000000.0)
    check("the line for a learning spell says how long is left",
          spells.study_spell_line(liner, "fire", now=1000000.0 + 60)
          .startswith("Fire: learning Ember Spark,")
          and "about 14 minutes" in spells.study_spell_line(
              liner, "fire", now=1000000.0 + 60))
    game_logic.study_pause(liner, now=1000000.0 + 60)
    check("the line for a paused spell offers to pick it up",
          "paused" in spells.study_spell_line(liner, "fire")
          and spells.study_spell_line(liner, "fire").endswith(
              "(press Enter)"))

    # The givers and the board: ten givers, five male and five
    # female, and the Belle rule — every giver can be first.
    check("the hangout has ten givers", len(quests.GIVERS) == 10)
    check("five male and five female givers",
          sum(1 for giver in quests.GIVERS
              if giver["gender"] == "male") == 5
          and sum(1 for giver in quests.GIVERS
                  if giver["gender"] == "female") == 5)
    check("the four witch givers are Hazel, Rowan, Wren and Bram",
          set(spells.STUDY_GIVERS)
          == {"Hazel", "Rowan", "Wren", "Bram"}
          and all(giver in [entry["name"] for entry in quests.GIVERS]
                  for giver in spells.STUDY_GIVERS))
    first_board = quests.starting_board(random.Random(38))
    check("a starting board has 2 Easy, 2 Medium and 1 Hard",
          [quest["difficulty"] for quest in first_board]
          == ["Easy", "Easy", "Medium", "Medium", "Hard"])
    check("a starting board mixes male and female givers",
          len(set(quest["giver_gender"] for quest in first_board)) == 2)
    rng = random.Random(38)
    first_givers = set()
    for _ in range(200):
        first_givers.add(quests.starting_board(rng)[0]["giver"])
    check("every giver can be first on the starting board",
          first_givers
          == set(entry["name"] for entry in quests.GIVERS))
    template_names = [template["name"]
                      for template in quests.QUEST_TEMPLATES]
    witch_fair = quests.generate_quest(
        random.Random(38), "Hard",
        existing_names=[name for name in template_names
                        if name != "The Witch's Fair"])
    check("the Witch's Fair is a co-op quest from Hazel",
          witch_fair["name"] == "The Witch's Fair"
          and witch_fair["coop"] is True
          and witch_fair["giver"] == "Hazel")
    grand_fair = quests.generate_quest(
        random.Random(38), "Hard",
        existing_names=[name for name in template_names
                        if name != "The Grand Hangout Fair"])
    check("the Grand Hangout Fair is still a co-op quest",
          grand_fair["name"] == "The Grand Hangout Fair"
          and grand_fair["coop"] is True
          and grand_fair["giver"] == "Marge")

    # Status text is one plain summary.
    text = game_logic.status_text(saved)
    check("status text names the fighter", "Saver" in text and "chef" in text)

    print("\nAll game-logic smoke tests passed.")


if __name__ == "__main__":
    main()
