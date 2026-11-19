"""Headless smoke test for main.py (the wxPython window).

wxPython is not installed on this machine, so wx is replaced with a
small stand-in module built from real classes (a bare Mock cannot be
a base class). The real game logic still runs underneath:
    python test_main_smoke.py

Covers: the window builds with all five tabs, every tab's list is
plain text, Enter on a fight item runs a real fight, Enter on a shop
item starts a real upgrade, idle fighting toggles, and the timer
finishes upgrades and repairs. It does NOT prove anything about NVDA,
focus order, or how the window looks on Windows: that needs a live
test by Joshua and McKenna.

Voice: edge-tts is not installed here either, so the first half runs
the no-voice fallback path (text only, no crash). The second half
stubs edge-tts with a fake that writes a small file instead of
calling the real service, and proves a line reaches the player. A
third half stubs a voice service that always fails, and a player that
cannot load a file, and proves each failure is logged in plain words
instead of silence. Every log line the game would write to
arena_log.txt is captured here, so the checks read the same words
Joshua would read.
"""

import io
import logging
import os
import random
import sys
import time
import types
from unittest import mock

# Capture every log line the game writes, the same words that would
# land in arena_log.txt on Joshua's machine.
LOG_CAPTURE = io.StringIO()
_log_handler = logging.StreamHandler(LOG_CAPTURE)
_log_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(_log_handler)
logging.getLogger().setLevel(logging.INFO)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Stand-in wx module, built from real classes ---------------------
# Only the pieces main.py touches are faked. ListBox and Notebook keep
# real state, so the window's list-refresh and tab logic run for real.


class _Widget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: None


class _ListBox(_Widget):
    def __init__(self, *args, **kwargs):
        self._items = []
        self._sel = -1

    def Set(self, items):
        self._items = list(items)
        if self._sel >= len(self._items):
            self._sel = -1

    def GetCount(self):
        return len(self._items)

    def GetString(self, index):
        return self._items[index]

    def GetSelection(self):
        return self._sel

    def SetSelection(self, index):
        self._sel = index

    def SetFocus(self):
        pass


class _TextCtrl(_Widget):
    def __init__(self, *args, **kwargs):
        self.text = ""

    def AppendText(self, text):
        self.text += text

    def GetValue(self):
        return self.text

    def SetFocus(self):
        pass


class _StaticText(_Widget):
    def __init__(self, *args, **kwargs):
        self.label = kwargs.get("label", "")

    def SetLabel(self, text):
        self.label = text

    def GetLabel(self):
        return self.label

    def Wrap(self, width):
        pass


class _Notebook(_Widget):
    def __init__(self, *args, **kwargs):
        self._pages = []
        self._sel = 0

    def AddPage(self, page, name):
        self._pages.append(name)

    def GetSelection(self):
        return self._sel

    def SetSelection(self, index):
        self._sel = index


class _Timer(_Widget):
    def Start(self, ms):
        pass

    def Stop(self):
        pass


class _RadioBox(_Widget):
    def GetSelection(self):
        return 0


class _FakeMusic:
    """Stand-in for pygame.mixer.music: records what would be played."""

    def __init__(self):
        self.loaded = []
        self.played = 0
        self.fail_load = False
        self.busy = False

    def load(self, path):
        if self.fail_load:
            raise RuntimeError("test: cannot decode this file")
        self.loaded.append(path)

    def play(self):
        self.played += 1
        self.busy = True

    def finish(self):
        """Pretend the current line has finished sounding."""
        self.busy = False

    def stop(self):
        self.busy = False

    def unload(self):
        pass

    def set_volume(self, value):
        pass

    def get_busy(self):
        return self.busy


class _FakeSound:
    """Stand-in for pygame.mixer.Sound: records what would be played."""

    def __init__(self, path):
        self.path = path
        self.played = 0
        self.maxtime = None
        self.loops = None
        self.volume = None
        self.stopped = False

    def play(self, loops=0, maxtime=None):
        self.played += 1
        self.loops = loops
        self.maxtime = maxtime

    def stop(self):
        self.stopped = True

    def set_volume(self, value):
        self.volume = value


class _FakeChannel:
    """Stand-in for pygame.mixer.Channel."""

    def __init__(self, number):
        self.number = number
        self.played = None
        self.loops = None
        self.stopped = False

    def play(self, sound, loops=0):
        self.played = sound
        self.loops = loops

    def stop(self):
        self.stopped = True


class _Frame(_Widget):
    def __init__(self, *args, **kwargs):
        self._status = ""

    def CreateStatusBar(self):
        pass

    def SetStatusText(self, text):
        self._status = text

    def GetStatusText(self):
        return self._status

    def Show(self):
        pass


class _Dialog(_Widget):
    # What ShowModal returns. Tests set this to ID_YES or
    # ID_NO before calling code that asks a yes/no question.
    modal_result = 1  # ID_OK

    def ShowModal(self):
        return type(self).modal_result

    def EndModal(self, result):
        type(self).modal_result = result

    def CreateButtonSizer(self, flags):
        return _Widget()

    def Destroy(self):
        pass


class _App(_Widget):
    def MainLoop(self):
        pass


def _make_wx():
    wx = types.ModuleType("wx")
    wx.Frame = _Frame
    wx.Dialog = _Dialog
    wx.Panel = _Widget
    wx.App = _App
    wx.Notebook = _Notebook
    wx.ListBox = _ListBox
    wx.TextCtrl = _TextCtrl
    wx.StaticText = _StaticText
    wx.RadioBox = _RadioBox
    wx.BoxSizer = _Widget
    wx.Button = _Widget
    wx.Timer = _Timer
    wx.Window = type("Window", (), {"FindFocus": staticmethod(lambda: None)})
    wx.Bell = lambda: None
    wx.MessageBox = lambda *args, **kwargs: None
    # CallAfter runs the call right away here: there is no real event loop.
    wx.CallAfter = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    wx.CallLater = lambda ms, fn, *args, **kwargs: fn(*args, **kwargs)
    wx.ID_OK = 1
    wx.ID_YES = 5103
    wx.ID_NO = 5104
    wx.YES_NO = 2
    wx.ICON_QUESTION = 4
    wx.OK = 1
    wx.CANCEL = 2
    wx.ICON_INFORMATION = 4
    wx.EVT_BUTTON = 6
    wx.WXK_ESCAPE = 27
    wx.WXK_RETURN = 13
    wx.WXK_LEFT = 314
    wx.WXK_RIGHT = 316
    wx.LB_SINGLE = 1
    wx.TE_MULTILINE = 1
    wx.TE_READONLY = 2
    wx.TE_RICH2 = 4
    wx.TE_PASSWORD = 8
    wx.RA_SPECIFY_COLS = 1
    wx.VERTICAL = 1
    wx.HORIZONTAL = 2
    wx.ALL = 1
    wx.EXPAND = 2
    wx.ALIGN_RIGHT = 4
    wx.LEFT = 8
    wx.RIGHT = 16
    wx.EVT_CHAR_HOOK = 1
    wx.EVT_NOTEBOOK_PAGE_CHANGED = 2
    wx.EVT_CLOSE = 3
    wx.EVT_TIMER = 4
    wx.EVT_LISTBOX_DCLICK = 5
    return wx


def _make_pygame():
    pygame = types.ModuleType("pygame")
    pygame.mixer = types.SimpleNamespace(
        init=lambda: None,
        music=_FakeMusic(),
        Sound=_FakeSound,
        Channel=_FakeChannel,
    )
    return pygame


sys.modules["wx"] = _make_wx()
sys.modules["pygame"] = _make_pygame()

import game_logic
import main


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)
    print("ok - " + name)


