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

The manifest orders heading, subtitle, and paragraph synchronization units while preserving existing paragraph IDs. `display_text` is the exact accessible book text and is never changed by speech normalization. Deterministic number, punctuation, and heading transforms plus project-specific substitutions from `config/pronunciation.yaml` are applied only to `tts_text`. Image blocks are not included in the TTS manifest.

Audit the prepared text for unresolved acronyms, ambiguous slash expressions, suspicious source text, and other tokens that need listening or editorial review:

```bash
make tts-audit
```

The command is network-free and writes `build/tts/audit.json`. Audit findings do not silently correct the source text.

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

Use `--section introduction` to select the introduction. Existing valid paragraph segments are reused only when their sidecar signature matches the current `tts_text`, voice, rate, and request-size setting; add `--force` to regenerate every paragraph in the selected section.

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

The QA sequence is:

```text
extract -> prepare-tts -> tts-audit -> tts-dry-run -> manual review -> real TTS
```

## Build the DAISY 3 sample

After Chapter 1 audio has been generated and reviewed, build the DAISY structure entirely from local artifacts:

```bash
make build-daisy
make validate
make package
```

The complete workflow remains explicit:

```bash
make tts
make build-daisy
make validate
make package
```

`make tts` is the only step in this sequence that calls Azure. It creates the Chapter 1 MP3 and timing data. `make build-daisy` does not synthesize or transcode audio; it validates the structured book, TTS manifest, timing data, and MP3, then creates the synchronization, navigation, and package documents.

The timing file is the bridge from synthesized audio to DAISY synchronization:

```text
build/audio/chapter_01/chapter_01_timing.json
   -> build/daisy/chapter_01.smil
```

The M3 output is one DAISY book containing the Chapter 1 sample:

```text
build/daisy/
   book.xml
   book.opf
   book.ncx
   chapter_01.smil
   chapter_01.mp3
```

The DTBook uses source `display_text`; speech-only `tts_text` remains in the TTS pipeline. The MP3 is copied byte-for-byte into the DAISY output. Generated files under `build/` and packaged files under `output/` are local artifacts and must not be committed.

Manual playback QA remains required. Open `build/daisy/book.opf` in Dolphin EasyReader and verify navigation, playback, highlighting, next/previous navigation, and seeking. DAISY Pipeline 2 conformance testing is a later manual QA step.

## Milestone scope

- EPUB is the only supported source format.
- The source contains one introduction and 20 numbered chapters.
- Normalization is deterministic and conservative. It does not guess OCR or text corrections.
- OCR/text correction is a later stage.
- M2 covers the TTS manifest, one selected section's spoken-unit audio, chapter MP3 assembly, and unit timing.
- M3 builds one DAISY 3 full-text/full-audio Chapter 1 sample from existing local TTS artifacts.
- Introduction, Chapters 2-20, and full-book TTS remain deferred.

Run the tests with:

```bash
pytest -q
```

All generated files under `build/` and `output/`, local secrets in `.env`, and copyrighted files under `data/source/` are ignored by Git.