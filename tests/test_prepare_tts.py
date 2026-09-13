import json

import pytest

from daisy_book.prepare_tts import prepare_manifest, prepare_tts


def sample_book():
    return {
        "metadata": {"title": "Sách", "language": "vi"},
        "sections": [
            {
                "id": "chapter_01",
                "type": "chapter",
                "number": 1,
                "title": "KHÔNG AI ĐIÊN",
                "subtitle": "Phụ đề của Morgan Housel",
                "blocks": [
                    {"type": "image", "src": "image.png", "alt": "Image"},
                    {
                        "id": "chapter_01_p0001",
                        "type": "paragraph",
                        "display_text": "  Morgan Housel  viết sách. ",
                    },
                ],
            }
        ],
    }


def test_prepares_manifest_without_changing_display_text():
    book = sample_book()
    original = book["sections"][0]["blocks"][1]["display_text"]

    manifest = prepare_manifest(book, {"Morgan Housel": "Mo-gân Hao-sồ"})

    heading, subtitle, paragraph = manifest["sections"][0]["units"]
    assert [heading["id"], subtitle["id"], paragraph["id"]] == [
        "chapter_01_title",
        "chapter_01_subtitle",
        "chapter_01_p0001",
    ]
    assert [heading["type"], subtitle["type"], paragraph["type"]] == [
        "heading",
        "subtitle",
        "paragraph",
    ]
    assert heading == {
        "id": "chapter_01_title",
        "type": "heading",
        "display_text": "KHÔNG AI ĐIÊN",
        "tts_text": "Chương 1. Không ai điên.",
    }
    assert subtitle == {
        "id": "chapter_01_subtitle",
        "type": "subtitle",
        "display_text": "Phụ đề của Morgan Housel",
        "tts_text": "Phụ đề của Mo-gân Hao-sồ",
    }
    assert paragraph == {
        "id": "chapter_01_p0001",
        "type": "paragraph",
        "display_text": original,
        "tts_text": "Mo-gân Hao-sồ viết sách.",
    }


def test_writes_manifest_using_pronunciation_file(tmp_path):
    book_path = tmp_path / "book.json"
    output_path = tmp_path / "tts" / "manifest.json"
    pronunciation_path = tmp_path / "pronunciation.yaml"
    book_path.write_text(json.dumps(sample_book(), ensure_ascii=False), encoding="utf-8")
    pronunciation_path.write_text(
        'replacements:\n  "Morgan Housel": "Tên tác giả"\n',
        encoding="utf-8",
    )

    prepare_tts(book_path, output_path, pronunciation_path)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    heading, subtitle, paragraph = written["sections"][0]["units"]
    assert heading["display_text"] == "KHÔNG AI ĐIÊN"
    assert subtitle["display_text"] == "Phụ đề của Morgan Housel"
    assert subtitle["tts_text"] == "Phụ đề của Tên tác giả"
    assert paragraph["display_text"] == "  Morgan Housel  viết sách. "
    assert paragraph["tts_text"] == "Tên tác giả viết sách."


def test_introduction_heading_does_not_get_chapter_zero():
    book = sample_book()
    section = book["sections"][0]
    section.update({"id": "introduction", "type": "introduction", "number": 0, "title": "GIỚI THIỆU"})

    heading = prepare_manifest(book, {})["sections"][0]["units"][0]

    assert heading["id"] == "introduction_title"
    assert heading["tts_text"] == "Giới thiệu"
    assert "Chương 0" not in heading["tts_text"]


def test_missing_subtitle_does_not_create_empty_unit():
    book = sample_book()
    del book["sections"][0]["subtitle"]

    units = prepare_manifest(book, {})["sections"][0]["units"]

    assert [unit["id"] for unit in units] == ["chapter_01_title", "chapter_01_p0001"]
    assert all(unit["tts_text"] for unit in units)


def test_missing_title_does_not_create_empty_unit():
    book = sample_book()
    del book["sections"][0]["title"]

    units = prepare_manifest(book, {})["sections"][0]["units"]

    assert [unit["id"] for unit in units] == ["chapter_01_subtitle", "chapter_01_p0001"]
    assert all(unit["tts_text"] for unit in units)


def test_rejects_duplicate_unit_ids():
    book = sample_book()
    book["sections"][0]["blocks"][1]["id"] = "chapter_01_title"

    with pytest.raises(ValueError, match="Duplicate unit id: chapter_01_title"):
        prepare_manifest(book, {})


def test_rejects_pronunciation_that_removes_all_tts_text():
    with pytest.raises(ValueError, match="empty tts_text after pronunciation rules"):
        prepare_manifest(sample_book(), {"Morgan Housel viết sách.": ""})