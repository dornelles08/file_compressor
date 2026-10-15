#!/usr/bin/env python3
"""Ponto de entrada da interface gráfica do File Compressor."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from gui.styles import apply_style
    from gui.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("File Compressor")
    app.setOrganizationName("file_compressor")
    apply_style(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
