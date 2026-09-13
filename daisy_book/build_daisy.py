from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lxml import etree

from .dtbook import build_dtbook
from .navigation import build_ncx
from .opf import build_opf, format_duration
from .smil import build_smil
from .validate_daisy import validate_daisy


DTBOOK_DOCTYPE = (
    '<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" '
    '"http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">'
)
NCX_DOCTYPE = (
    '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
    '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
)
SMIL_DOCTYPE = (
    '<!DOCTYPE smil PUBLIC "-//NISO//DTD dtbsmil 2005-2//EN" '
    '"http://www.daisy.org/z3986/2005/dtbsmil-2005-2.dtd">'
)
OPF_DOCTYPE = (
    '<!DOCTYPE package PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.2 Package//EN" '
    '"http://openebook.org/dtds/oeb-1.2/oebpkg12.dtd">'
)


@dataclass(frozen=True)
class BuildResult:
    section_id: str
    unit_count: int
    duration_ms: int
    uid: str
    output_dir: Path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object: {path}")
    return value


def _selected_section(source: dict[str, Any], section_id: str, label: str) -> dict[str, Any]:
    sections = source.get("sections")
    if not isinstance(sections, list):
        raise ValueError(f"{label} sections must be a list")
    matches = [
        section
        for section in sections
        if isinstance(section, dict) and section.get("id") == section_id
    ]
    if not matches:
        raise ValueError(f"Section {section_id} not found in {label}")
    if len(matches) > 1:
        raise ValueError(f"Duplicate section id in {label}: {section_id}")
    return matches[0]


def _expected_units(section: dict[str, Any]) -> list[dict[str, str]]:
    section_id = section.get("id")
    if not isinstance(section_id, str) or not section_id:
        raise ValueError("Selected book section has no non-empty id")
    units: list[dict[str, str]] = []

    for key, unit_type in (("title", "heading"), ("subtitle", "subtitle")):
        value = section.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Section {section_id} {key} must be non-empty text")
        units.append(
            {
                "id": f"{section_id}_{key}",
                "type": unit_type,
                "display_text": value,
            }
        )

    blocks = section.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError(f"Section {section_id} blocks must be a list")
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError(f"Section {section_id} contains a non-object block")
        block_type = block.get("type")
        if block_type == "image":
            continue
        if block_type != "paragraph":
            raise ValueError(f"Section {section_id} contains unsupported block type: {block_type}")
        unit_id = block.get("id")
        display_text = block.get("display_text")
        if not isinstance(unit_id, str) or not unit_id.strip():
            raise ValueError(f"Section {section_id} contains a paragraph with no non-empty id")
        if not isinstance(display_text, str) or not display_text.strip():
            raise ValueError(f"Paragraph {unit_id} has no non-empty display_text")
        units.append({"id": unit_id, "type": "paragraph", "display_text": display_text})

    ids = [unit["id"] for unit in units]
    duplicate = next((unit_id for unit_id in ids if ids.count(unit_id) > 1), None)
    if duplicate:
        raise ValueError(f"Duplicate source unit id: {duplicate}")
    if not units:
        raise ValueError(f"Section {section_id} contains no synchronization units")
    return units


