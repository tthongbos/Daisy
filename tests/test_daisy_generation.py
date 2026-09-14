import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from daisy_book.build_daisy import SMIL_DOCTYPE, build_daisy, resolve_book_uid, validate_source_relationships
from daisy_book.dtbook import DTBOOK_NS, build_dtbook
from daisy_book.navigation import NCX_NS, build_ncx
from daisy_book.opf import OPF_NS, build_opf, format_duration
from daisy_book.package_daisy import main as package_daisy
from daisy_book.smil import SMIL_NS, build_smil, ms_to_smil_clock


UID = "urn:uuid:11111111-2222-3333-4444-555555555555"


def sample_book():
    return {
        "metadata": {
            "title": "Tâm lý học về tiền",
            "author": "Morgan Housel",
            "translator": "Hoàng Thị Minh Phúc",
            "language": "vi",
            "subject": "Tâm lý học",
            "publisher": None,
            "date": None,
            "isbn": None,
            "description": None,
        },
        "sections": [
            {
                "id": "chapter_01",
                "type": "chapter",
                "number": 1,
                "title": "KHÔNG AI ĐIÊN",
                "subtitle": "Không ai điên cả",
                "blocks": [
                    {"type": "image", "src": "ignored.jpg", "alt": "Image"},
                    {
                        "id": "chapter_01_p0001",
                        "type": "paragraph",
                        "display_text": "Đoạn văn nguyên bản.",
                    },
                ],
            }
        ],
    }


def sample_manifest():
    return {
        "metadata": sample_book()["metadata"],
        "sections": [
            {
                "id": "chapter_01",
                "type": "chapter",
                "number": 1,
                "title": "KHÔNG AI ĐIÊN",
                "subtitle": "Không ai điên cả",
                "units": [
                    {
                        "id": "chapter_01_title",
                        "type": "heading",
                        "display_text": "KHÔNG AI ĐIÊN",
                        "tts_text": "Chương 1. Không ai điên.",
                    },
                    {
                        "id": "chapter_01_subtitle",
                        "type": "subtitle",
                        "display_text": "Không ai điên cả",
                        "tts_text": "Không ai điên cả.",
                    },
                    {
                        "id": "chapter_01_p0001",
                        "type": "paragraph",
                        "display_text": "Đoạn văn nguyên bản.",
                        "tts_text": "Đoạn văn để đọc.",
                    },
                ],
            }
        ],
    }


def sample_timing():
    return {
        "section_id": "chapter_01",
        "audio": "chapter_01.mp3",
        "duration_ms": 5100,
        "units": [
            {
                "id": "chapter_01_title",
                "type": "heading",
                "clip_begin_ms": 0,
                "clip_end_ms": 1000,
                "duration_ms": 1000,
            },
            {
                "id": "chapter_01_subtitle",
                "type": "subtitle",
                "clip_begin_ms": 1300,
                "clip_end_ms": 2500,
                "duration_ms": 1200,
            },
            {
                "id": "chapter_01_p0001",
                "type": "paragraph",
                "clip_begin_ms": 2800,
                "clip_end_ms": 5000,
                "duration_ms": 2200,
            },
        ],
    }


def parse(tree):
    return etree.fromstring(etree.tostring(tree))


