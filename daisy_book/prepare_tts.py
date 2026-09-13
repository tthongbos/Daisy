from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_pronunciation_map
from .text import apply_pronunciation_map, normalize_text


def prepare_manifest(book: dict[str, Any], pronunciation: dict[str, str]) -> dict[str, Any]:
    metadata = book.get("metadata")
    sections = book.get("sections")
    if not isinstance(metadata, dict):
        raise ValueError("book.json metadata must be an object")
    if not isinstance(sections, list):
        raise ValueError("book.json sections must be a list")

    prepared_sections: list[dict[str, Any]] = []
    section_ids: set[str] = set()
    paragraph_ids: set[str] = set()

    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Every section must be an object")
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id.strip():
            raise ValueError("Every section must have a non-empty id")
        if section_id in section_ids:
            raise ValueError(f"Duplicate section id: {section_id}")
        section_ids.add(section_id)

        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError(f"Section {section_id} blocks must be a list")

        paragraphs: list[dict[str, str]] = []
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError(f"Section {section_id} contains a non-object block")
            if block.get("type") == "image":
                continue
            if block.get("type") != "paragraph":
                continue

            paragraph_id = block.get("id")
            display_text = block.get("display_text")
            if not isinstance(paragraph_id, str) or not paragraph_id.strip():
                raise ValueError(f"Paragraph in section {section_id} has no non-empty id")
            if paragraph_id in paragraph_ids:
                raise ValueError(f"Duplicate paragraph id: {paragraph_id}")
            if not isinstance(display_text, str) or not normalize_text(display_text):
                raise ValueError(f"Paragraph {paragraph_id} has no non-empty display_text")
            paragraph_ids.add(paragraph_id)

            normalized = normalize_text(display_text)
            tts_text = normalize_text(apply_pronunciation_map(normalized, pronunciation))
            if not tts_text:
                raise ValueError(f"Paragraph {paragraph_id} has empty tts_text after pronunciation rules")
            paragraphs.append(
                {
                    "id": paragraph_id,
                    "display_text": display_text,
                    "tts_text": tts_text,
                }
            )

        prepared_section = {
            key: section[key]
            for key in ("id", "type", "number", "title", "subtitle")
            if key in section
        }
        prepared_section["paragraphs"] = paragraphs
        prepared_sections.append(prepared_section)

    return {"metadata": metadata, "sections": prepared_sections}


def prepare_tts(book_path: Path, output_path: Path, pronunciation_path: Path) -> dict[str, Any]:
    try:
        book = json.loads(book_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {book_path}: {exc}") from exc
    if not isinstance(book, dict):
        raise ValueError("book.json root must be an object")

    manifest = prepare_manifest(book, load_pronunciation_map(pronunciation_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare paragraph text for TTS from structured book JSON.")
    parser.add_argument("--book", default="build/structured/book.json", type=Path)
    parser.add_argument("--output", default="build/tts/manifest.json", type=Path)
    parser.add_argument("--pronunciation", default="config/pronunciation.yaml", type=Path)
    args = parser.parse_args()

    manifest = prepare_tts(args.book, args.output, args.pronunciation)
    paragraph_count = sum(len(section["paragraphs"]) for section in manifest["sections"])
    print(f"Wrote {args.output}: {len(manifest['sections'])} section(s), {paragraph_count} paragraph(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())