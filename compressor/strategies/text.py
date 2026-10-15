"""Texto (txt, csv, log, json, código…): lossless sempre.

- QUALITY: .gz nível 9 (abre nativamente no macOS/Windows, taxa ótima)
- MAX:     .xz nível 9 (melhor taxa de compressão para texto)
"""
from __future__ import annotations

import gzip
import lzma
from pathlib import Path

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, make_progress,
    unique_path,
)
from compressor.utils import CompressionError, Skip, verify_gzip, verify_xz

CHUNK = 1024 * 1024


def plan(info, preset: Preset) -> str:
    size = info.size
    if size < 64:
        raise Skip("Arquivo pequeno demais para compensar a compressão.")
    if preset is Preset.QUALITY:
        return "GZIP nível 9 (sem perda; abre em qualquer sistema)"
    return "XZ nível 9 (sem perda, máxima taxa para texto)"


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    src = info.path
    if preset is Preset.QUALITY:
        dst = unique_path(out_dir, f"{src.name}.gz")
        note = "GZIP nível 9 — conteúdo idêntico ao original (sem perda)"
        verify = verify_gzip
    else:
        dst = unique_path(out_dir, f"{src.name}.xz")
        note = "XZ nível 9 — conteúdo idêntico ao original (sem perda)"
        verify = verify_xz

    progress(0, "Comprimindo…")
    cb = make_progress(info.size, progress, "Comprimindo")

    try:
        with cleanup_on_failure(dst), open(src, "rb") as fin, open(dst, "wb") as fout:
            if preset is Preset.QUALITY:
                # mtime=0 para saída reproduzível
                with gzip.GzipFile(filename="", mode="wb", fileobj=fout,
                                   compresslevel=9, mtime=0) as gz:
                    done = 0
                    while True:
                        chunk = fin.read(CHUNK)
                        if not chunk:
                            break
                        gz.write(chunk)
                        done += len(chunk)
                        cb(done)
            else:
                comp = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=9)
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
        verify(dst)
    except lzma.LZMAError as e:
        raise CompressionError(f"Falha ao comprimir com XZ: {e}")
    except OSError as e:
        raise CompressionError(f"Falha de arquivo: {e}")

    return StrategyResult(dst, [note])
