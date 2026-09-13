import json

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from daisy_book.generate_audio import describe_dry_run, generate_section_audio, select_section


def sample_section():
    return {
        "id": "chapter_01",
        "type": "chapter",
        "paragraphs": [
            {
                "id": "chapter_01_p0001",
                "display_text": "Đoạn một.",
                "tts_text": "Đoạn một.",
            },
            {
                "id": "chapter_01_p0002",
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


def test_rejects_duplicate_paragraph_id_before_synthesis():
    section = sample_section()
    section["paragraphs"][1]["id"] = "chapter_01_p0001"

    with pytest.raises(ValueError, match="Duplicate paragraph id: chapter_01_p0001"):
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
    assert "chapter_01_p0001" in output
    assert result["paragraph_count"] == 2
    assert result["request_count"] >= 2


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
    assert len(calls) == 2
    assert (section_dir / "segments" / "chapter_01_p0001.mp3").is_file()
    assert (section_dir / "chapter_01.mp3").is_file()
    written = json.loads((section_dir / "chapter_01_timing.json").read_text(encoding="utf-8"))
    assert timing == written
    first, second = written["paragraphs"]
    assert first["id"] == "chapter_01_p0001"
    assert first["clip_begin_ms"] == 0
    assert first["clip_end_ms"] > first["clip_begin_ms"]
    assert second["clip_begin_ms"] >= first["clip_end_ms"]
    assert second["clip_end_ms"] > second["clip_begin_ms"]
    chapter_duration = len(AudioSegment.from_file(section_dir / "chapter_01.mp3", format="mp3"))
    assert written["duration_ms"] == chapter_duration
    assert abs(second["clip_end_ms"] - chapter_duration) <= 50

    generate_section_audio(
        section,
        tmp_path,
        "test-voice",
        "0%",
        pause_ms=25,
        max_chars=2500,
        synthesizer=fake_synthesizer,
    )
    assert len(calls) == 2

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
    assert len(calls) == 4