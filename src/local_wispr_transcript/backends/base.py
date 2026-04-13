from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from ..types import TranscriptUpdate


UpdateCallback = Callable[[TranscriptUpdate], None]


class StreamingSession(ABC):
    backend_name: str

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def feed_audio(self, chunk: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def finish(self, audio_path: Path) -> str:
        raise NotImplementedError


class BatchFallbackBackend(ABC):
    backend_name: str

    @abstractmethod
    def transcribe_file(self, audio_path: Path) -> str:
        raise NotImplementedError

