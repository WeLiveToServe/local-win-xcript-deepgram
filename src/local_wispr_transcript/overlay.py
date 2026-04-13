from __future__ import annotations

import queue
import tkinter as tk

from .constants import ASSETS_DIR
from .config import OverlaySettings
from .types import TranscriptUpdate


class FloatingOverlay:
    def __init__(self, settings: OverlaySettings, hotkey: str) -> None:
        self.settings = settings
        self.hotkey = hotkey
        self._queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self._root: tk.Tk | None = None
        self._status_label: tk.Label | None = None
        self._text_label: tk.Label | None = None

    def run(self) -> None:
        self._root = tk.Tk()
        self._root.title("Local Wispr Transcript")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", self.settings.alpha)
        self._root.configure(bg="#111827")
        icon_path = ASSETS_DIR / "microphone.ico"
        if icon_path.exists():
            try:
                self._root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self._apply_geometry()

        container = tk.Frame(self._root, bg="#111827", padx=18, pady=16, highlightbackground="#334155", highlightthickness=1)
        container.pack(fill="both", expand=True)

        button_row = tk.Frame(container, bg="#111827")
        button_row.pack(fill="x")

        close_button = tk.Button(
            button_row,
            text="X",
            command=self.close,
            fg="#fca5a5",
            bg="#111827",
            activeforeground="#fecaca",
            activebackground="#1f2937",
            bd=0,
            padx=6,
            pady=0,
            font=(self.settings.font_family, 10, "bold"),
            cursor="hand2",
        )
        close_button.pack(side="right")

        self._status_label = tk.Label(
            container,
            text=f"Hold {self.hotkey} to dictate",
            fg="#93c5fd",
            bg="#111827",
            anchor="w",
            justify="left",
            font=(self.settings.font_family, self.settings.status_font_size, "bold"),
        )
        self._status_label.pack(fill="x", pady=(2, 0))

        self._text_label = tk.Label(
            container,
            text="Streaming transcript will appear here.",
            fg="#f8fafc",
            bg="#111827",
            anchor="nw",
            justify="left",
            wraplength=self.settings.width - 42,
            font=(self.settings.font_family, self.settings.font_size),
        )
        self._text_label.pack(fill="both", expand=True, pady=(12, 0))

        self._root.after(50, self._process_queue)
        self._root.mainloop()

    def show_idle(self) -> None:
        self._queue.put(
            (
                "state",
                {
                    "status": f"Hold {self.hotkey} to dictate",
                    "text": "Streaming transcript will appear here.",
                },
            )
        )

    def show_message(self, status: str, text: str = "") -> None:
        self._queue.put(("state", {"status": status, "text": text}))

    def show_update(self, update: TranscriptUpdate) -> None:
        text = update.display_text or "Listening..."
        status = update.status or "Listening..."
        self._queue.put(("state", {"status": status, "text": text}))

    def _process_queue(self) -> None:
        assert self._root is not None
        try:
            while True:
                event, payload = self._queue.get_nowait()
                if event == "state":
                    self._apply_state(payload["status"], payload["text"])
        except queue.Empty:
            pass
        self._root.after(50, self._process_queue)

    def _apply_state(self, status: str, text: str) -> None:
        if self._status_label is not None:
            self._status_label.config(text=status)
        if self._text_label is not None:
            self._text_label.config(text=text)

    def _apply_geometry(self) -> None:
        assert self._root is not None
        width = self.settings.width
        height = self.settings.height
        screen_width = self._root.winfo_screenwidth()
        x = screen_width - width - self.settings.margin_x
        y = self.settings.margin_y
        self._root.geometry(f"{width}x{height}+{x}+{y}")

    def close(self) -> None:
        if self._root is not None:
            self._root.quit()
            self._root.destroy()
