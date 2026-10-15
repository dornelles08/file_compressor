"""Vídeo: reencode H.264 com aceleração por hardware quando disponível.

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
    which, detect_hwaccel,
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
        raise Skip("O arquivo não contém fluxo de vídeo.")
    crf = CRF[preset]
    hw = detect_hwaccel()
    if hw["encoder"] != "libx264":
        return f"Reencode H.264 ({hw['encoder']}, hw accel) CRF {crf} + áudio AAC — resolução mantida"
    return f"Reencode H.264 (libx264) CRF {crf} + áudio AAC — resolução mantida"


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
    hw = detect_hwaccel()
    encoder = hw["encoder"]
    enc_preset = hw["encoder_preset"]

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostdin",
    ]
    if hw.get("extra"):
        cmd.extend(hw["extra"])
    cmd.extend([
        "-i", str(info.path),
        "-map", "0:v:0", "-map", "0:a:0?",
    ])
    cmd.extend(["-c:v", encoder])
    if encoder == "libx264":
        cmd.extend(["-preset", enc_preset, "-crf", crf])
    elif encoder == "h264_nvenc":
        # NVENC: use -cq (quality) similar to CRF
        cmd.extend(["-preset", enc_preset, "-cq", crf, "-rc", "vbr", "-b:v", "0"])
    elif encoder == "h264_videotoolbox":
        cmd.extend(["-q:v", crf])
    elif encoder == "h264_qsv":
        cmd.extend(["-preset", enc_preset, "-global_quality", crf])
    elif encoder in ("h264_amf", "h264_vaapi"):
        cmd.extend(["-qp", crf])
    else:
        cmd.extend(["-preset", "slow", "-crf", crf])
    cmd.extend([
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", abr,
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(dst),
    ])

    duration = info.duration or probe_duration(meta)
    progress(0, "Preparando vídeo…")
    with cleanup_on_failure(dst):
        try:
            run_ffmpeg(cmd, duration, progress, stage="Comprimindo vídeo")
            verify_media(dst)
        except Exception:
            # Fallback to libx264 if hardware accel fails
            cmd_fb = [
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
            run_ffmpeg(cmd_fb, duration, progress, stage="Comprimindo vídeo (fallback)")
            verify_media(dst)
            encoder = "libx264 (fallback)"
            enc_preset = "slow"

    notes_list = list(notes)
    if encoder == "libx264 (fallback)":
        notes_list[0] = f"H.264 (libx264) CRF {crf}, preset slow [fallback automático após falha de hw accel]"
    elif encoder == "libx264":
        notes_list[0] = f"H.264 (libx264) CRF {crf}, preset slow"
    else:
        notes_list[0] = f"H.264 ({encoder}) CRF {crf}, preset {enc_preset} [hw accel]"
    notes = notes_list
    if w and h:
        notes.append(f"Resolução {w}×{h} mantida")
    if src_ext not in (".mp4", ".m4v"):
        notes.append(f"Container {src_ext.lstrip('.').upper()} → MP4")
    if src_pix and src_pix not in ("yuv420p", "yuvj420p"):
        notes.append(f"Pixels {src_pix} → yuv420p (compatibilidade)")
    if audio_count > 1:
        notes.append(f"{audio_count} trilhas de áudio: apenas a primeira mantida")
    return StrategyResult(dst, notes)
