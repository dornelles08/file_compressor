"""Motor de compressão: orquestra detecção, estratégia, verificação e relatório.

Fluxo por arquivo:
  1. Detecta o tipo real (magic bytes + extensão)
  2. A estratégia faz o "plano" (ou pula com motivo — Skip)
  3. Comprime com progresso e cancelamento
  4. Verifica a integridade da saída (já feito pela estratégia)
  5. Compara tamanhos: saída ≥ original ⇒ apaga saída e marca "sem ganho"

O arquivo original NUNCA é modificado.
"""
from __future__ import annotations

import time
from pathlib import Path

from compressor.detector import Category, FileInfo, detect
from compressor.presets import Preset
from compressor.report import Report, Status
from compressor.strategies import get_strategy
from compressor.utils import (
    CancelledError, CompressionError, ProgressFn, Skip, cancel_requested,
    set_cancel_event,
)

DEFAULT_OUT_DIRNAME = "compressados"


def default_out_dir(src: Path) -> Path:
    """Pasta `compressados/` ao lado do arquivo original."""
    return src.parent / DEFAULT_OUT_DIRNAME


def plan_file(info: FileInfo, preset: Preset) -> str:
    """Retorna o plano da estratégia ou levanta Skip com o motivo."""
    return get_strategy(info.category).plan(info, preset)


def compress_file(
    src: Path,
    preset: Preset,
    out_dir: Path | None = None,
    progress: ProgressFn | None = None,
    cancel_event=None,
) -> Report:
    """Comprime um arquivo. Nunca modifica o original."""
    progress = progress or (lambda pct, msg: None)
    started = time.monotonic()

    if cancel_event is not None:
        set_cancel_event(cancel_event)

    try:
        info = detect(src)
    except OSError as e:
        return Report(src=src, status=Status.ERROR, message=f"Sem acesso ao arquivo: {e}")

    report = Report(
        src=src,
        status=Status.PENDING,
        category_label=info.type_label,
        src_size=info.size,
        preset_label=preset.label,
    )

    strategy = get_strategy(info.category)

    # 1) Plano (pode pular)
    try:
        progress(None, "Analisando…")
        plan_note = strategy.plan(info, preset)
        report.notes.append(plan_note)
    except Skip as e:
        report.status = Status.SKIPPED
        report.message = e.message
        report.elapsed = time.monotonic() - started
        return report
    except CompressionError as e:
        report.status = Status.ERROR
        report.message = str(e)
        report.elapsed = time.monotonic() - started
        return report

    # 2) Execução
    target_dir = Path(out_dir).expanduser() if out_dir else default_out_dir(src)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        report.status = Status.ERROR
        report.message = f"Não foi possível criar a pasta de saída: {e}"
        report.elapsed = time.monotonic() - started
        return report

    try:
        result = strategy.run(info, target_dir, preset, progress)
    except Skip as e:
        report.status = Status.SKIPPED
        report.message = e.message
    except CancelledError:
        report.status = Status.CANCELLED
        report.message = "Cancelado pelo usuário."
    except CompressionError as e:
        report.status = Status.ERROR
        report.message = str(e)
    except PermissionError as e:
        report.status = Status.ERROR
        report.message = f"Sem permissão de escrita: {e}"
    except MemoryError:
        report.status = Status.ERROR
        report.message = "Memória insuficiente para processar este arquivo."
    except Exception as e:  # noqa: BLE001 — nunca derrubar a fila
        report.status = Status.ERROR
        report.message = f"Erro inesperado: {type(e).__name__}: {e}"
    finally:
        set_cancel_event(None)

    report.elapsed = time.monotonic() - started

    if report.status in (Status.CANCELLED, Status.ERROR):
        return report

    # 3) Verificações finais: existe? é válida? ficou menor?
    dst = result.dst
    if not dst.exists() or dst.stat().st_size == 0:
        report.status = Status.ERROR
        report.message = "A saída não foi gerada corretamente."
        return report

    dst_size = dst.stat().st_size
    if dst_size >= info.size:
        # Sem ganho: descarta a saída, preserva o original intacto.
        try:
            dst.unlink()
        except OSError:
            pass
        report.status = Status.NO_GAIN
        report.message = (
            "O resultado não ficou menor que o original — o arquivo já é "
            "otimizado para o formato dele."
        )
        return report

    report.status = Status.DONE
    report.dst = dst
    report.dst_size = dst_size
    report.notes.extend(result.notes)
    return report


def safe_plan(src: Path, preset: Preset) -> tuple[FileInfo | None, str | None, bool]:
    """Plano rápido para a UI: devolve (info, plano_ou_motivo, pulado).

    `plano` é a descrição do que será feito; se `pulado` for True,
    é o motivo de ignoração (Skip) ou erro.
    """
    try:
        info = detect(src)
    except OSError:
        return None, "Sem acesso ao arquivo.", True
    try:
        return info, plan_file(info, preset), False
    except Skip as e:
        return info, f"Ignorado: {e.message}", True
    except CompressionError as e:
        return info, f"Erro: {e}", True
