# File Compressor

Compressor inteligente e seguro de arquivos. Diferente de um ZIP, ele aplica estratégias específicas por formato para reduzir o tamanho com **mínima perda ou sem perda de dados**, nunca altera o arquivo original e sempre verifica a integridade da saída.

- **Interface**: GUI profissional em PySide6 (PT-BR)
- **Sem perdas** no preset padrão; redução agressiva opcional
- **Seguro**: detecta tipo real por magic bytes, verifica saída, compara tamanhos e descarta se não houve ganho
- **Flexível**: funciona com arquivos ou pastas inteiras, fila com progresso por arquivo

## Instalação

Requer [uv](https://github.com/astral-sh/uv). Depois de clonar, instale dependências:

```bash
uv sync
```

## Como usar

### Interface gráfica (recomendada)

```bash
uv run main.py
```

- Arraste arquivos ou pastas na área
- Escolha o preset (`Qualidade` ou `Máxima redução`)
- Escolha a pasta de saída (padrão: `compressados/` ao lado do original)
- Clique em **Iniciar**; o progresso é mostrado por linha
- Dê duplo clique num item para ver detalhes

### Linha de comando (CLI)

```bash
uv run cli.py arquivos... [--preset quality|max] [--output DIR]

# Exemplos
uv run cli.py video.mov
uv run cli.py ~/Downloads/fotos/ --preset max --output ~/Desktop/saída
uv run cli.py *.{jpg,png,pdf} --preset quality
```

## Presets

| Preset | Objetivo | Vídeo | Áudio | Imagem | PDF | Texto/Office | Genérico |
|---|---|---|---|---|---|---|---|
| **Qualidade** (padrão) | Visualmente sem perda | H.264 CRF 18, slow, AAC 160 kbps, yuv420p, +faststart | FLAC (nível 12) — arquivos lossless; ignora áudio já lossy | Recompressão lossless (PNG otimizado, JPEG q92 progressivo, HEIC q92, WebP) — resolução mantida | Ghostscript `/prepress` (300 DPI) | ZIP nível 9 (Office/EPUB), GZIP nível 9 (texto) | LZMA (.xz) nível 6 (com estimativa de ganho mínimo) |
| **Máxima redução** | Maior redução aceitável | H.264 CRF 26, slow, AAC 128 kbps | Lossless → AAC 160 kbps (.m4a); lossy elevado → AAC 128 kbps | PNG com alfa/poucas cores → paleta; PNG com muitas cores → JPEG q72; JPEG/HEIC/WebP q72; EXIF removido — resolução mantida | Ghostscript `/screen` (72 DPI) | ZIP nível 9 (Office/EPUB), XZ nível 9 (texto) | LZMA (.xz) nível 9 |

> ⚠️ No preset **Máxima redução**, o áudio é reencodado com perda (aceitável para envio). No preset **Qualidade**, áudio já lossy **não** é reencodado (para não piorar a qualidade).

## Dicas para WhatsApp

- **Envie como Documento** (não como Galeria/Mídia). Isso evita compressões adicionais do WhatsApp e preserva melhor a qualidade.
- Vídeos em MP4 (saída padrão) funcionam bem como documento.
- Para screen recordings grandes (2GB+), o preset **Qualidade** costuma dar reduções expressivas (~80–95%) com perda visualmente imperceptível.

## Formatos suportados

| Categoria | Exemplos | Estratégia |
|---|---|---|
| **Vídeo** | `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.m4v` | ffmpeg H.264 + AAC → `.mp4` |
| **Áudio** | `.wav`, `.aiff`, `.flac`, `.alac` (lossless) → `.flac` (Qualidade) ou `.m4a` (Máx.); formatos já lossy (`.mp3`, `.aac`, `.ogg`, `.opus`) tratados com critério conservador | ffmpeg |
| **Imagem** | `.png`, `.jpg`, `.jpeg`, `.heic`, `.heif`, `.webp`, `.gif`, `.bmp`, `.tiff`, `.ico` | Pillow + pillow-heif (resolução nunca muda) |
| **PDF** | `.pdf` | Ghostscript (regrava) |
| **Office/EPUB** | `.docx`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.odp`, `.epub` | Recompressão ZIP nível 9 (mimetype STORED preservado no EPUB) |
| **Texto** | `.txt`, `.csv`, `.log`, `.json`, `.xml`, `.md`, `.html`, `.css`, `.js`, `.ts`, `.py`, `.rtf`, ... | `.gz` (Qualidade) ou `.xz` (Máx.) sem perda |
| **Genérico** | Outros arquivos | LZMA `.xz` com estimativa de amostra (ignora se ganho < 3%) |

**Arquivos ignorados com justificativa**: `.jar/.apk/.aar` (assinatura digital — recomprimir invalidaria), arquivos muito pequenos, mídia já comprimida sem perspectiva de ganho (estimativa por amostra), arquivos corrompidos/inválidos.

## Ferramentas externas necessárias

- [`ffmpeg` + `ffprobe`](https://ffmpeg.org/) — necessário para vídeo/áudio
- [`ghostscript` (`gs`)](https://www.ghostscript.com/) — necessário para PDF

Instalação (macOS):

```bash
brew install ffmpeg ghostscript
```

Linux/Windows: consulte a documentação oficial.

## Desempenho por hardware (vídeo)

O compressor detecta automaticamente aceleradores de hardware para codificação H.264:

| Plataforma | Verificação | Codificador usado | Observações |
|---|---|---|---|
| Linux | NVIDIA (`h264_nvenc`) | `h264_nvenc` | Usa `-hwaccel auto`, CRF via `-cq`. Fallback p/ `libx264` caso falhe. |
| Linux | Intel QuickSync (`h264_qsv`) | `h264_qsv` | Usa `-global_quality`. Fallback automático. |
| Linux | AMD (VAAPI/AMF) | `h264_vaapi` ou `h264_amf` | Prioriza VAAPI quando disponível. Fallback automático. |
| macOS | VideoToolbox | `h264_videotoolbox` | Usa `-q:v` com CRF. Fallback automático para `libx264`. |
| Outros | — | `libx264` (preset `slow`, CRF padrão) | Mantém qualidade/compatibilidade com WhatsApp (MP4 H.264 yuv420p). |

- Saída sempre em MP4 H.264, pixel format `yuv420p` para máxima compatibilidade.
- Aceleração priorizada quando disponível; em caso de falha, há **fallback automático** para `libx264` preservando presets e CRF.
- Áudio mantém AAC (não priorizamos hw accel para áudio por raridade/compatibilidade neste caso).

## Segurança & integridade

- **Nunca toca no original** — saída em pasta separada (`compressados/` ou escolhida)
- **Verificação**: verifica ZIP (testzip), imagem (PIL.verify), PDF (%PDF + %%EOF), GZIP/XZ (leitura de amostra), mídia (ffprobe)
- **Sem ganho**: se a saída ≥ original, ela é apagada e o arquivo é marcado como "Sem ganho"
- **Cancelamento**: interrompe com limpeza segura de arquivos parciais

## Desenvolvimento

```bash
uv run cli.py /tmp/teste/ --preset quality
uv run python -m pytest  # (sem testes ainda)
```

## Licença

MIT
