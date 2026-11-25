"""Elemental spells and the witch study (Phase 38, Makenna Nov 25, 2026).

A witch or warlock starts out fighting with her wand only — the wand
is basically a melee weapon. In the study she learns elemental spells,
one at a time, in real time: common first and legendary last, higher
tiers taking longer, with the same 4-hour cap as everything else.
Once a spell is learned, fights use it more than the wand — the wand
is only backup if a spell does not work. Every spell starts at level
1, and after all spells of all elements are learned a spell can keep
being upgraded, one level at a time, to do more damage, forever.

Learning acts like quests, NOT like repairs or upgrades: the clock
only ticks while the player is in the study. Leave the study and the
clock pauses, coming back resumes with the same time left — like
school, you cannot put studying down and expect it to get done
(Makenna, Nov 25, 2026). Repairs and upgrades keep ticking while
you are away; study learning does not.

Spells are stored on the fighter as plain strings and numbers, so
the DynamoDB conversion carries them over unchanged (see
WITCH_FIGHTER_DESIGN.md section 10):

    fighter["spells"] = {"fire": {"common": 2, "uncommon": 1}, ...}
    fighter["study"] = {"element": "fire", "tier": "uncommon",
                        "name": "Flame Lash", "level": 2,
                        "finish_at": <epoch>, "paused": False,
                        "remaining_seconds": 0}   # or None

A missing "spells" (an older fighter) means nothing learned yet;
a missing "study" means nothing being learned. Never a direct
read that crashes — that is Makenna's standing compatibility rule
(Nov 18, 2026, the lesson of the Phase 25b and Phase 30 crashes).

Costs and times below are a PROPOSAL for Makenna to tune: each
tier costs twice the last and takes twice as long. Learning a
spell costs its tier price; upgrading a learned spell one level
costs the same tier price again and takes the same tier time.
A tier can only be started once the tier below it in the same
element is learned (level 1 or more) — common has no prerequisite.
"""

import random

# The ten elements, in the order Makenna named them, with earth
# and lightning added (the two most obvious missing ones, from
# the witch draft). Light, shadow and dark stay three separate
# elements, exactly as she named them.
ELEMENTS = ("fire", "water", "ice", "wind", "poison",
            "light", "shadow", "dark", "earth", "lightning")

TIERS = ("common", "uncommon", "rare", "epic", "legendary")

# Spell names, one per element per tier — Maren's proposals from
# the witch draft (Makenna, Nov 25, 2026: "Maren can name them
# all"). Makenna can rename any of them.
SPELL_NAMES = {
    "fire": ("Ember Spark", "Flame Lash", "Burning Veil",
             "Inferno Roar", "Phoenix Rebirth"),
    "water": ("Splash", "Tide Pull", "Rushing Torrent",
              "Deep Current", "Ocean's Wrath"),
    "ice": ("Frost Bite", "Ice Shard", "Frozen Hold",
            "Blizzard Veil", "Eternal Winter"),
    "wind": ("Breeze Cut", "Gale Rush", "Storm Gust",
             "Cyclone Dance", "Skybreaker Tempest"),
    "poison": ("Sting", "Venom Drip", "Toxic Cloud",
               "Plague Bloom", "Thorned Doom"),
    "light": ("Glow", "Sunbeam", "Radiant Shield",
              "Dawn Burst", "Heaven's Light"),
    "shadow": ("Shade Touch", "Dark Whisper", "Shadow Bind",
               "Nightmare Veil", "Eclipse"),
    "dark": ("Gloom Bolt", "Midnight Coil", "Abyss Call",
             "Void Rend", "Oblivion"),
    "earth": ("Pebble Toss", "Stone Grip", "Rockslide",
              "Mountain Roar", "Titan's Awakening"),
    "lightning": ("Static Zap", "Spark Chain", "Thunder Crack",
                  "Storm Surge", "Tempest Crown"),
}

# Cast lines, one per element, first person, in the player's own
# voice — short, one sentence each, so they fit Alexa's 8-second
# limit. From the witch draft, section 5. The server speaks the
# same lines (see the Phase 38 migration): the two copies must
# stay word-for-word the same, or a fight would sound different
# online and off.
CAST_LINES = {
    "fire": "I call the fire, and it bursts from my wand!",
    "water": "I call the water, and it rushes where I point!",
    "ice": "I call the ice, and the air turns sharp and cold!",
    "wind": "I call the wind, and it howls around me!",
    "poison": "I brew the poison, and it curls through the air!",
    "light": "I call the light, and it shines too bright to face!",
    "shadow": "I call the shadows, and they gather at my side!",
    "dark": "I call the dark, and it drinks the light away!",
    "earth": "I call the earth, and the ground answers me!",
    "lightning": "I call the lightning, and the sky cracks open!",
}

