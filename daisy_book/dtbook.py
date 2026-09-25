from __future__ import annotations

from typing import Any

from lxml import etree

from .epub import normalize_isbn


DTBOOK_NS = "http://www.daisy.org/z3986/2005/dtbook/"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _metadata_value(metadata: dict[str, Any], *path: str) -> str | None:
    value: Any = metadata
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _source_isbn_urn(metadata: dict[str, Any]) -> str | None:
    source = metadata.get("source") if isinstance(metadata.get("source"), dict) else {}
    isbn = _metadata_value(source, "isbn") or _metadata_value(metadata, "isbn")
    if not isbn:
        return None
    normalized = normalize_isbn(isbn)
    if normalized is None:
        return None
    return f"urn:isbn:{normalized}"


def _daisy_value(metadata: dict[str, Any], key: str) -> str | None:
    daisy = metadata.get("daisy") if isinstance(metadata.get("daisy"), dict) else {}
    return _metadata_value(daisy, key) or _metadata_value(metadata, key)


def _emit_meta(head: etree._Element, metadata: dict[str, Any]) -> None:
    for key, name in (
        ("title", "dc:Title"),
        ("author", "dc:Creator"),
        ("translator", "dc:Contributor"),
        ("language", "dc:Language"),
        ("subject", "dc:Subject"),
        ("description", "dc:Description"),
    ):
        value = _metadata_value(metadata, key)
        if value:
            etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name=name, content=value)
    source_urn = _source_isbn_urn(metadata)
    if source_urn:
        etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dc:Source", content=source_urn)
    generator = _daisy_value(metadata, "generator")
    if generator:
        etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dtb:generator", content=generator)


def _element(name: str, **attributes: str) -> etree._Element:
    return etree.Element(etree.QName(DTBOOK_NS, name), **attributes)


def build_dtbook(
    metadata: dict[str, Any],
    section: dict[str, Any],
    units: list[dict[str, Any]],
    uid: str,
) -> etree._ElementTree:
    """Build DTBook for a single section (backward compatible)."""
    language = str(metadata.get("language") or "vi")
    root = etree.Element(
        etree.QName(DTBOOK_NS, "dtbook"),
        nsmap={None: DTBOOK_NS},
        version="2005-3",
        attrib={etree.QName(XML_NS, "lang"): language},
    )
    head = etree.SubElement(root, etree.QName(DTBOOK_NS, "head"))
    etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dtb:uid", content=uid)
    _emit_meta(head, metadata)

    book = etree.SubElement(root, etree.QName(DTBOOK_NS, "book"))
    bodymatter = etree.SubElement(book, etree.QName(DTBOOK_NS, "bodymatter"))
    level = etree.SubElement(
        bodymatter,
        etree.QName(DTBOOK_NS, "level1"),
        id=str(section["id"]),
    )

    for unit in units:
        unit_id = str(unit["id"])
        unit_type = unit["type"]
        attributes = {
            "id": unit_id,
            "smilref": f"{section['id']}.smil#par_{unit_id}",
        }
        if unit_type == "heading":
            element = etree.SubElement(level, etree.QName(DTBOOK_NS, "h1"), **attributes)
        else:
            if unit_type == "subtitle":
                attributes["class"] = "subtitle"
            element = etree.SubElement(level, etree.QName(DTBOOK_NS, "p"), **attributes)
        element.text = str(unit["display_text"])

    return etree.ElementTree(root)


def build_dtbook_multi(
    metadata: dict[str, Any],
    sections_with_units: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    uid: str,
) -> etree._ElementTree:
    """Build DTBook for multiple sections with one level1 per section."""
    language = str(metadata.get("language") or "vi")
    root = etree.Element(
        etree.QName(DTBOOK_NS, "dtbook"),
        nsmap={None: DTBOOK_NS},
        version="2005-3",
        attrib={etree.QName(XML_NS, "lang"): language},
    )
    head = etree.SubElement(root, etree.QName(DTBOOK_NS, "head"))
    etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dtb:uid", content=uid)
    _emit_meta(head, metadata)

    book = etree.SubElement(root, etree.QName(DTBOOK_NS, "book"))
    bodymatter = etree.SubElement(book, etree.QName(DTBOOK_NS, "bodymatter"))

    for section, units in sections_with_units:
        level = etree.SubElement(
            bodymatter,
            etree.QName(DTBOOK_NS, "level1"),
            id=str(section["id"]),
        )

        for unit in units:
            unit_id = str(unit["id"])
            unit_type = unit["type"]
            attributes = {
                "id": unit_id,
                "smilref": f"{section['id']}.smil#par_{unit_id}",
            }
            if unit_type == "heading":
                element = etree.SubElement(level, etree.QName(DTBOOK_NS, "h1"), **attributes)
            else:
                if unit_type == "subtitle":
                    attributes["class"] = "subtitle"
                element = etree.SubElement(level, etree.QName(DTBOOK_NS, "p"), **attributes)
            element.text = str(unit["display_text"])

    return etree.ElementTree(root)