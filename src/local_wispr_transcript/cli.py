from __future__ import annotations

import argparse
import platform
from pathlib import Path

from .app import DictationApp
from .config import load_settings
from .logging_setup import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows-first local dictation utility.")
    parser.add_argument("--config", help="Path to a YAML config file.")
    parser.add_argument("--check", action="store_true", help="Print a quick environment report and exit.")
    args = parser.parse_args()

    config_path = Path(args.config).resolve() if args.config else None
    settings = load_settings(config_path=config_path)
    configure_logging(settings.app.log_level)

    if args.check:
        print(build_report(settings))
        return

    app = DictationApp(settings)
    app.run()


def build_report(settings) -> str:
    lines = [
        "local-wispr-transcript environment report",
        f"Platform: {platform.platform()}",
        f"Hotkey: {settings.app.hotkey}",
        f"Deepgram configured: {'yes' if settings.deepgram.api_key else 'no'}",
        f"Whisper binary: {settings.whisper_cpp.resolved_binary_path()}",
        f"Whisper binary exists: {settings.whisper_cpp.resolved_binary_path().exists()}",
        f"Whisper model: {settings.whisper_cpp.resolved_model_path()}",
        f"Whisper model exists: {settings.whisper_cpp.resolved_model_path().exists()}",
        f"Primary backend: {settings.app.primary_backend}",
        f"Fallback backend: {settings.app.fallback_backend}",
    ]

    try:
        import sounddevice as sd

        default_input, _ = sd.default.device
        devices = sd.query_devices()
        if default_input is not None and default_input >= 0:
            lines.append(f"Default input device: {devices[default_input]['name']}")
    except Exception as exc:  # pragma: no cover
        lines.append(f"Audio device lookup failed: {exc}")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
