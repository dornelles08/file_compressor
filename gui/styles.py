"""Tema escuro profissional (QSS) — paleta sóbria com acento azul."""
from __future__ import annotations

# Paleta
BG = "#0e1116"
SURFACE = "#151a21"
SURFACE_2 = "#1b212a"
BORDER = "#262d38"
BORDER_SOFT = "#1f2530"
TEXT = "#e6e9ef"
TEXT_MUTED = "#8b94a3"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#5b9bff"
ACCENT_PRESSED = "#2f6fd0"
SUCCESS = "#34d399"
WARN = "#fbbf24"
DANGER = "#f87171"
SKIP = "#7c8798"

FONT_STACK = '"SF Pro Text", "Helvetica Neue", "Segoe UI", sans-serif'


def qss() -> str:
    return f"""
    * {{
        font-family: {FONT_STACK};
        font-size: 13px;
        color: {TEXT};
    }}
    QWidget#Root {{
        background: {BG};
    }}

    /* ---------- Cabeçalho ---------- */
    QWidget#Header {{
        background: {SURFACE};
        border-bottom: 1px solid {BORDER};
    }}
    QLabel#AppTitle {{
        font-size: 19px;
        font-weight: 700;
        letter-spacing: 0.2px;
    }}
    QLabel#AppSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}
    QLabel#Badge {{
        background: rgba(59, 130, 246, 0.15);
        color: {ACCENT_HOVER};
        border: 1px solid rgba(59, 130, 246, 0.35);
        border-radius: 10px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    /* ---------- Cards ---------- */
    QFrame#Card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QLabel#SectionTitle {{
        font-size: 12px;
        font-weight: 700;
        color: {TEXT_MUTED};
        letter-spacing: 0.6px;
    }}
    QLabel#Hint {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}

    /* ---------- Botões ---------- */
    QPushButton {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: #212936;
        border-color: #33405a;
    }}
    QPushButton:pressed {{
        background: #1a212c;
    }}
    QPushButton:disabled {{
        color: #525c6b;
        background: #141920;
        border-color: {BORDER_SOFT};
    }}
    QPushButton#Primary {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
        color: #ffffff;
        font-weight: 600;
        padding: 9px 22px;
    }}
    QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton#Primary:pressed {{ background: {ACCENT_PRESSED}; }}
    QPushButton#Primary:disabled {{
        background: #22304a; border-color: #22304a; color: #6b7c96;
    }}
    QPushButton#Danger {{
        background: transparent;
        border: 1px solid rgba(248, 113, 113, 0.45);
        color: {DANGER};
    }}
    QPushButton#Danger:hover {{ background: rgba(248, 113, 113, 0.12); }}
    QPushButton#Ghost {{
        background: transparent;
        border: 1px solid {BORDER};
        color: {TEXT_MUTED};
    }}
    QPushButton#Ghost:hover {{ color: {TEXT}; border-color: #33405a; }}

    /* Segmentado (presets) */
    QPushButton#Segment {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        padding: 8px 18px;
        font-weight: 500;
        color: {TEXT_MUTED};
    }}
    QPushButton#Segment:checked {{
        background: rgba(59, 130, 246, 0.18);
        border: 1px solid {ACCENT};
        color: #dbeafe;
        font-weight: 600;
    }}
    QPushButton#SegmentLeft {{ border-top-left-radius: 8px; border-bottom-left-radius: 8px; border-top-right-radius: 0; border-bottom-right-radius: 0; }}
    QPushButton#SegmentRight {{ border-top-right-radius: 8px; border-bottom-right-radius: 8px; border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none; }}

    /* ---------- Área de arrastar ---------- */
    QFrame#DropArea {{
        background: rgba(21, 26, 33, 0.6);
        border: 1.6px dashed #33405a;
        border-radius: 12px;
    }}
    QFrame#DropArea[dragActive="true"] {{
        border-color: {ACCENT};
        background: rgba(59, 130, 246, 0.08);
    }}
    QLabel#DropTitle {{
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#DropSub {{
        color: {TEXT_MUTED};
    }}

    /* ---------- Tabela ---------- */
    QTableWidget {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: rgba(59, 130, 246, 0.18);
        selection-color: {TEXT};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px 8px;
        border-bottom: 1px solid {BORDER_SOFT};
    }}
    QTableWidget::item:selected {{
        background: rgba(59, 130, 246, 0.16);
    }}
    QHeaderView::section {{
        background: {SURFACE_2};
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 8px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}
    QHeaderView::section:first {{ border-top-left-radius: 12px; }}
    QHeaderView::section:last {{ border-top-right-radius: 12px; }}
    QTableCornerButton::section {{ background: {SURFACE_2}; border: none; }}

    /* ---------- Progresso ---------- */
    QProgressBar {{
        background: #202836;
        border: none;
        border-radius: 5px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 5px;
    }}

    /* ---------- Rodapé / resumo ---------- */
    QFrame#Summary {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QLabel#SummaryBig {{
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#SummarySaved {{
        font-size: 20px;
        font-weight: 700;
        color: {SUCCESS};
    }}
    QLabel#SummaryArrow {{
        color: {TEXT_MUTED};
        font-size: 16px;
        padding: 0 6px;
    }}

    /* ---------- Diversos ---------- */
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #313b4b; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #3d4a5e; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
    QScrollBar::handle:horizontal {{ background: #313b4b; border-radius: 5px; min-width: 30px; }}

    QToolTip {{
        background: {SURFACE_2};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px;
    }}
    QDialog {{ background: {BG}; }}
    QPlainTextEdit {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px;
        font-family: "SF Mono", "Menlo", monospace;
        font-size: 12px;
    }}
    QMessageBox {{ background: {SURFACE}; }}
    """


def apply_style(app) -> None:
    """Aplica o tema escuro e define uma fonte padrão explícita (evita avisos)."""
    from PySide6.QtGui import QFont, QFontInfo

    font = QFont("Helvetica Neue", 13)
    font.setWeight(QFont.Weight.Normal)
    info = QFontInfo(font)
    if info.family() != "Helvetica Neue":
        font = QFont("Lucida Grande", 13)
        info = QFontInfo(font)
        if info.family() != "Lucida Grande":
            font = QFont("system-ui", 13)
    app.setFont(font)
    app.setStyleSheet(qss())
