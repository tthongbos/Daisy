PYTHON ?= python
SOURCE ?= data/source/book.docx

.PHONY: setup metadata prepare tts validate package test

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev]'

metadata:
	$(PYTHON) -m daisy_book.check_metadata --config config/book.yaml

prepare:
	$(PYTHON) -m daisy_book.prepare_book --source $(SOURCE)

tts:
	$(PYTHON) -m daisy_book.generate_audio --all

validate:
	$(PYTHON) -m daisy_book.validate_daisy --input build/daisy

package:
	$(PYTHON) -m daisy_book.package_daisy --input build/daisy

test:
	pytest -q
