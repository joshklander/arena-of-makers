"""Arena of Makers - first playable skeleton.

A wxPython desktop game, built the easy way Magic Worlds is built:
one screen, six tabs, one list on each tab. Move with the arrow keys,
press Enter to choose, Escape to stop or go back. A lowercase letter
does something once; Shift plus the same letter starts the idle loop.

    F         fight one creature (Combat tab)
    Shift+F   idle fighting on and off (Combat tab)
    U         upgrade weapon (Shop tab)
    A         upgrade armor (Shop tab)
    H         upgrade healing (Shop tab)
    Shift+U   max affordable weapon upgrade (Shop tab)
    Shift+A   max affordable armor upgrade (Shop tab)
    Shift+H   max affordable healing upgrade (Shop tab)
    R         hear repair status (More tab)
    S         start or stop quests (hangout, More tab)
    1 / 2     choose a free gift upgrade: weapon or armor (More tab)

Study tab: one button, "Enter study". Pressing it starts the
study: the music plays, spell learning starts on its own with
a spell picked at random, and study quests trigger on their
own. Spells are learned one at a time, never all of one
element first. Press S to stop study quests. Learning a spell
takes real time, like a quest: the clock only ticks while you
are in the study, and pauses when you leave.

Stats live on the Home tab, in the same list as the fighter
status: move with the arrow keys, press Enter on a stat to
spend one banked stat point. Stay on the same stat and press
Enter again to spend another point there. No new keys, no
new tabs, no new screens.

Run it with:  python main.py
It needs Python, wxPython, edge-tts and pygame. Arena of Makers is
online-only, and the server is the only judge of a fighter: every
fight, upgrade and timer runs on the Supabase server, through the
arena_* functions in supabase/migrations/. The game shows what the
server sends back, so changing the game cannot change a fighter.
Players sign in with a username, a player code and a password.
The password box hides what is typed, and the password is never
saved, logged or shown; the server keeps only a hash of it. The
game will not start without a .env file next to it holding
SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY, in the right shape: the
launch check in supabase_config.py says so in plain words when
something is missing or wrong, and never prints or logs the key.
No secret of any kind lives in the code: the repository is public,
and .env is ignored by git. If the game hits a problem, the details are
written to arena_log.txt next to this file, so nobody has to open
a command prompt to see what went wrong. A player can export
their own data at any time from the More tab: it writes a JSON
file next to the game with only that player's fighter and their
own game actions, never anyone else's.

Voice: narration is spoken with real Microsoft Edge text-to-speech
(the free edge-tts package, no key, no account). The player picks a
male voice (en-US-GuyNeural) or a female voice (en-US-AriaNeural) when
they create their fighter, and can change it later in Settings. Speech
never blocks the game: lines are made in the background and only the
newest one is spoken. If edge-tts is not installed, or the voice
service cannot be reached, the game carries on with text only and
writes one plain line to arena_log.txt saying why. For diagnosis the
game also logs every speak attempt there: which Python is running it,
whether edge-tts and pygame are installed, which voice and volume are set, whether
each line's sound file was made and how big it was, and whether the
player started playing it. Sound effects and music come only from
Pixabay and freesound.org, using material marked free to use; the
picks and their licences are listed in SOUNDS.md, and the files
live in sounds/ next to this file. The game runs fine with no sound
files at all.
"""

import logging
import os
import random
import sys
import time
import traceback

import wx

try:
    # Only the sound mixer is used, never pygame's own window.
    import pygame
except ImportError:
    # Without pygame the voice stays off and the game carries on with
    # text only.
    pygame = None

import account
import arena_of_makers_updater
import game_logic
import online_save
import quests
import remember
import sounds
import spells
import supabase_config
import voice_engine

APP_TITLE = "Arena of Makers"
LOG_PATH = os.path.join(supabase_config.app_folder(), "arena_log.txt")

# Where this copy of the game lives on disk: next to the .py
# files, or next to ArenaOfMakers.exe (see
# supabase_config.app_folder). The launch update check reads
# the version note from this folder.
GAME_DIR = supabase_config.app_folder()

# How long the launch update check waits for GitHub to
# answer, in seconds. Longer than this and the game just
# plays the current version: a slow check must never hold
# up starting the game.
UPDATE_CHECK_TIMEOUT_SECONDS = 10

# Idle fighting does one fight about every 5 seconds.
IDLE_FIGHT_GAP = 5

# How often the game tells the server this player is still
# online. The server counts a player as online for 2 minutes
# after their last check-in.
HEARTBEAT_GAP = 45

# Turn-by-turn narration: the pause, in seconds, between spoken
# round lines in a manual fight. The game's one-second timer is
# what advances the narration, so the real gap is about a second.
TURN_PAUSE_SECONDS = 0.8

# Hangout quests (Phase 18): how often the quest giver speaks
# a progress update while a quest runs, in seconds.
QUEST_PROGRESS_GAP = 300


