"""Detecção de tipo real de arquivo: magic bytes + extensão + heurística."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from compressor.utils import probe_duration


class Category(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    PDF = "pdf"
    OFFICE = "office"
    TEXT = "text"
    GENERIC = "generic"


VIDEO_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg",
    ".wmv", ".flv", ".ts", ".mts", ".m2ts", ".vob", ".3gp", ".ogv",
}
AUDIO_EXT = {
    ".wav", ".aiff", ".aif", ".aifc", ".flac", ".m4a", ".mp3", ".ogg",
    ".oga", ".opus", ".aac", ".wma", ".alac", ".au",
}
IMAGE_EXT = {
    ".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp", ".gif", ".bmp",
    ".tiff", ".tif", ".ico", ".avif",
}
PDF_EXT = {".pdf"}
OFFICE_EXT = {
    ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub",
}
# Assinados: recomprimir invalida a assinatura — tratados à parte.
SIGNED_EXT = {".jar", ".apk", ".aar"}
TEXT_EXT = {
    ".txt", ".csv", ".log", ".json", ".xml", ".md", ".markdown", ".html",
    ".htm", ".css", ".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".c",
    ".cpp", ".h", ".hpp", ".ini", ".conf", ".cfg", ".yaml", ".yml",
    ".toml", ".sql", ".sh", ".bash", ".zsh", ".bat", ".ps1", ".srt",
    ".vtt", ".tsv", ".gitignore", ".env", ".rtf",
}
# Formatos já comprimidos: compressão externa não ganha nada.
PRECOMPRESSED_EXT = {
    ".zip", ".7z", ".rar", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".lz4",
    ".war", ".cab", ".arj", ".lha", ".lzh",
}


@dataclass
class FileInfo:
    path: Path
    category: Category
    format_label: str  # ex.: "MP4", "PNG"
    size: int
    duration: float | None = None
    meta: dict = field(default_factory=dict)

    @property
    def type_label(self) -> str:
        cat = {
            Category.VIDEO: "Vídeo",
            Category.AUDIO: "Áudio",
            Category.IMAGE: "Imagem",
            Category.PDF: "PDF",
            Category.OFFICE: "Office",
            Category.TEXT: "Texto",
            Category.GENERIC: "Arquivo",
        }[self.category]
        return f"{cat} · {self.format_label}"


def _head(path: Path, n: int = 8192) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _fmt_label(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return ext.upper() or "sem extensão"


def _from_magic(head: bytes, path: Path) -> Category | None:
    """Retorna categoria com base no cabeçalho binário, ou None se indefinido."""
    ext = path.suffix.lower()

    if head.startswith(b"%PDF"):
        return Category.PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Category.IMAGE
    if head.startswith(b"\xff\xd8\xff"):
        return Category.IMAGE
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return Category.IMAGE
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return Category.IMAGE
    if head.startswith(b"8BPS"):
        return Category.GENERIC  # PSD: estimativa decide
    if head[:4] == b"RIFF" and len(head) >= 12:
        fourcc = head[8:12]
        if fourcc == b"WEBP":
            return Category.IMAGE
        if fourcc == b"WAVE":
            return Category.AUDIO
        if fourcc == b"AVI ":
            return Category.VIDEO
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"):
            return Category.IMAGE
        if brand in (b"avif", b"avis"):
            return Category.IMAGE
        return Category.VIDEO  # isom, mp42, avc1, qt, M4V, dash...
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return Category.VIDEO  # Matroska/WebM
    if head.startswith(b"OggS"):
        return Category.VIDEO if ext == ".ogv" else Category.AUDIO
    if head.startswith(b"fLaC"):
        return Category.AUDIO
    if head.startswith(b"ID3") or (
        len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0
    ):
        return Category.AUDIO
    if head[:5] == b"FORM" and len(head) >= 12 and head[8:12] in (b"AIFF", b"AIFC"):
        return Category.AUDIO
    if head.startswith(b"MThd"):
        return Category.GENERIC  # MIDI
    if head.startswith(b"PK\x03\x04"):
        if ext in OFFICE_EXT:
            return Category.OFFICE
        if ext in SIGNED_EXT:
            return Category.OFFICE  # tratado como "assinado" na estratégia
        return Category.GENERIC  # zip comum: estimativa decide
    if head.startswith(b"\x1f\x8b"):
        return Category.GENERIC  # gzip: já comprimido
    if head.startswith(b"7z\xbc\xaf\x27\x1c") or head.startswith(b"Rar!"):
        return Category.GENERIC
    if head.startswith(b"MZ") or head.startswith(b"\x7fELF"):
        return Category.GENERIC
    if head.startswith(b"SQLite format 3\x00"):
        return Category.GENERIC
    if head[:5] == b"{\\rtf":
        return Category.TEXT  # RTF é texto (não é um container ZIP/Office)
    if head.startswith(b"<!DOC") or head.startswith(b"<!doc") or head.startswith(b"<!DOCTYPE"):
        return Category.TEXT
    return None


def _looks_like_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    # Taxa de bytes decodificáveis como UTF-8.
    decoded = head.decode("utf-8", errors="ignore")
    return len(decoded) >= len(head) * 0.85


def detect(path: Path) -> FileInfo:
    """Detecta a categoria real de `path`."""
    path = Path(path)
    size = path.stat().st_size
    head = _head(path)
    ext = path.suffix.lower()
    fmt = _fmt_label(path)

    category = _from_magic(head, path)

    if category is None:
        if ext in VIDEO_EXT:
            category = Category.VIDEO
        elif ext in AUDIO_EXT:
            category = Category.AUDIO
        elif ext in IMAGE_EXT:
            category = Category.IMAGE
        elif ext in PDF_EXT:
            category = Category.PDF
        elif ext in OFFICE_EXT or ext in SIGNED_EXT:
            category = Category.OFFICE
        elif ext in PRECOMPRESSED_EXT:
            category = Category.GENERIC
        elif _looks_like_text(head):
            category = Category.TEXT
        else:
            category = Category.GENERIC

    # Formato legível mais específico para a UI, quando conhecido.
    if category is Category.VIDEO and ext:
        fmt = ext.lstrip(".").upper()
    elif category is Category.OFFICE and ext in SIGNED_EXT:
        fmt = ext.lstrip(".").upper()

    info = FileInfo(path=path, category=category, format_label=fmt, size=size)

    if category in (Category.VIDEO, Category.AUDIO):
        try:
            from compressor.utils import ffprobe

            meta = ffprobe(path)
            info.meta["_ffprobe"] = meta
            info.duration = probe_duration(meta)
        except Exception:  # noqa: BLE001 — ffprobe opcional na detecção
            pass

    return info


def collect_files(inputs: list[Path]) -> list[Path]:
    """Coleta arquivos de uma lista de caminhos (arquivos ou pastas), sem duplicatas.
    Ignora pastas ocultas e a pasta `compressados` (saída)."""
    seen: set[str] = set()
    result: list[Path] = []
    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_file():
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                result.append(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(
                    d for d in dirs if not d.startswith(".") and d.lower() != "compressados"
                )
                for name in sorted(files):
                    if name.startswith("."):
                        continue
                    fp = Path(root) / name
                    if not fp.is_file():
                        continue
                    key = str(fp.resolve())
                    if key not in seen:
                        seen.add(key)
                        result.append(fp)
    return result
