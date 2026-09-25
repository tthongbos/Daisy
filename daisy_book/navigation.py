from __future__ import annotations

from typing import Any

from lxml import etree


NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _metadata_value(metadata: dict[str, Any], *path: str) -> str | None:
    value: Any = metadata
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _daisy_value(metadata: dict[str, Any], key: str) -> str | None:
    daisy = metadata.get("daisy") if isinstance(metadata.get("daisy"), dict) else {}
    return _metadata_value(daisy, key) or _metadata_value(metadata, key)


def build_ncx(
    metadata: dict[str, Any],
    section: dict[str, Any],
    uid: str,
) -> etree._ElementTree:
    """Build NCX for a single section (backward compatible)."""
    language = str(metadata.get("language") or "vi")
    root = etree.Element(
        etree.QName(NCX_NS, "ncx"),
        nsmap={None: NCX_NS},
        version="2005-1",
        attrib={etree.QName(XML_NS, "lang"): language},
    )
    head = etree.SubElement(root, etree.QName(NCX_NS, "head"))
    for name, content in (
        ("dtb:uid", uid),
        ("dtb:depth", "1"),
        ("dtb:totalPageCount", "0"),
        ("dtb:maxPageNumber", "0"),
    ):
        etree.SubElement(head, etree.QName(NCX_NS, "meta"), name=name, content=content)
    generator = _daisy_value(metadata, "generator")
    if generator:
        etree.SubElement(head, etree.QName(NCX_NS, "meta"), name="dtb:generator", content=generator)

    doc_title = etree.SubElement(root, etree.QName(NCX_NS, "docTitle"))
    etree.SubElement(doc_title, etree.QName(NCX_NS, "text")).text = str(metadata["title"])
    doc_author = etree.SubElement(root, etree.QName(NCX_NS, "docAuthor"))
    etree.SubElement(doc_author, etree.QName(NCX_NS, "text")).text = str(metadata["author"])

    nav_map = etree.SubElement(root, etree.QName(NCX_NS, "navMap"))
    nav_point = etree.SubElement(
        nav_map,
        etree.QName(NCX_NS, "navPoint"),
        id=f"nav_{section['id']}",
        playOrder="1",
    )
    nav_label = etree.SubElement(nav_point, etree.QName(NCX_NS, "navLabel"))
    number = section.get("number")
    label = f"Chương {number}. {section['title']}" if number is not None else str(section["title"])
    etree.SubElement(nav_label, etree.QName(NCX_NS, "text")).text = label
    etree.SubElement(
        nav_point,
        etree.QName(NCX_NS, "content"),
        src=f"{section['id']}.smil#par_{section['id']}_title",
    )
    return etree.ElementTree(root)


def build_ncx_multi(
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
    uid: str,
) -> etree._ElementTree:
    """Build NCX for multiple sections with one navPoint per section."""
    language = str(metadata.get("language") or "vi")
    root = etree.Element(
        etree.QName(NCX_NS, "ncx"),
        nsmap={None: NCX_NS},
        version="2005-1",
        attrib={etree.QName(XML_NS, "lang"): language},
    )
    head = etree.SubElement(root, etree.QName(NCX_NS, "head"))
    for name, content in (
        ("dtb:uid", uid),
        ("dtb:depth", "1"),
        ("dtb:totalPageCount", "0"),
        ("dtb:maxPageNumber", "0"),
    ):
        etree.SubElement(head, etree.QName(NCX_NS, "meta"), name=name, content=content)
    generator = _daisy_value(metadata, "generator")
    if generator:
        etree.SubElement(head, etree.QName(NCX_NS, "meta"), name="dtb:generator", content=generator)

    doc_title = etree.SubElement(root, etree.QName(NCX_NS, "docTitle"))
    etree.SubElement(doc_title, etree.QName(NCX_NS, "text")).text = str(metadata["title"])
    doc_author = etree.SubElement(root, etree.QName(NCX_NS, "docAuthor"))
    etree.SubElement(doc_author, etree.QName(NCX_NS, "text")).text = str(metadata["author"])

    nav_map = etree.SubElement(root, etree.QName(NCX_NS, "navMap"))

    for play_order, section in enumerate(sections, start=1):
        nav_point = etree.SubElement(
            nav_map,
            etree.QName(NCX_NS, "navPoint"),
            id=f"nav_{section['id']}",
            playOrder=str(play_order),
        )
        nav_label = etree.SubElement(nav_point, etree.QName(NCX_NS, "navLabel"))
        section_type = section.get("type", "chapter")
        number = section.get("number")
        if section_type == "introduction" or number is None:
            label = str(section["title"])
        else:
            label = f"Chương {number}. {section['title']}"
        etree.SubElement(nav_label, etree.QName(NCX_NS, "text")).text = label
        etree.SubElement(
            nav_point,
            etree.QName(NCX_NS, "content"),
            src=f"{section['id']}.smil#par_{section['id']}_title",
        )

    return etree.ElementTree(root)