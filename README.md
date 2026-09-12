# DAISY 3 - Tâm lý học về tiền

Repo này quản lý quy trình xây dựng bản sách nói **DAISY 3** tiếng Việt cho *Tâm lý học về tiền*, hướng tới người khiếm thị và người gặp khó khăn khi đọc chữ in.

Mục tiêu không phải chỉ tạo một audiobook MP3. Đầu ra cuối phải có cấu trúc DAISY 3 để người nghe có thể điều hướng theo chương/mục và đồng bộ văn bản - âm thanh.

## Scope

Pipeline dự kiến:

```text
DOCX/EPUB/PDF text
        |
        v
clean + structure text
        |
        +--> chapter text --> TTS/SSML --> chapter MP3
        |
        v
     DTBook XML
        |
        v
 DAISY Pipeline 2
        |
        v
 XML + SMIL + NCX + OPF + MP3
        |
        v
 validate -> EasyReader/Thorium -> ZIP + SHA256
```

**MVP đầu tiên là Chapter 1 end-to-end.** Chỉ chạy full book sau khi Chapter 1 đã mở và điều hướng đúng trong DAISY reader.

## Repository layout

```text
.
├── config/
│   ├── book.yaml
│   └── pronunciation.yaml
├── data/source/          # local copyrighted source; ignored by Git
├── build/
│   ├── clean/
│   ├── text/
│   ├── audio/
│   └── daisy/
├── daisy_book/           # Python utilities
├── docs/
│   ├── workflow.md
│   └── qa_checklist.md
├── output/               # final ZIP + SHA256; ignored by Git
├── tests/
├── .env.example
├── Makefile
├── pyproject.toml
└── requirements.txt
```

## 1. Requirements

- Python 3.10+
- DAISY Pipeline 2
- Dolphin EasyReader and/or Thorium Reader
- ffmpeg (required by `pydub` when joining MP3 chunks)
- Azure Speech Service account if using the included TTS script

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 2. Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## 3. Add the book source locally

Do **not** commit copyrighted book text or generated audiobook files to a public repository unless you have permission.

Put the selected source at:

```text
data/source/book.docx
```

Fill metadata for the exact Vietnamese edition in:

```text
config/book.yaml
```

Check it:

```bash
python -m daisy_book.check_metadata
```

## 4. Prepare text

```bash
python -m daisy_book.prepare_book --source data/source/book.docx
```

Outputs:

```text
build/clean/book_clean.docx
build/text/manifest.json
build/text/chapter_*.txt
```

The script is intentionally conservative and targets **text-first DOCX**. If the source contains complex tables, images or layout, handle those accessibility requirements explicitly instead of trusting this script to preserve them.

## 5. Chapter 1 TTS dry-run

Before spending API quota:

```bash
python -m daisy_book.generate_audio \
  --chapter build/text/<chapter-01-file>.txt \
  --dry-run
```

Review `config/pronunciation.yaml`. Pronunciation replacements are used only for speech synthesis and must not replace the displayed DTBook text.

## 6. Azure TTS

```bash
cp .env.example .env
```

Set:

```text
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=southeastasia
AZURE_SPEECH_VOICE=vi-VN-HoaiMyNeural
```

Generate one chapter:

```bash
python -m daisy_book.generate_audio \
  --chapter build/text/<chapter-01-file>.txt
```

After Chapter 1 passes QA:

```bash
python -m daisy_book.generate_audio --all
```

## 7. DAISY Pipeline 2

Recommended workflow:

1. Use **Word to DTBook** with `build/clean/book_clean.docx`.
2. Inspect/validate the generated DTBook XML.
3. Build the DAISY 3 package with text-to-speech/audio synchronization as required by the project workflow.
4. Put the final package contents in `build/daisy/`.

Expected final resource types:

```text
*.xml
*.smil
*.ncx
*.opf
*.mp3
```

## 8. Validate

```bash
python -m daisy_book.validate_daisy --input build/daisy
```

The validator checks required resource types, XML parsing, and common local `src`/`href` references. It does **not** replace real playback/accessibility QA.

Import the OPF into Dolphin EasyReader or Thorium and verify chapter navigation and synchronization.

## 9. Package submission

```bash
python -m daisy_book.package_daisy --input build/daisy
```

Outputs:

```text
output/Tam_ly_hoc_ve_tien_DAISY3.zip
output/Tam_ly_hoc_ve_tien_DAISY3_sha256sums.txt
```

## Team workflow

Suggested ownership:

- Source + metadata + text cleaning
- TTS + pronunciation + listening QA
- DTBook/SMIL/NCX/OPF + DAISY Pipeline 2
- Reader QA + packaging + report

See [`docs/workflow.md`](docs/workflow.md) and [`docs/qa_checklist.md`](docs/qa_checklist.md).
