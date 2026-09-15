from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


CHAPTER_RE = re.compile(r"^(?:chương|chapter)\s+([0-9ivxlcdm]+)\b", re.IGNORECASE)
CHAPTER_TTS_PREFIX_RE = re.compile(r"^(Chương\s+[^.]+\.\s*)(.*)$", re.IGNORECASE)
NUMBER_RE = r"\d+(?:[.,]\d+)*"

_MILLION_WORDS = {
    0: "không",
    1: "một",
    2: "hai",
    3: "ba",
    4: "bốn",
    5: "năm",
    6: "sáu",
    7: "bảy",
    8: "tám",
    9: "chín",
}
_TENS_WORDS = {
    2: "hai mươi",
    3: "ba mươi",
    4: "bốn mươi",
    5: "năm mươi",
    6: "sáu mươi",
    7: "bảy mươi",
    8: "tám mươi",
    9: "chín mươi",
}
_MEASUREMENT_UNITS = {
    "cm": "xen-ti-mét",
    "kg": "ki-lô-gam",
    "gb": "ghi-ga-bai",
    "m2": "mét vuông",
    "m²": "mét vuông",
}


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    paragraphs: list[str]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def looks_like_chapter_heading(text: str, style_name: str | None = None) -> bool:
    style = (style_name or "").lower().replace("_", " ")
    if style in {"heading 1", "title 1"}:
        return True
    return bool(CHAPTER_RE.match(normalize_text(text)))


def apply_pronunciation_map(text: str, replacements: dict[str, str]) -> str:
    result = text
    for source in sorted(replacements, key=len, reverse=True):
        result = result.replace(source, replacements[source])
    return result


def _is_predominantly_uppercase(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and sum(character.isupper() for character in letters) / len(letters) >= 0.8


def _sentence_case(text: str) -> str:
    lowered = text.lower()
    for index, character in enumerate(lowered):
        if character.isalpha():
            return lowered[:index] + character.upper() + lowered[index + 1 :]
    return lowered


def _normalize_heading_case(text: str) -> str:
    prefix_match = CHAPTER_TTS_PREFIX_RE.match(text)
    if prefix_match:
        prefix, title = prefix_match.groups()
        if _is_predominantly_uppercase(title):
            return prefix + _sentence_case(title)
        return text
    if _is_predominantly_uppercase(text):
        return _sentence_case(text)
    return text


def _read_0_99(value: int) -> str:
    if value < 10:
        return _MILLION_WORDS[value]
    if value < 20:
        words = ["mười", "mười một", "mười hai", "mười ba", "mười bốn", "mười lăm", "mười sáu", "mười bảy", "mười tám", "mười chín"]
        return words[value - 10]
    tens, units = divmod(value, 10)
    tens_word = _TENS_WORDS[tens]
    if units == 0:
        return tens_word
    if units == 1:
        return f"{tens_word} mốt"
    if units == 5:
        return f"{tens_word} lăm"
    return f"{tens_word} {_MILLION_WORDS[units]}"


def _read_0_999(value: int) -> str:
    if value < 100:
        return _read_0_99(value)
    hundreds, remainder = divmod(value, 100)
    if remainder == 0:
        return f"{_MILLION_WORDS[hundreds]} trăm"
    if remainder < 10:
        return f"{_MILLION_WORDS[hundreds]} trăm lẻ {_read_0_99(remainder)}"
    return f"{_MILLION_WORDS[hundreds]} trăm {_read_0_99(remainder)}"


def _read_integer_words(value: int) -> str:
    if value == 0:
        return "không"

    groups: list[int] = []
    while value > 0:
        groups.append(value % 1000)
        value //= 1000

    groups.reverse()
    scale_names = ["", "nghìn", "triệu", "tỷ"]
    parts: list[str] = []

    for index, group in enumerate(groups):
        if group == 0:
            continue
        scale_index = len(groups) - index - 1
        word = _read_0_999(group)
        if scale_index > 0 and scale_index < len(scale_names):
            word = f"{word} {scale_names[scale_index]}"
        parts.append(word)

    return " ".join(parts)


def _normalize_decimal_number(integer_part: str, fractional_part: str) -> str:
    whole = _read_integer_words(int(integer_part)) if integer_part and integer_part != "0" else "không"
    digits = " ".join(_MILLION_WORDS[int(digit)] for digit in fractional_part)
    return f"{whole} phẩy {digits}"


def _normalize_number(number: str) -> str:
    number = number.strip().replace(" ", "")
    if not number:
        return ""

    if "." in number:
        groups = number.split(".")
        if len(groups) > 1 and all(group.isdigit() for group in groups) and all(len(group) == 3 for group in groups[1:]):
            return _read_integer_words(int("".join(groups)))
        if len(groups) == 2 and all(group.isdigit() for group in groups):
            return _normalize_decimal_number(groups[0], groups[1])

    if "," in number:
        groups = number.split(",")
        if len(groups) == 2 and all(group.isdigit() for group in groups):
            return _normalize_decimal_number(groups[0], groups[1])

    if number.isdigit():
        return _read_integer_words(int(number))

    return number


def _normalize_measurement_unit(unit: str) -> str:
    key = unit.lower()
    if key in _MEASUREMENT_UNITS:
        return _MEASUREMENT_UNITS[key]
    return unit


def _normalize_measurement_units(text: str) -> str:
    def replace_attached(match: re.Match[str]) -> str:
        number = match.group("number")
        unit = match.group("unit")
        if number:
            return f"{_normalize_number(number)} {_normalize_measurement_unit(unit)}"
        return _normalize_measurement_unit(unit)

    text = re.sub(
        r"(?P<number>\d+(?:[.,]\d+)*)\s*(?P<unit>cm|kg|GB|m2|m²)",
        replace_attached,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<![A-Za-zÀ-ỹ])(?P<unit>cm|kg|GB|m2|m²)(?![A-Za-zÀ-ỹ])",
        lambda match: _normalize_measurement_unit(match.group("unit")),
        text,
        flags=re.IGNORECASE,
    )
    return text


