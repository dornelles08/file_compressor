# File Compressor

Compressor inteligente e seguro de arquivos, com estratégias específicas por formato. Diferente de um ZIP genérico, ele reduz o tamanho com o mínimo de perda (ou sem perda) aplicando o melhor método para cada tipo de arquivo. O arquivo original **nunca** é modificado.

## Principais recursos

- **Estratégias por formato** – Cada categoria (vídeo, áudio, imagem, PDF, Office/EPUB, texto e genérico) tem seu próprio algoritmo otimizado
- **Sem perda no padrão** – Preset *Qualidade* (padrão) busca compressão visualmente sem perda ou totalmente sem perda
- **Máxima redução** – Preset *Máxima redução* oferece compressão mais agressiva com perda aceitável quando apropriado
- **100% seguro** – Detecta tipo real por magic bytes, verifica integridade da saída, compara tamanhos e descarta resultados maiores/iguais ao original
- **Interface moderna** – GUI em PySide6 (PT-BR), com arrastar-e-soltar, fila de processamento, progresso detalhado e resumo de economia
- **CLI disponível** – Pode ser usado em scripts/automação com `uv run cli.py`
- **Cancelamento responsivo** – Interrompe o processamento a qualquer momento com limpeza segura de arquivos parciais
- **WhatsApp-friendly** – Gera saídas otimizadas para envio (dica: envie como **Documento** no WhatsApp para evitar recompressão extra)

## Suporte a formatos

| Categoria | Formatos | Estratégia (Qualidade) | Estratégia (Máx. Redução) |
|---|---|---|---|
| **Vídeo** | `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.m4v`, `.ts`, `.3gp`, `.ogv` | H.264 CRF 18, preset slow, AAC 160 kbps, yuv420p, +faststart → `.mp4` | H.264 CRF 26, preset slow, AAC 128 kbps → `.mp4` |
| **Áudio** | `.wav`, `.aiff`, `.flac`, `.alac` | FLAC nível 12 (sem perda) → `.flac` | Lossless → AAC 160 kbps; lossy elevado → AAC 128 kbps → `.m4a` |
| **Imagem** | `.png`, `.jpg`, `.jpeg`, `.heic`, `.heif`, `.webp`, `.gif`, `.bmp`, `.tiff`, `.ico` | Recompressão lossless/otimizada (PNG nivel 9, JPEG q92, HEIC q92, WebP) — resolução **nunca** muda | PNG alfa/poucas cores → paleta 256 cores; PNG muitas cores → JPEG q72; JPEG/HEIC/WebP q72; EXIF removido |
| **PDF** | `.pdf` | Ghostscript `/prepress` (300 DPI) — visualmente idêntico | Ghostscript `/screen` (72 DPI) — máxima redução |
| **Office/EPUB** | `.docx`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.odp`, `.epub` | Recompressão ZIP nível 9 (mimetype STORED preservado no EPUB) | ZIP nível 9 (sem perda) |
| **Texto** | `.txt`, `.csv`, `.log`, `.json`, `.xml`, `.md`, `.html`, `.css`, `.js`, `.ts`, `.py`, `.rtf`, ... | GZIP nível 9 → `.gz` (sem perda) | XZ nível 9 → `.xz` (sem perda, taxa máxima) |
| **Genérico** | Demais arquivos | LZMA/XZ nível 6 com estimativa de ganho (ignora se < 3%) | LZMA/XZ nível 9 |

Arquivos com assinatura digital (`.jar`, `.apk`, `.aar`) **não** são recomprimidos (para não invalidar assinaturas). Arquivos pequenos ou já altamente comprimidos são ignorados com justificativa clara.

## Segurança e integridade

- **Nunca altera o original** – Saída em pasta `compressados/` (ao lado do original) ou pasta definida pelo usuário
- **Verificação de integridade** – ZIP (testzip), imagens (PIL.verify), PDF (%PDF + %%EOF), GZIP/XZ (leitura de amostra), mídia (ffprobe)
- **Proteção contra perda** – Se a saída ficar ≥ tamanho original, ela é apagada e marcado como "Sem ganho"
- **Cancelamento seguro** – Arquivos parciais são limpos automaticamente ao cancelar

## Requisitos

- [uv](https://github.com/astral-sh/uv)
- [ffmpeg + ffprobe](https://ffmpeg.org/) – Vídeo/áudio
- [Ghostscript](https://www.ghostscript.com/) – PDF

**macOS:** `brew install ffmpeg ghostscript`

## Instalação e uso

```bash
# Instalar dependências
uv sync

# Interface gráfica
uv run main.py

# Linha de comando
uv run cli.py arquivo.mov
uv run cli.py pasta/ --preset max --output ./saida
```

## Dica WhatsApp

Para vídeos grandes (ex.: gravações de tela de 2GB), o preset **Qualidade** costuma reduzir ~80–95% com perda **visualmente imperceptível**. **Envie como Documento** (não como Galeria) para evitar a recompressão adicional do WhatsApp.

## Tecnologias

- Python 3.11 + [PySide6](https://doc.qt.io/qtforpython-6/) (GUI)
- [Pillow](https://python-pillow.org/) + [pillow-heif](https://github.com/bigcat88/pillow-heif) (imagens/HEIC)
- [pypdf](https://pypdf.readthedocs.io/) (leitura de PDFs)
- ffmpeg, Ghostscript (compressão nativa por formato)

## Licença

MIT
