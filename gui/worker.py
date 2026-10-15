"""Worker em thread separada: processa a fila sem travar a interface."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from compressor.engine import compress_file
from compressor.presets import Preset
from compressor.report import Report, Status


class CompressionWorker(QThread):
    """Processa os jobs em sequência, emitindo progresso para a UI."""

    job_progress = Signal(int, object, str)   # linha, pct (float|None), mensagem
    job_finished = Signal(int, object)        # linha, Report
    queue_finished = Signal()

    def __init__(self, jobs: list[tuple[int, Path]], preset: Preset,
                 out_dir: Path | None, parent=None) -> None:
        super().__init__(parent)
        self._jobs = jobs
        self._preset = preset
        self._out_dir = out_dir
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        for row, src in self._jobs:
            if self._cancel.is_set():
                self.job_finished.emit(
                    row,
                    Report(src=src, status=Status.CANCELLED,
                           message="Cancelado pelo usuário."),
                )
                continue

            def progress(pct, msg, _row=row):
                self.job_progress.emit(_row, pct, msg)

            report = compress_file(
                src, self._preset, out_dir=self._out_dir,
                progress=progress, cancel_event=self._cancel,
            )
            self.job_finished.emit(row, report)

        self.queue_finished.emit()
