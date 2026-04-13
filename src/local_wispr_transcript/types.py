from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TranscriptUpdate:
    committed_text: str = ""
    interim_text: str = ""
    status: str = "idle"
    backend_name: str = ""
    error: str | None = None

    @property
    def display_text(self) -> str:
        text = " ".join(part for part in (self.committed_text.strip(), self.interim_text.strip()) if part).strip()
        return text


@dataclass(slots=True)
class SessionResult:
    text: str
    backend_name: str
    used_fallback: bool = False
    audio_path: Path | None = None
    error: str | None = None

