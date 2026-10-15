"""PDF via Ghostscript.

- QUALITY: perfil /prepress (300 DPI, qualidade alta — visualmente idêntico)
- MAX:     perfil /screen (72 DPI, máxima redução)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, unique_path,
)
from compressor.utils import (
    CancelledError, CompressionError, Skip, cancel_requested,
    terminate_process, verify_pdf, which,
)

SETTINGS = {
    Preset.QUALITY: ("/prepress", "300 DPI (perfil prepress, visualmente idêntico)"),
    Preset.MAX: ("/screen", "72 DPI (perfil tela, máxima redução)"),
}
PAGE_RE = re.compile(r"Page\s+(\d+)")


def _total_pages(src: Path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(src)).pages)
    except Exception:  # noqa: BLE001 — contagem é opcional
        return None


def plan(info, preset: Preset) -> str:
    if not which("gs"):
        raise Skip("Ghostscript não encontrado — instale com: brew install ghostscript")
    setting, desc = SETTINGS[preset]
    return f"Regravar PDF com Ghostscript ({desc})"


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    if not which("gs"):
        raise Skip("Ghostscript não encontrado — instale com: brew install ghostscript")

    src = info.path
    setting, desc = SETTINGS[preset]
    total_pages = _total_pages(src)
    if not total_pages:
        # Sem conseguir ler a origem não dá para conferir a integridade da
        # saída — melhor não processar do que arriscar perder conteúdo.
        raise CompressionError(
            "Não foi possível ler o PDF de origem para conferir as páginas "
            "(arquivo possivelmente corrompido ou protegido)."
        )
    dst = unique_path(out_dir, f"{src.stem}.pdf")

    cmd = [
        "gs", "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        "-dNOPAUSE", "-dBATCH",
        f"-dPDFSETTINGS={setting}",
        "-dDetectDuplicateImages=true",
        "-dColorImageDownsampleThreshold=1.0",
        f"-sOutputFile={dst}",
        str(src),
    ]

    progress(0, f"Comprimindo 0/{total_pages}…")
    with cleanup_on_failure(dst):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as e:
            raise CompressionError(f"Não foi possível executar o Ghostscript: {e}")

        tail: list[str] = []
        cancelled = False
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    tail = (tail + [line])[-30:]
                m = PAGE_RE.search(line)
                if m:
                    page = int(m.group(1))
                    pct = min(99.0, page / total_pages * 100)
                    progress(pct, f"Comprimindo {page}/{total_pages} páginas…")
                if cancel_requested():
                    cancelled = True
                    terminate_process(proc)
                    break
            if cancelled:
                raise CancelledError()
            rc = proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()

        if rc != 0:
            errors = [ln for ln in tail
                      if any(k in ln.lower() for k in ("error", "invalid", "password", "denied", "corrupt"))]
            msg = " / ".join((errors or tail)[-3:])
            if "password" in msg.lower():
                raise Skip("PDF protegido por senha — não foi possível processar.")
            raise CompressionError(f"O Ghostscript falhou: {msg}")

        progress(99, "Verificando…")
        verify_pdf(dst)
        # Salvaguarda: o Ghostscript nunca deve mudar o nº de páginas.
        out_pages = _total_pages(dst)
        if out_pages is None or out_pages != total_pages:
            raise CompressionError(
                f"A checagem de páginas do PDF de saída falhou ({out_pages} "
                f"página(s) de {total_pages} esperada(s)) — saída descartada "
                "para não perder conteúdo."
            )

    return StrategyResult(dst, [
        f"Imagens reamostradas — {desc}",
        "Fontes e texto preservados em qualidade vetorial",
    ])