# Learning cost in credits, by tier — PROPOSAL for Makenna to
# tune. Each tier costs twice the last, starting at the same 25
# credits a weapon level starts at.
SPELL_COSTS = {"common": 25, "uncommon": 50, "rare": 100,
               "epic": 200, "legendary": 400}

# Learning time in minutes, by tier — PROPOSAL for Makenna to
# tune. Each tier takes twice as long; legendary is the 4-hour
# cap, never more, like every other timer in the game.
SPELL_MINUTES = {"common": 15, "uncommon": 30, "rare": 60,
                 "epic": 120, "legendary": 240}

# The 4-hour cap, in seconds, like every other timer.
STUDY_MAX_SECONDS = 4 * 3600

# A learned spell adds damage in a fight: +2 for every level
# above 1. A level 1 spell is flavour only — it speaks its
# cast line and plays its sound, but hits no harder than the
# wand. A level 5 spell adds 8. PROPOSAL for Makenna to tune.
SPELL_DAMAGE_PER_LEVEL = 2

# Study quests (Phase 38): after a study quest ends, the next
# one starts 10 to 15 minutes later (Makenna, Nov 25, 2026) —
# a gap to study in, not a quest the moment the last one ends.
STUDY_QUEST_GAP_MINUTES = (10, 15)

# The four study quest givers — the witch givers from the witch
# draft, section 7. Their quests are the study quests, and they
# also give quests in the hangout like every other giver.
STUDY_GIVERS = ("Hazel", "Rowan", "Wren", "Bram")

# While learning, the study plays the ambience loop of the spell
# being learned, over the study music (Makenna, Nov 25, 2026).
# There is one loop per family of elements, not one per element
# — ten loops would be ten files to find and check. The families
# are by feel: bubbling for fire, water and poison; storm for
# wind, lightning and earth; moonlight for ice, light, shadow
# and dark. A quest's own ambience replaces the learning loop
# while a quest is running. Full per-element loops are a
# follow-up polish, not this phase.
ELEMENT_AMBIENCE = {
    "fire": "brewing",
    "water": "brewing",
    "poison": "brewing",
    "wind": "storm",
    "lightning": "storm",
    "earth": "storm",
    "ice": "moonlight",
    "light": "moonlight",
    "shadow": "moonlight",
    "dark": "moonlight",
}

# Spell trainers (Phase 38, Makenna Nov 25, 2026): learning a
# spell is TAUGHT by another warlock or witch, and the teaching
# lines speak in the trainer's voice, talking to the player
# directly by name — like the hangout quest givers do, because
# that gives it more personality. Hazel teaches the brewing
# elements, Rowan the storm elements, Wren the moonlight
# elements; Bram, the old warlock, teaches spell upgrades —
# any element, level 2 and up. The voices are the same ones
# quests.py GIVERS uses for these four, all verified alive on
# Microsoft's live Edge list Nov 25, 2026 (the Phase 27
# lesson: Davis and Sara looked fine and were dead). The
# mapping is client-side only — the trainer is presentation,
# derived from the element — so no server change and no new
# migration. If a trainer or voice is ever missing, the game
# falls back to the player's voice, never a crash
# (compatibility rule). Makenna can reassign trainers when
# she tests them; only this mapping changes, nothing else.
TRAINER_FOR_ELEMENT = {
    "fire": "Hazel",
    "water": "Hazel",
    "poison": "Hazel",
    "wind": "Rowan",
    "lightning": "Rowan",
    "earth": "Rowan",
    "ice": "Wren",
    "light": "Wren",
    "shadow": "Wren",
    "dark": "Wren",
}

TRAINER_VOICES = {
    "Hazel": "en-US-AvaNeural",
    "Rowan": "en-US-RogerNeural",
    "Wren": "en-US-AnaNeural",
    "Bram": "en-US-SteffanNeural",
}

UPGRADE_TRAINER = "Bram"

