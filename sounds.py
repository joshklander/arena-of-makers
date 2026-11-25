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
    # Quest ambience loops (Phase 23): market murmur for
    # gathering quests, damp cloth on a floor for cleaning
    # quests. Both are MP3, like the music tracks — pygame
    # plays them fine. Until they are uploaded to sounds/
    # (Makenna uploads them through the GitHub website),
    # those quests simply play no loop.
    "ambience_gathering": ("ambience_gathering.mp3", None),
    "ambience_cleaning": ("ambience_cleaning.mp3", None),
    # NPC creature sounds (Phase 24): every creature gets its    # OWN appear sound and its OWN hit sound, different from
    # Scrap Rat and from each other, so you can tell who it is
    # by sound alone (Makenna's per-creature sound rule, Nov 18,
    # 2026). All Kenney, CC0. The two 5-second clips are
    # trimmed to their first 2 seconds when played, so an
    # appear cue never drones on. Until they are uploaded to
    # sounds/ (through the GitHub website), that creature
    # simply plays no sound — the fight carries on silently.
    "npc_zip_scout_appear": ("npc_zip_scout_appear.ogg", None),
    "npc_zip_scout_hit": ("npc_zip_scout_hit.ogg", None),
    "npc_bulkhead_appear": ("npc_bulkhead_appear.ogg", None),
    "npc_bulkhead_hit": ("npc_bulkhead_hit.ogg", None),
    "npc_mend_o_matic_appear": ("npc_mend_o_matic_appear.ogg", 2000),
    "npc_mend_o_matic_hit": ("npc_mend_o_matic_hit.ogg", None),
    "npc_ghost_drone_appear": ("npc_ghost_drone_appear.ogg", None),
    "npc_ghost_drone_hit": ("npc_ghost_drone_hit.ogg", None),
    "npc_chop_chop_appear": ("npc_chop_chop_appear.ogg", None),
    "npc_chop_chop_hit": ("npc_chop_chop_hit.ogg", None),
    "npc_grill_gus_appear": ("npc_grill_gus_appear.ogg", 2000),
    "npc_grill_gus_hit": ("npc_grill_gus_hit.ogg", None),
    "npc_baker_belle_appear": ("npc_baker_belle_appear.ogg", None),
    "npc_baker_belle_hit": ("npc_baker_belle_hit.ogg", None),
    "npc_zap_fox_appear": ("npc_zap_fox_appear.ogg", None),
    "npc_zap_fox_hit": ("npc_zap_fox_hit.ogg", None),
    "npc_ember_owl_appear": ("npc_ember_owl_appear.ogg", None),
    "npc_ember_owl_hit": ("npc_ember_owl_hit.ogg", None),
    # The 12 magical creatures (Phase 39): each keeps its own
    # appear and hit sounds from MAGICAL_CREATURES_DESIGN.md
    # (Kenney CC0, from the packs already downloaded for
    # Phase 38). Their magic is NOT a separate file — an
    # elemental's magic IS its own element's spell sound
    # (spell_<element>.ogg, already in the game, see
    # play_magic_sound), and the Rival Witch's magic is a
    # random spell sound each cast — so no npc_*_magic
    # entries for them. Only the Rival Warlock has his own
    # magic file (his curse sound, Sci-fi spaceEngineLow_002,
    # 5.00 s, so it plays only its first 2 seconds like the
    # other 5-second files). These 25 files go up via the
    # GitHub website like Phase 38's; until they are there a
    # creature with a missing file simply plays no sound.
    "npc_ember_sprite_appear": ("npc_ember_sprite_appear.ogg", 2000),
    "npc_ember_sprite_hit": ("npc_ember_sprite_hit.ogg", None),
    "npc_tide_wisp_appear": ("npc_tide_wisp_appear.ogg", 2000),
    "npc_tide_wisp_hit": ("npc_tide_wisp_hit.ogg", None),
    "npc_frost_faerie_appear": ("npc_frost_faerie_appear.ogg", None),
    "npc_frost_faerie_hit": ("npc_frost_faerie_hit.ogg", None),
    "npc_gale_sylph_appear": ("npc_gale_sylph_appear.ogg", 2000),
    "npc_gale_sylph_hit": ("npc_gale_sylph_hit.ogg", None),
    "npc_bog_toad_appear": ("npc_bog_toad_appear.ogg", None),
    "npc_bog_toad_hit": ("npc_bog_toad_hit.ogg", None),
    "npc_dawn_moth_appear": ("npc_dawn_moth_appear.ogg", None),
    "npc_dawn_moth_hit": ("npc_dawn_moth_hit.ogg", None),
    "npc_shade_stalker_appear": ("npc_shade_stalker_appear.ogg", 2000),
    "npc_shade_stalker_hit": ("npc_shade_stalker_hit.ogg", None),
    "npc_void_imp_appear": ("npc_void_imp_appear.ogg", None),
    "npc_void_imp_hit": ("npc_void_imp_hit.ogg", None),
    "npc_pebble_golem_appear": ("npc_pebble_golem_appear.ogg", None),
    "npc_pebble_golem_hit": ("npc_pebble_golem_hit.ogg", None),
    "npc_storm_roc_appear": ("npc_storm_roc_appear.ogg", None),
    "npc_storm_roc_hit": ("npc_storm_roc_hit.ogg", None),
    "npc_rival_witch_appear": ("npc_rival_witch_appear.ogg", None),
    "npc_rival_witch_hit": ("npc_rival_witch_hit.ogg", None),
    "npc_rival_warlock_appear": ("npc_rival_warlock_appear.ogg", None),
    "npc_rival_warlock_hit": ("npc_rival_warlock_hit.ogg", None),
    "npc_rival_warlock_magic": ("npc_rival_warlock_magic.ogg", 2000),
    # Witch sounds (Phase 38): one cast sound per element, the
    # wand's own swish for melee hits, the study music track,
    # and the three new quest ambience loops (brewing, storm,
    # moonlight). All Kenney CC0 except the study music
    # (Kevin MacLeod, CC-BY 4.0 — credit in SOUNDS.md) and
    # the three ambience loops (Eric Matyas, soundimage.org —
    # free with attribution, credit in SOUNDS.md). The two
    # trimmed files (fire 5.0s -> 1.5s, poison 4.7s -> 1.2s)
    # were cut with ffmpeg from the CC0 originals; trimming
    # a CC0 file needs no permission. A missing file plays
    # nothing and never stops the game, exactly like the
    # other sounds — the cast line still speaks.
    "spell_fire": ("spell_fire.ogg", None),
    "spell_water": ("spell_water.ogg", None),
    "spell_ice": ("spell_ice.ogg", None),
    "spell_wind": ("spell_wind.ogg", None),
    "spell_poison": ("spell_poison.ogg", None),
    "spell_light": ("spell_light.ogg", None),
    "spell_shadow": ("spell_shadow.ogg", None),
    "spell_dark": ("spell_dark.ogg", None),
    "spell_earth": ("spell_earth.ogg", None),
    "spell_lightning": ("spell_lightning.ogg", None),
    "wand_swish": ("wand_swish.ogg", None),
    "ambience_brewing": ("ambience_brewing.mp3", None),
    "ambience_storm": ("ambience_storm.mp3", None),
    "ambience_moonlight": ("ambience_moonlight.mp3", None),
    # Aliases (Phase 38 fix): spells.study_ambience() returns the
    # family name ("brewing" / "storm" / "moonlight") and
    # main.py:_refresh_ambience passes it straight to
    # start_ambience, so the family names must be playable too.
    # Without these the study ambience loop silently never played
    # while learning a spell. Same files as above, just extra names.
    "brewing": ("ambience_brewing.mp3", None),
    "storm": ("ambience_storm.mp3", None),
    "moonlight": ("ambience_moonlight.mp3", None),
    # The music. Three tracks, one per place: the cozy cafe track for
    # the hangout (Jazz Brunch), the sci-fi track for fights
    # (Mesmerizing Galaxy Loop), and the mystical track for the
    # study (Spellbound). "music" is the old single name and
    # stays as an alias for the hangout track, so older code and
    # tests keep working: music_loop.mp3 is the same file as
    # music_hangout.mp3.
    "music": ("music_loop.mp3", None),
    "music_hangout": ("music_hangout.mp3", None),
    "music_fight": ("music_fight.mp3", None),
    "music_study": ("music_study.mp3", None),
}

