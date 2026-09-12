from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from pydub import AudioSegment

from .config import load_pronunciation_map, load_tts_config
from .text import apply_pronunciation_map, chunk_text, normalize_text


def build_ssml(text: str, voice: str, rate: str, pause_ms: int) -> str:
    paragraphs = [normalize_text(p) for p in text.split("\n") if normalize_text(p)]
    joined = f'<break time="{pause_ms}ms"/>'.join(escape(p) for p in paragraphs)
    return (
        '<speak version="1.0" xml:lang="vi-VN">'
        f'<voice name="{escape(voice)}"><prosody rate="{escape(rate)}">'
        f"{joined}"
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


def synthesize_file(source: Path, output: Path, dry_run: bool = False) -> None:
    tts = load_tts_config()
    pronunciation = load_pronunciation_map()
    voice = os.getenv("AZURE_SPEECH_VOICE", "").strip() or str(tts.get("voice", "vi-VN-HoaiMyNeural"))
    rate = str(tts.get("rate", "-5%"))
    pause_ms = int(tts.get("pause_ms", 350))
    max_chars = int(tts.get("max_chars_per_request", 2500))

    display_text = source.read_text(encoding="utf-8")
    tts_text = apply_pronunciation_map(display_text, pronunciation)
    chunks = chunk_text(tts_text, max_chars=max_chars)

    if dry_run:
        print(f"{source.name}: {len(chunks)} TTS request(s)")
        for i, chunk in enumerate(chunks, start=1):
            print(f"--- chunk {i} ({len(chunk)} chars) ---")
            print(chunk[:500] + ("..." if len(chunk) > 500 else ""))
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    combined = AudioSegment.empty()
    with tempfile.TemporaryDirectory(prefix="daisy_tts_") as tmp:
        temp_dir = Path(tmp)
        for i, chunk in enumerate(chunks, start=1):
            segment = temp_dir / f"segment_{i:04d}.mp3"
            ssml = build_ssml(chunk, voice=voice, rate=rate, pause_ms=pause_ms)
            print(f"Synthesizing {source.name}: {i}/{len(chunks)}")
            synthesize_chunk(ssml, segment, voice=voice)
            combined += AudioSegment.from_file(segment, format="mp3")

    combined.export(output, format="mp3", bitrate="64k")
    print(f"Wrote {output}")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate chapter MP3 files with Azure TTS.")
    parser.add_argument("--chapter", help="One chapter .txt file")
    parser.add_argument("--all", action="store_true", help="Generate all chapters from build/text/manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Show chunks without calling Azure")
    parser.add_argument("--text-dir", default="build/text")
    parser.add_argument("--audio-dir", default="build/audio")
    args = parser.parse_args()

    if not args.chapter and not args.all:
        parser.error("Use --chapter FILE or --all")

    audio_dir = Path(args.audio_dir)
    if args.chapter:
        source = Path(args.chapter)
        synthesize_file(source, audio_dir / f"{source.stem}.mp3", dry_run=args.dry_run)
        return 0

    manifest_path = Path(args.text_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for chapter in manifest["chapters"]:
        source = Path(args.text_dir) / chapter["file"]
        synthesize_file(source, audio_dir / f"{source.stem}.mp3", dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
