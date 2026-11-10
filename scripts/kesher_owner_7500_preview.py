#!/usr/bin/env python3
"""Source-locked private OWNER media render for the approved code 7500 article."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from scripts.kesher_daily_pipeline import clean_article_html, source_metadata
from scripts.kesher_owner_positivity_preview import (sha_file, sha_bytes, make_image, encode_scene, join_scenes, review_frames, verify_video, MODEL_SHA, G2P_SHA)
ROOT = Path(__file__).resolve().parents[1]
SLUG = "relationship-code-7500"
SOURCE_SHA = "797750526c533f41e661123dc86339da3f0a5721d5eff820d70937ee7f6d5bdd"
CANONICAL_SHA = "a8a7c93632f826aa04c382bf3b3944ebb3da1ac386ef5e7970c6e91da5046d19"
ARTICLE = "https://kesher.saharoni.com/blog/" + SLUG
RESEARCH = ROOT / "research/kesher-relationship-code-7500-20261110.md"
PHOTOS = ROOT / "research/kesher-relationship-code-7500-photo-provenance.json"
SOURCE_KINDS = ("overview", "short")
OVERVIEW_PHOTOS = (0, 0, 0, 1, 2, 1, 1)
SHORT_PHOTOS = (3, 4, 3, 4)

def source_scripts():
    doc = RESEARCH.read_text(encoding="utf-8")
    overview = re.findall(r'^\d+\. (.+)$', doc, re.M)
    short_text = doc.split("## Short script",1)[1].strip().splitlines()[0]
    parts = re.split(r'(?<=[.!?])\s+', short_text)
    if len(overview) != 7 or len(parts) != 7 or len(short_text.split()) < 85:
        raise ValueError("SOURCE_SCRIPT_SHAPE")
    short = [parts[0]+" "+parts[1], parts[2]+" "+parts[3], parts[4], parts[5]+" "+parts[6]]
    if "בטיחות קודמת" not in short_text or "אינה אבחנה" not in " ".join(overview) or "מטאפורה" not in overview[0]:
        raise ValueError("MISSING_SAFETY_OR_RESEARCH_CAVEAT")
    return {"overview": overview, "short": short}

def source_check(*, public=False):
    posts=json.loads((ROOT/"src/data/postsRecent.json").read_text(encoding="utf-8"))
    selected=[x for x in posts if x.get("slug")==SLUG]
    if len(selected)!=1: raise ValueError("ARTICLE_NOT_UNIQUE")
    post=selected[0]; source=source_metadata(post)
    if source["content_sha256"]!=CANONICAL_SHA or sha_bytes(clean_article_html(post["content"]).encode())!=SOURCE_SHA:
        raise ValueError("SOURCE_IDENTITY_CHANGED")
    provenance=json.loads(PHOTOS.read_text(encoding="utf-8")); images=provenance["images"]
    if provenance["source_slug"]!=SLUG or provenance["content_sha256"]!=SOURCE_SHA or provenance["canonical_content_sha256"]!=CANONICAL_SHA or len(images)!=5 or len({x["path"] for x in images})!=5:
        raise ValueError("PHOTO_PROVENANCE_MISMATCH")
    from PIL import Image
    for i,item in enumerate(images):
        path=ROOT/item["path"]
        if not path.is_file() or path.is_symlink() or not str(path.resolve()).startswith(str(ROOT/"public/images")+"/") or sha_file(path)!=item["sha256"] or item["generated_for"]!=SLUG or not item["license_url"].startswith("https://helpx.adobe.com/"):
            raise ValueError("PHOTO_RIGHTS_OR_BYTES_MISMATCH")
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if i>=3 and im.size!=(1080,1920): raise ValueError("NATIVE_SHORT_PHOTO_REQUIRED")
            if i<3 and im.width<=im.height: raise ValueError("LANDSCAPE_PHOTO_REQUIRED")
    if public:
        import requests
        response=requests.get(ARTICLE,timeout=30)
        if response.status_code!=200 or f'rel="canonical" href="{ARTICLE}"' not in response.text or f'<meta name="kesher:content-sha256" content="{CANONICAL_SHA}">' not in response.text:
            raise ValueError("LIVE_ARTICLE_IDENTITY_MISMATCH")
    return source_scripts(),provenance

def preview(out):
    scripts,provenance=source_check()
    if out.exists(): raise ValueError("PREVIEW_EXISTS")
    out.mkdir(parents=True)
    from scripts import kesher_owner_vantage_short as voice
    voice.SCENES=[(kind+"-"+str(i),text) for kind in SOURCE_KINDS for i,text in enumerate(scripts[kind])]
    voices,durations,info=voice.speak(out)
    if len(voices)!=11 or info["model_revision"]!=MODEL_SHA or info["g2p_revision"]!=G2P_SHA or info["weights_license"]!="MIT" or info["reference_license"]!="CC BY 4.0" or info["g2p_license"]!="Apache-2.0":
        raise ValueError("VOICE_RIGHTS_OR_REVISION_CHANGED")
    offset=0
    for kind in SOURCE_KINDS:
        loc=out/kind; loc.mkdir()
        count=len(scripts[kind]); voicepaths=voices[offset:offset+count]; secs=durations[offset:offset+count]; offset+=count
        segments=[]; indices=OVERVIEW_PHOTOS if kind=="overview" else SHORT_PHOTOS
        for i in range(count):
            photo=ROOT/provenance["images"][indices[i]]["path"]
            canvas=loc/f"scene-{i}.jpg"; part=loc/f"segment-{i}.mp4"
            if kind=="overview":
                make_image(photo,canvas,kind)
            else:
                # Native 1080x1920 photo: use the full source, no blurred padding.
                canvas=photo
            encode_scene(canvas,voicepaths[i],part,kind,secs[i]+0.05,i%2==1); segments.append(part)
        video=out/f"{kind}.mp4"; join_scenes(segments,video)
        # Review the actual final muxed audio, not a separate pre-mux narration.
        wav=out/f"{kind}-review-voice.wav"
        subprocess.run(["ffmpeg","-hide_banner","-v","error","-y","-i",str(video),"-map","0:a:0","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],check=True)
        media=verify_video(video,kind); frames,contact=review_frames(video,out,kind)
        manifest={"source_slug":SLUG,"content_sha256":SOURCE_SHA,"canonical_content_sha256":CANONICAL_SHA,"kind":kind,"media_item_id":f"owner-{kind}-20261110-{SOURCE_SHA[:12]}","source_file":str(RESEARCH.relative_to(ROOT)),"source_file_sha256":sha_file(RESEARCH),"script_segments":scripts[kind],"script_sha256":sha_bytes("\n".join(scripts[kind]).encode()),"visual_sources":provenance["images"],"voice_provenance":info,"voice_model":"BlueTTS2.5-onnx:libri_female_6147","video_sha256":sha_file(video),"audio_sha256":sha_file(wav),"audio_review_source":"decoded_final_mp4_audio","contact_sha256":sha_file(contact),"frame_sha256":[sha_file(x) for x in frames],"media":media,"composition":"native_full_frame_9_16_no_padding" if kind=="short" else "full_frame_16_9","owner_editorial_qa":"PENDING_GENUINE_INDEPENDENT_REVIEW","uploaded":False,"public":False}
        (out/f"{kind}-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("OWNER_PRIVATE_PREVIEW_READY",kind,manifest["video_sha256"],media,flush=True)

def transcribe(out):
    from faster_whisper import WhisperModel
    from scripts.kesher_owner_positivity_asr import similarity
    model=WhisperModel("small",device="cpu",compute_type="int8",download_root=str(out/"asr-model-cache"))
    report={"source_slug":SLUG,"content_sha256":SOURCE_SHA,"canonical_content_sha256":CANONICAL_SHA,"engine":"faster-whisper==1.2.1 / small Hebrew","audio_source":"decoded_final_mp4_audio","review":"PENDING_OWNER_EDITORIAL_CONFIRMATION","media":{}}
    for kind in SOURCE_KINDS:
        m=json.loads((out/f"{kind}-manifest.json").read_text()); wav=out/f"{kind}-review-voice.wav"
        if m["source_slug"]!=SLUG or m["content_sha256"]!=SOURCE_SHA or sha_file(wav)!=m["audio_sha256"] or sha_file(out/f"{kind}.mp4")!=m["video_sha256"] or m["public"] is not False: raise ValueError("ASR_IDENTITY_MISMATCH")
        segments,details=model.transcribe(str(wav),language="he",beam_size=5,condition_on_previous_text=False,vad_filter=False)
        text=" ".join(x.text.strip() for x in segments).strip()
        if len(re.findall(r"[\u0590-\u05ff]",text))<60: raise ValueError("ASR_TOO_LITTLE_HEBREW")
        p=out/f"{kind}-asr.txt";p.write_text(text+"\n",encoding="utf-8")
        report["media"][kind]={"audio_sha256":m["audio_sha256"],"transcript_sha256":sha_file(p),"script_sha256":m["script_sha256"],"script_similarity":similarity(text," ".join(m["script_segments"])),"language":details.language,"editorial_decision":"QA_PENDING_REVIEW","human_listening":False}
    (out/"asr-review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ASR_EVIDENCE_READY_NO_PUBLICATION",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("operation",choices=["preflight","preview","asr"]); p.add_argument("--source-sha",required=True); p.add_argument("--output",type=Path,default=Path("owner-7500-media-output")); a=p.parse_args()
    if a.source_sha!=SOURCE_SHA: raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    if a.operation=="preflight": source_check(); print("SOURCE_PREFLIGHT_OK",SLUG,SOURCE_SHA,CANONICAL_SHA)
    elif a.operation=="preview": preview(a.output)
    else: transcribe(a.output)
