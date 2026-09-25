from __future__ import annotations

import argparse
import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from .config import load_book_config
from .epub import EpubBook, EpubMetadata, load_epub
from .normalize import normalize_document, normalize_text, paragraph_text


CHAPTER_SUBTITLE_CLASSES = {"block_2", "block_10"}


@dataclass(frozen=True)
class ImageReference:
    src: str
    alt: str


@dataclass(frozen=True)
class ParagraphRecord:
    classes: tuple[str, ...]
    text: str
    images: tuple[ImageReference, ...]


@dataclass(frozen=True)
class ChapterMarker:
    number: int
    marker_index: int
    title_index: int
    subtitle_index: int


def _resolve_image_path(document_path: str, src: str) -> str:
    clean_src = unquote(src.split("#", 1)[0].split("?", 1)[0])
    path = posixpath.normpath(posixpath.join(posixpath.dirname(document_path), clean_src))
    if path.startswith("../") or path.startswith("/"):
        raise ValueError(f"Image resolves outside the EPUB archive: {src}")
    return path


def parse_paragraphs(book: EpubBook) -> list[ParagraphRecord]:
    records: list[ParagraphRecord] = []
    for document in book.documents:
        root = normalize_document(document.content)
        for paragraph in root.xpath("//p"):
            images = tuple(
                ImageReference(
                    src=_resolve_image_path(document.href, image.get("src", "")),
                    alt=normalize_text(image.get("alt", "")),
                )
                for image in paragraph.xpath(".//img[@src]")
            )
            records.append(
                ParagraphRecord(
                    classes=tuple((paragraph.get("class") or "").split()),
                    text=paragraph_text(paragraph),
                    images=images,
                )
            )
    return records


def _next_text_record(records: list[ParagraphRecord], start: int) -> int | None:
    for index in range(start, len(records)):
        if records[index].text:
            return index
    return None


def detect_chapter_markers(records: list[ParagraphRecord]) -> list[ChapterMarker]:
    markers: list[ChapterMarker] = []
    for index, record in enumerate(records):
        if "block_" not in record.classes or not record.text.isdigit():
            continue
        number = int(record.text)
        if not 1 <= number <= 20:
            continue

        title_index = _next_text_record(records, index + 1)
        subtitle_index = _next_text_record(records, (title_index or index) + 1)
        if title_index is None or subtitle_index is None:
            continue
        if "block_" not in records[title_index].classes:
            continue
        if CHAPTER_SUBTITLE_CLASSES.isdisjoint(records[subtitle_index].classes):
            continue
        markers.append(ChapterMarker(number, index, title_index, subtitle_index))

    if len(markers) != 20:
        raise ValueError(f"Expected 20 numbered chapters, found {len(markers)}.")
    numbers = [marker.number for marker in markers]
    expected = list(range(1, 21))
    if numbers != expected:
        raise ValueError(f"Expected chapters 1..20 in order, found: {numbers}.")
    return markers


def detect_introduction(records: list[ParagraphRecord], before_index: int) -> tuple[int, int]:
    for index, record in enumerate(records[:before_index]):
        if "block_" not in record.classes or record.text.casefold() != "giới thiệu".casefold():
            continue
        subtitle_index = _next_text_record(records, index + 1)
        if subtitle_index is not None and "block_2" in records[subtitle_index].classes:
            return index, subtitle_index
    raise ValueError("Expected an introduction heading followed by a block_2 subtitle, found none.")


def image_needs_alt_review(alt: str) -> bool:
    value = normalize_text(alt)
    if value.casefold() in {"", "image", "undefined"}:
        return True
    return bool(re.fullmatch(r"[^\s/]+\.(?:gif|jpe?g|png|webp)", value, re.IGNORECASE))


def _image_block(image: ImageReference) -> dict[str, object]:
    return {
        "type": "image",
        "src": image.src,
        "alt": image.alt,
        "needs_alt_review": image_needs_alt_review(image.alt),
    }


def _section_blocks(
    section_id: str,
    records: list[ParagraphRecord],
    heading_start: int,
    content_start: int,
    end: int,
) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    paragraph_number = 0

    for record in records[heading_start:content_start]:
        blocks.extend(_image_block(image) for image in record.images)

    for record in records[content_start:end]:
        blocks.extend(_image_block(image) for image in record.images)
        if record.text:
            paragraph_number += 1
            blocks.append(
                {
                    "id": f"{section_id}_p{paragraph_number:04d}",
                    "type": "paragraph",
                    "display_text": record.text,
                }
            )
    return blocks


