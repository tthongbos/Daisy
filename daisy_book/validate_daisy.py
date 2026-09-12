from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import unquote

from lxml import etree


XML_EXTENSIONS = {".xml", ".smil", ".ncx", ".opf"}


def local_references(tree: etree._ElementTree, attr_name: str = "src") -> list[str]:
    values = tree.xpath(f"//*[@{attr_name}]/@{attr_name}")
    refs: list[str] = []
    for value in values:
        value = str(value).strip()
        if not value or "://" in value or value.startswith("data:"):
            continue
        refs.append(unquote(value.split("#", 1)[0]))
    return refs


def validate_daisy(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        return [f"Not a directory: {root}"], warnings

    files = [p for p in root.rglob("*") if p.is_file()]
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
            errors.append(f"Invalid XML: {path.relative_to(root)}: {exc}")

    # Check local src/href references in XML-family files.
    for path, tree in parsed.items():
        for attr in ("src", "href"):
            for ref in local_references(tree, attr_name=attr):
                if not ref:
                    continue
                candidate = (path.parent / ref).resolve()
                try:
                    candidate.relative_to(root.resolve())
                except ValueError:
                    warnings.append(f"Reference escapes package directory: {path.relative_to(root)} -> {ref}")
                    continue
                if not candidate.exists():
                    errors.append(f"Broken reference: {path.relative_to(root)} -> {ref}")

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
