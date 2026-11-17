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
calling the real service, and proves a line reaches the player.
"""

import os
import sys
import time
import types
from unittest import mock

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


class _MediaCtrl(_Widget):
    """Stand-in for wx.media.MediaCtrl: records what would be played."""

    def __init__(self, *args, **kwargs):
        self.loaded = []
        self.played = 0

    def Load(self, path):
        self.loaded.append(path)
        return True

    def Play(self):
        self.played += 1
        return True

    def Stop(self):
        pass

    def Hide(self):
        pass

    def SetVolume(self, value):
        pass


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
    def ShowModal(self):
        return 1  # ID_OK

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
    wx.Timer = _Timer
    wx.Window = type("Window", (), {"FindFocus": staticmethod(lambda: None)})
    wx.Bell = lambda: None
    wx.MessageBox = lambda *args, **kwargs: None
    # CallAfter runs the call right away here: there is no real event loop.
    wx.CallAfter = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    wx.ID_OK = 1
    wx.OK = 1
    wx.CANCEL = 2
    wx.ICON_INFORMATION = 4
    wx.WXK_ESCAPE = 27
    wx.WXK_RETURN = 13
    wx.WXK_LEFT = 314
    wx.WXK_RIGHT = 316
    wx.LB_SINGLE = 1
    wx.TE_MULTILINE = 1
    wx.TE_READONLY = 2
    wx.TE_RICH2 = 4
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


def _make_media():
    media = types.ModuleType("wx.media")
    media.MediaCtrl = _MediaCtrl
    return media


sys.modules["wx"] = _make_wx()
sys.modules["wx.media"] = _make_media()
sys.modules["wx"].media = sys.modules["wx.media"]

import game_logic
import main


def check(name, condition):
    if not condition:
        raise AssertionError("FAILED: " + name)
    print("ok - " + name)


def main_test():
    fighter = game_logic.new_fighter("Bolt", "robot")
    fighter["points"] = 500
    frame = main.MainFrame(fighter)

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
    check("fight saved the game", os.path.exists(main.SAVE_PATH))
    loaded = game_logic.load_game(main.SAVE_PATH)
    check("saved fighter loads back", loaded is not None and loaded["name"] == "Bolt")

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
    check("upgrade targets the weapon", fighter["upgrade"]["slot"] == "weapon")

    # The one-second tick finishes the upgrade once its time is up.
    fighter["upgrade"]["finish"] = 0.0  # pretend the wait is over
    frame.on_tick(mock.MagicMock())
    check("tick finishes a ready upgrade", fighter["upgrade"] is None)
    check("weapon level rose after upgrade", fighter["weapon_level"] == 2)

    # The tick heals the fighter back to full health when repairs end.
    fighter["repair_until"] = time.time() - 10  # repair already over
    frame.was_repairing = True
    fighter["hp"] = 1
    frame.on_tick(mock.MagicMock())
    check("tick heals after repairs finish", fighter["hp"] == fighter["max_hp"])

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
    frame.announce("A quiet line.")
    check("announce still shows text without a voice",
          frame.message_line.GetLabel() == "A quiet line.")
    source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "main.py"), encoding="utf-8").read()
    check("no bell left in main.py", "Bell" not in source)
    check("no tone method left in main.py", "def tone" not in source)

    # Settings: Enter on the Voice item switches the voice and saves it.
    frame.notebook.SetSelection(4)  # Settings tab
    frame.refresh_list("Settings")
    settings_box = frame.lists["Settings"]
    check("settings first item is the voice",
          settings_box.GetString(0).startswith("Voice: Male"))
    settings_box.SetSelection(0)
    frame.activate_current()
    check("voice item switches to female", fighter["gender"] == "female")
    check("voice item saves the switch",
          game_logic.load_game(main.SAVE_PATH)["gender"] == "female")
    check("settings now shows female",
          frame.list_items("Settings")[0].startswith("Voice: Female"))
    frame.activate_current()
    check("voice item switches back to male", fighter["gender"] == "male")

    os.unlink(main.SAVE_PATH)
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
    check("female fighter gets the female voice",
          frame.voice.voice == voice_engine.FEMALE_VOICE)
    media = frame._media

    def last_spoken():
        try:
            with open(media.loaded[-1], "rb") as handle:
                return handle.read()
        except (IndexError, OSError):
            return b""

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
    if os.path.exists(main.SAVE_PATH):
        os.unlink(main.SAVE_PATH)
    print("\nAll voice smoke tests passed.")


if __name__ == "__main__":
    main_test()
    voice_test()
