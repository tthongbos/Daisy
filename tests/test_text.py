import pytest

from daisy_book.text import (
    apply_pronunciation_map,
    chunk_text,
    looks_like_chapter_heading,
    normalize_for_tts,
    normalize_text,
)


def test_normalize_text():
    assert normalize_text("  Xin   chào  ! ") == "Xin chào!"


def test_heading_detection():
    assert looks_like_chapter_heading("Chương 1: Không ai điên")
    assert looks_like_chapter_heading("Một tiêu đề", "Heading 1")
    assert not looks_like_chapter_heading("Một đoạn văn bình thường", "Normal")


def test_pronunciation_mapping_keeps_unmapped_text():
    text = "Morgan Housel viết về tiền."
    assert apply_pronunciation_map(text, {"Morgan Housel": "Mo-gân Hao-sồ"}) == "Mo-gân Hao-sồ viết về tiền."


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("KHÔNG AI ĐIÊN", "Không ai điên"),
        ("MAY MẮN & RỦI RO", "May mắn và rủi ro"),
    ],
)
def test_normalize_for_tts_sentence_cases_all_caps_headings(source, expected):
    assert normalize_for_tts(source, unit_type="heading") == expected


def test_normalize_for_tts_does_not_lowercase_body_text():
    assert normalize_for_tts("Không ai điên.", unit_type="paragraph") == "Không ai điên."


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("84.5", "84 phẩy 5"),
        ("3.000", "3000"),
        ("134.217.728", "134217728"),
        ("99.9%", "99 phẩy 9 phần trăm"),
        ("0,00000001%", "0 phẩy 00000001 phần trăm"),
        ("$3.000", "3000 đô la"),
        ("$0.25", "0 phẩy 25 đô la"),
        ("180kg", "180 kg"),
        ("1GB", "1 GB"),
    ],
)
def test_normalize_for_tts_handles_safe_numeric_forms(source, expected):
    assert normalize_for_tts(source) == expected


def test_normalize_for_tts_preserves_normal_vietnamese_punctuation():
    source = "Anh nói: “Không, tôi không nghĩ vậy!”"
    assert normalize_for_tts(source) == source


@pytest.mark.parametrize(
    ("source", "spoken"),
    [
        ("KIẾM TIỀN >< GIỮ TIỀN", "Kiếm tiền khác với giữ tiền"),
        ("HỢP LÝ > CÓ LÝ", "Hợp lý quan trọng hơn có lý"),
    ],
)
def test_normalize_for_tts_uses_exact_phrase_override_before_symbol_handling(source, spoken):
    assert normalize_for_tts(
        source,
        unit_type="heading",
        pronunciation={source: spoken},
    ) == spoken


def test_chunk_text_respects_limit_for_normal_words():
    chunks = chunk_text("Câu một. Câu hai. Câu ba.", max_chars=15)
    assert chunks
    assert all(len(chunk) <= 15 for chunk in chunks)


def test_chunk_text_rejects_nonpositive_limit():
    with pytest.raises(ValueError, match="max_chars must be positive"):
        chunk_text("Nội dung", max_chars=0)
