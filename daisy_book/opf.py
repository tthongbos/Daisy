from __future__ import annotations

from typing import Any

from lxml import etree


OPF_NS = "http://openebook.org/namespaces/oeb-package/1.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"


def format_duration(milliseconds: int) -> str:
    if not isinstance(milliseconds, int) or isinstance(milliseconds, bool) or milliseconds < 0:
        raise ValueError("Duration must be a non-negative integer")
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def build_opf(
    metadata: dict[str, Any],
    section_id: str,
    uid: str,
    duration_ms: int,
) -> etree._ElementTree:
    root = etree.Element(
        etree.QName(OPF_NS, "package"),
        nsmap={None: OPF_NS},
        attrib={"unique-identifier": "uid"},
    )
    metadata_element = etree.SubElement(root, etree.QName(OPF_NS, "metadata"))
    dc_metadata = etree.SubElement(
        metadata_element,
        etree.QName(OPF_NS, "dc-metadata"),
        nsmap={None: OPF_NS, "dc": DC_NS, "oebpackage": OPF_NS},
    )
    mappings = (
        ("title", "Title"),
        ("author", "Creator"),
        ("subject", "Subject"),
        ("description", "Description"),
        ("publisher", "Publisher"),
        ("translator", "Contributor"),
        ("date", "Date"),
    )
    for key, element_name in mappings:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            etree.SubElement(dc_metadata, etree.QName(DC_NS, element_name)).text = value
    etree.SubElement(dc_metadata, etree.QName(DC_NS, "Identifier"), id="uid").text = uid
    language = metadata.get("language")
    if isinstance(language, str) and language.strip():
        etree.SubElement(dc_metadata, etree.QName(DC_NS, "Language")).text = language
    etree.SubElement(dc_metadata, etree.QName(DC_NS, "Format")).text = (
        "ANSI/NISO Z39.86-2005"
    )

    extra_metadata = etree.SubElement(metadata_element, etree.QName(OPF_NS, "x-metadata"))
    for name, content in (
        ("dtb:uid", uid),
        ("dtb:multimediaType", "audioFullText"),
        ("dtb:multimediaContent", "audio,text"),
        ("dtb:audioFormat", "MP3"),
        ("dtb:totalTime", format_duration(duration_ms)),
    ):
        etree.SubElement(
            extra_metadata,
            etree.QName(OPF_NS, "meta"),
            name=name,
            content=content,
        )

    manifest = etree.SubElement(root, etree.QName(OPF_NS, "manifest"))
    resources = (
        ("opf", "book.opf", "text/xml"),
        ("dtbook", "book.xml", "application/x-dtbook+xml"),
        ("ncx", "book.ncx", "application/x-dtbncx+xml"),
        (f"smil_{section_id}", f"{section_id}.smil", "application/smil"),
        (f"audio_{section_id}", f"{section_id}.mp3", "audio/mpeg"),
    )
    for item_id, href, media_type in resources:
        etree.SubElement(
            manifest,
            etree.QName(OPF_NS, "item"),
            id=item_id,
            href=href,
            **{"media-type": media_type},
        )

    spine = etree.SubElement(root, etree.QName(OPF_NS, "spine"))
    etree.SubElement(
        spine,
        etree.QName(OPF_NS, "itemref"),
        idref=f"smil_{section_id}",
    )
    return etree.ElementTree(root)


def build_opf_multi(
    metadata: dict[str, Any],
    section_ids: list[str],
    section_durations: list[int],
    uid: str,
) -> etree._ElementTree:
    """Build OPF for multiple sections.
    
    Args:
        metadata: Book metadata
        section_ids: List of section IDs in source order
        section_durations: List of duration_ms for each section
        uid: Unique identifier
    
    Returns:
        ElementTree containing manifest and spine entries for all sections
    """
    if len(section_ids) != len(section_durations):
        raise ValueError("section_ids and section_durations must have same length")
    
    # Calculate total duration as sum of all sections
    total_duration_ms = sum(section_durations)
    
    root = etree.Element(
        etree.QName(OPF_NS, "package"),
        nsmap={None: OPF_NS},
        attrib={"unique-identifier": "uid"},
    )
    metadata_element = etree.SubElement(root, etree.QName(OPF_NS, "metadata"))
    dc_metadata = etree.SubElement(
        metadata_element,
        etree.QName(OPF_NS, "dc-metadata"),
        nsmap={None: OPF_NS, "dc": DC_NS, "oebpackage": OPF_NS},
    )
    mappings = (
        ("title", "Title"),
        ("author", "Creator"),
        ("subject", "Subject"),
        ("description", "Description"),
        ("publisher", "Publisher"),
        ("translator", "Contributor"),
        ("date", "Date"),
    )
    for key, element_name in mappings:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            etree.SubElement(dc_metadata, etree.QName(DC_NS, element_name)).text = value
    etree.SubElement(dc_metadata, etree.QName(DC_NS, "Identifier"), id="uid").text = uid
    language = metadata.get("language")
    if isinstance(language, str) and language.strip():
        etree.SubElement(dc_metadata, etree.QName(DC_NS, "Language")).text = language
    etree.SubElement(dc_metadata, etree.QName(DC_NS, "Format")).text = (
        "ANSI/NISO Z39.86-2005"
    )

    extra_metadata = etree.SubElement(metadata_element, etree.QName(OPF_NS, "x-metadata"))
    for name, content in (
        ("dtb:uid", uid),
        ("dtb:multimediaType", "audioFullText"),
        ("dtb:multimediaContent", "audio,text"),
        ("dtb:audioFormat", "MP3"),
        ("dtb:totalTime", format_duration(total_duration_ms)),
    ):
        etree.SubElement(
            extra_metadata,
            etree.QName(OPF_NS, "meta"),
            name=name,
            content=content,
        )

    manifest = etree.SubElement(root, etree.QName(OPF_NS, "manifest"))
    
    # Add static resources
    resources = (
        ("opf", "book.opf", "text/xml"),
        ("dtbook", "book.xml", "application/x-dtbook+xml"),
        ("ncx", "book.ncx", "application/x-dtbncx+xml"),
    )
    for item_id, href, media_type in resources:
        etree.SubElement(
            manifest,
            etree.QName(OPF_NS, "item"),
            id=item_id,
            href=href,
            **{"media-type": media_type},
        )
    
    # Add manifest entries for each section's SMIL and MP3 in order
    for section_id in section_ids:
        etree.SubElement(
            manifest,
            etree.QName(OPF_NS, "item"),
            id=f"smil_{section_id}",
            href=f"{section_id}.smil",
            **{"media-type": "application/smil"},
        )
        etree.SubElement(
            manifest,
            etree.QName(OPF_NS, "item"),
            id=f"audio_{section_id}",
            href=f"{section_id}.mp3",
            **{"media-type": "audio/mpeg"},
        )

    # Add spine entries for each SMIL in source order
    spine = etree.SubElement(root, etree.QName(OPF_NS, "spine"))
    for section_id in section_ids:
        etree.SubElement(
            spine,
            etree.QName(OPF_NS, "itemref"),
            idref=f"smil_{section_id}",
        )
    
    return etree.ElementTree(root)