"""Arena of Makers - first playable skeleton.

A wxPython desktop game, built the easy way Magic Worlds is built:
one screen, five tabs, one list on each tab. Move with the arrow keys,
press Enter to choose, Escape to stop or go back. A lowercase letter
does something once; Shift plus the same letter starts the idle loop.

    F         fight one creature (Combat tab)
    Shift+F   idle fighting on and off (Combat tab)
    U         upgrade weapon (Shop tab)
    A         upgrade armor (Shop tab)
    Shift+U   max affordable weapon upgrade (Shop tab)
    Shift+A   max affordable armor upgrade (Shop tab)
    R         hear repair status (More tab)

Stats live on the Home tab, in the same list as the fighter
status: move with the arrow keys, press Enter on a stat to
spend one banked stat point. Stay on the same stat and press
Enter again to spend another point there. No new keys, no
new tabs, no new screens.

Run it with:  python main.py
It needs Python, wxPython, edge-tts and pygame. Arena of Makers is
online-only, and the server is the only judge of a fighter: every
fight, upgrade and timer runs on the Supabase server, through the
arena_* functions in supabase_schema.sql. The game shows what the
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
import game_logic
import online_save
import remember
import sounds
import supabase_config
import voice_engine

APP_TITLE = "Arena of Makers"
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena_log.txt")

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
    """First launch: pick robot or chef, pick a voice, name the fighter."""

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
            label="Welcome to Arena of Makers. Pick your fighter, then give them a name.",
        )
        hint.Wrap(420)
        sizer.Add(hint, 0, wx.ALL, 10)

        self.kind_box = wx.RadioBox(
            self,
            label="Fighter type",
            choices=["Robot fighter", "Chef fighter"],
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
        kind = "robot" if self.kind_box.GetSelection() == 0 else "chef"
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
    robot or a chef fighter; a returning player's choices
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
            choices=["Robot fighter", "Chef fighter"],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        sizer.Add(self.kind_box, 0, wx.ALL | wx.EXPAND, 10)

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
        kind = "robot" if self.kind_box.GetSelection() == 0 else "chef"
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


class MainFrame(wx.Frame):
    """One window, five tabs, one list on each tab."""

    TAB_NAMES = ["Home", "Combat", "Shop", "More", "Settings"]

    TAB_HINTS = {
        "Home": "Home. Your fighter, and where to go next.",
        "Combat": "Combat. Fight one creature, or let idle fighting keep going.",
        "Shop": "Shop. Upgrade your weapon and armor, or buy as many levels as you can afford. Upgrades take time, capped at 4 hours.",
        "More": "More. Hangout, repairs, and quests.",
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
        self.sounds.load()
        self.sounds.set_volume(self.volume)
        if self.sound_on and self.music_on:
            self.sounds.start_music()

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
                    "You have %d stat %s to spend. Press Enter on a "
                    "stat to spend one point."
                    % (points, "point" if points == 1 else "points")
                )
            else:
                items.append("You have no stat points to spend right now.")
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
                "Go to Settings",
            ]
            return items
        if tab == "Combat":
            state = "on" if self.idle_fighting else "off"
            return [
                "Fight a Scrap Rat (press F)",
                "Idle fighting: %s (press Shift F)" % state,
                "Hear my fighter status",
            ]
        if tab == "Shop":
            weapon_cost = game_logic.upgrade_cost(fighter["weapon_level"])
            armor_cost = game_logic.upgrade_cost(fighter["armor_level"])
            upgrade = game_logic.upgrade_status(fighter)
            if upgrade:
                weapon_line = upgrade
            else:
                weapon_line = (
                    "Upgrade %s to level %d, costs %d credits (press U)"
                    % (fighter["weapon_name"], fighter["weapon_level"] + 1, weapon_cost)
                )
            armor_line = (
                "Upgrade %s to level %d, costs %d credits (press A)"
                % (fighter["armor_name"], fighter["armor_level"] + 1, armor_cost)
            )
            items = [weapon_line, armor_line]
            if not upgrade:
                # Max affordable: one line per slot, worked out
                # from the fighter the server sent back. The
                # server decides the real queue and price.
                for slot, key in (("weapon", "U"), ("armor", "A")):
                    plan = game_logic.max_affordable(fighter, slot)
                    if plan["levels"]:
                        count = len(plan["levels"])
                        items.append(
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
                    else:
                        items.append(
                            "Max affordable: your next %s level costs %d "
                            "credits and you have %d credits."
                            % (plan["name"], plan["next_cost"], plan["credits"])
                        )
            items.append("Hear my fighter status")
            return items
        if tab == "More":
            return [
                "Visit the hangout",
                "Hear repair status (press R)",
                "Quests (coming soon)",
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
        if tab == "Settings":
            sound = "on" if self.sound_on else "off"
            music = "on" if self.music_on else "off"
            gender = self.fighter.get("gender", "male")
            voice_name = "Male" if gender == "male" else "Female"
            voice_state = "" if self.voice is not None else " (voice off)"
            return [
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
        voice = voice_engine.EdgeVoice(voice_name, self._on_voice_file)
        if not voice.start():
            return None
        self._player_ready = True
        return voice

    def _on_voice_file(self, path):
        """Called on the voice thread when a line is ready to play.
        Hop to the UI thread before touching the player."""
        wx.CallAfter(self._play_voice_file, path)

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

    def announce(self, text):
        """Show it in plain words, and speak it when the voice is on.
        This is a single line: it cancels any narration in progress
        and, through voice.speak(), drops any older line still
        waiting, so it can never pile up a backlog."""
        self._cancel_narration()
        self.message_line.SetLabel(text)
        if self.voice is not None:
            self.voice.speak(text)

    def announce_sequence(self, lines, pause_seconds=TURN_PAUSE_SECONDS):
        """Speak lines one at a time, in order, with a short pause
        between them. This is how a manual fight is narrated turn
        by turn. It does not block the window: the first line is
        spoken now, and _advance_narration() (called from the
        one-second timer in on_tick) speaks each next line only
        once the mixer has finished the current one. The Combat
        text log already holds every line, so the log and the
        voice tell the same story. With no voice, only the last
        line is shown, as before."""
        lines = [line for line in (lines or []) if (line or "").strip()]
        if not lines:
            return
        if self.voice is None:
            self.message_line.SetLabel(lines[-1])
            return
        self._cancel_narration()
        self._narration_queue = list(lines)
        self._narration_pause = pause_seconds
        self._narration_next_at = 0.0
        self._speak_next_narration()

    def _speak_next_narration(self):
        """Speak the next queued narration line, and play the
        sound effect that goes with it. Only ever called when no
        line is currently sounding."""
        if not self._narration_queue or self.voice is None:
            return
        line = self._narration_queue.pop(0)
        self._play_sound_for_line(line)
        self.message_line.SetLabel(line)
        self._narration_waiting = True
        self.voice.speak(line)

    def _advance_narration(self, now):
        """Called once a second from on_tick. Speaks the next
        narration line when the current one has finished playing
        and the pause after it has passed. Does nothing while a
        line is still being made or is still sounding."""
        if not self._narration_queue:
            return
        if self._narration_waiting:
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

    def _play_sound_for_line(self, line):
        """The sound effect for one narration line, or nothing
        when sounds are off or the file is missing. Robot and
        chef fighters hear different sounds for the same hit."""
        if not self.sound_on:
            return
        kind = self.fighter.get("kind", "robot")
        if "You won!" in line:
            self.sounds.play_win()
        elif "You lost." in line:
            self.sounds.play_loss()
        elif "appears!" in line:
            self.sounds.play_intro(kind)
        elif "hits the Scrap Rat" in line:
            self.sounds.play_hit(kind)
        elif "The Scrap Rat hits" in line:
            self.sounds.play_creature_hit(kind)

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
                   fighter.get("level", 1), fighter.get("kind", ""),
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
               row.get("level") or 1, row.get("kind") or "")
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
            % (found["username"], fighter.get("level", 1), fighter.get("kind", ""))
        )
        self.do_fight(opponent_code=found["player_code"])

    # -- actions -------------------------------------------------------

    def do_fight(self, idle=False, opponent_code=None):
        """Fight one creature. A manual fight (F, or Enter on the
        fight item) is narrated turn by turn, round by round.
        An idle fight speaks only its last line -- the result --
        and plays no fight sounds, so idle fighting every 5
        seconds can never build a speech or sound backlog.

        Online, the server runs the fight with its own dice and
        sends back the lines and the new fighter; the server
        also records the fight. Only the headless tests, which
        have no server, run the fight here, and nothing they do
        is ever saved."""
        if self.online_config:
            result, error = online_save.fight(
                self.online_config, opponent_code=opponent_code
            )
            if error:
                if idle:
                    self.idle_fighting = False
                self.server_problem(error)
                self.refresh_all()
                return
            self.use_server_fighter(result.get("fighter"))
        else:
            result = game_logic.fight(self.fighter, rng=self.random)
        self.log(result["lines"])
        if idle:
            self.announce(result["lines"][-1])
        else:
            self.announce_sequence(result["lines"])
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
        if game_logic.is_repairing(self.fighter):
            self.announce(
                "Your fighter is still repairing. %s left."
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
        self._log_online(
            "idle_on" if self.idle_fighting else "idle_off"
        )
        self.refresh_all()

    def _confirm(self, text):
        """Ask yes or no with a plain-words question. Returns
        True only when the player says yes. Used before any
        spending that cannot be undone: a max-affordable queue
        and a respec."""
        yes_no = getattr(wx, "YES_NO", 0)
        question = getattr(wx, "ICON_QUESTION", 0)
        yes = getattr(wx, "ID_YES", 1)
        return wx.MessageBox(text, APP_TITLE, yes_no | question) == yes

    def do_upgrade(self, slot):
        """Start a timed upgrade. Online, the server checks the
        credits, takes the cost and sets the finish time."""
        if self.online_config:
            server_fighter, _messages, error = online_save.start_upgrade(
                self.online_config, slot
            )
            self.use_server_fighter(server_fighter)
        else:
            error = game_logic.start_upgrade(self.fighter, slot)
        if error:
            self.announce(error)
            self.refresh_all()
            return
        upgrade = self.fighter["upgrade"]
        self.announce(
            "Upgrading %s to level %d, %s left."
            % (
                upgrade["name"],
                upgrade["level"],
                game_logic.format_time(upgrade["finish"] - time.time()),
            )
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

    def do_respec(self):
        """Reset all 5 stats, refunding every spent point. The
        first respec is free; later ones cost 100 credits. A
        respec cannot be undone, so the game asks first."""
        fighter = self.fighter
        spent = sum(game_logic.stats_of(fighter).values())
        if spent <= 0:
            self.announce("You have no stat points spent to reset.")
            return
        used = fighter.get("respecs_used", 0)
        if used <= 0:
            question = (
                "Reset all your stats? You have %d stat points spent. "
                "They will all come back to spend again. Your first "
                "respec is free. Do you want to do it?" % spent
            )
        else:
            question = (
                "Reset all your stats? You have %d stat points spent. "
                "They will all come back to spend again. This respec "
                "costs 100 credits and you have %d credits. Do you "
                "want to do it?"
                % (spent, game_logic.credits_of(fighter))
            )
        if not self._confirm(question):
            self.announce("Your stats stay as they are.")
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
        credits and the 4-hour cap allow. The game says the
        whole deal in plain words and asks first, because once
        started the queue runs to the end with no cancelling."""
        fighter = self.fighter
        plan = game_logic.max_affordable(fighter, slot)
        if not plan["levels"]:
            self.announce(
                "Your next %s level costs %d credits and you have %d credits."
                % (plan["name"], plan["next_cost"], plan["credits"])
            )
            return
        count = len(plan["levels"])
        question = (
            "Your %s can go up %d %s for %d credits, leaving %d. "
            "It will take %s, one level after another. Do you want "
            "to do it?"
            % (
                plan["name"],
                count,
                "level" if count == 1 else "levels",
                plan["cost"],
                plan["credits_left"],
                game_logic.format_time(plan["seconds"]),
            )
        )
        if not self._confirm(question):
            self.announce("Nothing was bought. Your credits stay as they are.")
            return
        if self.online_config:
            server_fighter, message, _messages, error = online_save.max_upgrade(
                self.online_config, slot
            )
            self.use_server_fighter(server_fighter)
        else:
            error, message = game_logic.start_max_upgrade(self.fighter, slot)
        if error:
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
        elif tab == "Home" and item.startswith("You have "):
            points = fighter.get("stat_points", 0)
            if points > 0:
                self.announce(
                    "You have %d stat %s to spend. Move with the arrow "
                    "keys to a stat and press Enter to spend one point."
                    % (points, "point" if points == 1 else "points")
                )
            else:
                self.announce(
                    "You have no stat points to spend right now. You get "
                    "2 points every time you level up."
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
        elif tab == "Home" and item.startswith("Reset all my stats"):
            self.do_respec()
        elif tab == "Combat" and item.startswith("Fight a Scrap Rat"):
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
        elif tab == "Shop" and item.startswith("Max affordable: your next"):
            self.announce(item)
        elif tab == "Shop" and item.startswith("Upgrading "):
            self.announce(game_logic.upgrade_status(fighter) or "No upgrade is running.")
        elif tab == "More" and item == "Visit the hangout":
            self.announce(
                "You are in the hangout. Other players will join here when "
                "multiplayer arrives. For now, enjoy the quiet."
            )
        elif tab == "More" and item.startswith("Hear repair status"):
            if game_logic.is_repairing(fighter):
                self.announce(
                    "Repairing. %s left."
                    % game_logic.format_time(
                        game_logic.repair_left_seconds(fighter)
                    )
                )
            else:
                self.announce("No repairs running. Your fighter is ready.")
        elif tab == "More" and item == "Quests (coming soon)":
            self.announce("Quests are coming soon. The hangout is open meanwhile.")
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
            if self.sound_on and self.music_on:
                self.sounds.start_music()
            self.announce("Sound effects %s." % ("on" if self.sound_on else "off"))
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Background music:"):
            self.music_on = not self.music_on
            if self.music_on and self.sound_on:
                self.sounds.start_music()
            else:
                self.sounds.stop_music()
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

    # -- events --------------------------------------------------------

    def on_list_activate(self, event):
        self.activate_current()
        event.Skip()

    def on_tab_changed(self, event):
        event.Skip()
        tab = self.current_tab()
        self.refresh_list(tab)
        self.announce(self.TAB_HINTS[tab])

    def on_key(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()
        on_list = isinstance(focused, wx.ListBox)
        # Every game key press goes to the server, with the tab
        # it was pressed on. Only keys that do something in the
        # game are logged: F, Shift F, U, Shift U, A, Shift A,
        # R, Return, Escape.
        if on_list and key in (
            ord("f"), ord("F"), ord("u"), ord("U"), ord("a"), ord("A"), ord("r"),
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
                self.refresh_all()
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
            if key == ord("U"):
                self.do_max_upgrade("weapon")
                return
            if key == ord("A"):
                self.do_max_upgrade("armor")
                return
        if on_list and self.current_tab() == "More" and key == ord("r"):
            fighter = self.fighter
            if game_logic.is_repairing(fighter):
                self.announce(
                    "Repairing. %s left."
                    % game_logic.format_time(
                        game_logic.repair_left_seconds(fighter)
                    )
                )
            else:
                self.announce("No repairs running. Your fighter is ready.")
            return
        event.Skip()

    def on_tick(self, event):
        """Once a second: turn-by-turn narration, idle fights,
        finished upgrades, finished repairs."""
        now = time.time()
        self._advance_narration(now)
        if self.idle_fighting and now - self.last_idle_fight >= IDLE_FIGHT_GAP:
            self.last_idle_fight = now
            self.do_fight(idle=True)
            if game_logic.is_repairing(self.fighter):
                self.idle_fighting = False
                self.announce("Idle fighting stopped while your fighter repairs.")
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
                self.announce("Repairs finished. Your fighter is back to full health.")
                self.refresh_all()
        self.was_repairing = game_logic.is_repairing(self.fighter, now)
        self.SetStatusText(game_logic.status_text(self.fighter, now))

    def _tick_online(self, now):
        """When this computer's clock says an upgrade or repair
        is done, ask the server: the server's clock decides,
        and it finishes them. Otherwise, check in now and then
        so friends can see this player is online."""
        upgrade = self.fighter.get("upgrade")
        upgrade_due = bool(upgrade) and now >= upgrade.get("finish", 0)
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
        if self.online_config:
            online_save.sign_out(self.online_config)
        self.timer.Stop()
        self._cancel_narration()
        self.sounds.stop_music()
        if self.voice is not None:
            self.voice.stop()
            if self._player_ready:
                self._release_voice_file()
            self.voice.cleanup_files()
        event.Skip()


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
