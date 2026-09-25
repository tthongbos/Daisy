from __future__ import annotations

from typing import Any

from lxml import etree


SMIL_NS = "http://www.w3.org/2001/SMIL20/"


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


def ms_to_smil_clock(milliseconds: int) -> str:
    if not isinstance(milliseconds, int) or isinstance(milliseconds, bool) or milliseconds < 0:
        raise ValueError("SMIL clock milliseconds must be a non-negative integer")
    # Convert milliseconds to colon-clock format H:MM:SS.mmm using integer arithmetic
    total_seconds, millis = divmod(milliseconds, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def build_smil(
    section_id: str,
    timing: dict[str, Any],
    uid: str,
    metadata: dict[str, Any] | None = None,
) -> etree._ElementTree:
    root = etree.Element(
        etree.QName(SMIL_NS, "smil"),
        nsmap={None: SMIL_NS},
    )
    head = etree.SubElement(root, etree.QName(SMIL_NS, "head"))
    etree.SubElement(head, etree.QName(SMIL_NS, "meta"), name="dtb:uid", content=uid)
    if metadata is not None:
        generator = _metadata_value(metadata.get("daisy") if isinstance(metadata.get("daisy"), dict) else {}, "generator") or _metadata_value(metadata, "generator")
        if generator:
            etree.SubElement(head, etree.QName(SMIL_NS, "meta"), name="dtb:generator", content=generator)
    etree.SubElement(
        head,
        etree.QName(SMIL_NS, "meta"),
        name="dtb:totalElapsedTime",
        content="00:00:00.000",
    )
    body = etree.SubElement(root, etree.QName(SMIL_NS, "body"))
    sequence = etree.SubElement(body, etree.QName(SMIL_NS, "seq"), id=f"seq_{section_id}")

    for unit in timing["units"]:
        unit_id = str(unit["id"])
        parallel = etree.SubElement(
            sequence,
            etree.QName(SMIL_NS, "par"),
            id=f"par_{unit_id}",
        )
        etree.SubElement(
            parallel,
            etree.QName(SMIL_NS, "text"),
            src=f"book.xml#{unit_id}",
        )
        etree.SubElement(
            parallel,
            etree.QName(SMIL_NS, "audio"),
            src=f"{section_id}.mp3",
            clipBegin=ms_to_smil_clock(unit["clip_begin_ms"]),
            clipEnd=ms_to_smil_clock(unit["clip_end_ms"]),
        )

    return etree.ElementTree(root)