# Teaching lines, three per trainer per moment, rotating —
# the same spell always gets the same line (picked from the
# spell's name, like quests.quest_variant picks a quest's
# variant), so the trainer feels steady, not random. Every
# line talks to the player directly by name — "Katprincess"
# in the text is swapped for the fighter's real name, the
# same way quest lines do it — and stays short enough for
# Alexa's 8-second limit (every line is under 25 words).
# A resume picks up an opening line again: the trainer
# greets the returning student, same as a fresh start.
TRAINER_OPENINGS = {
    "Hazel": (
        "Katprincess, come closer — {spell} starts with a steady "
        "hand, not a wild one.",
        "Katprincess, the herbs are listening. Let's coax {spell} "
        "out gently, together.",
        "Ah, Katprincess — {spell} likes patience. Breathe in, "
        "and we'll begin.",
    ),
    "Rowan": (
        "Katprincess, the storm is waiting! {spell} won't tame "
        "itself — let's go.",
        "Ha! Katprincess, you've got the spark. {spell} answers "
        "the bold, not the shy.",
        "Katprincess, stand tall — {spell} bends to those who "
        "don't flinch.",
    ),
    "Wren": (
        "Katprincess, the moon is up — the perfect hour for "
        "{spell}. Shall we?",
        "Softly now, Katprincess. {spell} comes to quiet hearts, "
        "not loud ones.",
        "Katprincess, close your eyes a moment. {spell} is "
        "already reaching for you.",
    ),
    "Bram": (
        "Ah, Katprincess. You return to sharpen {spell}. Sit. "
        "We take our time.",
        "Katprincess, an old spell can still learn new tricks. "
        "{spell} is listening.",
        "Slow and steady, Katprincess. {spell} grows stronger "
        "with every careful hour.",
    ),
}

TRAINER_LEARN_LINES = {
    "Hazel": (
        "There, Katprincess — {spell} is yours now. The herbs "
        "are proud of you.",
        "You did it, Katprincess! {spell} blooms for you, just "
        "like I knew it would.",
        "Lovely work, Katprincess. {spell} will grow with you "
        "from here.",
    ),
    "Rowan": (
        "Ha! Look at that, Katprincess — {spell} is yours. The "
        "storm listens to you now.",
        "Katprincess, you tamed it! {spell} crackles at your "
        "call. Well struck.",
        "That's the way, Katprincess! {spell} is yours — the sky "
        "itself noticed.",
    ),
    "Wren": (
        "Oh, Katprincess — {spell} glows for you now. Beautiful, "
        "just like moonlight.",
        "You did it, Katprincess. {spell} is yours, shining soft "
        "and true.",
        "There it is, Katprincess — {spell}, learned under a kind "
        "moon.",
    ),
    "Bram": (
        "Well, Katprincess — {spell} is yours now. Even old "
        "warlocks learn new tricks.",
        "There it is, Katprincess. {spell} answers to you now. "
        "Guard it well.",
        "Slow work, well done, Katprincess. {spell} is yours.",
    ),
}

# Upgrade completions are always Bram's (he teaches every
# upgrade), and they name the new level.
TRAINER_UPGRADE_LINES = (
    "There, Katprincess — {spell} is level {level} now. Sharper, "
    "like a honed blade.",
    "Well done, Katprincess. {spell} stands at level {level} — "
    "the shadows approve.",
    "Katprincess, {spell} is level {level} now. Old magic, made "
    "stronger by your hands.",
)


def _trainer_variant(key, count):
    """Which of a trainer's lines a spell gets: picked from the
    spell's name, so the same spell always gets the same line
    (like quests.quest_variant picks a quest's variant from its
    id — never hash(), which is randomised per process)."""
    return sum(ord(c) for c in str(key or "")) % max(1, count)


def _trainer_line(lines, fighter_name, spell_name, level=None):
    """Fill in one teaching line: the player's real name in
    place of Katprincess, the spell's name, and the new level
    for an upgrade line."""
    if not lines:
        return None
    line = lines[_trainer_variant(spell_name, len(lines))]
    line = line.replace("Katprincess", fighter_name or "Katprincess")
    line = line.replace("{spell}", spell_name or "a spell")
    if level is not None:
        line = line.replace("{level}", str(level))
    return line


def trainer_for_spell(element, is_upgrade=False):
    """(trainer name, voice) teaching this spell — Bram for an
    upgrade, the element's trainer for a first learning — or
    (None, None) when the element is unknown. The caller falls
    back to the player's voice then, never a crash."""
    if is_upgrade:
        return (UPGRADE_TRAINER, TRAINER_VOICES[UPGRADE_TRAINER])
    trainer = TRAINER_FOR_ELEMENT.get(element or "")
    if not trainer:
        return (None, None)
    return (trainer, TRAINER_VOICES.get(trainer))


def trainer_opening_line(trainer, fighter_name, spell_name):
    """The trainer's greeting when learning starts — or when a
    paused spell is picked up again. None for an unknown
    trainer; the caller then says nothing in the trainer's
    voice."""
    lines = TRAINER_OPENINGS.get(trainer or "")
    if not lines:
        return None
    return _trainer_line(lines, fighter_name, spell_name)


