from __future__ import annotations

import audioop
import logging
import threading
import time
import wave
from pathlib import Path

from .audio import AudioRecorder
from .backends import DeepgramStreamingBackend, WhisperCppFallbackBackend
from .config import Settings
from .hotkeys import HoldHotkeyService
from .output import ClipboardPasteOutput
from .overlay import FloatingOverlay
from .postprocess import LightCleanupProcessor
from .types import SessionResult, TranscriptUpdate

logger = logging.getLogger(__name__)


class DictationApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.overlay = FloatingOverlay(settings.overlay, settings.app.hotkey)
        self.recorder = AudioRecorder(settings.audio)
        self.deepgram_backend = DeepgramStreamingBackend(settings.deepgram)
        self.whisper_backend = WhisperCppFallbackBackend(settings.whisper_cpp)
        self.output = ClipboardPasteOutput(settings.output)
        self.cleanup = LightCleanupProcessor(settings.cleanup)
        self.hotkey_service = (
            HoldHotkeyService(settings.app.hotkey, self._on_hotkey_press, self._on_hotkey_release)
            if settings.app.enable_hotkeys and settings.app.hotkey
            else None
        )
        self._lock = threading.RLock()
        self._active_session = None
        self._recording = False
        self._finalizing = False
        self._target_window = None

    def run(self) -> None:
        # Defensive: if a prior run crashed mid-injection, ensure modifiers aren't stuck down.
        self.output.release_stuck_modifiers()
        if self.hotkey_service is not None:
            self.hotkey_service.start()
        self.overlay.show_idle()
        try:
            self.overlay.run()
        finally:
            if self.hotkey_service is not None:
                self.hotkey_service.stop()
            self.output.release_stuck_modifiers()

    def _on_hotkey_press(self) -> None:
        with self._lock:
            if self._recording or self._finalizing:
                return

            self._recording = True
            self._target_window = self.output.capture_target()
            self._active_session = None

            if self.deepgram_backend.is_configured():
                try:
                    self._active_session = self.deepgram_backend.create_session(self._on_transcript_update)
                    self._active_session.start()
                except Exception as exc:
                    logger.exception("Deepgram session start failed")
                    self.overlay.show_message("Deepgram unavailable, using local fallback", str(exc))
                    self._active_session = None
            else:
                self.overlay.show_message("Recording locally, Deepgram not configured", "Release to run whisper.cpp fallback.")

            self.recorder.start(self._on_audio_chunk)
            if self._active_session is not None:
                self.overlay.show_message("Listening...", "Streaming transcript will appear here.")
            else:
                self.overlay.show_message("Recording locally...", "Release to transcribe with whisper.cpp fallback.")

    def _on_hotkey_release(self) -> None:
        threading.Thread(target=self._finalize_recording, name="finalize-recording", daemon=True).start()

    def _on_audio_chunk(self, chunk: bytes) -> None:
        session = self._active_session
        if session is not None:
            session.feed_audio(chunk)

    def _on_transcript_update(self, update: TranscriptUpdate) -> None:
        self.overlay.show_update(update)

    def _finalize_recording(self) -> None:
        with self._lock:
            if not self._recording or self._finalizing:
                return
            self._finalizing = True

        self.overlay.show_message("Finalizing...", "Wrapping up the transcript.")

        try:
            audio_path = self.recorder.stop()
            session_result = self._transcribe(audio_path)
            final_text = self.cleanup.clean(session_result.text)

            if final_text and self.settings.app.paste_on_finalize:
                self.output.emit(final_text, self._target_window)

            status = f"Done via {session_result.backend_name}"
            body = final_text or "No speech detected."
            self.overlay.show_message(status, body)
            time.sleep(1.3)
        except Exception as exc:  # pragma: no cover
            logger.exception("Finalize failed")
            self.overlay.show_message("Transcription failed", str(exc))
            time.sleep(2.0)
        finally:
            with self._lock:
                self._recording = False
                self._finalizing = False
                self._active_session = None
                self._target_window = None
            self.overlay.show_idle()

    def _transcribe(self, audio_path: Path) -> SessionResult:
        primary_text = ""
        primary_error = None

        if self._active_session is not None:
            try:
                primary_text = self._active_session.finish(audio_path)
            except Exception as exc:
                primary_error = str(exc)
                logger.warning("Primary backend failed: %s", exc)

        cleaned_primary = primary_text.strip()
        if cleaned_primary:
            return SessionResult(text=cleaned_primary, backend_name="deepgram", used_fallback=False, audio_path=audio_path)

        if self._looks_like_silence(audio_path):
            return SessionResult(text="", backend_name="silence-gate", used_fallback=False, audio_path=audio_path, error=primary_error)

        fallback_text = self.whisper_backend.transcribe_file(audio_path)
        return SessionResult(
            text=fallback_text,
            backend_name="whisper.cpp",
            used_fallback=True,
            audio_path=audio_path,
            error=primary_error,
        )

    def _looks_like_silence(self, audio_path: Path, rms_threshold: int = 120) -> bool:
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                if not frames:
                    return True
                rms = audioop.rms(frames, wav_file.getsampwidth())
                return rms < rms_threshold
        except Exception:
            return False
