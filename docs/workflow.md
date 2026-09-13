# Workflow

## Current milestone: EPUB extraction

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

## Deferred work

OCR/text correction, TTS, DTBook generation, SMIL synchronization, DAISY navigation/package generation, playback QA, and final packaging are separate later milestones.