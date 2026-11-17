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


class EdgeVoice:
    """One background voice. Give it text, it hands back MP3 files.

    play_callback is called on the voice thread with the path of each
    finished MP3. The caller must hop to the UI thread before touching
    any window (in wxPython, wx.CallAfter does that).
    """

    def __init__(self, voice, play_callback):
        self.voice = voice
        self._play = play_callback
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = None
        self._dead = False
        self._made_files = []

    @property
    def available(self):
        """False when there is no voice service to speak with."""
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
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._worker, name="arena-voice", daemon=True
            )
            self._thread.start()
        return True

    def speak(self, text):
        """Queue one line to speak. Drops any line still waiting, so
        only the newest message is ever spoken. Returns False when
        the voice is off."""
        text = (text or "").strip()
        if not text or not self.available:
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

    def _worker(self):
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
                path = asyncio.run(self._synthesize(text))
            except Exception as error:
                logging.warning(
                    "Edge voice is off: could not reach the voice "
                    "service (%s). The game keeps going with text only.",
                    error,
                )
                self._dead = True
                continue
            self._made_files.append(path)
            try:
                self._play(path)
            except Exception:
                pass

    async def _synthesize(self, text):
        """Turn one line into an MP3 file. Returns its path."""
        communicate = edge_tts.Communicate(text, self.voice)
        handle, path = tempfile.mkstemp(suffix=".mp3", prefix="arena-voice-")
        os.close(handle)
        await communicate.save(path)
        return path
