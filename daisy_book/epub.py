from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from lxml import etree


CONTAINER_PATH = "META-INF/container.xml"
CONTAINER_NS = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_NS = "http://www.idpf.org/2007/opf"


def normalize_isbn(value: str | object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    candidate = candidate.removeprefix("urn:isbn:").strip()
    candidate = re.sub(r"^isbn\s*", "", candidate, flags=re.IGNORECASE).strip()
    candidate = re.sub(r"[^0-9Xx]", "", candidate)
    if not candidate:
        return None

    def isbn13_is_valid(number: str) -> bool:
        if len(number) != 13 or not number.isdigit():
            return False
        total = sum((1 if index % 2 == 0 else 3) * int(digit) for index, digit in enumerate(number))
        return total % 10 == 0

    def isbn10_to_isbn13(number: str) -> str | None:
        if len(number) != 10 or not number[:-1].isdigit() or not (number[-1].isdigit() or number[-1].lower() == "x"):
            return None
        checksum = 0
        for index, digit in enumerate(number[:-1]):
            checksum += int(digit) * (10 - index)
        check_digit = (11 - (checksum % 11)) % 11
        if check_digit == 10:
            check_digit = "X"
        else:
            check_digit = str(check_digit)
        if str(number[-1]).upper() != str(check_digit):
            return None
        return "978" + number[:-1]

    if isbn13_is_valid(candidate):
        return candidate
    converted = isbn10_to_isbn13(candidate)
    if converted is not None and isbn13_is_valid(converted):
        return converted
    return None


@dataclass(frozen=True)
class EpubMetadata:
    title: str | None
    creators: tuple[str, ...]
    authors: tuple[str, ...]
    translators: tuple[str, ...]
    language: str | None
    identifiers: tuple[str, ...]
    publisher: str | None = None
    date: str | None = None
    subject: str | None = None
    description: str | None = None
    rights: str | None = None


@dataclass(frozen=True)
class EpubDocument:
    id: str
    href: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class EpubBook:
    metadata: EpubMetadata
    documents: tuple[EpubDocument, ...]
    opf_path: str


def _archive_path(base_path: str, href: str) -> str:
    href_path = unquote(href.split("#", 1)[0])
    path = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), href_path))
    if path.startswith("../") or path.startswith("/"):
        raise ValueError(f"EPUB item resolves outside the archive: {href}")
    return path


def _text(element: etree._Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _parse_metadata(opf: etree._Element) -> EpubMetadata:
    namespaces = {"dc": DC_NS, "opf": OPF_NS}
    creator_elements = opf.xpath("./opf:metadata/dc:creator", namespaces=namespaces)
    creators = tuple(value for element in creator_elements if (value := _text(element)))

    authors: list[str] = []
    translators: list[str] = []
    for element in creator_elements:
        name = _text(element)
        if not name:
            continue
        role = (element.get(f"{{{OPF_NS}}}role") or "").lower()
        if role == "trl" or re.search(r"\(\s*dịch\s*\)$", name, re.IGNORECASE):
            translators.append(re.sub(r"\s*\(\s*dịch\s*\)\s*$", "", name, flags=re.IGNORECASE))
        else:
            authors.append(name)

    identifiers = tuple(
        value
        for element in opf.xpath("./opf:metadata/dc:identifier", namespaces=namespaces)
        if (value := _text(element))
    )
    subject_elements = opf.xpath("./opf:metadata/dc:subject", namespaces=namespaces)
    subjects = tuple(value for element in subject_elements if (value := _text(element)))
    return EpubMetadata(
        title=_text(opf.find("./opf:metadata/dc:title", namespaces)),
        creators=creators,
        authors=tuple(authors),
        translators=tuple(translators),
        language=_text(opf.find("./opf:metadata/dc:language", namespaces)),
        identifiers=identifiers,
        publisher=_text(opf.find("./opf:metadata/dc:publisher", namespaces)),
        date=_text(opf.find("./opf:metadata/dc:date", namespaces)),
        subject="; ".join(subjects) if subjects else None,
        description=_text(opf.find("./opf:metadata/dc:description", namespaces)),
        rights=_text(opf.find("./opf:metadata/dc:rights", namespaces)),
    )


def load_epub(path: str | Path) -> EpubBook:
    epub_path = Path(path)
    if not epub_path.is_file():
        raise FileNotFoundError(f"EPUB source not found: {epub_path}")

    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        with ZipFile(epub_path) as archive:
            try:
                container = etree.fromstring(archive.read(CONTAINER_PATH), parser)
            except KeyError as error:
                raise ValueError(f"EPUB is missing {CONTAINER_PATH}") from error

            rootfiles = container.xpath(
                "./container:rootfiles/container:rootfile/@full-path",
                namespaces=CONTAINER_NS,
            )
            if not rootfiles:
                raise ValueError("EPUB container does not identify an OPF package")
            opf_path = str(rootfiles[0])

            try:
                opf = etree.fromstring(archive.read(opf_path), parser)
            except KeyError as error:
                raise ValueError(f"EPUB package is missing: {opf_path}") from error

            namespaces = {"opf": OPF_NS}
            manifest: dict[str, etree._Element] = {
                item_id: item
                for item in opf.xpath("./opf:manifest/opf:item", namespaces=namespaces)
                if (item_id := item.get("id"))
            }
            documents: list[EpubDocument] = []
            for itemref in opf.xpath("./opf:spine/opf:itemref", namespaces=namespaces):
                idref = itemref.get("idref")
                item = manifest.get(idref or "")
                if item is None:
                    raise ValueError(f"EPUB spine references missing manifest item: {idref}")
                href = item.get("href")
                if not href:
                    raise ValueError(f"EPUB manifest item has no href: {idref}")
                media_type = item.get("media-type", "")
                if media_type not in {"application/xhtml+xml", "text/html"}:
                    continue
                archive_path = _archive_path(opf_path, href)
                try:
                    content = archive.read(archive_path)
                except KeyError as error:
                    raise ValueError(f"EPUB spine document is missing: {archive_path}") from error
                documents.append(
                    EpubDocument(
                        id=idref or "",
                        href=archive_path,
                        media_type=media_type,
                        content=content,
                    )
                )
    except BadZipFile as error:
        raise ValueError(f"Invalid EPUB ZIP archive: {epub_path}") from error

    return EpubBook(
        metadata=_parse_metadata(opf),
        documents=tuple(documents),
        opf_path=opf_path,
    )