def normalized_metadata(source: EpubMetadata, overrides: dict[str, object]) -> dict[str, object]:
    def preferred(key: str, fallback: str | None) -> str | None:
        value = overrides.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)
        return fallback

    def preferred_nested(mapping: dict[str, object], key: str, fallback: str | None) -> str | None:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)
        return fallback

    metadata_overrides = overrides if isinstance(overrides, dict) else {}
    source_overrides = metadata_overrides.get("source")
    daisy_overrides = metadata_overrides.get("daisy")
    source_override_dict = source_overrides if isinstance(source_overrides, dict) else {}
    daisy_override_dict = daisy_overrides if isinstance(daisy_overrides, dict) else {}

    if not source_override_dict:
        source_override_dict = {
            key: metadata_overrides[key]
            for key in ("publisher", "date", "isbn", "url", "edition", "rights")
            if key in metadata_overrides
        }

    source_isbn = preferred_nested(source_override_dict, "isbn", None)
    if source_isbn is None:
        for identifier in source.identifiers:
            normalized = normalize_isbn(identifier)
            if normalized is not None:
                source_isbn = identifier.strip()
                break
    if source_isbn is None and "isbn" in metadata_overrides and isinstance(metadata_overrides["isbn"], str):
        source_isbn = str(metadata_overrides["isbn"]).strip()

    source_date = preferred_nested(source_override_dict, "date", source.date)
    source_publisher = preferred_nested(source_override_dict, "publisher", source.publisher)
    source_rights = preferred_nested(source_override_dict, "rights", source.rights)
    source_url = preferred_nested(source_override_dict, "url", None)
    source_edition = preferred_nested(source_override_dict, "edition", None)

    metadata: dict[str, object] = {
        "title": preferred("title", source.title),
        "author": preferred("creator", source.authors[0] if source.authors else None),
        "translator": preferred("translator", source.translators[0] if source.translators else None),
        "language": preferred("language", source.language),
        "subject": preferred("subject", source.subject),
        "description": preferred("description", source.description),
        "source": {
            "publisher": source_publisher,
            "date": source_date,
            "isbn": source_isbn,
            "url": source_url,
            "edition": source_edition,
            "rights": source_rights,
        },
        "daisy": {
            "producer": preferred_nested(daisy_override_dict, "producer", None),
            "generator": preferred_nested(daisy_override_dict, "generator", None),
        },
    }
    return metadata


def build_structured_book(book: EpubBook, overrides: dict[str, object]) -> dict[str, object]:
    records = parse_paragraphs(book)
    markers = detect_chapter_markers(records)
    introduction_index, introduction_subtitle_index = detect_introduction(
        records, markers[0].marker_index
    )

    sections: list[dict[str, object]] = [
        {
            "id": "introduction",
            "type": "introduction",
            "title": records[introduction_index].text,
            "subtitle": records[introduction_subtitle_index].text,
            "blocks": _section_blocks(
                "introduction",
                records,
                0,
                introduction_subtitle_index + 1,
                markers[0].marker_index,
            ),
        }
    ]

    for marker_index, marker in enumerate(markers):
        section_id = f"chapter_{marker.number:02d}"
        end = (
            markers[marker_index + 1].marker_index
            if marker_index + 1 < len(markers)
            else len(records)
        )
        sections.append(
            {
                "id": section_id,
                "type": "chapter",
                "number": marker.number,
                "title": records[marker.title_index].text,
                "subtitle": records[marker.subtitle_index].text,
                "blocks": _section_blocks(
                    section_id,
                    records,
                    marker.marker_index,
                    marker.subtitle_index + 1,
                    end,
                ),
            }
        )

    return {"metadata": normalized_metadata(book.metadata, overrides), "sections": sections}


def write_structured_book(
    source: Path,
    output_dir: Path,
    config_path: Path,
) -> tuple[EpubBook, dict[str, object]]:
    epub = load_epub(source)
    structured = build_structured_book(epub, load_book_config(config_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.json"
    book_path = output_dir / "book.json"
    metadata_path.write_text(
        json.dumps(structured["metadata"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    book_path.write_text(
        json.dumps(structured, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return epub, structured


def _summary(epub: EpubBook, structured: dict[str, object], output_dir: Path) -> str:
    metadata = structured["metadata"]
    sections = structured["sections"]
    assert isinstance(metadata, dict)
    assert isinstance(sections, list)
    blocks = [block for section in sections for block in section["blocks"]]
    paragraphs = sum(block["type"] == "paragraph" for block in blocks)
    images = [block for block in blocks if block["type"] == "image"]
    alt_reviews = sum(bool(block["needs_alt_review"]) for block in images)
    chapters = sum(section["type"] == "chapter" for section in sections)
    introduction = any(section["type"] == "introduction" for section in sections)
    return "\n".join(
        [
            f"Book: {metadata.get('title') or ''}",
            f"Author: {metadata.get('author') or ''}",
            f"Translator: {metadata.get('translator') or ''}",
            f"Language: {metadata.get('language') or ''}",
            "",
            f"Spine documents: {len(epub.documents)}",
            f"Introduction: {'found' if introduction else 'not found'}",
            f"Numbered chapters: {chapters}",
            f"Paragraphs: {paragraphs}",
            f"Images: {len(images)}",
            f"Images requiring alt review: {alt_reviews}",
            "",
            "Generated:",
            f"  {output_dir / 'metadata.json'}",
            f"  {output_dir / 'book.json'}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a structured book from an EPUB source.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("build/structured"))
    parser.add_argument("--config", type=Path, default=Path("config/book.yaml"))
    args = parser.parse_args(argv)

    epub, structured = write_structured_book(args.source, args.output, args.config)
    print(_summary(epub, structured, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())