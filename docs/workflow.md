# Workflow

## Current milestone: paragraph-level TTS

1. Keep the legally obtained source at `data/source/tam-ly-hoc-ve-tien.epub`.
2. Set known final metadata in `config/book.yaml`; leave unknown publication fields as `null`.
3. Install the project and development dependencies.
4. Extract the EPUB to structured JSON.

```bash
pip install -e '.[dev]'
python -m daisy_book.extract \
    data/source/tam-ly-hoc-ve-tien.epub \
    --output build/structured
pytest -q
```

Review `build/structured/book.json` for:

- one introduction followed by chapters 1 through 20;
- correct titles, subtitles, and paragraph boundaries;
- retained image references and images marked `needs_alt_review`;
- source text defects that need a later, deliberate correction pass.

Generated `build/` content and the copyrighted EPUB remain local and must not be committed.

Prepare the TTS manifest and inspect Chapter 1 before synthesis:

```bash
python -m daisy_book.prepare_tts \
    --book build/structured/book.json \
    --output build/tts/manifest.json
python -m daisy_book.generate_audio \
    --manifest build/tts/manifest.json \
    --section chapter_01 \
    --output-dir build/audio \
    --dry-run
```

The manifest preserves paragraph IDs and exact display text while ordering heading, subtitle, and paragraph units. Pronunciation substitutions affect only `tts_text`. Real synthesis writes unit segments, an assembled section MP3, and unit timing JSON under `build/audio/<section-id>/`.

## Deferred work

OCR/text correction, full-book TTS, DTBook generation, SMIL synchronization, DAISY navigation/package generation, playback QA, and final packaging are separate later milestones.