MUSIC_VOLUME_FACTOR = 0.5  # Music plays at half the effects volume.
AMBIENCE_VOLUME_FACTOR = 0.25  # Quest ambience loops play at a
# quarter of the effects volume: quieter than the music, well
# under the voice.


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
        # Music track per place: {"hangout": sound, "fight": sound}.
        self._tracks = {}
        # Which track is looping now: "hangout", "fight", or None.
        self._music_name = None
        # Quest ambience loop (Phase 23): its own channel,
        # so it never interrupts the voice or the music.
        self._ambience_channel = None
        # Which ambience sound is looping now, or None.
        self._ambience_name = None
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
            if name in ("music", "music_hangout"):
                # The named hangout file wins over the old alias,
                # because SOUND_FILES lists "music" first.
                self._tracks["hangout"] = sound
                self._music = sound
            elif name == "music_fight":
                self._tracks["fight"] = sound
            elif name == "music_study":
                self._tracks["study"] = sound
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
                if name in ("music", "music_hangout", "music_fight",
                            "music_study"):
                    level *= MUSIC_VOLUME_FACTOR
                elif name == self._ambience_name:
                    level *= AMBIENCE_VOLUME_FACTOR
                sound.set_volume(level)
            except Exception:
                pass

    def set_enabled(self, enabled):
        """Turn all game sounds on or off. Turning off also stops
        the music and the quest ambience loop."""
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop_music()
            self.stop_ambience()

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
        chopping sound for a chef, the wand's swish for a witch.
        A witch hit that follows a cast line does not play here
        at all — the cast line already played the spell's sound
        (see main.py: the spell is the hit, the wand is only
        backup)."""
        if kind == "chef":
            return self.play("chef_chop")
        if kind == "witch":
            return self.play("wand_swish")
        return self.play("robot_laser")

    def play_creature_hit(self, kind):
        """The Scrap Rat hitting back: metal for a robot fighter,
        a pan clang for a chef fighter, a dull rock thud for a
        witch fighter (the earth spell sound — a thud that fits
        any fighter, as the witch draft proposes)."""
        if kind == "chef":
            return self.play("pan_clang")
        if kind == "witch":
            return self.play("spell_earth")
        return self.play("robot_clank")

    def play_intro(self, kind):
        """A short sound when a creature appears: a servo whirr
        for a robot fighter, a sizzle for a chef fighter, a
        bright shimmer for a witch fighter (the light spell
        sound)."""
        if kind == "chef":
            return self.play("chef_sizzle")
        if kind == "witch":
            return self.play("spell_light")
        return self.play("robot_servo")

    def play_spell(self, element):
        """One elemental cast sound, by element name ("fire",
        "water", ...). Returns False for an unknown element or
        a missing file — the cast line still speaks."""
        if element not in ("fire", "water", "ice", "wind", "poison",
                           "light", "shadow", "dark", "earth",
                           "lightning"):
            return False
        return self.play("spell_" + element)

    def play_magic_sound(self, sound_key):
        """A creature's magic sound, by the sound key the fight
        carries (Phase 39): "spell_<element>" plays that
        element's cast sound — an elemental's magic IS its own
        spell sound, and the Rival Witch's magic is a random
        one — while any other key (the Rival Warlock's
        "npc_rival_warlock_magic") plays that file directly.
        Returns False for an unknown key or a missing file —
        the fight never stops for a sound."""
        if not sound_key:
            return False
        if sound_key.startswith("spell_"):
            return self.play_spell(sound_key[len("spell_"):])
        return self.play(sound_key)

    def play_win(self):
        return self.play("win")

    def play_loss(self):
        return self.play("loss")

    @property
    def current_music_track(self):
        """Which music track is looping now: "hangout", "fight",
        "study", or None when nothing is playing."""
        return self._music_name

    def start_music(self, track="hangout"):
        """Start one background music loop. track is "hangout"
        (the cafe track), "fight" (the sci-fi track) or "study"
        (the mystical track, Phase 38); with no track given it
        plays the hangout track, as before.
        Returns False when there is no music file for that
        track, sounds are off, or the mixer cannot play it.
        Asking for the track that is already playing just
        returns True, so switching tabs or starting another
        fight never restarts the loop. The music uses its own
        channel, so it never interrupts the voice narration."""
        if track not in ("hangout", "fight", "study"):
            track = "hangout"
        if not self.enabled:
            return False
        sound = self._tracks.get(track)
        if sound is None:
            return False
        if self._music_name == track and self._music_channel is not None:
            return True
        self.stop_music()
        try:
            sound.set_volume(self._volume * MUSIC_VOLUME_FACTOR)
        except Exception:
            pass
        try:
            channel = self._pygame.mixer.Channel(2)
            channel.play(sound, loops=-1)
            self._music_channel = channel
            self._music = sound
            self._music_name = track
            return True
        except Exception:
            pass
        try:
            sound.play(loops=-1)
            self._music = sound
            self._music_name = track
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
        self._music_name = None

    @property
    def current_ambience(self):
        """Which ambience loop is playing now: the sound name,
        or None when nothing is playing."""
        return self._ambience_name

    def start_ambience(self, name):
        """Start one quest ambience loop. name is a sound in
        SOUND_FILES, e.g. "chef_sizzle" for cooking quests.
        The loop runs on its own channel (3), so it never
        interrupts the voice narration (mixer.music) or the
        background music (channel 2), and it plays quieter
        than the music, well under the voice. Returns False
        when sounds are off, the file was not loaded, or
        playback failed. Asking for the loop that is already
        playing just returns True, so the next quest with
        the same kind of work never restarts the loop."""
        if not self.enabled or not self.available:
            return False
        sound = self._sounds.get(name)
        if sound is None:
            return False
        if (self._ambience_name == name
                and self._ambience_channel is not None):
            return True
        self.stop_ambience()
        try:
            sound.set_volume(self._volume * AMBIENCE_VOLUME_FACTOR)
        except Exception:
            pass
        try:
            channel = self._pygame.mixer.Channel(3)
            channel.play(sound, loops=-1)
            self._ambience_channel = channel
            self._ambience_name = name
            return True
        except Exception:
            pass
        try:
            sound.play(loops=-1)
            self._ambience_name = name
            return True
        except Exception:
            return False

    def stop_ambience(self):
        """Stop the quest ambience loop, if one is playing.
        The sound's volume is put back to the effects volume,
        so a later one-shot of the same sound (a sizzle, a
        servo) plays at full volume again."""
        if self._ambience_channel is not None:
            try:
                self._ambience_channel.stop()
            except Exception:
                pass
            self._ambience_channel = None
        if self._ambience_name is not None:
            sound = self._sounds.get(self._ambience_name)
            if sound is not None:
                try:
                    sound.stop()
                except Exception:
                    pass
                try:
                    sound.set_volume(self._volume)
                except Exception:
                    pass
            self._ambience_name = None
