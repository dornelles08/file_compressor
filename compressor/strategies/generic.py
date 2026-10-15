"""Fallback: qualquer arquivo não classificado — LZMA (.xz) lossless.

Antes de gastar tempo, faz uma estimativa por amostra; se o arquivo já é
praticamente incompressível (mídia já comprimida, binários aleatórios…),
informa "sem ganho" sem processar.
"""
from __future__ import annotations

import lzma
from pathlib import Path

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, make_progress,
    unique_path,
)
from compressor.utils import CompressionError, Skip, verify_xz

CHUNK = 1024 * 1024
SAMPLE = 8 * 1024 * 1024        # 8 MB para estimar
MIN_GAIN = 0.03                 # ganho mínimo estimado (3%) para prosseguir


def _estimate_ratio(src: Path, size: int) -> float:
    """Comprime uma amostra e devolve a taxa projetada (0–1)."""
    try:
        with open(src, "rb") as f:
            sample = f.read(min(SAMPLE, size))
        if not sample:
            return 1.0
        ratio = len(lzma.compress(sample, preset=0)) / len(sample)
        if size <= len(sample):
            return ratio
        # Amostra pequena tende a superestimar ganho em arquivos mistos:
        # aplicamos uma penalidade conservadora.
        return min(1.0, ratio * 1.15)
    except (OSError, lzma.LZMAError):
        return 1.0


def plan(info, preset: Preset) -> str:
    size = info.size
    if size < 64:
        raise Skip("Arquivo pequeno demais para compensar a compressão.")

    ratio = _estimate_ratio(info.path, size)
    gain = 1 - ratio
    if gain < MIN_GAIN:
        pct = max(0, int(gain * 100))
        raise Skip(
            f"Arquivo já muito comprimido — ganho estimado de apenas {pct}% "
            "não compensa o processamento."
        )
    level = "6 (rápido)" if preset is Preset.QUALITY else "9 (máximo)"
    pct_est = int(gain * 100)
    return (
        f"LZMA nível {level} — ganho estimado ~{pct_est}% "
        "(compressão sem perda)"
    )


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    src = info.path
    dst = unique_path(out_dir, f"{src.name}.xz")
    preset_val = 6 if preset is Preset.QUALITY else 9

    progress(0, "Comprimindo…")
    cb = make_progress(info.size, progress, "Comprimindo")

    try:
        with cleanup_on_failure(dst), open(src, "rb") as fin, open(dst, "wb") as fout:
            comp = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=preset_val)
            done = 0
            while True:
                chunk = fin.read(CHUNK)
                if not chunk:
                    break
                out = comp.compress(chunk)
                if out:
                    fout.write(out)
                done += len(chunk)
                cb(done)
            fout.write(comp.flush())
            cb(info.size)
        verify_xz(dst)
    except lzma.LZMAError as e:
        raise CompressionError(f"Falha ao comprimir com XZ: {e}")
    except OSError as e:
        raise CompressionError(f"Falha de arquivo: {e}")

    return StrategyResult(dst, [
        f"XZ nível {preset_val} — conteúdo idêntico ao original (sem perda)"
    ])