def wait_for_log(text, timeout=5.0):
    """True once the log capture holds the text (voice work happens
    on a background thread, so log lines arrive a moment later)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if text in LOG_CAPTURE.getvalue():
            return True
        time.sleep(0.05)
    return False


def main_test():
    # Online only in the tests too: the window gets a fake
    # online config, and the "server" is a fake in memory that
    # runs the real rules on its own copy of the fighter, the
    # way the real server does. The window only shows what the
    # server sends back. No network, no password, no token, and
    # no local save file is ever written.
    import copy
    import online_save as _online_save
    fighter = game_logic.new_fighter("Bolt", "robot")
    fighter["credits"] = 500
    fighter["player_code"] = "4242"
    server = {"fighter": copy.deepcopy(fighter), "calls": []}

    def _fake_fight(config, opponent_code=None):
        server["calls"].append("fight")
        result = game_logic.fight(server["fighter"], rng=random.Random(3))
        result["fighter"] = copy.deepcopy(server["fighter"])
        return result, None

    def _fake_fight_npc(config, npc_id):
        server["calls"].append("fight_npc")
        result = game_logic.fight(server["fighter"], rng=random.Random(3),
                                  npc_id=npc_id)
        result["fighter"] = copy.deepcopy(server["fighter"])
        return result, None

    def _fake_upgrade(config, slot):
        server["calls"].append("upgrade")
        error = game_logic.start_upgrade(server["fighter"], slot)
        return copy.deepcopy(server["fighter"]), [], error

    def _fake_spend_stat(config, stat):
        server["calls"].append("spend_stat")
        error, message = game_logic.spend_stat(server["fighter"], stat)
        return copy.deepcopy(server["fighter"]), message, [], error

    def _fake_respec(config):
        server["calls"].append("respec")
        error, message = game_logic.respec_stats(server["fighter"])
        return copy.deepcopy(server["fighter"]), message, [], error

    def _fake_max_upgrade(config, slot):
        server["calls"].append("max_upgrade")
        error, message = game_logic.start_max_upgrade(server["fighter"], slot)
        return copy.deepcopy(server["fighter"]), message, [], error

    def _fake_state(config):
        server["calls"].append("state")
        messages = []
        done = game_logic.finish_upgrade_if_ready(server["fighter"])
        if done:
            messages.append(done)
        if 0 < server["fighter"]["repair_until"] <= time.time():
            server["fighter"]["hp"] = server["fighter"]["max_hp"]
            server["fighter"]["repair_until"] = 0
            messages.append("My repairs are finished. I'm back to full health.")
        return copy.deepcopy(server["fighter"]), messages, None

    def _fake_voice(config, gender):
        server["calls"].append("voice")
        server["fighter"]["gender"] = gender
        return copy.deepcopy(server["fighter"]), None

    _online_save.fight = _fake_fight
    _online_save.fight_npc = _fake_fight_npc
    _online_save.start_upgrade = _fake_upgrade
    _online_save.spend_stat = _fake_spend_stat
    _online_save.respec_stats = _fake_respec
    _online_save.max_upgrade = _fake_max_upgrade
    _online_save.refresh_state = _fake_state
    _online_save.set_voice = _fake_voice
    _online_save.heartbeat = lambda *args, **kwargs: True
    _online_save.sign_out = lambda *args, **kwargs: True
    _online_save.log_action = lambda *args, **kwargs: True
    frame = main.MainFrame(
        fighter,
        online_config={"url": "https://example.supabase.co",
                       "key": "sb_publishable_fake", "session": "a" * 64},
        player_account={"username": "Bolt", "player_code": "4242"},
    )

    check("five tabs exist", main.MainFrame.TAB_NAMES == [
        "Home", "Combat", "Shop", "More", "Settings"])
    for tab in main.MainFrame.TAB_NAMES:
        items = frame.list_items(tab)
        check("list for %s is plain text" % tab,
              bool(items) and all(isinstance(item, str) for item in items))
        check("no list item is empty on %s" % tab,
              all(item.strip() for item in items))
    print("    Home list: %s" % frame.list_items("Home"))

    # Phase 24: fights pick a creature at random. Pin the
    # first fight to Scrap Rat so the checks below are exact.
    _real_random_npc = game_logic.random_npc_id
    game_logic.random_npc_id = lambda rng: "scrap_rat"

    # Enter on "Fight" runs a real fight and saves.
    frame.notebook.SetSelection(1)  # Combat tab
    combat_box = frame.lists["Combat"]
    combat_box.SetSelection(0)
    check("combat first item is the fight",
          combat_box.GetString(0) == "Fight")
    wins_before = fighter["wins"] + fighter["losses"]
    frame.activate_current()
    check("fight item runs a fight", fighter["wins"] + fighter["losses"] == wins_before + 1)
    check("fight was narrated to the log", "Scrap Rat" in frame.logs["Combat"].text)
    check("fight ran on the server", server["calls"].count("fight") == 1)
    check("window shows the server's fighter",
          fighter["wins"] + fighter["losses"]
          == server["fighter"]["wins"] + server["fighter"]["losses"])
    fighter["credits"] = 999999  # a cheat in the game's memory
    server["fighter"]["repair_until"] = 0
    frame.do_fight()
    check("a cheat in memory is wiped by the next server answer",
          fighter["credits"] == server["fighter"]["credits"] != 999999)
    check("no local save file was created",
          not os.path.exists(os.path.join(
              os.path.dirname(os.path.abspath(__file__)), "arena_save.json")))

    # Phase 24: fighting a named creature goes through the
    # NPC fight on the server, with that creature's sounds.
    server["fighter"]["repair_until"] = 0
    fighter["repair_until"] = 0
    server["fighter"]["hp"] = game_logic.fighter_max_hp(server["fighter"])
    fighter["hp"] = game_logic.fighter_max_hp(fighter)
    frame.do_fight(npc_id="zip_scout")
    check("fighting a named creature uses the npc fight",
          "fight_npc" in server["calls"])
    check("the npc fight is narrated to the log",
          "Zip Scout" in frame.logs["Combat"].text)
    game_logic.random_npc_id = _real_random_npc

    # Phase 24 (Makenna, Nov 18, 2026): the button says just
    # "Fight" — no creature name — and pressing it picks a
    # random creature each time, not always Scrap Rat.
    # (Auto-fight picks random creatures too — see the
    # idle-fight check below, Makenna Nov 18, 2026.)
    frame.random.seed(11)
    log_before = len(frame.logs["Combat"].text)
    seen_creatures = set()
    for _ in range(10):
        server["fighter"]["repair_until"] = 0
        fighter["repair_until"] = 0
        server["fighter"]["hp"] = game_logic.fighter_max_hp(
            server["fighter"])
        fighter["hp"] = game_logic.fighter_max_hp(fighter)
        combat_box.SetSelection(0)
        frame.activate_current()
        new_text = frame.logs["Combat"].text[log_before:]
        log_before = len(frame.logs["Combat"].text)
        for name in ["Scrap Rat"] + [npc["name"]
                                     for npc in game_logic.NPCS.values()]:
            if ("A %s appears!" % name) in new_text:
                seen_creatures.add(name)
    check("pressing Fight picks different creatures, "
          "not always scrap rat",
          len(seen_creatures) > 1)
    # Phase 24 follow-up (Makenna, Nov 18, 2026): auto-fight
    # picks a random creature too — repeated idle fights give
    # different creatures, not always Scrap Rat.
    frame.random.seed(23)
    idle_creatures = set()
    log_before = len(frame.logs["Combat"].text)
    for _ in range(10):
        server["fighter"]["repair_until"] = 0
        fighter["repair_until"] = 0
        server["fighter"]["hp"] = game_logic.fighter_max_hp(
            server["fighter"])
        fighter["hp"] = game_logic.fighter_max_hp(fighter)
        frame.do_fight(idle=True)
        new_text = frame.logs["Combat"].text[log_before:]
        log_before = len(frame.logs["Combat"].text)
        for name in ["Scrap Rat"] + [npc["name"]
                                     for npc in game_logic.NPCS.values()]:
            if ("A %s appears!" % name) in new_text:
                idle_creatures.add(name)
    check("auto-fight picks different creatures, "
          "not always scrap rat",
          len(idle_creatures) > 1)

    # Idle fighting toggles on and off.
    frame.toggle_idle()
    check("idle fighting turns on", frame.idle_fighting is True)
    frame.toggle_idle()
    check("idle fighting turns off", frame.idle_fighting is False)

    # Enter on the weapon line starts a real timed upgrade.
    frame.notebook.SetSelection(2)  # Shop tab
    frame.refresh_list("Shop")
    shop_box = frame.lists["Shop"]
    shop_box.SetSelection(0)
    check("shop first item is the weapon upgrade",
          shop_box.GetString(0).startswith("Upgrade Laser Blaster"))
    frame.activate_current()
    check("shop item starts an upgrade", fighter["upgrade"] is not None)
    check("upgrade ran on the server", "upgrade" in server["calls"])
    check("upgrade targets the weapon", fighter["upgrade"]["slot"] == "weapon")

    # The one-second tick finishes the upgrade once its time is up.
    fighter["upgrade"]["finish"] = 0.0  # pretend the wait is over
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame.on_tick(mock.MagicMock())
    check("tick asks the server when an upgrade is due", "state" in server["calls"])
    check("tick finishes a ready upgrade", fighter["upgrade"] is None)
    check("weapon level rose after upgrade", fighter["weapon_level"] == 2)

    # The tick heals the fighter back to full health when repairs end.
    fighter["repair_until"] = time.time() - 10  # repair already over
    server["fighter"]["repair_until"] = fighter["repair_until"]
    frame.was_repairing = True
    fighter["hp"] = 1
    server["fighter"]["hp"] = 1
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("tick heals after repairs finish", fighter["hp"] == fighter["max_hp"])

    # Stats live on the Home tab, in the same list as the
    # fighter status: 5 stat lines, spoken in plain words.
    frame.notebook.SetSelection(0)  # Home tab
    frame.refresh_list("Home")
    home_items = frame.list_items("Home")
    check("home list has the 5 stat lines",
          sum(1 for item in home_items
              if item.split(",")[0] in
              ("Strength", "Defense", "Health", "Speed", "Luck")) == 5)
    check("home list says credits nowhere on stat lines",
          all("points" not in item or "stat point" in item
              for item in home_items))

    # Enter on a stat line spends one banked point on the
    # server, and the spoken line says how many are left.
    # The fake server starts with 0 banked points, so give
    # both copies 8 and spend them all in one stat.
    server["fighter"]["stat_points"] = 8
    fighter["stat_points"] = 8
    frame.refresh_list("Home")
    home_box = frame.lists["Home"]
    home_box.SetSelection(home_items.index(
        [item for item in home_items if item.startswith("Strength,")][0]))
    frame.activate_current()
    check("enter on a stat spends one point on the server",
          "spend_stat" in server["calls"])
    check("one point spent, 7 banked left",
          fighter["stat_points"] == 7 and fighter["stats"]["strength"] == 1)
    # Stay on the same line and press Enter again: the next
    # point goes to the same stat. No forced spreading.
    for _ in range(7):
        frame.activate_current()
    check("all 8 banked points can go into Strength",
          fighter["stats"]["strength"] == 8 and fighter["stat_points"] == 0)
    check("the server's fighter matches after spending",
          server["fighter"]["stats"]["strength"] == 8)

    # Shop shows "credits" and a max-affordable line, and
    # Enter on it starts the queue on the server after the
    # player says yes. The stub's confirm box says no, so
    # the queue must not start here.
    frame.notebook.SetSelection(2)  # Shop tab
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("shop lines say credits, not points",
          any("credits" in item for item in shop_items)
          and not any("points" in item and "stat" not in item
                      for item in shop_items))
    check("shop has a max-affordable line",
          any(item.startswith("Max affordable: Laser Blaster up")
              for item in shop_items))
    shop_box.SetSelection(
        [i for i, item in enumerate(shop_items)
         if item.startswith("Max affordable: Laser Blaster up")][0])
    credits_before = fighter["credits"]
    frame.activate_current()
    check("max affordable asks first and does not start on no",
          "max_upgrade" not in server["calls"])
    check("saying no leaves the credits alone",
          fighter["credits"] == credits_before)

    # The same question answered yes must start the queue:
    # Enter on Yes was once heard as No, and the game said
    # "Nothing was bought" (2026-11-18). The dialog answers
    # yes here, and the queue starts on the server.
    sys.modules["wx"].Dialog.modal_result = sys.modules["wx"].ID_YES
    check("yes means yes in the confirm dialog",
          frame._confirm("Buy it?") is True)
    sys.modules["wx"].Dialog.modal_result = sys.modules["wx"].ID_NO
    check("no means no in the confirm dialog",
          frame._confirm("Buy it?") is False)
    sys.modules["wx"].Dialog.modal_result = sys.modules["wx"].ID_YES
    frame.activate_current()
    sys.modules["wx"].Dialog.modal_result = 1  # back to ID_OK
    check("max affordable starts the queue on yes",
          "max_upgrade" in server["calls"])
    check("the queue is running after yes",
          fighter.get("upgrade") is not None)
    check("the credits were spent after yes",
          fighter["credits"] < credits_before)

    # One upgrade set at a time (Phase 24, Makenna's rule):
    # while the weapon queue runs, no other set can start —
    # single or max-affordable, the other slot or the same
    # slot — and the player is told how long is left.
    check("the running set is the weapon queue",
          fighter["upgrade"]["slot"] == "weapon")
    frame.do_upgrade("armor")
    check("armor upgrade is blocked while the weapon queue runs",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "weapon")
    check("the armor block is spoken with the time left",
          "already got an upgrade running" in frame.message_line.GetLabel()
          and "left" in frame.message_line.GetLabel())
    frame.do_upgrade("weapon")
    check("another weapon upgrade is blocked while its queue runs",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "weapon")
    max_calls = server["calls"].count("max_upgrade")
    frame.do_max_upgrade("armor")
    check("max affordable is blocked while a queue runs",
          server["calls"].count("max_upgrade") == max_calls)
    check("the max block is spoken with the time left",
          "already got an upgrade running" in frame.message_line.GetLabel()
          and "left" in frame.message_line.GetLabel())
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("shop shows the running set with its time left",
          shop_items[0].startswith("I'm upgrading my Laser Blaster")
          and "left" in shop_items[0])
    check("shop says the other slot waits for the running set",
          any("waits until the running upgrade finishes" in item
              for item in shop_items))
    check("no max-affordable line while a set runs",
          not any(item.startswith("Max affordable:")
                  for item in shop_items))
    # Drain the queue one level at a time, then a new set
    # CAN start — the rule is a wait, not a lock.
    for _ in range(10):
        if fighter.get("upgrade") is None:
            break
        fighter["upgrade"]["finish"] = 0.0
        server["fighter"]["upgrade"]["finish"] = 0.0
        frame._last_timer_check = 0
        frame.on_tick(mock.MagicMock())
    check("the queue drains to the end",
          fighter.get("upgrade") is None)
    # The max queue spends everything the fighter can afford,
    # and the extra fights before the Shop earned more credits,
    # so the queue bought more levels and left too few credits
    # for even one armor level. Top both copies up: the point
    # here is the one-set-at-a-time rule, not the wallet.
    fighter["credits"] = 100
    server["fighter"]["credits"] = 100
    frame.do_upgrade("armor")
    check("a new set can start once the first set finishes",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "armor")
    fighter["upgrade"]["finish"] = 0.0
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("the new set finishes too",
          fighter.get("upgrade") is None)

    # Healing skill (Phase 25, Makenna Nov 18, 2026): a third
    # Shop slot, bought like weapon and armor, max level 5,
    # with its own cost and time. It is called Second Wind —
    # a name that fits a robot and a chef.
    fighter["credits"] = 500
    server["fighter"]["credits"] = 500
    frame.notebook.SetSelection(2)  # Shop tab
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("shop shows Second Wind with its cost",
          any(item == "Upgrade Second Wind to level 1, costs 50 credits (press H)"
              for item in shop_items))
    check("shop shows max affordable Second Wind with its time",
          any(item.startswith("Max affordable: Second Wind up")
              and "done in" in item for item in shop_items))
    check("home status says the Second Wind level",
          "Second Wind level 0" in game_logic.status_text(fighter))

    # Enter on the Second Wind line starts the upgrade on
    # the server, and the tick finishes it like any upgrade.
    frame.notebook.SetSelection(2)  # Shop tab
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    shop_box.SetSelection(
        [i for i, item in enumerate(shop_items)
         if item.startswith("Upgrade Second Wind")][0])
    frame.activate_current()
    check("second wind starts an upgrade", fighter["upgrade"] is not None)
    check("second wind ran on the server", "upgrade" in server["calls"])
    check("second wind targets healing", fighter["upgrade"]["slot"] == "healing")
    fighter["upgrade"]["finish"] = 0.0
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("second wind finishes at level 1", fighter["healing_level"] == 1)

    # One upgrade set at a time (Phase 24) covers Healing
    # both ways: a Second Wind set blocks weapon and armor,
    # and a weapon set blocks Second Wind.
    frame.do_upgrade("healing")
    check("a second wind set is running",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "healing")
    frame.do_upgrade("weapon")
    check("weapon is blocked while a second wind set runs",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "healing")
    check("the weapon block is spoken with the time left",
          "already got an upgrade running" in frame.message_line.GetLabel()
          and "left" in frame.message_line.GetLabel())
    max_calls = server["calls"].count("max_upgrade")
    frame.do_max_upgrade("armor")
    check("max armor is blocked while a second wind set runs",
          server["calls"].count("max_upgrade") == max_calls)
    fighter["upgrade"]["finish"] = 0.0
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("second wind finishes at level 2", fighter["healing_level"] == 2)
    fighter["credits"] = 1000  # the weapon is level 7 by now,
    server["fighter"]["credits"] = 1000  # so its next level costs 427
    frame.do_upgrade("weapon")
    check("a weapon set is running",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "weapon")
    frame.do_upgrade("healing")
    check("second wind is blocked while a weapon set runs",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "weapon")
    fighter["upgrade"]["finish"] = 0.0
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("the weapon set finishes too",
          fighter.get("upgrade") is None)

    # Max affordable Second Wind: with 365 credits left,
    # level 3 (140) fits and level 4 (240) does not, so the
    # queue buys one level. Saying yes starts it.
    fighter["credits"] = 365
    server["fighter"]["credits"] = 365
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("max affordable second wind buys one level here",
          any(item.startswith("Max affordable: Second Wind up 1 level")
              and "140 credits" in item for item in shop_items))
    sys.modules["wx"].Dialog.modal_result = sys.modules["wx"].ID_YES
    shop_box.SetSelection(
        [i for i, item in enumerate(shop_items)
         if item.startswith("Max affordable: Second Wind")][0])
    frame.activate_current()
    sys.modules["wx"].Dialog.modal_result = 1  # back to ID_OK
    check("max second wind starts the queue on yes",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "healing")
    for _ in range(10):
        if fighter.get("upgrade") is None:
            break
        fighter["upgrade"]["finish"] = 0.0
        server["fighter"]["upgrade"]["finish"] = 0.0
        frame._last_timer_check = 0
        frame.on_tick(mock.MagicMock())
    check("max second wind queue drains to level 3",
          fighter["healing_level"] == 3)

    # Level 5 is the cap: at level 5 the Shop says so, and
    # buying or max-buying is refused in plain words.
    server["fighter"]["healing_level"] = 5
    fighter["healing_level"] = 5
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("shop says second wind is at its best at level 5",
          any(item == "Second Wind is at its best, level 5."
              for item in shop_items))
    check("no second wind buy line at level 5",
          not any(item.startswith("Upgrade Second Wind")
                  for item in shop_items))
    check("no max second wind line at level 5",
          not any(item.startswith("Max affordable: Second Wind")
                  for item in shop_items))
    frame.do_upgrade("healing")
    check("buying past level 5 is refused",
          "at its best" in frame.message_line.GetLabel())
    frame.do_max_upgrade("healing")
    check("max buying past level 5 is refused",
          "at its best" in frame.message_line.GetLabel())

    # Level 5 auto-heal (Phase 25): at full Healing the
    # fighter comes back to full health after a fight, win
    # or loss, and no repair ever starts.
    server["fighter"]["hp"] = 10
    fighter["hp"] = 10
    server["fighter"]["repair_until"] = 0
    fighter["repair_until"] = 0
    log_before = len(frame.logs["Combat"].text)
    frame.do_fight()
    check("level 5 auto-heal restores full health after a fight",
          fighter["hp"] == fighter["max_hp"])
    check("level 5 auto-heal starts no repair",
          fighter["repair_until"] == 0)
    check("level 5 auto-heal is narrated",
          "Second Wind" in frame.logs["Combat"].text[log_before:])
    server["fighter"]["healing_level"] = 3
    fighter["healing_level"] = 3

    # Hotfix Phase 25b (Makenna Nov 18, 2026): a fighter made
    # before Phase 18 has no healing_level key at all, and the
    # game used to crash on launch — refresh_all builds every
    # tab including the Shop. Missing means level 0: the Shop
    # offers Second Wind level 1 for 50 credits, buying and
    # max-buying work, and the key appears once level 1 lands.
    fighter.pop("healing_level", None)
    server["fighter"].pop("healing_level", None)
    check("a pre-Phase-18 fighter has no healing_level key",
          "healing_level" not in fighter)
    frame.refresh_all()  # the startup path that used to crash
    frame.notebook.SetSelection(2)  # Shop tab
    frame.refresh_list("Shop")
    shop_items = frame.list_items("Shop")
    check("shop shows Second Wind level 1 at 50 credits without the key",
          any(item == "Upgrade Second Wind to level 1, costs 50 credits (press H)"
              for item in shop_items))
    check("shop shows a max affordable Second Wind line without the key",
          any(item.startswith("Max affordable: Second Wind")
              for item in shop_items))
    check("home status says Second Wind level 0 without the key",
          "Second Wind level 0" in game_logic.status_text(fighter))
    frame.do_upgrade("healing")
    check("second wind starts from a missing level",
          fighter.get("upgrade") is not None
          and fighter["upgrade"]["slot"] == "healing")
    fighter["upgrade"]["finish"] = 0.0
    server["fighter"]["upgrade"]["finish"] = 0.0
    frame._last_timer_check = 0
    frame.on_tick(mock.MagicMock())
    check("second wind finishes at level 1 from a missing level",
          fighter.get("healing_level") == 1)
    # Restore the level the later tests expect.
    server["fighter"]["healing_level"] = 3
    fighter["healing_level"] = 3

    # Music rule (2026-11-18, quests Phase 18): no music
    # at launch, hangout music only once quests have
    # started in the hangout, fight music only while
    # auto-fighting, and nothing for a manual fight.
    check("no music starts at launch",
          frame.sounds.current_music_track is None)
    frame.notebook.SetSelection(3)  # More tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    frame.refresh_list("More")
    more_box = frame.lists["More"]
    more_box.SetSelection(frame.list_items("More").index("Visit the hangout"))
    frame.activate_current()
    check("entering the hangout alone starts no music",
          frame.sounds.current_music_track is None)
    check("arriving in the hangout says to press Start",
          frame.message_line.GetLabel().startswith(
              "You are in the hangout. Press Start"))
    frame.notebook.SetSelection(0)  # Home tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    check("leaving the hangout stops the music",
          frame.sounds.current_music_track is None)
    frame.toggle_idle()
    check("auto-fighting starts the fight music",
          frame.sounds.current_music_track == "fight")
    frame.toggle_idle()
    check("stopping auto-fighting stops the music",
          frame.sounds.current_music_track is None)
    frame.do_fight()
    check("a manual fight plays no music",
          frame.sounds.current_music_track is None)

    # Music respects the game state (2026-11-18, Makenna):
    # it plays continuously across a whole auto-fight session
    # — never stopping and restarting between fights — and
    # stops only when the session ends.
    frame.toggle_idle()
    check("auto-fighting starts the fight music again",
          frame.sounds.current_music_track == "fight")
    frame.do_fight(idle=True)
    check("a won idle fight keeps the music playing",
          frame.sounds.current_music_track == "fight")
    frame.on_key(types.SimpleNamespace(
        GetKeyCode=lambda: sys.modules["wx"].WXK_ESCAPE))
    check("Escape stops auto-fighting",
          frame.idle_fighting is False)
    check("Escape stops the fight music too",
          frame.sounds.current_music_track is None)
    frame.toggle_idle()
    _online_save.fight = lambda *args, **kwargs: (None, "test: server down")
    _online_save.fight_npc = lambda *args, **kwargs: (None, "test: server down")
    frame.do_fight(idle=True)
    check("a failed idle fight turns auto-fighting off",
          frame.idle_fighting is False)
    check("a failed idle fight stops the music",
          frame.sounds.current_music_track is None)
    _online_save.fight = _fake_fight
    _online_save.fight_npc = _fake_fight_npc
    frame.toggle_idle()
    check("auto-fighting starts the fight music a third time",
          frame.sounds.current_music_track == "fight")
    # A lost fight starts repairs: the next tick ends
    # auto-fighting, and its music must stop with it. (This
    # was the bug: the music kept playing after a loss, even
    # though auto-fight was off and repairs were running.)
    server["fighter"]["repair_until"] = time.time() + 600
    frame._cancel_narration()
    sys.modules["pygame"].mixer.music.finish()
    frame.on_tick(mock.MagicMock())
    check("repairs stop auto-fighting", frame.idle_fighting is False)
    check("music stops when repairs stop auto-fighting",
          frame.sounds.current_music_track is None)

    # The fighter-creation dialog returns kind, name and gender.
    dialog = main.CreateFighterDialog(None)
    dialog.name_ctrl.text = "Ember"
    check("dialog returns kind, name and gender",
          dialog.get_result() == ("robot", "Ember", "male"))
    dialog.gender_box.GetSelection = lambda: 1
    check("dialog returns female when picked",
          dialog.get_result() == ("robot", "Ember", "female"))
    dialog.kind_box.GetSelection = lambda: 1
    check("dialog returns chef when picked",
          dialog.get_result() == ("chef", "Ember", "female"))
    dialog.name_ctrl.text = "   "
    check("dialog returns nothing without a name",
          dialog.get_result() is None)

    # No voice here (edge-tts is not installed on this machine): the
    # game must carry on with text only and never ring a bell.
    check("voice is off without edge-tts", frame.voice is None)
    check("startup log names the Python running the game",
          "Voice startup: Python" in LOG_CAPTURE.getvalue())
    check("startup log says edge-tts is missing",
          "edge-tts not installed" in LOG_CAPTURE.getvalue())
    frame.announce("A quiet line.")
    check("announce still shows text without a voice",
          frame.message_line.GetLabel() == "A quiet line.")
    source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "main.py"), encoding="utf-8").read()
    check("no bell left in main.py",
          "wx.Bell" not in source and ".Bell(" not in source)
    check("no tone method left in main.py", "def tone" not in source)
    check("no local save file in main.py", "arena_save.json" not in source)
    check("no local save function in main.py", "save_game" not in source)

    # Settings: Enter on the Voice item switches the voice and saves it.
    frame.notebook.SetSelection(4)  # Settings tab
    frame.refresh_list("Settings")
    settings_box = frame.lists["Settings"]
    check("settings first item is the voice",
          settings_box.GetString(0).startswith("Voice: Male"))
    settings_box.SetSelection(0)
    frame.activate_current()
    check("voice item switches to female", fighter["gender"] == "female")
    check("voice item saves the switch on the server",
          server["fighter"]["gender"] == "female")
    check("settings now shows female",
          frame.list_items("Settings")[0].startswith("Voice: Female"))
    frame.activate_current()
    check("voice item switches back to male", fighter["gender"] == "male")

    # Settings: keep me signed in turns on and off, through the
    # server and a stand-in password store.
    import account as _account
    import remember as _remember
    store = {}
    _remember.keyring = types.SimpleNamespace(
        get_password=lambda s, n: store.get(n),
        set_password=lambda s, n, v: store.__setitem__(n, v),
        delete_password=lambda s, n: store.pop(n),
    )
    forgotten = []
    _account.remember_this_computer = lambda config: ("e" * 64, None)
    _account.forget_this_computer = lambda config, token: forgotten.append(token) or True
    frame.refresh_list("Settings")
    items = frame.list_items("Settings")
    keep_index = [i for i, item in enumerate(items)
                  if item.startswith("Keep me signed in")][0]
    check("keep me signed in starts off", items[keep_index].endswith(": off"))
    settings_box.SetSelection(keep_index)
    frame.activate_current()
    check("keep me signed in turns on", frame.remembered is True)
    check("the token went to the password store", list(store.values()) == ["e" * 64])
    frame.activate_current()
    check("keep me signed in turns off", frame.remembered is False)
    check("turning it off removes the token here", store == {})
    check("turning it off tells the server", forgotten == ["e" * 64])

    check("still no local save file at the end",
          not os.path.exists(os.path.join(
              os.path.dirname(os.path.abspath(__file__)), "arena_save.json")))
    print("\nAll window smoke tests passed.")
    print("NOTE: NVDA focus order, real screen-reader behaviour, and how")
    print("the window looks on Windows still need a live test by Joshua/McKenna.")


def _make_fake_edge_tts():
    """A stand-in edge-tts that writes a small file instead of calling
    the real voice service."""

    class _FakeCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, path):
            with open(path, "wb") as handle:
                handle.write(("fake-mp3:" + self.text).encode("utf-8"))

    module = types.ModuleType("edge_tts")
    module.Communicate = _FakeCommunicate
    return module


def voice_test():
    """With a stubbed edge-tts, a spoken line reaches the player,
    and a newer line replaces an older one still waiting."""
    import importlib
    import voice_engine

    sys.modules["edge_tts"] = _make_fake_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)

    fighter = game_logic.new_fighter("Piper", "chef", "female")
    frame = main.MainFrame(fighter)
    check("voice is on with edge-tts present", frame.voice is not None)
    check("startup log says edge-tts is installed",
          "edge-tts installed" in LOG_CAPTURE.getvalue())
    check("startup log names the female voice",
          "voice en-US-AriaNeural" in LOG_CAPTURE.getvalue())
    check("female fighter gets the female voice",
          frame.voice.voice == voice_engine.FEMALE_VOICE)
    media = sys.modules["pygame"].mixer.music

    def last_spoken():
        try:
            with open(media.loaded[-1], "rb") as handle:
                return handle.read()
        except (IndexError, OSError):
            return b""

    # The welcome line is still sounding in the fake player: wait
    # for it to reach the player, then let it finish, since a new
    # line now waits behind a line already speaking instead of
    # cutting it off.
    check("the welcome line reaches the player first",
          _wait_spoken(frame, "Welcome to Arena of Makers, Piper."))
    media.finish()
    # Tab switching is silent (2026-11-18, Makenna): NVDA
    # already announces the tab and its list, so Edge must
    # not speak the tab hint over it. Switching through
    # every tab must speak nothing and queue nothing, while
    # still showing the hint as text.
    spoken_before = len(media.loaded)
    for _tab in (1, 2, 3, 4, 0):
        frame.notebook.SetSelection(_tab)
        frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    time.sleep(0.5)
    check("switching tabs speaks nothing",
          len(media.loaded) == spoken_before)
    check("switching tabs queues no narration",
          frame._narration_queue == [])
    check("switching tabs still shows the tab hint as text",
          frame.message_line.GetLabel() == main.MainFrame.TAB_HINTS["Home"])
    # "Go to X" changes tabs through the same handler,
    # so it must be silent too.
    frame.notebook.SetSelection(0)
    frame.refresh_list("Home")
    home_box = frame.lists["Home"]
    home_box.SetSelection(frame.list_items("Home").index("Go to Combat"))
    frame.activate_current()
    # The fake notebook does not fire the tab-changed event
    # on its own, so call the handler the way the other
    # tab tests do — in the real game wx fires it.
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    time.sleep(0.3)
    check("Go to Combat speaks nothing",
          len(media.loaded) == spoken_before)
    check("Go to Combat still changes tab",
          frame.current_tab() == "Combat")
    frame.announce("Hello, fighter.")
    deadline = time.time() + 5
    heard = False
    while time.time() < deadline:
        time.sleep(0.05)
        if last_spoken() == b"fake-mp3:Hello, fighter.":
            heard = True
            break
    check("a spoken line reaches the player", heard)
    check("the player actually played it", media.played >= 1)
    check("mixer busy check is logged",
          wait_for_log("Voice: mixer is playing."))
    check("speak attempt is logged with voice and preview",
          'Voice: speaking "Hello, fighter." with en-US-AriaNeural'
          in LOG_CAPTURE.getvalue())
    check("synthesis is logged with file size",
          wait_for_log('Voice: made "Hello, fighter." with en-US-AriaNeural ('))
    check("playback start is logged",
          wait_for_log("Voice: playing voice file ("))

    # A newer line replaces an older one still waiting.
    frame.voice.speak("old line")
    frame.voice.speak("new line")
    deadline = time.time() + 5
    while time.time() < deadline:
        time.sleep(0.05)
        if frame.voice._queue.empty():
            break
    time.sleep(1.0)
    check("only the newest line is spoken",
          last_spoken() == b"fake-mp3:new line")

    # Switching voice in Settings changes the engine voice too.
    frame.notebook.SetSelection(4)
    frame.refresh_list("Settings")
    frame.lists["Settings"].SetSelection(0)
    frame.activate_current()
    check("settings switch changes the voice",
          frame.voice.voice == voice_engine.MALE_VOICE)

    frame.on_close(mock.MagicMock())
    check("voice files are cleaned up on close",
          not os.path.exists(media.loaded[-1]))
    print("\nAll voice smoke tests passed.")


def _make_failing_edge_tts():
    """A stand-in edge-tts whose voice service always fails."""

    class _FailingCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, path):
            raise ConnectionError("test: no network")

    module = types.ModuleType("edge_tts")
    module.Communicate = _FailingCommunicate
    return module


def voice_failure_test():
    """With a voice service that always fails, the failure is logged
    in plain words naming the voice, the line is retried once, and
    the engine stays alive: one failed line never kills the voice
    for the whole session (Phase 27, Makenna 2026-11-18). Later
    lines are tried again instead of being silently dropped."""
    import importlib
    import voice_engine

    sys.modules["edge_tts"] = _make_failing_edge_tts()
    importlib.reload(voice_engine)

    voice = voice_engine.EdgeVoice(voice_engine.FEMALE_VOICE, lambda path: None)
    check("failing voice still starts its thread", voice.start() is True)
    voice.speak("This line will fail.")
    check("failed synthesis is logged in plain words naming the voice",
          wait_for_log("the voice service failed for voice "
                       "en-US-AriaNeural (ConnectionError: test: no network)"))
    check("a transient failure is retried once",
          wait_for_log("Voice en-US-AriaNeural failed once "
                       "(ConnectionError: test: no network); trying once more."))
    check("engine is still available after a transient failure",
          voice.available is True)
    failures_before = LOG_CAPTURE.getvalue().count(
        "the voice service failed for voice")
    voice.speak("Another line.")
    deadline = time.time() + 5
    tried_again = False
    while time.time() < deadline:
        time.sleep(0.05)
        if LOG_CAPTURE.getvalue().count(
                "the voice service failed for voice") > failures_before:
            tried_again = True
            break
    check("a later line is tried again after a failure", tried_again)
    check("engine is still available after the second failure",
          voice.available is True)
    voice.stop()
    check("voice thread shutdown is logged",
          "Voice thread stopped." in LOG_CAPTURE.getvalue())
    print("\nAll voice failure tests passed.")


def voice_playback_failure_test():
    """With a player that cannot load the file, the failure is logged
    in plain words instead of silence."""
    import importlib
    import voice_engine

    sys.modules["edge_tts"] = _make_fake_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)
    sys.modules["pygame"].mixer.music.fail_load = True

    fighter = game_logic.new_fighter("Rusty", "robot", "male")
    frame = main.MainFrame(fighter)
    check("voice is on even when playback fails", frame.voice is not None)
    check("failed playback is logged in plain words",
          wait_for_log("the voice file could not be played"))
    frame.on_close(mock.MagicMock())
    print("\nAll voice playback failure tests passed.")


def _make_dead_voice_edge_tts():
    """A stand-in edge-tts where the two retired voices (Davis,
    Sara) always fail with NoAudioReceived, and every other voice
    works. Counts every synthesis attempt per voice, so a test
    can tell whether a dead voice was retried."""

    class NoAudioReceived(Exception):
        pass

    class _DeadVoiceCommunicate:
        attempts = {}

        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, path):
            _DeadVoiceCommunicate.attempts[self.voice] = \
                _DeadVoiceCommunicate.attempts.get(self.voice, 0) + 1
            if self.voice in ("en-US-DavisNeural", "en-US-SaraNeural"):
                raise NoAudioReceived(
                    "No audio was received. Please verify that your "
                    "parameters are correct.")
            with open(path, "wb") as handle:
                handle.write(("fake-mp3:" + self.text).encode("utf-8"))

    module = types.ModuleType("edge_tts")
    module.Communicate = _DeadVoiceCommunicate
    return module


def phase27_voice_test():
    """Dead giver voices (Makenna Nov 18, 2026, Phase 27): Gus
    and Belle get working voices, a line in a dead voice falls
    back to the player's voice instead of silencing the game,
    and a failed line never leaves the narration stuck waiting
    — the next line, and the 5-minute quest progress update,
    still speak."""
    import copy
    import importlib
    import quests as quests_module
    import online_save as _online_save
    import voice_engine

    # 1. The giver table: Gus and Belle have working voices now,
    #    and nobody else changed.
    check("Gus speaks with Andrew now",
          quests_module.GIVER_BY_NAME["Gus"]["voice"] == "en-US-AndrewNeural")
    check("Belle speaks with Emma now",
          quests_module.GIVER_BY_NAME["Belle"]["voice"] == "en-US-EmmaNeural")
    check("Bolt, Marge, Pip and Dot keep their voices",
          quests_module.GIVER_BY_NAME["Bolt"]["voice"]
          == "en-US-ChristopherNeural"
          and quests_module.GIVER_BY_NAME["Marge"]["voice"]
          == "en-US-JennyNeural"
          and quests_module.GIVER_BY_NAME["Pip"]["voice"]
          == "en-US-EricNeural"
          and quests_module.GIVER_BY_NAME["Dot"]["voice"]
          == "en-US-MichelleNeural")
    check("the dead Davis and Sara voices are gone from the giver table",
          all(giver["voice"] not in ("en-US-DavisNeural", "en-US-SaraNeural")
              for giver in quests_module.GIVERS))
    check("the player voices are unchanged",
          voice_engine.MALE_VOICE == "en-US-GuyNeural"
          and voice_engine.FEMALE_VOICE == "en-US-AriaNeural")

    # 2. A line in a dead voice falls back to the player's voice.
    sys.modules["edge_tts"] = _make_dead_voice_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)
    media = sys.modules["pygame"].mixer.music
    media.fail_load = False

    def _drain(frame):
        while frame._narration_queue:
            _finish_line_and_advance(frame)
        media.finish()

    def _spoken(frame, text, timeout=8.0, after=0):
        """True once the voice log shows this line being spoken.
        Advances the one-second timer while waiting, like the
        real game does — a line queued behind one still
        speaking only sounds once the timer advances it. `after`
        is a log position to look past, so a line an earlier
        test already spoke cannot pass this check."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if ('Voice: speaking "' + text) in LOG_CAPTURE.getvalue()[after:]:
                return True
            _finish_line_and_advance(frame)
        return ('Voice: speaking "' + text) in LOG_CAPTURE.getvalue()[after:]

    fighter = game_logic.new_fighter("Katprincess", "robot", "male")
    fighter["credits"] = 100
    fighter["player_code"] = "2169"
    frame = main.MainFrame(fighter)
    check("voice is on for the Phase 27 test", frame.voice is not None)
    check("welcome line speaks first",
          _wait_spoken(frame, "Welcome to Arena of Makers, Katprincess."))
    _drain(frame)
    frame.announce_as("Gus asks: fetch the scrap.", "en-US-DavisNeural")
    check("a dead-voice line is still spoken, in the fallback voice",
          _wait_spoken(frame, "Gus asks: fetch the scrap."))
    check("the dead voice is logged by name",
          wait_for_log("Voice en-US-DavisNeural is not available "
                       "from the voice service"))
    check("the fallback line was made with the player's voice",
          wait_for_log('Voice: made "Gus asks: fetch the scrap." '
                       "with en-US-GuyNeural"))
    check("the dead voice was tried only once",
          sys.modules["edge_tts"].Communicate.attempts.get(
              "en-US-DavisNeural", 0) == 1)
    check("the engine stays available after a dead voice",
          frame.voice.available is True)
    _finish_line_and_advance(frame)
    frame.announce_as("Gus asks: fetch another scrap.", "en-US-DavisNeural")
    check("a second dead-voice line falls back too",
          _wait_spoken(frame, "Gus asks: fetch another scrap."))
    check("the dead voice is not retried",
          sys.modules["edge_tts"].Communicate.attempts.get(
              "en-US-DavisNeural", 0) == 1)
    _drain(frame)

    # 3. A Gus quest starts in Andrew's voice, a Belle quest in
    #    Emma's voice, and the 5-minute progress update speaks.
    board = [
        {"id": "q-gus", "name": "Rescue the Burnt Dish",
         "difficulty": "Medium", "giver": "Gus",
         "giver_voice": "en-US-AndrewNeural", "ambience": "cooking",
         "description": "A pan was left on too long. Save dinner "
                        "before the smoke alarm goes off.",
         "duration_minutes": 30},
        {"id": "q-belle", "name": "Perfect the Recipe",
         "difficulty": "Medium", "giver": "Belle",
         "giver_voice": "en-US-EmmaNeural", "ambience": "cooking",
         "description": "A cake keeps coming out flat. Taste it and "
                        "tell the baker what it needs.",
         "duration_minutes": 30},
    ]

    def _fake_start_quest(config, quest_id):
        quest = next((q for q in board if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        started = dict(quest)
        started["started_at"] = time.time()
        started["finish_at"] = (started["started_at"]
                                + started["duration_minutes"] * 60)
        return {"fighter": copy.deepcopy(fighter),
                "quest": started}, None

    _online_save.start_quest = _fake_start_quest
    frame._quests_active = True
    frame._quest_board = list(board)
    log_before = LOG_CAPTURE.getvalue()
    frame._begin_quest(board[0])
    check("a Gus quest speaks in Andrew's voice",
          # The voice log keeps a 40-character preview, so
          # the match has to fit inside it.
          _spoken(frame, "Gus asks: Katprincess, my grill could",
                  after=len(log_before)))
    # The "speaking" log appears at once, but the worker logs
    # "made" a moment later — wait for it in the new log
    # before checking which voice made it.
    deadline = time.time() + 5
    new_log = ""
    while time.time() < deadline:
        time.sleep(0.05)
        new_log = LOG_CAPTURE.getvalue()[len(log_before):]
        if 'Voice: made "Gus asks: Katprincess, my grill could' \
                in new_log:
            break
    check("the Gus quest line was made with Andrew",
          'Voice: made "Gus asks: Katprincess, my grill could' in new_log
          and "with en-US-AndrewNeural" in new_log)
    _drain(frame)
    frame._quest_current["finish_at"] = time.time() + 600
    frame._quest_last_progress_at = time.time() - 301
    log_before = LOG_CAPTURE.getvalue()
    frame.on_tick(mock.MagicMock())
    check("a quest progress update still speaks",
          _spoken(frame, "You're about ", after=len(log_before)))
    _drain(frame)
    log_before = LOG_CAPTURE.getvalue()
    frame._begin_quest(board[1])
    check("a Belle quest speaks in Emma's voice",
          # 40-character voice-log preview, as above.
          _spoken(frame, "Belle asks: Katprincess, oh, thank you",
                  after=len(log_before)))
    deadline = time.time() + 5
    new_log = ""
    while time.time() < deadline:
        time.sleep(0.05)
        new_log = LOG_CAPTURE.getvalue()[len(log_before):]
        if 'Voice: made "Belle asks: Katprincess, oh, thank you' \
                in new_log:
            break
    check("the Belle quest line was made with Emma",
          'Voice: made "Belle asks: Katprincess, oh, thank you' in new_log
          and "with en-US-EmmaNeural" in new_log)
    _drain(frame)
    frame.on_close(mock.MagicMock())

    # 4. When every voice fails, the failed line does not leave
    #    the narration stuck waiting — the next line is still
    #    attempted, not queued forever.
    sys.modules["edge_tts"] = _make_failing_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)
    sys.modules["pygame"].mixer.music.fail_load = False
    dead_frame = main.MainFrame(
        game_logic.new_fighter("Rusty", "robot", "male"))
    check("voice is on even when the service always fails",
          dead_frame.voice is not None)
    check("the welcome line fails and names the voice",
          wait_for_log("the voice service failed for voice "
                       "en-US-GuyNeural (ConnectionError: test: no network)"))
    time.sleep(0.5)
    dead_frame.announce_as("Gus asks: fetch the scrap.",
                           "en-US-AndrewNeural")
    check("a failed quest line is logged naming the voice",
          wait_for_log("the voice service failed for voice "
                       "en-US-AndrewNeural (ConnectionError: test: no network)"))
    time.sleep(0.5)
    check("a failed line does not leave the narration waiting",
          dead_frame._narration_waiting is False)
    check("a failed line does not leave the narration busy",
          dead_frame._narration_busy() is False)
    check("the engine stays available after a total failure",
          dead_frame.voice.available is True)
    dead_frame.announce("A later line still speaks.")
    check("a later line is attempted, not queued forever",
          wait_for_log('Voice: speaking "A later line still speaks.'))
    check("the later line is not stuck in the queue",
          dead_frame._narration_queue == [])
    dead_frame.on_close(mock.MagicMock())
    print("\nAll Phase 27 voice tests passed.")


def _wait_spoken(frame, text, timeout=5.0):
    """True once the fake player has played a file for this text."""
    media = sys.modules["pygame"].mixer.music
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.05)
        if media.loaded:
            try:
                with open(media.loaded[-1], "rb") as handle:
                    if handle.read() == ("fake-mp3:" + text).encode("utf-8"):
                        return True
            except (IndexError, OSError):
                pass
    return False


