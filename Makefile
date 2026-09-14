PYTHON ?= python
SOURCE ?= data/source/tam-ly-hoc-ve-tien.epub

.PHONY: setup metadata extract prepare-tts tts-audit tts tts-dry-run build-daisy validate package test tts-all full-book-dry-run build-daisy-all validate-all package-all full-book

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev]'

metadata:
	$(PYTHON) -m daisy_book.check_metadata --config config/book.yaml

extract:
	$(PYTHON) -m daisy_book.extract $(SOURCE) --output build/structured

prepare-tts:
	$(PYTHON) -m daisy_book.prepare_tts --book build/structured/book.json --output build/tts/manifest.json

tts-audit: prepare-tts
	$(PYTHON) -m daisy_book.audit_tts --manifest build/tts/manifest.json --output build/tts/audit.json

tts-dry-run: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --section chapter_01 --output-dir build/audio --dry-run

tts: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --section chapter_01 --output-dir build/audio

build-daisy:
	$(PYTHON) -m daisy_book.build_daisy \
		--book build/structured/book.json \
		--manifest build/tts/manifest.json \
		--audio-dir build/audio \
		--output build/daisy \
		--section chapter_01

validate:
	$(PYTHON) -m daisy_book.validate_daisy --input build/daisy

package:
	$(PYTHON) -m daisy_book.package_daisy --input build/daisy

## Full-book targets (all sections)
tts-all: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --all --output-dir build/audio

full-book-dry-run: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --all --output-dir build/audio --dry-run

build-daisy-all: tts-all
	$(PYTHON) -m daisy_book.build_daisy \
		--book build/structured/book.json \
		--manifest build/tts/manifest.json \
		--audio-dir build/audio \
		--output build/daisy \
		--all

validate-all: build-daisy-all
	$(PYTHON) -m daisy_book.validate_daisy --input build/daisy

package-all: validate-all
	$(PYTHON) -m daisy_book.package_daisy --input build/daisy --name Tam_ly_hoc_ve_tien_DAISY3

full-book: extract prepare-tts tts-audit tts-all build-daisy-all validate-all package-all

test:
	pytest -q
