from __future__ import annotations

import ctypes
import logging
import threading
import time

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

MODIFIER_KEYS = {
    "CTRL": 0x11,
    "ALT": 0x12,
    "SHIFT": 0x10,
    "WIN": 0x5B,
}

SPECIAL_KEYS = {
    "SPACE": 0x20,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "CAPSLOCK": 0x14,
    "BACKSPACE": 0x08,
}


def _parse_key_name(name: str) -> int:
    token = name.strip().upper()
    if token in MODIFIER_KEYS:
        return MODIFIER_KEYS[token]
    if token in SPECIAL_KEYS:
        return SPECIAL_KEYS[token]
    if token.startswith("F") and token[1:].isdigit():
        value = int(token[1:])
        if 1 <= value <= 24:
            return 0x6F + value
    if len(token) == 1 and token.isalnum():
        return ord(token)
    raise ValueError(f"Unsupported hotkey token: {name}")


def _is_key_down(vk_code: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)


class HoldHotkeyService:
    def __init__(self, hotkey: str, on_press, on_release, poll_interval: float = 0.015) -> None:
        self.hotkey = hotkey
        self.on_press = on_press
        self.on_release = on_release
        self.poll_interval = poll_interval
        self._vk_codes = [_parse_key_name(token) for token in hotkey.split("+")]
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._is_active = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._poll_loop, name="hotkey-poller", daemon=True)
        self._thread.start()
        logger.info("Hotkey service started for %s", self.hotkey)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            pressed = all(_is_key_down(vk) for vk in self._vk_codes)
            if pressed and not self._is_active:
                self._is_active = True
                self.on_press()
            elif not pressed and self._is_active:
                self._is_active = False
                self.on_release()
            time.sleep(self.poll_interval)

