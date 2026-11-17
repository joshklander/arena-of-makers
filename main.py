"""Arena of Makers - first playable skeleton.

A wxPython desktop game, built the easy way Magic Worlds is built:
one screen, five tabs, one list on each tab. Move with the arrow keys,
press Enter to choose, Escape to stop or go back. A lowercase letter
does something once; Shift plus the same letter starts the idle loop.

    F         fight one creature (Combat tab)
    Shift+F   idle fighting on and off (Combat tab)
    U         upgrade weapon (Shop tab)
    A         upgrade armor (Shop tab)
    R         hear repair status (More tab)

Run it with:  python main.py
It needs Python, wxPython, edge-tts and pygame. The save lives in arena_save.json next
to this file, on this computer only. No accounts, no passwords, no
server, and no keys of any kind in the code: the repository is public.
If the game hits a problem, the details are written to arena_log.txt
next to this file, so nobody has to open a command prompt to see what
went wrong.

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
player started playing it. Sound effects are still to come, only from
Pixabay and freesound.org, using material marked free to use.
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

import game_logic
import voice_engine

APP_TITLE = "Arena of Makers"
SAVE_PATH = game_logic.default_save_path()
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena_log.txt")

# Idle fighting does one fight about every 5 seconds.
IDLE_FIGHT_GAP = 5


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


class MainFrame(wx.Frame):
    """One window, five tabs, one list on each tab."""

    TAB_NAMES = ["Home", "Combat", "Shop", "More", "Settings"]

    TAB_HINTS = {
        "Home": "Home. Your fighter, and where to go next.",
        "Combat": "Combat. Fight one creature, or let idle fighting keep going.",
        "Shop": "Shop. Upgrade your weapon and armor. Upgrades take time, capped at 4 hours.",
        "More": "More. Hangout, repairs, and quests.",
        "Settings": "Settings. Voice, sound effects, and volume.",
    }

    def __init__(self, fighter):
        super().__init__(None, title=APP_TITLE, size=(640, 480))
        self.fighter = fighter
        self.random = random.Random()
        self.idle_fighting = False
        self.last_idle_fight = 0.0
        self.sound_on = True
        self.volume = 40
        self.was_repairing = game_logic.is_repairing(fighter)
        self.voice = None
        self._player_ready = False
        self._voice_file = None
        self._voice_play_failed = False

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

        self.refresh_all()
        self.announce("Welcome to Arena of Makers, %s." % fighter["name"])
        self.lists["Home"].SetFocus()

    # -- lists ---------------------------------------------------------

    def current_tab(self):
        return self.TAB_NAMES[self.notebook.GetSelection()]

    def list_items(self, tab):
        fighter = self.fighter
        if tab == "Home":
            return [
                "Hear my fighter status",
                "Go to Combat",
                "Go to Shop",
                "Go to More",
                "Go to Settings",
            ]
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
                    "Upgrade %s to level %d, costs %d points (press U)"
                    % (fighter["weapon_name"], fighter["weapon_level"] + 1, weapon_cost)
                )
            armor_line = (
                "Upgrade %s to level %d, costs %d points (press A)"
                % (fighter["armor_name"], fighter["armor_level"] + 1, armor_cost)
            )
            return [weapon_line, armor_line, "Hear my fighter status"]
        if tab == "More":
            return [
                "Visit the hangout",
                "Hear repair status (press R)",
                "Quests (coming soon)",
                "Hear my fighter status",
            ]
        if tab == "Settings":
            sound = "on" if self.sound_on else "off"
            gender = self.fighter.get("gender", "male")
            voice_name = "Male" if gender == "male" else "Female"
            voice_state = "" if self.voice is not None else " (voice off)"
            return [
                "Voice: %s%s (press Enter to change)" % (voice_name, voice_state),
                "Sound effects: %s" % sound,
                "Lower volume (now %d percent)" % self.volume,
                "Raise volume (now %d percent)" % self.volume,
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
            return
        self._voice_play_failed = False
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

    def announce(self, text):
        """Show it in plain words, and speak it when the voice is on."""
        self.message_line.SetLabel(text)
        if self.voice is not None:
            self.voice.speak(text)

    def log(self, lines):
        """Add fight narration to the Combat log."""
        if "Combat" in self.logs:
            self.logs["Combat"].AppendText("\n".join(lines) + "\n")

    def save(self):
        game_logic.save_game(self.fighter, SAVE_PATH)

    # -- actions -------------------------------------------------------

    def do_fight(self):
        result = game_logic.fight(self.fighter, rng=self.random)
        self.log(result["lines"])
        self.announce(result["lines"][-1])
        self.save()
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
        self.refresh_all()

    def do_upgrade(self, slot):
        error = game_logic.start_upgrade(self.fighter, slot)
        if error:
            self.announce(error)
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
        self.save()
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
        elif tab == "Combat" and item.startswith("Fight a Scrap Rat"):
            self.do_fight()
        elif tab == "Combat" and item.startswith("Idle fighting:"):
            self.toggle_idle()
        elif tab == "Shop" and item.startswith("Upgrade " + fighter["weapon_name"]):
            self.do_upgrade("weapon")
        elif tab == "Shop" and item.startswith("Upgrade " + fighter["armor_name"]):
            self.do_upgrade("armor")
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
        elif tab == "Settings" and item.startswith("Voice:"):
            gender = "female" if self.fighter.get("gender", "male") == "male" else "male"
            self.fighter["gender"] = gender
            if self.voice is not None:
                self.voice.set_voice(voice_engine.voice_for_gender(gender))
            self.save()
            self.announce("Voice set to %s." % gender)
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Sound effects:"):
            self.sound_on = not self.sound_on
            self.announce("Sound effects %s." % ("on" if self.sound_on else "off"))
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Lower volume"):
            self.volume = max(0, self.volume - 10)
            self.announce("Volume %d percent." % self.volume)
            self.refresh_all()
        elif tab == "Settings" and item.startswith("Raise volume"):
            self.volume = min(100, self.volume + 10)
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
        """Once a second: idle fights, finished upgrades, finished repairs."""
        now = time.time()
        if self.idle_fighting and now - self.last_idle_fight >= IDLE_FIGHT_GAP:
            self.last_idle_fight = now
            self.do_fight()
            if game_logic.is_repairing(self.fighter):
                self.idle_fighting = False
                self.announce("Idle fighting stopped while your fighter repairs.")
                self.refresh_all()
        done = game_logic.finish_upgrade_if_ready(self.fighter, now)
        if done:
            self.announce(done)
            self.save()
            self.refresh_all()
        repairing = game_logic.is_repairing(self.fighter, now)
        if self.was_repairing and not repairing:
            self.fighter["hp"] = self.fighter["max_hp"]
            self.announce("Repairs finished. Your fighter is back to full health.")
            self.save()
            self.refresh_all()
        self.was_repairing = repairing
        self.SetStatusText(game_logic.status_text(self.fighter, now))

    def on_close(self, event):
        self.save()
        self.timer.Stop()
        if self.voice is not None:
            self.voice.stop()
            if self._player_ready:
                self._release_voice_file()
            self.voice.cleanup_files()
        event.Skip()


def run_game():
    app = wx.App()
    fighter = game_logic.load_game(SAVE_PATH)
    if fighter is None:
        dialog = CreateFighterDialog(None)
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return
        result = dialog.get_result()
        dialog.Destroy()
        if result is None:
            wx.MessageBox(
                "Give your fighter a name first.",
                "Arena of Makers",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        kind, name, gender = result
        try:
            fighter = game_logic.new_fighter(name, kind, gender)
        except ValueError as error:
            wx.MessageBox(str(error), "Arena of Makers", wx.OK | wx.ICON_INFORMATION)
            return
        game_logic.save_game(fighter, SAVE_PATH)
    frame = MainFrame(fighter)
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
