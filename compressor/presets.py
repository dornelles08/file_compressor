"""Presets de qualidade."""
from __future__ import annotations

from enum import Enum


class Preset(Enum):
    QUALITY = "quality"   # Visualmente sem perda
    MAX = "max"           # Máxima redução

    @property
    def label(self) -> str:
        return {
            Preset.QUALITY: "Visualmente sem perda",
            Preset.MAX: "Máxima redução",
        }[self]

    @property
    def short(self) -> str:
        return "padrão" if self is Preset.QUALITY else "máxima redução"
