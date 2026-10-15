"""Áudio: FLAC sem perda no preset padrão; AAC na máxima redução.

- QUALITY: WAV/AIFF/ALAC/FLAC → FLAC (lossless, ~50% menor)
           áudio já lossy (mp3/aac/ogg/opus) → ignorado (reencodar pioraria)
- MAX:     lossless → AAC 160 kbps (.m4a)
           lossy com bitrate alto (>160k) → AAC 128 kbps; senão ignorado
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

LOSSLESS_CODECS = ("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_u8",
                   "pcm_f32le", "pcm_f64le", "pcm_s16be", "pcm_s24be",
                   "flac", "alac", "wavpack", "tta")
AAC_BITRATE = {Preset.QUALITY: None, Preset.MAX: "160k"}
MAX_LOSSY_AAC_BITRATE = "128k"


def _streams(info) -> tuple[dict, dict]:
    meta = info.meta.get("_ffprobe") or ffprobe(info.path)
    streams = meta.get("streams") or []
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if not audios:
        raise Skip("O arquivo não contém fluxo de áudio.")
    return meta, audios[0]


def _bitrate_kbps(meta: dict, stream: dict) -> int:
    for raw in (stream.get("bit_rate"), meta.get("format", {}).get("bit_rate")):
        try:
            return int(raw) // 1000
        except (TypeError, ValueError):
            continue
    return 0


def plan(info, preset: Preset) -> str:
    if not which("ffmpeg"):
        raise Skip("ffmpeg não encontrado — instale com: brew install ffmpeg")
    meta, a = _streams(info)
    codec = a.get("codec_name") or ""
    lossless = codec in LOSSLESS_CODECS

    if preset is Preset.QUALITY:
        if lossless:
            return "Recodificar em FLAC (sem perda, ~50% menor)"
        raise Skip(
            f"Áudio já comprimido ({codec.upper()}, com perda) — "
            "no preset padrão não reencodamos para não piorar a qualidade."
        )

    # MAX
    kbps = _bitrate_kbps(meta, a)
    if lossless:
        return "Codificar em AAC 160 kbps (.m4a) — máxima redução"
    if kbps and kbps <= 160:
        raise Skip(
            f"Áudio já comprimido em {kbps} kbps — reencodar só pioraria."
        )
    return f"Reencodar {codec.upper()} → AAC 128 kbps (.m4a)"


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    meta, a = _streams(info)
    codec = a.get("codec_name") or ""
    lossless = codec in LOSSLESS_CODECS
    duration = info.duration or probe_duration(meta)
    notes: list[str] = []

    if preset is Preset.QUALITY:
        assert lossless  # plan() garante
        dst = unique_path(out_dir, f"{info.path.stem}.flac")
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostdin",
            "-i", str(info.path), "-map", "0:a:0",
            "-c:a", "flac", "-compression_level", "12",
            "-progress", "pipe:1", "-nostats", str(dst),
        ]
        notes.append("FLAC nível 12 — dados idênticos ao original (sem perda)")
        if not codec.startswith("pcm"):
            notes.append(f"{codec.upper()} → FLAC (recode lossless)")
    else:
        kbps = _bitrate_kbps(meta, a)
        abr = "160k" if lossless else MAX_LOSSY_AAC_BITRATE
        dst = unique_path(out_dir, f"{info.path.stem}.m4a")
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostdin",
            "-i", str(info.path), "-map", "0:a:0",
            "-c:a", "aac", "-b:a", abr, "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(dst),
        ]
        if lossless:
            notes.append(f"{codec.upper()} → AAC {abr.rstrip('k')} kbps (perda aceita no preset máximo)")
        else:
            notes.append(f"{codec.upper()} {kbps} kbps → AAC {abr.rstrip('k')} kbps")
        notes.append("Formato .m4a compatível com WhatsApp/players")

    progress(0, "Preparando áudio…")
    with cleanup_on_failure(dst):
        run_ffmpeg(cmd, duration, progress, stage="Comprimindo áudio")
        verify_media(dst)
    return StrategyResult(dst, notes)