def trainer_learn_line(trainer, fighter_name, spell_name):
    """The trainer's line when a spell is learned for the first
    time. None for an unknown trainer."""
    lines = TRAINER_LEARN_LINES.get(trainer or "")
    if not lines:
        return None
    return _trainer_line(lines, fighter_name, spell_name)


def trainer_upgrade_line(fighter_name, spell_name, level):
    """Bram's line when a spell reaches a new level. Upgrades
    are always Bram's, whatever the element."""
    return _trainer_line(TRAINER_UPGRADE_LINES, fighter_name,
                         spell_name, level=level)


def spell_name(element, tier):
    """The spell's name, or None for an unknown element or tier."""
    names = SPELL_NAMES.get(element or "")
    if not names:
        return None
    try:
        return names[TIERS.index(tier)]
    except ValueError:
        return None


def spell_cost(tier):
    """Credits to learn — or to upgrade one level of — a spell
    of this tier. None for an unknown tier."""
    return SPELL_COSTS.get(tier)


def spell_minutes(tier):
    """Minutes to learn — or to upgrade one level of — a spell
    of this tier. None for an unknown tier."""
    return SPELL_MINUTES.get(tier)


def spell_seconds(tier):
    """Seconds to learn a spell of this tier, capped at 4 hours."""
    minutes = spell_minutes(tier)
    if minutes is None:
        return None
    return min(minutes * 60, STUDY_MAX_SECONDS)


def spells_of(fighter):
    """The fighter's learned spells, as {element: {tier: level}}.
    Missing means nothing learned yet — never a crash, for a
    fighter made before the study existed."""
    spells = (fighter or {}).get("spells") or {}
    out = {}
    for element in ELEMENTS:
        tiers = spells.get(element) or {}
        levels = {}
        for tier in TIERS:
            level = int(tiers.get(tier) or 0)
            if level > 0:
                levels[tier] = level
        if levels:
            out[element] = levels
    return out


def spell_level(fighter, element, tier):
    """The level of one spell, 0 when it is not learned yet."""
    spells = (fighter or {}).get("spells") or {}
    tiers = spells.get(element or "") or {}
    return max(0, int(tiers.get(tier or "") or 0))


def learned_spells(fighter):
    """Every learned spell, as a list of (element, tier, name,
    level) — in element order, common first. Empty when the
    witch has learned nothing yet and still fights wand-only."""
    out = []
    for element in ELEMENTS:
        for tier in TIERS:
            level = spell_level(fighter, element, tier)
            if level > 0:
                out.append((element, tier, spell_name(element, tier),
                            level))
    return out


def spell_count(fighter):
    """How many spells the fighter has learned, of the 50."""
    return len(learned_spells(fighter))


def cast_line(element):
    """The cast line for one element, or None."""
    return CAST_LINES.get(element or "")


def element_for_cast_line(line):
    """Which element a cast line belongs to, or None. The game
    uses this to play the right elemental sound under the line
    — the line itself carries the element, so no extra field
    has to travel from the server."""
    for element, text in CAST_LINES.items():
        if text == (line or ""):
            return element
    return None


def spell_damage_bonus(level):
    """Extra damage a cast spell adds: +2 per level above 1.
    Level 1 adds nothing — flavour only."""
    return SPELL_DAMAGE_PER_LEVEL * max(0, int(level or 0) - 1)


def pick_spell(fighter, rng=None):
    """Pick one learned spell at random for a fight hit — every
    learned spell has the same chance, whatever its level. None
    when nothing is learned yet: the witch fights wand-only.
    Returns (element, tier, name, level)."""
    learned = learned_spells(fighter)
    if not learned:
        return None
    rng = rng or random
    return rng.choice(learned)


def tier_index(tier):
    """0 for common, up to 4 for legendary; -1 for unknown."""
    try:
        return TIERS.index(tier)
    except ValueError:
        return -1


def next_spell_for_element(fighter, element):
    """The next spell to learn or upgrade for one element: the
    lowest tier not yet learned, or — when all five tiers are
    learned — the lowest-level learned spell of that element,
    to upgrade one level. One line per element on the Study
    tab offers exactly this spell, so a player never has to
    arrow through all 50 spells to find the next one.
    Returns (tier, name, level_now, is_upgrade) or None when
    the element is unknown."""
    if element not in ELEMENTS:
        return None
    for tier in TIERS:
        level = spell_level(fighter, element, tier)
        if level <= 0:
            return (tier, spell_name(element, tier), 0, False)
    # All five tiers learned: upgrade the lowest-level one.
    best = None
    for tier in TIERS:
        level = spell_level(fighter, element, tier)
        if best is None or level < best[2]:
            best = (tier, spell_name(element, tier), level, True)
    return best


