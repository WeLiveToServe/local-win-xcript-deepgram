from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .constants import CONFIG_PATH, DOTENV_PATH, PROJECT_ROOT


@dataclass(slots=True)
class AppSettings:
    hotkey: str = "F8"
    enable_hotkeys: bool = True
    primary_backend: str = "deepgram"
    fallback_backend: str = "whisper_cpp"
    keep_recordings: bool = False
    log_level: str = "INFO"
    paste_on_finalize: bool = True


@dataclass(slots=True)
class AudioSettings:
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "int16"
    blocksize: int = 1600


@dataclass(slots=True)
class DeepgramSettings:
    api_key: str | None = None
    model: str = "nova-3"
    language: str = "en-US"
    interim_results: bool = True
    endpointing_ms: int = 300
    utterance_end_ms: int = 1000
    punctuate: bool = True
    smart_format: bool = True
    encoding: str = "linear16"
    connect_timeout_seconds: float = 8.0
    close_timeout_seconds: float = 4.0


@dataclass(slots=True)
class WhisperCppSettings:
    binary_path: str = "tools/whispercpp/whisper-cli.exe"
    model_path: str = "models/ggml-base.en.bin"
    language: str = "en"
    threads: int = 4
    translate: bool = False
    no_speech_threshold: float = 0.72
    suppress_non_speech: bool = True

    def resolved_binary_path(self) -> Path:
        return (PROJECT_ROOT / self.binary_path).resolve()

    def resolved_model_path(self) -> Path:
        return (PROJECT_ROOT / self.model_path).resolve()


@dataclass(slots=True)
class OverlaySettings:
    width: int = 520
    height: int = 180
    margin_x: int = 28
    margin_y: int = 28
    alpha: float = 0.94
    font_family: str = "Segoe UI"
    font_size: int = 13
    status_font_size: int = 10


@dataclass(slots=True)
class OutputSettings:
    mode: str = "clipboard_paste"
    paste_delay_ms: int = 120
    restore_focus: bool = True
    restore_clipboard: bool = True


@dataclass(slots=True)
class CleanupSettings:
    normalize_whitespace: bool = True
    capitalize_first_letter: bool = True
    strip_text: bool = True


@dataclass(slots=True)
class Settings:
    app: AppSettings
    audio: AudioSettings
    deepgram: DeepgramSettings
    whisper_cpp: WhisperCppSettings
    overlay: OverlaySettings
    output: OutputSettings
    cleanup: CleanupSettings


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    return content or {}


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(DOTENV_PATH)

    file_path = config_path or CONFIG_PATH
    raw = _deep_merge(_read_yaml(CONFIG_PATH), _read_yaml(file_path)) if file_path != CONFIG_PATH else _read_yaml(CONFIG_PATH)

    deepgram = raw.get("deepgram", {})
    whisper_cpp = raw.get("whisper_cpp", {})

    import os

    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY") or deepgram.get("api_key")

    return Settings(
        app=AppSettings(**raw.get("app", {})),
        audio=AudioSettings(**raw.get("audio", {})),
        deepgram=DeepgramSettings(api_key=deepgram_api_key, **{k: v for k, v in deepgram.items() if k != "api_key"}),
        whisper_cpp=WhisperCppSettings(**whisper_cpp),
        overlay=OverlaySettings(**raw.get("overlay", {})),
        output=OutputSettings(**raw.get("output", {})),
        cleanup=CleanupSettings(**raw.get("cleanup", {})),
    )