def _normalize_unicode_fractions(text: str) -> str:
    mapping = {
        "¼": "một phần tư",
        "½": "một phần hai",
        "¾": "ba phần tư",
        "⅐": "một phần bảy",
        "⅑": "một phần chín",
        "⅓": "một phần ba",
        "⅔": "hai phần ba",
        "⅛": "một phần tám",
        "⅜": "ba phần tám",
        "⅝": "năm phần tám",
        "⅞": "bảy phần tám",
    }
    for source, replacement in mapping.items():
        text = text.replace(source, replacement)
    return text


def _normalize_phone_numbers(text: str) -> str:
    def replace_phone(match: re.Match[str]) -> str:
        digits = match.group(0).replace("-", "")
        prefix = " ".join(_MILLION_WORDS[int(digit)] for digit in digits[:3])
        suffix = " ".join(_MILLION_WORDS[int(digit)] for digit in digits[3:])
        return f"{prefix}, {suffix}"

    return re.sub(r"(?<!\d)\d{3}-\d{4}(?!\d)", replace_phone, text)


def _normalize_401k(text: str) -> str:
    return re.sub(
        r"(?<!\w)\d{3}\s*\(\s*k\s*\)(?!\w)",
        "bốn không một k",
        text,
        flags=re.IGNORECASE,
    )


def _normalize_special_slash_expressions(text: str) -> str:
    text = re.sub(r"(?<!\w)24/7(?!\w)", "hai mươi bốn giờ một ngày, bảy ngày một tuần", text)
    text = re.sub(r"(?<!\w)11/9(?!\w)", "ngày mười một tháng chín", text)
    text = re.sub(r"(?<!\w)50/50(?!\w)", "năm mươi năm mươi", text)
    return text


def _normalize_fraction_expressions(text: str) -> str:
    fraction_map = {
        (1, 2): "một phần hai",
        (1, 3): "một phần ba",
        (2, 3): "hai phần ba",
        (1, 4): "một phần tư",
        (3, 4): "ba phần tư",
        (1, 5): "một phần năm",
        (1, 6): "một phần sáu",
        (1, 8): "một phần tám",
        (3, 8): "ba phần tám",
        (1, 10): "một phần mười",
    }

    def replace_fraction(match: re.Match[str]) -> str:
        numerator_text = match.group("numerator")
        denominator_text = match.group("denominator")
        numerator = int(numerator_text)
        denominator = int(denominator_text)
        if (numerator, denominator) in fraction_map:
            return fraction_map[(numerator, denominator)]
        return match.group(0)

    return re.sub(
        r"(?<!\w)(?P<numerator>\d+)\s*/\s*(?P<denominator>\d+)(?!\w)",
        replace_fraction,
        text,
    )


def _normalize_multiplicative_expressions(text: str) -> str:
    def replace_range(match: re.Match[str]) -> str:
        start = _normalize_number(match.group("start"))
        end = _normalize_number(match.group("end"))
        return f"gấp {start} đến {end} lần"

    text = re.sub(
        r"(?P<start>\d+(?:[.,]\d+)*)x\s*(?:–|-)\s*(?P<end>\d+(?:[.,]\d+)*)x",
        replace_range,
        text,
    )

    def replace_single(match: re.Match[str]) -> str:
        return f"gấp {_normalize_number(match.group('value'))} lần"

    return re.sub(
        r"(?<!\w)(?P<value>\d+(?:[.,]\d+)*)x(?!\w)",
        replace_single,
        text,
    )


