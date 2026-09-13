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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DAISY project metadata.")
    parser.add_argument("--config", default="config/book.yaml")
    args = parser.parse_args()

    book = load_book_config(args.config)
    missing = [key for key in REQUIRED if not str(book.get(key, "")).strip()]

    if missing:
        print("Missing required metadata:")
        for key in missing:
            print(f"  - {key}")
        return 1

    print("Required metadata: OK")
    for key in OPTIONAL:
        if book.get(key) is None:
            print(f"Optional metadata is unset: {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
