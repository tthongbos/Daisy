import json

from daisy_book.audit_tts import audit_manifest, write_audit
from daisy_book.text import normalize_for_tts


def sample_manifest():
    display_text = "NASA ghi nhận 84.5, 99.9%, $3.000, 3/4, 180kg, 401(k) và Roth IRA."
    return {
        "metadata": {"title": "Sách"},
        "sections": [
            {
                "id": "chapter_01",
                "units": [
                    {
                        "id": "chapter_01_p0001",
                        "type": "paragraph",
                        "display_text": display_text,
                        "tts_text": normalize_for_tts(display_text),
                    },
                    {
                        "id": "chapter_01_p0002",
                        "type": "paragraph",
                        "display_text": "Warrant Buffet từng viết như vậy.",
                        "tts_text": "Warrant Buffet từng viết như vậy.",
                    },
                ],
            }
        ],
    }


def test_audit_reports_risky_and_transformed_tokens():
    report = audit_manifest(sample_manifest())
    found = {(issue["category"], issue["token"]) for issue in report["issues"]}

    assert report["summary"]["sections"] == 1
    assert report["summary"]["units"] == 2
    assert ("acronym", "NASA") in found
    assert ("acronym", "401(k)") in found
    assert ("acronym", "Roth IRA") in found
    assert ("decimal", "84.5") in found
    assert ("percent", "99.9%") in found
    assert ("currency", "$3.000") in found
    assert ("slash_expression", "3/4") in found
    assert ("attached_unit", "180kg") in found
    assert ("suspicious_source_text", "Warrant Buffet") in found
    assert all(len(issue["display_text"]) <= 160 for issue in report["issues"])


def test_audit_does_not_report_an_acronym_removed_by_pronunciation_mapping():
    manifest = sample_manifest()
    unit = manifest["sections"][0]["units"][0]
    unit["tts_text"] = unit["tts_text"].replace("NASA", "Na-sa")

    report = audit_manifest(manifest)

    assert not any(
        issue["category"] == "acronym" and issue["token"] == "NASA"
        for issue in report["issues"]
    )


def test_write_audit_creates_json_report(tmp_path):
    output_path = tmp_path / "tts" / "audit.json"

    report = write_audit(sample_manifest(), output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == report