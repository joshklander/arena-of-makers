"""Microsoft Edge text-to-speech for Arena of Makers.

Free, no key, no account: the edge-tts package talks to Microsoft's
Edge voice service. Two voices, so the player picks the one that fits
their fighter: male en-US-GuyNeural, female en-US-AriaNeural.

Speech never blocks the game: a background thread synthesizes each
line to a small MP3 file and hands it to the window, which plays it
on the main thread. Only the newest line is kept. If a newer message
arrives while one is still being made, the older one is dropped, so
idle fighting every 5 seconds can never pile up a backlog of old
lines for the player to sit through.

If edge-tts is not installed, or the voice service cannot be reached,
the engine reports itself unavailable and the game carries on with
text only. One plain line about why is written to the log file.
No secrets of any kind live here: the service needs no key.

One failed line never kills the voice for the whole session
(Phase 27, Makenna 2026-11-19): a voice the service no longer
carries — Microsoft retired Gus's Davis and Belle's Sara, so
their lines failed and the old engine marked the whole voice
dead, silencing every later line while the music kept playing —
is remembered as dead for that voice only, and the line is
spoken once in the player's own voice instead, so the player
still hears it. A one-off network failure is retried once with
the same voice. Only a dead background thread marks the whole
engine dead. Every failure names the voice that failed, in the
log, so a dead voice can be found and replaced instead of
guessed at.

For diagnosis, the engine also logs every speak attempt to the same
log file: the line it tried to speak and the voice it used, whether
the sound file was made and how big it was, and whether the player
took it. Nothing about the voice is allowed to fail silently: a dead
background thread, a dropped line, and a failed handover to the
player all get a plain line of their own.
"""

import asyncio
import logging
import os
import queue
import tempfile
import threading

try:
    import edge_tts
except ImportError:
    edge_tts = None

MALE_VOICE = "en-US-GuyNeural"
FEMALE_VOICE = "en-US-AriaNeural"

VOICES = {"male": MALE_VOICE, "female": FEMALE_VOICE}


def voice_for_gender(gender):
    """Edge voice name for 'male' or 'female'. Anything else gets male."""
    return VOICES.get(gender, MALE_VOICE)


def _preview(text, length=40):
    """Short one-line preview of a spoken line, for the log file."""
    one_line = " ".join((text or "").split())
    if len(one_line) > length:
        return one_line[:length] + "..."
    return one_line


