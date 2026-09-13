import pytest

from daisy_book.extract import (
    ParagraphRecord,
    build_structured_book,
    detect_chapter_markers,
    image_needs_alt_review,
)
from daisy_book.epub import EpubBook, EpubDocument, EpubMetadata


def sample_html(chapter_count: int = 20) -> bytes:
    paragraphs = [
        '<p class="block_"><img src="images/cover.jpg" alt="Image"></p>',
        '<p class="block_">GIỚI THIỆU</p>',
        '<p class="block_2">Mở đầu</p>',
        '<p class="block_3">Nội dung giới thiệu.</p>',
    ]
    for number in range(1, chapter_count + 1):
        paragraphs.extend(
            [
                f'<p class="block_">{number}</p>',
                f'<p class="block_">CHƯƠNG {number}</p>',
                f'<p class="block_2">Phụ đề {number}</p>',
                f'<p class="block_3">Nội dung {number}.</p>',
            ]
        )
    paragraphs.insert(8, '<p class="block_3">2</p>')
    return f"<html><body>{''.join(paragraphs)}</body></html>".encode()


def sample_book(chapter_count: int = 20) -> EpubBook:
    return EpubBook(
        metadata=EpubMetadata(
            title="Source title",
            creators=("Author",),
            authors=("Author",),
            translators=(),
            language="vi",
            identifiers=(),
        ),
        documents=(
            EpubDocument(
                id="content",
                href="EPUB/content.xhtml",
                media_type="application/xhtml+xml",
                content=sample_html(chapter_count),
            ),
        ),
        opf_path="EPUB/book.opf",
    )


def test_detects_introduction_and_exactly_20_chapters():
    structured = build_structured_book(
        sample_book(),
        {
            "title": "Final title",
            "creator": "Morgan Housel",
            "translator": "Hoàng Thị Minh Phúc",
            "language": "vi",
        },
    )

    assert structured["metadata"]["title"] == "Final title"
    assert structured["sections"][0]["id"] == "introduction"
    assert structured["sections"][0]["blocks"][0] == {
        "type": "image",
        "src": "EPUB/images/cover.jpg",
        "alt": "Image",
        "needs_alt_review": True,
    }
    chapters = [section for section in structured["sections"] if section["type"] == "chapter"]
    assert [chapter["number"] for chapter in chapters] == list(range(1, 21))
    assert chapters[0]["id"] == "chapter_01"
    assert chapters[0]["blocks"][0]["display_text"] == "Nội dung 1."


def test_rejects_any_count_other_than_20():
    with pytest.raises(ValueError, match="Expected 20 numbered chapters, found 19"):
        build_structured_book(sample_book(19), {})


def test_chapter_pattern_requires_title_and_subtitle_classes():
    records = [
        ParagraphRecord(("block_",), str(number), ())
        for number in range(1, 21)
    ]

    with pytest.raises(ValueError, match="found 0"):
        detect_chapter_markers(records)


def test_accepts_alternate_subtitle_style_used_by_source():
    records = []
    for number in range(1, 21):
        records.extend(
            [
                ParagraphRecord(("block_",), str(number), ()),
                ParagraphRecord(("block_",), f"CHƯƠNG {number}", ()),
                ParagraphRecord(("block_10" if number == 4 else "block_2",), "Phụ đề", ()),
            ]
        )

    assert [marker.number for marker in detect_chapter_markers(records)] == list(range(1, 21))


@pytest.mark.parametrize("alt", ["", "Image", "undefined", "image-ABC123.jpg", "cover.png"])
def test_useless_image_alt_requires_review(alt: str):
    assert image_needs_alt_review(alt)


def test_descriptive_image_alt_does_not_require_review():
    assert not image_needs_alt_review("Biểu đồ tăng trưởng lãi kép")