def _normalize_math_expressions(text: str) -> str:
    text = re.sub(
        r"(?P<left>\d+(?:[.,]\d+)*)\s*\+\s*(?P<right>\d+(?:[.,]\d+)*)",
        lambda match: f"{_normalize_number(match.group('left'))} cộng {_normalize_number(match.group('right'))}",
        text,
    )
    return re.sub(
        r"(?P<left>\d+(?:[.,]\d+)*)\s*×\s*(?P<right>\d+(?:[.,]\d+)*)",
        lambda match: f"{_normalize_number(match.group('left'))} nhân {_normalize_number(match.group('right'))}",
        text,
    )


def _normalize_numeric_ranges(text: str) -> str:
    def replace_range(match: re.Match[str]) -> str:
        start = _normalize_number(match.group("start"))
        end = _normalize_number(match.group("end"))
        suffix = " độ C" if match.group("temp") else ""
        return f"từ {start} đến {end}{suffix}"

    return re.sub(
        r"(?<!\w)(?P<start>\d+(?:[.,]\d+)*)\s*(?:–|—|-)\s*(?P<end>\d+(?:[.,]\d+)*)(?P<temp>\s*°C)?(?!\w)",
        replace_range,
        text,
    )


def _normalize_temperature(text: str) -> str:
    return re.sub(
        r"(?P<number>\d+(?:[.,]\d+)*)\s*°C",
        lambda match: f"{_normalize_number(match.group('number'))} độ C",
        text,
    )


def _normalize_currency_rates(text: str) -> str:
    def replace_rate(match: re.Match[str]) -> str:
        value = _normalize_number(match.group("number"))
        period = match.group("period")
        return f"{value} đô la mỗi {period}"

    return re.sub(
        r"\$(?P<number>\d+(?:[.,]\d+)*)\s*/\s*(?P<period>tháng|năm|tuần|ngày)",
        replace_rate,
        text,
    )


def _apply_exact_heading_override(text: str, replacements: dict[str, str]) -> str:
    if text in replacements:
        return replacements[text]

    prefix_match = CHAPTER_TTS_PREFIX_RE.match(text)
    if not prefix_match:
        return text
    prefix, title = prefix_match.groups()
    title_without_end = title.rstrip(".!?…")
    ending = title[len(title_without_end) :]
    if title_without_end in replacements:
        return prefix + replacements[title_without_end] + ending
    return text


def normalize_for_tts(
    text: str,
    *,
    unit_type: str | None = None,
    pronunciation: dict[str, str] | None = None,
) -> str:
    """Normalize visible text conservatively for Vietnamese speech rendering."""
    replacements = pronunciation or {}
    result = normalize_text(text)
    if unit_type in {"heading", "title", "subtitle"}:
        result = _apply_exact_heading_override(result, replacements)
        result = _normalize_heading_case(result)

    result = re.sub(r"(?<=\s)&(?=\s)", "và", result)
    result = _normalize_unicode_fractions(result)
    result = _normalize_phone_numbers(result)
    result = _normalize_401k(result)
    result = _normalize_special_slash_expressions(result)
    result = _normalize_fraction_expressions(result)
    result = _normalize_measurement_units(result)
    result = _normalize_currency_rates(result)
    result = _normalize_multiplicative_expressions(result)
    result = _normalize_math_expressions(result)
    result = _normalize_numeric_ranges(result)
    result = _normalize_temperature(result)
    result = re.sub(
        rf"\$(?P<number>{NUMBER_RE})",
        lambda match: f"{_normalize_number(match.group('number'))} đô la",
        result,
    )
    result = re.sub(
        rf"(?P<number>{NUMBER_RE})%",
        lambda match: f"{_normalize_number(match.group('number'))} phần trăm",
        result,
    )
    result = re.sub(
        rf"(?<![\w.,])({NUMBER_RE})(?![\w.,(])",
        lambda match: _normalize_number(match.group(1)),
        result,
    )
    result = apply_pronunciation_map(result, replacements)
    return normalize_text(result)


def chunk_text(text: str, max_chars: int = 2500) -> list[str]:
    """Split text conservatively without cutting words when possible."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut <= 0:
                cut = max_chars
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        current = sentence

    if current:
        chunks.append(current)
    return chunks
