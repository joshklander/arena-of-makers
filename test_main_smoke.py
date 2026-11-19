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
            messages.append("Repairs finished. Your fighter is back to full health.")
        return copy.deepcopy(server["fighter"]), messages, None

    def _fake_voice(config, gender):
        server["calls"].append("voice")
        server["fighter"]["gender"] = gender
        return copy.deepcopy(server["fighter"]), None

    _online_save.fight = _fake_fight
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

    # Enter on "Fight a Scrap Rat" runs a real fight and saves.
    frame.notebook.SetSelection(1)  # Combat tab
    combat_box = frame.lists["Combat"]
    combat_box.SetSelection(0)
    check("combat first item is the fight",
          combat_box.GetString(0).startswith("Fight a Scrap Rat"))
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

    # Music rule (2026-11-18): no music at launch, hangout
    # music only in the hangout, fight music only while
    # auto-fighting, and nothing for a manual fight.
    check("no music starts at launch",
          frame.sounds.current_music_track is None)
    frame.notebook.SetSelection(3)  # More tab
    frame.on_tab_changed(types.SimpleNamespace(Skip=lambda: None))
    frame.refresh_list("More")
    more_box = frame.lists["More"]
    more_box.SetSelection(frame.list_items("More").index("Visit the hangout"))
    frame.activate_current()
    check("entering the hangout starts the hangout music",
          frame.sounds.current_music_track == "hangout")
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
    frame.do_fight(idle=True)
    check("a failed idle fight turns auto-fighting off",
          frame.idle_fighting is False)
    check("a failed idle fight stops the music",
          frame.sounds.current_music_track is None)
    _online_save.fight = _fake_fight
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
    check("no bell left in main.py", "Bell" not in source)
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
    in plain words, the engine goes dead, and later lines are dropped
    with one log line instead of silence or a flood."""
    import importlib
    import voice_engine

    sys.modules["edge_tts"] = _make_failing_edge_tts()
    importlib.reload(voice_engine)

    voice = voice_engine.EdgeVoice(voice_engine.FEMALE_VOICE, lambda path: None)
    check("failing voice still starts its thread", voice.start() is True)
    voice.speak("This line will fail.")
    check("failed synthesis is logged in plain words",
          wait_for_log("the voice service failed (ConnectionError: test: no network)"))
    check("engine is dead after a failed synthesis", voice.available is False)
    before = LOG_CAPTURE.getvalue().count("Voice: not spoken")
    voice.speak("Another line.")
    voice.speak("And another.")
    time.sleep(0.5)
    check("dropped lines are logged once, not once per line",
          LOG_CAPTURE.getvalue().count("Voice: not spoken") == before + 1)
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
          any(line.startswith("You lost") and "credits" in line
              for line in spoken))
    print("    Spoken lines checked: %s" % spoken)

    # The window's lists, and the line spoken when you press
    # Enter on "You have no stat points to spend right now."
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
         if item.startswith("You have no stat points")][0])
    frame.activate_current()
    spoken_no_points = frame.message_line.GetLabel()
    check("no-points announce says stat points, not points",
          spoken_no_points ==
          "You have no stat points to spend right now. You get "
          "2 stat points every time you level up.")
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
    newest = open(os.path.join(mig_dir, names[-1]), encoding="utf-8").read()
    check("newest migration is the credits-wording fix",
          "fix_credits_wording" in names[-1])
    check("newest migration fixes the rename line",
          "Your balance is now in credits." in newest)
    check("newest migration never says points for the currency",
          "Your points are now called credits" not in newest)
    check("newest migration replaces apply_timers only",
          "create or replace function arena_private.apply_timers(" in newest
          and "set search_path = ''" in newest)
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
          list(frame._narration_queue) == lines[1:])

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
          frame._narration_queue[-1] == "Idle fighting off."
          and len(frame._narration_queue) >= 2)
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


if __name__ == "__main__":
    main_test()
    currency_wording_test()
    voice_test()
    narration_test()
    sounds_test()
    voice_failure_test()
    voice_playback_failure_test()
    launch_update_test()
