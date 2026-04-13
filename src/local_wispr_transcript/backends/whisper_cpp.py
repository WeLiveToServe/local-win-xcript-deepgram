from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..config import WhisperCppSettings
from .base import BatchFallbackBackend

logger = logging.getLogger(__name__)


class WhisperCppFallbackBackend(BatchFallbackBackend):
    backend_name = "whisper.cpp"

    def __init__(self, settings: WhisperCppSettings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        return self.settings.resolved_binary_path().exists() and self.settings.resolved_model_path().exists()

    def transcribe_file(self, audio_path: Path) -> str:
        binary = self.settings.resolved_binary_path()
        model = self.settings.resolved_model_path()

        if not binary.exists():
            raise RuntimeError(f"whisper.cpp binary not found: {binary}")
        if not model.exists():
            raise RuntimeError(f"whisper.cpp model not found: {model}")

        output_prefix = audio_path.with_suffix("")
        txt_path = output_prefix.with_suffix(".txt")
        if txt_path.exists():
            txt_path.unlink()

        command = [
            str(binary),
            "-m",
            str(model),
            "-f",
            str(audio_path),
            "-l",
            self.settings.language,
            "-t",
            str(self.settings.threads),
            "-nth",
            str(self.settings.no_speech_threshold),
            "-nt",
            "-np",
            "-otxt",
            "-of",
            str(output_prefix),
        ]

        if self.settings.translate:
            command.append("--translate")
        if self.settings.suppress_non_speech:
            command.append("-sns")

        logger.info("Running whisper.cpp fallback")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "whisper.cpp failed")

        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8").strip()

        return result.stdout.strip()