def _finish_line_and_advance(frame):
    """Pretend the spoken line finished, wait out the pause, and
    let the one-second timer speak the next narration line."""
    media = sys.modules["pygame"].mixer.music
    media.finish()
    frame.on_tick(mock.MagicMock())  # marks the line finished, starts the pause
    time.sleep(1.0)
    frame.on_tick(mock.MagicMock())  # pause is over, next line speaks


def currency_wording_test():
    """Currency is always spoken as "credits", never "points".
    "Stat points" is a different, correct term and stays, as
    does "one more point" on a stat line. Checks the real
    spoken lines from game_logic, the window's lists and the
    "no stat points" announce, and the server's spoken lines
    in the migrations: the newest apply_timers replaces the
    baseline's one rename line that still said "points"."""
    import copy
    import re

    def _bare_points(line):
        """True when a line says "point(s)" about anything but stats."""
        cleaned = re.sub(r"stat points?", "", line, flags=re.IGNORECASE)
        cleaned = re.sub(r"one (more )?point", "", cleaned, flags=re.IGNORECASE)
        return "point" in cleaned.lower()

    spoken = []
    # Fight lines: a win (seed 0), a loss (a fighter on 1 HP
    # loses on seed 0), and a win that levels the fighter up.
    trial = copy.deepcopy(game_logic.new_fighter("Bolt", "robot"))
    spoken += game_logic.fight(trial, rng=random.Random(0))["lines"]
    trial = copy.deepcopy(game_logic.new_fighter("Bolt", "robot"))
    trial["hp"] = 1
    trial["credits"] = 50
    spoken += game_logic.fight(trial, rng=random.Random(0))["lines"]
    trial = copy.deepcopy(game_logic.new_fighter("Bolt", "robot"))
    trial["xp"] = game_logic.xp_to_next_level(1) - 1
    spoken += game_logic.fight(trial, rng=random.Random(0))["lines"]
    # Stat spending, respec, upgrades and the status line.
    banker = game_logic.new_fighter("Bolt", "robot")
    banker["stat_points"] = 2
    _error, line = game_logic.spend_stat(banker, "strength")
    spoken.append(line)
    _error, line = game_logic.spend_stat(banker, "strength")
    spoken.append(line)
    _error, line = game_logic.respec_stats(banker)
    spoken.append(line)
    poor = game_logic.new_fighter("Bolt", "robot")
    poor["credits"] = 0
    spoken.append(game_logic.start_upgrade(poor, "weapon"))
    rich = game_logic.new_fighter("Bolt", "robot")
    rich["credits"] = 100000
    _error, line = game_logic.start_max_upgrade(rich, "weapon")
    spoken.append(line)
    spoken.append(game_logic.status_text(rich))
    for stat in game_logic.STAT_NAMES:
        spoken.append(game_logic.stat_line(rich, stat))
    check("fight and upgrade lines were collected", len(spoken) >= 10)
    check("no spoken line says points for the currency",
          not any(_bare_points(line) for line in spoken))
    check("the win line says credits",
          any("earned" in line and "credits" in line for line in spoken))
    check("the loss line says credits",
          any(line.startswith("I lost") and "credits" in line
              for line in spoken))
    print("    Spoken lines checked: %s" % spoken)

    # The window's lists, and the line spoken when you press
    # Enter on "I have no stat points to spend right now."
    fighter = game_logic.new_fighter("Bolt", "robot")
    fighter["stat_points"] = 0
    frame = main.MainFrame(fighter)
    for tab in main.MainFrame.TAB_NAMES:
        for item in frame.list_items(tab):
            check("list item says credits, not points: %r" % item,
                  not _bare_points(item))
    frame.notebook.SetSelection(0)  # Home tab
    frame.refresh_list("Home")
    home_box = frame.lists["Home"]
    home_box.SetSelection(
        [i for i, item in enumerate(frame.list_items("Home"))
         if item.startswith("I have no stat points")][0])
    frame.activate_current()
    spoken_no_points = frame.message_line.GetLabel()
    check("no-points announce says stat points, not points",
          spoken_no_points ==
          "I have no stat points to spend right now. I get "
          "2 stat points every time I level up.")
    check("no-points announce has no bare points",
          not _bare_points(spoken_no_points))
    frame.on_close(mock.MagicMock())

    # The server's spoken lines: format('...') strings in the
    # migrations. The baseline's one rename line is history,
    # superseded by the newest migration, so it is checked
    # there instead of here.
    here = os.path.dirname(os.path.abspath(__file__))
    mig_dir = os.path.join(here, "supabase", "migrations")
    names = sorted(os.listdir(mig_dir))
    check("a credits-wording migration exists",
          any("fix_credits_wording" in name for name in names))
    credits_fix = open(os.path.join(
        mig_dir, [n for n in names if "fix_credits_wording" in n][0]),
        encoding="utf-8").read()
    check("the credits-wording migration fixes the rename line",
          "Your balance is now in credits." in credits_fix)
    check("the credits-wording migration never says points for the currency",
          "Your points are now called credits" not in credits_fix)
    check("the credits-wording migration replaces apply_timers only",
          "create or replace function arena_private.apply_timers(" in credits_fix
          and "set search_path = ''" in credits_fix)
    # The hangout quests migration (Phase 18) adds
    # arena_get_quests and friends. The quest levels one
    # (Phase 23) adds arena_spend_quest_stat and redefines
    # complete so it awards quest XP and banks quest points.
    # The npc creatures one (Phase 24) adds arena_fight_npc.
    # The healing skill one (Phase 25) redefines the upgrade
    # and fight functions so Healing can be bought and level
    # 5 heals to full after every fight. The quest growth one
    # (Phase 26) makes durations, quest credits and the
    # automatic quest-stat bonus all grow with the quest
    # level. The newest migration is the dead giver voices one
    # (Phase 27, Makenna Nov 18, 2026): Gus speaks with Andrew
    # and Belle with Emma, because Davis and Sara are retired.
    # The quest pause migration (Phase 22) is still there,
    # and quest completion must never check repairs. No
    # migration may say "points" for the currency.
    quests_mig = open(os.path.join(
        mig_dir, [n for n in names if "add_hangout_quests" in n][0]),
        encoding="utf-8").read()
    check("the quests migration adds the quest functions",
          "arena_get_quests" in quests_mig
          and "arena_complete_quest" in quests_mig
          and "arena_join_quest" in quests_mig)
    check("a quest pause migration exists",
          any("quest_pause_resume" in name for name in names))
    pause_mig = open(os.path.join(
        mig_dir, [n for n in names if "quest_pause_resume" in n][0]),
        encoding="utf-8").read()
    check("the quest pause migration adds the pause function",
          "arena_pause_quest" in pause_mig
          and "arena_start_quest" in pause_mig
          and "arena_complete_quest" in pause_mig)
    check("an npc creatures migration exists",
          any("npc_creatures" in name for name in names))
    npc_mig = open(os.path.join(
        mig_dir, [n for n in names if "npc_creatures" in n][0]),
        encoding="utf-8").read()
    check("the npc creatures migration adds the npc fight function",
          "arena_fight_npc" in npc_mig)
    growth_mig = open(os.path.join(
        mig_dir, [n for n in names if "quest_growth" in n][0]),
        encoding="utf-8").read()
    check("a quest growth migration exists",
          any("quest_growth" in name for name in names))
    check("quest growth migration redefines the quest dealing and completion functions",
          "arena_new_quest" in growth_mig
          and "arena_complete_quest" in growth_mig)
    check("quest growth migration keys quest credits to the quest level",
          "quest_level" in growth_mig
          and "arena_private.quest_reward" in growth_mig)
    check("quest growth migration grows durations with the quest level but caps at 4 hours",
          "240" in growth_mig and "quest_level" in growth_mig)
    check("quest growth migration adds the automatic quest-stat bonus",
          "v_auto" in growth_mig)
    check("quest growth migration never says points for the currency",
          "Your points are now called credits" not in growth_mig)
    # Hotfix Phase 25b (Makenna Nov 18, 2026): the healing-level
    # hotfix is no longer the newest migration — the quest bonus
    # change (below) is. The hotfix checks read its file by name.
    hotfix_mig = open(os.path.join(
        mig_dir, [n for n in names if "healing_level_hotfix" in n][0]),
        encoding="utf-8").read()
    check("hotfix migration defaults healing_level to 0 in fighter_out",
          "fighter_out" in hotfix_mig
          and "coalesce((p_fighter ->> 'healing_level')::integer, 0)"
          in hotfix_mig)
    check("hotfix migration coalesces the upgrade slot levels",
          "lvl := coalesce((f ->> (p_slot || '_level'))::integer, 0);"
          in hotfix_mig
          and "v_level := coalesce((f ->> (p_slot || '_level'))::integer, 0);"
          in hotfix_mig)
    check("hotfix migration coalesces the max-upgrade healing cost lookup",
          "coalesce((f ->> 'healing_level')::integer, 0) + 1" in hotfix_mig)
    check("hotfix migration touches no fight function",
          "arena_fight" not in hotfix_mig)
    # Quest bonus from level 1 (Makenna Nov 18, 2026): it redefines
    # arena_complete_quest so the automatic bonus is quest level x
    # 1% — 1% already at quest level 1. It is no longer the newest
    # migration — the dead giver voices one (Phase 27, below) is —
    # so it is read by name, like the hotfix above.
    bonus_mig = open(os.path.join(
        mig_dir, [n for n in names if "quest_bonus_from_level1" in n][0]),
        encoding="utf-8").read()
    check("bonus migration gives 1 percent at quest level 1",
          "arena_complete_quest" in bonus_mig
          and "v_auto := greatest(0, v_qlevel);" in bonus_mig)
    check("bonus migration drops the old level minus one formula",
          "v_qlevel - 1" not in bonus_mig)
    check("bonus migration touches no fight function",
          "arena_fight" not in bonus_mig)
    # Dead giver voices (Makenna Nov 18, 2026, Phase 27): it
    # redefines quest_giver_voice so Gus speaks with Andrew
    # and Belle with Emma — Davis and Sara are retired. It
    # is no longer the newest migration — the first-person
    # one (Phase 28, below) is — so it is read by name.
    voices_mig = open(os.path.join(
        mig_dir, [n for n in names if "replace_dead_giver_voices" in n][0]),
        encoding="utf-8").read()
    check("dead giver voices migration gives Gus the Andrew voice",
          "arena_private.quest_giver_voice" in voices_mig
          and "when 'Gus' then 'en-US-AndrewNeural'" in voices_mig)
    check("dead giver voices migration gives Belle the Emma voice",
          "when 'Belle' then 'en-US-EmmaNeural'" in voices_mig)
    check("dead giver voices migration drops the dead Davis and Sara voices",
          "when 'Gus' then 'en-US-DavisNeural'" not in voices_mig
          and "when 'Belle' then 'en-US-SaraNeural'" not in voices_mig)
    check("dead giver voices migration keeps the other giver voices",
          "en-US-ChristopherNeural" in voices_mig
          and "en-US-JennyNeural" in voices_mig
          and "en-US-EricNeural" in voices_mig
          and "en-US-MichelleNeural" in voices_mig)
    check("dead giver voices migration touches no fight function",
          "arena_fight" not in voices_mig)
    # First-person narration (Makenna Nov 18, 2026, Phase 28):
    # the newest migration re-issues the fight, repair,
    # upgrade, stat and quest functions so the player's own
    # lines say "I / me / my" and givers address the player
    # by name. No numbers, costs or times change.
    newest = open(os.path.join(mig_dir, names[-1]), encoding="utf-8").read()
    check("newest migration is the first-person narration one",
          "first_person_narration" in names[-1])
    check("newest migration says I hit in a fight",
          "I hit the Scrap Rat for %s" in newest
          and "I hit the %s for %s" in newest)
    check("newest migration says the creature hits me",
          "The Scrap Rat hits me for %s" in newest
          and "The %s hits me for %s" in newest)
    check("newest migration says I won and I lost",
          "I won! I earned %s experience and %s credits." in newest
          and "I lost. I need repairs, %s." in newest)
    check("newest migration says repairs in the first person",
          "My repairs are finished. I''m back to full health." in newest)
    check("newest migration names the player on a finished quest",
          "Quest done, %s! Thank you — you earned %s credits." in newest)
    check("newest migration updates the NPC ability lines too",
          "My hit bounces off!" in newest
          and "My next hit is sticky and weak!" in newest)
    check("newest migration keeps the dead voices dead",
          "en-US-DavisNeural" not in newest
          and "en-US-SaraNeural" not in newest)
    healing_mig = open(os.path.join(
        mig_dir, [n for n in names if "healing_skill" in n][0]),
        encoding="utf-8").read()
    check("the healing skill migration redefines the upgrade functions",
          "arena_start_upgrade" in healing_mig
          and "arena_max_upgrade" in healing_mig)
    check("the healing skill migration redefines the fight functions",
          "arena_fight" in healing_mig
          and "arena_fight_npc" in healing_mig)
    check("the healing skill migration names the skill Second Wind",
          "Second Wind" in healing_mig)
    check("the healing skill migration heals to full at level 5",
          "healing_level" in healing_mig
          and "never need repairs again" in healing_mig)
    levels_mig = open(os.path.join(
        mig_dir, [n for n in names if "quest_levels" in n][0]),
        encoding="utf-8").read()
    check("the quest levels migration adds the quest stat spending function",
          "arena_spend_quest_stat" in levels_mig
          and "arena_complete_quest" in levels_mig)
    check("quest completion never checks repairs",
          "is_repairing" not in levels_mig)
    baseline = open(os.path.join(
        mig_dir, "20261118045430_baseline.sql"), encoding="utf-8").read()
    baseline_lines = [
        literal for literal in re.findall(r"format\('([^']*)'", baseline)
        if "Your points are now called credits" not in literal]
    check("baseline fight and upgrade lines say credits, not points",
          not any(_bare_points(literal) for literal in baseline_lines))
    check("baseline win line says credits",
          any("You won! You earned" in literal and "credits" in literal
              for literal in baseline_lines))
    print("\nAll currency wording tests passed.")


