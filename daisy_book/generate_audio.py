from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from pydub import AudioSegment

from .config import load_tts_config
from .text import chunk_text, normalize_text


SynthesisFunction = Callable[[str, Path, str], None]


def _validate_output_id(identifier: str, label: str) -> None:
    if identifier in {".", ".."} or Path(identifier).name != identifier or "\\" in identifier:
        raise ValueError(f"Unsafe {label} id: {identifier}")


def build_ssml(text: str, voice: str, rate: str) -> str:
    return (
        '<speak version="1.0" xml:lang="vi-VN">'
        f'<voice name="{escape(voice)}"><prosody rate="{escape(rate)}">'
        f"{escape(normalize_text(text))}"
        "</prosody></voice></speak>"
    )


def synthesize_chunk(ssml: str, output: Path, voice: str) -> None:
    import azure.cognitiveservices.speech as speechsdk

    key = os.getenv("AZURE_SPEECH_KEY", "").strip()
    region = os.getenv("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        raise RuntimeError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required. Copy .env.example to .env.")

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = getattr(result, "cancellation_details", None)
        reason = getattr(details, "reason", "unknown")
        error = getattr(details, "error_details", "")
        raise RuntimeError(f"Azure TTS failed: {reason} {error}".strip())


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("TTS manifest root must be an object")
    if not isinstance(manifest.get("sections"), list):
        raise ValueError("TTS manifest sections must be a list")
    return manifest


def select_section(manifest: dict[str, Any], section_id: str) -> dict[str, Any]:
    matches = [
        section
        for section in manifest.get("sections", [])
        if isinstance(section, dict) and section.get("id") == section_id
    ]
    if not matches:
        raise ValueError(f"Section not found: {section_id}")
    if len(matches) > 1:
        raise ValueError(f"Duplicate section id: {section_id}")
    validate_section(matches[0])
    return matches[0]


def validate_section(section: dict[str, Any]) -> None:
    section_id = section.get("id")
    if not isinstance(section_id, str) or not section_id.strip():
        raise ValueError("Selected section has no non-empty id")
    _validate_output_id(section_id, "section")
    paragraphs = section.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise ValueError(f"Section {section_id} contains no paragraphs")

    paragraph_ids: set[str] = set()
    for paragraph in paragraphs:
        if not isinstance(paragraph, dict):
            raise ValueError(f"Section {section_id} contains a non-object paragraph")
        paragraph_id = paragraph.get("id")
        if not isinstance(paragraph_id, str) or not paragraph_id.strip():
            raise ValueError(f"Section {section_id} contains a paragraph with no non-empty id")
        _validate_output_id(paragraph_id, "paragraph")
        if paragraph_id in paragraph_ids:
            raise ValueError(f"Duplicate paragraph id: {paragraph_id}")
        paragraph_ids.add(paragraph_id)
        tts_text = paragraph.get("tts_text")
        if not isinstance(tts_text, str) or not normalize_text(tts_text):
            raise ValueError(f"Paragraph {paragraph_id} has no non-empty tts_text")


def describe_dry_run(section: dict[str, Any], max_chars: int) -> dict[str, int]:
    validate_section(section)
    paragraphs = section["paragraphs"]
    total_characters = sum(len(paragraph["tts_text"]) for paragraph in paragraphs)
    request_count = sum(len(chunk_text(paragraph["tts_text"], max_chars)) for paragraph in paragraphs)

    print(f"Selected section: {section['id']}")
    print(f"Paragraph count: {len(paragraphs)}")
    print(f"Total characters: {total_characters}")
    print(f"Estimated request count: {request_count}")
    for paragraph in paragraphs:
        chunks = chunk_text(paragraph["tts_text"], max_chars)
        chunk_sizes = ", ".join(str(len(chunk)) for chunk in chunks)
        print(f"{paragraph['id']}: {len(chunks)} chunk(s) [{chunk_sizes} chars]")

    return {
        "paragraph_count": len(paragraphs),
        "total_characters": total_characters,
        "request_count": request_count,
    }


def _load_valid_audio(path: Path) -> AudioSegment | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        audio = AudioSegment.from_file(path, format="mp3")
    except Exception:
        return None
    return audio if len(audio) > 0 else None


def _synthesize_to_path(
    text: str,
    output: Path,
    voice: str,
    rate: str,
    synthesizer: SynthesisFunction,
) -> AudioSegment:
    temporary = output.with_name(f".{output.stem}.part.mp3")
    synthesizer(build_ssml(text, voice, rate), temporary, voice)
    audio = _load_valid_audio(temporary)
    if audio is None:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Synthesis produced no valid audio: {output.name}")
    temporary.replace(output)
    return audio