def write_inputs(tmp_path: Path):
    book_path = tmp_path / "book.json"
    manifest_path = tmp_path / "manifest.json"
    audio_dir = tmp_path / "audio"
    chapter_dir = audio_dir / "chapter_01"
    chapter_dir.mkdir(parents=True)
    book_path.write_text(json.dumps(sample_book(), ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(sample_manifest(), ensure_ascii=False), encoding="utf-8")
    (chapter_dir / "chapter_01_timing.json").write_text(
        json.dumps(sample_timing()), encoding="utf-8"
    )
    audio_bytes = b"ID3\x04\x00\x00sample-audio"
    (chapter_dir / "chapter_01.mp3").write_bytes(audio_bytes)
    return book_path, manifest_path, audio_dir, audio_bytes


def test_dtbook_uses_source_display_text_and_resolvable_smilrefs():
    section, units = validate_source_relationships(
        sample_book(), sample_manifest(), sample_timing(), "chapter_01"
    )
    root = parse(build_dtbook(sample_book()["metadata"], section, units, UID))

    assert root.tag == f"{{{DTBOOK_NS}}}dtbook"
    assert root.get("{http://www.w3.org/XML/1998/namespace}lang") == "vi"
    assert root.xpath("string(d:head/d:meta[@name='dtb:uid']/@content)", namespaces={"d": DTBOOK_NS}) == UID
    assert root.xpath("string(.//*[@id='chapter_01_title'])") == "KHÔNG AI ĐIÊN"
    assert root.xpath("string(.//*[@id='chapter_01_subtitle'])") == "Không ai điên cả"
    assert root.xpath("string(.//*[@id='chapter_01_p0001'])") == "Đoạn văn nguyên bản."
    assert "Chương 1. Không ai điên." not in "".join(root.itertext())
    assert root.xpath("string(.//*[@id='chapter_01_p0001']/@smilref)") == (
        "chapter_01.smil#par_chapter_01_p0001"
    )


def test_smil_maps_each_timing_unit_exactly():
    root = parse(build_smil("chapter_01", sample_timing(), UID))
    namespaces = {"s": SMIL_NS}

    assert ms_to_smil_clock(8450) == "npt=8.450s"
    assert root.get("version") is None
    assert root.xpath("name(s:head)", namespaces=namespaces) == "head"
    assert root.xpath("name(s:body)", namespaces=namespaces) == "body"
    assert root.xpath("string(s:head/s:meta[@name='dtb:uid']/@content)", namespaces=namespaces) == UID
    assert root.xpath(
        "string(s:head/s:meta[@name='dtb:totalElapsedTime']/@content)", namespaces=namespaces
    ) == "00:00:00.000"
    assert root.xpath("string(s:body/s:seq/@id)", namespaces=namespaces) == "seq_chapter_01"
    assert root.xpath("//s:par/@id", namespaces=namespaces) == [
        "par_chapter_01_title",
        "par_chapter_01_subtitle",
        "par_chapter_01_p0001",
    ]
    assert root.xpath("//s:par/s:text/@src", namespaces=namespaces) == [
        "book.xml#chapter_01_title",
        "book.xml#chapter_01_subtitle",
        "book.xml#chapter_01_p0001",
    ]
    assert root.xpath("//s:par/s:audio/@src", namespaces=namespaces) == [
        "chapter_01.mp3",
        "chapter_01.mp3",
        "chapter_01.mp3",
    ]
    assert root.xpath("//s:par/s:audio/@clipBegin", namespaces=namespaces) == [
        "npt=0.000s",
        "npt=1.300s",
        "npt=2.800s",
    ]
    assert root.xpath("//s:par/s:audio/@clipEnd", namespaces=namespaces) == [
        "npt=1.000s",
        "npt=2.500s",
        "npt=5.000s",
    ]


@pytest.mark.parametrize(("begin", "end"), [(1000, 1000), (1001, 1000)])
def test_rejects_nonpositive_clip_intervals(begin, end):
    timing = sample_timing()
    timing["units"][1]["clip_begin_ms"] = begin
    timing["units"][1]["clip_end_ms"] = end

    with pytest.raises(ValueError, match="clip_end_ms must be greater"):
        validate_source_relationships(sample_book(), sample_manifest(), timing, "chapter_01")


def test_ncx_has_one_human_readable_navigation_point():
    root = parse(build_ncx(sample_book()["metadata"], sample_book()["sections"][0], UID))
    namespaces = {"n": NCX_NS}

    assert root.xpath("string(n:head/n:meta[@name='dtb:uid']/@content)", namespaces=namespaces) == UID
    assert root.xpath("string(n:docTitle/n:text)", namespaces=namespaces) == "Tâm lý học về tiền"
    assert root.xpath("string(n:docAuthor/n:text)", namespaces=namespaces) == "Morgan Housel"
    assert root.xpath("string(//n:navPoint/@playOrder)", namespaces=namespaces) == "1"
    assert root.xpath("string(//n:navLabel/n:text)", namespaces=namespaces) == "Chương 1. KHÔNG AI ĐIÊN"
    assert root.xpath("string(//n:content/@src)", namespaces=namespaces) == (
        "chapter_01.smil#par_chapter_01_title"
    )


def test_opf_declares_valid_oeb_1_2_structure_for_audio_full_text():
    root = parse(build_opf(sample_book()["metadata"], "chapter_01", UID, 5100))
    namespaces = {"o": OPF_NS, "dc": "http://purl.org/dc/elements/1.1/"}
    items = {
        item.get("href"): item.get("media-type")
        for item in root.xpath("//o:manifest/o:item", namespaces=namespaces)
    }
    dc_metadata = root.xpath("//o:metadata/o:dc-metadata", namespaces=namespaces)[0]
    spine = root.xpath("//o:spine", namespaces=namespaces)[0]

    assert root.nsmap.get(None) == OPF_NS
    assert root.get("unique-identifier") == "uid"
    assert root.get("version") is None
    assert root.nsmap.get("dc") is None
    assert dc_metadata.nsmap.get("dc") == "http://purl.org/dc/elements/1.1/"
    assert dc_metadata.nsmap.get("oebpackage") == OPF_NS
    assert spine.get("toc") is None

    assert items == {
        "book.opf": "text/xml",
        "book.xml": "application/x-dtbook+xml",
        "book.ncx": "application/x-dtbncx+xml",
        "chapter_01.smil": "application/smil",
        "chapter_01.mp3": "audio/mpeg",
    }
    assert root.xpath("string(//o:spine/o:itemref/@idref)", namespaces=namespaces) == "smil_chapter_01"
    assert root.xpath("string(//dc:Title)", namespaces=namespaces) == "Tâm lý học về tiền"
    assert root.xpath("string(//dc:Creator)", namespaces=namespaces) == "Morgan Housel"
    assert root.xpath("string(//dc:Contributor)", namespaces=namespaces) == "Hoàng Thị Minh Phúc"
    assert root.xpath("string(//dc:Language)", namespaces=namespaces) == "vi"
    assert root.xpath("string(//dc:Subject)", namespaces=namespaces) == "Tâm lý học"
    assert root.xpath("//dc:Format/text()", namespaces=namespaces) == [
        "ANSI/NISO Z39.86-2005"
    ]
    assert not root.xpath("//dc:Publisher | //dc:Date | //dc:Description", namespaces=namespaces)
    assert root.xpath("string(//dc:Identifier[@id='uid'])", namespaces=namespaces) == UID
    assert root.xpath(
        "string(//o:meta[@name='dtb:uid']/@content)", namespaces=namespaces
    ) == UID
    assert root.xpath(
        "string(//o:meta[@name='dtb:multimediaType']/@content)", namespaces=namespaces
    ) == "audioFullText"
    assert root.xpath(
        "string(//o:meta[@name='dtb:multimediaContent']/@content)", namespaces=namespaces
    ) == "audio,text"
    assert root.xpath(
        "string(//o:meta[@name='dtb:audioFormat']/@content)", namespaces=namespaces
    ) == "MP3"
    assert root.xpath("string(//o:meta[@name='dtb:totalTime']/@content)", namespaces=namespaces) == "00:00:05.100"
    assert format_duration(3_661_007) == "01:01:01.007"


def test_uid_uses_normalized_isbn_or_stable_metadata_uuid():
    metadata = sample_book()["metadata"]
    assert resolve_book_uid({**metadata, "isbn": "978-1-4028-9462-6"}) == "urn:isbn:9781402894626"
    assert resolve_book_uid(metadata) == resolve_book_uid(dict(metadata))
    assert resolve_book_uid(metadata).startswith("urn:uuid:")


def test_build_creates_valid_sample_and_copies_audio_unchanged(tmp_path):
    book_path, manifest_path, audio_dir, audio_bytes = write_inputs(tmp_path)
    output = tmp_path / "daisy"

    result = build_daisy(book_path, manifest_path, audio_dir, output, "chapter_01")

    assert {path.name for path in output.iterdir()} == {
        "book.xml",
        "book.opf",
        "book.ncx",
        "chapter_01.smil",
        "chapter_01.mp3",
    }
    assert (output / "chapter_01.mp3").read_bytes() == audio_bytes
    assert result.unit_count == 3
    assert result.duration_ms == 5100
    assert result.uid == resolve_book_uid(sample_book()["metadata"])


def test_generated_smil_uses_daisy_2005_2_doctype_without_version(tmp_path):
    book_path, manifest_path, audio_dir, _ = write_inputs(tmp_path)
    output = tmp_path / "daisy"

    build_daisy(book_path, manifest_path, audio_dir, output, "chapter_01")

    smil_text = (output / "chapter_01.smil").read_text(encoding="utf-8")
    smil_lines = smil_text.splitlines()
    assert SMIL_DOCTYPE == (
        '<!DOCTYPE smil PUBLIC "-//NISO//DTD dtbsmil 2005-2//EN" '
        '"http://www.daisy.org/z3986/2005/dtbsmil-2005-2.dtd">'
    )
    assert smil_lines[1] == SMIL_DOCTYPE
    assert smil_lines[2] == '<smil xmlns="http://www.w3.org/2001/SMIL20/">'
    assert 'version="2.0"' not in smil_text


def test_package_contains_only_root_resources_and_preserves_mp3(tmp_path, monkeypatch):
    book_path, manifest_path, audio_dir, audio_bytes = write_inputs(tmp_path)
    output = tmp_path / "daisy"
    package_output = tmp_path / "package"
    build_daisy(book_path, manifest_path, audio_dir, output, "chapter_01")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_daisy",
            "--input",
            str(output),
            "--output-dir",
            str(package_output),
            "--name",
            "sample",
        ],
    )

    assert package_daisy() == 0

    with zipfile.ZipFile(package_output / "sample.zip") as archive:
        assert set(archive.namelist()) == {
            "book.opf",
            "book.xml",
            "book.ncx",
            "chapter_01.smil",
            "chapter_01.mp3",
        }
        packaged_audio = archive.read("chapter_01.mp3")
    assert hashlib.sha256(packaged_audio).hexdigest() == hashlib.sha256(audio_bytes).hexdigest()


@pytest.mark.parametrize("missing_name", ["chapter_01_timing.json", "chapter_01.mp3"])
def test_build_rejects_missing_audio_inputs_without_replacing_output(tmp_path, missing_name):
    book_path, manifest_path, audio_dir, _ = write_inputs(tmp_path)
    (audio_dir / "chapter_01" / missing_name).unlink()
    output = tmp_path / "daisy"
    output.mkdir()
    (output / "sentinel").write_text("keep", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match=missing_name):
        build_daisy(book_path, manifest_path, audio_dir, output, "chapter_01")

    assert [path.name for path in output.iterdir()] == ["sentinel"]


@pytest.mark.parametrize("failure", ["id", "order", "duplicate"])
def test_rejects_manifest_timing_mismatches(failure):
    timing = sample_timing()
    if failure == "id":
        timing["units"][2]["id"] = "wrong_id"
    elif failure == "order":
        timing["units"][1], timing["units"][2] = timing["units"][2], timing["units"][1]
    else:
        timing["units"][2]["id"] = timing["units"][1]["id"]

    with pytest.raises(ValueError, match="Timing unit IDs/order|Duplicate timing unit id"):
        validate_source_relationships(sample_book(), sample_manifest(), timing, "chapter_01")