def narration_test():
    """Turn-by-turn narration: a manual fight speaks every round
    line in order, with a pause; an idle fight does the same;
    a single announce waits behind a narration instead of
    cutting it off; and the next idle fight waits for the
    narration to finish before it starts."""
    import importlib
    import voice_engine

    sys.modules["edge_tts"] = _make_fake_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)
    media = sys.modules["pygame"].mixer.music
    media.fail_load = False
    media.finish()

    fighter = game_logic.new_fighter("Bolt", "robot")
    frame = main.MainFrame(fighter)
    check("voice is on for narration", frame.voice is not None)

    # A manual fight queues every line, and speaks the first one.
    frame.random = random.Random(7)
    frame.do_fight()
    lines = frame.logs["Combat"].text.strip().split("\n")
    check("manual fight logs every round line", len(lines) >= 3)
    check("manual fight speaks the first line first",
          _wait_spoken(frame, lines[0]))
    check("manual fight queues the rest in order",
          [text for text, _voice in frame._narration_queue] == lines[1:])

    # Finish each line in turn: the next line must be the next
    # line of the fight, never a skipped or repeated one.
    spoken = [lines[0]]
    while frame._narration_queue:
        _finish_line_and_advance(frame)
        check("next narration line is the next fight line",
              _wait_spoken(frame, lines[len(spoken)]))
        spoken.append(lines[len(spoken)])
    check("every fight line was spoken, in order", spoken == lines)
    check("narration queue is empty at the end", frame._narration_queue == [])

    # A single announce no longer cuts a narration off: it waits
    # at the end of the queue and is spoken after the fight's
    # lines, in order. (This is how turning idle fighting off
    # mid-fight works: the fight finishes talking first.)
    frame.random = random.Random(7)
    log_before = len(frame.logs["Combat"].text.strip().split("\n"))
    frame.do_fight()
    second_lines = frame.logs["Combat"].text.strip().split("\n")[log_before:]
    check("a second fight queues its lines again", bool(frame._narration_queue))
    frame.announce("Idle fighting off.")
    check("announce queues behind a narration, it does not cancel it",
          frame._narration_queue[-1][0] == "Idle fighting off."
          and len(frame._narration_queue) >= 2)
    # A giver's line keeps the giver's voice in the queue.
    frame.announce_as("Bolt asks: fetch the scrap.", "en-US-ChristopherNeural")
    check("a giver line queues in the giver's voice",
          frame._narration_queue[-1]
          == ("Bolt asks: fetch the scrap.", "en-US-ChristopherNeural"))
    frame._narration_queue.pop()  # take it back out: the drain below
    # is about the fight lines and the off line only.
    # Finish the fight's lines first, then the queued line speaks.
    # Drain the whole queue: the off line is only popped when it
    # starts speaking, so the loop cannot end early.
    while frame._narration_queue:
        _finish_line_and_advance(frame)
    check("the queued line speaks after the fight lines",
          _wait_spoken(frame, "Idle fighting off."))
    check("narration queue is empty at the end", frame._narration_queue == [])
    media.finish()

    # An idle fight now narrates every round line, exactly like a
    # manual fight, with the same queue and the same order.
    frame.random = random.Random(7)
    log_before = len(frame.logs["Combat"].text.strip().split("\n"))
    before = len(media.loaded)
    frame.do_fight(idle=True)
    idle_lines = frame.logs["Combat"].text.strip().split("\n")[log_before:]
    check("idle fight queues every round line, not just the result",
          len(frame._narration_queue) == len(idle_lines) - 1)
    check("idle fight speaks the first round line first",
          _wait_spoken(frame, idle_lines[0]))
    spoken = [idle_lines[0]]
    while frame._narration_queue:
        _finish_line_and_advance(frame)
        check("next idle line is the next fight line",
              _wait_spoken(frame, idle_lines[len(spoken)]))
        spoken.append(idle_lines[len(spoken)])
    check("every idle fight line was spoken, in order", spoken == idle_lines)
    check("idle fight spoke every line, not just one",
          len(media.loaded) == before + len(idle_lines))
    media.finish()

    # The next idle fight waits for the narration to finish.
    # While the first fight is still talking, a tick must not
    # start a second fight, and must not restart the 5-second
    # gap either. Once the talking is done, the next tick
    # starts the next fight straight away.
    import copy
    wins_losses = fighter["wins"] + fighter["losses"]
    winning_seed = None
    for seed in range(50):
        trial = copy.deepcopy(fighter)
        if game_logic.fight(trial, rng=random.Random(seed))["won"]:
            winning_seed = seed
            break
    check("a winning seed exists for the gating test", winning_seed is not None)
    frame.random = random.Random(winning_seed)
    log_before = len(frame.logs["Combat"].text.strip().split("\n"))
    frame.do_fight(idle=True)
    gating_lines = frame.logs["Combat"].text.strip().split("\n")[log_before:]
    check("gating fight started", fighter["wins"] + fighter["losses"] == wins_losses + 1)
    frame.idle_fighting = True
    frame.last_idle_fight = 0.0  # the 5-second gap is long past
    frame.on_tick(mock.MagicMock())
    check("no second idle fight starts while narration is speaking",
          fighter["wins"] + fighter["losses"] == wins_losses + 1)
    check("the waiting gap is not restarted while narration speaks",
          frame.last_idle_fight == 0.0)
    while frame._narration_queue:
        _finish_line_and_advance(frame)
    # The last line was only just spoken: wait for it to reach
    # the player and finish sounding before the next tick, or
    # the gate will (rightly) still see narration in progress.
    check("the gating fight's last line reaches the player",
          _wait_spoken(frame, gating_lines[-1]))
    media.finish()
    frame.on_tick(mock.MagicMock())
    check("the next idle fight starts once the narration has finished",
          fighter["wins"] + fighter["losses"] == wins_losses + 2)
    frame.idle_fighting = False

    frame.on_close(mock.MagicMock())
    print("\nAll turn-by-turn narration tests passed.")


