"""Imagens via Pillow (+ pillow-heif para HEIC/HEIF).

Regras — resolução NUNCA muda:

QUALITY (visualmente sem perda):
  PNG → recompressão lossless (optimize, nível 9)
  JPEG → reencode q92 progressivo (EXIF preservado)
  HEIC → reencode q92 (EXIF preservado)
  WebP → reencode q92
  GIF → otimização de paleta lossless (frames preservados)
  BMP/TIFF → convertido para PNG (lossless) quando couber

MAX (máxima redução):
  PNG  → se ≤256 cores repara em paleta (visualmente igual p/ screenshots);
          caso contrário vira JPEG q72 (nota explicando)
        → PNGs com transparência: paleta com alfa (256 cores)
  JPEG → q72, EXIF removido (após aplicar orientação)
  HEIC → q72, EXIF removido
  WebP → q72
  GIF  → paleta reduzida a 128 cores
  BMP/TIFF → JPEG q72 (sem alfa) ou PNG paleta (com alfa)

Em QUALITY, se a saída sair maior que a original, o motor marca "sem ganho".
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

try:  # registro de HEIC/HEIF
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:  # noqa: BLE001 — sem HEIC, a estratégia apenas ignora o formato
    pass

from compressor.strategies.base import (
    Preset, ProgressFn, StrategyResult, cleanup_on_failure, unique_path,
)
from compressor.utils import CompressionError, Skip, verify_image

JPEG_Q = {Preset.QUALITY: 92, Preset.MAX: 72}
WEBP_Q = {Preset.QUALITY: 92, Preset.MAX: 72}
GIF_COLORS = {Preset.MAX: 128}
MAX_PNG_COLORS = 256

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp",
                 ".gif", ".bmp", ".tiff", ".tif", ".ico"}


def plan(info, preset: Preset) -> str:
    ext = info.path.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise Skip(f"Formato de imagem não suportado ({ext or 'sem extensão'}).")
    if preset is Preset.QUALITY:
        return "Recompressão otimizada — resolução e cores preservadas"
    return "Redução agressiva — mesma resolução, qualidade reduzida"


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )


def _save(img: Image.Image, dst: Path, fmt: str, preset: Preset, **kwargs) -> None:
    """Salva aplicando a política de metadados do preset.

    QUALITY preserva o EXIF; MAX descarta (Pillow e pillow-heif leem o EXIF
    de ``img.info``, então é preciso removê-lo de lá — só omitir o kwarg não
    basta).
    """
    if preset is Preset.QUALITY:
        exif = img.info.get("exif")
        if exif:
            kwargs["exif"] = exif
    else:
        img.info.pop("exif", None)
    icc = img.info.get("icc_profile")
    if icc:
        kwargs["icc_profile"] = icc
    img.save(dst, format=fmt, **kwargs)


def _png_colors(img: Image.Image) -> int | None:
    """Número de cores se ≤ MAX_PNG_COLORS, senão None."""
    try:
        colors = img.convert("RGB").getcolors(maxcolors=MAX_PNG_COLORS)
    except Exception:  # noqa: BLE001
        return None
    return len(colors) if colors is not None else None


def _process(src: Path, dst: Path, preset: Preset) -> str:
    """Executa a conversão. Retorna uma nota sobre o que foi feito."""
    try:
        img = Image.open(src)
    except Exception as e:  # noqa: BLE001
        raise CompressionError(f"Não foi possível abrir a imagem: {e}")

    ext = src.suffix.lower()
    animated = getattr(img, "is_animated", False)
    note = ""

    with img:
        if preset is Preset.MAX:
            # MAX: orientação aplicada, metadados descartados
            try:
                img = ImageOps.exif_transpose(img) or img
            except Exception:  # noqa: BLE001
                pass

        if ext == ".png":
            img.load()
            if preset is Preset.QUALITY:
                if animated:
                    frames = _frames(img)
                    _save_animated(frames, dst, "PNG", preset,
                                   optimize=True, compress_level=9)
                else:
                    _save(img, dst, "PNG", preset, optimize=True, compress_level=9)
                return note or "Recompressão PNG lossless (nível 9)"
            # MAX
            ncolors = _png_colors(img)
            alpha = _has_alpha(img)
            if alpha:
                pal = _quantize(img, MAX_PNG_COLORS, method=Image.FASTOCTREE)
                _save(pal, dst, "PNG", preset, optimize=True, compress_level=9)
                return "Reduzido para paleta de 256 cores com alfa (screenshots parecem idênticos)"
            if ncolors is not None and ncolors <= MAX_PNG_COLORS:
                pal = img.convert("P", palette=Image.ADAPTIVE, colors=MAX_PNG_COLORS)
                _save(pal, dst, "PNG", preset, optimize=True, compress_level=9)
                return (f"Convertido para paleta de {ncolors} cores "
                        "(visualmente idêntico para telas/gráficos)")
            # Foto em PNG → JPEG
            rgb = img.convert("RGB")
            _save(rgb, dst, "JPEG", preset, quality=JPEG_Q[preset],
                  optimize=True, progressive=True)
            return (f"PNG com muitas cores → JPEG q{JPEG_Q[preset]} "
                    "(mesma resolução)")

        if ext in (".jpg", ".jpeg"):
            if animated:
                raise Skip("JPEG animado não é suportado.")
            img.load()
            if preset is Preset.MAX and _has_alpha(img):
                img = img.convert("RGB")
            _save(img, dst, "JPEG", preset, quality=JPEG_Q[preset],
                  optimize=True, progressive=True)
            if preset is Preset.MAX:
                return f"JPEG q{JPEG_Q[preset]}, progressivo, EXIF removido"
            return f"JPEG q{JPEG_Q[preset]} progressivo (EXIF preservado)"

        if ext in (".heic", ".heif"):
            img.load()
            # pillow-heif registra o formato como "HEIF" (não "HEIC")
            _save(img, dst, "HEIF", preset, quality=JPEG_Q[preset])
            if preset is Preset.MAX:
                return f"HEIC q{JPEG_Q[preset]}, EXIF removido"
            return f"HEIC q{JPEG_Q[preset]} (EXIF preservado)"

        if ext == ".webp":
            img.load()
            lossless = preset is Preset.QUALITY and not animated and not _has_alpha(img)
            _save(img, dst, "WEBP", preset, quality=WEBP_Q[preset],
                  lossless=lossless, method=6)
            if lossless:
                return "WebP lossless (sem perda)"
            return f"WebP q{WEBP_Q[preset]}"

        if ext == ".gif":
            img.load()
            if animated:
                frames = _frames(img)
                if preset is Preset.MAX:
                    frames = [_quantize(f.convert("RGBA"), GIF_COLORS[preset],
                                        method=Image.FASTOCTREE)
                              for f in frames]
                    _save_animated(frames, dst, "GIF", preset,
                                   optimize=True, colors=GIF_COLORS[preset])
                    return f"Animação reduzida a {GIF_COLORS[preset]} cores"
                _save_animated(frames, dst, "GIF", preset, optimize=True)
                return "Otimização GIF (frames preservados, sem perda)"
            colors = GIF_COLORS.get(preset)
            if colors:
                pal = _quantize(img.convert("RGBA"), colors, method=Image.FASTOCTREE)
                _save(pal, dst, "GIF", preset, optimize=True, colors=colors)
                return f"Paleta reduzida a {colors} cores"
            _save(img, dst, "GIF", preset, optimize=True)
            return "Otimização GIF (sem perda)"

        if ext in (".bmp", ".tiff", ".tif", ".ico"):
            img.load()
            alpha = _has_alpha(img)
            if preset is Preset.QUALITY and not animated:
                # Lossless: vira PNG
                _save(img.convert("RGBA" if alpha else "RGB"), dst, "PNG",
                      preset, optimize=True, compress_level=9)
                return f"{ext.lstrip('.').upper()} → PNG (lossless)"
            if alpha:
                pal = _quantize(img.convert("RGBA"), MAX_PNG_COLORS,
                                method=Image.FASTOCTREE)
                _save(pal, dst, "PNG", preset, optimize=True, compress_level=9)
                return "Convertido para PNG paleta 256 cores com alfa"
            rgb = img.convert("RGB")
            _save(rgb, dst, "JPEG", preset, quality=JPEG_Q[preset],
                  optimize=True, progressive=True)
            return f"→ JPEG q{JPEG_Q[preset]} (mesma resolução)"

        raise Skip(f"Formato de imagem não suportado ({ext}).")


def _quantize(img: Image.Image, colors: int, method: int) -> Image.Image:
    try:
        return img.quantize(colors=colors, method=method)
    except Exception:  # noqa: BLE001
        return img


def _frames(img: Image.Image) -> list[Image.Image]:
    frames: list[Image.Image] = []
    try:
        for i in range(getattr(img, "n_frames", 1)):
            img.seek(i)
            frames.append(img.copy())
    except Exception:  # noqa: BLE001
        frames = [img.copy()]
    return frames or [img.copy()]


def _save_animated(frames: list[Image.Image], dst: Path, fmt: str,
                   preset: Preset, **kwargs) -> None:
    if not frames:
        raise CompressionError("Animação sem frames.")
    first, rest = frames[0], frames[1:]
    durations = [f.info.get("duration", frames[0].info.get("duration", 100))
                 for f in frames]
    first.save(dst, format=fmt, save_all=True, append_images=rest,
               duration=durations, loop=first.info.get("loop", 0), **kwargs)


def run(info, out_dir: Path, preset: Preset, progress: ProgressFn) -> StrategyResult:
    src = info.path
    ext = src.suffix.lower()
    # Saída em .png pode virar .jpg (decidido no _process); resolvemos após.
    dst = unique_path(out_dir, src.name)

    progress(10, "Decodificando imagem…")
    with cleanup_on_failure(dst):
        try:
            note = _process(src, dst, preset)
        except CompressionError:
            raise
        except OSError as e:
            # Imagem truncada/corrompida: Pillow levanta OSError no load().
            raise CompressionError(
                f"Imagem corrompida ou truncada — não foi possível decodificar ({e})."
            )
        # Se o formato de saída divergiu do nome (ex.: .png → .jpg), corrige.
        fmt = _detected_fmt(dst)
        wanted = {"JPEG": ".jpg", "PNG": ".png", "HEIF": ".heic", "WEBP": ".webp",
                  "GIF": ".gif"}.get(fmt)
        if wanted and dst.suffix.lower() != wanted:
            renamed = dst.with_suffix(wanted)
            if renamed.exists():
                renamed = unique_path(out_dir, renamed.name)
            dst.rename(renamed)
            dst = renamed
        progress(90, "Verificando…")
        verify_image(dst)

    notes = [note] if note else []
    if preset is Preset.MAX:
        notes.append("Resolução inalterada")
    return StrategyResult(dst, notes)


def _detected_fmt(path: Path) -> str:
    try:
        with Image.open(path) as img:
            return img.format or ""
    except Exception:  # noqa: BLE001
        return ""
