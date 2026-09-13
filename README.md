# Tâm lý học về tiền - structured EPUB and TTS workflow

This repository extracts and normalizes the Vietnamese EPUB of *Tâm lý học về tiền* into structured JSON, then prepares paragraph-level text and audio for one selected section.

The canonical source is:

```text
data/source/tam-ly-hoc-ve-tien.epub
```

The EPUB is copyrighted local source material and is ignored by Git. The extractor reads the OPF manifest and spine to determine document order; it does not rely on split HTML filenames or the incomplete NCX navigation.

## Current workflow

1. Place the EPUB at `data/source/tam-ly-hoc-ve-tien.epub`.
2. Install the project:

   ```bash
   sudo apt-get install ffmpeg
   pip install -e '.[dev]'
   ```

3. Extract the structured book:

   ```bash
   python -m daisy_book.extract \
       data/source/tam-ly-hoc-ve-tien.epub \
       --output build/structured
   ```

4. Inspect `build/structured/book.json` and `build/structured/metadata.json`.

The extractor uses final metadata overrides from `config/book.yaml`, detects the introduction and exactly 20 numbered chapters from HTML paragraph structure, preserves paragraph boundaries and image references, and flags weak image alt text for manual review.

## Prepare TTS

The structured book remains the source of truth. Create the TTS manifest without changing any `display_text` values:

```bash
python -m daisy_book.prepare_tts \
   --book build/structured/book.json \
   --output build/tts/manifest.json
```

The manifest orders heading, subtitle, and paragraph synchronization units while preserving existing paragraph IDs. Project-specific substitutions from `config/pronunciation.yaml` are applied only to each unit's `tts_text`. Image blocks are not included in the TTS manifest.

Validate and inspect the Chapter 1 request plan without Azure credentials or network calls:

```bash
python -m daisy_book.generate_audio \
   --manifest build/tts/manifest.json \
   --section chapter_01 \
   --output-dir build/audio \
   --dry-run
```

After setting `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and optionally `AZURE_SPEECH_VOICE` in `.env`, generate Chapter 1:

```bash
python -m daisy_book.generate_audio \
   --manifest build/tts/manifest.json \
   --section chapter_01 \
   --output-dir build/audio
```

Use `--section introduction` to select the introduction. Existing non-empty, valid paragraph segments are reused; add `--force` to regenerate every paragraph in the selected section.

Expected Chapter 1 outputs:

```text
build/audio/chapter_01/
   segments/
      chapter_01_p0001.mp3
      chapter_01_p0002.mp3
      ...
   chapter_01.mp3
   chapter_01_timing.json
```

`chapter_01_timing.json` records integer unit clip boundaries on the assembled chapter timeline. Full-book synthesis is intentionally deferred until Chapter 1 audio and text quality pass manual QA.

## Milestone scope

- EPUB is the only supported source format.
- The source contains one introduction and 20 numbered chapters.
- Normalization is deterministic and conservative. It does not guess OCR or text corrections.
- OCR/text correction is a later stage.
- M2 covers the TTS manifest, one selected section's spoken-unit audio, chapter MP3 assembly, and unit timing.
- DTBook, SMIL, NCX, OPF, full-book TTS, and DAISY package generation remain deferred.

Run the tests with:

```bash
pytest -q
```

All generated files under `build/` and `output/`, local secrets in `.env`, and copyrighted files under `data/source/` are ignored by Git.