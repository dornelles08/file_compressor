"""Vídeo: reencode H.264 (x264) via ffmpeg.

- Preset QUALITY: CRF 18 (visualmente sem perda), áudio AAC 160 kbps
- Preset MAX:     CRF 26, áudio AAC 128 kbps
- Saída sempre em MP4 (compatível com WhatsApp/players), resolução mantida.
"""
from __future__ import annotations

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, unique_path,
)
from compressor.utils import (
    CompressionError, Skip, ffprobe, probe_duration, run_ffmpeg, verify_media,
    which,
)
from pathlib import Path

CRF = {Preset.QUALITY: "18", Preset.MAX: "26"}
ABITRATE = {Preset.QUALITY: "160k", Preset.MAX: "128k"}


def plan(info, preset: Preset) -> str:
    if not which("ffmpeg"):
        raise Skip("ffmpeg não encontrado — instale com: brew install ffmpeg")
    meta = info.meta.get("_ffprobe") or {}
    streams = meta.get("streams") or []
    if not any(s.get("codec_type") == "video" for s in streams):
        # Não deveria chegar aqui (categoria áudio), mas garante.
        raise Skip("O arquivo não contém fluxo de vídeo.")
    crf = CRF[preset]
    return f"Reencode H.264 (CRF {crf}) + áudio AAC — resolução mantida"


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    meta = info.meta.get("_ffprobe") or ffprobe(info.path)
    streams = meta.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if v is None:
        raise Skip("O arquivo não contém fluxo de vídeo.")
    audio_count = sum(1 for s in streams if s.get("codec_type") == "audio")

    w, h = v.get("width") or 0, v.get("height") or 0
    src_pix = v.get("pix_fmt") or ""
    src_ext = info.path.suffix.lower()
    crf, abr = CRF[preset], ABITRATE[preset]

    dst = unique_path(out_dir, f"{info.path.stem}.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostdin",
        "-i", str(info.path),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "slow", "-crf", crf,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", abr,
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(dst),
    ]

    duration = info.duration or probe_duration(meta)
    progress(0, "Preparando vídeo…")
    with cleanup_on_failure(dst):
        run_ffmpeg(cmd, duration, progress, stage="Comprimindo vídeo")
        verify_media(dst)

    notes = [
        f"H.264 (x264) CRF {crf}, preset slow",
        f"Áudio AAC {int(abr.rstrip('k'))} kbps",
    ]
    if w and h:
        notes.append(f"Resolução {w}×{h} mantida")
    if src_ext not in (".mp4", ".m4v"):
        notes.append(f"Container {src_ext.lstrip('.').upper()} → MP4")
    if src_pix and src_pix not in ("yuv420p", "yuvj420p"):
        notes.append(f"Pixels {src_pix} → yuv420p (compatibilidade)")
    if audio_count > 1:
        notes.append(f"{audio_count} trilhas de áudio: apenas a primeira mantida")
    return StrategyResult(dst, notes)
