from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


CHAPTER_RE = re.compile(r"^(?:chương|chapter)\s+([0-9ivxlcdm]+)\b", re.IGNORECASE)


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


def chunk_text(text: str, max_chars: int = 2500) -> list[str]:
    """Split text conservatively without cutting words when possible."""
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
