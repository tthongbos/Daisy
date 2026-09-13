PYTHON ?= python
SOURCE ?= data/source/tam-ly-hoc-ve-tien.epub

.PHONY: setup metadata extract tts validate package test

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev]'

metadata:
	$(PYTHON) -m daisy_book.check_metadata --config config/book.yaml

extract:
	$(PYTHON) -m daisy_book.extract $(SOURCE) --output build/structured

tts:
	$(PYTHON) -m daisy_book.generate_audio --all

validate:
	$(PYTHON) -m daisy_book.validate_daisy --input build/daisy

package:
	$(PYTHON) -m daisy_book.package_daisy --input build/daisy

test:
	pytest -q
