import pytest

from daisy_book.text import apply_pronunciation_map, chunk_text, looks_like_chapter_heading, normalize_text


def test_normalize_text():
    assert normalize_text("  Xin   chào  ! ") == "Xin chào!"


def test_heading_detection():
    assert looks_like_chapter_heading("Chương 1: Không ai điên")
    assert looks_like_chapter_heading("Một tiêu đề", "Heading 1")
    assert not looks_like_chapter_heading("Một đoạn văn bình thường", "Normal")


def test_pronunciation_mapping_keeps_unmapped_text():
    text = "Morgan Housel viết về tiền."
    assert apply_pronunciation_map(text, {"Morgan Housel": "Mo-gân Hao-sồ"}) == "Mo-gân Hao-sồ viết về tiền."


def test_chunk_text_respects_limit_for_normal_words():
    chunks = chunk_text("Câu một. Câu hai. Câu ba.", max_chars=15)
    assert chunks
    assert all(len(chunk) <= 15 for chunk in chunks)


def test_chunk_text_rejects_nonpositive_limit():
    with pytest.raises(ValueError, match="max_chars must be positive"):
        chunk_text("Nội dung", max_chars=0)
