from __future__ import annotations

from typing import Any

from lxml import etree


DTBOOK_NS = "http://www.daisy.org/z3986/2005/dtbook/"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _element(name: str, **attributes: str) -> etree._Element:
    return etree.Element(etree.QName(DTBOOK_NS, name), **attributes)


def build_dtbook(
    metadata: dict[str, Any],
    section: dict[str, Any],
    units: list[dict[str, Any]],
    uid: str,
) -> etree._ElementTree:
    language = str(metadata.get("language") or "vi")
    root = etree.Element(
        etree.QName(DTBOOK_NS, "dtbook"),
        nsmap={None: DTBOOK_NS},
        version="2005-3",
        attrib={etree.QName(XML_NS, "lang"): language},
    )
    head = etree.SubElement(root, etree.QName(DTBOOK_NS, "head"))
    etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dtb:uid", content=uid)

    metadata_names = {
        "title": "dc:Title",
        "author": "dc:Creator",
        "translator": "dc:Contributor",
        "language": "dc:Language",
        "subject": "dc:Subject",
        "publisher": "dc:Publisher",
        "date": "dc:Date",
        "description": "dc:Description",
    }
    for key, name in metadata_names.items():
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name=name, content=value)
    isbn = metadata.get("isbn")
    if isinstance(isbn, str) and isbn.strip():
        etree.SubElement(head, etree.QName(DTBOOK_NS, "meta"), name="dc:Identifier", content=uid)

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