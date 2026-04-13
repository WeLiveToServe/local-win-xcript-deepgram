from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass

from ..config import OutputSettings

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = ctypes.c_bool
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p
user32.GetClipboardData.argtypes = [ctypes.c_uint]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
SW_RESTORE = 9
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


@dataclass(slots=True)
class WindowTarget:
    hwnd: int | None


class ClipboardPasteOutput:
    def __init__(self, settings: OutputSettings) -> None:
        self.settings = settings

    def release_stuck_modifiers(self) -> None:
        # Best-effort cleanup. If the process (or Windows) gets weird about key state,
        # this avoids leaving Ctrl/Alt/Shift stuck down until reboot.
        for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def emit(self, text: str, target: WindowTarget | None = None) -> None:
        original_text = self._try_get_clipboard_text() if self.settings.restore_clipboard else None

        try:
            if target and target.hwnd and self.settings.restore_focus:
                self._restore_window_focus(target.hwnd)
                time.sleep(self.settings.paste_delay_ms / 1000)

            self._set_clipboard_text(text)
            self._send_ctrl_v()
            time.sleep(0.18)
        finally:
            self.release_stuck_modifiers()
            if self.settings.restore_clipboard and original_text is not None:
                self._set_clipboard_text(original_text)

    def capture_target(self) -> WindowTarget:
        return WindowTarget(hwnd=user32.GetForegroundWindow())

    def _restore_window_focus(self, hwnd: int) -> None:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)

    def _send_ctrl_v(self) -> None:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def _try_get_clipboard_text(self) -> str | None:
        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return None
            try:
                try:
                    return ctypes.wstring_at(pointer)
                except OSError:
                    return None
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def _set_clipboard_text(self, text: str) -> None:
        data = text + "\0"
        raw_data = data.encode("utf-16-le")
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_data))
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, raw_data, len(raw_data))
        kernel32.GlobalUnlock(handle)

        user32.OpenClipboard(None)
        try:
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, handle)
            handle = None
        finally:
            user32.CloseClipboard()
            if handle:
                kernel32.GlobalFree(handle)
