from __future__ import annotations

import re

from ..config import CleanupSettings


class LightCleanupProcessor:
    def __init__(self, settings: CleanupSettings) -> None:
        self.settings = settings

    def clean(self, text: str) -> str:
        value = text
        if self.settings.strip_text:
            value = value.strip()
        if self.settings.normalize_whitespace:
            value = re.sub(r"\s+", " ", value)
            value = re.sub(r"\s+([,.;!?])", r"\1", value)
            value = re.sub(r"([(\[])\s+", r"\1", value)
            value = re.sub(r"\s+([)\]])", r"\1", value)
        if self.settings.capitalize_first_letter and value:
            value = value[0].upper() + value[1:]
        return value

