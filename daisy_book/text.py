from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


CHAPTER_RE = re.compile(r"^(?:chương|chapter)\s+([0-9ivxlcdm]+)\b", re.IGNORECASE)
CHAPTER_TTS_PREFIX_RE = re.compile(r"^(Chương\s+[^.]+\.\s*)(.*)$", re.IGNORECASE)
NUMBER_RE = r"\d+(?:[.,]\d+)*"


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


def _normalize_number(number: str) -> str:
    if "." in number:
        groups = number.split(".")
        if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
            return "".join(groups)
        if len(groups) == 2:
            return f"{groups[0]} phẩy {groups[1]}"
    if number.count(",") == 1:
        whole, decimal = number.split(",")
        return f"{whole} phẩy {decimal}"
    return number


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
        rf"(?<![\w.,])({NUMBER_RE})(?![\w.,])",
        lambda match: _normalize_number(match.group(1)),
        result,
    )
    result = re.sub(r"(?<=\d)(GB|kg)\b", r" \1", result)
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
