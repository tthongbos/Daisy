PYTHON ?= python
SOURCE ?= data/source/tam-ly-hoc-ve-tien.epub

.PHONY: setup metadata extract prepare-tts tts tts-dry-run validate package test

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev]'

metadata:
	$(PYTHON) -m daisy_book.check_metadata --config config/book.yaml

extract:
	$(PYTHON) -m daisy_book.extract $(SOURCE) --output build/structured

prepare-tts:
	$(PYTHON) -m daisy_book.prepare_tts --book build/structured/book.json --output build/tts/manifest.json

tts-dry-run: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --section chapter_01 --output-dir build/audio --dry-run

tts: prepare-tts
	$(PYTHON) -m daisy_book.generate_audio --manifest build/tts/manifest.json --section chapter_01 --output-dir build/audio

validate:
	$(PYTHON) -m daisy_book.validate_daisy --input build/daisy

package:
	$(PYTHON) -m daisy_book.package_daisy --input build/daisy

test:
	pytest -q
