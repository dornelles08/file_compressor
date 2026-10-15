"""Janela principal do File Compressor."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from compressor.detector import collect_files, detect
from compressor.engine import compress_file, default_out_dir, safe_plan
from compressor.presets import Preset
from compressor.report import Report, Status
from compressor.utils import human_size
from gui.widgets import (
    DropArea, DetailsDialog, ProgressCell, color_for,
)
from gui.worker import CompressionWorker

COLUMNS = ["ARQUIVO", "TIPO", "ORIGINAL", "PROGRESSO", "STATUS", "RESULTADO", "ECONOMIA", "TEMPO"]
WHATSAPP_TIP = ("Dica: no WhatsApp, envie o arquivo como Documento "
                "(clipe 📎) para evitar nova compressão do aplicativo.")


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("File Compressor")
        self.resize(1120, 760)
        self.setMinimumSize(920, 620)
        self.setAcceptDrops(True)

        self._preset = Preset.QUALITY
        self._out_dir: Path | None = None
        self._worker: CompressionWorker | None = None
        self._reports: dict[int, Report] = {}
        self._paths: list[Path] = []
        self._items: list[Path] = []  # all paths in order
        self._finished: set[int] = set()  # finished row indices

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QVBoxLayout()
        body.setContentsMargins(20, 18, 20, 14)
        body.setSpacing(14)

        body.addWidget(self._build_controls())

        self.stack = QStackedWidget()
        self.drop_area = DropArea()
        self.drop_area.dropped.connect(self._add_paths)
        self.drop_area.browse_requested.connect(self._browse_files)
        self.table = self._build_table()
        self.stack.addWidget(self.drop_area)
        self.stack.addWidget(self.table)
        body.addWidget(self.stack, 1)

        body.addWidget(self._build_summary())
        root.addLayout(body, 1)

        self._update_state()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(74)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("File Compressor")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Reduza o tamanho de qualquer arquivo — os originais nunca são alterados")
        subtitle.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        lay.addLayout(titles)
        lay.addStretch(1)

        badge = QLabel("ffmpeg · ghostscript · Pillow")
        badge.setObjectName("Badge")
        lay.addWidget(badge)
        return header

    def _build_controls(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(18)

        # --- preset ---
        preset_box = QVBoxLayout()
        preset_box.setSpacing(6)
        preset_title = QLabel("MODO DE COMPRESSÃO")
        preset_title.setObjectName("SectionTitle")
        preset_box.addWidget(preset_title)

        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.btn_quality = QPushButton("Visualmente sem perda")
        self.btn_quality.setObjectName("Segment")
        self.btn_quality.setProperty("class", "SegmentLeft")
        self.btn_quality.setCheckable(True)
        self.btn_quality.setChecked(True)
        self.btn_max = QPushButton("Máxima redução")
        self.btn_max.setObjectName("Segment")
        self.btn_max.setCheckable(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.btn_quality)
        group.addButton(self.btn_max)
        group.buttonClicked.connect(self._on_preset_changed)
        self.btn_quality.setStyleSheet(
            "QPushButton#Segment { border-top-left-radius: 8px; "
            "border-bottom-left-radius: 8px; }"
        )
        self.btn_max.setStyleSheet(
            "QPushButton#Segment { border-top-right-radius: 8px; "
            "border-bottom-right-radius: 8px; border-left: none; }"
        )
        seg.addWidget(self.btn_quality)
        seg.addWidget(self.btn_max)
        preset_box.addLayout(seg)
        preset_box.addWidget(self._hint(
            "Padrão: CRF 18, FLAC, recompressão lossless · Máxima: CRF 26, paletas"
        ))
        lay.addLayout(preset_box)

        # --- destino ---
        dest_box = QVBoxLayout()
        dest_box.setSpacing(6)
        dest_title = QLabel("PASTA DE SAÍDA")
        dest_title.setObjectName("SectionTitle")
        dest_box.addWidget(dest_title)
        self.btn_dest = QPushButton("compressados/ (ao lado de cada arquivo)")
        self.btn_dest.setObjectName("Ghost")
        self.btn_dest.setToolTip("Clique para escolher uma pasta de destino")
        self.btn_dest.clicked.connect(self._choose_out_dir)
        dest_box.addWidget(self.btn_dest)
        dest_box.addWidget(self._hint("Original sempre preservado · saída nunca sobrescreve"))
        lay.addLayout(dest_box)

        lay.addStretch(1)

        # --- ações ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_add = QPushButton("＋ Arquivos")
        self.btn_add.clicked.connect(self._browse_files)
        self.btn_add_folder = QPushButton("＋ Pasta")
        self.btn_add_folder.clicked.connect(self._browse_folder)
        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.clicked.connect(self._clear)
        self.btn_remove = QPushButton("Remover")
        self.btn_remove.setObjectName("Ghost")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_start = QPushButton("Comprimir")
        self.btn_start.setObjectName("Primary")
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("Danger")
        self.btn_cancel.clicked.connect(self._cancel)
        for b in (self.btn_add, self.btn_add_folder, self.btn_clear, self.btn_remove):
            b.setCursor(Qt.PointingHandCursor)
            actions.addWidget(b)
        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_cancel)
        lay.addLayout(actions)
        return card

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(COLUMNS))
        table.setHorizontalHeaderLabels(COLUMNS)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.doubleClicked.connect(self._show_details)
        table.selectionModel().selectionChanged.connect(
            lambda *_: self._update_state()
        )

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, w in ((1, 150), (2, 100), (3, 150), (4, 150), (5, 100), (6, 90), (7, 90)):
            header.setSectionResizeMode(i, QHeaderView.Fixed)
            table.setColumnWidth(i, w)
        return table

    def _build_summary(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Summary")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("RESUMO")
        title.setObjectName("SectionTitle")
        left.addWidget(title)
        self.summary_hint = self._hint(WHATSAPP_TIP)
        left.addWidget(self.summary_hint)
        lay.addLayout(left)
        lay.addStretch(1)

        self.lbl_src = QLabel("—")
        self.lbl_src.setObjectName("SummaryBig")
        arrow = QLabel("→")
        arrow.setObjectName("SummaryArrow")
        self.lbl_dst = QLabel("—")
        self.lbl_dst.setObjectName("SummaryBig")
        self.lbl_saved = QLabel("")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        self.lbl_saved.setFont(f)
        self.lbl_saved.setStyleSheet("color: #34d399;")

        for w in (self.lbl_src, arrow, self.lbl_dst):
            lay.addWidget(w)
        lay.addSpacing(6)
        lay.addWidget(self.lbl_saved)

        lay.addSpacing(16)
        self.lbl_total_time = QLabel("Tempo total: —")
        self.lbl_total_time.setObjectName("Hint")
        lay.addWidget(self.lbl_total_time)
        lay.addSpacing(8)
        self.btn_open = QPushButton("Abrir pasta")
        self.btn_open.setObjectName("Ghost")
        self.btn_open.clicked.connect(self._open_out_dir)
        lay.addWidget(self.btn_open)
        return card

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Hint")
        label.setWordWrap(True)
        return label

    # --------------------------------------------------------------- entrada
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_paths(paths)
            event.acceptProposedAction()

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Escolher arquivos")
        if files:
            self._add_paths([Path(f) for f in files])

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta")
        if folder:
            self._add_paths([Path(folder)])

    def _add_paths(self, paths: list[Path]) -> None:
        if self._worker and self._worker.isRunning():
            return
        found = collect_files([Path(p) for p in paths])
        if not found:
            QMessageBox.information(self, "Nada para adicionar",
                                    "Nenhum arquivo encontrado nos itens selecionados.")
            return

        existing = {str(p) for p in self._paths}
        for path in found:
            if str(path) in existing:
                continue
            existing.add(str(path))
            self._paths.append(path)
            self._items.append(path)

            row = self.table.rowCount()
            self.table.insertRow(row)

            name = QTableWidgetItem(path.name)
            name.setToolTip(str(path))
            self.table.setItem(row, 0, name)

            try:
                info = detect(path)
                type_text = info.type_label
                size_text = human_size(info.size)
            except OSError:
                type_text, size_text = "—", "—"
            type_item = QTableWidgetItem(type_text)
            type_item.setForeground(color_for(Status.PENDING))
            self.table.setItem(row, 1, type_item)

            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, size_item)

            self.table.setCellWidget(row, 3, ProgressCell())

            status_item = QTableWidgetItem("Na fila")
            status_item.setForeground(color_for(Status.PENDING))
            self.table.setItem(row, 4, status_item)

            for col in (5, 6, 7):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

        self.stack.setCurrentWidget(self.table)
        self._update_state()

    # ------------------------------------------------------------- execução
    def _on_preset_changed(self, button) -> None:
        self._preset = Preset.QUALITY if button is self.btn_quality else Preset.MAX
        if self._worker and self._worker.isRunning():
            return
        # Reavalia arquivos que ainda estão na fila (planos mudam entre presets)
        for row, path in enumerate(self._paths):
            if row in self._reports:
                continue
            _, plan_text, skipped = safe_plan(path, self._preset)
            item = self.table.item(row, 4)
            if item and plan_text:
                item.setText(("Ignorado" if skipped else "Na fila"))
                item.setToolTip(plan_text)
                item.setForeground(color_for(Status.SKIPPED if skipped else Status.PENDING))

    def _choose_out_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta de saída")
        if folder:
            self._out_dir = Path(folder)
            self.btn_dest.setText(f"{self._out_dir}")

    def _start(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        pending = [
            (row, path) for row, path in enumerate(self._paths)
            if row not in self._reports
        ]
        if not pending:
            QMessageBox.information(self, "Fila vazia", "Adicione arquivos para comprimir.")
            return

        for row, _ in pending:
            item = self.table.item(row, 4)
            if item:
                item.setText("Aguardando…")
                item.setForeground(color_for(Status.PENDING))
            cell = self.table.cellWidget(row, 3)
            if isinstance(cell, ProgressCell):
                cell.bar.setRange(0, 0)

        self._worker = CompressionWorker(pending, self._preset, self._out_dir, self)
        self._worker.job_progress.connect(self._on_progress)
        self._worker.job_finished.connect(self._on_finished)
        self._worker.queue_finished.connect(self._on_queue_finished)
        self._worker.start()
        self._set_running(True)

    def _cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("Cancelando…")

    def _on_progress(self, row: int, pct: object, msg: str) -> None:
        cell = self.table.cellWidget(row, 3)
        if isinstance(cell, ProgressCell):
            cell.set_pct(pct if isinstance(pct, (int, float)) else None)
        item = self.table.item(row, 4)
        if item:
            item.setText(msg)
            item.setForeground(color_for(Status.RUNNING))

    def _on_finished(self, row: int, report: Report) -> None:
        self._reports[row] = report
        self._finished.add(row)

        cell = self.table.cellWidget(row, 3)
        if isinstance(cell, ProgressCell):
            if report.status in (Status.DONE, Status.NO_GAIN, Status.SKIPPED):
                cell.finish()
            else:
                cell.bar.setRange(0, 100)
                cell.bar.setValue(0)

        status_item = self.table.item(row, 4)
        if status_item:
            status_item.setText(report.status.label)
            status_item.setForeground(color_for(report.status))
            status_item.setToolTip(report.message or report.status.label)

        result_item = self.table.item(row, 5)
        if result_item:
            result_item.setText(report.result_text)
            if report.status is Status.DONE:
                result_item.setForeground(color_for(Status.DONE))

        savings_item = self.table.item(row, 6)
        if savings_item:
            savings_item.setText(report.savings_text)
            if report.status is Status.DONE:
                savings_item.setForeground(color_for(Status.DONE))

        time_item = self.table.item(row, 7)
        if time_item:
            if report.elapsed > 0:
                if report.elapsed < 60:
                    time_item.setText(f"{report.elapsed:.1f}s")
                else:
                    m = int(report.elapsed // 60)
                    s = int(report.elapsed % 60)
                    time_item.setText(f"{m:02d}:{s:02d}")
            else:
                time_item.setText("—")

        self._update_summary()

    def _on_queue_finished(self) -> None:
        self._set_running(False)
        self._update_summary()
        self._update_state()

    def _set_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_start.setText("Comprimindo…" if running else "Comprimir")
        self.btn_cancel.setEnabled(running)
        self.btn_cancel.setText("Cancelar")
        for b in (self.btn_add, self.btn_add_folder, self.btn_clear,
                  self.btn_remove, self.btn_quality, self.btn_max, self.btn_dest):
            b.setEnabled(not running)

    # --------------------------------------------------------------- resumo
    def _update_summary(self) -> None:
        src_total = dst_total = 0
        done = 0
        total_time = 0.0
        for report in self._reports.values():
            if report.status is Status.DONE:
                src_total += report.src_size
                dst_total += report.dst_size
                done += 1
            if report.elapsed > 0:
                total_time += report.elapsed
        if done and src_total:
            self.lbl_src.setText(human_size(src_total))
            self.lbl_dst.setText(human_size(dst_total))
            pct = (1 - dst_total / src_total) * 100
            self.lbl_saved.setText(f"−{pct:.0f}%  ({human_size(src_total - dst_total)} a menos)")
            self.summary_hint.setText(WHATSAPP_TIP)
        else:
            self.lbl_src.setText("—")
            self.lbl_dst.setText("—")
            self.lbl_saved.setText("")
        if total_time > 0:
            if total_time < 60:
                self.lbl_total_time.setText(f"Tempo total: {total_time:.1f}s")
            else:
                m = int(total_time // 60)
                s = int(total_time % 60)
                self.lbl_total_time.setText(f"Tempo total: {m:02d}:{s:02d}")
        else:
            self.lbl_total_time.setText("Tempo total: —")

    def _update_state(self) -> None:
        has_files = self.table.rowCount() > 0
        self.btn_start.setEnabled(has_files and not (self._worker and self._worker.isRunning()))
        self.btn_clear.setEnabled(has_files)
        sel = self.table.selectionModel()
        self.btn_remove.setEnabled(has_files and not (self._worker and self._worker.isRunning()) and sel and sel.hasSelection())
        self.btn_open.setEnabled(any(
            r.status is Status.DONE for r in self._reports.values()
        ) or self._out_dir is not None)
        self.stack.setCurrentWidget(self.table if has_files else self.drop_area)

    def _clear(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.table.setRowCount(0)
        self._paths.clear()
        self._reports.clear()
        self._finished.clear()
        self._items.clear()
        self._update_summary()
        self._update_state()

    def _remove_selected(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        # Collect which paths to remove (pending only)
        rows = sorted((idx.row() for idx in selected), reverse=True)
        to_remove_paths = set()
        for row in rows:
            if row in self._reports:
                continue  # não afeta itens já finalizados
            if row < len(self._paths):
                to_remove_paths.add(str(self._paths[row]))
        if not to_remove_paths:
            return
        # Rebuild everything preserving finished items
        old_paths = list(self._paths)
        old_reports = dict(self._reports)
        self.table.setRowCount(0)
        self._paths.clear()
        self._reports.clear()
        self._finished.clear()
        # Rebuild in order, skipping removed pending paths
        for i, path in enumerate(old_paths):
            if i not in old_reports and str(path) in to_remove_paths:
                continue  # removed pending
            self._paths.append(path)
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(path.name)
            name.setToolTip(str(path))
            self.table.setItem(row, 0, name)
            try:
                info = detect(path)
                type_text = info.type_label
                size_text = human_size(info.size)
            except OSError:
                type_text, size_text = "—", "—"
            type_item = QTableWidgetItem(type_text)
            type_item.setForeground(color_for(Status.PENDING))
            self.table.setItem(row, 1, type_item)
            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, size_item)
            self.table.setCellWidget(row, 3, ProgressCell())
            status_item = QTableWidgetItem("Na fila")
            status_item.setForeground(color_for(Status.PENDING))
            self.table.setItem(row, 4, status_item)
            for col in (5, 6, 7):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, item)
            if i in old_reports:
                self._on_finished(row, old_reports[i])
        self._update_summary()
        self._update_state()

    def _open_out_dir(self) -> None:
        target: Path | None = self._out_dir
        if target is None:
            for report in self._reports.values():
                if report.status is Status.DONE and report.dst:
                    target = report.dst.parent
                    break
        if target is None and self._paths:
            target = default_out_dir(self._paths[0]) if self._paths else None
        if target and target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        else:
            QMessageBox.information(self, "Pasta ainda não existe",
                                    "Nada foi comprimido ainda.")

    def _show_details(self) -> None:
        row = self.table.currentRow()
        report = self._reports.get(row)
        if report is None:
            return
        DetailsDialog(report, self).exec()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self._remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(8000)
        event.accept()
