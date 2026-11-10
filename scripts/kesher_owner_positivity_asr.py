#!/usr/bin/env python3
"""Independent OWNER-only offline Hebrew ASR for immutable private review WAVs.

The transcript is evidence for editorial review, never an auto-approval.
No uploader, YouTube connection, source modifications or workflow dispatch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from . import kesher_owner_positivity_preview as owner

def hebrew_only(value: str) -> str:
    return " ".join(re.findall(r"[\u0590-\u05FF]+", value))

def similarity(asr: str, script: str) -> float:
    left, right = hebrew_only(asr), hebrew_only(script)
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right, autojunk=False).ratio(), 4)

def verify(out: Path, kind: str):
    manifest_path = out / (kind + "-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_slug") != owner.SLUG or manifest.get("content_sha256") != owner.SOURCE_SHA or manifest.get("kind") != kind or manifest.get("public") is not False:
        raise ValueError("INDEPENDENT_ASR_SOURCE_IDENTITY_MISMATCH")
    source = out / (kind + "-review-voice.wav")
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != manifest["audio_sha256"]:
        raise ValueError("INDEPENDENT_ASR_AUDIO_SHA256_MISMATCH")
    return source, manifest

def recognize(out: Path):
    from faster_whisper import WhisperModel
    scripts = owner.source_scripts()
    model = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(out / "asr-model-cache"))
    report = {"source_slug": owner.SLUG, "content_sha256": owner.SOURCE_SHA,
              "engine": "faster-whisper==1.2.1 / small, CPU, Hebrew", "review": "PENDING_OWNER_EDITORIAL_CONFIRMATION", "media": {}}
    for kind in owner.SOURCE_KINDS:
        source, manifest = verify(out, kind)
        segments, details = model.transcribe(str(source), language="he", beam_size=5,
                                          condition_on_previous_text=False, vad_filter=False)
        rows = list(segments)
        text = " ".join(str(x.text).strip() for x in rows).strip()
        script = " ".join(scripts[kind])
        transcript_file = out / (kind + "-asr.txt")
        transcript_file.write_text(text + "\n", encoding="utf-8")
        report["media"][kind] = {
            "media_item_id": manifest["media_item_id"], "audio_sha256": manifest["audio_sha256"],
            "transcript_sha256": hashlib.sha256(transcript_file.read_bytes()).hexdigest(),
            "recognized_language": details.language, "segment_count": len(rows),
            "hebrew_chars": len(re.findall(r"[\u0590-\u05FF]", text)),
            "script_similarity": similarity(text, script),
            "script_sha256": manifest["script_sha256"],
            "human_listening": False,
            "editorial_decision": "QA_PENDING_REVIEW",
        }
        if report["media"][kind]["hebrew_chars"] < 60:
            raise ValueError("ASR_TOO_LITTLE_RECOGNIZED_HEBREW_" + kind.upper())
        print("INDEPENDENT_ASR_WRITTEN",kind,"recognized_words=",len(text.split()),
              "script_similarity=",report["media"][kind]["script_similarity"],flush=True)
    (out / "asr-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print("ASR_REVIEW_EVIDENCE_READY_NOT_PUBLIC_NOT_APPROVED",flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-sha",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.source_sha!=owner.SOURCE_SHA:
        raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    recognize(args.output)
