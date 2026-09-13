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
                "title": "Chương một",
                "subtitle": "Phụ đề",
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

    paragraph = manifest["sections"][0]["paragraphs"][0]
    assert paragraph == {
        "id": "chapter_01_p0001",
        "display_text": original,
        "tts_text": "Mo-gân Hao-sồ viết sách.",
    }
    assert len(manifest["sections"][0]["paragraphs"]) == 1


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
    assert written["sections"][0]["paragraphs"][0]["tts_text"] == "Tên tác giả viết sách."


def test_rejects_duplicate_paragraph_ids():
    book = sample_book()
    book["sections"][0]["blocks"].append(dict(book["sections"][0]["blocks"][1]))

    with pytest.raises(ValueError, match="Duplicate paragraph id: chapter_01_p0001"):
        prepare_manifest(book, {})


def test_rejects_pronunciation_that_removes_all_tts_text():
    with pytest.raises(ValueError, match="empty tts_text after pronunciation rules"):
        prepare_manifest(sample_book(), {"Morgan Housel viết sách.": ""})