#!/usr/bin/env python3
"""CLI do File Compressor — útil para testes e automação.

Uso:
    uv run cli.py arquivos... [--preset quality|max] [--output DIR]

Exemplos:
    uv run cli.py video.mov
    uv run cli.py fotos/ --preset max --output /tmp/saida
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compressor.detector import collect_files
from compressor.engine import compress_file
from compressor.presets import Preset
from compressor.report import Status
from compressor.utils import human_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprime arquivos de qualquer tipo sem tocar nos originais.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="arquivos ou pastas")
    parser.add_argument(
        "-p", "--preset", choices=["quality", "max"], default="quality",
        help="quality = visualmente sem perda (padrão); max = máxima redução",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="pasta de saída (padrão: pasta 'compressados' ao lado de cada arquivo)",
    )
    args = parser.parse_args(argv)

    preset = Preset.QUALITY if args.preset == "quality" else Preset.MAX
    files = collect_files(args.inputs)
    if not files:
        print("Nenhum arquivo encontrado.", file=sys.stderr)
        return 1

    print(f" preset: {preset.label} · {len(files)} arquivo(s)\n")
    total_src = total_dst = 0
    counts = {s: 0 for s in Status}

    for src in files:
        def progress(pct, msg, _last={"": ""}):  # noqa: B006
            key = msg.split("…")[0]
            if _last.get("") != key:
                print(f"\r   {msg:<60}", end="", flush=True)
                _last[""] = key

        report = compress_file(src, preset, out_dir=args.output, progress=progress)
        print(f"\r{'':<70}", end="\r")
        counts[report.status] += 1

        if report.status is Status.DONE:
            total_src += report.src_size
            total_dst += report.dst_size
            print(f"  ✔ {report.src.name}: {human_size(report.src_size)} → "
                  f"{human_size(report.dst_size)}  ({report.savings_text})")
            for note in report.notes:
                print(f"      · {note}")
        elif report.status in (Status.SKIPPED, Status.NO_GAIN):
            print(f"  • {report.src.name}: {report.status.label} — {report.message}")
        elif report.status is Status.CANCELLED:
            print(f"  • {report.src.name}: cancelado")
        else:
            print(f"  ✖ {report.src.name}: {report.message}")

    print()
    done = counts[Status.DONE]
    if done:
        saved = total_src - total_dst
        pct = (saved / total_src * 100) if total_src else 0
        print(f"  Total: {human_size(total_src)} → {human_size(total_dst)} "
              f"(−{pct:.0f}%, economizou {human_size(saved)})")
    parts = [f"{n} {s.label.lower()}" for s, n in counts.items() if n]
    print(f"  {len(files)} arquivo(s): {' · '.join(parts)}")

    return 0 if counts[Status.ERROR] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
