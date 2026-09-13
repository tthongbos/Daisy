from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


CATEGORIES = (
    "all_caps",
    "acronym",
    "decimal",
    "percent",
    "currency",
    "slash_expression",
    "attached_unit",
    "unusual_symbol",
    "suspicious_source_text",
    "unmapped_foreign_token",
)
KNOWN_RISKY_TOKENS = (
    "S&P 500",
    "Roth IRA",
    "401(k)",
    "ARPANET",
    "GEICO",
    "NAFTA",
    "CNBC",
    "NASA",
    "MBA",
    "JFK",
    "NYU",
    "LHQ",
    "SEC",
    "CEO",
    "IRA",
    "GDP",
    "IBM",
    "MPG",
    "AWS",
    "SUV",
    "NIH",
    "ICU",
    "ROI",
    "IRS",
    "USC",
    "P&G",
    "TV",
    "VC",
    "GE",
    "PC",
    "UC",
    "JP",
    "DC",
    "GS",
    "GB",
)
SUSPICIOUS_SOURCE_TEXT = (
    "Warrant Buffet",
    "Bill Gate",
    "nữa số lần",
    "quan trong",
    "Marc Andreesen",
)
NUMBER_PATTERN = r"\d+(?:[.,]\d+)*"
DECIMAL_RE = re.compile(rf"\b{NUMBER_PATTERN}\b")
PERCENT_RE = re.compile(rf"{NUMBER_PATTERN}%")
CURRENCY_RE = re.compile(rf"\${NUMBER_PATTERN}")
SLASH_RE = re.compile(r"\b\d+/\d+\b")
ATTACHED_UNIT_RE = re.compile(rf"{NUMBER_PATTERN}(?:GB|kg)\b")
ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")
FOREIGN_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))+\b")
UNUSUAL_SYMBOL_RE = re.compile(r"><|[<>]")


def _is_decimal(token: str) -> bool:
    if "," in token:
        return token.count(",") == 1
    if "." not in token:
        return False
    groups = token.split(".")
    return not (len(groups) > 1 and all(len(group) == 3 for group in groups[1:]))


def _is_predominantly_uppercase(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and sum(character.isupper() for character in letters) / len(letters) >= 0.8


def _excerpt(text: str, token: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    index = text.find(token)
    if index < 0:
        return text[: limit - 3].rstrip() + "..."
    start = max(0, index - (limit - len(token)) // 2)
    end = min(len(text), start + limit)
    start = max(0, end - limit)
    excerpt = text[start:end]
    if start:
        excerpt = "..." + excerpt[3:]
    if end < len(text):
        excerpt = excerpt[:-3] + "..."
    return excerpt


def _known_unmapped_tokens(display_text: str, tts_text: str) -> Iterator[str]:
    occupied: list[tuple[int, int]] = []
    for token in KNOWN_RISKY_TOKENS:
        for match in re.finditer(re.escape(token), display_text):
            occupied.append(match.span())
            if token in tts_text:
                yield token
    for match in ACRONYM_RE.finditer(display_text):
        if any(start <= match.start() and match.end() <= end for start, end in occupied):
            continue
        if match.group() in tts_text:
            yield match.group()


def audit_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sections = manifest.get("sections")
    if not isinstance(sections, list):
        raise ValueError("TTS manifest sections must be a list")

    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    unit_count = 0

    def add_issue(
        section_id: str,
        unit_id: str,
        category: str,
        token: str,
        display_text: str,
        tts_text: str,
    ) -> None:
        key = (unit_id, category, token)
        if key in seen:
            return
        seen.add(key)
        issues.append(
            {
                "section_id": section_id,
                "unit_id": unit_id,
                "category": category,
                "token": token,
                "display_text": _excerpt(display_text, token),
                "tts_text": _excerpt(tts_text, token),
            }
        )

    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("id", ""))
        units = section.get("units", [])
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            unit_count += 1
            unit_id = str(unit.get("id", ""))
            display_text = str(unit.get("display_text", ""))
            tts_text = str(unit.get("tts_text", ""))
            unit_type = unit.get("type")

            if unit_type in {"heading", "subtitle"} and _is_predominantly_uppercase(tts_text):
                add_issue(section_id, unit_id, "all_caps", tts_text, display_text, tts_text)
            for token in _known_unmapped_tokens(display_text, tts_text):
                add_issue(section_id, unit_id, "acronym", token, display_text, tts_text)
            for match in DECIMAL_RE.finditer(display_text):
                if _is_decimal(match.group()):
                    add_issue(section_id, unit_id, "decimal", match.group(), display_text, tts_text)
            for category, pattern in (
                ("percent", PERCENT_RE),
                ("currency", CURRENCY_RE),
                ("slash_expression", SLASH_RE),
                ("attached_unit", ATTACHED_UNIT_RE),
            ):
                for match in pattern.finditer(display_text):
                    add_issue(section_id, unit_id, category, match.group(), display_text, tts_text)
            for match in UNUSUAL_SYMBOL_RE.finditer(display_text):
                if match.group() in tts_text:
                    add_issue(section_id, unit_id, "unusual_symbol", match.group(), display_text, tts_text)
            for token in SUSPICIOUS_SOURCE_TEXT:
                if re.search(
                    rf"(?<!\w){re.escape(token)}(?!\w)",
                    display_text,
                    re.IGNORECASE,
                ):
                    add_issue(section_id, unit_id, "suspicious_source_text", token, display_text, tts_text)
            for match in FOREIGN_NAME_RE.finditer(display_text):
                token = match.group()
                if token in tts_text:
                    add_issue(section_id, unit_id, "unmapped_foreign_token", token, display_text, tts_text)

    counts = Counter(issue["category"] for issue in issues)
    return {
        "summary": {
            "sections": len(sections),
            "units": unit_count,
            "categories": {category: counts[category] for category in CATEGORIES},
        },
        "issues": issues,
    }


def write_audit(manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    report = audit_manifest(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _print_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("TTS audit")
    print(f"sections: {summary['sections']}")
    print(f"units: {summary['units']}")
    for category, count in summary["categories"].items():
        print(f"{category}: {count}")
    tokens = sorted(
        {
            issue["token"]
            for issue in report["issues"]
            if issue["category"] in {"acronym", "unmapped_foreign_token"}
        }
    )
    if tokens:
        print("Unmapped high-risk tokens:")
        for token in tokens:
            print(f"  {token}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit prepared TTS text without calling Azure.")
    parser.add_argument("--manifest", default="build/tts/manifest.json", type=Path)
    parser.add_argument("--output", default="build/tts/audit.json", type=Path)
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("TTS manifest root must be an object")
        report = write_audit(manifest, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    _print_summary(report)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())