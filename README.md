# Tâm lý học về tiền - EPUB extraction

This repository currently extracts and normalizes the Vietnamese EPUB of *Tâm lý học về tiền* into a structured, reviewable JSON representation.

The canonical source is:

```text
data/source/tam-ly-hoc-ve-tien.epub
```

The EPUB is copyrighted local source material and is ignored by Git. The extractor reads the OPF manifest and spine to determine document order; it does not rely on split HTML filenames or the incomplete NCX navigation.

## Current workflow

1. Place the EPUB at `data/source/tam-ly-hoc-ve-tien.epub`.
2. Install the project:

   ```bash
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

## Milestone scope

- EPUB is the only supported source format.
- The source contains one introduction and 20 numbered chapters.
- Normalization is deterministic and conservative. It does not guess OCR or text corrections.
- OCR/text correction is a later stage.
- TTS, DTBook, SMIL, NCX, OPF, and DAISY package generation are not part of this milestone.

Run the tests with:

```bash
pytest -q
```

All generated files under `build/` and `output/`, local secrets in `.env`, and copyrighted files under `data/source/` are ignored by Git.