def _require_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def validate_source_relationships(
    book: dict[str, Any],
    manifest: dict[str, Any],
    timing: dict[str, Any],
    section_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    section = _selected_section(book, section_id, "book.json")
    manifest_section = _selected_section(manifest, section_id, "manifest.json")
    expected = _expected_units(section)
    manifest_units = manifest_section.get("units")
    if not isinstance(manifest_units, list):
        raise ValueError(f"Manifest section {section_id} units must be a list")
    if len(manifest_units) != len(expected):
        raise ValueError(
            f"Manifest unit count mismatch for {section_id}: expected {len(expected)}, found {len(manifest_units)}"
        )

    manifest_ids: set[str] = set()
    for index in range(len(expected)):
        unit = manifest_units[index]
        if not isinstance(unit, dict):
            raise ValueError(f"Manifest unit at index {index} must be an object")
        unit_id = unit.get("id")
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError(f"Manifest unit at index {index} has no non-empty id")
        if unit_id in manifest_ids:
            raise ValueError(f"Duplicate manifest unit id: {unit_id}")
        manifest_ids.add(unit_id)
        expected_unit = expected[index]
        if unit_id != expected_unit["id"]:
            raise ValueError(
                f"Manifest unit IDs/order mismatch at index {index}: expected {expected_unit['id']}, found {unit_id}"
            )
        if unit.get("type") != expected_unit["type"]:
            raise ValueError(f"Manifest unit type mismatch for {unit_id}")
        if unit.get("display_text") != expected_unit["display_text"]:
            raise ValueError(f"Manifest display_text mismatch for {unit_id}")

    if timing.get("section_id") != section_id:
        raise ValueError(
            f"Timing section_id mismatch: expected {section_id}, found {timing.get('section_id')}"
        )
    timing_units = timing.get("units")
    if not isinstance(timing_units, list):
        raise ValueError(f"Timing section {section_id} units must be a list")
    if len(timing_units) != len(manifest_units):
        raise ValueError(
            f"Timing unit count mismatch for {section_id}: expected {len(manifest_units)}, found {len(timing_units)}"
        )
    duration_ms = _require_integer(timing.get("duration_ms"), "Timing duration_ms")
    if duration_ms <= 0:
        raise ValueError("Timing duration_ms must be greater than zero")

    timing_ids: set[str] = set()
    previous_end = 0
    for index in range(len(manifest_units)):
        timing_unit = timing_units[index]
        if not isinstance(timing_unit, dict):
            raise ValueError(f"Timing unit at index {index} must be an object")
        unit_id = timing_unit.get("id")
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError(f"Timing unit at index {index} has no non-empty id")
        if unit_id in timing_ids:
            raise ValueError(f"Duplicate timing unit id: {unit_id}")
        timing_ids.add(unit_id)
        manifest_unit = manifest_units[index]
        if unit_id != manifest_unit["id"]:
            raise ValueError(
                f"Timing unit IDs/order mismatch at index {index}: expected {manifest_unit['id']}, found {unit_id}"
            )
        if timing_unit.get("type") != manifest_unit.get("type"):
            raise ValueError(f"Timing unit type mismatch for {unit_id}")
        begin = _require_integer(timing_unit.get("clip_begin_ms"), f"{unit_id} clip_begin_ms")
        end = _require_integer(timing_unit.get("clip_end_ms"), f"{unit_id} clip_end_ms")
        if begin < 0:
            raise ValueError(f"{unit_id} clip_begin_ms must be non-negative")
        if end <= begin:
            raise ValueError(f"{unit_id} clip_end_ms must be greater than clip_begin_ms")
        if begin < previous_end:
            raise ValueError(f"Timing is not monotonic at {unit_id}")
        if end > duration_ms:
            raise ValueError(
                f"{unit_id} clip_end_ms {end} exceeds timing duration_ms {duration_ms}"
            )
        previous_end = end

    return section, manifest_units


def resolve_book_uid(metadata: dict[str, Any]) -> str:
    isbn = metadata.get("isbn")
    if isinstance(isbn, str) and isbn.strip():
        normalized = re.sub(r"[^0-9Xx]", "", re.sub(r"^urn:isbn:", "", isbn.strip(), flags=re.I))
        if normalized:
            return f"urn:isbn:{normalized.upper()}"

    stable_metadata: dict[str, str] = {}
    for key in ("title", "author", "language"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Book metadata requires a non-empty {key}")
        stable_metadata[key] = value.strip()
    seed = json.dumps(stable_metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, seed)}"


def _write_xml(path: Path, tree: etree._ElementTree, doctype: str) -> None:
    tree.write(
        str(path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
        doctype=doctype,
    )


def build_daisy(
    book_path: Path,
    manifest_path: Path,
    audio_dir: Path,
    output_dir: Path,
    section_id: str,
) -> BuildResult:
    if section_id != "chapter_01":
        raise ValueError("Milestone M3 supports only section chapter_01")
    book = _load_json(book_path, "structured book")
    manifest = _load_json(manifest_path, "TTS manifest")
    chapter_dir = audio_dir / section_id
    timing_path = chapter_dir / f"{section_id}_timing.json"
    audio_path = chapter_dir / f"{section_id}.mp3"
    timing = _load_json(timing_path, "chapter timing")
    if not audio_path.is_file():
        raise FileNotFoundError(f"Missing chapter audio: {audio_path}")
    section, units = validate_source_relationships(book, manifest, timing, section_id)
    metadata = book.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("book.json metadata must be an object")
    uid = resolve_book_uid(metadata)
    duration_ms = _require_integer(timing.get("duration_ms"), "Timing duration_ms")

    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{output_dir.name}.tmp"
    backup = parent / f".{output_dir.name}.backup"
    if staging.exists():
        shutil.rmtree(staging)
    if backup.exists():
        shutil.rmtree(backup)

    try:
        staging.mkdir()
        _write_xml(staging / "book.xml", build_dtbook(metadata, section, units, uid), DTBOOK_DOCTYPE)
        _write_xml(staging / f"{section_id}.smil", build_smil(section_id, timing, uid), SMIL_DOCTYPE)
        _write_xml(staging / "book.ncx", build_ncx(metadata, section, uid), NCX_DOCTYPE)
        _write_xml(staging / "book.opf", build_opf(metadata, section_id, uid, duration_ms), OPF_DOCTYPE)
        shutil.copyfile(audio_path, staging / f"{section_id}.mp3")

        errors, warnings = validate_daisy(staging)
        if errors:
            raise ValueError("Generated DAISY validation failed: " + "; ".join(errors))

        if output_dir.exists():
            if not output_dir.is_dir():
                raise ValueError(f"DAISY output exists and is not a directory: {output_dir}")
            output_dir.replace(backup)
        try:
            staging.replace(output_dir)
        except Exception:
            if backup.exists() and not output_dir.exists():
                backup.replace(output_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return BuildResult(section_id, len(units), duration_ms, uid, output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a DAISY 3 Chapter 1 sample from local artifacts.")
    parser.add_argument("--book", default="build/structured/book.json", type=Path)
    parser.add_argument("--manifest", default="build/tts/manifest.json", type=Path)
    parser.add_argument("--audio-dir", default="build/audio", type=Path)
    parser.add_argument("--output", default="build/daisy", type=Path)
    parser.add_argument("--section", default="chapter_01")
    args = parser.parse_args(argv)

    try:
        result = build_daisy(
            args.book,
            args.manifest,
            args.audio_dir,
            args.output,
            args.section,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Built DAISY 3 sample")
    print(f"section: {result.section_id}")
    print(f"units: {result.unit_count}")
    print(f"duration: {format_duration(result.duration_ms)}")
    print(f"uid: {result.uid}")
    print(f"output: {result.output_dir}")
    for name in ("book.xml", f"{result.section_id}.smil", "book.ncx", "book.opf", f"{result.section_id}.mp3"):
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())