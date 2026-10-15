"""Utilitários compartilhados: tamanhos, ffprobe, ffmpeg com progresso."""
from __future__ import annotations

import json
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

# Callback de progresso: pct entre 0 e 100 (ou None = indeterminado), mensagem.
ProgressFn = Callable[[float | None, str], None]


class CompressionError(Exception):
    """Erro de compressão com mensagem amigável em PT-BR."""


class CancelledError(Exception):
    """Operação cancelada pelo usuário."""


class Skip(Exception):
    """Estratégia decidiu não comprimir (motivo em `.message`)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def human_size(n: int | float) -> str:
    """Converte bytes para texto legível (PT-BR)."""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n:.2f} TB".replace(".", ",")


def which(tool: str) -> str | None:
    return shutil.which(tool)


def ffprobe(path: Path) -> dict:
    """Retorna metadados JSON de mídia via ffprobe."""
    if not which("ffprobe"):
        raise CompressionError("ffprobe não encontrado (instale o ffmpeg).")
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise CompressionError("ffprobe demorou demais para analisar o arquivo.")
    if out.returncode != 0:
        raise CompressionError(f"Não foi possível analisar a mídia: {_tail(out.stderr)}")
    try:
        return json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        raise CompressionError("ffprobe retornou dados inválidos.")


def probe_duration(meta: dict) -> float | None:
    try:
        d = float(meta.get("format", {}).get("duration"))
        return d if d > 0 else None
    except (TypeError, ValueError):
        return None


def _tail(text: str, n: int = 4) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return " / ".join(lines[-n:]) if lines else "sem detalhes"


def terminate_process(proc: subprocess.Popen, grace: float = 0.75) -> None:
    """Encerra um subprocesso rapidamente.

    Alguns programas (ex.: ffmpeg) demoram muitos segundos para sair após
    SIGTERM — como o cancelamento descarta a saída, damos um pequeno período
    de graça e então forçamos com SIGKILL.
    """
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def run_ffmpeg(
    cmd: list[str],
    duration: float | None,
    progress: ProgressFn,
    stage: str = "Comprimindo",
) -> None:
    """
    Executa um comando ffmpeg lendo `-progress pipe:1`, reportando percentual
    quando a duração é conhecida. Suporta cancelamento via CancelledError.
    O chamador deve injetar `-progress pipe:1 -nostats` no cmd.
    """
    if not which("ffmpeg"):
        raise CompressionError("ffmpeg não encontrado (instale: brew install ffmpeg).")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    tail: deque[str] = deque(maxlen=60)
    cancelled = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            tail.append(line)
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                # Ambas as chaves do -progress são microssegundos.
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if duration and duration > 0:
                    pct = min(99.0, max(0.0, us / 1_000_000 / duration * 100))
                    progress(pct, f"{stage}… {pct:.0f}%")
                else:
                    progress(None, f"{stage}…")
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
        msg = _interesting_tail(tail)
        raise CompressionError(f"O ffmpeg falhou: {msg}")


def _interesting_tail(lines) -> str:
    bad = [
        ln for ln in lines
        if any(k in ln.lower() for k in ("error", "invalid", "failed", "no such", "denied", "unknown"))
    ]
    chosen = bad[-3:] if bad else list(lines)[-5:]
    return " / ".join(chosen) if chosen else "sem detalhes"


# ---------------------------------------------------------------- cancelamento
_cancel_event = None  # definido pelo engine/CLI/GUI (threading.Event)


def set_cancel_event(event) -> None:
    global _cancel_event
    _cancel_event = event


def cancel_requested() -> bool:
    return _cancel_event is not None and _cancel_event.is_set()


# ------------------------------------------------------------------ verificações
def verify_media(path: Path) -> None:
    meta = ffprobe(path)
    streams = meta.get("streams") or []
    if not streams:
        raise CompressionError("O arquivo de saída não contém fluxos de mídia válidos.")


def verify_zip(path: Path) -> None:
    import zipfile

    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise CompressionError(f"Entrada corrompida no ZIP de saída: {bad}")
    except zipfile.BadZipFile:
        raise CompressionError("O arquivo de saída não é um ZIP válido.")


def verify_image(path: Path) -> None:
    from PIL import Image

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as e:  # noqa: BLE001
        raise CompressionError(f"A imagem de saída é inválida ({e}).")


def verify_pdf(path: Path) -> None:
    with open(path, "rb") as f:
        head = f.read(16)
        if not head.startswith(b"%PDF"):
            raise CompressionError("O PDF de saída não tem cabeçalho válido.")
        f.seek(max(0, path.stat().st_size - 4096))
        if b"%%EOF" not in f.read():
            raise CompressionError("O PDF de saída está incompleto (sem %%EOF).")


def verify_gzip(path: Path) -> None:
    import gzip

    try:
        with gzip.open(path, "rb") as f:
            f.read(1024 * 1024)
    except OSError:
        raise CompressionError("O arquivo .gz de saída está corrompido.")


def verify_xz(path: Path) -> None:
    import lzma

    try:
        with lzma.open(path, "rb") as f:
            f.read(1024 * 1024)
    except lzma.LZMAError:
        raise CompressionError("O arquivo .xz de saída está corrompido.")


def unique_path(folder: Path, filename: str) -> Path:
    """Caminho único em `folder`, acrescentando -2, -3... se já existir."""
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 2
    while True:
        candidate = folder / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1
