"""Office/epub/jar: são containers ZIP — recompressão lossless no nível 9.

Nada é removido nem alterado; apenas os dados são recomprimidos melhor.
Entradas que já são STORED (ex.: `mimetype` do EPUB, obrigatório assim)
são mantidas como estão.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, unique_path,
)
from compressor.utils import (
    CancelledError, CompressionError, Skip, cancel_requested, verify_zip,
)

# .jar/.apk contêm assinatura: recomprimir invalidaria. Não vale o risco.
SIGNED_NOTE = {
    ".jar": "JAR",
    ".apk": "APK",
    ".aar": "AAR",
}

COPY_CHUNK = 1024 * 256


def _copy_cancellable(fsrc, fdst) -> None:
    """Copia em blocos, permitindo cancelamento durante a cópia."""
    while True:
        if cancel_requested():
            raise CancelledError()
        buf = fsrc.read(COPY_CHUNK)
        if not buf:
            break
        fdst.write(buf)


def plan(info, preset: Preset) -> str:
    ext = info.path.suffix.lower()
    if ext in SIGNED_NOTE:
        raise Skip(
            f"{SIGNED_NOTE[ext]} tem assinatura digital — recomprimir "
            "invalidaria a assinatura. Arquivo mantido."
        )
    try:
        with zipfile.ZipFile(info.path) as zf:
            zf.testzip()
    except zipfile.BadZipFile:
        raise Skip("Não é um arquivo ZIP/Office válido.")
    return "Recompressão ZIP nível 9 (sem perda, nada é removido)"


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    src, ext = info.path, info.path.suffix.lower()
    if ext in SIGNED_NOTE:
        raise Skip(f"{SIGNED_NOTE[ext]} assinado — mantido.")

    dst = unique_path(out_dir, src.name)
    progress(0, "Analisando o pacote…")

    try:
        zin = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise CompressionError("O arquivo não é um ZIP/Office válido.")

    notes = ["Recompressão deflate nível 9", "Conteúdo idêntico ao original"]
    with zin, cleanup_on_failure(dst):
        items = zin.infolist()
        if not items:
            raise CompressionError("Pacote ZIP vazio.")
        total = sum(i.file_size for i in items) or 1
        done = 0
        progress(0, f"Comprimindo 0/{len(items)}…")
        with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for n, item in enumerate(items):
                if item.is_dir():
                    zout.writestr(item, b"")
                    continue
                # Preserva compress_type original quando STORED (ex.: mimetype do EPUB)
                new = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                new.comment = item.comment
                new.extra = item.extra
                new.external_attr = item.external_attr
                new.internal_attr = item.internal_attr
                new.create_system = item.create_system
                if item.compress_type == zipfile.ZIP_STORED:
                    new.compress_type = zipfile.ZIP_STORED
                else:
                    new.compress_type = zipfile.ZIP_DEFLATED
                    new._compresslevel = 9
                try:
                    with zin.open(item) as fsrc, zout.open(new, "w") as fdst:
                        _copy_cancellable(fsrc, fdst)
                except (NotImplementedError, OSError, zipfile.BadZipFile) as e:
                    raise CompressionError(f"Falha ao recomprimir '{item.filename}': {e}")
                done += item.file_size
                progress(min(99.0, done / total * 100),
                         f"Comprimindo {n + 1}/{len(items)}…")

        progress(99, "Verificando…")
        verify_zip(dst)

    stored = sum(1 for i in zin.infolist()
                 if not i.is_dir() and i.compress_type == zipfile.ZIP_STORED)
    if stored:
        notes.append(f"{stored} entrada(s) já compactada(s) em STORED (preservada(s))")
    return StrategyResult(dst, notes)
