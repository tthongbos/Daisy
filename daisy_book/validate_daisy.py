from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

from lxml import etree


XML_EXTENSIONS = {".xml", ".smil", ".ncx", ".opf"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
SMIL_CLOCK = re.compile(r"^npt=(\d+(?:\.\d+)?)s$")


def local_references(tree: etree._ElementTree, attr_name: str = "src") -> list[str]:
    values = tree.xpath(f"//*[@{attr_name}]/@{attr_name}")
    refs: list[str] = []
    for value in values:
        value = str(value).strip()
        if not value or "://" in value or value.startswith("data:"):
            continue
        refs.append(unquote(value))
    return refs


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _document_ids(
    path: Path,
    tree: etree._ElementTree,
    root: Path,
    errors: list[str],
) -> set[str]:
    identifiers: set[str] = set()
    for element in tree.iter():
        for attribute in ("id", XML_ID):
            identifier = element.get(attribute)
            if not identifier:
                continue
            if identifier in identifiers:
                errors.append(f"Duplicate XML id in {_relative(path, root)}: {identifier}")
            identifiers.add(identifier)
    return identifiers


def _parse_smil_clock(value: str) -> float | None:
    match = SMIL_CLOCK.fullmatch(value.strip())
    return float(match.group(1)) if match else None


def _validate_opf(
    path: Path,
    tree: etree._ElementTree,
    root: Path,
    errors: list[str],
) -> None:
    manifest_items = tree.xpath("//*[local-name()='manifest']/*[local-name()='item']")
    manifest_ids = {str(item.get("id")) for item in manifest_items if item.get("id")}
    for item in manifest_items:
        item_id = item.get("id")
        href = item.get("href")
        if not item_id:
            errors.append(f"OPF manifest item has no id: {_relative(path, root)}")
        if not href:
            errors.append(f"OPF manifest item has no href: {_relative(path, root)}")

    for itemref in tree.xpath("//*[local-name()='spine']/*[local-name()='itemref']"):
        idref = itemref.get("idref")
        if not idref or idref not in manifest_ids:
            errors.append(
                f"OPF spine idref does not resolve in {_relative(path, root)}: {idref or '<missing>'}"
            )
    for spine in tree.xpath("//*[local-name()='spine']"):
        toc = spine.get("toc")
        if not toc or toc not in manifest_ids:
            errors.append(
                f"OPF spine toc does not resolve in {_relative(path, root)}: {toc or '<missing>'}"
            )

    unique_id = tree.getroot().get("unique-identifier")
    identifiers = tree.xpath("//*[local-name()='Identifier']")
    matching = [element for element in identifiers if element.get("id") == unique_id]
    if not unique_id or len(matching) != 1 or not (matching[0].text or "").strip():
        errors.append(f"OPF unique-identifier does not resolve in {_relative(path, root)}")


def _validate_smil_clips(
    path: Path,
    tree: etree._ElementTree,
    root: Path,
    errors: list[str],
) -> None:
    for audio in tree.xpath("//*[local-name()='audio']"):
        begin_text = audio.get("clipBegin", "")
        end_text = audio.get("clipEnd", "")
        begin = _parse_smil_clock(begin_text)
        end = _parse_smil_clock(end_text)
        if begin is None or end is None:
            errors.append(
                f"Invalid SMIL clip clock in {_relative(path, root)}: {begin_text!r} -> {end_text!r}"
            )
        elif begin >= end:
            errors.append(
                f"SMIL clipBegin must be less than clipEnd in {_relative(path, root)}: "
                f"{begin_text} -> {end_text}"
            )


def _uid_values(path: Path, tree: etree._ElementTree, root: Path, errors: list[str]) -> set[str]:
    values = {
        str(value).strip()
        for value in tree.xpath("//*[local-name()='meta'][@name='dtb:uid']/@content")
        if str(value).strip()
    }
    if path.suffix.lower() == ".opf":
        unique_id = tree.getroot().get("unique-identifier")
        values.update(
            (element.text or "").strip()
            for element in tree.xpath("//*[local-name()='Identifier']")
            if element.get("id") == unique_id and (element.text or "").strip()
        )
    if len(values) != 1:
        errors.append(
            f"Expected one consistent dtb:uid in {_relative(path, root)}, found: {sorted(values)}"
        )
    return values


def validate_daisy(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        return [f"Not a directory: {root}"], warnings

    root = root.resolve()

    files = [p.resolve() for p in root.rglob("*") if p.is_file()]
    by_ext: dict[str, list[Path]] = {}
    for p in files:
        by_ext.setdefault(p.suffix.lower(), []).append(p)

    required = {".opf": 1, ".xml": 1, ".smil": 1, ".ncx": 1, ".mp3": 1}
    for ext, minimum in required.items():
        count = len(by_ext.get(ext, []))
        if count < minimum:
            errors.append(f"Missing required DAISY resource: {ext} (found {count})")

    if len(by_ext.get(".opf", [])) > 1:
        warnings.append("More than one OPF file found; verify the intended package file.")

    parsed: dict[Path, etree._ElementTree] = {}
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
    for path in files:
        if path.suffix.lower() not in XML_EXTENSIONS:
            continue
        try:
            parsed[path] = etree.parse(str(path), parser)
        except (etree.XMLSyntaxError, OSError) as exc:
            errors.append(f"Invalid XML: {_relative(path, root)}: {exc}")

    ids_by_path = {
        path: _document_ids(path, tree, root, errors)
        for path, tree in parsed.items()
    }

    for path, tree in parsed.items():
        for attr in ("src", "href", "smilref"):
            for ref in local_references(tree, attr_name=attr):
                file_ref, separator, fragment = ref.partition("#")
                candidate = (path.parent / file_ref).resolve() if file_ref else path
                try:
                    candidate.relative_to(root.resolve())
                except ValueError:
                    errors.append(f"Reference escapes package directory: {_relative(path, root)} -> {ref}")
                    continue
                if not candidate.exists():
                    errors.append(f"Broken reference: {_relative(path, root)} -> {ref}")
                    continue
                if separator and fragment:
                    target_ids = ids_by_path.get(candidate)
                    if target_ids is not None and fragment not in target_ids:
                        errors.append(f"Broken fragment: {_relative(path, root)} -> {ref}")

        if path.suffix.lower() == ".opf":
            _validate_opf(path, tree, root, errors)
        if path.suffix.lower() == ".smil":
            _validate_smil_clips(path, tree, root, errors)

    uid_by_path = {
        path: _uid_values(path, tree, root, errors)
        for path, tree in parsed.items()
    }
    complete_uids = {
        next(iter(values))
        for values in uid_by_path.values()
        if len(values) == 1
    }
    if len(complete_uids) > 1:
        details = ", ".join(
            f"{_relative(path, root)}={next(iter(values))}"
            for path, values in sorted(uid_by_path.items())
            if len(values) == 1
        )
        errors.append(f"Inconsistent dtb:uid across DAISY XML files: {details}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run structural checks on a DAISY 3 output folder.")
    parser.add_argument("--input", default="build/daisy")
    args = parser.parse_args()

    errors, warnings = validate_daisy(Path(args.input))
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Validation failed: {len(errors)} error(s), {len(warnings)} warning(s).")
        return 1
    print(f"Validation passed with {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
