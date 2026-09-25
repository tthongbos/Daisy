from __future__ import annotations

import argparse

from .config import load_book_config


REQUIRED = [
    "title",
    "creator",
    "subject",
    "language",
]
OPTIONAL = ["translator", "publisher", "date", "isbn", "description"]


def _value(mapping: dict, *path: str):
    current: object = mapping
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if isinstance(current, str):
        return current.strip() or None
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DAISY project metadata.")
    parser.add_argument("--config", default="config/book.yaml")
    args = parser.parse_args()

    book = load_book_config(args.config)
    required = [
        ("title", _value(book, "title")),
        ("creator", _value(book, "creator") or _value(book, "author")),
        ("subject", _value(book, "subject")),
        ("language", _value(book, "language")),
    ]
    missing = [key for key, value in required if not value]

    if missing:
        print("Missing required metadata:")
        for key in missing:
            print(f"  - {key}")
        return 1

    source = book.get("source") if isinstance(book.get("source"), dict) else {}
    source_date = _value(source, "date")
    if source_date is not None:
        if not __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}", source_date):
            print(f"Invalid source metadata date: {source_date}")
            return 1
    source_isbn = _value(source, "isbn")
    if source_isbn is not None:
        from daisy_book.epub import normalize_isbn
        normalized = normalize_isbn(source_isbn)
        if normalized is None:
            print(f"Invalid source ISBN: {source_isbn}")
            return 1
        if normalized != source_isbn.replace("-", "").replace(" ", "").replace("urn:isbn:", ""):
            print(f"Normalized source ISBN: {normalized}")

    print("Required metadata: OK")
    for key in OPTIONAL:
        if book.get(key) is None and not (isinstance(source, dict) and source.get(key) is not None):
            print(f"Optional metadata is unset: {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
