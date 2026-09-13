from __future__ import annotations

import re
import unicodedata

from lxml import etree, html


WHITESPACE_RE = re.compile(r"\s+")
SAFE_SPAN_ATTRIBUTES = {
    "class",
    "dir",
    "lang",
    "style",
    "{http://www.w3.org/XML/1998/namespace}lang",
}


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFC", text).replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", value).strip()


def paragraph_text(paragraph: etree._Element) -> str:
    return normalize_text("".join(paragraph.itertext()))


def _normalize_text_nodes(element: etree._Element) -> None:
    slots: list[tuple[etree._Element, str]] = []
    for node in element.iter():
        if node.text is not None:
            slots.append((node, "text"))
        for child in node:
            if child.tail is not None:
                slots.append((child, "tail"))

    previous_ended_with_space = False
    for node, attribute in slots:
        value = getattr(node, attribute)
        normalized = unicodedata.normalize("NFC", value).replace("\u00a0", " ")
        normalized = WHITESPACE_RE.sub(" ", normalized)
        if previous_ended_with_space:
            normalized = normalized.lstrip(" ")
        setattr(node, attribute, normalized)
        if normalized:
            previous_ended_with_space = normalized.endswith(" ")

    for node, attribute in slots:
        value = getattr(node, attribute)
        if value:
            setattr(node, attribute, value.lstrip(" "))
            break
    for node, attribute in reversed(slots):
        value = getattr(node, attribute)
        if value:
            setattr(node, attribute, value.rstrip(" "))
            break


def normalize_document(content: bytes | str) -> html.HtmlElement:
    parser = html.HTMLParser(encoding="utf-8") if isinstance(content, bytes) else None
    document = html.fromstring(content, parser=parser)

    for span in list(document.xpath("//span")):
        if set(span.attrib).issubset(SAFE_SPAN_ATTRIBUTES):
            span.drop_tag()

    for paragraph in list(document.xpath("//p")):
        _normalize_text_nodes(paragraph)
        for image in paragraph.xpath(".//img"):
            if image.get("alt") is not None:
                image.set("alt", normalize_text(image.get("alt", "")))
        if not paragraph_text(paragraph) and not paragraph.xpath(".//img"):
            parent = paragraph.getparent()
            if parent is not None:
                parent.remove(paragraph)

    return document