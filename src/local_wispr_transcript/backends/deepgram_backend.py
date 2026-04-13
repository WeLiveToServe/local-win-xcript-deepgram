from __future__ import annotations

import json
import logging
import queue
import threading
import time
import urllib.parse
from pathlib import Path

import websocket

from ..config import DeepgramSettings
from ..types import TranscriptUpdate
from .base import StreamingSession, UpdateCallback

logger = logging.getLogger(__name__)


class DeepgramStreamingBackend:
    backend_name = "deepgram"

    def __init__(self, settings: DeepgramSettings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(self.settings.api_key)

    def create_session(self, on_update: UpdateCallback) -> "DeepgramStreamingSession":
        if not self.is_configured():
            raise RuntimeError("DEEPGRAM_API_KEY is not configured")
        return DeepgramStreamingSession(self.settings, on_update)


class DeepgramStreamingSession(StreamingSession):
    backend_name = "deepgram"

    def __init__(self, settings: DeepgramSettings, on_update: UpdateCallback) -> None:
        self.settings = settings
        self.on_update = on_update
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self._open_event = threading.Event()
        self._closed_event = threading.Event()
        self._error_event = threading.Event()
        self._ws_app: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._sender_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._committed_parts: list[str] = []
        self._interim_text = ""
        self._error_message: str | None = None

    def start(self) -> None:
        params = {
            "model": self.settings.model,
            "language": self.settings.language,
            "encoding": self.settings.encoding,
            "sample_rate": "16000",
            "interim_results": str(self.settings.interim_results).lower(),
            "endpointing": str(self.settings.endpointing_ms),
            "utterance_end_ms": str(self.settings.utterance_end_ms),
            "punctuate": str(self.settings.punctuate).lower(),
            "smart_format": str(self.settings.smart_format).lower(),
        }
        url = "wss://api.deepgram.com/v1/listen?" + urllib.parse.urlencode(params)

        headers = [f"Authorization: Token {self.settings.api_key}"]

        self._ws_app = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._ws_thread = threading.Thread(target=self._run_ws, name="deepgram-ws", daemon=True)
        self._sender_thread = threading.Thread(target=self._audio_sender_loop, name="deepgram-audio", daemon=True)
        self._ws_thread.start()
        self._sender_thread.start()
        self.on_update(TranscriptUpdate(status="Connecting to Deepgram...", backend_name=self.backend_name))

    def feed_audio(self, chunk: bytes) -> None:
        if self._error_event.is_set():
            return
        self._audio_queue.put(chunk)

    def finish(self, audio_path: Path) -> str:
        self._audio_queue.put(None)

        if self._sender_thread:
            self._sender_thread.join(timeout=self.settings.close_timeout_seconds + 1.0)

        self._closed_event.wait(timeout=self.settings.close_timeout_seconds)

        with self._lock:
            committed = " ".join(part for part in self._committed_parts if part).strip()
            interim = self._interim_text.strip()

        return committed if committed else interim

    @property
    def error_message(self) -> str | None:
        return self._error_message

    def _run_ws(self) -> None:
        assert self._ws_app is not None
        try:
            self._ws_app.run_forever(ping_interval=20, ping_timeout=10, skip_utf8_validation=True)
        except Exception as exc:  # pragma: no cover
            self._set_error(f"Deepgram websocket failed: {exc}")
            logger.exception("Deepgram websocket failure")
        finally:
            self._closed_event.set()

    def _audio_sender_loop(self) -> None:
        if not self._open_event.wait(timeout=self.settings.connect_timeout_seconds):
            self._set_error("Deepgram connection timed out")
            return

        assert self._ws_app is not None

        while True:
            chunk = self._audio_queue.get()
            if chunk is None:
                break
            try:
                self._ws_app.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as exc:
                self._set_error(f"Deepgram audio send failed: {exc}")
                return

        try:
            self._ws_app.send(json.dumps({"type": "Finalize"}))
            time.sleep(0.15)
            self._ws_app.send(json.dumps({"type": "CloseStream"}))
        except Exception as exc:
            self._set_error(f"Deepgram finalize failed: {exc}")

    def _on_open(self, ws) -> None:
        self._open_event.set()
        self.on_update(TranscriptUpdate(status="Listening...", backend_name=self.backend_name))

    def _on_message(self, ws, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("Deepgram sent non-JSON message: %s", message)
            return

        if not isinstance(payload, dict):
            logger.debug("Deepgram sent non-dict payload: %r", payload)
            return

        channel = payload.get("channel", {})
        if not isinstance(channel, dict):
            logger.debug("Deepgram sent non-dict channel payload: %r", channel)
            return

        alternatives = channel.get("alternatives", [])
        if not isinstance(alternatives, list) or not alternatives:
            if payload.get("type") not in {"Metadata", "UtteranceEnd"}:
                logger.debug("Deepgram payload had no transcript alternatives: %r", payload)
            if payload.get("type") == "UtteranceEnd":
                self.on_update(TranscriptUpdate(status="Listening...", backend_name=self.backend_name))
            return

        first_alternative = alternatives[0]
        if not isinstance(first_alternative, dict):
            logger.debug("Deepgram sent non-dict alternative payload: %r", first_alternative)
            return

        transcript = first_alternative.get("transcript", "").strip()

        if transcript:
            with self._lock:
                if payload.get("is_final"):
                    self._committed_parts.append(transcript)
                    self._interim_text = ""
                else:
                    self._interim_text = transcript

                committed = " ".join(part for part in self._committed_parts if part).strip()
                interim = self._interim_text

            self.on_update(
                TranscriptUpdate(
                    committed_text=committed,
                    interim_text=interim,
                    status="Listening...",
                    backend_name=self.backend_name,
                )
            )

        if payload.get("from_finalize"):
            self.on_update(TranscriptUpdate(status="Finalizing...", backend_name=self.backend_name))

    def _on_error(self, ws, error) -> None:
        text = str(error)
        if "opcode=8" in text and "\\x03\\xe8" in text:
            logger.info("Deepgram closed the websocket normally")
            return
        self._set_error(f"Deepgram error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        self._closed_event.set()

    def _set_error(self, message: str) -> None:
        if self._error_event.is_set():
            return
        self._error_event.set()
        self._error_message = message
        self.on_update(
            TranscriptUpdate(
                status="Deepgram unavailable, fallback on finalize",
                backend_name=self.backend_name,
                error=message,
            )
        )
        logger.warning(message)