def synthesize_paragraph(
    paragraph: dict[str, str],
    segments_dir: Path,
    voice: str,
    rate: str,
    max_chars: int,
    force: bool = False,
    synthesizer: SynthesisFunction = synthesize_chunk,
) -> AudioSegment:
    paragraph_id = paragraph["id"]
    segment_path = segments_dir / f"{paragraph_id}.mp3"
    if not force:
        cached = _load_valid_audio(segment_path)
        if cached is not None:
            print(f"Reusing cached segment: {segment_path}")
            return cached

    chunks = chunk_text(paragraph["tts_text"], max_chars)
    segments_dir.mkdir(parents=True, exist_ok=True)
    print(f"Synthesizing {paragraph_id}: {len(chunks)} request(s)")

    if len(chunks) == 1:
        return _synthesize_to_path(chunks[0], segment_path, voice, rate, synthesizer)

    chunk_dir = segments_dir / paragraph_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_audio: list[AudioSegment] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_path = chunk_dir / f"chunk_{index:04d}.mp3"
        cached_chunk = None if force else _load_valid_audio(chunk_path)
        if cached_chunk is not None:
            print(f"Reusing cached chunk: {chunk_path}")
            chunk_audio.append(cached_chunk)
            continue
        print(f"Synthesizing {paragraph_id} chunk {index}/{len(chunks)}")
        chunk_audio.append(_synthesize_to_path(chunk, chunk_path, voice, rate, synthesizer))

    combined = AudioSegment.empty()
    for audio in chunk_audio:
        combined += audio
    temporary = segment_path.with_name(f".{segment_path.stem}.part.mp3")
    combined.export(temporary, format="mp3", bitrate="64k")
    segment = _load_valid_audio(temporary)
    if segment is None:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to assemble paragraph audio: {paragraph_id}")
    temporary.replace(segment_path)
    return segment


def generate_section_audio(
    section: dict[str, Any],
    output_dir: Path,
    voice: str,
    rate: str,
    pause_ms: int,
    max_chars: int,
    force: bool = False,
    synthesizer: SynthesisFunction = synthesize_chunk,
) -> dict[str, Any]:
    validate_section(section)
    if pause_ms < 0:
        raise ValueError("pause_ms must be non-negative")

    section_id = section["id"]
    section_dir = output_dir / section_id
    segments_dir = section_dir / "segments"
    paragraph_audio: list[tuple[str, AudioSegment]] = []
    for paragraph in section["paragraphs"]:
        audio = synthesize_paragraph(
            paragraph,
            segments_dir,
            voice,
            rate,
            max_chars,
            force=force,
            synthesizer=synthesizer,
        )
        paragraph_audio.append((paragraph["id"], audio))

    chapter_audio = AudioSegment.empty()
    timings: list[dict[str, int | str]] = []
    for index, (paragraph_id, audio) in enumerate(paragraph_audio):
        clip_begin = len(chapter_audio)
        chapter_audio += audio
        clip_end = len(chapter_audio)
        timings.append(
            {
                "id": paragraph_id,
                "clip_begin_ms": clip_begin,
                "clip_end_ms": clip_end,
                "duration_ms": clip_end - clip_begin,
            }
        )
        if pause_ms and index < len(paragraph_audio) - 1:
            silence = AudioSegment.silent(duration=pause_ms, frame_rate=chapter_audio.frame_rate)
            silence = silence.set_channels(chapter_audio.channels).set_sample_width(chapter_audio.sample_width)
            chapter_audio += silence

    section_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = section_dir / f"{section_id}.mp3"
    temporary = chapter_path.with_name(f".{chapter_path.stem}.part.mp3")
    chapter_audio.export(temporary, format="mp3", bitrate="64k")
    encoded_audio = _load_valid_audio(temporary)
    if encoded_audio is None:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to assemble section audio: {section_id}")
    temporary.replace(chapter_path)

    timing = {
        "section_id": section_id,
        "audio": chapter_path.name,
        "duration_ms": len(encoded_audio),
        "paragraphs": timings,
    }
    timing_path = section_dir / f"{section_id}_timing.json"
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {chapter_path}")
    print(f"Wrote {timing_path}")
    return timing


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate one section MP3 with paragraph timing using Azure TTS.")
    parser.add_argument("--manifest", default="build/tts/manifest.json", type=Path)
    parser.add_argument("--section", required=True, help="Section id, for example chapter_01 or introduction")
    parser.add_argument("--output-dir", default="build/audio", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate and show requests without calling Azure")
    parser.add_argument("--force", action="store_true", help="Regenerate all paragraph audio in the selected section")
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        section = select_section(manifest, args.section)
        tts = load_tts_config()
        voice = os.getenv("AZURE_SPEECH_VOICE", "").strip() or str(
            tts.get("voice", "vi-VN-HoaiMyNeural")
        )
        rate = str(tts.get("rate", "-5%"))
        pause_ms = int(tts.get("pause_ms", 350))
        max_chars = int(tts.get("max_chars_per_request", 2500))
        if args.dry_run:
            describe_dry_run(section, max_chars)
            return 0
        generate_section_audio(
            section,
            args.output_dir,
            voice,
            rate,
            pause_ms,
            max_chars,
            force=args.force,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
