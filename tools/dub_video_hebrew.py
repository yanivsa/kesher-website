#!/usr/bin/env python3
import argparse
import asyncio
import base64
import json
import math
import os
import re
import subprocess
import urllib.error
import urllib.request
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from deep_translator import GoogleTranslator


def run(cmd, timeout=600):
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def ffmpeg_path():
    return imageio_ffmpeg.get_ffmpeg_exe()


def media_duration(path):
    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        text=True,
        capture_output=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def split_text(text, max_chars=4200):
    parts = []
    current = []
    current_len = 0
    for paragraph in re.split(r"\n{2,}", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current_len + len(paragraph) + 2 > max_chars and current:
            parts.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        parts.append("\n\n".join(current))
    return parts


def translate_to_hebrew(text, source_language):
    if source_language in {"he", "iw", "hebrew"}:
        return text
    translator = GoogleTranslator(source=source_language, target="iw")
    translated = []
    for chunk in split_text(text):
        translated.append(translator.translate(chunk))
    return "\n\n".join(translated)


def atempo_chain(factor):
    values = []
    while factor > 2.0:
        values.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        values.append(0.5)
        factor /= 0.5
    values.append(factor)
    return ",".join(f"atempo={value:.6f}" for value in values)


async def synthesize_hebrew(text, output_audio, voice):
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(output_audio))


def write_pcm_wav(output_path, pcm_bytes, rate=24000):
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm_bytes)


def synthesize_hebrew_gemini(text, output_audio, voice, model, api_key):
    if not api_key:
        raise RuntimeError("Missing Google API key. Set GOOGLE_API_KEY or pass --google-api-key.")

    prompt = (
        "Read this in natural Israeli Hebrew with a warm, modern, non-metallic female voice. "
        "Keep the pace calm, clear, and emotionally grounded.\n\n"
        f"{text}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice,
                    }
                }
            },
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini TTS failed ({exc.code}): {error_body[:1200]}") from exc

    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    inline = next((part.get("inlineData") for part in parts if part.get("inlineData")), None)
    if not inline or not inline.get("data"):
        raise RuntimeError(f"Gemini TTS returned no audio: {json.dumps(data)[:1200]}")

    pcm_bytes = base64.b64decode(inline["data"])
    wav_path = output_audio.with_suffix(".wav")
    write_pcm_wav(wav_path, pcm_bytes, rate=24000)
    return wav_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workdir", type=Path, default=Path("dub-output"))
    parser.add_argument("--model", default="tiny.en")
    parser.add_argument("--voice", default="he-IL-HilaNeural")
    parser.add_argument("--tts-provider", choices=["edge", "gemini"], default="edge")
    parser.add_argument("--gemini-model", default="gemini-2.5-flash-preview-tts")
    parser.add_argument("--google-api-key", default=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--source-text-file", type=Path)
    parser.add_argument("--source-language", default="auto")
    parser.add_argument("--skip-speed-match", action="store_true")
    args = parser.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    output = args.output or args.workdir / f"{args.input.stem}-hebrew-dub.mp4"
    audio_wav = args.workdir / f"{args.input.stem}.wav"
    transcript_txt = args.workdir / f"{args.input.stem}-transcript-en.txt"
    hebrew_txt = args.workdir / f"{args.input.stem}-script-he.txt"
    tts_mp3 = args.workdir / f"{args.input.stem}-hebrew-tts.mp3"
    matched_mp3 = args.workdir / f"{args.input.stem}-hebrew-tts-matched.mp3"

    if args.source_text_file:
        transcript = args.source_text_file.read_text(encoding="utf-8").strip()
        detected_language = "text-file"
    else:
        from faster_whisper import WhisperModel

        run([
            ffmpeg_path(),
            "-y",
            "-i",
            str(args.input),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_wav),
        ])

        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_wav), language="en", vad_filter=True)
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        detected_language = info.language
    transcript_txt.write_text(transcript + "\n", encoding="utf-8")

    if not transcript:
        raise RuntimeError("No transcript was detected in the input video.")

    hebrew = translate_to_hebrew(transcript, args.source_language)
    hebrew_txt.write_text(hebrew + "\n", encoding="utf-8")

    if args.tts_provider == "gemini":
        tts_audio = synthesize_hebrew_gemini(hebrew, tts_mp3, args.voice, args.gemini_model, args.google_api_key)
    else:
        asyncio.run(synthesize_hebrew(hebrew, tts_mp3, args.voice))
        tts_audio = tts_mp3

    audio_for_mux = tts_audio
    video_dur = media_duration(args.input)
    tts_dur = media_duration(tts_audio)
    if not args.skip_speed_match and video_dur and tts_dur and video_dur > 0:
        factor = tts_dur / video_dur
        if math.isfinite(factor) and 0.25 <= factor <= 4:
            run([
                ffmpeg_path(),
                "-y",
                "-i",
                str(tts_audio),
                "-filter:a",
                atempo_chain(factor),
                "-vn",
                str(matched_mp3),
            ])
            audio_for_mux = matched_mp3

    run([
        ffmpeg_path(),
        "-y",
        "-i",
        str(args.input),
        "-i",
        str(audio_for_mux),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ])

    print(f"output={output}")
    print(f"transcript={transcript_txt}")
    print(f"hebrew_script={hebrew_txt}")
    print(f"video_seconds={video_dur}")
    print(f"tts_seconds={tts_dur}")
    print(f"language={detected_language}")


if __name__ == "__main__":
    main()
