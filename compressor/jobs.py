"""Modelo de fila de trabalho (usado pela GUI e pela CLI)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from compressor.report import Report, Status


@dataclass
class Job:
    src: Path
    status: Status = Status.PENDING
    progress: float = 0.0          # 0–100
    stage: str = ""                # texto do estágio atual
    report: Report | None = None

    @property
    def name(self) -> str:
        return self.src.name