class EdgeVoice:
    """One background voice. Give it text, it hands back MP3 files.

    play_callback is called on the voice thread with the path of each
    finished MP3. The caller must hop to the UI thread before touching
    any window (in wxPython, wx.CallAfter does that).
    """

    def __init__(self, voice, play_callback, fail_callback=None,
                 fallback_voice=None):
        """One background voice. Give it text, it hands back MP3 files.

        play_callback is called on the voice thread with the path of
        each finished MP3. fail_callback, when given, is called on the
        voice thread when a line could not be spoken at all, even
        after a retry and a fallback voice, so the caller can stop
        waiting for it. fallback_voice, when given, is the voice a
        line is spoken in when its own voice is dead — the player's
        own voice, so a giver is still heard, just not in their own
        voice, instead of going silent.
        """
        self.voice = voice
        self._play = play_callback
        self._fail = fail_callback
        self._fallback_voice = fallback_voice
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = None
        self._dead = False
        # Voices the service no longer carries, remembered for
        # this session so they are never retried: a retired voice
        # fails the same way every time, and retrying it would
        # only delay the line that could be speaking instead.
        self._dead_voices = set()
        self._dead_voice_logged = set()
        self._made_files = []
        self._dropped_logged = False

    @property
    def available(self):
        """False when there is no voice service to speak with, or
        when the background thread itself has died. A single
        failed line never makes this False: the engine keeps
        trying the next line (Phase 27)."""
        return edge_tts is not None and not self._dead

    def start(self):
        """Start the background thread. Returns False when the voice
        is off, and writes one plain line to the log saying why."""
        if edge_tts is None:
            logging.warning(
                "Edge voice is off: the edge-tts package is not installed. "
                "Run: pip install edge-tts"
            )
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._dropped_logged = False
        try:
            self._thread = threading.Thread(
                target=self._worker, name="arena-voice", daemon=True
            )
            self._thread.start()
        except Exception as error:
            logging.warning(
                "Edge voice is off: the voice thread could not start "
                "(%s: %s). The game keeps going with text only.",
                type(error).__name__,
                error,
            )
            return False
        logging.info("Voice: engine started, voice %s.", self.voice)
        return True

    def speak(self, text):
        """Queue one line to speak. Drops any line still waiting, so
        only the newest message is ever spoken. Returns False when
        the voice is off. Every attempt is logged, and a line that is
        dropped because the voice is off is logged once, so a dead
        voice never fails silently and never floods the log either.
        A line whose voice is dead is still attempted: the worker
        speaks it in the fallback voice instead (Phase 27)."""
        text = (text or "").strip()
        if not text:
            return False
        if not self.available:
            if not self._dropped_logged:
                self._dropped_logged = True
                reason = (
                    "the edge-tts package is not installed"
                    if edge_tts is None
                    else "the voice service could not be reached"
                )
                logging.warning(
                    'Voice: not spoken, the voice is off (%s). '
                    'Line was: "%s".',
                    reason,
                    _preview(text),
                )
            return False
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            pass
        logging.info(
            'Voice: speaking "%s" with %s.', _preview(text), self.voice
        )
        return True

    def set_voice(self, voice):
        """Change the voice for lines spoken from now on."""
        self.voice = voice

    def stop(self):
        """Stop the background thread. Call when the game closes."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def cleanup_files(self):
        """Delete the MP3 files this voice made. Call after playback
        has stopped, when the game closes."""
        for path in self._made_files:
            try:
                os.unlink(path)
            except OSError:
                pass
        self._made_files = []

    def _is_unsupported_voice_error(self, error):
        """True when the voice service refused this voice itself —
        the voice is retired or unknown — rather than failing on
        a network blip. The service answers a bad voice with no
        audio at all (NoAudioReceived), or closes the connection
        (1007), so those are the signs. Anything else is treated
        as transient and retried once."""
        if type(error).__name__ == "NoAudioReceived":
            return True
        lowered = str(error).lower()
        return ("1007" in lowered
                or "invalid voice" in lowered
                or "voice not found" in lowered
                or "not supported" in lowered)

    def _synthesize_with_recovery(self, text):
        """Turn one line into an MP3 file, recovering when the
        voice fails. Returns the file path, or raises after
        every recovery has been tried.

        A voice the service no longer carries is remembered as
        dead for the session and never retried: the line is
        spoken once in the fallback voice instead, so the
        player still hears it. A one-off failure — a network
        blip — is retried once with the same voice. The caller
        is told about every failure through the log, naming the
        voice that failed, so a dead voice can be replaced
        instead of silenced."""
        voice = self.voice
        if (voice in self._dead_voices and self._fallback_voice
                and self._fallback_voice != voice):
            if voice not in self._dead_voice_logged:
                self._dead_voice_logged.add(voice)
                logging.info(
                    "Voice %s is dead, so this line is spoken "
                    "with %s instead.", voice, self._fallback_voice)
            self.voice = self._fallback_voice
            voice = self._fallback_voice
        try:
            return asyncio.run(self._synthesize(text))
        except Exception as error:
            if self._is_unsupported_voice_error(error):
                if voice not in self._dead_voices:
                    self._dead_voices.add(voice)
                    logging.warning(
                        "Voice %s is not available from the voice "
                        "service (%s: %s). It will not be tried again "
                        "this session.",
                        voice, type(error).__name__, error)
                if (self._fallback_voice
                        and self._fallback_voice != voice):
                    self.voice = self._fallback_voice
                    return asyncio.run(self._synthesize(text))
                raise
            logging.info(
                "Voice %s failed once (%s: %s); trying once more.",
                voice, type(error).__name__, error)
            return asyncio.run(self._synthesize(text))

    def _notify_failed(self):
        """Tell the window a line could not be spoken at all, so
        it can stop waiting for it. Never raises: a dead voice
        must never take the game down with it."""
        if self._fail is None:
            return
        try:
            self._fail()
        except Exception as error:
            logging.warning(
                "Voice: the failed-line notice could not be handed "
                "to the player (%s: %s).",
                type(error).__name__,
                error,
            )

    def _worker(self):
        """Make sound files for queued lines, one at a time. A thread
        that dies without a word would leave the game silent with no
        clue, so the whole loop is watched: any unexpected error is
        logged in plain words and the voice is marked dead. A single
        failed line is not a dead engine (Phase 27): the worker
        logs which voice failed, tells the window the line will
        never sound, and carries on to the next line."""
        try:
            while not self._stop.is_set():
                try:
                    text = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                # A newer line may have arrived while this one waited:
                # speak the newest and drop the rest.
                try:
                    while True:
                        text = self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    path = self._synthesize_with_recovery(text)
                except Exception as error:
                    logging.warning(
                        "Edge voice: the voice service failed for "
                        "voice %s (%s: %s). That line was not "
                        "spoken. The game keeps going with text only.",
                        self.voice,
                        type(error).__name__,
                        error,
                    )
                    self._notify_failed()
                    continue
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                self._made_files.append(path)
                logging.info(
                    'Voice: made "%s" with %s (%d bytes).',
                    _preview(text),
                    self.voice,
                    size,
                )
                try:
                    self._play(path)
                except Exception as error:
                    logging.warning(
                        "Voice: the finished line could not be handed "
                        "to the player (%s: %s).",
                        type(error).__name__,
                        error,
                    )
                    self._notify_failed()
        except Exception as error:
            logging.warning(
                "Voice thread stopped unexpectedly (%s: %s). The game "
                "keeps going with text only.",
                type(error).__name__,
                error,
            )
            self._dead = True
            self._notify_failed()
        finally:
            logging.info("Voice thread stopped.")

    async def _synthesize(self, text):
        """Turn one line into an MP3 file. Returns its path. An empty
        file is not a sound, so it counts as a failure: the half-made
        file is thrown away and the error is raised for the worker to
        log in plain words."""
        communicate = edge_tts.Communicate(text, self.voice)
        handle, path = tempfile.mkstemp(suffix=".mp3", prefix="arena-voice-")
        os.close(handle)
        try:
            await communicate.save(path)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size == 0:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise ValueError("the voice service returned an empty sound file")
        return path
