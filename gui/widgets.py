"""Widgets reutilizáveis da interface."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from compressor.detector import collect_files
from compressor.report import Report, Status
from compressor.utils import human_size

STATUS_COLORS = {
    Status.DONE: "#34d399",
    Status.NO_GAIN: "#fbbf24",
    Status.SKIPPED: "#7c8798",
    Status.ERROR: "#f87171",
    Status.CANCELLED: "#7c8798",
    Status.PENDING: "#8b94a3",
    Status.RUNNING: "#5b9bff",
}


class DropArea(QFrame):
    """Área que aceita arquivos/pastas arrastados (ou clique para escolher)."""

    dropped = Signal(list)   # lista de Path
    browse_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setMinimumHeight(220)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        icon = QLabel("⬇")
        icon.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(30)
        icon.setFont(f)
        icon.setStyleSheet("color: #3b82f6;")

        title = QLabel("Arraste arquivos ou pastas aqui")
        title.setObjectName("DropTitle")
        title.setAlignment(Qt.AlignCenter)

        sub = QLabel("Vídeo, áudio, imagem, PDF, Office, texto — qualquer arquivo")
        sub.setObjectName("DropSub")
        sub.setAlignment(Qt.AlignCenter)

        btn = QPushButton("Escolher arquivos…")
        btn.setObjectName("Primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.browse_requested)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(10)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)

    # --- drag & drop ---
    def _set_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_active(False)
        paths = [
            Path(u.toLocalFile())
            for u in event.mimeData().urls() if u.isLocalFile()
        ]
        if paths:
            self.dropped.emit(paths)
            event.acceptProposedAction()


class ProgressCell(QWidget):
    """Barra de progresso compacta usada dentro das células da tabela."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

    def set_pct(self, pct: float | None) -> None:
        if pct is None:
            self.bar.setRange(0, 0)      # indeterminado
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(max(0, min(100, pct))))

    def finish(self) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(100)


class DetailsDialog(QDialog):
    """Mostra os detalhes/notas de um arquivo processado."""

    def __init__(self, report: Report, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Detalhes — {report.src.name}")
        self.resize(640, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(self._text(report))
        layout.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        copy_btn = QPushButton("Copiar")
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(lambda: self._copy(box))
        buttons.addButton(copy_btn, QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)

    @staticmethod
    def _text(r: Report) -> str:
        lines = [
            f"Arquivo:    {r.src}",
            f"Tipo:       {r.category_label or '—'}",
            f"Preset:     {r.preset_label or '—'}",
            f"Status:     {r.status.label}",
            f"Original:   {human_size(r.src_size)}",
        ]
        if r.status is Status.DONE and r.dst:
            lines += [
                f"Resultado:  {human_size(r.dst_size)}  ({r.savings_text})",
                f"Economia:   {human_size(r.saved_bytes)}",
                f"Saída:      {r.dst}",
            ]
        lines.append(f"Tempo:      {r.elapsed:.1f}s")
        if r.message:
            lines.append(f"\nObservação: {r.message}")
        if r.notes:
            lines.append("\nDetalhes do processamento:")
            lines += [f"  · {n}" for n in r.notes]
        return "\n".join(lines)

    def _copy(self, box: QPlainTextEdit) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(box.toPlainText())


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    return label


def color_for(status: Status) -> QColor:
    return QColor(STATUS_COLORS.get(status, "#8b94a3"))
