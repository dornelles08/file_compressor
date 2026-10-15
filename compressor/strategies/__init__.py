"""Registro de estratégias por categoria de arquivo."""
from __future__ import annotations

from compressor.detector import Category
from compressor.strategies import audio, generic, image, office, pdf, text, video

STRATEGIES = {
    Category.VIDEO: video,
    Category.AUDIO: audio,
    Category.IMAGE: image,
    Category.PDF: pdf,
    Category.OFFICE: office,
    Category.TEXT: text,
    Category.GENERIC: generic,
}


def get_strategy(category):
    return STRATEGIES[category]
