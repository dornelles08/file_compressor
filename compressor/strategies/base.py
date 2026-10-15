"""Base compartilhada das estratégias de compressão."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from compressor.presets import Preset
from compressor.utils import ProgressFn, cancel_requested, unique_path

__all__ = ["Preset", "ProgressFn", "StrategyResult", "cleanup_on_failure",
           "unique_path", "cancel_requested"]


@dataclass
class StrategyResult:
    dst: Path
    notes: list[str] = field(default_factory=list)


@contextmanager
def cleanup_on_failure(dst: Path):
    """Remove a saída parcial se a estratégia falhar ou for cancelada."""
    try:
        yield
    except BaseException:
        if dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
        raise


def make_progress(total: int, progress: ProgressFn, stage: str):
    """Retorna um callback `cb(done_bytes)` que reporta percentual."""
    def cb(done: int) -> None:
        if cancel_requested():
            from compressor.utils import CancelledError
            raise CancelledError()
        pct = min(99.0, done / total * 100) if total else None
        progress(pct, f"{stage}… {pct:.0f}%" if pct is not None else f"{stage}…")
    return cb
