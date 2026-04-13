from __future__ import annotations

import logging
import queue
import threading
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import sounddevice as sd

from ..config import AudioSettings
from ..constants import TMP_DIR

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RecorderSession:
    path: Path
    bytes_written: int = 0


class AudioRecorder:
    def __init__(self, settings: AudioSettings) -> None:
        self.settings = settings
        self._stream: sd.RawInputStream | None = None
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._writer_thread: threading.Thread | None = None
        self._callback = None
        self._wave_file = None
        self._session: RecorderSession | None = None

    def start(self, on_audio_chunk) -> RecorderSession:
        if self._stream is not None:
            raise RuntimeError("Recorder already started")

        TMP_DIR.mkdir(parents=True, exist_ok=True)
        wav_path = TMP_DIR / f"recording-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.wav"
        self._wave_file = wave.open(str(wav_path), "wb")
        self._wave_file.setnchannels(self.settings.channels)
        self._wave_file.setsampwidth(2)
        self._wave_file.setframerate(self.settings.sample_rate)
        self._session = RecorderSession(path=wav_path)
        self._callback = on_audio_chunk

        self._writer_thread = threading.Thread(target=self._fanout_loop, name="audio-fanout", daemon=True)
        self._writer_thread.start()

        def callback(indata, frames, time_info, status) -> None:
            if status:
                logger.warning("Audio stream status: %s", status)
            self._queue.put(bytes(indata))

        self._stream = sd.RawInputStream(
            samplerate=self.settings.sample_rate,
            channels=self.settings.channels,
            dtype=self.settings.dtype,
            blocksize=self.settings.blocksize,
            callback=callback,
        )
        self._stream.start()
        logger.info("Recorder started: %s", wav_path)
        return self._session

    def stop(self) -> Path:
        if self._stream is None or self._session is None:
            raise RuntimeError("Recorder not started")

        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._queue.put(None)

        if self._writer_thread:
            self._writer_thread.join(timeout=2.0)

        if self._wave_file:
            self._wave_file.close()
            self._wave_file = None

        path = self._session.path
        logger.info("Recorder stopped: %s", path)
        self._session = None
        return path

    def _fanout_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            if self._wave_file:
                self._wave_file.writeframes(item)
            if self._session:
                self._session.bytes_written += len(item)
            if self._callback:
                self._callback(item)

