# Workflow

## Phase 0 - Source and metadata

1. Register the selected Vietnamese edition so the team does not duplicate another group.
2. Confirm title, author, publisher, publication date, ISBN and source URL.
3. Put the legally obtained source at `data/source/book.docx` locally. This directory is intentionally ignored by Git.
4. Fill `config/book.yaml`.

## Phase 1 - MVP: one chapter end-to-end

Do not synthesize the whole book first. Prove the complete workflow with Chapter 1.

```bash
python -m daisy_book.check_metadata
python -m daisy_book.prepare_book --source data/source/book.docx
python -m daisy_book.generate_audio --chapter build/text/<chapter-01>.txt --dry-run
```

Review `build/clean/book_clean.docx` and the generated Chapter 1 text manually.

## Phase 2 - DTBook

Use DAISY Pipeline 2:

1. Word to DTBook
2. Input: `build/clean/book_clean.docx`
3. Verify the generated DTBook XML is well-formed.
4. Check chapter headings and navigation anchors.

Keep the Pipeline 2 output in `build/dtbook/` or another local working directory. Generated data does not belong in Git unless the course explicitly requires it.

## Phase 3 - TTS

Copy `.env.example` to `.env`, fill Azure credentials, and generate Chapter 1.

```bash
python -m daisy_book.generate_audio --chapter build/text/<chapter-01>.txt
```

After Chapter 1 passes listening QA, synthesize all chapters:

```bash
python -m daisy_book.generate_audio --all
```

The pronunciation map changes only the speech input, not the displayed book text.

## Phase 4 - DAISY 3

Use DAISY Pipeline 2 to generate the final DAISY 3 package. The final `build/daisy/` folder should contain at least:

- DTBook/XML content
- SMIL synchronization files
- NCX navigation
- OPF package metadata
- MP3 audio

Prefer chapter-sized audio over one very large MP3.

## Phase 5 - Validate and accessible playback QA

```bash
python -m daisy_book.validate_daisy --input build/daisy
```

Then import the OPF into Dolphin EasyReader and/or Thorium Reader. Verify navigation without relying on sight alone where practical: chapter navigation, play/pause, next/previous unit, restart position and text/audio synchronization.

## Phase 6 - Package

```bash
python -m daisy_book.package_daisy --input build/daisy
```

This produces a ZIP and SHA-256 checksum under `output/`.
