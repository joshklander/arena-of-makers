"""Royalty-free sound effects and background music for Arena of Makers.

All sounds come from the picks in SOUNDS.md: Freesound sounds under
CC0 (public domain, no attribution required, but credited there anyway)
and Pixabay audio under the Pixabay Content License (free to use, no
attribution required). No sound file is bundled here yet: download the
files listed in SOUNDS.md into the sounds/ folder next to this file,
using the filenames in SOUND_FILES. The game runs fine with no sound
files at all -- every missing file is logged once in plain words and
the game carries on silently, so a player who has not downloaded the
sounds yet never hears an error and never crashes.

How it works: pygame.mixer.Sound objects play effects on their own
channels, and the background music loops on its own channel. The
voice narration keeps using pygame.mixer.music, so music and effects
never cut a spoken line off, and a spoken line never cuts the music
off. Long recordings (the chopping and sizzling files are long) are
played with a maxtime, so only the first second or two sounds.

No secrets, no network, no accounts. Sound files are local only.
"""

import logging
import os

# name -> (filename in sounds/, longest time it may play, in ms or None)
SOUND_FILES = {
    "robot_laser": ("robot_laser.wav", None),
    "robot_servo": ("robot_servo.wav", None),
    "robot_clank": ("robot_clank.wav", None),
    "chef_chop": ("chef_chop.wav", 1500),
    "chef_sizzle": ("chef_sizzle.wav", 2000),
    "pan_clang": ("pan_clang.wav", None),
    "win": ("win_jingle.wav", None),
    "loss": ("loss_sound.wav", None),
    # The music loop. An .mp3 is expected (Pixabay downloads are mp3);
    # a .wav with the same base name is accepted too.
    "music": ("music_loop.mp3", None),
}

MUSIC_VOLUME_FACTOR = 0.5  # Music plays at half the effects volume.


def default_sounds_dir():
    """The sounds/ folder next to this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "sounds")


class SoundBank:
    """Loads and plays the game's sound effects and music, if present.

    pygame is passed in (main.py already imports it) so this module
    stays importable and testable when pygame is missing: with no
    pygame, or no mixer, every play call simply returns False and
    the game carries on with text and voice only.
    """

    def __init__(self, directory=None, pygame_module=None):
        self.directory = directory or default_sounds_dir()
        self._pygame = pygame_module
        self._sounds = {}
        self._music = None
        self._music_channel = None
        self.enabled = True
        self._volume = 0.4  # effects volume, 0.0 to 1.0

    @property
    def available(self):
        """True when pygame's mixer can play sounds at all."""
        pygame = self._pygame
        return pygame is not None and getattr(pygame, "mixer", None) is not None

    @property
    def loaded_names(self):
        """Names of the sounds actually loaded, for tests and the log."""
        return sorted(self._sounds)

    def load(self):
        """Load every sound file that exists. Missing files are not
        an error: one plain log line each, and the game plays on
        without them."""
        if not self.available:
            logging.info("Sounds: off, pygame is not available.")
            return
        for name, (filename, _maxtime) in SOUND_FILES.items():
            path = os.path.join(self.directory, filename)
            if name == "music" and not os.path.exists(path):
                # Accept music_loop.wav as well as music_loop.mp3.
                alt = os.path.join(self.directory, "music_loop.wav")
                if os.path.exists(alt):
                    path = alt
            if not os.path.exists(path):
                logging.info("Sound missing, skipped: %s", filename)
                continue
            try:
                sound = self._pygame.mixer.Sound(path)
            except Exception as error:
                logging.warning(
                    "Sound could not be loaded, skipped: %s (%s: %s).",
                    filename,
                    type(error).__name__,
                    error,
                )
                continue
            try:
                sound.set_volume(self._volume)
            except Exception:
                pass
            self._sounds[name] = sound
            if name == "music":
                self._music = sound
        logging.info(
            "Sounds: loaded %d of %d: %s.",
            len(self._sounds),
            len(SOUND_FILES),
            ", ".join(self.loaded_names) or "none",
        )

    def set_volume(self, percent):
        """Volume in percent, like the game's volume setting. Music
        is always quieter than the effects, so it stays in the
        background under the voice."""
        self._volume = max(0.0, min(1.0, percent / 100.0))
        for name, sound in self._sounds.items():
            try:
                level = self._volume
                if name == "music":
                    level *= MUSIC_VOLUME_FACTOR
                sound.set_volume(level)
            except Exception:
                pass

    def set_enabled(self, enabled):
        """Turn all game sounds on or off. Turning off also stops
        the music; turning back on restarts it."""
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop_music()

    def play(self, name):
        """Play one named sound once. Returns False when sounds are
        off, the file was not loaded, or playback failed. Never
        raises: a missing sound is never a reason to stop the game."""
        if not self.enabled or not self.available:
            return False
        sound = self._sounds.get(name)
        if sound is None:
            return False
        _filename, maxtime = SOUND_FILES[name]
        try:
            if maxtime is not None:
                sound.play(maxtime=maxtime)
            else:
                sound.play()
        except TypeError:
            # A minimal mixer stand-in may not take maxtime.
            try:
                sound.play()
            except Exception:
                return False
        except Exception:
            return False
        return True

    def play_hit(self, kind):
        """The fighter's own attack sound: laser for a robot, a
        chopping sound for a chef."""
        if kind == "chef":
            return self.play("chef_chop")
        return self.play("robot_laser")

    def play_creature_hit(self, kind):
        """The Scrap Rat hitting back: metal for a robot fighter,
        a pan clang for a chef fighter."""
        if kind == "chef":
            return self.play("pan_clang")
        return self.play("robot_clank")

    def play_intro(self, kind):
        """A short sound when a creature appears: a servo whirr
        for a robot fighter, a sizzle for a chef fighter."""
        if kind == "chef":
            return self.play("chef_sizzle")
        return self.play("robot_servo")

    def play_win(self):
        return self.play("win")

    def play_loss(self):
        return self.play("loss")

    def start_music(self):
        """Start the background music loop. Returns False when
        there is no music file, sounds are off, or the mixer
        cannot play it. The music uses its own channel, so it
        never interrupts the voice narration."""
        if not self.enabled or self._music is None:
            return False
        try:
            self._music.set_volume(self._volume * MUSIC_VOLUME_FACTOR)
        except Exception:
            pass
        try:
            channel = self._pygame.mixer.Channel(2)
            channel.play(self._music, loops=-1)
            self._music_channel = channel
            return True
        except Exception:
            pass
        try:
            self._music.play(loops=-1)
            return True
        except Exception:
            return False

    def stop_music(self):
        """Stop the background music, if it is playing."""
        if self._music_channel is not None:
            try:
                self._music_channel.stop()
            except Exception:
                pass
            self._music_channel = None
        if self._music is not None:
            try:
                self._music.stop()
            except Exception:
                pass