def can_learn(fighter, element, tier):
    """Whether this spell can be started now: the element and
    tier exist, and the tier below it in the same element is
    already learned (common has no prerequisite). Returns
    (True, None) or (False, plain-words reason)."""
    if element not in ELEMENTS or tier not in TIERS:
        return False, "I do not know that spell."
    index = tier_index(tier)
    if index > 0:
        below = TIERS[index - 1]
        if spell_level(fighter, element, below) <= 0:
            return False, (
                "I need to learn %s first, before I can learn %s."
                % (spell_name(element, below), spell_name(element, tier)))
    return True, None


def study_of(fighter):
    """The spell being learned now, or None. A missing or
    broken study record means nothing is being learned —
    never a crash (compatibility rule)."""
    study = (fighter or {}).get("study")
    if not isinstance(study, dict):
        return None
    if study.get("element") not in ELEMENTS:
        return None
    if study.get("tier") not in TIERS:
        return None
    return study


def study_status_line(fighter, now=None):
    """One plain-words line for the study: what is being
    learned and how long is left, or that nothing is being
    learned. The remaining time is what the study clock says
    — paused time is frozen, never counted down."""
    import time
    if now is None:
        now = time.time()
    study = study_of(fighter)
    if not study:
        return "I am not learning a spell right now."
    name = study.get("name") or spell_name(
        study.get("element"), study.get("tier")) or "a spell"
    if study.get("paused"):
        remaining = study.get("remaining_seconds") or 0
        return (
            "I am learning %s — paused, %s left. Going back to "
            "the study picks it up where I left off."
            % (name, _format_time(remaining)))
    finish = study.get("finish_at") or 0
    remaining = max(0.0, finish - now)
    return "I am learning %s, %s left." % (name, _format_time(remaining))


def _format_time(seconds):
    """Short plain-words time, like game_logic.format_time."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "%d seconds" % seconds
    minutes = seconds // 60
    if minutes < 60:
        if minutes <= 1:
            return "about 1 minute"
        return "about %d minutes" % minutes
    hours = seconds / 3600.0
    if hours < 2:
        return "about 1 hour"
    return "about %d hours" % int(round(hours))


def study_is_learning(fighter):
    """Whether a spell is being learned right now: a study
    record exists and it is not paused. A paused study is
    not learning — the clock is frozen until the player comes
    back to the study. The one-second tick completes a study
    whose time is up, so a finished-but-not-yet-completed
    study still counts as learning here for one tick."""
    study = study_of(fighter)
    if not study:
        return False
    return not study.get("paused")


def study_spell_line(fighter, element, now=None):
    """One Study-tab line for one element: the next spell to
    learn or upgrade there, with its cost and time, and
    "(press Enter)" when it can be started — or, when this
    element's spell is the one being learned now, how long is
    left on it. One line per element, so the player never has
    to arrow through all 50 spells to find the next one."""
    import time
    if now is None:
        now = time.time()
    label = element.capitalize()
    study = study_of(fighter)
    if study and study.get("element") == element:
        name = study.get("name") or spell_name(
            element, study.get("tier")) or "a spell"
        if study.get("paused"):
            remaining = study.get("remaining_seconds") or 0
            return ("%s: learning %s — paused, %s left "
                    "(press Enter)"
                    % (label, name, _format_time(remaining)))
        remaining = max(0.0, (study.get("finish_at") or 0) - now)
        return "%s: learning %s, %s left." % (
            label, name, _format_time(remaining))
    nxt = next_spell_for_element(fighter, element)
    if nxt is None:
        return "%s: I do not know that spell." % label
    tier, name, level_now, is_upgrade = nxt
    cost = spell_cost(tier)
    minutes = spell_minutes(tier)
    if is_upgrade:
        return ("%s: upgrade %s to level %d, %s, %d credits, "
                "%d minutes (press Enter)"
                % (label, name, level_now + 1, tier, cost, minutes))
    return "%s: learn %s, %s, %d credits, %d minutes (press Enter)" % (
        label, name, tier, cost, minutes)


def study_ambience(fighter):
    """The ambience family for the spell being learned now, or
    None when nothing is being learned. The game plays this
    loop under the study music; a running quest's own ambience
    replaces it while the quest runs."""
    study = study_of(fighter)
    if not study:
        return None
    return ELEMENT_AMBIENCE.get(study.get("element"))
