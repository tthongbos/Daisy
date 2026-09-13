from __future__ import annotations

from typing import Any

from lxml import etree


SMIL_NS = "http://www.w3.org/2001/SMIL20/"


def ms_to_smil_clock(milliseconds: int) -> str:
    if not isinstance(milliseconds, int) or isinstance(milliseconds, bool) or milliseconds < 0:
        raise ValueError("SMIL clock milliseconds must be a non-negative integer")
    return f"npt={milliseconds / 1000:.3f}s"


def build_smil(
    section_id: str,
    timing: dict[str, Any],
    uid: str,
) -> etree._ElementTree:
    root = etree.Element(
        etree.QName(SMIL_NS, "smil"),
        nsmap={None: SMIL_NS},
    )
    head = etree.SubElement(root, etree.QName(SMIL_NS, "head"))
    etree.SubElement(head, etree.QName(SMIL_NS, "meta"), name="dtb:uid", content=uid)
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