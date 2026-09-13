import json
import sys

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from daisy_book.generate_audio import describe_dry_run, generate_section_audio, main, select_section


def sample_section():
    return {
        "id": "chapter_01",
        "type": "chapter",
        "units": [
            {
                "id": "chapter_01_title",
                "type": "heading",
                "display_text": "KHÔNG AI ĐIÊN",
                "tts_text": "Chương 1. KHÔNG AI ĐIÊN.",
            },
            {
                "id": "chapter_01_subtitle",
                "type": "subtitle",
                "display_text": "Phụ đề.",
                "tts_text": "Phụ đề.",
            },
            {
                "id": "chapter_01_p0001",
                "type": "paragraph",
                "display_text": "Đoạn một.",
                "tts_text": "Đoạn một.",
            },
            {
                "id": "chapter_01_p0002",
                "type": "paragraph",
                "display_text": "Đoạn hai.",
                "tts_text": "Đoạn hai.",
            },
        ],
    }


def test_selects_section_and_rejects_missing_section():
    manifest = {"sections": [sample_section()]}
    assert select_section(manifest, "chapter_01")["id"] == "chapter_01"
    with pytest.raises(ValueError, match="Section not found: introduction"):
        select_section(manifest, "introduction")


def test_rejects_duplicate_unit_id_before_synthesis():
    section = sample_section()
    section["units"][1]["id"] = "chapter_01_title"

    with pytest.raises(ValueError, match="Duplicate unit id: chapter_01_title"):
        generate_section_audio(section, None, "voice", "0%", 0, 2500)


def test_rejects_unsafe_output_ids_before_synthesis(tmp_path):
    section = sample_section()
    section["id"] = "../outside"

    with pytest.raises(ValueError, match=r"Unsafe section id: \.\./outside"):
        generate_section_audio(section, tmp_path, "voice", "0%", 0, 2500)


def test_dry_run_reports_chunks_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)

    result = describe_dry_run(sample_section(), max_chars=8)

    output = capsys.readouterr().out
    assert "Selected section: chapter_01" in output
    assert "Unit count: 4" in output
    assert "chapter_01_title" in output
    assert "chapter_01_subtitle" in output
    assert "chapter_01_p0001" in output
    assert result["unit_count"] == 4
    assert result["request_count"] >= 4


def test_cli_dry_run_does_not_require_credentials(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"sections": [sample_section()]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_audio", "--manifest", str(manifest_path), "--section", "chapter_01", "--dry-run"],
    )

    assert main() == 0
    assert "Unit count: 4" in capsys.readouterr().out


def test_generates_ordered_timing_and_reuses_cached_segments(tmp_path):
    calls = []

    def fake_synthesizer(ssml, output, voice):
        calls.append((ssml, voice))
        Sine(440).to_audio_segment(duration=120).export(output, format="mp3", bitrate="64k")

    section = sample_section()
    timing = generate_section_audio(
        section,
        tmp_path,
        "test-voice",
        "0%",
        pause_ms=25,
        max_chars=2500,
        synthesizer=fake_synthesizer,
    )

    section_dir = tmp_path / "chapter_01"
    assert len(calls) == 4
    assert "Chương 1. KHÔNG AI ĐIÊN." in calls[0][0]
    assert "Phụ đề." in calls[1][0]
    assert "Đoạn một." in calls[2][0]
    assert "Đoạn hai." in calls[3][0]
    assert (section_dir / "segments" / "chapter_01_title.mp3").is_file()
    assert (section_dir / "segments" / "chapter_01_subtitle.mp3").is_file()
    assert (section_dir / "segments" / "chapter_01_p0001.mp3").is_file()
    assert (section_dir / "segments" / "chapter_01_p0002.mp3").is_file()
    assert (section_dir / "chapter_01.mp3").is_file()
    written = json.loads((section_dir / "chapter_01_timing.json").read_text(encoding="utf-8"))
    assert timing == written
    timing_units = written["units"]
    assert [unit["id"] for unit in timing_units] == [unit["id"] for unit in section["units"]]
    assert [unit["type"] for unit in timing_units] == ["heading", "subtitle", "paragraph", "paragraph"]
    first = timing_units[0]
    assert first["clip_begin_ms"] == 0
    assert first["clip_end_ms"] > first["clip_begin_ms"]
    for previous, current in zip(timing_units, timing_units[1:]):
        assert current["clip_begin_ms"] >= previous["clip_end_ms"]
        assert current["clip_end_ms"] > current["clip_begin_ms"]
        assert current["duration_ms"] == current["clip_end_ms"] - current["clip_begin_ms"]
    chapter_duration = len(AudioSegment.from_file(section_dir / "chapter_01.mp3", format="mp3"))
    assert written["duration_ms"] == chapter_duration
    assert abs(timing_units[-1]["clip_end_ms"] - chapter_duration) <= 50

    generate_section_audio(
        section,
        tmp_path,
        "test-voice",
        "0%",
        pause_ms=25,
        max_chars=2500,
        synthesizer=fake_synthesizer,
    )
    assert len(calls) == 4

    generate_section_audio(
        section,
        tmp_path,
        "test-voice",
        "0%",
        pause_ms=25,
        max_chars=2500,
        force=True,
        synthesizer=fake_synthesizer,
    )
    assert len(calls) == 8