def game_action_speech_test():
    """Makenna's TTS rule (2026-11-18): Edge speaks for
    in-game actions — an upgrade starting, quests starting,
    quest progress and finish, auto-fight narration — and
    stays silent for navigation, where NVDA is the only
    voice. Tab silence is checked in voice_test and
    auto-fight narration in narration_test; this checks
    the other speaking side with the voice on."""
    import copy
    import importlib
    import quests as quests_module
    import online_save as _online_save
    import voice_engine

    sys.modules["edge_tts"] = _make_fake_edge_tts()
    importlib.reload(voice_engine)
    importlib.reload(main)
    media = sys.modules["pygame"].mixer.music
    media.fail_load = False

    def _spoken(frame, text, timeout=8.0):
        """True once the voice thread logs speaking this text.
        The log is the reliable record: the previous line's
        voice file is deleted as soon as the next line plays,
        so reading the file back is a race. A line queued
        behind one still speaking only sounds once the
        one-second timer advances the narration, so advance
        it here while waiting — in the real game the timer
        does this on its own."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if ('Voice: speaking "' + text) in LOG_CAPTURE.getvalue():
                return True
            _finish_line_and_advance(frame)
        return ('Voice: speaking "' + text) in LOG_CAPTURE.getvalue()

    def _drain(frame):
        while frame._narration_queue:
            _finish_line_and_advance(frame)
        media.finish()

    # 1. An upgrade starting in the Shop speaks.
    fighter = game_logic.new_fighter("Rusty", "robot")
    fighter["credits"] = 1000
    frame = main.MainFrame(fighter)
    check("voice is on for game-action speech", frame.voice is not None)
    check("welcome line speaks first",
          _wait_spoken(frame, "Welcome to Arena of Makers, Rusty."))
    _drain(frame)
    frame.do_upgrade("weapon")
    check("starting an upgrade speaks",
          # The voice log keeps a 40-character preview, so
          # the match has to fit inside it.
          _spoken(frame, "I'm upgrading my Laser Blaster to level"))
    frame.on_close(mock.MagicMock())

    # 2. Quests starting, progressing and finishing speak.
    # A small fake server, same rules as quest_test.
    qfighter = game_logic.new_fighter("Bolt", "robot")
    qfighter["credits"] = 100
    qfighter["player_code"] = "4242"
    server = {"fighter": copy.deepcopy(qfighter),
              "board": quests_module.starting_board(random.Random(7)),
              "done": [], "rep": {}, "active": None,
              "joined": [], "gift_pending": None, "calls": []}

    def _fighter_out():
        return copy.deepcopy(server["fighter"])

    def _fake_get_quests(config):
        return {"fighter": _fighter_out(),
                "quests": copy.deepcopy(server["board"]),
                "active": copy.deepcopy(server["active"]),
                "reputation": dict(server["rep"]),
                "gift_pending": None}, None

    def _fake_start_quest(config, quest_id):
        quest = next((q for q in server["board"] if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        if quest.get("coop") and quest_id not in server["joined"]:
            return {}, "Join the Grand Hangout Fair first, then start it."
        started = copy.deepcopy(quest)
        started["started_at"] = time.time()
        started["finish_at"] = started["started_at"] + started["duration_minutes"] * 60
        server["active"] = started
        return {"fighter": _fighter_out(),
                "quest": copy.deepcopy(started)}, None

    def _fake_join_quest(config, quest_id):
        if quest_id not in server["joined"]:
            server["joined"].append(quest_id)
        return {"fighter": _fighter_out(),
                "message": "You joined the Grand Hangout Fair."}, None

    def _fake_complete_quest(config, quest_id):
        quest = next((q for q in server["board"] if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        active = server["active"]
        if active is None or active["id"] != quest_id:
            return {}, "Start that quest in the hangout first."
        if active.get("paused") and active.get("remaining_seconds", 0) > 0:
            return {}, "That quest is paused."
        if active["finish_at"] > time.time():
            return {}, "That quest is not done yet."
        giver = quest["giver"]
        server["rep"][giver] = server["rep"].get(giver, 0) + 1
        # Quest growth (Phase 26): credits are keyed to the
        # quest level, not the fighter level, and the
        # automatic bonus (+1% per quest level) applies.
        # At quest level 1 here the bonus is 1%.
        qlevel = server["fighter"].get("quest_level", 1)
        auto = max(0, qlevel)
        reward = int(quests_module.quest_reward(
            quest["difficulty"], qlevel) * (1 + 0.01 * auto))
        server["fighter"]["credits"] += reward
        # Quest levels (Phase 23), same rules as quest_test:
        # quest XP for the difficulty, level-ups banking a
        # quest point. No quest stats here, so no boosts
        # beyond the automatic bonus.
        qxp = server["fighter"].get("quest_xp", 0)
        qpoints = server["fighter"].get("quest_points", 0)
        xp_earned = int(quests_module.quest_xp(
            quest["difficulty"], qlevel) * (1 + 0.01 * auto))
        qxp += xp_earned
        level_ups = 0
        while qxp >= quests_module.quest_xp_to_next(qlevel):
            qxp -= quests_module.quest_xp_to_next(qlevel)
            qlevel += 1
            qpoints += 1
            level_ups += 1
        server["fighter"]["quest_level"] = qlevel
        server["fighter"]["quest_xp"] = qxp
        server["fighter"]["quest_points"] = qpoints
        quest_xp_line = (
            "You earned %s quest experience, Bolt. You have %s quest "
            "experience now, %s more to reach quest level %s."
            % (xp_earned, qxp,
               quests_module.quest_xp_to_next(qlevel) - qxp, qlevel + 1))
        quest_level_line = None
        if level_ups > 0:
            quest_level_line = (
                "You're now quest level %s, Bolt! You have %s quest %s to spend."
                % (qlevel, qpoints,
                   "point" if qpoints == 1 else "points"))
        server["board"] = [q for q in server["board"] if q["id"] != quest_id]
        server["done"].append(quest_id)
        server["active"] = None
        return {"fighter": _fighter_out(),
                "quest": copy.deepcopy(quest),
                "quests": copy.deepcopy(server["board"]),
                "credits": reward,
                "message": "Quest done, Bolt! Thank you — you earned %s credits." % reward,
                "tier_line": None, "giver": giver,
                "giver_voice": quest["giver_voice"],
                "reputation": dict(server["rep"]),
                "gift_pending": None,
                "quest_xp_earned": xp_earned,
                "quest_level": qlevel,
                "quest_xp": qxp,
                "quest_xp_to_next":
                    quests_module.quest_xp_to_next(qlevel) - qxp,
                "quest_points": qpoints,
                "quest_level_ups": level_ups,
                "bonus_reputation": 0,
                "quest_xp_line": quest_xp_line,
                "quest_level_line": quest_level_line}, None

    def _fake_new_quest(config):
        # Finished quest ids are never dealt again: the real
        # server only ever deals a fresh quest, and the
        # client treats a finished id on the board as stale
        # and drops it, so re-dealing one would kill the loop.
        ids = [q["id"] for q in server["board"]] + list(server["done"])
        names = [q["name"] for q in server["board"]]
        quest = quests_module.generate_quest(
            random.Random(len(ids)), None, ids,
            coop_allowed=not any(q.get("coop") for q in server["board"]),
            existing_names=names,
            quest_level=server["fighter"].get("quest_level", 1))
        server["board"].append(quest)
        return {"fighter": _fighter_out(),
                "quest": copy.deepcopy(quest)}, None

    def _fake_pause_quest(config):
        active = server["active"]
        if active is None:
            return {"fighter": _fighter_out(), "quest": None}, None
        if active.get("paused"):
            return {"fighter": _fighter_out(),
                    "quest": copy.deepcopy(active),
                    "remaining_seconds": active.get("remaining_seconds", 0)}, None
        remaining = max(0.0, active["finish_at"] - time.time())
        active["paused"] = True
        active["remaining_seconds"] = remaining
        return {"fighter": _fighter_out(),
                "quest": copy.deepcopy(active),
                "remaining_seconds": remaining}, None

    _online_save.get_quests = _fake_get_quests
    _online_save.new_quest = _fake_new_quest
    _online_save.start_quest = _fake_start_quest
    _online_save.join_quest = _fake_join_quest
    _online_save.complete_quest = _fake_complete_quest
    _online_save.pause_quest = _fake_pause_quest
    _online_save.refresh_state = lambda config: (_fighter_out(), [], None)
    _online_save.heartbeat = lambda *args, **kwargs: True
    _online_save.sign_out = lambda *args, **kwargs: True
    _online_save.log_action = lambda *args, **kwargs: True

    qframe = main.MainFrame(
        qfighter,
        online_config={"url": "https://example.supabase.co",
                       "key": "sb_publishable_fake", "session": "a" * 64},
        player_account={"username": "Bolt", "player_code": "4242"},
    )
    check("welcome line speaks in the quest game too",
          _wait_spoken(qframe, "Welcome to Arena of Makers, Bolt."))
    _drain(qframe)
    # Navigation in this game too: a tab change speaks nothing.
    before = len(media.loaded)
    spoken_before = LOG_CAPTURE.getvalue().count("Voice: speaking")
    qframe.notebook.SetSelection(0)
    qframe.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    time.sleep(0.3)
    check("a tab change speaks nothing, with the voice on",
          len(media.loaded) == before
          and qframe._narration_queue == []
          and LOG_CAPTURE.getvalue().count("Voice: speaking") == spoken_before)
    # Visit the hangout, then Start with Enter.
    qframe.notebook.SetSelection(3)
    qframe.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    qframe.refresh_list("More")
    more_box = qframe.lists["More"]
    more_box.SetSelection(
        qframe.list_items("More").index("Visit the hangout"))
    qframe.activate_current()
    _drain(qframe)
    qframe.activate_current()
    check("starting quests speaks",
          # The voice log previews only the first 40 chars,
          # so match the start of the line, not the whole line.
          _spoken(qframe, "Quests started. I will keep giving"))
    _finish_line_and_advance(qframe)
    giver = qframe._quest_current["giver"]
    check("the quest giver speaks the new quest",
          _spoken(qframe, "%s asks: " % giver))
    # A progress update speaks, in the giver's voice.
    _drain(qframe)
    qframe._quest_current["started_at"] = time.time() - 600
    qframe._quest_current["finish_at"] = time.time() + 600
    qframe._quest_last_progress_at = time.time() - 301
    qframe.on_tick(mock.MagicMock())
    check("a quest progress update speaks",
          _spoken(qframe, "You're about "))
    # Finishing a quest speaks.
    _drain(qframe)
    finished_difficulty = qframe._quest_current["difficulty"]
    qframe._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    qframe.on_tick(mock.MagicMock())
    check("a finished quest speaks",
          # 40-character voice-log preview, as above.
          _spoken(qframe, "Quest done, Bolt! Thank you — you earned"))
    check("a finished quest announces the reputation gained",
          _spoken(qframe, "You gained 1 reputation with me, Bolt"))
    check("a finished quest announces the quest experience earned",
          _spoken(qframe, "You earned %s quest experience"
                  % quests_module.quest_xp(finished_difficulty, 1)))
    # The distance to the next tier is past the voice log's
    # 40-character preview, so it is checked word-for-word
    # in quest_test instead of here.
    qframe.on_close(mock.MagicMock())
    print("\nAll game-action speech tests passed.")


def sounds_test():
    """The sound bank: missing files are skipped without a crash,
    loaded files play the right sound for robot and chef, music
    loops on its own channel, and turning sounds off stops it."""
    import importlib
    import sounds as sounds_module

    importlib.reload(sounds_module)
    pygame = sys.modules["pygame"]

    # No files at all: nothing plays, nothing crashes.
    import tempfile
    empty_dir = tempfile.mkdtemp()
    bank = sounds_module.SoundBank(directory=empty_dir, pygame_module=pygame)
    bank.load()
    check("sound bank loads nothing from an empty folder",
          bank.loaded_names == [])
    check("playing a missing sound returns False",
          bank.play("robot_laser") is False)
    check("music does not start with no music file",
          bank.start_music() is False)

    # Dummy files for every pick: the bank loads them all.
    full_dir = tempfile.mkdtemp()
    for _name, (filename, _maxtime) in sounds_module.SOUND_FILES.items():
        with open(os.path.join(full_dir, filename), "wb") as handle:
            handle.write(b"fake-sound")
    bank = sounds_module.SoundBank(directory=full_dir, pygame_module=pygame)
    bank.load()
    check("sound bank loads every pick when the files are there",
          len(bank.loaded_names) == len(sounds_module.SOUND_FILES))
    check("robot hit plays the laser",
          bank.play_hit("robot") and bank._sounds["robot_laser"].played == 1)
    check("chef hit plays the chopping sound",
          bank.play_hit("chef") and bank._sounds["chef_chop"].played == 1)
    check("chopping plays only its first moments",
          bank._sounds["chef_chop"].maxtime == 1500)
    check("creature hit on a robot plays the metal clank",
          bank.play_creature_hit("robot")
          and bank._sounds["robot_clank"].played == 1)
    check("creature hit on a chef plays the pan clang",
          bank.play_creature_hit("chef")
          and bank._sounds["pan_clang"].played == 1)
    check("win plays the win jingle",
          bank.play_win() and bank._sounds["win"].played == 1)
    check("loss plays the loss sound",
          bank.play_loss() and bank._sounds["loss"].played == 1)
    check("music starts and loops",
          bank.start_music() is True
          and bank._music_channel is not None
          and bank._music_channel.loops == -1)
    check("the default music track is the hangout track",
          bank.current_music_track == "hangout")
    check("the hangout track is the cafe track",
          bank._music_channel.played
          is bank._sounds["music_hangout"])
    channel = bank._music_channel
    check("asking for the same track again does not restart it",
          bank.start_music("hangout") is True
          and bank._music_channel is channel)
    check("the fight track switches the music",
          bank.start_music("fight") is True
          and bank.current_music_track == "fight"
          and bank._music_channel.played
          is bank._sounds["music_fight"])
    check("music is quieter than the effects",
          bank._music.volume == 0.4 * sounds_module.MUSIC_VOLUME_FACTOR)
    bank.set_volume(100)
    check("volume turns the music up too, still at half",
          bank._music.volume == 1.0 * sounds_module.MUSIC_VOLUME_FACTOR)
    bank.set_enabled(False)
    check("turning sounds off stops the music",
          bank._music_channel is None)
    check("no sound plays while sounds are off",
          bank.play("win") is False)

    # With only the hangout track on disk, the fight track
    # cannot start, and the hangout track still can.
    hangout_only = tempfile.mkdtemp()
    with open(os.path.join(hangout_only, "music_loop.mp3"), "wb") as handle:
        handle.write(b"fake-sound")
    bank = sounds_module.SoundBank(directory=hangout_only,
                                   pygame_module=pygame)
    bank.load()
    check("the fight track does not start without its file",
          bank.start_music("fight") is False)
    check("the hangout track still starts from the old name",
          bank.start_music("hangout") is True
          and bank.current_music_track == "hangout")

    # Quest ambience loops (Phase 23): one loop on its own
    # channel, quieter than the music, that stops when the
    # quest ends. With no such sound, nothing plays.
    bank = sounds_module.SoundBank(directory=full_dir, pygame_module=pygame)
    bank.load()
    check("ambience does not start with no such sound",
          bank.start_ambience("no_such_sound") is False)
    check("an ambience loop starts and loops",
          bank.start_ambience("chef_sizzle") is True
          and bank._ambience_channel is not None
          and bank._ambience_channel.loops == -1
          and bank.current_ambience == "chef_sizzle")
    check("the ambience loop is on its own channel, not the music channel",
          bank._ambience_channel.number == 3)
    check("the ambience loop is quieter than the music",
          bank._sounds["chef_sizzle"].volume
          == 0.4 * sounds_module.AMBIENCE_VOLUME_FACTOR)
    channel = bank._ambience_channel
    check("asking for the same ambience again does not restart it",
          bank.start_ambience("chef_sizzle") is True
          and bank._ambience_channel is channel)
    check("switching ambience stops the old loop and starts the new one",
          bank.start_ambience("robot_servo") is True
          and bank.current_ambience == "robot_servo"
          and channel.stopped)
    bank.set_volume(100)
    check("volume turns the ambience up too, still quieter than the music",
          bank._sounds["robot_servo"].volume
          == 1.0 * sounds_module.AMBIENCE_VOLUME_FACTOR)
    bank.stop_ambience()
    check("stopping the ambience clears it",
          bank.current_ambience is None
          and bank._ambience_channel is None)
    check("stopping the ambience puts the sound's volume back",
          bank._sounds["robot_servo"].volume == 1.0)
    bank.start_ambience("robot_servo")
    bank.set_enabled(False)
    check("turning sounds off stops the ambience",
          bank.current_ambience is None)
    check("no ambience starts while sounds are off",
          bank.start_ambience("chef_sizzle") is False)
    print("\nAll sound bank tests passed.")


def launch_update_test():
    """Launch update check (Phase 19): the game asks
    GitHub at launch, offers Yes/No, and never updates
    without being told to. No network is used: the
    updater's GitHub calls are stubbed here.
    """
    import json
    import tempfile
    import arena_of_makers_updater as updater

    def _make_game(folder, head="abc123"):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "main.py"),
                  "w", encoding="utf-8") as handle:
            handle.write("# game\n")
        with open(os.path.join(folder, updater.VERSION_FILE_NAME),
                  "w", encoding="utf-8") as handle:
            json.dump({"head_sha": head, "files": ["main.py"]}, handle)

    wx = sys.modules["wx"]
    base = tempfile.mkdtemp()
    game_dir = os.path.join(base, "Arena of Makers")
    _make_game(game_dir)

    old_head = updater.get_head_sha
    old_tree = updater.get_tree
    old_release = updater.get_latest_release
    old_sync = updater.sync_game
    try:
        # Up to date: no question, just play.
        updater.get_head_sha = lambda timeout=60: "abc123"
        result = main.check_for_update_at_launch(game_dir)
        check("up to date means no update offered",
              result["available"] is False
              and result["unreachable"] is False)

        # GitHub unreachable: play on, not a crash, and the
        # player is told in plain words.
        updater.get_head_sha = lambda timeout=60: None
        result = main.check_for_update_at_launch(game_dir)
        check("GitHub unreachable means play on, not a crash",
              result["available"] is False
              and result["unreachable"] is True)
        check("unreachable still plays on",
              main.maybe_update_at_launch(game_dir) is False)

        # A newer version is waiting: No plays on and does
        # not start the update.
        updater.get_head_sha = lambda timeout=60: "def456"
        calls = []
        updater.sync_game = (
            lambda folder, log, include_updater=False:
            calls.append(include_updater) or True
        )
        wx.Dialog.modal_result = wx.ID_NO
        check("saying No to the update plays on",
              main.maybe_update_at_launch(game_dir) is False)
        check("saying No does not start the update", calls == [])

        # Yes applies the update, including the updater's
        # own file, and the game stops so a restart plays
        # the new version.
        wx.Dialog.modal_result = wx.ID_YES
        check("saying Yes stops the game after the update",
              main.maybe_update_at_launch(game_dir) is True)
        check("Yes updates through the game, updater file included",
              calls == [True])

        # A failed update plays on instead of quitting.
        updater.sync_game = (
            lambda folder, log, include_updater=False: False
        )
        check("a failed update plays on",
              main.maybe_update_at_launch(game_dir) is False)
        wx.Dialog.modal_result = 1  # back to ID_OK

        # No version note, files already matching main: the
        # note is written quietly and no question is asked.
        plain_dir = os.path.join(base, "Plain")
        os.makedirs(plain_dir)
        with open(os.path.join(plain_dir, "main.py"),
                  "w", encoding="utf-8") as handle:
            handle.write("# game\n")
        updater.get_tree = lambda timeout=60: [
            {"path": "main.py",
             "sha": updater.local_blob_hash(
                 os.path.join(plain_dir, "main.py"))}
        ]
        result = main.check_for_update_at_launch(plain_dir)
        check("matching files without a note play on quietly",
              result["available"] is False
              and result["unreachable"] is False)
        head, _files = updater.load_state(plain_dir)
        check("matching files write the version note",
              head == "def456")

        # No version note, files different from main: the
        # update is offered.
        updater.get_tree = lambda timeout=60: [
            {"path": "main.py",
             "sha": updater.blob_hash(b"# newer game\n")},
            {"path": "arena_of_makers_updater.py",
             "sha": updater.blob_hash(b"# newer updater\n")},
        ]
        plain2 = os.path.join(base, "Plain2")
        os.makedirs(plain2)
        with open(os.path.join(plain2, "main.py"),
                  "w", encoding="utf-8") as handle:
            handle.write("# game\n")
        result = main.check_for_update_at_launch(plain2)
        check("different files without a note are offered the update",
              result["available"] is True)
    finally:
        updater.get_head_sha = old_head
        updater.get_tree = old_tree
        updater.get_latest_release = old_release
        updater.sync_game = old_sync
    print("Launch update tests passed.")


def quest_test():
    """Hangout quests (Phase 18): Start and Stop in the
    hangout, quests running automatically one after another,
    progress updates every 5 minutes, rewards from the
    server, reputation and gifts, quests while repairing,
    and the co-op fair. The "server" here is a fake in
    memory that runs the same rules as the migration:
    board of 5, start records the time, complete checks
    the time and never checks repairs, reputation +1 per
    finished quest, gifts instant. Phase 22 adds: the quest
    clock pauses when the player leaves the hangout (Stop,
    leaving the tab, closing the game) and resumes from the
    frozen remaining time; the loop skips a stale quest
    instead of stopping; progress updates mention repairs;
    completion announces reputation gained and distance to
    the next tier."""
    import copy
    import quests as quests_module
    import online_save as _online_save

    check("quest givers are three male and three female",
          sum(1 for g in quests_module.GIVERS
              if g["gender"] == "male") == 3
          and sum(1 for g in quests_module.GIVERS
                  if g["gender"] == "female") == 3)
    check("every giver has their own Edge voice",
          len({g["voice"] for g in quests_module.GIVERS}) == 6)
    check("no quest is restricted by fighter kind",
          all("kind" not in q for q in quests_module.QUEST_TEMPLATES)
          and all("kind" not in q
                  for q in quests_module.starting_board(random.Random(2))))
    check("easy quest pays 7 credits at quest level 1",
          quests_module.quest_reward("Easy", 1) == 7)
    check("medium quest pays 15 credits at quest level 1",
          quests_module.quest_reward("Medium", 1) == 15)
    check("hard quest pays 30 credits at quest level 1",
          quests_module.quest_reward("Hard", 1) == 30)
    check("quest durations never pass 4 hours",
          all(quests_module.quest_duration_minutes(d, random.Random(i)) <= 240
              for i, d in enumerate(
                  ["Easy", "Medium", "Hard"] * 20)))

    # Quest growth (Phase 26): durations, credits and the
    # automatic quest-stat bonus all grow with the quest
    # level. The timer still caps at 4 hours; the rewards
    # never cap. Quest XP formulas are unchanged.
    class _MinRng:
        def randint(self, low, high):
            return low

    class _MaxRng:
        def randint(self, low, high):
            return high

    check("quest durations are unchanged at quest level 1",
          quests_module.quest_duration_minutes("Easy", _MinRng(), 1) == 5
          and quests_module.quest_duration_minutes("Easy", _MaxRng(), 1) == 15
          and quests_module.quest_duration_minutes("Medium", _MinRng(), 1) == 15
          and quests_module.quest_duration_minutes("Medium", _MaxRng(), 1) == 45
          and quests_module.quest_duration_minutes("Hard", _MinRng(), 1) == 60
          and quests_module.quest_duration_minutes("Hard", _MaxRng(), 1) == 240)
    check("quest durations grow with the quest level",
          quests_module.quest_duration_minutes("Easy", _MinRng(), 5) == 7
          and quests_module.quest_duration_minutes("Easy", _MaxRng(), 5) == 21
          and quests_module.quest_duration_minutes("Medium", _MinRng(), 5) == 21
          and quests_module.quest_duration_minutes("Medium", _MaxRng(), 5) == 62
          and quests_module.quest_duration_minutes("Hard", _MinRng(), 5) == 84
          and quests_module.quest_duration_minutes("Hard", _MaxRng(), 5) == 240
          and quests_module.quest_duration_minutes("Easy", _MinRng(), 10) == 9
          and quests_module.quest_duration_minutes("Easy", _MaxRng(), 10) == 28
          and quests_module.quest_duration_minutes("Hard", _MinRng(), 10) == 114)
    check("quest durations never pass 4 hours at high quest levels",
          all(quests_module.quest_duration_minutes(d, random.Random(i), level) <= 240
              for level in (5, 10, 50, 200)
              for i, d in enumerate(["Easy", "Medium", "Hard"] * 20)))
    check("a board dealt at quest level 5 has longer durations",
          all(5 <= q["duration_minutes"] <= 240
              for q in quests_module.starting_board(random.Random(3), 5))
          and any(q["duration_minutes"] > 15
                  for q in quests_module.starting_board(random.Random(3), 5)
                  if q["difficulty"] == "Easy"))
    check("quest credits grow with the quest level",
          quests_module.quest_reward("Easy", 5) == 15
          and quests_module.quest_reward("Medium", 5) == 35
          and quests_module.quest_reward("Hard", 5) == 70
          and quests_module.quest_reward("Medium", 10) == 60
          and quests_module.quest_reward("Hard", 10) == 120)
    check("quest experience formulas are unchanged at quest level 5",
          quests_module.quest_xp("Easy", 5) == 20
          and quests_module.quest_xp("Medium", 5) == 45
          and quests_module.quest_xp("Hard", 5) == 90)
    check("the automatic quest-stat bonus is 1 percent at quest level 1",
          quests_module.quest_auto_bonus_percent({"quest_level": 1}) == 1)
    check("the automatic quest-stat bonus is 5 percent at quest level 5",
          quests_module.quest_auto_bonus_percent({"quest_level": 5}) == 5)
    check("the automatic bonus stacks with spent charm points",
          quests_module.quest_stat_effect_percent(
              {"quest_level": 5,
               "quest_stats": {"charm": 2, "renown": 0, "insight": 0}},
              "charm") == 15)
    check("the automatic bonus stacks with spent insight points",
          quests_module.quest_stat_effect_percent(
              {"quest_level": 5,
               "quest_stats": {"charm": 0, "renown": 0, "insight": 2}},
              "insight") == 15)
    check("renown chance never passes 100 percent",
          quests_module.quest_stat_effect_percent(
              {"quest_level": 5,
               "quest_stats": {"charm": 0, "renown": 10, "insight": 0}},
              "renown") == 100)
    check("the quest level line says the automatic bonus from level 1 up",
          quests_module.quest_level_line(
              {"quest_level": 3, "quest_xp": 0})
          == "Quest level 3, 300 quest experience to level 4. "
             "My quest level adds 3 percent to Charm, Renown "
             "and Insight.")
    check("charm line says the automatic bonus on top of the points",
          quests_module.quest_stat_line(
              {"quest_level": 5,
               "quest_stats": {"charm": 2, "renown": 0, "insight": 0}},
              "charm")
          == "Charm, 2. Quests pay 15 percent more credits, "
             "5 from my quest level. One more point adds 5 percent.")
    check("renown line says the automatic bonus on top of the points",
          quests_module.quest_stat_line(
              {"quest_level": 5,
               "quest_stats": {"charm": 0, "renown": 0, "insight": 0}},
              "renown")
          == "Renown, 0. 5 percent chance of 1 bonus reputation "
             "when a quest finishes, 5 from my quest level. "
             "One more point adds 10 percent.")

    # Quest levels (Phase 23): separate from combat. Only
    # finishing a quest earns quest XP; starting, stopping
    # or pausing earns nothing. Easy 10 + 2 x quest level,
    # Medium 20 + 5 x quest level, Hard 40 + 10 x quest level.
    check("easy quest pays 12 quest experience at quest level 1",
          quests_module.quest_xp("Easy", 1) == 12)
    check("medium quest pays 25 quest experience at quest level 1",
          quests_module.quest_xp("Medium", 1) == 25)
    check("hard quest pays 50 quest experience at quest level 1",
          quests_module.quest_xp("Hard", 1) == 50)
    check("medium quest experience is a fight win's experience",
          quests_module.quest_xp("Medium", 1) == 20 + 5 * 1)
    check("100 quest experience to reach quest level 2",
          quests_module.quest_xp_to_next(1) == 100)
    check("200 quest experience to reach quest level 3",
          quests_module.quest_xp_to_next(2) == 200)
    check("quest level line says the level and the experience to the next",
          quests_module.quest_level_line(
              {"quest_level": 1, "quest_xp": 60})
          == "Quest level 1, 40 quest experience to level 2. "
             "My quest level adds 1 percent to Charm, Renown "
             "and Insight.")
    check("charm line says what one more point does",
          quests_module.quest_stat_line(
              {"quest_stats": {"charm": 2, "renown": 0, "insight": 0}},
              "charm")
          == "Charm, 2. Quests pay 11 percent more credits, "
             "1 from my quest level. One more point adds 5 percent.")
    check("renown line says the chance",
          quests_module.quest_stat_line(
              {"quest_stats": {"charm": 0, "renown": 10, "insight": 0}},
              "renown")
          == "Renown, 10. 100 percent chance of 1 bonus reputation "
             "when a quest finishes, 1 from my quest level. "
             "One more point adds 10 percent.")

    fighter = game_logic.new_fighter("Bolt", "robot")
    fighter["credits"] = 100
    fighter["player_code"] = "4242"
    server = {"fighter": copy.deepcopy(fighter),
              "board": quests_module.starting_board(random.Random(7)),
              "done": [], "rep": {}, "active": None,
              "joined": [], "gift_pending": None, "calls": []}

    def _fighter_out():
        return copy.deepcopy(server["fighter"])

    def _fake_get_quests(config):
        server["calls"].append("get_quests")
        return {"fighter": _fighter_out(), "quests": copy.deepcopy(server["board"]),
                "active": copy.deepcopy(server["active"]),
                "reputation": dict(server["rep"]),
                "gift_pending": copy.deepcopy(server["gift_pending"])}, None

    def _fake_new_quest(config):
        server["calls"].append("new_quest")
        # Finished quest ids are never dealt again: the real
        # server only ever deals a fresh quest, and the
        # client treats a finished id on the board as stale
        # and drops it, so re-dealing one would kill the loop.
        # The quest is dealt at the fighter's quest level
        # (Phase 26), so its duration grows with it.
        ids = [q["id"] for q in server["board"]] + list(server["done"])
        names = [q["name"] for q in server["board"]]
        coop_ok = not any(q.get("coop") for q in server["board"])
        quest = quests_module.generate_quest(
            random.Random(len(ids)), None, ids,
            coop_allowed=coop_ok, existing_names=names,
            quest_level=server["fighter"].get("quest_level", 1))
        server["board"].append(quest)
        return {"fighter": _fighter_out(), "quest": copy.deepcopy(quest)}, None

    def _fake_start_quest(config, quest_id):
        server["calls"].append("start_quest")
        quest = next((q for q in server["board"] if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        if quest_id in server["done"]:
            return {}, "You already finished that quest."
        if server["active"] is not None:
            if server["active"]["id"] == quest_id:
                if server["active"].get("paused"):
                    # Paused (Phase 22): resume from the frozen
                    # remaining time, not the old finish time.
                    remaining = server["active"].get(
                        "remaining_seconds",
                        max(0.0, server["active"]["finish_at"] - time.time()))
                    resumed = copy.deepcopy(server["active"])
                    resumed["finish_at"] = time.time() + remaining
                    resumed["paused"] = False
                    resumed.pop("remaining_seconds", None)
                    server["active"] = resumed
                    return {"fighter": _fighter_out(),
                            "quest": copy.deepcopy(resumed)}, None
                return {"fighter": _fighter_out(),
                        "quest": copy.deepcopy(server["active"])}, None
            return {}, "You already have a quest going."
        if quest.get("coop") and quest_id not in server["joined"]:
            return {}, "Join the Grand Hangout Fair first, then start it."
        started = copy.deepcopy(quest)
        started["started_at"] = time.time()
        started["finish_at"] = started["started_at"] + started["duration_minutes"] * 60
        server["active"] = started
        return {"fighter": _fighter_out(), "quest": copy.deepcopy(started)}, None

    def _fake_pause_quest(config):
        server["calls"].append("pause_quest")
        active = server["active"]
        if active is None:
            return {"fighter": _fighter_out(), "quest": None}, None
        if active.get("paused"):
            return {"fighter": _fighter_out(),
                    "quest": copy.deepcopy(active),
                    "remaining_seconds": active.get("remaining_seconds", 0)}, None
        remaining = max(0.0, active["finish_at"] - time.time())
        active["paused"] = True
        active["remaining_seconds"] = remaining
        return {"fighter": _fighter_out(),
                "quest": copy.deepcopy(active),
                "remaining_seconds": remaining}, None

    def _fake_join_quest(config, quest_id):
        server["calls"].append("join_quest")
        quest = next((q for q in server["board"] if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        if not quest.get("coop"):
            return {}, "That quest is solo. You do not need to join it."
        if quest_id not in server["joined"]:
            server["joined"].append(quest_id)
        return {"fighter": _fighter_out(), "quest": copy.deepcopy(quest),
                "message": "You joined the Grand Hangout Fair."}, None

    def _fake_complete_quest(config, quest_id):
        server["calls"].append("complete_quest")
        quest = next((q for q in server["board"] if q["id"] == quest_id), None)
        if quest is None:
            return {}, "That quest is not on your board."
        if quest_id in server["done"]:
            return {}, "You already finished that quest."
        active = server["active"]
        if active is None or active["id"] != quest_id:
            return {}, "Start that quest in the hangout first."
        if active.get("paused") and active.get("remaining_seconds", 0) > 0:
            return {}, "That quest is paused."
        if active["finish_at"] > time.time():
            return {}, "That quest is not done yet."
        # Never check repairs here, exactly like the server.
        giver = quest["giver"]
        # Quest growth (Phase 26), same rules as the migration:
        # credits are keyed to the quest level, not the fighter
        # level, and the automatic bonus (+1% per quest
        # level) stacks with Charm, Renown and Insight.
        # Quest XP levels up at 100 x quest level, banking 1 point.
        qstats = server["fighter"].get("quest_stats", {}) or {}
        charm = qstats.get("charm", 0)
        renown = qstats.get("renown", 0)
        insight = qstats.get("insight", 0)
        qlevel = server["fighter"].get("quest_level", 1)
        auto = max(0, qlevel)
        bonus_rep = 1 if random.random() < min(1.0, renown * 0.10 + auto * 0.01) else 0
        rep_before = server["rep"].get(giver, 0)
        rep_after = rep_before + 1 + bonus_rep
        server["rep"][giver] = rep_after
        reward = quests_module.quest_reward(
            quest["difficulty"], qlevel)
        if rep_before >= 3:
            reward = int(reward * 1.25)
        reward = int(reward * (1 + 0.05 * charm + 0.01 * auto))
        server["fighter"]["credits"] += reward
        qxp = server["fighter"].get("quest_xp", 0)
        qpoints = server["fighter"].get("quest_points", 0)
        xp_earned = int(quests_module.quest_xp(
            quest["difficulty"], qlevel) * (1 + 0.05 * insight + 0.01 * auto))
        qxp += xp_earned
        level_ups = 0
        while qxp >= quests_module.quest_xp_to_next(qlevel):
            qxp -= quests_module.quest_xp_to_next(qlevel)
            qlevel += 1
            qpoints += 1
            level_ups += 1
        server["fighter"]["quest_level"] = qlevel
        server["fighter"]["quest_xp"] = qxp
        server["fighter"]["quest_points"] = qpoints
        quest_xp_line = (
            "You earned %s quest experience, Bolt. You have %s quest "
            "experience now, %s more to reach quest level %s."
            % (xp_earned, qxp,
               quests_module.quest_xp_to_next(qlevel) - qxp, qlevel + 1))
        quest_level_line = None
        if level_ups > 0:
            quest_level_line = (
                "You're now quest level %s, Bolt! You have %s quest %s to spend."
                % (qlevel, qpoints,
                   "point" if qpoints == 1 else "points"))
        server["board"] = [q for q in server["board"] if q["id"] != quest_id]
        server["done"].append(quest_id)
        server["active"] = None
        tier_line = None
        if rep_before < 3 and rep_after >= 3:
            tier_line = ("%s says: Three jobs done, Bolt, and not one of "
                         "them sloppy. You're a helper now, and my quests "
                         "pay a little extra for you." % giver)
        elif rep_before < 8 and rep_after >= 8:
            tier_line = ("%s says: Eight jobs done, Bolt. You're a friend "
                         "now, and friends get looked after. Pick a free "
                         "upgrade: your weapon or your armor." % giver)
            server["gift_pending"] = {"giver": giver, "tier": "Friend"}
        elif rep_before < 15 and rep_after >= 15:
            heal = server["fighter"].get("healing_level", 0)
            if heal < 5:
                server["fighter"]["healing_level"] = heal + 1
                tier_line = ("%s says: Fifteen jobs done, Bolt. You're "
                             "family now. Let me patch up that healing skill "
                             "of yours — on the house. Healing is now level "
                             "%s." % (giver, heal + 1))
        return {"fighter": _fighter_out(), "quest": copy.deepcopy(quest),
                "credits": reward,
                "message": "Quest done, Bolt! Thank you — you earned %s credits." % reward,
                "tier_line": tier_line, "giver": giver,
                "giver_voice": quest["giver_voice"],
                "reputation": dict(server["rep"]),
                "gift_pending": copy.deepcopy(server["gift_pending"]),
                "quest_xp_earned": xp_earned,
                "quest_level": qlevel,
                "quest_xp": qxp,
                "quest_xp_to_next":
                    quests_module.quest_xp_to_next(qlevel) - qxp,
                "quest_points": qpoints,
                "quest_level_ups": level_ups,
                "bonus_reputation": bonus_rep,
                "quest_xp_line": quest_xp_line,
                "quest_level_line": quest_level_line}, None

    def _fake_spend_quest_stat(config, stat):
        server["calls"].append("spend_quest_stat")
        # Like the real online_save wrapper, this returns
        # (fighter, message, messages, error), not the
        # two-value rpc shape.
        if stat not in ("charm", "renown", "insight"):
            return _fighter_out(), None, [], \
                "Pick charm, renown, or insight."
        points = server["fighter"].get("quest_points", 0)
        if points <= 0:
            return _fighter_out(), None, [], \
                "I have no quest points to spend right now."
        qstats = server["fighter"].setdefault(
            "quest_stats", {"charm": 0, "renown": 0, "insight": 0})
        if qstats.get(stat, 0) >= 10:
            return _fighter_out(), None, [], \
                "%s is already at its best, level 10." % stat.capitalize()
        qstats[stat] = qstats.get(stat, 0) + 1
        server["fighter"]["quest_points"] = points - 1
        value = qstats[stat]
        if stat == "charm":
            line = ("Charm is now %s. Quests pay %s percent more credits."
                    % (value, value * 5))
        elif stat == "renown":
            line = ("Renown is now %s. %s percent chance of 1 bonus "
                    "reputation when a quest finishes."
                    % (value, value * 10))
        else:
            line = ("Insight is now %s. Quests pay %s percent more "
                    "quest experience." % (value, value * 5))
        if points - 1 > 0:
            line += " I have %s quest %s left." % (
                points - 1, "point" if points - 1 == 1 else "points")
        else:
            line += " That was your last quest point."
        return _fighter_out(), line, [], None

    def _fake_choose_gift(config, slot):
        server["calls"].append("choose_gift")
        if server["gift_pending"] is None:
            return {}, "No free gift is waiting for you right now."
        giver = server["gift_pending"]["giver"]
        server["fighter"][slot + "_level"] += 1
        server["gift_pending"] = None
        return {"fighter": _fighter_out(),
                "message": "%s gave you a free %s upgrade." % (giver, slot)}, None

    def _fake_state(config):
        return _fighter_out(), [], None

    _online_save.get_quests = _fake_get_quests
    _online_save.new_quest = _fake_new_quest
    _online_save.start_quest = _fake_start_quest
    _online_save.join_quest = _fake_join_quest
    _online_save.complete_quest = _fake_complete_quest
    _online_save.pause_quest = _fake_pause_quest
    _online_save.choose_quest_gift = _fake_choose_gift
    _online_save.spend_quest_stat = _fake_spend_quest_stat
    _online_save.refresh_state = _fake_state
    _online_save.heartbeat = lambda *args, **kwargs: True
    _online_save.sign_out = lambda *args, **kwargs: True
    _online_save.log_action = lambda *args, **kwargs: True

    frame = main.MainFrame(
        fighter,
        online_config={"url": "https://example.supabase.co",
                       "key": "sb_publishable_fake", "session": "a" * 64},
        player_account={"username": "Bolt", "player_code": "4242"},
    )
    frame.notebook.SetSelection(3)  # More tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    frame.refresh_list("More")
    more_box = frame.lists["More"]
    more_box.SetSelection(frame.list_items("More").index("Visit the hangout"))
    frame.activate_current()
    # Visit must rewrite the visible list at once (2026-11-18,
    # Makenna): the old code never refreshed it, so the player
    # kept seeing the pre-hangout list with no Start anywhere,
    # even though list_items() already offered it. Check the
    # visible ListBox, not just list_items() — that is how
    # this bug slipped past the old check.
    visible = [more_box.GetString(i) for i in range(more_box.GetCount())]
    check("visiting the hangout shows Start quests in the visible list",
          any(item.startswith("Start quests") for item in visible))
    check("visiting the hangout lands the selection on Start quests",
          more_box.GetString(more_box.GetSelection()).startswith("Start quests"))
    check("entering the hangout starts no music yet",
          frame.sounds.current_music_track is None)
    check("entering the hangout does not promise music before Start",
          "listen to the music" not in frame.message_line.GetLabel()
          and "music starts when you press Start" in frame.message_line.GetLabel())

    # Start with Enter on the visible Start item.
    frame.activate_current()
    check("Enter on Start quests starts quests",
          frame._quests_active is True)
    # The quest-start announcement says "about" once, not
    # twice: format_time already says "about 9 minutes", so
    # the line must not add another "about" on top of it
    # (Makenna, live test 2026-11-18: "about about 9 minutes").
    check("the quest-start announcement never says about about",
          "about about" not in frame.message_line.GetLabel())
    check("the quest-start announcement still says how long it takes",
          "That'll take about" in frame.message_line.GetLabel())
    check("starting quests starts the hangout music",
          frame.sounds.current_music_track == "hangout")
    check("the starting board has 5 quests",
          len(frame._quest_board) == 5)
    check("the starting board is 2 easy, 2 medium, 1 hard",
          sorted(q["difficulty"] for q in frame._quest_board)
          == ["Easy", "Easy", "Hard", "Medium", "Medium"])
    check("the starting board mixes male and female givers",
          len({q["giver_gender"] for q in frame._quest_board}) == 2)
    check("at most one co-op quest is on the board",
          sum(1 for q in frame._quest_board if q.get("coop")) <= 1)
    check("a quest is running after Start",
          frame._quest_current is not None)
    first_id = frame._quest_current["id"]
    first_giver = frame._quest_current["giver"]

    # The 5-minute progress update, spoken by the giver.
    frame._quest_current["started_at"] = time.time() - 600
    frame._quest_current["finish_at"] = time.time() + 600
    frame._quest_last_progress_at = time.time() - 301
    frame.on_tick(mock.MagicMock())
    check("a progress update is spoken every 5 minutes",
          "percent done" in frame.message_line.GetLabel())
    # The progress update says "about" once, not twice, for
    # the same reason as the start line above.
    check("a progress update never says about about",
          "about about" not in frame.message_line.GetLabel())

    # The same update, while repairing, says the fighter is
    # repairing and how long repairs have left — and when
    # not repairing, it says nothing about repairs at all.
    fighter["repair_until"] = time.time() + 600
    server["fighter"]["repair_until"] = fighter["repair_until"]
    frame._quest_last_progress_at = time.time() - 301
    frame.on_tick(mock.MagicMock())
    check("a progress update while repairing says so",
          "still repairing" in frame.message_line.GetLabel())
    check("a progress update while repairing says how long is left",
          "left" in frame.message_line.GetLabel())
    fighter["repair_until"] = 0
    server["fighter"]["repair_until"] = 0
    frame._quest_last_progress_at = time.time() - 301
    frame.on_tick(mock.MagicMock())
    check("a progress update while not repairing says nothing about repairs",
          "repairing" not in frame.message_line.GetLabel())

    # Finish the quest: the server pays, the quest leaves
    # the board, reputation grows, and the next quest starts.
    credits_before = fighter["credits"]
    frame._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    frame.on_tick(mock.MagicMock())
    check("a finished quest pays credits",
          fighter["credits"] > credits_before)
    check("a finished quest leaves the board",
          all(q["id"] != first_id for q in frame._quest_board))
    check("finishing a quest builds reputation with its giver",
          frame._quest_rep.get(first_giver) == 1)
    check("the next quest starts at once, endlessly",
          frame._quest_current is not None
          and frame._quest_current["id"] != first_id)
    check("the music stays on across quests",
          frame.sounds.current_music_track == "hangout")

    # The reputation line itself: gain, new total, and how
    # far to the next tier — or the top tier, when there is
    # no next tier. (The spoken line is checked with the
    # voice on in game_action_speech_test; here the words
    # are checked, because without a voice the next quest's
    # line overwrites the message line at once.)
    check("reputation line says the gain, total and distance to Helper",
          quests_module.reputation_line("Bolt", 1, fighter_name="Bolt") ==
          "You gained 1 reputation with me, Bolt — thank you! "
          "You have 1 reputation with me now, 2 more to reach Helper.")
    check("reputation line says 1 more at the edge of a tier",
          quests_module.reputation_line("Bolt", 2, fighter_name="Bolt") ==
          "You gained 1 reputation with me, Bolt — thank you! "
          "You have 2 reputation with me now, 1 more to reach Helper.")
    check("reputation line at the top tier says so, with no cap",
          quests_module.reputation_line("Bolt", 15, fighter_name="Bolt") ==
          "You gained 1 reputation with me, Bolt — thank you! "
          "You have 15 reputation with me now. That is the top tier, "
          "Trusted Friend, and your reputation keeps building with "
          "no cap.")
    check("reputation line leaves the name out when it has none",
          quests_module.reputation_line("Bolt", 1) ==
          "You gained 1 reputation with me — thank you! "
          "You have 1 reputation with me now, 2 more to reach Helper.")
    check("next tier after Helper is Friend at 8",
          quests_module.next_tier(3) == (8, "Friend"))
    check("no next tier at or past Trusted Friend",
          quests_module.next_tier(15) is None)

    # A stale quest on the board must not kill the loop:
    # mark the next board quest after the current one as
    # already finished on the server, then finish the
    # current quest. The loop must skip the stale one and
    # start the one after it, without stopping.
    stale_id = frame._quest_board[1]["id"]
    server["done"].append(stale_id)
    frame._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    frame.on_tick(mock.MagicMock())
    check("a stale board quest does not stop the loop",
          frame._quests_active is True)
    check("the loop skips the stale quest",
          frame._quest_current is not None
          and frame._quest_current["id"] != stale_id)
    check("the stale quest leaves the board",
          all(q["id"] != stale_id for q in frame._quest_board))

    # Find me another quest: one fresh quest, never a repeat.
    board_before = len(frame._quest_board)
    frame.find_another_quest()
    check("find me another quest adds one fresh quest",
          len(frame._quest_board) == board_before + 1)

    # Stop: the loop stops, the music stops, and the quest
    # stays saved on the server, its remaining time frozen.
    # Time away must not eat the quest: pretend 10 minutes
    # passed while stopped, so the old finish time is now
    # in the past, then start again with S.
    saved_id = frame._quest_current["id"]
    remaining_at_stop = frame._quest_current["finish_at"] - time.time()
    frame.stop_quests()
    check("stopping quests stops the loop", frame._quests_active is False)
    check("stopping quests stops the music",
          frame.sounds.current_music_track is None)
    check("stopping quests keeps the quest saved on the server",
          server["active"] is not None and server["active"]["id"] == saved_id)
    check("stopping quests pauses the quest on the server",
          server["active"].get("paused") is True)
    check("stopping quests freezes the remaining time",
          abs(server["active"]["remaining_seconds"] - remaining_at_stop) < 5)
    server["active"]["finish_at"] = time.time() - 600
    # Start again with S, the way a player does it: the
    # key handler only runs when a list box has focus, so
    # point the stand-in focus at the More list first.
    sys.modules["wx"].Window.FindFocus = staticmethod(lambda: more_box)
    frame.on_key(types.SimpleNamespace(GetKeyCode=lambda: ord("s")))
    sys.modules["wx"].Window.FindFocus = staticmethod(lambda: None)
    check("pressing S starts quests again",
          frame._quests_active is True)
    check("starting again picks up the saved quest",
          frame._quest_current["id"] == saved_id)
    check("starting again resumes it from the frozen remaining time",
          abs((frame._quest_current["finish_at"] - time.time())
              - remaining_at_stop) < 5)
    check("starting again clears the pause",
          server["active"].get("paused") is not True)

    # Leaving the hangout to fight, then coming back, must
    # also freeze and resume the quest — not lose its time.
    remaining_at_leave = frame._quest_current["finish_at"] - time.time()
    frame.notebook.SetSelection(0)  # Home tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    check("leaving the hangout stops the quest loop",
          frame._quests_active is False)
    check("leaving the hangout pauses the quest on the server",
          server["active"] is not None
          and server["active"].get("paused") is True)
    check("leaving the hangout freezes the remaining time",
          abs(server["active"]["remaining_seconds"] - remaining_at_leave) < 5)
    server["active"]["finish_at"] = time.time() - 600
    frame.notebook.SetSelection(3)  # More tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    frame.refresh_list("More")
    more_box.SetSelection(frame.list_items("More").index("Visit the hangout"))
    frame.activate_current()
    frame.activate_current()  # Enter on Start quests
    check("coming back resumes the same quest",
          frame._quest_current is not None
          and frame._quest_current["id"] == saved_id)
    check("coming back does not lose quest time",
          abs((frame._quest_current["finish_at"] - time.time())
              - remaining_at_leave) < 5)

    # Quests work while repairing: a fighter at 1 health,
    # mid-repair, still starts and finishes quests.
    server["fighter"]["repair_until"] = time.time() + 600
    server["fighter"]["hp"] = 1
    fighter["repair_until"] = time.time() + 600
    fighter["hp"] = 1
    frame._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    credits_before = fighter["credits"]
    frame.on_tick(mock.MagicMock())
    check("a quest completes while repairing",
          fighter["credits"] > credits_before)
    check("repairing does not stop the quest loop",
          frame._quests_active is True)

    # Reputation gifts: 8 finished quests for one giver
    # waits a free weapon-or-armor gift, chosen by the player.
    giver = frame._quest_current["giver"]
    server["rep"][giver] = 7
    frame._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    frame.on_tick(mock.MagicMock())
    check("8 finished quests waits a free gift",
          frame._quest_gift_pending is not None
          and frame._quest_gift_pending["giver"] == giver)
    check("the gift is offered as a choice, weapon or armor",
          any(item.startswith("Choose my free gift: weapon")
              for item in frame.list_items("More"))
          and any(item.startswith("Choose my free gift: armor")
                  for item in frame.list_items("More")))
    weapon_before = fighter["weapon_level"]
    frame.choose_quest_gift("weapon")
    check("the free gift is instant, a weapon level at once",
          fighter["weapon_level"] == weapon_before + 1)
    check("taking the gift clears it",
          frame._quest_gift_pending is None)

    # Trusted Friend: 15 finished quests gives a free
    # Healing level, never past level 5.
    giver = frame._quest_current["giver"]
    server["rep"][giver] = 14
    server["fighter"]["healing_level"] = 0
    fighter["healing_level"] = 0
    frame._quest_current["finish_at"] = time.time() - 1
    server["active"]["finish_at"] = time.time() - 1
    frame.on_tick(mock.MagicMock())
    check("15 finished quests gives a free Healing level",
          fighter.get("healing_level") == 1)

    # Quest levels (Phase 23): separate from combat. Record
    # what the giver announces, so the completion lines can
    # be checked word-for-word even though the next quest's
    # line overwrites the message line at once.
    spoken_lines = []
    _real_announce_as = frame.announce_as

    def _record_announce_as(text, voice_name=None):
        spoken_lines.append(text)
        return _real_announce_as(text, voice_name)

    frame.announce_as = _record_announce_as

    def _finish_current_quest():
        quest = frame._quest_current
        frame._quest_current["finish_at"] = time.time() - 1
        server["active"]["finish_at"] = time.time() - 1
        frame.on_tick(mock.MagicMock())
        return quest

    def _set_quest_state(level=1, xp=0, points=0, stats=None):
        server["fighter"]["quest_level"] = level
        server["fighter"]["quest_xp"] = xp
        server["fighter"]["quest_points"] = points
        server["fighter"]["quest_stats"] = dict(
            stats or {"charm": 0, "renown": 0, "insight": 0})

    # Start the quest-level checks from a clean slate, on
    # both the server and the local fighter (earlier quests
    # in this test already earned quest experience).
    _set_quest_state()
    fighter["quest_level"] = 1
    fighter["quest_xp"] = 0
    fighter["quest_points"] = 0
    fighter["quest_stats"] = {"charm": 0, "renown": 0, "insight": 0}

    # The Home tab shows the quest level next to the fighter
    # level, and the hangout list shows the quest level, the
    # quest XP to the next level, the banked quest points,
    # and the three quest stat lines — next to the board.
    check("the Home tab shows the quest level line",
          "Quest level 1, 100 quest experience to level 2. "
          "My quest level adds 1 percent to Charm, Renown "
          "and Insight."
          in frame.list_items("Home"))
    check("the hangout list shows the quest level and the experience to the next",
          "Quest level 1, 100 quest experience to level 2. "
          "My quest level adds 1 percent to Charm, Renown "
          "and Insight."
          in frame.list_items("More"))
    check("the hangout list shows the banked quest points",
          "I have no quest points to spend right now."
          in frame.list_items("More"))
    check("the hangout list shows the three quest stat lines",
          any(item.startswith("Charm,") for item in frame.list_items("More"))
          and any(item.startswith("Renown,") for item in frame.list_items("More"))
          and any(item.startswith("Insight,") for item in frame.list_items("More")))
    check("the fighter status says the quest level too",
          "Quest level 1, 100 quest experience to level 2."
          in game_logic.status_text(fighter))

    # Finishing a quest earns quest XP for its difficulty,
    # and combat XP, combat level and max HP are untouched.
    _set_quest_state()
    combat_xp_before = fighter["xp"]
    combat_level_before = fighter["level"]
    max_hp_before = fighter["max_hp"]
    quest = frame._quest_current
    expected_xp = quests_module.quest_xp(quest["difficulty"], 1)
    _finish_current_quest()
    check("finishing a quest earns the right quest experience",
          fighter.get("quest_xp") == expected_xp)
    check("quests do not touch combat experience",
          fighter["xp"] == combat_xp_before)
    check("quests do not touch the combat level",
          fighter["level"] == combat_level_before)
    check("quests do not give max health",
          fighter["max_hp"] == max_hp_before)
    check("finishing a quest announces the quest experience earned",
          any("You earned %s quest experience" % expected_xp in line
              for line in spoken_lines))
    check("finishing a quest announces the experience to the next quest level",
          any("more to reach quest level 2" in line for line in spoken_lines))

    # Quest XP levels up at 100 x quest level, banking 1
    # quest point, and the level-up line is announced.
    _set_quest_state(xp=90)
    quest = frame._quest_current
    expected_xp = quests_module.quest_xp(quest["difficulty"], 1)
    total = 90 + expected_xp
    _finish_current_quest()
    check("quest experience levels up at 100 times the quest level",
          fighter.get("quest_level") == 2
          and fighter.get("quest_xp") == total - 100)
    check("a quest level-up banks 1 quest point",
          fighter.get("quest_points") == 1)
    check("a quest level-up is announced",
          any("You're now quest level 2, Bolt! You have 1 quest point to spend."
              in line for line in spoken_lines))

    # Charm: +5% quest credits per point.
    _set_quest_state(stats={"charm": 2, "renown": 0, "insight": 0})
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    credits_before = fighter["credits"]
    expected_credits = int(quests_module.quest_reward(
        quest["difficulty"],
        server["fighter"].get("quest_level", 1)) * 1.10)
    _finish_current_quest()
    check("charm boosts quest credits by 5 percent a point",
          fighter["credits"] - credits_before == expected_credits)

    # Insight: +5% quest XP per point.
    _set_quest_state(stats={"charm": 0, "renown": 0, "insight": 2})
    quest = frame._quest_current
    expected_xp = int(quests_module.quest_xp(
        quest["difficulty"], 1) * 1.10)
    _finish_current_quest()
    check("insight boosts quest experience by 5 percent a point",
          fighter.get("quest_xp") == expected_xp)

    # Renown at 10 points: every finished quest earns +1
    # bonus reputation, announced by name.
    _set_quest_state(stats={"charm": 0, "renown": 10, "insight": 0})
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    _finish_current_quest()
    check("renown at 10 points earns bonus reputation every time",
          frame._quest_rep.get(quest["giver"]) == 2)
    check("bonus reputation is announced",
          any("Bonus reputation, Bolt — thank you!" in line
              for line in spoken_lines))
    check("the reputation line says 2 gained when the bonus lands",
          quests_module.reputation_line(quest["giver"], 2, gained=2,
                                        fighter_name="Bolt")
          == "You gained 2 reputation with me, Bolt — thank you! "
             "You have 2 reputation with me now, 1 more to reach Helper.")
    # Renown at 0 points: no bonus, no announcement.
    _set_quest_state(stats={"charm": 0, "renown": 0, "insight": 0})
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    spoken_lines.clear()
    _finish_current_quest()
    check("renown at 0 points earns no bonus reputation",
          frame._quest_rep.get(quest["giver"]) == 1)
    check("no bonus reputation is announced without renown",
          not any("Bonus reputation" in line for line in spoken_lines))

    # Spending a quest point: Enter on a quest stat line
    # spends one banked point there, one at a time.
    _set_quest_state(points=1)
    frame.refresh_list("More")
    more_box.SetSelection(frame.list_items("More").index(
        next(item for item in frame.list_items("More")
             if item.startswith("Charm,"))))
    frame.activate_current()
    check("spending a quest point raises charm by 1",
          quests_module.quest_stats_of(fighter)["charm"] == 1)
    check("spending a quest point uses up the banked point",
          fighter.get("quest_points") == 0)
    check("the hangout list shows the spent point",
          any(item.startswith("Charm, 1.") for item in frame.list_items("More")))
    # A maxed quest stat refuses the point, and the point
    # stays banked. No points at all refuses too.
    server["fighter"]["quest_stats"] = {
        "charm": 10, "renown": 0, "insight": 0}
    server["fighter"]["quest_points"] = 1
    frame.refresh_list("More")
    more_box.SetSelection(frame.list_items("More").index(
        next(item for item in frame.list_items("More")
             if item.startswith("Charm,"))))
    frame.activate_current()
    check("a maxed quest stat refuses the point",
          quests_module.quest_stats_of(fighter)["charm"] == 10
          and fighter.get("quest_points") == 1)
    check("a maxed quest stat says so",
          "already at its best" in frame.message_line.GetLabel())
    server["fighter"]["quest_points"] = 0
    frame.refresh_list("More")
    more_box.SetSelection(frame.list_items("More").index(
        next(item for item in frame.list_items("More")
             if item.startswith("Renown,"))))
    frame.activate_current()
    check("spending with no quest points is refused",
          quests_module.quest_stats_of(fighter)["renown"] == 0)
    check("spending with no quest points says so",
          "no quest points to spend" in frame.message_line.GetLabel())

    # Quest growth (Phase 26): credits follow the quest
    # level, not the fighter level; the automatic bonus
    # applies and stacks with spent points; a quest dealt
    # at a higher quest level takes longer; pausing and
    # resuming still freeze the remaining time.
    _set_quest_state(level=1)
    fighter["level"] = 5
    server["fighter"]["level"] = 5
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    credits_before = fighter["credits"]
    expected_credits = quests_module.quest_reward(
        quest["difficulty"], 1)
    _finish_current_quest()
    check("quest credits follow the quest level, not the fighter level",
          fighter["credits"] - credits_before == expected_credits)
    _set_quest_state(level=5)
    fighter["level"] = 1
    server["fighter"]["level"] = 1
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    credits_before = fighter["credits"]
    expected_credits = int(quests_module.quest_reward(
        quest["difficulty"], 5) * 1.05)
    expected_xp = int(quests_module.quest_xp(
        quest["difficulty"], 5) * 1.05)
    _finish_current_quest()
    check("quest credits grow with the quest level",
          fighter["credits"] - credits_before == expected_credits)
    check("the automatic bonus adds quest experience too",
          fighter.get("quest_xp") == expected_xp)
    _set_quest_state(level=5,
                     stats={"charm": 2, "renown": 0, "insight": 2})
    quest = frame._quest_current
    server["rep"][quest["giver"]] = 0
    credits_before = fighter["credits"]
    expected_credits = int(quests_module.quest_reward(
        quest["difficulty"], 5) * 1.15)
    expected_xp = int(quests_module.quest_xp(
        quest["difficulty"], 5) * 1.15)
    _finish_current_quest()
    check("the automatic bonus stacks with spent charm points",
          fighter["credits"] - credits_before == expected_credits)
    check("the automatic bonus stacks with spent insight points",
          fighter.get("quest_xp") == expected_xp)
    _set_quest_state(level=5)
    frame.find_another_quest()
    dealt = frame._quest_board[-1]
    low, high = quests_module.DURATION_MINUTES[dealt["difficulty"]]
    scaled_low = min(240, int(low * 1.4))
    scaled_high = min(240, int(high * 1.4))
    check("a quest dealt at quest level 5 has a longer duration range",
          scaled_low <= dealt["duration_minutes"] <= scaled_high)
    # Pausing still freezes the remaining time at quest
    # level 5, with the longer durations.
    remaining_at_stop = frame._quest_current["finish_at"] - time.time()
    frame.stop_quests()
    check("stopping quests at quest level 5 freezes the remaining time",
          abs(server["active"]["remaining_seconds"] - remaining_at_stop) < 5)
    frame.start_quests()
    check("starting again at quest level 5 resumes the same quest",
          frame._quest_current is not None)
    check("starting again at quest level 5 does not lose quest time",
          abs((frame._quest_current["finish_at"] - time.time())
              - remaining_at_stop) < 5)

    # Quest ambience loops (Phase 23): while a quest runs,
    # a sound matching the kind of work plays in a loop on
    # its own channel, quieter than the music, under the
    # voice. It stops when the quest completes, stops,
    # pauses, or the player leaves the hangout. A quest
    # whose ambience file is not in sounds/ yet plays no
    # loop at all — the game carries on silently.
    import sounds as sounds_module
    check("every quest template names an ambience",
          all(q.get("ambience") in quests_module.AMBIENCES
              for q in quests_module.QUEST_TEMPLATES))
    check("cooking quests sizzle",
          quests_module.ambience_sound_name({"name": "Perfect the Recipe"})
          == "chef_sizzle")
    check("repair quests hum with a servo",
          quests_module.ambience_sound_name({"name": "Tune-Up Time"})
          == "robot_servo")
    check("gathering quests murmur like a market",
          quests_module.ambience_sound_name({"name": "Market Run"})
          == "ambience_gathering")
    check("cleaning quests scrub",
          quests_module.ambience_sound_name({"name": "The Great Oil Spill"})
          == "ambience_cleaning")
    check("a server-dealt quest finds its ambience by name",
          quests_module.quest_ambience({"name": "The Midnight Feast"})
          == "cooking")

    def _quest_for(name):
        template = next(
            t for t in quests_module.QUEST_TEMPLATES if t["name"] == name)
        giver = quests_module.GIVER_BY_NAME[template["giver"]]
        quest = {"id": "q_test_%s" % name.lower().replace(" ", "_")
                 .replace("'", ""),
                 "name": template["name"],
                 "description": template["description"],
                 "giver": giver["name"],
                 "giver_voice": giver["voice"],
                 "giver_gender": giver["gender"],
                 "difficulty": template["difficulty"],
                 "duration_minutes": 10,
                 "coop": False,
                 "ambience": template["ambience"]}
        server["board"].append(quest)
        return quest

    # Drive the loop: complete the quest already running and
    # let the loop start the next one from a board we control,
    # so each ambience is heard on a real quest start.
    cooking = _quest_for("Perfect the Recipe")
    frame._quest_board = [cooking]
    _finish_current_quest()
    check("starting a cooking quest starts the sizzle loop",
          frame.sounds.current_ambience == "chef_sizzle")
    check("the ambience loop is quieter than the music",
          frame.sounds._sounds["chef_sizzle"].volume
          == frame.sounds._volume * sounds_module.AMBIENCE_VOLUME_FACTOR)
    # Completing it starts the next quest on the board; make
    # that a gathering quest. Its file is in sounds/ now
    # (uploaded 2026-11-19, commit 01bd111), so the sizzle
    # loop must stop and the market loop must start instead
    # of the old loop carrying on into the new quest.
    gathering = _quest_for("Market Run")
    frame._quest_board = [gathering]
    _finish_current_quest()
    check("completing a quest stops its ambience loop",
          frame.sounds.current_ambience != "chef_sizzle")
    check("the next quest starts its own ambience loop",
          frame._quest_current is not None
          and frame._quest_current["name"] == "Market Run"
          and frame.sounds.current_ambience == "ambience_gathering")
    # A quest whose ambience file is not in sounds/ yet plays
    # no loop at all — the game carries on silently. Every
    # ambience file is in sounds/ now, so prove the rule at
    # the bank level instead: a bank with no files starts no
    # loop.
    import tempfile
    empty_bank = sounds_module.SoundBank(
        directory=tempfile.mkdtemp(),
        pygame_module=sys.modules["pygame"])
    empty_bank.load()
    check("a bank with no ambience file starts no loop",
          empty_bank.start_ambience("ambience_gathering") is False)
    repair = _quest_for("Tune-Up Time")
    frame._quest_board = [repair]
    _finish_current_quest()
    check("starting a repair quest starts the servo loop",
          frame.sounds.current_ambience == "robot_servo")
    frame._pause_current_quest()
    check("pausing a quest stops the ambience loop",
          frame.sounds.current_ambience is None)
    # Pausing leaves quests active, so resume through the
    # loop itself: it picks the paused quest back up.
    frame._begin_next_quest()
    check("resuming a repair quest restarts the servo loop",
          frame.sounds.current_ambience == "robot_servo")
    frame.notebook.SetSelection(0)  # Home tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    check("leaving the hangout stops the ambience loop",
          frame.sounds.current_ambience is None)
    # Back in the hangout, quests running again, so the rest
    # of the test (chef, close/reopen) finds a quest running.
    frame.notebook.SetSelection(3)  # More tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    frame.refresh_list("More")
    more_box.SetSelection(frame.list_items("More").index("Visit the hangout"))
    frame.activate_current()
    frame.start_quests()
    check("re-entering the hangout restarts the loop",
          frame._quests_active is True
          and frame._quest_current is not None)

    # A chef can do quests too: fighter kind never locks
    # anyone out. Start the same loop as a chef.
    chef = game_logic.new_fighter("Belle", "chef")
    chef["player_code"] = "4242"
    chef_frame = main.MainFrame(
        chef,
        online_config={"url": "https://example.supabase.co",
                       "key": "sb_publishable_fake", "session": "a" * 64},
        player_account={"username": "Belle", "player_code": "4242"},
    )
    chef_frame.notebook.SetSelection(3)
    chef_frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    chef_frame.refresh_list("More")
    chef_box = chef_frame.lists["More"]
    chef_box.SetSelection(chef_frame.list_items("More").index("Visit the hangout"))
    chef_frame.activate_current()
    chef_frame.start_quests()
    check("a chef can start quests too",
          chef_frame._quests_active is True
          and chef_frame._quest_current is not None)
    # Closing the game with a quest active freezes its
    # remaining time, and reopening resumes it from there.
    closer_id = frame._quest_current["id"]
    remaining_at_close = frame._quest_current["finish_at"] - time.time()
    frame.on_close(mock.MagicMock())
    check("closing the game pauses the quest on the server",
          server["active"] is not None
          and server["active"].get("paused") is True)
    check("closing the game freezes the remaining time",
          abs(server["active"]["remaining_seconds"] - remaining_at_close) < 5)
    reopened = main.MainFrame(
        fighter,
        online_config={"url": "https://example.supabase.co",
                       "key": "sb_publishable_fake", "session": "a" * 64},
        player_account={"username": "Bolt", "player_code": "4242"},
    )
    reopened.notebook.SetSelection(3)  # More tab
    reopened.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    reopened.refresh_list("More")
    reopen_box = reopened.lists["More"]
    reopen_box.SetSelection(
        reopened.list_items("More").index("Visit the hangout"))
    reopened.activate_current()
    reopened.start_quests()
    check("reopening resumes the same quest",
          reopened._quest_current is not None
          and reopened._quest_current["id"] == closer_id)
    check("reopening does not lose quest time",
          abs((reopened._quest_current["finish_at"] - time.time())
              - remaining_at_close) < 5)
    reopened.on_close(mock.MagicMock())
    chef_frame.on_close(mock.MagicMock())
    frame.on_close(mock.MagicMock())
    print("\nAll hangout quest tests passed.")


def npc_test():
    """More creatures (Phase 24): the 9 draft NPCs are real
    fightable opponents alongside Scrap Rat, each with its
    own appear and hit sounds, scaled to the fighter's level
    so fights stay fair, and a missing sound file never
    crashes a fight. The upgrade rule is checked in
    main_test; the free quest gift is instant by design, so
    it needs no timer and cannot corrupt a running set."""
    import re
    import tempfile
    import sounds as sounds_module

    # The table: 9 NPCs, none of them Scrap Rat, each with
    # its own ability and its own two sounds.
    check("there are nine new creatures besides scrap rat",
          len(game_logic.NPCS) == 9 and "scrap_rat" not in game_logic.NPCS)
    check("every creature has an appear and a hit sound",
          all(npc["appear_sound"] and npc["hit_sound"]
              for npc in game_logic.NPCS.values()))
    check("no two creatures share an appear sound",
          len({npc["appear_sound"]
               for npc in game_logic.NPCS.values()}) == 9)
    check("no two creatures share a hit sound",
          len({npc["hit_sound"]
               for npc in game_logic.NPCS.values()}) == 9)
    check("no creature uses a scrap rat sound",
          not any(npc["appear_sound"] in ("robot_servo", "chef_sizzle")
                  or npc["hit_sound"] in ("robot_clank", "pan_clang",
                                          "robot_laser", "chef_chop")
                  for npc in game_logic.NPCS.values()))
    check("every creature sound is in the sound bank",
          all(npc["appear_sound"] in sounds_module.SOUND_FILES
              and npc["hit_sound"] in sounds_module.SOUND_FILES
              for npc in game_logic.NPCS.values()))
    check("the fight pool is scrap rat plus the nine",
          set(game_logic.NPC_POOL)
          == {"scrap_rat"} | set(game_logic.NPCS))
    check("a random pick only ever names a real creature",
          all(game_logic.random_npc_id(random.Random(i))
              in game_logic.NPC_POOL for i in range(20)))
    check("a random pick sometimes picks a new creature",
          any(game_logic.random_npc_id(random.Random(i)) != "scrap_rat"
              for i in range(20)))
    check("unknown creature falls back to scrap rat",
          game_logic.creature_for_level(5, "not_a_creature")["name"]
          == "Scrap Rat")

    # A fight against every creature works, at low level,
    # mid level and high level, and stays fair: it ends,
    # it names the creature, and no single hit on the
    # fighter takes more than three quarters of the
    # fighter's health (the fairness guard).
    for npc_id in game_logic.NPC_ORDER:
        npc = game_logic.NPCS[npc_id]
        for level in (1, 10, 50):
            fighter = game_logic.new_fighter("Test", "robot")
            fighter["level"] = level
            fighter["weapon_level"] = level
            fighter["armor_level"] = level
            fighter["hp"] = game_logic.fighter_max_hp(fighter)
            fighter["credits"] = 0
            result = game_logic.fight(
                fighter, rng=random.Random(level * 7 + 1), npc_id=npc_id)
            max_hp = game_logic.fighter_max_hp(fighter)
            check("fight against %s at level %d ends"
                  % (npc["name"], level),
                  result["won"] is not None)
            check("fight against %s at level %d says the creature"
                  % (npc["name"], level),
                  npc["name"] in " ".join(result["lines"]))
            worst = 0
            for line in result["lines"]:
                for match in re.findall(r"hits me for (\d+)",
                                        line):
                    worst = max(worst, int(match))
            check("no hit from %s at level %d takes more than "
                  "three quarters of your health"
                  % (npc["name"], level),
                  worst <= 0.75 * max_hp)
        # Beating the creature pays its reward: a fight win
        # times the creature's factor.
        won = None
        for seed in range(5):
            fighter = game_logic.new_fighter("Test", "robot")
            fighter["level"] = 10
            fighter["weapon_level"] = 10
            fighter["armor_level"] = 10
            fighter["hp"] = game_logic.fighter_max_hp(fighter)
            result = game_logic.fight(fighter, rng=random.Random(seed),
                                      npc_id=npc_id)
            if result["won"]:
                won = result
                break
        check("beating %s pays the creature's reward" % npc["name"],
              won is not None
              and won["credits"]
              == int(round((10 + 5 * 10) * npc["reward_mult"]))
              and won["xp"]
              == int(round((20 + 5 * 10) * npc["reward_mult"])))

    # Every creature's ability actually fires in a fight:
    # a weak fighter (level 50, weapon and armor level 1)
    # keeps the fight going long enough for it to trigger.
    for npc_id in game_logic.NPC_ORDER:
        npc = game_logic.NPCS[npc_id]
        found = False
        for seed in range(10):
            fighter = game_logic.new_fighter("Test", "robot")
            fighter["level"] = 50
            fighter["weapon_level"] = 1
            fighter["armor_level"] = 1
            fighter["hp"] = game_logic.fighter_max_hp(fighter)
            result = game_logic.fight(fighter,
                                      rng=random.Random(100 + seed),
                                      npc_id=npc_id)
            if npc["ability_line"] in " ".join(result["lines"]):
                found = True
                break
        check("%s ability fires: %s" % (npc["name"], npc["ability_line"]),
              found)

    # A missing sound file never crashes a fight: the bank
    # plays nothing for a creature whose files are not there
    # yet, and the game still speaks its lines.
    empty_dir = tempfile.mkdtemp()
    empty_bank = sounds_module.SoundBank(
        directory=empty_dir, pygame_module=sys.modules["pygame"])
    empty_bank.load()
    for npc in game_logic.NPCS.values():
        check("missing %s appear plays nothing" % npc["name"],
              empty_bank.play(npc["appear_sound"]) is False)
        check("missing %s hit plays nothing" % npc["name"],
              empty_bank.play(npc["hit_sound"]) is False)
    frame = main.MainFrame(game_logic.new_fighter("Test", "robot"))
    frame.sounds = empty_bank
    frame.sound_on = True
    try:
        for npc_id in game_logic.NPC_ORDER:
            npc = game_logic.NPCS[npc_id]
            frame._play_sound_for_line(
                "A %s appears! Level 5." % npc["name"])
            frame._play_sound_for_line(
                "The %s hits me for 10." % npc["name"])
        no_crash = True
    except Exception:
        no_crash = False
    check("npc lines with no sound files do not crash", no_crash)

    # With the files there, each creature's lines play its
    # own sounds — and your own hit still plays the
    # fighter's sound, not the creature's.
    full_dir = tempfile.mkdtemp()
    for _name, (filename, _maxtime) in sounds_module.SOUND_FILES.items():
        with open(os.path.join(full_dir, filename), "wb") as handle:
            handle.write(b"fake-sound")
    full_bank = sounds_module.SoundBank(
        directory=full_dir, pygame_module=sys.modules["pygame"])
    full_bank.load()
    frame.sounds = full_bank
    frame.sound_on = True
    frame._play_sound_for_line("A Zip Scout appears! Level 5.")
    check("zip scout appear plays its own sound",
          full_bank._sounds["npc_zip_scout_appear"].played == 1)
    frame._play_sound_for_line("The Zip Scout hits me for 10.")
    check("zip scout hit plays its own sound",
          full_bank._sounds["npc_zip_scout_hit"].played == 1)
    frame._play_sound_for_line("I hit the Zip Scout for 10.")
    check("your own hit still plays the fighter's sound",
          full_bank._sounds["robot_laser"].played == 1)
    frame._play_sound_for_line("A Baker Belle appears! Level 5.")
    check("baker belle appear plays its own sound",
          full_bank._sounds["npc_baker_belle_appear"].played == 1)
    frame._play_sound_for_line("The Baker Belle hits me for 10.")
    check("baker belle hit plays its own sound",
          full_bank._sounds["npc_baker_belle_hit"].played == 1)
    frame._play_sound_for_line("A Scrap Rat appears! Level 5.")
    check("scrap rat appear still plays the fighter-kind sound",
          full_bank._sounds["robot_servo"].played == 1)
    print("\nAll creature tests passed.")


if __name__ == "__main__":
    main_test()
    quest_test()
    npc_test()
    currency_wording_test()
    voice_test()
    narration_test()
    game_action_speech_test()
    sounds_test()
    voice_failure_test()
    voice_playback_failure_test()
    phase27_voice_test()
    launch_update_test()
