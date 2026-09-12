from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def load_book_config(path: str | Path = "config/book.yaml") -> dict[str, Any]:
    data = load_yaml(path)
    return data.get("book", {})


def load_tts_config(path: str | Path = "config/book.yaml") -> dict[str, Any]:
    data = load_yaml(path)
    return data.get("tts", {})


def load_pronunciation_map(path: str | Path = "config/pronunciation.yaml") -> dict[str, str]:
    data = load_yaml(path)
    replacements = data.get("replacements", {})
    if not isinstance(replacements, dict):
        raise ValueError("replacements must be a mapping")
    return {str(k): str(v) for k, v in replacements.items()}
