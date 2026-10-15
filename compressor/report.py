"""Relatório de compressão de um arquivo."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from compressor.utils import human_size


class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    NO_GAIN = "no_gain"      # saída maior ou igual ao original
    SKIPPED = "skipped"      # não precisa / não suportado / já otimizado
    ERROR = "error"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return {
            Status.PENDING: "Na fila",
            Status.RUNNING: "Comprimindo…",
            Status.DONE: "Concluído",
            Status.NO_GAIN: "Sem ganho",
            Status.SKIPPED: "Ignorado",
            Status.ERROR: "Erro",
            Status.CANCELLED: "Cancelado",
        }[self]


@dataclass
class Report:
    src: Path
    status: Status
    category_label: str = ""
    dst: Path | None = None
    src_size: int = 0
    dst_size: int = 0
    preset_label: str = ""
    elapsed: float = 0.0
    message: str = ""          # mensagem de erro ou motivo de skip
    notes: list[str] = field(default_factory=list)

    @property
    def saved_bytes(self) -> int:
        return max(0, self.src_size - self.dst_size)

    @property
    def saved_pct(self) -> float:
        if self.status is not Status.DONE or self.src_size <= 0:
            return 0.0
        return (1 - self.dst_size / self.src_size) * 100

    @property
    def size_text(self) -> str:
        return human_size(self.src_size)

    @property
    def result_text(self) -> str:
        if self.status is Status.DONE and self.dst:
            return human_size(self.dst_size)
        return "—"

    @property
    def savings_text(self) -> str:
        if self.status is Status.DONE:
            return f"−{self.saved_pct:.0f}%".replace(".", ",")
        if self.status is Status.NO_GAIN:
            return "0%"
        return "—"

    @property
    def summary(self) -> str:
        """Uma linha para a UI/CLI."""
        name = self.src.name
        if self.status is Status.DONE:
            return (
                f"{name}: {human_size(self.src_size)} → {human_size(self.dst_size)} "
                f"(−{self.saved_pct:.0f}%) em {self.elapsed:.1f}s"
            )
        if self.status in (Status.SKIPPED, Status.NO_GAIN, Status.ERROR):
            return f"{name}: {self.status.label} — {self.message}"
        return f"{name}: {self.status.label}"