def setup_logging():
    """Write a plain-text log next to the game, so a crash can be read
    from the log file instead of the command prompt."""
    logging.basicConfig(
        filename=LOG_PATH,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    logging.info("Arena of Makers started.")


def tell_player_about_log():
    """Plain-words message about the log file. Never let telling the
    player fail too: if there is no window to show it in, stay quiet
    and let the log file speak."""
    try:
        wx.MessageBox(
            "Arena of Makers hit a problem. The details were written to "
            "arena_log.txt, next to the game, so you can send that file "
            "to Muse to look at.",
            "Arena of Makers",
            wx.OK | wx.ICON_INFORMATION,
        )
    except Exception:
        pass


def log_uncaught(exc_type, exc_value, exc_tb):
    """Anything that escapes gets written to the log file, and the
    player is told where it is, in plain words."""
    logging.error(
        "The game hit a problem:", exc_info=(exc_type, exc_value, exc_tb)
    )
    tell_player_about_log()


class CreateFighterDialog(wx.Dialog):
    """First launch: pick robot, chef or witch, pick a voice, name the fighter."""

    def __init__(self, parent):
        super().__init__(parent, title="Create your fighter")
        self.kind = "robot"
        self.fighter_name = ""

        # The sizer lives on the dialog itself, with every control a
        # direct child of the dialog. CreateButtonSizer parents its
        # OK/Cancel buttons to the dialog, and wx requires every window
        # in a sizer to share the sizer's window as its parent: putting
        # the controls on a panel while the buttons belonged to the
        # dialog crashed at startup with a wx assertion error.
        sizer = wx.BoxSizer(wx.VERTICAL)

        hint = wx.StaticText(
            self,
            label="Welcome to Arena of Makers. Pick your fighter, then give them a name. A male witch is called a warlock.",
        )
        hint.Wrap(420)
        sizer.Add(hint, 0, wx.ALL, 10)

        self.kind_box = wx.RadioBox(
            self,
            label="Fighter type",
            choices=["Robot fighter", "Chef fighter", "Witch fighter"],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        sizer.Add(self.kind_box, 0, wx.ALL | wx.EXPAND, 10)

        self.gender_box = wx.RadioBox(
            self,
            label="Voice",
            choices=["Male voice", "Female voice"],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        sizer.Add(self.gender_box, 0, wx.ALL | wx.EXPAND, 10)

        sizer.Add(wx.StaticText(self, label="Fighter name:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.name_ctrl = wx.TextCtrl(self)
        sizer.Add(self.name_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.SetSizer(sizer)
        sizer.Fit(self)
        # Focus only once the dialog is actually showing: focusing a
        # control in a hidden dialog trips another wx assertion.
        wx.CallAfter(self.name_ctrl.SetFocus)

    def get_result(self):
        """Return (kind, name, gender), or None when the name is empty."""
        selection = self.kind_box.GetSelection()
        kind = ("robot", "chef", "witch")[selection] if 0 <= selection < 3 else "robot"
        gender = "male" if self.gender_box.GetSelection() == 0 else "female"
        name = self.name_ctrl.GetValue().strip()
        if not name:
            return None
        return kind, name, gender


class CreateAccountDialog(wx.Dialog):
    """After the online key check, every launch: sign in with
    a username, a player code and a password, or make a new
    account in the same dialog. A new account also picks a
    gender (which picks the voice) and whether they are a
    robot, chef or witch fighter; a returning player's choices
    come from the server instead. The username is also the
    fighter's name.

    The password box hides what is typed. The password is
    never saved on this computer, never logged and never
    shown: it goes to the server once, then is dropped.
    Nothing from this dialog is saved on this computer."""

    def __init__(self, parent):
        super().__init__(parent, title="Sign in or make your account")
        sizer = wx.BoxSizer(wx.VERTICAL)
        hint = wx.StaticText(
            self,
            label=(
                "Welcome to Arena of Makers. Type your username, "
                "player code and password to sign in. New here? "
                "Pick them now, plus a voice and fighter type, and "
                "your account is made. Friends can look you up by "
                "your player code. Never share your password."
            ),
        )
        hint.Wrap(420)
        sizer.Add(hint, 0, wx.ALL, 10)

        sizer.Add(wx.StaticText(self, label="Username:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.name_ctrl = wx.TextCtrl(self)
        sizer.Add(self.name_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        self.gender_box = wx.RadioBox(
            self,
            label="Voice",
            choices=["Male voice", "Female voice"],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        sizer.Add(self.gender_box, 0, wx.ALL | wx.EXPAND, 10)

        self.kind_box = wx.RadioBox(
            self,
            label="Fighter type",
            choices=["Robot fighter", "Chef fighter", "Witch fighter"],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        sizer.Add(self.kind_box, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(
            wx.StaticText(
                self,
                label="A male witch is called a warlock.",
            ),
            0, wx.ALL, 10,
        )

        sizer.Add(wx.StaticText(self, label="Player code (4 digits):"), 0, wx.LEFT | wx.RIGHT, 10)
        self.code_ctrl = wx.TextCtrl(self)
        self.code_ctrl.SetValue(account.generate_player_code())
        sizer.Add(self.code_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        self.new_code_button = wx.Button(self, label="Make a code for me")
        self.new_code_button.Bind(wx.EVT_BUTTON, self.on_new_code)
        sizer.Add(self.new_code_button, 0, wx.ALL, 10)

        sizer.Add(
            wx.StaticText(self, label="Password (at least 8 characters, hidden):"),
            0, wx.LEFT | wx.RIGHT, 10,
        )
        self.password_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        sizer.Add(self.password_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        # Only offered when this computer has a password store.
        # Off unless the player ticks it.
        self.keep_box = None
        if remember.available():
            self.keep_box = wx.CheckBox(
                self, label="Keep me signed in on this computer"
            )
            sizer.Add(self.keep_box, 0, wx.ALL, 10)

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.SetSizer(sizer)
        sizer.Fit(self)
        wx.CallAfter(self.name_ctrl.SetFocus)

    def on_new_code(self, event):
        self.code_ctrl.SetValue(account.generate_player_code())

    def keep_signed_in(self):
        return bool(self.keep_box is not None and self.keep_box.GetValue())

    def get_result(self):
        """Return (username, gender, kind, player_code, password),
        or None when the username, code or password is empty or
        not usable. The password box is cleared once read."""
        name = self.name_ctrl.GetValue().strip()
        password = self.password_ctrl.GetValue()
        self.password_ctrl.SetValue("")
        if not name or not password:
            return None
        code = account.clean_player_code(self.code_ctrl.GetValue())
        if account.validate_player_code(code):
            return None
        selection = self.kind_box.GetSelection()
        kind = ("robot", "chef", "witch")[selection] if 0 <= selection < 3 else "robot"
        gender = "male" if self.gender_box.GetSelection() == 0 else "female"
        return name, gender, kind, code, password


class ConfirmPasswordDialog(wx.Dialog):
    """New accounts only: type the password once more, so a
    typing slip in a hidden box does not lock the player out."""

    def __init__(self, parent, player_code):
        super().__init__(parent, title="Make a new account")
        sizer = wx.BoxSizer(wx.VERTICAL)
        hint = wx.StaticText(
            self,
            label=(
                "Nobody has the player code %s yet, so this makes a new "
                "account. Type your password again to confirm it."
                % player_code
            ),
        )
        hint.Wrap(420)
        sizer.Add(hint, 0, wx.ALL, 10)
        sizer.Add(wx.StaticText(self, label="Password again (hidden):"),
                  0, wx.LEFT | wx.RIGHT, 10)
        self.password_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        sizer.Add(self.password_ctrl, 0, wx.ALL | wx.EXPAND, 10)
        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(sizer)
        sizer.Fit(self)
        wx.CallAfter(self.password_ctrl.SetFocus)

    def get_result(self):
        password = self.password_ctrl.GetValue()
        self.password_ctrl.SetValue("")
        return password


class FindPlayerDialog(wx.Dialog):
    """Look a player up by their player code."""

    def __init__(self, parent):
        super().__init__(parent, title="Look up a player")
        sizer = wx.BoxSizer(wx.VERTICAL)
        hint = wx.StaticText(
            self,
            label="Type a friend's player code, and the game will tell you their username.",
        )
        hint.Wrap(420)
        sizer.Add(hint, 0, wx.ALL, 10)
        sizer.Add(wx.StaticText(self, label="Player code:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.code_ctrl = wx.TextCtrl(self)
        sizer.Add(self.code_ctrl, 0, wx.ALL | wx.EXPAND, 10)
        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(sizer)
        sizer.Fit(self)
        wx.CallAfter(self.code_ctrl.SetFocus)

    def get_result(self):
        code = self.code_ctrl.GetValue().strip()
        return code or None


class _ConfirmDialog(wx.Dialog):
    """A yes/no question with Yes as the default button.

    A plain wx.MessageBox left the default button up to the
    platform, and Enter on Yes was heard as No: a player
    pressed Enter on Yes for a max-affordable queue and the
    game answered "Nothing was bought" (2026-11-18). This
    dialog makes Yes explicit: it is the default button and
    it starts with the focus, Y answers yes, N answers no,
    and Escape answers no. The question itself is spoken
    aloud, so the player always knows what Yes means."""

    def __init__(self, parent, text):
        super().__init__(parent, title=APP_TITLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        question = wx.StaticText(
            self,
            label=text + " Press Y for yes, or N for no.",
        )
        question.Wrap(560)
        sizer.Add(question, 0, wx.ALL, 10)
        row = wx.BoxSizer(wx.HORIZONTAL)
        yes_button = wx.Button(self, wx.ID_YES, "Yes")
        yes_button.SetDefault()
        yes_button.Bind(
            wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_YES)
        )
        row.Add(yes_button, 0, wx.ALL, 5)
        no_button = wx.Button(self, wx.ID_NO, "No")
        no_button.Bind(
            wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_NO)
        )
        row.Add(no_button, 0, wx.ALL, 5)
        sizer.Add(row, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        # Focus only once the dialog is actually showing:
        # focusing a control in a hidden dialog trips a wx
        # assertion, the same as in CreateFighterDialog.
        wx.CallAfter(yes_button.SetFocus)

    def _on_key(self, event):
        key = event.GetKeyCode()
        if key in (ord("y"), ord("Y")):
            self.EndModal(wx.ID_YES)
        elif key in (ord("n"), ord("N"), wx.WXK_ESCAPE):
            self.EndModal(wx.ID_NO)
        else:
            event.Skip()


class MainFrame(wx.Frame):
    """One window, six tabs, one list on each tab."""

    TAB_NAMES = ["Home", "Combat", "Shop", "More", "Study", "Settings"]

    TAB_HINTS = {
        "Home": "Home. Your fighter, and where to go next.",
        "Combat": "Combat. Fight one creature, or let idle fighting keep going.",
        "Shop": "Shop. Upgrade your weapon, armor and healing, or buy as many levels as you can afford. Upgrades take time, capped at 4 hours.",
        "More": "More. Hangout, repairs, and quests.",
        "Study": "Study. Press Enter study to learn spells and take quests from other witches and warlocks. Learning only ticks while you are here.",
        "Settings": "Settings. Voice, sound effects, and volume.",
    }

    def __init__(self, fighter, online_config=None, player_account=None,
                 remembered=False):
        super().__init__(None, title=APP_TITLE, size=(640, 480))
        # True when "Keep me signed in on this computer" is on.
        self.remembered = remembered
        self.fighter = fighter
        # The account made on first launch: {"username": ...,
        # "player_code": ...}. The fighter carries the player
        # code too, so an online save can be traced to its player.
        self.player_account = player_account
        if player_account:
            self.fighter["player_code"] = player_account["player_code"]
            self.fighter["username"] = player_account["username"]
        # Online-only: the Supabase URL and publishable key from
        # the player's own .env file, checked at launch in
        # run_game(). None in the headless tests, where there is
        # no .env and no server: those tests use the local save only.
        # online_config also holds the session token, in memory
        # only. With it, every fight and upgrade runs on the
        # server, which is the only judge of the fighter.
        self.online_config = online_config
        self.online_status = (
            "Online: Supabase" if online_config else "Offline: no online key"
        )
        self.last_heartbeat = time.time()
        self._last_timer_check = 0.0
        self.random = random.Random()
        self.idle_fighting = False
        self.last_idle_fight = 0.0
        # Music rule (Makenna, 2026-11-17): music only plays for
        # one activity at a time — the hangout, or auto-fighting.
        # It never starts at launch and never starts just from
        # switching tabs. _in_hangout is True from "Visit the
        # hangout" until the player leaves the More tab.
        self._in_hangout = False
        # Hangout quests (Phase 18): _quests_active is True
        # from Start until Stop (or leaving the hangout).
        # _quest_current is the quest running now, with the
        # server's started_at and finish_at in it. Stopping
        # only stops the loop here: the quest stays saved on
        # the server, and Start picks it up again.
        self._quests_active = False
        self._quest_current = None
        self._quest_board = []
        self._quest_rep = {}
        self._quest_gift_pending = None
        self._quest_last_progress_at = 0.0
        # The study (Phase 38, auto-study in Phase 38b): _in_study
        # is True while the player is on the Study tab. Learning
        # only ticks while in the study — leaving the tab freezes
        # the remaining time on the server, coming back resumes
        # it. _study_quest_active is True from Enter study until
        # Stop for the study quest loop, which shares the hangout's
        # board and active quest (a quest is a quest). The first
        # study quest starts at once; after one ends, the next is
        # dealt 10 to 15 minutes later, so there is time to
        # study in between.
        self._in_study = False
        self._study_quest_active = False
        self._study_last_progress_at = 0.0
        self._study_quest_next_at = 0.0
        # A refused study completion, retried (Phase 39c):
        # when the server says a spell is not done yet, the
        # game asks again at most every 10 seconds, and says
        # the refusal once per spell — never once a second.
        self._last_study_complete_try_at = 0.0
        self._study_complete_try_key = None
        self._study_complete_error_key = None
        # A cast line is always followed at once by its hit
        # line: this remembers that the last line spoken was a
        # cast, so the hit line skips the wand sound — the spell
        # IS the hit, and the wand is only backup.
        self._spell_cast_pending = False
        self._last_tab = "Home"
        self.sound_on = True
        self.music_on = True
        self.volume = 40
        self.was_repairing = game_logic.is_repairing(fighter)
        self.voice = None
        self._player_ready = False
        self._voice_file = None
        self._voice_play_failed = False
        # Turn-by-turn narration: lines waiting to be spoken, in
        # order. Only one line is ever handed to the voice at a
        # time, and the next one is not spoken until the mixer has
        # finished playing the current one (checked in on_tick).
        self._narration_queue = []
        self._narration_pause = TURN_PAUSE_SECONDS
        self._narration_waiting = False  # a line is being made
        self._narration_playing = False  # a line is sounding now
        self._narration_next_at = 0.0
        self.sounds = sounds.SoundBank(pygame_module=pygame)

        self.notebook = wx.Notebook(self)
        self.lists = {}
        self.logs = {}
        for name in self.TAB_NAMES:
            page = wx.Panel(self.notebook)
            sizer = wx.BoxSizer(wx.VERTICAL)
            hint = wx.StaticText(page, label=self.TAB_HINTS[name])
            hint.Wrap(600)
            sizer.Add(hint, 0, wx.ALL, 8)
            list_box = wx.ListBox(page, style=wx.LB_SINGLE)
            sizer.Add(list_box, 1, wx.ALL | wx.EXPAND, 8)
            self.lists[name] = list_box
            if name == "Combat":
                log = wx.TextCtrl(
                    page, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
                )
                sizer.Add(log, 1, wx.ALL | wx.EXPAND, 8)
                self.logs[name] = log
            page.SetSizer(sizer)
            self.notebook.AddPage(page, name)
            list_box.Bind(wx.EVT_LISTBOX_DCLICK, self.on_list_activate)

        self.message_line = wx.StaticText(self, label="")
        self.message_line.Wrap(620)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(self.notebook, 1, wx.EXPAND)
        frame_sizer.Add(self.message_line, 0, wx.ALL | wx.EXPAND, 8)
        self.SetSizer(frame_sizer)

        self.CreateStatusBar()
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_tick, self.timer)
        self.timer.Start(1000)  # once a second

        self.voice = self._setup_voice()

        # Sound effects and music use the same mixer the voice
        # already opened. With no sound files in sounds/ this just
        # logs that nothing was loaded, and the game plays on.
        # No music at launch: it only starts for an activity
        # (the hangout, or auto-fighting), never on its own.
        self.sounds.load()
        self.sounds.set_volume(self.volume)

        self.refresh_all()
        self.announce("Welcome to Arena of Makers, %s." % fighter["name"])
        self.lists["Home"].SetFocus()

    # -- lists ---------------------------------------------------------

    def current_tab(self):
        return self.TAB_NAMES[self.notebook.GetSelection()]

    def list_items(self, tab):
        fighter = self.fighter
        if tab == "Home":
            items = ["Hear my fighter status"]
            # Stats live here, in the same list as the fighter
            # status: arrow keys to move, Enter to spend one
            # banked point on the highlighted stat. Banked
            # points may all go into one stat: stay on the
            # line and press Enter again for the next point.
            points = fighter.get("stat_points", 0)
            if points > 0:
                items.append(
                    "I have %d stat %s to spend. Press Enter on a "
                    "stat to spend one point."
                    % (points, "point" if points == 1 else "points")
                )
            else:
                items.append("I have no stat points to spend right now.")
            # Quest level (Phase 23), next to the fighter level:
            # one line, always shown, even at quest level 1.
            items.append(quests.quest_level_line(fighter))
            # Quest points (Phase 36 fix, Makenna 2026-11-25):
            # banked quest points and the three quest stats live
            # here too, not only in the hangout, so they can be
            # spent where combat points are spent. Same Enter
            # pattern as the hangout lines: arrow to the line,
            # Enter spends one banked point there.
            qpoints = quests.quest_points_of(fighter)
            if qpoints > 0:
                items.append(
                    "I have %d quest %s to spend. Press Enter on a "
                    "quest stat to spend one point."
                    % (qpoints, "point" if qpoints == 1 else "points")
                )
            else:
                items.append("I have no quest points to spend right now.")
            for qstat in quests.QUEST_STAT_NAMES:
                items.append(quests.quest_stat_line(fighter, qstat))
            for stat in game_logic.STAT_NAMES:
                items.append(game_logic.stat_line(fighter, stat))
            if sum(game_logic.stats_of(fighter).values()) > 0:
                items.append(
                    "Reset all my stats (first one free, later ones 100 credits)"
                )
            items += [
                "Go to Combat",
                "Go to Shop",
                "Go to More",
                "Go to Study",
                "Go to Settings",
            ]
            return items
        if tab == "Combat":
            state = "on" if self.idle_fighting else "off"
            return [
                "Fight",
                "Idle fighting: %s (press Shift F)" % state,
                "Hear my fighter status",
            ]
        if tab == "Shop":
            upgrade = game_logic.upgrade_status(fighter)
            # The three upgrade slots, in Shop order, with
            # their list key: weapon U, armor A, healing H
            # (Phase 25). Healing is called Second Wind and
            # stops at level 5; the other two climb forever.
            slots = (
                ("weapon", "U"),
                ("armor", "A"),
                ("healing", "H"),
            )

            def _single_line(slot, key):
                """One line for buying the next level of a
                slot, or the maxed line for a Healing skill
                already at level 5."""
                name = game_logic.HEALING_NAME if slot == "healing" \
                    else fighter[slot + "_name"]
                # A fighter made before Phase 18 has no
                # healing_level key at all: missing means
                # level 0, never a crash (Phase 25b hotfix).
                level = fighter.get(slot + "_level", 0) or 0
                if slot == "healing" and level >= game_logic.HEALING_MAX_LEVEL:
                    return "%s is at its best, level %d." % (
                        name, game_logic.HEALING_MAX_LEVEL)
                cost = game_logic.slot_upgrade_cost(slot, level)
                return (
                    "Upgrade %s to level %d, costs %d credits (press %s)"
                    % (name, level + 1, cost, key)
                )

            def _max_line(slot, key):
                """One max-affordable line for a slot, or None
                when the slot has nothing to say: a Healing
                skill already at level 5 has its maxed line
                up above instead of a max-affordable line."""
                plan = game_logic.max_affordable(fighter, slot)
                if plan.get("maxed"):
                    return None
                if plan["levels"]:
                    count = len(plan["levels"])
                    return (
                        "Max affordable: %s up %d %s for %d credits, "
                        "done in %s (press Shift %s)"
                        % (
                            plan["name"],
                            count,
                            "level" if count == 1 else "levels",
                            plan["cost"],
                            game_logic.format_time(plan["seconds"]),
                            key,
                        )
                    )
                return (
                    "Max affordable: my next %s level costs %d "
                    "credits and I have %d credits."
                    % (plan["name"], plan["next_cost"], plan["credits"])
                )

            if upgrade:
                # One upgrade set at a time (Makenna, Nov 18,
                # 2026): while a set is running, the Shop shows
                # the running set with its time left first, and
                # the other slots say plainly that they wait —
                # they never pretend the next upgrade is ready
                # to start. Enter on any of those lines still
                # goes through do_upgrade, which speaks the
                # block with the time left.
                running_slot = (fighter.get("upgrade") or {}).get("slot")
                items = [upgrade]
                for slot, key in slots:
                    if slot == running_slot:
                        continue
                    name = game_logic.HEALING_NAME if slot == "healing" \
                        else fighter[slot + "_name"]
                    # Same missing-key rule as above: a
                    # fighter made before Phase 18 has no
                    # healing_level key; missing means level 0.
                    level = fighter.get(slot + "_level", 0) or 0
                    if slot == "healing" and level >= game_logic.HEALING_MAX_LEVEL:
                        items.append(
                            "%s is at its best, level %d."
                            % (name, game_logic.HEALING_MAX_LEVEL)
                        )
                        continue
                    cost = game_logic.slot_upgrade_cost(slot, level)
                    items.append(
                        "Upgrade %s to level %d, costs %d credits "
                        "-- waits until the running upgrade finishes, "
                        "%s left (press %s)"
                        % (
                            name,
                            level + 1,
                            cost,
                            game_logic.format_time(
                                max(0, fighter["upgrade"]["finish"]
                                    - time.time())),
                            key,
                        )
                    )
            else:
                items = [_single_line(slot, key) for slot, key in slots]
                # Max affordable: one line per slot, worked out
                # from the fighter the server sent back. The
                # server decides the real queue and price.
                for slot, key in slots:
                    line = _max_line(slot, key)
                    if line:
                        items.append(line)
            items.append("Hear my fighter status")
            return items
        if tab == "More":
            items = ["Visit the hangout"]
            if self._in_hangout:
                # Hangout quests (Phase 18): a real Start and
                # Stop, plus one more quest and the board.
                # Every quest is open to robots and chefs
                # alike — fighter kind never locks anyone out.
                if self._quest_gift_pending:
                    items.append(
                        "Choose my free gift: weapon upgrade (press 1)")
                    items.append(
                        "Choose my free gift: armor upgrade (press 2)")
                if self._quests_active:
                    items.append("Stop quests (press S)")
                else:
                    items.append("Start quests (press S)")
                items.append("Find me another quest")
                items.append("Hear my quests")
                # Quest levels (Phase 23): quest level, quest XP
                # to the next level, banked quest points, and the
                # three quest stat lines — next to the quest
                # board, not instead of it. Enter on a quest
                # stat spends one banked quest point there.
                items.append(quests.quest_level_line(self.fighter))
                qpoints = quests.quest_points_of(self.fighter)
                if qpoints > 0:
                    items.append(
                        "I have %d quest %s to spend. Press Enter on a "
                        "quest stat to spend one point."
                        % (qpoints, "point" if qpoints == 1 else "points")
                    )
                else:
                    items.append("I have no quest points to spend right now.")
                for qstat in quests.QUEST_STAT_NAMES:
                    items.append(quests.quest_stat_line(self.fighter, qstat))
                for line in quests.reputation_summary(self._quest_rep):
                    items.append(line)
            else:
                items.append("Quests live in the hangout")
            items += [
                "Hear repair status (press R)",
                "Export my data (save a copy on this computer)",
                "Look up a player by code",
                "See who is online",
                "Fight a player by code",
                "My player code: %s" % (
                    self.player_account["player_code"]
                    if self.player_account else "no account yet"
                ),
                self.online_status,
                "Hear my fighter status",
            ]
            return items
        if tab == "Study":
            # The study (Phase 38b, Makenna Nov 25, 2026): one
            # button, "Enter study" — the player never picks a
            # spell. Entering starts the music, starts learning
            # a spell picked at random, and starts study quests
            # on their own. Learning is witch-only; study quests
            # are open to everyone, robot, chef and witch alike.
            items = [spells.study_status_line(fighter)]
            if (spells.study_is_learning(fighter)
                    or self._study_quest_active):
                items.append("Studying in the study (press Enter)")
            else:
                items.append("Enter study (press Enter)")
            if fighter.get("kind", "robot") != "witch":
                items.append(
                    "Only a witch or warlock can learn spells in "
                    "the study — but study quests are open to "
                    "everyone.")
            if self._study_quest_active:
                items.append("Stop study quests (press S)")
            items.append("Hear my quests")
            return items
        if tab == "Settings":
            sound = "on" if self.sound_on else "off"
            music = "on" if self.music_on else "off"
            gender = self.fighter.get("gender", "male")
            voice_name = "Male" if gender == "male" else "Female"
            voice_state = "" if self.voice is not None else " (voice off)"
            lines = [
                "Voice: %s%s (press Enter to change)" % (voice_name, voice_state),
                "Sound effects: %s" % sound,
                "Background music: %s" % music,
                "Lower volume (now %d percent)" % self.volume,
                "Raise volume (now %d percent)" % self.volume,
                "Keep me signed in on this computer: %s" % (
                    ("on" if self.remembered else "off")
                    if remember.available() and self.online_config
                    else "not available"
                ),
            ]
            # Change fighter (Phase 36, Makenna Nov 25, 2026):
            # one line for each kind this fighter is not, so the
            # player picks the kind on the line itself. The first
            # switch is free; after that the price doubles every
            # switch, with no cap. The cost shown is the display
            # price — the server decides the real one.
            current_kind = self.fighter.get("kind", "robot")
            switches = self.fighter.get("kind_switches", 0) or 0
            cost = game_logic.switch_cost(switches)
            for kind in ("robot", "chef", "witch"):
                if kind == current_kind:
                    continue
                word = game_logic.kind_word(kind, gender)
                if cost <= 0:
                    lines.append(
                        "Change fighter to %s: first switch is free "
                        "(press Enter)" % word
                    )
                else:
                    lines.append(
                        "Change fighter to %s: costs %d credits "
                        "(press Enter)" % (word, cost)
                    )
            return lines
        return []

    def refresh_list(self, tab):
        """Only rewrite a list when its items actually changed, so the
        screen reader never loses its place mid-fight."""
        items = self.list_items(tab)
        box = self.lists[tab]
        current = [box.GetString(i) for i in range(box.GetCount())]
        if current != items:
            selection = box.GetSelection()
            box.Set(items)
            if 0 <= selection < box.GetCount():
                box.SetSelection(selection)
            elif box.GetCount():
                box.SetSelection(0)

    def refresh_all(self):
        for tab in self.TAB_NAMES:
            self.refresh_list(tab)
        self.SetStatusText(game_logic.status_text(self.fighter))

    # -- speaking and sound --------------------------------------------

    def _setup_voice(self):
        """Start the Edge voice, or stay text-only with one log line
        saying why. Returns the voice, or None when it is off. The
        startup line in the log records everything a diagnosis needs:
        which Python is running the game, whether edge-tts and pygame
        are installed, which voice is picked, and the volume."""
        voice_name = voice_engine.voice_for_gender(
            self.fighter.get("gender", "male")
        )
        logging.info(
            "Voice startup: Python %s; edge-tts %s; pygame %s; "
            "voice %s; volume %d percent.",
            sys.executable,
            "installed" if voice_engine.edge_tts is not None else "not installed",
            "installed" if pygame is not None else "not installed",
            voice_name,
            self.volume,
        )
        if pygame is None:
            logging.warning(
                "Edge voice is off: the pygame package is not installed, "
                "so there is nothing to play voice with. Run: "
                "pip install pygame. The game keeps going with text only."
            )
            return None
        try:
            pygame.mixer.init()
        except Exception as error:
            logging.warning(
                "Edge voice is off: this computer could not open its "
                "sound device (%s: %s). The game keeps going with "
                "text only.",
                type(error).__name__,
                error,
            )
            return None
        voice = voice_engine.EdgeVoice(
            voice_name, self._on_voice_file,
            fail_callback=self._on_voice_failed,
            fallback_voice=voice_name)
        if not voice.start():
            return None
        self._player_ready = True
        return voice

    def _on_voice_file(self, path):
        """Called on the voice thread when a line is ready to play.
        Hop to the UI thread before touching the player."""
        wx.CallAfter(self._play_voice_file, path)

    def _on_voice_failed(self):
        """Called on the voice thread when a line could not be
        spoken at all, even after a retry and a fallback voice.
        Hop to the UI thread before touching the narration flags."""
        wx.CallAfter(self._clear_narration_waiting)

    def _clear_narration_waiting(self):
        """A line that will never sound is over: stop waiting
        for it, so the next queued line can speak. Without this,
        one failed line leaves _narration_waiting True forever
        and every later quest line queues behind it, unheard —
        exactly what Makenna saw on 2026-11-18, when a dead
        giver voice silenced the whole hangout (Phase 27)."""
        self._narration_waiting = False
        self._narration_playing = False
        self._narration_next_at = 0.0

    def _release_voice_file(self):
        """Stop playback and let go of the current file, so Windows
        allows it to be deleted. Never raises."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

    def _play_voice_file(self, path):
        """Play one spoken line, at the game's volume. The previous
        line's file is deleted first, so old files never pile up.
        Every outcome is logged, and a moment after play starts the
        mixer is asked whether it is really making sound."""
        if not self._player_ready:
            logging.warning(
                "Voice: the player is missing, so a finished line "
                "could not be played. The game keeps going with text only."
            )
            return
        self._release_voice_file()
        old = self._voice_file
        if old and old != path:
            try:
                os.unlink(old)
            except OSError:
                pass
        self._voice_file = path
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            pygame.mixer.music.play()
        except Exception as error:
            if not self._voice_play_failed:
                self._voice_play_failed = True
                logging.warning(
                    "Edge voice is off: the voice file could not be "
                    "played (%s: %s; %d bytes). The game keeps going "
                    "with text only.",
                    type(error).__name__,
                    error,
                    size,
                )
            # Playback failed, so this narrated line is over: let
            # the narration move on to the next line, if any.
            self._narration_waiting = False
            self._narration_playing = False
            self._narration_next_at = 0.0
            return
        self._voice_play_failed = False
        # This line is now sounding. The narration waits for it.
        self._narration_waiting = False
        self._narration_playing = True
        logging.info("Voice: playing voice file (%d bytes).", size)
        wx.CallLater(300, self._log_voice_busy)

    def _log_voice_busy(self):
        """Log whether the mixer is really playing, shortly after a
        line started. A line that is still sounding is the proof that
        sound is coming out of the speakers."""
        try:
            busy = pygame.mixer.music.get_busy()
        except Exception:
            return
        logging.info(
            "Voice: mixer is %s.", "playing" if busy else "not playing"
        )

    def _cancel_narration(self):
        """Stop any turn-by-turn narration in progress. A single
        announce() always wins over a queued narration, so a new
        message is never stuck behind a long fight."""
        self._narration_queue = []
        self._narration_waiting = False
        self._narration_playing = False
        self._narration_next_at = 0.0

    def _narration_busy(self):
        """True while a fight narration is still speaking or
        waiting to be spoken: lines queued, a line being made
        by the voice, or the mixer still playing a line. The
        mixer is the ground truth for a line sounding: the
        _narration_playing flag goes stale after a single
        announce() line finishes, because _advance_narration
        only clears it while a narration queue is running, so
        it is not used here. A voice that is off or dead never
        counts as busy, so a dead voice can never stall idle
        fighting: the game just carries on with text only."""
        if self._narration_queue or self._narration_waiting:
            return True
        if self.voice is None or pygame is None:
            return False
        if not self.voice.available:
            return False
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def announce(self, text):
        """Show it in plain words, and speak it when the voice is on.
        A single line never cuts off a fight narration in progress:
        when narration is still speaking or queued, the line waits
        at the end of the queue and is spoken after the fight's
        lines, in order. That is how turning idle fighting off
        mid-fight works: the current fight's lines finish first,
        then \"Idle fighting off.\" is spoken, and no new fight
        starts. Only when nothing is speaking does a line speak
        at once. (Closing the game is the one exception: on_close
        cancels narration outright.)"""
        self.announce_as(text, None)

    def announce_as(self, text, voice_name):
        """Say it in a given Edge voice, or the player's own
        voice when voice_name is None. Quest givers speak in
        their own voice (Bolt, Marge, Pip, Dot, Gus, Belle);
        the player's fighter keeps the voice they chose.
        When a giver's voice cannot be reached, the voice
        engine speaks that line in the player's voice instead
        (Phase 27), so the game never goes silent — the giver's
        name stays in the spoken text. Narration entries are
        (text, voice, sound) triples, so a giver's line queued
        behind a fight is still spoken in the giver's voice
        when its turn comes; sound is the magic-sound key for
        a creature's special (Phase 39), else None."""
        text = (text or "").strip()
        if not text:
            return
        if self.voice is None:
            self.message_line.SetLabel(text)
            return
        if self._narration_busy():
            # Phase 39c: never queue the same line twice —
            # a once-a-second announcer must not flood the
            # queue with identical lines and bury the trainer
            # and giver lines that come after them.
            if any(text == queued[0]
                   for queued in self._narration_queue):
                return
            self._narration_queue.append((text, voice_name, None))
            return
        self.message_line.SetLabel(text)
        self._cancel_narration()
        # The line is being made now: mark it waiting, so the
        # next idle fight does not start and cut it off while
        # the voice is still synthesising it. _play_voice_file
        # clears this the moment the line starts sounding, and
        # _on_voice_failed clears it when the line can never
        # sound. If speak() itself refuses the line, clear it
        # here: a refused line must never leave the narration
        # stuck waiting for it.
        self._narration_waiting = True
        if voice_name:
            self.voice.set_voice(voice_name)
        else:
            self.voice.set_voice(
                voice_engine.voice_for_gender(
                    self.fighter.get("gender", "male")))
        if not self.voice.speak(text):
            self._narration_waiting = False

    def announce_sequence(self, lines, pause_seconds=TURN_PAUSE_SECONDS,
                            line_sounds=None):
        """Speak lines one at a time, in order, with a short pause
        between them. This is how a fight is narrated turn by
        turn, manual or idle: the first line is spoken now, and
        _advance_narration() (called from the one-second timer
        in on_tick) speaks each next line only once the mixer
        has finished the current one. The Combat text log
        already holds every line, so the log and the voice tell
        the same story. With no voice, only the last line is
        shown, as before. line_sounds (Phase 39) is a dict of
        line index -> magic-sound key for the rounds a
        creature's special fired, from the fight result's
        "creature_magic"; those lines play the magic sound
        instead of whatever the words alone would pick."""
        # Keep the fight result's own line numbers: the magic
        # keys are indexed by them, so filter blank lines only
        # after pairing each line with its original index.
        kept = [(index, line) for index, line in enumerate(lines or [])
                if (line or "").strip()]
        if not kept:
            return
        if self.voice is None:
            self.message_line.SetLabel(kept[-1][1])
            return
        self._cancel_narration()
        sounds = line_sounds or {}
        self._narration_queue = [
            (line, None, sounds.get(index))
            for index, line in kept]
        self._narration_pause = pause_seconds
        self._narration_next_at = 0.0
        self._speak_next_narration()

    def _speak_next_narration(self):
        """Speak the next queued narration line, and play the
        sound effect that goes with it. Only ever called when no
        line is currently sounding."""
        if not self._narration_queue or self.voice is None:
            return
        line, voice_name, sound_key = self._narration_queue.pop(0)
        self._play_sound_for_line(line, sound_key)
        self.message_line.SetLabel(line)
        self._narration_waiting = True
        if voice_name:
            self.voice.set_voice(voice_name)
        else:
            self.voice.set_voice(
                voice_engine.voice_for_gender(
                    self.fighter.get("gender", "male")))
        if not self.voice.speak(line):
            # The voice refused the line (its thread died, or
            # the service is gone): it will never sound, so do
            # not wait for it — the next queued line must still
            # get its turn (Phase 27).
            self._narration_waiting = False

    def _advance_narration(self, now):
        """Called once a second from on_tick. Speaks the next
        narration line when the current one has finished playing
        and the pause after it has passed. Does nothing while a
        line is still being made or is still sounding. If the
        voice died while a line was being made, that line will
        never sound: stop waiting for it here too, so the queue
        can still drain (Phase 27 — the safety net under the
        voice engine's failed-line notice)."""
        if not self._narration_queue:
            return
        if self._narration_waiting:
            if self.voice is not None and not self.voice.available:
                self._clear_narration_waiting()
            else:
                return
        if pygame is None:
            return
        try:
            busy = pygame.mixer.music.get_busy()
        except Exception:
            busy = False
        if busy:
            self._narration_playing = True
            return
        if self._narration_playing:
            # The line just finished: start the pause, then wait.
            self._narration_playing = False
            self._narration_next_at = now + self._narration_pause
            return
        if now < self._narration_next_at:
            return
        self._speak_next_narration()

    def _play_sound_for_line(self, line, sound_key=None):
        """The sound effect for one narration line, or nothing
        when sounds are off or the file is missing. Robot and
        chef fighters hear different sounds for the same hit.
        Each creature has its OWN appear and hit sounds, so
        you can tell who it is by sound alone (Makenna's
        per-creature sound rule, Nov 18, 2026): when a named
        NPC appears or hits, its own sounds play; Scrap Rat
        keeps the fighter-kind sounds it always had. A
        missing creature sound simply plays nothing — the
        fight never stops for a sound file. sound_key
        (Phase 39) is the fight's own say-so for this line:
        when the creature's special fired, it names the magic
        sound ("spell_<element>" or the warlock's own file),
        and that plays instead of whatever the words alone
        would pick — the magic IS that round's sound."""
        if not self.sound_on:
            return
        if sound_key:
            # A magic round: the creature's special fired, so
            # its magic sound plays and nothing else does.
            # The fighter's spell-pending flag is untouched —
            # a magic line is never the fighter's own cast or
            # hit, so the flag is already clear by now.
            self.sounds.play_magic_sound(sound_key)
            return
        kind = self.fighter.get("kind", "robot")
        cast_element = spells.element_for_cast_line(line)
        if cast_element:
            # A spell cast: its own elemental sound, and the
            # wand stays quiet for the hit line that follows —
            # the spell IS the hit, and the wand is only backup
            # if a spell does not work (Makenna, Nov 25, 2026).
            self.sounds.play_spell(cast_element)
            self._spell_cast_pending = True
            return
        if "I won!" in line:
            self._spell_cast_pending = False
            self.sounds.play_win()
        elif "I lost." in line:
            self._spell_cast_pending = False
            self.sounds.play_loss()
        elif "appears!" in line:
            self._spell_cast_pending = False
            npc_id = game_logic.creature_in_line(line)
            if npc_id and npc_id != "scrap_rat":
                self.sounds.play(
                    game_logic.NPCS[npc_id]["appear_sound"])
            else:
                self.sounds.play_intro(kind)
        elif "I hit the " in line:
            # The fighter's hit, first person since Phase 28:
            # "I hit the Zip Scout for 12." always means the
            # fighter's own weapon sound, whoever the enemy is —
            # unless a spell was just cast, in which case the
            # spell's sound already played and the wand stays
            # quiet: the spell IS the hit.
            if self._spell_cast_pending:
                self._spell_cast_pending = False
            else:
                self.sounds.play_hit(kind)
        elif " hits " in line:
            self._spell_cast_pending = False
            # Who is hitting whom is in the words: "The Zip
            # Scout hits me" is the creature hitting. The
            # fighter's hits no longer say "hits" at all —
            # they say "I hit the ..." and are caught above.
            # Matching the exact wording keeps a fighter
            # whose name starts with "The" from stealing the
            # creature's sound.
            npc_id = game_logic.creature_in_line(line)
            if npc_id and npc_id != "scrap_rat":
                name = game_logic.NPCS[npc_id]["name"]
                if "The %s hits" % name in line:
                    self.sounds.play(
                        game_logic.NPCS[npc_id]["hit_sound"])
                elif "hits the %s" % name in line:
                    self.sounds.play_hit(kind)
            elif npc_id == "scrap_rat":
                if "The Scrap Rat hits" in line:
                    self.sounds.play_creature_hit(kind)
                elif "hits the Scrap Rat" in line:
                    self.sounds.play_hit(kind)
            else:
                # No creature named: the fighter's own weapon
                # sound, as before.
                self.sounds.play_hit(kind)
        else:
            # Any other narration line: a cast line is always
            # followed at once by its hit line, so anything
            # else means the sequence moved on.
            self._spell_cast_pending = False

    def log(self, lines):
        """Add fight narration to the Combat log."""
        if "Combat" in self.logs:
            self.logs["Combat"].AppendText("\n".join(lines) + "\n")

    def _log_online(self, action, detail=None):
        """Send one game action to the server, if online. A
        failed send never stops the game: online_save logs it."""
        if self.online_config:
            online_save.log_action(
                self.online_config, self.fighter["name"], action, detail,
                player_code=self.fighter.get("player_code"),
            )

    def use_server_fighter(self, server_fighter):
        """Show the fighter exactly as the server has it. The
        game never saves a fighter itself: the server changes
        it, and the game only copies the server's answer. The
        dict is updated in place, so every part of the window
        sees the same fighter."""
        if not server_fighter:
            return
        code = self.fighter.get("player_code")
        username = self.fighter.get("username")
        self.fighter.clear()
        self.fighter.update(server_fighter)
        if code:
            self.fighter.setdefault("player_code", code)
        if username:
            self.fighter.setdefault("username", username)

    def server_problem(self, error):
        """Say a server problem in plain words, and keep it for
        the Online line on the More tab."""
        self.online_status = "Online problem: " + error
        logging.error("Server: %s", error)
        self.announce(error)

    def do_export(self):
        """Export this player's own data only: their fighter and
        their own game actions, never anyone else's data."""
        if not self.online_config:
            self.announce(
                "Export needs the online key. The game did not start "
                "with a .env file, so there is nothing to export from."
            )
            return
        try:
            path, error = online_save.export_user_data(
                self.online_config, self.fighter
            )
        except Exception as error:
            logging.error("Export failed (%s: %s).", type(error).__name__, error)
            self.announce("Export failed. Check arena_log.txt for details.")
            return
        if error:
            self.announce("Export failed. " + error)
            return
        self._log_online(
            "export_data", {"file": os.path.basename(path)}
        )
        self.announce(
            "Your data was exported to %s, next to the game. It holds "
            "only your fighter and your own game actions, not anyone "
            "else's." % os.path.basename(path)
        )

    def do_lookup(self):
        """Look a friend up by their player code, and hear their username."""
        if not self.online_config:
            self.announce(
                "Looking up a player needs the online key. The game "
                "did not start with a .env file."
            )
            return
        dialog = FindPlayerDialog(None)
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return
        code = dialog.get_result()
        dialog.Destroy()
        if code is None:
            self.announce("Type a player code first.")
            return
        found, error = account.lookup_player(self.online_config, code)
        if error:
            self.announce(error)
            return
        fighter = found.get("fighter") or {}
        if fighter:
            self.announce(
                "Player %s is %s, a level %d %s. %d wins, %d losses. "
                "Their player code is %s."
                % (found["player_code"], found["username"],
                   fighter.get("level", 1), game_logic.kind_word(fighter.get("kind", ""), fighter.get("gender", "female")),
                   fighter.get("wins", 0), fighter.get("losses", 0),
                   found["player_code"])
            )
        else:
            self.announce(
                "Player %s is %s. They have no fighter yet. "
                "Their player code is %s."
                % (found["player_code"], found["username"], found["player_code"])
            )

    def do_list_players(self):
        """Hear who else is online right now, with their codes,
        so you can look them up or fight them."""
        if not self.online_config:
            self.announce("Seeing who is online needs the online key.")
            return
        players, error = online_save.list_online_players(self.online_config)
        if error:
            self.announce(error)
            return
        if not players:
            self.announce("Nobody else is online right now.")
            return
        lines = [
            "%s, code %s, level %s %s"
            % (row.get("username"), row.get("player_code"),
               row.get("level") or 1, game_logic.kind_word(row.get("kind") or ""))
            for row in players
        ]
        count = len(players)
        self.announce(
            "%d %s online: %s."
            % (count, "player" if count == 1 else "players", "; ".join(lines))
        )

    def do_fight_player(self):
        """Fight another player, found by their player code, in
        the same shared table. The fight is against a creature
        at your level, and the result is logged to the server
        with that player's code, so you can tell them about it."""
        if not self.online_config:
            self.announce("Fighting a player needs the online key.")
            return
        dialog = FindPlayerDialog(None)
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return
        code = dialog.get_result()
        dialog.Destroy()
        if code is None:
            self.announce("Type a player code first.")
            return
        found, error = account.lookup_player(self.online_config, code)
        if error:
            self.announce(error)
            return
        fighter = found.get("fighter") or {}
        if not fighter:
            self.announce(
                "%s has no fighter yet, so there is nobody to fight."
                % found["username"]
            )
            return
        self.announce(
            "Fighting %s, level %d %s."
            % (found["username"], fighter.get("level", 1), game_logic.kind_word(fighter.get("kind", ""), fighter.get("gender", "female")))
        )
        self.do_fight(opponent_code=found["player_code"])

    # -- actions -------------------------------------------------------

    def do_fight(self, idle=False, opponent_code=None, npc_id=None):
        """Fight one creature. A manual fight (F, or Enter on the
        fight item) and an idle fight are both narrated turn by
        turn, round by round, with the fight sounds for every
        line. Idle fighting used to speak only the result line
        and play no sounds, so it could run every 5 seconds
        without a backlog; that quiet-idle behaviour was
        removed at Makenna's request (Nov 17, 2026): auto-fight
        is the full battle, music and sounds and turn-by-turn
        TTS. The backlog is prevented a different way now: the
        next idle fight does not start until the previous
        fight's narration has finished speaking (see on_tick),
        so the 5-second gap is a minimum wait, never an
        interrupt.

        The opponent for a fight — manual or idle — is one
        creature picked at random from the pool — Scrap Rat or
        one of the 9 NPCs (Phase 24, Makenna Nov 18, 2026) —
        all at the fighter's own level, so fights stay fair.
        Auto-fight picks random creatures too (Makenna, Nov 18,
        2026 — follow-up to Phase 24): it is still just a
        toggle, on or off, and nothing else about it changes.
        A caller may pass npc_id to fight one creature in
        particular (the tests do). A fight against another
        player (opponent_code) never picks a creature.

        Online, the server runs the fight with its own dice and
        sends back the lines and the new fighter; the server
        also records the fight. Only the headless tests, which
        have no server, run the fight here, and nothing they do
        is ever saved."""
        # Music follows the fight: an auto-fight keeps the fight
        # track playing, a manual fight has sound effects only.
        self._refresh_music()
        if opponent_code is None and npc_id is None:
            # One creature picked at random each fight
            # (Makenna, Nov 18, 2026) — manual Fight and
            # auto-fight alike. Auto-fight is still just a
            # toggle, on or off; only its opponent is random now.
            npc_id = game_logic.random_npc_id(self.random)
        if self.online_config:
            if opponent_code is not None:
                result, error = online_save.fight(
                    self.online_config, opponent_code=opponent_code
                )
            elif npc_id in (None, "scrap_rat"):
                result, error = online_save.fight(self.online_config)
            else:
                result, error = online_save.fight_npc(
                    self.online_config, npc_id
                )
            if error:
                if idle:
                    self.idle_fighting = False
                    # Auto-fighting stopped, so its music stops
                    # too: a failed fight must not leave the
                    # fight track playing with nothing fighting.
                    self._refresh_music()
                self.server_problem(error)
                self.refresh_all()
                return
            self.use_server_fighter(result.get("fighter"))
        else:
            result = game_logic.fight(
                self.fighter, rng=self.random,
                npc_id=npc_id or "scrap_rat")
        self.log(result["lines"])
        # The rounds the creature's special fired (Phase 39):
        # line index -> magic-sound key. The server sends the
        # keys as text (JSON object keys are always text); the
        # offline fight uses plain ints. Normalise to ints so
        # announce_sequence can match them to the lines.
        magic = result.get("creature_magic") or {}
        line_sounds = {}
        for key, value in magic.items():
            try:
                line_sounds[int(key)] = value
            except (TypeError, ValueError):
                continue
        self.announce_sequence(result["lines"], line_sounds=line_sounds)
        self.refresh_all()

    def toggle_keep_signed_in(self):
        """Turn keep me signed in on or off. On: the server
        makes a remember token, kept in Windows Credential
        Manager. Off: the token is deleted there and on the
        server, so it stops working at once."""
        if not (remember.available() and self.online_config):
            self.announce(
                "Keep me signed in is not available on this computer. "
                "It needs the keyring package."
            )
            return
        if self.remembered:
            token = remember.load_token(self.online_config)
            account.forget_this_computer(self.online_config, token)
            remember.forget_token(self.online_config)
            self.remembered = False
            self.announce(
                "Keep me signed in is off. Next time, you will sign in "
                "with your password."
            )
        else:
            token, error = account.remember_this_computer(self.online_config)
            if error:
                self.server_problem(error)
                return
            if not remember.save_token(self.online_config, token):
                account.forget_this_computer(self.online_config, token)
                self.announce(
                    "Keep me signed in could not be saved on this computer, "
                    "so it is still off."
                )
                return
            self.remembered = True
            self.announce(
                "Keep me signed in is on. Next time, the game signs you in "
                "by itself. Turn this off on a shared computer."
            )
        self.refresh_all()

    def toggle_idle(self):
        """Turn idle fighting on or off. Turning it off
        mid-fight does not cut the fight's narration short:
        announce() queues \"Idle fighting off.\" behind the
        fight's lines, so they finish first and no new fight
        starts after them."""
        if game_logic.is_repairing(self.fighter):
            self.announce(
                "I'm still repairing. %s left."
                % game_logic.format_time(
                    game_logic.repair_left_seconds(self.fighter)
                )
            )
            return
        self.idle_fighting = not self.idle_fighting
        if self.idle_fighting:
            self.last_idle_fight = 0.0
            self.announce("Idle fighting on. Press Escape to stop.")
        else:
            self.announce("Idle fighting off.")
        self._refresh_music()
        self._log_online(
            "idle_on" if self.idle_fighting else "idle_off"
        )
        self.refresh_all()

    def _refresh_music(self):
        """Play the music for what the player is doing right
        now, or stop it. Hangout music only once quests have
        started in the hangout, fight music while
        auto-fighting is on, nothing anywhere else: entering
        the hangout alone starts nothing, a manual fight has
        sound effects only, switching tabs starts nothing,
        and launch starts nothing. Turning music or sound
        effects off in Settings stops it too. Asking for the
        track that is already playing does not restart it,
        so the loop never jumps.

        The music belongs to the whole session, not to one
        fight or one quest: while auto-fighting stays on, the
        fight track plays on continuously across every fight
        — it is never stopped and restarted between fights,
        or at the end of a single won fight, or between
        rounds. It stops only when the session ends:
        auto-fight turned off by hand, a loss that starts
        repairs, a failed fight, leaving the hangout, or the
        hangout's Stop. The hangout works the same way: its
        music plays from Start until Stop (or leaving),
        continuously across every quest, even while a quest
        is saved or paused. The study works the same way: its
        music plays while a spell is being learned or a study
        quest is running, and stops when the player leaves the
        study. Every place that ends auto-fighting or quests
        must call this, or the music keeps playing after the
        activity stops."""
        if not self.sound_on or not self.music_on:
            self.sounds.stop_music()
            return
        if self.idle_fighting:
            self.sounds.start_music("fight")
        elif self._in_hangout and self._quests_active:
            self.sounds.start_music("hangout")
        elif self._in_study and (
                spells.study_is_learning(self.fighter)
                or self._study_quest_active):
            self.sounds.start_music("study")
        else:
            self.sounds.stop_music()

    def _refresh_ambience(self):
        """Play the current quest's ambience loop, or stop it.
        The loop is background audio like the music: it plays
        only when sound effects and background music are both
        on, a little louder than the music so it is clearly
        noticeable, and still well under the voice (Phase 39d).
        A quest whose ambience has no sound file in sounds/
        yet plays nothing in the hangout — in the study the
        spell loop plays instead (Phase 39b). Asking for the
        loop that is already playing does not restart it, so
        the next quest with the same kind of work keeps the
        same loop going, and the once-a-second tick can
        re-assert the loop for free (Phase 39b). Every place
        that ends a quest must stop the loop, or it keeps
        playing after the activity stops:
        complete, Stop, pause, leaving the hangout, closing
        the game, and turning sounds or music off. In the
        study the loop is the ambience of the spell being
        learned when no quest is running; a quest's own
        ambience replaces it while a quest runs, and leaving
        the study stops it."""
        if not self.sound_on or not self.music_on:
            self.sounds.stop_ambience()
            return
        if self._quest_current:
            name = quests.ambience_sound_name(self._quest_current)
            if name and self.sounds.start_ambience(name):
                return
            # No loop for this quest — its file is not in
            # sounds/ yet, or playback failed. In the study,
            # fall through to the spell being learned instead
            # of going silent (Phase 39b, Nov 25, 2026:
            # Makenna heard no ambience at all while learning
            # Gloom Bolt on a quest). In the hangout there is
            # no spell loop to fall back to, so stop the old
            # loop instead of letting it carry on into a quest
            # it does not belong to.
            if not self._in_study:
                self.sounds.stop_ambience()
                return
        # In the study with no quest running, the loop is the
        # ambience of the spell being learned (Phase 38): the
        # brewing loop for fire, water and poison, the storm
        # loop for wind, lightning and earth, the moonlight loop
        # for ice, light, shadow and dark — still over the study
        # music. A quest's own ambience replaces it while a
        # quest is running, above.
        if self._in_study:
            name = spells.study_ambience(self.fighter)
            if name and self.sounds.start_ambience(name):
                return
        self.sounds.stop_ambience()

    # -- hangout quests (Phase 18) -------------------------------------

    def _apply_quest_data(self, data):
        """Take the server's quest answer into the window:
        board, reputation, any waiting gift, and the fighter
        as the server has it. The active quest, when the
        server has one, is the saved quest to pick up."""
        data = data or {}
        if data.get("quests") is not None:
            self._quest_board = list(data["quests"])
        if data.get("reputation") is not None:
            self._quest_rep = dict(data["reputation"])
        self._quest_gift_pending = data.get("gift_pending")
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])
        if data.get("active"):
            self._quest_current = data["active"]

    def _board_add_quest(self, quest):
        """Add a dealt quest to the board, once: the server's
        answer already carries the new quest in its board, so
        adding it again would list it twice. The quest tests'
        fake leaves the board out of its answer, so the add
        still happens there — exactly once, either way."""
        if quest and not any(q.get("id") == quest.get("id")
                             for q in self._quest_board):
            self._quest_board.append(quest)

    def start_quests(self):
        """Press Start in the hangout: quests run
        automatically in the idle loop, one after another,
        endlessly generated, while you stay in the hangout.
        Quests are not fights, never need health, and work
        while repairing and while upgrading. The cozy cafe
        track plays from Start until Stop. The server deals
        the board and starts each quest; the game only shows
        what the server sends back."""
        if not self._in_hangout:
            self.announce(
                "Go to the hangout first. It is on the More tab, "
                "under Visit the hangout.")
            return
        if self._quests_active:
            self.announce("Quests are already started.")
            return
        if not self.online_config:
            self.announce(
                "Quests need the online key. The game did not start "
                "with a .env file, so there is nothing to do quests from.")
            return
        data, error = online_save.get_quests(self.online_config)
        if error:
            self.server_problem(error)
            return
        self._apply_quest_data(data)
        self._quests_active = True
        self._refresh_music()
        self.announce(
            "Quests started. I will keep giving you tasks while you are here.")
        self._begin_next_quest()
        self.refresh_all()

    def _pause_current_quest(self):
        """Freeze the active quest's remaining time on the
        server, so its clock stops while the player is away
        from the hangout. Best effort: when the server cannot
        be reached, the loop still stops locally, and the
        quest stays saved with its old finish time. The
        server never completes a paused quest. The ambience
        loop stops too: a paused quest is not being worked
        on, so nothing should keep sounding."""
        self.sounds.stop_ambience()
        if not self._quest_current or not self.online_config:
            return
        data, error = online_save.pause_quest(self.online_config)
        if error or not data:
            return
        if data.get("quest"):
            self._quest_current = data["quest"]

    def stop_quests(self):
        """Press Stop: the quest flow stops cleanly. The quest
        in progress stays saved on the server — its remaining
        time frozen, not its finish time — and pressing Start
        again picks it up from exactly where it stopped. The
        music stops too."""
        if not self._quests_active:
            self.announce("Quests are not running.")
            return
        self._pause_current_quest()
        self._quests_active = False
        self._quest_current = None
        self._refresh_music()
        self.announce(
            "Quests stopped. Come back any time — there will always "
            "be another task waiting.")
        self.refresh_all()

    def _begin_next_quest(self):
        """Start the next quest in the loop: the saved one
        first when there is one, otherwise the first quest
        on the board, dealing a fresh one when the board
        is empty. Quests keep coming, one after another.
        A stale quest — one the server says is already
        finished, or no longer on the board — is dropped
        and the next one is tried, instead of stopping the
        whole loop. The loop only stops on a real failure,
        like the server being unreachable."""
        if not self._quests_active:
            return
        if self._quest_current:
            if self._begin_quest(self._quest_current):
                return
            if not self._quests_active:
                return
            # The saved quest was stale: drop it and try the board.
            self._quest_current = None
        while self._quest_board:
            if self._begin_quest(self._quest_board[0]):
                return
            if not self._quests_active:
                return
            # Stale: drop it and try the next one on the board.
            self._quest_board = self._quest_board[1:]
        data, error = online_save.new_quest(self.online_config)
        if error:
            self.server_problem(error)
            self._quests_active = False
            self._refresh_music()
            return
        self._apply_quest_data(data)
        self._board_add_quest(data.get("quest"))
        if not self._quest_board:
            self.announce("There are no quests on the board right now.")
            return
        self._begin_quest(self._quest_board[0])

    def _begin_quest(self, quest):
        """Start one quest, in the giver's own voice. A
        co-op quest (the Grand Hangout Fair) is joined first,
        so the server knows this player helped. The server
        records when the quest started, so it can check the
        quest really took its time. Returns True when the
        quest started. A quest the server says is already
        finished, or is no longer on the board, is stale:
        False, with no announcement and the loop left
        running, so the caller can try the next quest
        instead of stopping everything. Any other failure
        stops the loop, as before."""
        quest = quest or {}
        if quest.get("coop"):
            _data, error = online_save.join_quest(
                self.online_config, quest["id"])
            if error:
                self.announce(error)
                self._quests_active = False
                self._refresh_music()
                self.refresh_all()
                return False
        data, error = online_save.start_quest(
            self.online_config, quest["id"])
        if error:
            if ("already finished" in error
                    or "not on your board" in error):
                return False
            self.announce(error)
            self._quests_active = False
            self._refresh_music()
            self.refresh_all()
            return False
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])
        started = data.get("quest") or quest
        self._quest_current = started
        self._quest_last_progress_at = time.time()
        giver = started.get("giver", "Bolt")
        voice = started.get("giver_voice")
        # Phase 28: the giver asks the player by name for
        # help, in their own voice — never a generic "asks".
        # The giver and voice come from the server's answer,
        # never the quest template (the starting board
        # shuffles givers, so the template's giver can differ).
        self.announce_as(
            quests.quest_start_line(
                giver,
                self.fighter.get("name", "Katprincess"),
                started.get("description", ""),
                game_logic.format_time(
                    (started.get("duration_minutes") or 15) * 60),
                quest_id=started.get("id")),
            voice)
        # The quest's ambience loop starts now, under the
        # music and the voice, and keeps playing until the
        # quest completes, stops, pauses, or the player
        # leaves the hangout.
        self._refresh_ambience()
        self.refresh_all()
        return True

    def _complete_current_quest(self):
        """The quest's time is up: ask the server to finish
        it. The server checks the board, the time, and the
        co-op join — and never checks repairs, so a quest
        completes while repairing exactly like a healthy one.
        Then the next quest starts at once."""
        quest = self._quest_current
        if not quest:
            return
        data, error = online_save.complete_quest(
            self.online_config, quest["id"])
        if error:
            # The server's clock says it is not done yet.
            # Keep the quest and say so, in plain words.
            self.announce(error)
            return
        finished_id = quest["id"]
        self._quest_current = None
        # The server's answer does not include the updated
        # board, so drop the finished quest from the local
        # board here. Without this the loop tries to start
        # the just-finished quest again, the server says it
        # is already finished, and the loop dies — exactly
        # what Makenna saw on 2026-11-18. _apply_quest_data
        # still takes the board when the server does send one.
        self._quest_board = [q for q in self._quest_board
                             if q.get("id") != finished_id]
        self._apply_quest_data(data)
        voice = data.get("giver_voice")
        if data.get("message"):
            self.announce_as(data["message"], voice)
        if data.get("tier_line"):
            self.announce_as(data["tier_line"], voice)
        # Reputation, in the giver's voice: what she gained,
        # her new total with this giver, and how far to the
        # next tier — or the top tier, when there is no next
        # one. The tier-crossing line above still speaks too.
        # Renown (Phase 23) can make the gain 2 instead of 1.
        giver = data.get("giver") or quest.get("giver")
        rep = (data.get("reputation") or {}).get(giver) \
            if giver else None
        if giver and rep is not None:
            gained = 1 + (1 if data.get("bonus_reputation") else 0)
            self.announce_as(
                quests.reputation_line(
                    giver, int(rep), gained=gained,
                    fighter_name=self.fighter.get("name", "Katprincess")),
                voice)
        # Quest XP (Phase 23): what she earned, how far to the
        # next quest level, and a level-up line when it levels
        # her up — all in the giver's voice. The numbers come
        # from the server, never invented here. Renown's bonus
        # reputation is announced in its own words, too.
        if data.get("quest_xp_line"):
            self.announce_as(data["quest_xp_line"], voice)
        if data.get("quest_level_line"):
            self.announce_as(data["quest_level_line"], voice)
        if data.get("bonus_reputation"):
            self.announce_as(
                "Bonus reputation, %s — thank you!"
                % self.fighter.get("name", "Katprincess"), voice)
        if data.get("gift_pending"):
            self.announce(
                "I've got a free gift waiting. Press 1 for a free weapon "
                "upgrade, or 2 for a free armor upgrade.")
        # The finished quest's ambience loop stops here: the
        # next quest starts its own loop in _begin_next_quest —
        # or, in the study, the learning loop plays again while
        # the next study quest waits out its 10 to 15 minute gap.
        self.sounds.stop_ambience()
        if self._in_study:
            self._study_quest_next_at = (
                time.time()
                + self.random.randint(*spells.STUDY_QUEST_GAP_MINUTES) * 60)
            self._begin_next_study_quest()
        else:
            self._begin_next_quest()
        self.refresh_all()

    def _quest_progress_update(self, now):
        """Every 5 minutes, the giver speaks a progress
        update in their own voice, so the player always
        knows where the quest stands without asking. The
        percent comes from the quest's own duration, so it
        stays right even after a pause and a resume. When
        the fighter is repairing, the update says so and
        how long repairs have left; when not repairing,
        no repair line — the update stays short."""
        quest = self._quest_current
        if not quest:
            return
        finish = quest.get("finish_at") or 0
        total = max(1.0, (quest.get("duration_minutes") or 15) * 60)
        left = max(0.0, finish - now)
        done = max(0.0, min(1.0, 1.0 - left / total))
        # Phase 28: the giver speaks the quest part in their
        # own voice — and the repair part is a separate line
        # in the player's own voice, not the giver's. The
        # two lines are queued in order, so the giver is
        # still heard first.
        self.announce_as(
            quests.quest_progress_line(
                quest.get("giver", "Bolt"),
                int(done * 100),
                game_logic.format_time(left),
                quest_id=quest.get("id"),
                fighter_name=self.fighter.get("name", "Katprincess")),
            quest.get("giver_voice"))
        if game_logic.is_repairing(self.fighter):
            self.announce(
                "I'm still repairing, %s left."
                % game_logic.format_time(
                    game_logic.repair_left_seconds(self.fighter)))
        self._quest_last_progress_at = now

    def find_another_quest(self):
        """Find me another quest: the server deals one fresh
        quest, endlessly generated, and adds it to the board.
        No daily cap; a quest can only be completed once."""
        if not self._in_hangout:
            self.announce(
                "Go to the hangout first. It is on the More tab, "
                "under Visit the hangout.")
            return
        if not self.online_config:
            self.announce("Quests need the online key.")
            return
        data, error = online_save.new_quest(self.online_config)
        if error:
            self.server_problem(error)
            return
        self._apply_quest_data(data)
        quest = data.get("quest")
        if quest:
            self._board_add_quest(quest)
            self.announce_as(
                "%s has a new quest for you, %s: %s, %s, %s credits. "
                "%s asks: %s"
                % (quest.get("giver"),
                   self.fighter.get("name", "Katprincess"),
                   quest.get("name"), quest.get("difficulty"),
                   quests.quest_reward(
                       quest.get("difficulty"),
                       quests.quest_level_of(self.fighter)),
                   quest.get("giver"), quest.get("description")),
                quest.get("giver_voice"))
        self.refresh_all()

    def hear_quests(self):
        """Hear the board, one quest at a time, in plain words:
        name, difficulty, credits, and who gives it. The board
        stays short: 5 to start, one more at a time."""
        if not self._quest_board:
            self.announce(
                "No quests on the board yet. Press Start and the "
                "first quest will be given to you.")
            return
        lines = []
        for quest in self._quest_board[:5]:
            lines.append(
                "%s, %s, %s credits, from %s."
                % (quest.get("name"), quest.get("difficulty"),
                   quests.quest_reward(
                       quest.get("difficulty"),
                       quests.quest_level_of(self.fighter)),
                   quest.get("giver")))
        self.announce("; ".join(lines))

    # -- the study (Phase 38) ----------------------------------------

    def start_study_quests(self):
        """Start the study quest loop: quests from the witch
        givers (Hazel, Rowan, Wren, Bram) run in the study
        loop, one after another, while you stay in the study.
        Called on its own by Enter study (Phase 38b) — the
        player never presses Start any more; entering the
        study starts the quests. The first quest starts at
        once; after one ends, the next is dealt 10 to 15
        minutes later, so there is time to study in between.
        Study quests share the hangout's board and active
        quest — a quest is a quest — and are open to every
        fighter kind, robot, chef and witch alike. The study
        music plays while the loop runs."""
        if not self._in_study:
            self.announce(
                "Go to the study first. It is its own tab, after More.")
            return
        if self._study_quest_active:
            self.announce("Study quests are already started.")
            return
        if not self.online_config:
            self.announce(
                "Study quests need the online key. The game did not start "
                "with a .env file, so there is nothing to do quests from.")
            return
        data, error = online_save.get_quests(self.online_config)
        if error:
            self.server_problem(error)
            return
        self._apply_quest_data(data)
        self._study_quest_active = True
        self._quests_active = True
        self._study_quest_next_at = 0.0
        self._refresh_music()
        # Start the spell loop at once too (Phase 39b): the
        # quest's own loop replaces it a moment later, when
        # the first quest is dealt — but if no quest can be
        # dealt, the spell loop is already playing.
        self._refresh_ambience()
        self.announce(
            "Study quests started. The witches and warlocks here will "
            "keep giving you tasks while you study.")
        self._begin_next_study_quest()
        self.refresh_all()

    def stop_study_quests(self):
        """Press Stop: the study quest loop stops cleanly. The
        quest in progress stays saved on the server — its
        remaining time frozen, not its finish time — and
        pressing Start again picks it up from exactly where it
        stopped. Learning a spell is not stopped: it keeps its
        own clock while you stay in the study."""
        if not self._study_quest_active:
            self.announce("Study quests are not running.")
            return
        self._pause_current_quest()
        self._study_quest_active = False
        self._quests_active = False
        self._quest_current = None
        self._refresh_music()
        self._refresh_ambience()
        self.announce(
            "Study quests stopped. Come back any time — there will "
            "always be another task waiting.")
        self.refresh_all()

    def _begin_next_study_quest(self):
        """Deal the next study quest: the saved one first when
        there is one, otherwise a fresh one from a witch giver
        — never from the shared board, which may hold hangout
        quests from the other givers. After a study quest ends,
        the next one is only dealt once the 10 to 15 minute gap
        has passed, so there is time to study in between; while
        waiting, the learning ambience plays again."""
        if not self._study_quest_active or not self._in_study:
            return
        if self._quest_current:
            if self._begin_quest(self._quest_current):
                return
            if not self._study_quest_active:
                return
            # The saved quest was stale: drop it and deal fresh.
            self._quest_current = None
        now = time.time()
        if now < self._study_quest_next_at:
            self._refresh_ambience()
            return
        data, error = online_save.new_study_quest(self.online_config)
        if error:
            self.server_problem(error)
            self._study_quest_active = False
            self._quests_active = False
            self._refresh_music()
            return
        self._apply_quest_data(data)
        self._board_add_quest(data.get("quest"))
        if not self._quest_board:
            self.announce("There are no study quests on the board right now.")
            return
        # The quest just dealt is the last one on the board.
        if not self._begin_quest(self._quest_board[-1]):
            if not self._study_quest_active:
                return
            # Stale already — drop it and try again in a minute,
            # instead of dealing quest after quest in one second.
            self._quest_board = self._quest_board[:-1]
            self._study_quest_next_at = now + 60
            self._refresh_ambience()

    def _study_progress_update(self, now):
        """Every 5 minutes in the study, a progress update in
        the player's own voice (Makenna, Nov 25, 2026 — the
        study updates are the player's voice, not the givers'):
        the spell being learned and how long is left, the
        study quest when one is running, and repairs when
        repairing — including when repairs are done, if they
        finished while studying."""
        study = spells.study_of(self.fighter)
        if study:
            self.announce(spells.study_status_line(self.fighter, now))
        quest = self._quest_current
        if quest:
            finish = quest.get("finish_at") or 0
            total = max(1.0, (quest.get("duration_minutes") or 15) * 60)
            left = max(0.0, finish - now)
            done = max(0.0, min(1.0, 1.0 - left / total))
            self.announce(
                "My quest, %s, is %d percent done, %s left."
                % (quest.get("name", "a quest"), int(done * 100),
                   game_logic.format_time(left)))
        if game_logic.is_repairing(self.fighter):
            self.announce(
                "I'm still repairing, %s left."
                % game_logic.format_time(
                    game_logic.repair_left_seconds(self.fighter)))
        self._study_last_progress_at = now

    def do_start_study(self, element, auto=False):
        """Learn — or upgrade one level of — the next spell for
        one element. Learning costs NO credits at all — it is
        time-based only, not credit-based (Makenna, Nov 25,
        2026) — so the game asks first and says the time and
        the study rule: the clock only ticks while you are in
        the study. A paused spell is picked up again, with the
        same time left. One spell at a time: a spell already
        being learned blocks any other. Only a witch or warlock
        can learn spells; study quests are open to everyone.
        auto=True is the study picking the next spell on its own
        after one finishes (Phase 38b): no second question,
        because entering the study already said yes to learning
        one spell at a time, in a random order, while staying
        here — the start is still announced, with the trainer's
        line and the server's line naming the spell."""
        fighter = self.fighter
        if fighter.get("kind", "robot") != "witch":
            self.announce(
                "Only a witch or warlock can learn spells in the study.")
            return False
        if not self.online_config:
            self.announce(
                "Learning spells needs the server, and I am not "
                "signed in right now.")
            return False
        nxt = spells.next_spell_for_element(fighter, element)
        if nxt is None:
            self.announce("I do not know that spell.")
            return False
        tier, name, level_now, is_upgrade = nxt
        study = spells.study_of(fighter)
        if study and (study.get("element"), study.get("tier")) != (element, tier):
            self.announce(
                "I am already learning %s. Finish it first, in the study."
                % (study.get("name") or "a spell"))
            return False
        if study and not study.get("paused"):
            # Already learning this very spell: say where it stands.
            self.announce(spells.study_status_line(fighter))
            return False
        resume = bool(study and study.get("paused"))
        if not resume and not auto:
            ok, reason = spells.can_learn(fighter, element, tier)
            if not ok:
                self.announce(reason)
                return False
            minutes = spells.spell_minutes(tier)
            if is_upgrade:
                what = "Upgrade %s to level %d" % (name, level_now + 1)
            else:
                what = "Learn %s" % name
            question = (
                "%s? It takes %d minutes, and it costs no credits — "
                "learning is time-based only. The clock only ticks "
                "while I am in the study — leaving pauses it, coming "
                "back picks it up where I left off. Once this one is "
                "learned, the study will pick the next spell on its "
                "own, one at a time, in a random order, while I stay "
                "here. Do you want to do it?"
                % (what, minutes))
            if not self._confirm(question):
                self.announce("I keep studying what I have.")
                return False
        # A resume keeps the same time left, and a fresh start
        # costs nothing — learning is time-based only. The server
        # decides either way, and sends the study back.
        data, error = online_save.study_start(
            self.online_config, element, tier)
        if error:
            self.announce(error)
            self.refresh_all()
            return False
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])
        # The trainer teaches the spell, in their own voice,
        # talking to the player directly by name (Makenna,
        # Nov 25, 2026) — Hazel, Rowan or Wren for a first
        # learning, Bram for an upgrade. The trainer speaks
        # first; the server's own line follows with the facts.
        # An unknown element or voice falls back to the
        # player's voice alone — the game never goes silent.
        trainer, voice = spells.trainer_for_spell(element, is_upgrade)
        if trainer and voice:
            line = spells.trainer_opening_line(
                trainer, fighter.get("name", "Katprincess"), name)
            if line:
                self.announce_as(line, voice)
        if data.get("message"):
            self.announce(data["message"])
        self._study_last_progress_at = time.time()
        self._refresh_music()
        self._refresh_ambience()
        self.refresh_all()
        return True

    def enter_study(self):
        """The one study button (Phase 38b, Makenna Nov 25,
        2026): the player never picks a spell. Pressing Enter
        study starts the study — the music, a spell picked at
        random, and study quests on their own. One spell at a
        time, in a random order, never all of one element
        first. A paused spell is picked up again, with the
        same time left. Study quests are open to everyone, so
        a robot or chef entering the study gets quests, just
        no spell learning. Entering the study is the yes
        (Phase 39b, Makenna Nov 25, 2026): the first spell
        starts at once, with no question at all — just the
        trainer's line and the spell and its time — and after
        that the study keeps teaching on its own while
        the player stays here. Leaving the tab pauses the
        learning clock and stops the quest loop, as before."""
        if not self.online_config:
            self.announce(
                "The study needs the server, and I am not signed "
                "in right now.")
            return
        fighter = self.fighter
        if fighter.get("kind", "robot") != "witch":
            if not self._study_quest_active:
                self.start_study_quests()
            self.announce(
                "Only a witch or warlock can learn spells in the "
                "study — but the study quests are open to "
                "everyone, so I will do those.")
            return
        study = spells.study_of(fighter)
        if study and not study.get("paused"):
            # Already learning: say where it stands, and make
            # sure the quests are running too.
            if not self._study_quest_active:
                self.start_study_quests()
            self.announce(spells.study_status_line(fighter))
            return
        if study and study.get("paused"):
            # Pick up the paused spell again, free, with the
            # same time left — then start the quests, when the
            # pick-up worked.
            if self.do_start_study(study.get("element")):
                if not self._study_quest_active:
                    self.start_study_quests()
            return
        pick = spells.pick_next_study_spell(fighter, rng=self.random)
        if pick is None:
            if not self._study_quest_active:
                self.start_study_quests()
            self.announce(
                "I have learned every spell there is to learn.")
            return
        element = pick[0]
        # No question at all (Phase 39b, Makenna Nov 25,
        # 2026): entering the study IS the yes, so the first
        # spell starts the same way the study auto-starts the
        # next one after a spell finishes — auto=True skips
        # the Yes/No in do_start_study and just announces the
        # trainer's line and the spell and its time. If the
        # start fails, nothing else starts either.
        if not self.do_start_study(element, auto=True):
            return
        if not self._study_quest_active:
            self.start_study_quests()

    def _auto_start_next_study(self):
        """After a spell finishes, the study picks the next one
        on its own (Phase 38b) — one at a time, in a random
        order — while the player is still in the study. No
        second question: entering the study already said yes.
        The start is still announced, with the trainer's line
        and the server's line naming the spell. Learning costs
        no credits, so nothing ever stops it for money — it
        keeps going while the player stays here."""
        if not self._in_study:
            return
        if self.fighter.get("kind", "robot") != "witch":
            return
        if not self.online_config:
            return
        if spells.study_of(self.fighter) is not None:
            # Something is already being learned — one at a
            # time, always — so there is nothing to start.
            return
        pick = spells.pick_next_study_spell(
            self.fighter, rng=self.random)
        if pick is None:
            return
        element, _tier, _name, _level_now, _is_upgrade = pick
        # No credit check: learning costs no credits at all,
        # it is time-based only (Makenna, Nov 25, 2026).
        self.do_start_study(element, auto=True)

    def _pause_study(self):
        """Freeze the spell being learned, on the server, so its
        clock stops while the player is away from the study.
        Best effort, like _pause_current_quest: when the server
        cannot be reached, learning still stops locally, and
        the study stays saved with its frozen time. The server
        never completes a paused study."""
        if not spells.study_of(self.fighter) or not self.online_config:
            return
        data, error = online_save.study_pause(self.online_config)
        if error or not data:
            return
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])

    def _complete_study(self):
        """The spell's time is up in the study: ask the server
        to finish learning it. The server checks the time and
        grants the level; the trainer speaks first in their own
        voice (Makenna, Nov 25, 2026) — Hazel, Rowan or Wren
        for a first learning, Bram for an upgrade — then the
        server's own line, and the game plays that spell's own
        sound effect, so you hear the spell you just learned.
        Phase 39c (Makenna, Nov 25, 2026): her PC clock runs
        a little ahead of the server's, so the client can
        think a spell is due a minute or two before the
        server does. A refused completion is therefore
        retried at most every 10 seconds, and its refusal is
        said once per spell — never once a second, which
        flooded the narration queue with identical lines and
        buried the next spell's trainer line (and the quest
        giver's line) behind them."""
        study = spells.study_of(self.fighter)
        now = time.time()
        key = None
        if study is not None:
            key = (study.get("element"), study.get("tier"),
                   study.get("finish_at"))
            if (key == self._study_complete_try_key
                    and now - self._last_study_complete_try_at < 10.0):
                return
            self._study_complete_try_key = key
            self._last_study_complete_try_at = now
        data, error = online_save.study_complete(self.online_config)
        if error:
            # The server's clock says it is not done yet.
            # Its own fighter comes back even with a
            # plain-words error (online_save.rpc): take it, so
            # a local study record the server has already
            # moved on from stops being retried at all.
            if data and data.get("fighter"):
                self.use_server_fighter(data["fighter"])
                self.refresh_all()
            # Say the refusal once per spell, not once a
            # second: the retries in between are silent.
            if key != self._study_complete_error_key:
                self._study_complete_error_key = key
                self.announce(error)
            return
        # The spell IS learned now: drop any queued "not
        # learned yet" lines — they are stale, and they must
        # not drown the trainer's line that follows.
        self._study_complete_error_key = None
        self._study_complete_try_key = None
        self._narration_queue = [
            entry for entry in self._narration_queue
            if "not learned yet" not in (entry[0] or "")]
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])
        spell = data.get("spell") or {}
        if spell.get("element"):
            level = int(spell.get("level") or 1)
            trainer, voice = spells.trainer_for_spell(
                spell.get("element"), level > 1)
            if trainer and voice:
                fighter_name = self.fighter.get("name", "Katprincess")
                spell_name = spell.get("name") or "a spell"
                if level > 1:
                    line = spells.trainer_upgrade_line(
                        fighter_name, spell_name, level)
                else:
                    line = spells.trainer_learn_line(
                        trainer, fighter_name, spell_name)
                if line:
                    self.announce_as(line, voice)
        if data.get("message"):
            self.announce(data["message"])
        if spell.get("element"):
            self.sounds.play_spell(spell["element"])
        self._refresh_music()
        self._refresh_ambience()
        self.refresh_all()
        # Phase 38b: the study picks the next spell on its own
        # while the player is still here — one at a time, in a
        # random order — so learning never stalls on a finished
        # spell. Leaving the study pauses it instead.
        self._auto_start_next_study()

    def choose_quest_gift(self, slot):
        """Take a free gift upgrade from a quest giver (Friend
        tier): weapon or armor, your choice, instant. No
        credits, no time, no queue."""
        if not self._quest_gift_pending:
            self.announce("No free gift is waiting for you right now.")
            return
        if not self.online_config:
            self.announce("Quests need the online key.")
            return
        data, error = online_save.choose_quest_gift(
            self.online_config, slot)
        if error:
            self.announce(error)
            return
        self._quest_gift_pending = None
        if data.get("fighter"):
            self.use_server_fighter(data["fighter"])
        if data.get("message"):
            self.announce(data["message"])
        self.refresh_all()

    def _confirm(self, text):
        """Ask yes or no with a plain-words question. Returns
        True only when the player says yes. Used before any
        spending that cannot be undone: a max-affordable queue
        and a respec. The dialog is a real Yes/No dialog with
        Yes as the default button, not a MessageBox: Enter on
        Yes must mean yes."""
        dialog = _ConfirmDialog(self, text)
        try:
            return dialog.ShowModal() == wx.ID_YES
        finally:
            dialog.Destroy()

    def _announce_upgrade_block(self):
        """Speak the one-upgrade-at-a-time block, with how long
        is left on the running set. Used whenever the player
        tries to start another upgrade while one is running —
        single or max-affordable, either slot — so the answer
        is never just "wait", it always says how long the wait
        is. The fighter here is the server's copy (online) or
        the local one (offline), so the time left is fresh."""
        status = game_logic.upgrade_status(self.fighter)
        if status:
            self.announce(
                "I've already got an upgrade running. I'll wait for it to "
                "finish first. " + status
            )
        else:
            self.announce(
                "I've already got an upgrade running. I'll wait for it to "
                "finish first."
            )

    def do_upgrade(self, slot):
        """Start a timed upgrade. Online, the server checks the
        credits, takes the cost and sets the finish time. One
        upgrade set at a time: if a set is already running —
        on either slot — the server (or the local rule, when
        offline) says so, and the block is spoken with the
        time left on the running set."""
        if self.online_config:
            server_fighter, _messages, error = online_save.start_upgrade(
                self.online_config, slot
            )
            self.use_server_fighter(server_fighter)
        else:
            error = game_logic.start_upgrade(self.fighter, slot)
        if error:
            if error.startswith("An upgrade is already running"):
                self._announce_upgrade_block()
            else:
                self.announce(error)
            self.refresh_all()
            return
        # The upgrade the server just started must be a real
        # one (Phase 30): a null level or finish here used to
        # crash this announce, so say it plainly instead.
        if game_logic.upgrade_is_running(self.fighter):
            upgrade = self.fighter["upgrade"]
            self.announce(
                "I'm upgrading my %s to level %d. It'll be done in %s."
                % (
                    upgrade.get("name") or upgrade["slot"],
                    upgrade["level"],
                    game_logic.format_time(upgrade["finish"] - time.time()),
                )
            )
        else:
            self.announce(
                "That upgrade did not start cleanly. No upgrade is running."
            )
        self.refresh_all()

    def do_spend_stat(self, stat):
        """Spend one banked stat point on the highlighted stat.
        One point per press: stay on the line and press Enter
        again to spend another point there, in the same stat
        or a different one. Online, the server decides."""
        if self.online_config:
            server_fighter, message, _messages, error = online_save.spend_stat(
                self.online_config, stat
            )
            self.use_server_fighter(server_fighter)
        else:
            error, message = game_logic.spend_stat(self.fighter, stat)
        if error:
            self.announce(error)
            self.refresh_all()
            return
        self.announce(message)
        self.refresh_all()

    def do_spend_quest_stat(self, stat):
        """Spend one banked quest point on the highlighted quest
        stat. One point per press: stay on the line and press
        Enter again to spend another point there, in the same
        stat or a different one. Max 10 points in any one quest
        stat. Online, the server decides."""
        if self.online_config:
            server_fighter, message, _messages, error = online_save.spend_quest_stat(
                self.online_config, stat
            )
            self.use_server_fighter(server_fighter)
        else:
            error, message = game_logic.spend_quest_stat(self.fighter, stat)
        if error:
            self.announce(error)
            self.refresh_all()
            return
        self.announce(message)
        self.refresh_all()

    def do_switch_fighter(self, kind):
        """Change fighter to a new kind. The first switch is free;
        after that it costs credits, doubling every switch, with
        no cap. The game asks first and says exactly what resets
        and what stays, because a switch cannot be undone: combat
        level and stats, quest level and quest stats, reputation
        with every giver, and weapon/armor upgrades all start
        over, while Healing stays and credits stay apart from
        the switch cost. Online, the server decides. Switching
        is allowed while repairing or upgrading: the new fighter
        starts at full health, so a repair ends, and a running
        upgrade ends with the old weapon and armor."""
        fighter = self.fighter
        current = fighter.get("kind", "robot")
        gender = fighter.get("gender", "male")
        if kind == current:
            self.announce(
                "I am already a %s."
                % game_logic.kind_word(current, gender))
            return
        if kind not in ("robot", "chef", "witch"):
            self.announce("Pick robot, chef or witch for your fighter.")
            return
        if not self.online_config:
            self.announce(
                "Changing fighter needs the server, and I am not "
                "signed in right now.")
            return
        switches = fighter.get("kind_switches", 0) or 0
        cost = game_logic.switch_cost(switches)
        credits = game_logic.credits_of(fighter)
        healing = fighter.get("healing_level", 0) or 0
        word = game_logic.kind_word(kind, gender)
        if cost > credits:
            self.announce(
                "Changing fighter costs %d credits and I have %d credits."
                % (cost, credits))
            return
        if cost <= 0:
            cost_line = "This first switch is free."
        else:
            cost_line = (
                "This switch costs %d credits and I have %d credits."
                % (cost, credits))
        extra = ""
        if game_logic.upgrade_is_running(fighter):
            extra = (" My upgrade that is running now ends.")
        if game_logic.is_repairing(fighter):
            extra += " My repair ends and I start at full health."
        question = (
            "Change fighter to %s? %s "
            "What changes: my combat level and stats go back to "
            "level 1, my quest level and quest stats go back to "
            "level 1, my reputation with every quest giver goes "
            "back to zero, and my weapon and armor start over at "
            "level 1 with no upgrades.%s "
            "What stays: my Healing skill stays at level %d, my "
            "credits stay apart from the cost of the switch, and "
            "my wins and losses stay. Do you want to do it?"
            % (word, cost_line, extra, healing)
        )
        if not self._confirm(question):
            self.announce(
                "I stay a %s." % game_logic.kind_word(current, gender))
            return
        server_fighter, message, _messages, error = online_save.switch_kind(
            self.online_config, kind
        )
        self.use_server_fighter(server_fighter)
        if error:
            self.announce(error)
            self.refresh_all()
            return
        self.announce(message)
        self.refresh_all()

    def do_respec(self):
        """Reset all 5 stats, refunding every spent point. The
        first respec is free; later ones cost 100 credits. A
        respec cannot be undone, so the game asks first."""
        fighter = self.fighter
        spent = sum(game_logic.stats_of(fighter).values())
        if spent <= 0:
            self.announce("I have no stat points spent to reset.")
            return
        used = fighter.get("respecs_used", 0)
        if used <= 0:
            question = (
                "Reset all my stats? I have %d stat points spent. "
                "They will all come back to spend again. My first "
                "respec is free. Do you want to do it?" % spent
            )
        else:
            question = (
                "Reset all my stats? I have %d stat points spent. "
                "They will all come back to spend again. This respec "
                "costs 100 credits and I have %d credits. Do you "
                "want to do it?"
                % (spent, game_logic.credits_of(fighter))
            )
        if not self._confirm(question):
            self.announce("My stats stay as they are.")
            return
        if self.online_config:
            server_fighter, message, _messages, error = online_save.respec_stats(
                self.online_config
            )
            self.use_server_fighter(server_fighter)
        else:
            error, message = game_logic.respec_stats(self.fighter)
        if error:
            self.announce(error)
            self.refresh_all()
            return
        self.announce(message)
        self.refresh_all()

    def do_max_upgrade(self, slot):
        """Start a max-affordable queue: as many levels as the
        credits allow. The wait is capped at 4 hours no matter
        how many levels (Phase 37): a long queue's levels come
        faster than the usual one-level wait, so they all fit.
        The game says the whole deal in plain words and asks
        first, because once started the queue runs to the end
        with no cancelling.
        One upgrade set at a time: if a set is already running
        the player is told so — with the time left — before
        any question is asked, so they never confirm a queue
        the server would then refuse (that could happen with
        a stale local copy, which the server's answer would
        otherwise only correct after the Yes)."""
        fighter = self.fighter
        # A broken upgrade record (Phase 30: null level or
        # finish) does not block here: it is not a real
        # running upgrade, and the server is the judge — it
        # refuses when a real set is running, and the fixed
        # server clears the broken one.
        if game_logic.upgrade_is_running(fighter):
            self._announce_upgrade_block()
            return
        plan = game_logic.max_affordable(fighter, slot)
        if plan.get("maxed"):
            self.announce(
                "My %s is already at its best, level %d."
                % (plan["name"], game_logic.HEALING_MAX_LEVEL)
            )
            return
        if not plan["levels"]:
            self.announce(
                "My next %s level costs %d credits and I have %d credits."
                % (plan["name"], plan["next_cost"], plan["credits"])
            )
            return
        count = len(plan["levels"])
        if plan.get("time_scale", 1) < 1:
            # The queue was shrunk to fit in 4 hours (Phase 37):
            # say so plainly, so the player hears the wait is a
            # cap, not the raw total.
            wait_words = "%s at most" % game_logic.format_time(plan["seconds"])
        else:
            wait_words = game_logic.format_time(plan["seconds"])
        question = (
            "My %s can go up %d %s for %d credits, leaving %d. "
            "It will take %s, one level after another. Do you want "
            "to do it?"
            % (
                plan["name"],
                count,
                "level" if count == 1 else "levels",
                plan["cost"],
                plan["credits_left"],
                wait_words,
            )
        )
        if not self._confirm(question):
            self.announce("Nothing was bought. My credits stay as they are.")
            return
        if self.online_config:
            server_fighter, message, _messages, error = online_save.max_upgrade(
                self.online_config, slot
            )
            self.use_server_fighter(server_fighter)
        else:
            error, message = game_logic.start_max_upgrade(self.fighter, slot)
        if error:
            if error.startswith("An upgrade is already running"):
                self._announce_upgrade_block()
            else:
                self.announce(error)
            self.refresh_all()
            return
        self.announce(message)
        self.refresh_all()

    def activate_current(self):
        """Enter on the selected list item."""
        tab = self.current_tab()
        box = self.lists[tab]
        index = box.GetSelection()
        if index < 0:
            return
        item = box.GetString(index)
        fighter = self.fighter
        if item == "Hear my fighter status":
            self.announce(game_logic.status_text(fighter))
        elif item.startswith("Go to "):
            self.notebook.SetSelection(self.TAB_NAMES.index(item[6:]))
        elif tab == "Home" and item.startswith("I have "):
            if "quest" in item:
                # Quest points live on the Home tab too (Phase 36
                # fix): the line says how many are banked, and
                # Enter on a quest stat spends one.
                qpoints = quests.quest_points_of(fighter)
                if qpoints > 0:
                    self.announce(
                        "I have %d quest %s to spend. Move with the arrow "
                        "keys to a quest stat and press Enter to spend one point."
                        % (qpoints, "point" if qpoints == 1 else "points")
                    )
                else:
                    self.announce(
                        "I have no quest points to spend right now. I get "
                        "1 quest point every time I go up a quest level."
                    )
            else:
                points = fighter.get("stat_points", 0)
                if points > 0:
                    self.announce(
                        "I have %d stat %s to spend. Move with the arrow "
                        "keys to a stat and press Enter to spend one point."
                        % (points, "point" if points == 1 else "points")
                    )
                else:
                    self.announce(
                        "I have no stat points to spend right now. I get "
                        "2 stat points every time I level up."
                    )
        elif tab == "Home" and item.startswith("Strength,"):
            self.do_spend_stat("strength")
        elif tab == "Home" and item.startswith("Defense,"):
            self.do_spend_stat("defense")
        elif tab == "Home" and item.startswith("Health,"):
            self.do_spend_stat("health")
        elif tab == "Home" and item.startswith("Speed,"):
            self.do_spend_stat("speed")
        elif tab == "Home" and item.startswith("Luck,"):
            self.do_spend_stat("luck")
        elif tab == "Home" and item.startswith("Charm,"):
            self.do_spend_quest_stat("charm")
        elif tab == "Home" and item.startswith("Renown,"):
            self.do_spend_quest_stat("renown")
        elif tab == "Home" and item.startswith("Insight,"):
            self.do_spend_quest_stat("insight")
        elif tab == "Home" and item.startswith("Quest level "):
            self.announce(item)
        elif tab == "Home" and item.startswith("Reset all my stats"):
            self.do_respec()
        elif tab == "Combat" and item == "Fight":
            self.do_fight()
        elif tab == "Combat" and item.startswith("Idle fighting:"):
            self.toggle_idle()
        elif tab == "Shop" and item.startswith("Upgrade " + fighter["weapon_name"]):
            self.do_upgrade("weapon")
        elif tab == "Shop" and item.startswith("Upgrade " + fighter["armor_name"]):
            self.do_upgrade("armor")
        elif tab == "Shop" and item.startswith(
            "Max affordable: " + fighter["weapon_name"] + " up"
        ):
            self.do_max_upgrade("weapon")
        elif tab == "Shop" and item.startswith(
            "Max affordable: " + fighter["armor_name"] + " up"
        ):
            self.do_max_upgrade("armor")
        elif tab == "Shop" and item.startswith(
            "Upgrade " + game_logic.HEALING_NAME
        ):
            self.do_upgrade("healing")
        elif tab == "Shop" and item.startswith(
            "Max affordable: " + game_logic.HEALING_NAME + " up"
        ):
            self.do_max_upgrade("healing")
        elif tab == "Shop" and item.startswith(
            game_logic.HEALING_NAME + " is at its best"
        ):
            self.announce(item)
        elif tab == "Shop" and item.startswith("Max affordable: my next"):
            self.announce(item)
        elif tab == "Shop" and (item.startswith("Upgrading ")
                                 or item.startswith("I'm upgrading")):
            self.announce(game_logic.upgrade_status(fighter) or "No upgrade is running.")
        elif tab == "More" and item == "Visit the hangout":
            # Entering the hangout alone starts nothing: the
            # cafe music plays only once quests have started
            # (see _refresh_music), and quests only start
            # when the player presses Start. Leaving the More
            # tab leaves the hangout (see on_tab_changed).
            self._in_hangout = True
            # The visible list must be rewritten at once:
            # list_items("More") only offers Start quests
            # once _in_hangout is True, and without this
            # refresh the player keeps seeing the old list
            # (Visit, look-ups, and so on) with no Start
            # anywhere — Makenna reported exactly that on
            # 2026-11-18. Land the selection on Start quests.
            self.refresh_list("More")
            _start = [i for i, _item in enumerate(
                self.list_items("More"))
                if _item.startswith("Start quests")]
            if _start:
                self.lists["More"].SetSelection(_start[0])
            self._refresh_music()
            self.announce(
                "You are in the hangout. Press Start when you want "
                "tasks. The music starts when you press Start.")
        elif tab == "More" and item.startswith("Start quests"):
            self.start_quests()
        elif tab == "More" and item.startswith("Stop quests"):
            self.stop_quests()
        elif tab == "More" and item.startswith("Find me another quest"):
            self.find_another_quest()
        elif tab == "More" and item.startswith("Hear my quests"):
            self.hear_quests()
        elif tab == "More" and item.startswith("Quest level "):
            self.announce(item)
        elif tab == "More" and item.startswith("I have ") and "quest" in item:
            qpoints = quests.quest_points_of(fighter)
            if qpoints > 0:
                self.announce(
                    "I have %d quest %s to spend. Move with the arrow "
                    "keys to a quest stat and press Enter to spend one point."
                    % (qpoints, "point" if qpoints == 1 else "points")
                )
            else:
                self.announce(
                    "I have no quest points to spend right now. I get "
                    "1 quest point every time I go up a quest level."
                )
        elif tab == "More" and item.startswith("Charm,"):
            self.do_spend_quest_stat("charm")
        elif tab == "More" and item.startswith("Renown,"):
            self.do_spend_quest_stat("renown")
        elif tab == "More" and item.startswith("Insight,"):
            self.do_spend_quest_stat("insight")
        elif tab == "More" and item.startswith(
                "Choose my free gift: weapon"):
            self.choose_quest_gift("weapon")
        elif tab == "More" and item.startswith(
                "Choose my free gift: armor"):
            self.choose_quest_gift("armor")
        elif tab == "More" and item.startswith("Quests live in the hangout"):
            self.announce(
                "Quests live in the hangout. Press Enter on Visit the "
                "hangout, then press Start when you want tasks.")
        elif tab == "More" and item.startswith("Hear repair status"):
            if game_logic.is_repairing(fighter):
                self.announce(
                    "I'm repairing. I'll be done in %s."
                    % game_logic.format_time(
                        game_logic.repair_left_seconds(fighter)
                    )
                )
            else:
                self.announce("No repairs running. I'm ready.")
        elif tab == "More" and item.startswith("Export my data"):
            self.do_export()
        elif tab == "More" and item.startswith("Look up a player"):
            self.do_lookup()
        elif tab == "More" and item.startswith("See who is online"):
            self.do_list_players()
        elif tab == "More" and item.startswith("Fight a player"):
            self.do_fight_player()
        elif tab == "More" and item.startswith("My player code"):
            if self.player_account:
                self.announce(
                    "Your username is %s, and your player code is %s."
                    % (self.player_account["username"],
                       self.player_account["player_code"])
                )
            else:
                self.announce("You do not have an account yet.")
        elif tab == "More" and item.startswith("Online"):
            self.announce(self.online_status)
        elif tab == "Study" and item.startswith("Enter study"):
            self.enter_study()
        elif tab == "Study" and item.startswith("Studying in the study"):
            self.announce(spells.study_status_line(fighter))
        elif tab == "Study" and item.startswith("Stop study quests"):
            self.stop_study_quests()
        elif tab == "Study" and item.startswith("Hear my quests"):
            self.hear_quests()
        elif tab == "Study" and item.startswith("I am "):
            self.announce(item)
        elif tab == "Study" and item.startswith("Only a witch"):
            self.announce(item)
        elif tab == "Settings" and item.startswith("Voice:"):
            gender = "female" if self.fighter.get("gender", "male") == "male" else "male"
            if self.online_config:
                server_fighter, error = online_save.set_voice(
                    self.online_config, gender
                )
                if error:
                    self.server_problem(error)
                    return
                self.use_server_fighter(server_fighter)
            else:
                self.fighter["gender"] = gender
            if self.voice is not None:
                self.voice.set_voice(voice_engine.voice_for_gender(gender))
            self.announce("Voice set to %s." % gender)
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Sound effects:"):
            self.sound_on = not self.sound_on
            self.sounds.set_enabled(self.sound_on)
            self._refresh_music()
            self._refresh_ambience()
            self.announce("Sound effects %s." % ("on" if self.sound_on else "off"))
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Background music:"):
            self.music_on = not self.music_on
            self._refresh_music()
            self._refresh_ambience()
            self.announce("Background music %s." % ("on" if self.music_on else "off"))
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Keep me signed in"):
            self.toggle_keep_signed_in()
        elif tab == "Settings" and item.startswith("Lower volume"):
            self.volume = max(0, self.volume - 10)
            self.sounds.set_volume(self.volume)
            self.announce("Volume %d percent." % self.volume)
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Raise volume"):
            self.volume = min(100, self.volume + 10)
            self.sounds.set_volume(self.volume)
            self.announce("Volume %d percent." % self.volume)
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Change fighter to "):
            word = item[len("Change fighter to "):].split(":")[0].strip()
            kind = {"warlock": "witch", "witch": "witch",
                    "robot": "robot", "chef": "chef"}.get(word)
            if kind:
                self.do_switch_fighter(kind)

    # -- events --------------------------------------------------------

    def on_list_activate(self, event):
        self.activate_current()
        event.Skip()

    def on_tab_changed(self, event):
        event.Skip()
        tab = self.current_tab()
        if self._last_tab == "More" and tab != "More":
            # Leaving the More tab leaves the hangout, and
            # stops the quest loop cleanly: the quest in
            # progress stays saved on the server, its
            # remaining time frozen, and Start picks it up
            # again from exactly there. The music stops too.
            if self._quests_active:
                self._pause_current_quest()
                self._quests_active = False
                self._quest_current = None
            self._in_hangout = False
        if self._last_tab == "Study" and tab != "Study":
            # Leaving the Study tab leaves the study, and stops
            # both clocks cleanly: the spell's remaining time
            # freezes on the server, and the study quest in
            # progress freezes too, like leaving the hangout.
            # Learning is picked up again from the Study list;
            # the quest is picked up again by Start.
            if self._study_quest_active:
                self._pause_current_quest()
                self._study_quest_active = False
                self._quests_active = False
                self._quest_current = None
            self._pause_study()
            self.sounds.stop_ambience()
            self._in_study = False
        if tab == "Study":
            self._in_study = True
            self._study_last_progress_at = time.time()
        self._last_tab = tab
        self.refresh_list(tab)
        # Switching tabs never starts music on its own; this
        # only stops it when the player has left the activity
        # it belongs to (or keeps the fight track while
        # auto-fighting).
        self._refresh_music()
        # And the ambience loop is re-asserted on every tab
        # switch (Phase 39b): leaving the Study tab stops it,
        # and coming back used to leave it silent even though
        # the music came back — the loop only ever started
        # again on the next quest or spell event, and the
        # once-a-second tick never re-asserted it. Asking for
        # the loop that is already playing does not restart
        # it, so this costs nothing when it is already playing.
        self._refresh_ambience()
        # Tab switching is silent (2026-11-18, Makenna):
        # NVDA already announces the tab and its list, so
        # Edge speaking the tab hint as well talks over it.
        # Show the hint as text only — no speak, no queued
        # narration. Edge speaks only for game events
        # (fight narration, quests, repairs, upgrades).
        # "Go to X" items, Left/Right tab keys and Escape
        # to Home all change tabs through here, so they
        # are all covered by this one change.
        self.message_line.SetLabel(self.TAB_HINTS[tab])

    def on_key(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()
        on_list = isinstance(focused, wx.ListBox)
        # Every game key press goes to the server, with the tab
        # it was pressed on. Only keys that do something in the
        # game are logged: F, Shift F, U, Shift U, A, Shift A,
        # R, Return, Escape.
        if on_list and key in (
            ord("f"), ord("F"), ord("u"), ord("U"), ord("a"), ord("A"),
            ord("h"), ord("H"), ord("r"),
            wx.WXK_RETURN, wx.WXK_ESCAPE,
        ):
            label = chr(key) if 32 <= key < 127 else str(key)
            self._log_online(
                "key_press", {"key": label, "tab": self.current_tab()}
            )

        if key == wx.WXK_ESCAPE:
            if self.idle_fighting:
                self.idle_fighting = False
                self.announce("Idle fighting off.")
                # Stopping auto-fight by hand stops its music
                # too, at once: the fight track belongs to the
                # auto-fight session, not to the Combat tab.
                self._refresh_music()
                self.refresh_all()
            elif self._study_quest_active:
                # Escape in the study stops study quests, the
                # same as the Stop button: the quest stays
                # saved on the server, and the music stops.
                self.stop_study_quests()
            elif self._quests_active:
                # Escape in the hangout stops quests, the
                # same as the Stop button: the quest stays
                # saved on the server, and the music stops.
                self.stop_quests()
            elif self.current_tab() != "Home":
                self.notebook.SetSelection(0)
            return
        if key == wx.WXK_RETURN and on_list:
            self.activate_current()
            return
        if on_list and key in (wx.WXK_LEFT, wx.WXK_RIGHT):
            step = -1 if key == wx.WXK_LEFT else 1
            page = (self.notebook.GetSelection() + step) % len(self.TAB_NAMES)
            self.notebook.SetSelection(page)
            return
        if on_list and self.current_tab() == "Combat":
            if key == ord("f"):
                self.do_fight()
                return
            if key == ord("F"):
                self.toggle_idle()
                return
        if on_list and self.current_tab() == "Shop":
            if key == ord("u"):
                self.do_upgrade("weapon")
                return
            if key == ord("a"):
                self.do_upgrade("armor")
                return
            if key == ord("h"):
                self.do_upgrade("healing")
                return
            if key == ord("U"):
                self.do_max_upgrade("weapon")
                return
            if key == ord("A"):
                self.do_max_upgrade("armor")
                return
            if key == ord("H"):
                self.do_max_upgrade("healing")
                return
        if on_list and self.current_tab() == "More" and key == ord("r"):
            fighter = self.fighter
            if game_logic.is_repairing(fighter):
                self.announce(
                    "I'm repairing. I'll be done in %s."
                    % game_logic.format_time(
                        game_logic.repair_left_seconds(fighter)
                    )
                )
            else:
                self.announce("No repairs running. I'm ready.")
            return
        if on_list and self.current_tab() == "More":
            if key == ord("s"):
                if self._quests_active:
                    self.stop_quests()
                else:
                    self.start_quests()
                return
            if key == ord("S"):
                if self._quests_active:
                    self.stop_quests()
                else:
                    self.start_quests()
                return
            if key == ord("1") and self._quest_gift_pending:
                self.choose_quest_gift("weapon")
                return
            if key == ord("2") and self._quest_gift_pending:
                self.choose_quest_gift("armor")
                return
        if on_list and self.current_tab() == "Study":
            if key in (ord("s"), ord("S")):
                if self._study_quest_active:
                    self.stop_study_quests()
                else:
                    # Quests start on their own when you enter
                    # the study (Phase 38b) — there is no Start
                    # any more. Pressing Enter study starts them.
                    self.announce(
                        "Study quests start on their own when I "
                        "enter the study.")
                return
        event.Skip()

    def on_tick(self, event):
        """Once a second: turn-by-turn narration, idle fights,
        finished upgrades, finished repairs. The 5-second idle
        gap is a minimum, not a trigger: the next idle fight
        only starts once the previous fight's narration has
        finished speaking (see _narration_busy), so one fight's
        rounds are never cut off by the next fight. While
        narration is still going, last_idle_fight is left
        alone, so the fight starts as soon as the talking ends
        instead of waiting out another full gap."""
        now = time.time()
        self._advance_narration(now)
        # Hangout quests (Phase 18): the loop runs here, once
        # a second. A quest whose time is up finishes on the
        # server and the next one starts at once; every 5
        # minutes the giver speaks a progress update. Quests
        # never need health, so repairing never stops them.
        if self._quests_active and self._quest_current:
            finish = self._quest_current.get("finish_at") or 0
            if finish and now >= finish:
                self._complete_current_quest()
            elif self._in_study:
                # In the study the 5-minute update is the study
                # update, in the player's own voice — spell,
                # quest and repairs together — not the giver's
                # hangout update.
                if (now - self._study_last_progress_at
                        >= QUEST_PROGRESS_GAP):
                    self._study_progress_update(now)
            elif (now - self._quest_last_progress_at
                    >= QUEST_PROGRESS_GAP):
                self._quest_progress_update(now)
        elif self._quests_active and not self._quest_current:
            if self._in_study:
                self._begin_next_study_quest()
            else:
                self._begin_next_quest()
        # The study (Phase 38): while learning in the study, a
        # spell whose time is up is completed on the server, and
        # the 5-minute study update speaks while learning, even
        # with no quest running.
        if self._in_study:
            study = spells.study_of(self.fighter)
            if study and not study.get("paused"):
                finish = study.get("finish_at") or 0
                if finish and now >= finish:
                    self._complete_study()
                elif (not self._quest_current
                        and now - self._study_last_progress_at
                        >= QUEST_PROGRESS_GAP):
                    self._study_progress_update(now)
        if self.idle_fighting and now - self.last_idle_fight >= IDLE_FIGHT_GAP:
            if not self._narration_busy():
                self.last_idle_fight = now
                self.do_fight(idle=True)
                if game_logic.is_repairing(self.fighter):
                    self.idle_fighting = False
                    self.announce("Idle fighting stopped while I'm repairing.")
                    # A loss that starts repairs ends the
                    # auto-fight session, so the fight music
                    # stops here too. (This was the bug Makenna
                    # reported 2026-11-18: the music kept playing
                    # after a lost fight, even though auto-fight
                    # was off and repairs were running.)
                    self._refresh_music()
                    self.refresh_all()
        if self.online_config:
            self._tick_online(now)
        else:
            done = game_logic.finish_upgrade_if_ready(self.fighter, now)
            if done:
                self.announce(done)
                self.refresh_all()
            repairing = game_logic.is_repairing(self.fighter, now)
            if self.was_repairing and not repairing:
                self.fighter["hp"] = self.fighter["max_hp"]
                self.announce("My repairs are finished. I'm back to full health.")
                self.refresh_all()
        self.was_repairing = game_logic.is_repairing(self.fighter, now)
        # The ambience loop is re-asserted once a second
        # (Phase 39b): if it was stopped, or never started,
        # it comes back within a second — in the study the
        # spell loop or the quest loop, in the hangout the
        # quest loop. Asking for the loop that is already
        # playing does not restart it, so this costs nothing
        # when it is already playing.
        self._refresh_ambience()
        self.SetStatusText(game_logic.status_text(self.fighter, now))

    def _tick_online(self, now):
        """When this computer's clock says an upgrade or repair
        is done, ask the server: the server's clock decides,
        and it finishes them. Otherwise, check in now and then
        so friends can see this player is online."""
        # A broken upgrade record (Phase 30: null level or
        # finish from the Nov 19 Healing crash) is not a
        # running upgrade: comparing now with a null finish
        # crashed the once-a-second tick, so it must never
        # count as due here.
        upgrade_due = (
            game_logic.upgrade_is_running(self.fighter)
            and now >= self.fighter["upgrade"]["finish"]
        )
        repair_due = (
            self.fighter.get("repair_until", 0) > 0
            and not game_logic.is_repairing(self.fighter, now)
        )
        if upgrade_due or repair_due:
            # Ask at most every few seconds, in case the two
            # clocks disagree a little.
            if now - self._last_timer_check < 3:
                return
            self._last_timer_check = now
            server_fighter, messages, error = online_save.refresh_state(
                self.online_config
            )
            self.last_heartbeat = now
            if error:
                self.server_problem(error)
                return
            self.use_server_fighter(server_fighter)
            for message in messages:
                self.announce(message)
            if messages:
                self.refresh_all()
            return
        if now - self.last_heartbeat >= HEARTBEAT_GAP:
            self.last_heartbeat = now
            online_save.heartbeat(self.online_config)

    def on_close(self, event):
        # Closing in the study freezes the spell's remaining
        # time on the server first, like a quest — then sign out.
        if self._in_study:
            self._pause_study()
        # Closing with a quest active freezes its remaining
        # time on the server first, so no quest time is lost
        # while the game is closed — then sign out.
        if self._quests_active and self._quest_current:
            self._pause_current_quest()
        if self.online_config:
            online_save.sign_out(self.online_config)
        self.timer.Stop()
        self._cancel_narration()
        self.sounds.stop_music()
        self.sounds.stop_ambience()
        if self.voice is not None:
            self.voice.stop()
            if self._player_ready:
                self._release_voice_file()
            self.voice.cleanup_files()
        event.Skip()


def check_for_update_at_launch(game_dir):
    """Ask GitHub whether main is newer than this copy.

    Returns a small dict: available (a newer version is
    waiting), unreachable (GitHub did not answer), folder
    (the folder holding the game), remote (the remote
    version id — a commit id in source mode, a release tag
    in exe mode), reason (why there is nothing to offer).

    Nothing here ever raises: any failure means "play the
    current version". The check is quick on purpose — see
    UPDATE_CHECK_TIMEOUT_SECONDS — and it never writes a
    local save file. The one file it may write is the
    updater's own version note, and only when the files on
    disk already match main, so a later launch can compare
    versions without asking again.
    """
    if getattr(sys, "frozen", False):
        # The exe: the game is the folder holding ArenaOfMakers.exe.
        # It has no main.py, so the source-install search below
        # would never find it; the version note, when there is
        # one, sits right here.
        folder = os.path.abspath(game_dir)
    else:
        try:
            folder = arena_of_makers_updater.find_installed_folder(game_dir)
        except Exception:
            folder = None
    if folder is None:
        # A hand-installed copy has no version note yet, so
        # the updater cannot find it — but main.py in the
        # folder itself still means the game is here. Look
        # in the folder, one level down, and the parent, the
        # same places the updater looks, and take the first
        # one holding main.py.
        normal = arena_of_makers_updater.normalise_install_folder(game_dir)
        candidates = [
            normal,
            os.path.join(normal, "Arena of Makers"),
            os.path.dirname(normal),
        ]
        seen = set()
        for candidate in candidates:
            candidate = os.path.abspath(candidate)
            if candidate in seen:
                continue
            seen.add(candidate)
            if os.path.exists(os.path.join(candidate, "main.py")):
                folder = candidate
                break
    if folder is None:
        return {"available": False, "unreachable": False,
                "folder": None, "remote": None,
                "reason": "no-install-found"}
    try:
        stored_head, _files = arena_of_makers_updater.load_state(folder)
    except Exception:
        stored_head = None
    try:
        if getattr(sys, "frozen", False):
            # The last update's swap left the exe that was running
            # then as ArenaOfMakers.old.exe. It has closed now, so
            # it can go.
            arena_of_makers_updater.remove_old_exe(folder)
            # The exe knows its own version (baked in by
            # build_exe.py). With no version note yet, write one
            # quietly, so a fresh copy is not offered the Release
            # it already is, and the standalone updater agrees.
            if not stored_head:
                baked = arena_of_makers_updater.installed_exe_version(folder)
                if baked:
                    arena_of_makers_updater.save_state(
                        folder, baked,
                        {arena_of_makers_updater.GAME_EXE_NAME})
                    stored_head = baked
            state, tag, _url = arena_of_makers_updater.release_state(
                timeout=UPDATE_CHECK_TIMEOUT_SECONDS
            )
            if state == "none":
                # GitHub answered: no Release has been made yet.
                # Nothing to offer, and nothing is wrong, so play
                # on without a message.
                return {"available": False, "unreachable": False,
                        "folder": folder, "remote": None,
                        "reason": "no-release-yet"}
            if tag is None:
                return {"available": False, "unreachable": True,
                        "folder": folder, "remote": None,
                        "reason": "github-unreachable"}
            if not stored_head:
                # No version note and no baked version (an exe
                # built before versions were baked in): offer the
                # release, and the update itself writes the note.
                return {"available": True, "unreachable": False,
                        "folder": folder, "remote": tag,
                        "reason": "no-version-note"}
            return {"available": tag != stored_head,
                    "unreachable": False, "folder": folder,
                    "remote": tag, "reason": ""}
        head = arena_of_makers_updater.get_head_sha(
            timeout=UPDATE_CHECK_TIMEOUT_SECONDS
        )
        if head is None:
            return {"available": False, "unreachable": True,
                    "folder": folder, "remote": None,
                    "reason": "github-unreachable"}
        if stored_head:
            return {"available": stored_head != head,
                    "unreachable": False, "folder": folder,
                    "remote": head, "reason": ""}
        # No version note (a hand-installed copy, like the
        # nested-folder installs): compare the files
        # themselves. If they already match main, write the
        # note quietly and play on; if they differ, offer
        # the update, and the update writes the note.
        tree = arena_of_makers_updater.get_tree(
            timeout=UPDATE_CHECK_TIMEOUT_SECONDS
        )
        if tree is None:
            return {"available": False, "unreachable": True,
                    "folder": folder, "remote": None,
                    "reason": "github-unreachable"}
        to_download, _left, synced = arena_of_makers_updater.plan_sync(
            tree, folder, include_updater=True
        )
        if not to_download:
            arena_of_makers_updater.save_state(folder, head, synced)
            return {"available": False, "unreachable": False,
                    "folder": folder, "remote": head, "reason": ""}
        return {"available": True, "unreachable": False,
                "folder": folder, "remote": head,
                "reason": "no-version-note"}
    except Exception:
        logging.exception("Launch: update check failed.")
        return {"available": False, "unreachable": True,
                "folder": folder, "remote": None,
                "reason": "github-unreachable"}


def maybe_update_at_launch(game_dir):
    """Offer a newer version at launch, if there is one.

    Returns True when the game should stop after an update,
    so the player restarts into the new version. Returns
    False when the game should carry on and play: no update
    waiting, GitHub unreachable, the player said No, or the
    update did not finish. Nothing here ever updates
    without the player saying Yes first.

    Why stop instead of restarting in place: Python has
    already loaded the old .py files, so the new files only
    take effect after a restart. The check runs before any
    sound file is loaded, so replacing files on disk is
    safe — nothing the game is using is open — but
    restarting from inside the game on Windows is fragile
    (the .bat, the frozen exe), so the game says so in
    plain words and closes instead.
    """
    update = check_for_update_at_launch(game_dir)
    if update["unreachable"]:
        logging.info("Launch: could not reach GitHub to check for updates.")
        wx.MessageBox(
            "Could not check for updates just now. "
            "Playing the current version.",
            APP_TITLE,
            wx.OK | wx.ICON_INFORMATION,
        )
        return False
    if not update["available"]:
        return False
    question = (
        "A new version of Arena of Makers is ready. "
        "Do you want to update now? If you say No, you can "
        "keep playing this version, and the game will ask "
        "again next time you open it."
    )
    dialog = _ConfirmDialog(None, question)
    answer = dialog.ShowModal()
    dialog.Destroy()
    if answer != wx.ID_YES:
        logging.info("Launch: player said No to the update.")
        return False
    lines = []
    ok = arena_of_makers_updater.sync_game(
        update["folder"], lines.append, include_updater=True
    )
    if ok:
        logging.info("Launch: updated to %s.", update["remote"])
        wx.MessageBox(
            "Update finished. Close the game and open it again "
            "to play the new version.",
            APP_TITLE,
            wx.OK | wx.ICON_INFORMATION,
        )
        return True
    logging.warning(
        "Launch: update did not finish: %s",
        lines[-1] if lines else "no detail",
    )
    wx.MessageBox(
        "The update did not finish. You can keep playing this "
        "version, or close the game and run the updater to try again.",
        APP_TITLE,
        wx.OK | wx.ICON_INFORMATION,
    )
    return False


def run_game():
    app = wx.App()
    # Launch gate: online-only. No .env, no key in the right
    # shape, no game. The message says what is missing, in
    # plain words, and never shows the key.
    config, error = supabase_config.check_online_config()
    if error:
        logging.error("Launch: online check failed.")
        wx.MessageBox(
            error,
            "Arena of Makers - online check",
            wx.OK | wx.ICON_INFORMATION,
        )
        return

    # Update check (Phase 19): quietly ask GitHub whether
    # main is newer than this copy, before signing in. If
    # the player says Yes and the update works, the game
    # stops here so a restart plays the new version.
    # Anything else — no update, no answer from GitHub,
    # No, or a failed update — just plays the current
    # version. The standalone updater stays as the backup
    # if this ever fails to connect or take the new version.
    if maybe_update_at_launch(GAME_DIR):
        return

    # Sign in: the player types their username,
    # player code and password. When nobody has that code yet,
    # the same details make a new account, after the password
    # is typed once more. The server makes the level 1 fighter
    # with the account. There is no local account file and no
    # local save file to fall back to.
    #
    # The password is only ever held in a local variable here,
    # sent to the server once over HTTPS, and then dropped. It
    # is never logged, saved or shown.
    # Keep me signed in: when a remember token is saved in
    # Windows Credential Manager, try it first, with no dialog.
    session = None
    keep_signed_in = False
    remembered = False
    saved_token = remember.load_token(config)
    if saved_token:
        session, error, forget = account.resume(config, saved_token)
        del saved_token
        if session is not None:
            remembered = remember.save_token(config, session["remember_token"])
        elif forget:
            remember.forget_token(config)
        else:
            wx.MessageBox(
                error or "Signing in did not work. Try again.",
                "Arena of Makers",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

    if session is None:
        dialog = CreateAccountDialog(None)
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return
        result = dialog.get_result()
        keep_signed_in = dialog.keep_signed_in()
        dialog.Destroy()
        if result is None:
            wx.MessageBox(
                "Type a username, a 4-digit player code, and a password.",
                "Arena of Makers",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        username, gender, kind, code, password = result
        session, error, no_account = account.sign_in(config, code, username, password)
        if no_account:
            problem = account.validate_password(password)
            if problem is None:
                confirm = ConfirmPasswordDialog(None, code)
                if confirm.ShowModal() != wx.ID_OK:
                    confirm.Destroy()
                    return
                again = confirm.get_result()
                confirm.Destroy()
                if again != password:
                    problem = (
                        "The two passwords were not the same, so no account "
                        "was made. Start the game again and retype them."
                    )
                del again
            if problem is None:
                session, error = account.create_account(
                    config, username, code, password, gender=gender, kind=kind
                )
            else:
                error = problem
        del password
        if session is None:
            wx.MessageBox(
                error or "Signing in did not work. Try again.",
                "Arena of Makers",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
    # The session token lives in memory only, with the URL and
    # the publishable key. It is never written to disk or logged.
    config["session"] = session["token"]
    player_account = session["account"]
    fighter = session["fighter"]
    if not fighter:
        wx.MessageBox(
            "The server did not send your fighter. Try again.",
            "Arena of Makers",
            wx.OK | wx.ICON_INFORMATION,
        )
        return
    logging.info("Signed in as player code %s.", player_account.get("player_code"))
    if keep_signed_in and not remembered:
        token, keep_error = account.remember_this_computer(config)
        if token and remember.save_token(config, token):
            remembered = True
        else:
            if token:
                account.forget_this_computer(config, token)
            logging.warning("Keep me signed in could not be turned on.")
    frame = MainFrame(fighter, online_config=config,
                      player_account=player_account, remembered=remembered)
    frame.Show()
    app.MainLoop()


def main():
    setup_logging()
    sys.excepthook = log_uncaught
    try:
        run_game()
    except Exception:
        logging.exception("The game hit a problem and had to stop.")
        tell_player_about_log()
        return
    logging.info("Arena of Makers closed.")


if __name__ == "__main__":
    main()
