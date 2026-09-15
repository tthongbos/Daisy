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
        ("0", "không"),
        ("4", "bốn"),
        ("14", "mười bốn"),
        ("40", "bốn mươi"),
        ("140", "một trăm bốn mươi"),
        ("145", "một trăm bốn mươi lăm"),
        ("3.000", "ba nghìn"),
        (
            "134.217.728",
            "một trăm ba mươi bốn triệu hai trăm mười bảy nghìn bảy trăm hai mươi tám",
        ),
        ("84.5", "tám mươi bốn phẩy năm"),
        ("0.25", "không phẩy hai năm"),
        (
            "0.000000001",
            "không phẩy không không không không không không không không một",
        ),
        ("140%", "một trăm bốn mươi phần trăm"),
        (
            "0,00000001%",
            "không phẩy không không không không không không không một phần trăm",
        ),
        ("$3.000", "ba nghìn đô la"),
        ("$0.25", "không phẩy hai năm đô la"),
        ("180kg", "một trăm tám mươi ki-lô-gam"),
        ("1GB", "một ghi-ga-bai"),
        ("vài cm", "vài xen-ti-mét"),
        ("5cm", "năm xen-ti-mét"),
        ("1.670 m2", "một nghìn sáu trăm bảy mươi mét vuông"),
    ],
)
def test_normalize_for_tts_speaks_numbers_and_units_in_vietnamese(source, expected):
    assert normalize_for_tts(source) == expected


def test_140_is_not_left_for_azure_to_guess():
    result = normalize_for_tts("mức tăng 140%")
    assert result == "mức tăng một trăm bốn mươi phần trăm"
    assert "140" not in result


def test_prepare_manifest_keeps_display_text_while_normalizing_tts():
    source = "Mức tăng 140% và dày vài cm."
    manifest = {
        "metadata": {"title": "Test"},
        "sections": [
            {
                "id": "s1",
                "type": "chapter",
                "number": "1",
                "title": "Giới thiệu",
                "blocks": [{"id": "b1", "type": "paragraph", "display_text": source}],
            }
        ],
    }

    prepared = __import__("daisy_book.prepare_tts", fromlist=["prepare_manifest"]).prepare_manifest(manifest, {})
    unit = next(unit for unit in prepared["sections"][0]["units"] if unit["id"] == "b1")
    assert unit["display_text"] == source
    assert unit["tts_text"] == "Mức tăng một trăm bốn mươi phần trăm và dày vài xen-ti-mét."


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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("140%", "một trăm bốn mươi phần trăm"),
        ("0.000000001", "không phẩy không không không không không không không không một"),
        ("vài cm", "vài xen-ti-mét"),
        ("180kg", "một trăm tám mươi ki-lô-gam"),
        ("1.670 m2", "một nghìn sáu trăm bảy mươi mét vuông"),
        ("1GB", "một ghi-ga-bai"),
        ("1/4", "một phần tư"),
        ("3/4", "ba phần tư"),
        ("⅓", "một phần ba"),
        ("24/7", "hai mươi bốn giờ một ngày, bảy ngày một tuần"),
        ("11/9", "ngày mười một tháng chín"),
        ("50/50", "năm mươi năm mươi"),
        ("10x", "gấp mười lần"),
        ("10x – 20x", "gấp mười đến hai mươi lần"),
        ("8 + 8", "tám cộng tám"),
        ("8 × 8", "tám nhân tám"),
        ("37.7–40°C", "từ ba mươi bảy phẩy bảy đến bốn mươi độ C"),
        ("525-7851", "năm hai năm, bảy tám năm một"),
    ],
)
def test_normalize_for_tts_handles_special_symbolic_expressions(source, expected):
    assert normalize_for_tts(source) == expected


def test_normalize_for_tts_leaves_ordinary_english_alone():
    assert normalize_for_tts("Bill Gates dùng Gmail.") == "Bill Gates dùng Gmail."
    assert normalize_for_tts("CEO của IBM") == "CEO của IBM"
    assert normalize_for_tts("Warren Buffett") == "Warren Buffett"
    assert normalize_for_tts("Wi-Fi") == "Wi-Fi"


def test_prepare_manifest_keeps_display_text_when_special_symbols_are_normalized():
    source = "Bill Gates nói mức tăng 140%, căn phòng rộng 90m2."
    manifest = {
        "metadata": {"title": "Test"},
        "sections": [
            {
                "id": "s1",
                "type": "chapter",
                "number": "1",
                "title": "Giới thiệu",
                "blocks": [{"id": "b1", "type": "paragraph", "display_text": source}],
            }
        ],
    }

    prepared = __import__("daisy_book.prepare_tts", fromlist=["prepare_manifest"]).prepare_manifest(manifest, {})
    unit = next(unit for unit in prepared["sections"][0]["units"] if unit["id"] == "b1")
    assert unit["display_text"] == source
    assert unit["tts_text"] == "Bill Gates nói mức tăng một trăm bốn mươi phần trăm, căn phòng rộng chín mươi mét vuông."


def test_chunk_text_respects_limit_for_normal_words():
    chunks = chunk_text("Câu một. Câu hai. Câu ba.", max_chars=15)
    assert chunks
    assert all(len(chunk) <= 15 for chunk in chunks)


def test_chunk_text_rejects_nonpositive_limit():
    with pytest.raises(ValueError, match="max_chars must be positive"):
        chunk_text("Nội dung", max_chars=0)
