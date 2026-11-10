#!/usr/bin/env python3
"""Source-locked private OWNER media render; no upload or automatic QA approval."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from scripts.kesher_daily_pipeline import clean_article_html, source_metadata
from scripts.kesher_owner_positivity_preview import (sha_file, sha_bytes, make_image, encode_scene, join_scenes, merge_wavs, review_frames, verify_video, MODEL_SHA, G2P_SHA)
ROOT = Path(__file__).resolve().parents[1]
SLUG = "productive-failure-parents-learning-resilience"
SOURCE_SHA = "37f9b2e3ef91fa1b77b923f35281df9a66014d243389bb08e7fa1954bc86ab50"
CANONICAL_SHA = "3c591714830cf7787c453be6b11eab3d7eb8e743eed97da69d449acc9a80b5bf"
ARTICLE = "https://kesher.saharoni.com/blog/" + SLUG
RESEARCH = ROOT / "research/kesher-productive-failure-20261110.md"
PHOTOS = ROOT / "research/kesher-productive-failure-photo-provenance.json"
SOURCE_KINDS = ("overview", "short")

def source_scripts():
    doc = RESEARCH.read_text(encoding="utf-8")
    overview = re.findall(r'^\d+\. (.+)$', doc, re.M)
    short_text = doc.split("## Short script",1)[1].strip()
    short = re.split(r'(?<=[.!?])\s+', short_text)
    short = [short[0]+" "+short[1], *short[2:]]
    if len(overview) != 6 or len(short) < 4 or len(short) > 8:
        raise ValueError("SOURCE_SCRIPT_SHAPE")
    if "לא לכל ילד" not in short_text or "לא היו זהות בכל גיל" not in " ".join(overview):
        raise ValueError("MISSING_RESEARCH_CAVEAT")
    return {"overview": overview, "short": short}

def source_check(*, public=False):
    posts=json.loads((ROOT/"src/data/postsRecent.json").read_text(encoding="utf-8"))
    selected=[x for x in posts if x.get("slug")==SLUG]
    if len(selected)!=1: raise ValueError("ARTICLE_NOT_UNIQUE")
    post=selected[0]
    source=source_metadata(post)
    if source["content_sha256"]!=CANONICAL_SHA or sha_bytes(clean_article_html(post["content"]).encode())!=SOURCE_SHA:
        raise ValueError("SOURCE_IDENTITY_CHANGED")
    provenance=json.loads(PHOTOS.read_text(encoding="utf-8"))
    images=provenance["images"]
    if provenance["source_slug"]!=SLUG or provenance["content_sha256"]!=SOURCE_SHA or provenance["canonical_content_sha256"]!=CANONICAL_SHA or len(images)!=3 or len({x["path"] for x in images})!=3:
        raise ValueError("PHOTO_PROVENANCE_MISMATCH")
    for item in images:
        path=ROOT/item["path"]
        if not path.is_file() or path.is_symlink() or not str(path.resolve()).startswith(str(ROOT/"public/images")+"/") or sha_file(path)!=item["sha256"] or item["generated_for"]!=SLUG or not item["license_url"].startswith("https://helpx.adobe.com/"):
            raise ValueError("PHOTO_RIGHTS_OR_BYTES_MISMATCH")
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
    if info["model_revision"]!=MODEL_SHA or info["g2p_revision"]!=G2P_SHA or info["weights_license"]!="MIT" or info["reference_license"]!="CC BY 4.0" or info["g2p_license"]!="Apache-2.0":
        raise ValueError("VOICE_RIGHTS_OR_REVISION_CHANGED")
    offset=0
    for kind in SOURCE_KINDS:
        loc=out/kind; loc.mkdir()
        count=len(scripts[kind]); voicepaths=voices[offset:offset+count]; secs=durations[offset:offset+count]; offset+=count
        segments=[]
        for i in range(count):
            photo=ROOT/provenance["images"][([0,1,1,2,0,2] if kind=="overview" else [0,1,2,0,2,1,2,0])[i]]["path"]
            canvas=loc/f"scene-{i}.jpg"; part=loc/f"segment-{i}.mp4"
            make_image(photo,canvas,kind); encode_scene(canvas,voicepaths[i],part,kind,secs[i]+0.05,i%2==1); segments.append(part)
        video=out/f"{kind}.mp4"; join_scenes(segments,video)
        wav=out/f"{kind}-review-voice.wav"; merge_wavs(voicepaths,wav)
        media=verify_video(video,kind); frames,contact=review_frames(video,out,kind)
        manifest={"source_slug":SLUG,"content_sha256":SOURCE_SHA,"canonical_content_sha256":CANONICAL_SHA,"kind":kind,"media_item_id":f"owner-{kind}-20261110-{SOURCE_SHA[:12]}","source_file":str(RESEARCH.relative_to(ROOT)),"source_file_sha256":sha_file(RESEARCH),"script_segments":scripts[kind],"script_sha256":sha_bytes("\n".join(scripts[kind]).encode()),"visual_sources":provenance["images"],"voice_provenance":info,"voice_model":"BlueTTS2.5-onnx:libri_female_6147","video_sha256":sha_file(video),"audio_sha256":sha_file(wav),"contact_sha256":sha_file(contact),"frame_sha256":[sha_file(x) for x in frames],"media":media,"owner_editorial_qa":"PENDING_GENUINE_INDEPENDENT_REVIEW","uploaded":False,"public":False}
        (out/f"{kind}-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("OWNER_PRIVATE_PREVIEW_READY",kind,manifest["video_sha256"],media,flush=True)

def transcribe(out):
    from faster_whisper import WhisperModel
    from scripts.kesher_owner_positivity_asr import similarity
    model=WhisperModel("small",device="cpu",compute_type="int8",download_root=str(out/"asr-model-cache"))
    report={"source_slug":SLUG,"content_sha256":SOURCE_SHA,"canonical_content_sha256":CANONICAL_SHA,"engine":"faster-whisper==1.2.1 / small Hebrew","review":"PENDING_OWNER_EDITORIAL_CONFIRMATION","media":{}}
    for kind in SOURCE_KINDS:
        m=json.loads((out/f"{kind}-manifest.json").read_text())
        wav=out/f"{kind}-review-voice.wav"
        if m["source_slug"]!=SLUG or m["content_sha256"]!=SOURCE_SHA or sha_file(wav)!=m["audio_sha256"] or m["public"] is not False: raise ValueError("ASR_IDENTITY_MISMATCH")
        segments,details=model.transcribe(str(wav),language="he",beam_size=5,condition_on_previous_text=False,vad_filter=False)
        text=" ".join(x.text.strip() for x in segments).strip()
        if len(re.findall(r"[\u0590-\u05ff]",text))<60: raise ValueError("ASR_TOO_LITTLE_HEBREW")
        p=out/f"{kind}-asr.txt";p.write_text(text+"\n",encoding="utf-8")
        report["media"][kind]={"audio_sha256":m["audio_sha256"],"transcript_sha256":sha_file(p),"script_sha256":m["script_sha256"],"script_similarity":similarity(text," ".join(m["script_segments"])),"language":details.language,"editorial_decision":"QA_PENDING_REVIEW","human_listening":False}
    (out/"asr-review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ASR_EVIDENCE_READY_NO_PUBLICATION",flush=True)


# Exact previous private artifact. The original Overview, both WAVs and ASR
# evidence are reused; only the Short's padded visual composition is replaced.
REPAIR_ARCHIVE_SHA = "c7bcb8acc2ff876e028b977fa100d0439822421ddc4ade24c9740e73e2b513fe"
REPAIR_SHORT_SHA = "61dc7879e0735a73d1c7de4d2b9d6b37ac25884e954d922bc1f9d61bb16c55d7"
REPAIR_OVERVIEW_SHA = "f81a4ab1cd1432b5674d14d1b3f5ed8bcfbc335d22ef8180295db6421cf4f831"
REPAIR_FPS = 25

def _run_bytes(args):
    import subprocess
    return subprocess.check_output(args, stderr=subprocess.PIPE)

def _run_checked(args):
    import subprocess
    subprocess.run(args, check=True)

def _audio_packets(video):
    return sha_bytes(_run_bytes(["ffmpeg","-v","error","-i",str(video),
                                 "-map","0:a:0","-c:a","copy","-f","adts","-"]))

def _native_portrait(src, target, index):
    from PIL import Image, ImageOps
    # Editorial focus: child struggling, hands trying, parent/child learning.
    # Use actual full-frame portrait crops, not blurred letterbox padding.
    center = ((0.29,0.5),(0.52,0.5),(0.5,0.5))[index]
    im=Image.open(src).convert("RGB")
    ImageOps.fit(im,(1080,1920),method=Image.Resampling.LANCZOS,
                 centering=center).save(target,"JPEG",quality=94,optimize=True)

def repair_short(archive, out):
    import shutil, zipfile
    import numpy as np
    from scripts.kesher_owner_positivity_preview import motion_filter
    scripts,provenance=source_check()
    if out.exists() or sha_file(archive)!=REPAIR_ARCHIVE_SHA:
        raise ValueError("EXACT_REPAIR_ARCHIVE_REQUIRED")
    expected={"asr-review.json"}
    for kind in SOURCE_KINDS:
        expected.update((f"{kind}.mp4",f"{kind}-manifest.json",f"{kind}-review-voice.wav",
                         f"{kind}-visual-contact-sheet.jpg",f"{kind}-asr.txt"))
        expected.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1,9))
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=expected or sum(x.file_size for x in z.infolist())>=100_000_000:
            raise ValueError("REPAIR_ARCHIVE_FILE_SET_MISMATCH")
        out.mkdir(parents=True)
        for name in sorted(expected):
            if Path(name).name!=name: raise ValueError("UNSAFE_REPAIR_ARCHIVE_PATH")
            (out/name).write_bytes(z.read(name))
    for kind,video_sha in (("overview",REPAIR_OVERVIEW_SHA),("short",REPAIR_SHORT_SHA)):
        m=json.loads((out/f"{kind}-manifest.json").read_text(encoding="utf-8"))
        if (m["source_slug"]!=SLUG or m["content_sha256"]!=SOURCE_SHA
            or m["canonical_content_sha256"]!=CANONICAL_SHA or m["kind"]!=kind
            or m["source_file_sha256"]!=sha_file(RESEARCH) or m["script_segments"]!=scripts[kind]
            or m["visual_sources"]!=provenance["images"] or m["public"] is not False
            or m["uploaded"] is not False or m["video_sha256"]!=video_sha
            or sha_file(out/f"{kind}.mp4")!=video_sha
            or sha_file(out/f"{kind}-review-voice.wav")!=m["audio_sha256"]
            or sha_file(out/f"{kind}-visual-contact-sheet.jpg")!=m["contact_sha256"]
            or [sha_file(out/f"{kind}-frame-{i:02d}.jpg") for i in range(1,9)]!=m["frame_sha256"]):
            raise ValueError("REPAIR_SOURCE_EVIDENCE_MISMATCH")
    asr=json.loads((out/"asr-review.json").read_text(encoding="utf-8"))
    for kind in SOURCE_KINDS:
        if sha_file(out/f"{kind}-asr.txt")!=asr["media"][kind]["transcript_sha256"]:
            raise ValueError("REPAIR_ASR_EVIDENCE_MISMATCH")
    work=out/"short-visual-repair"; work.mkdir()
    old=work/"original-short.mp4"; shutil.copy2(out/"short.mp4",old)
    audio_sha=_audio_packets(old)
    raw=_run_bytes(["ffmpeg","-v","error","-i",str(old),"-map","0:v:0",
                    "-vf","scale=160:90,format=gray","-f","rawvideo","-"])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,90,160)
    differences=np.abs(np.diff(frames.astype(np.int16),axis=0)).mean(axis=(1,2))
    boundaries=[0]+[i+1 for i,d in enumerate(differences) if d>18]+[len(frames)]
    # Exact immutable original had seven scenes and 760 frames at 25 fps.
    if boundaries!=[0,128,267,331,407,506,701,760]:
        raise ValueError("REPAIR_SCENE_BOUNDARIES_CHANGED "+str(boundaries))
    indices=[0,1,2,0,2,1,2]
    parts=[]
    for i,index in enumerate(indices):
        count=boundaries[i+1]-boundaries[i]
        crop=work/f"crop-{i}.jpg"; part=work/f"part-{i}.mp4"
        _native_portrait(ROOT/provenance["images"][index]["path"],crop,index)
        expr=motion_filter("short",count/REPAIR_FPS,i%2==1)
        _run_checked(["ffmpeg","-hide_banner","-v","error","-y","-loop","1",
                      "-framerate",str(REPAIR_FPS),"-i",str(crop),"-filter_complex",expr,
                      "-map","[v]","-frames:v",str(count),"-an","-c:v","libx264",
                      "-preset","veryfast","-crf","23","-movflags","+faststart",str(part)])
        parts.append(part)
    visual=work/"visual.mp4"; join_scenes(parts,visual)
    repaired=work/"repaired.mp4"
    _run_checked(["ffmpeg","-hide_banner","-v","error","-y","-i",str(visual),"-i",str(old),
                  "-map","0:v:0","-map","1:a:0","-c","copy","-movflags","+faststart",str(repaired)])
    if _audio_packets(repaired)!=audio_sha:
        raise ValueError("REPAIR_AUDIO_PACKET_BYTES_CHANGED")
    new_raw=_run_bytes(["ffmpeg","-v","error","-i",str(repaired),"-map","0:v:0",
                        "-vf","scale=160:90,format=gray","-f","rawvideo","-"])
    if len(new_raw)!=len(raw):
        raise ValueError("REPAIR_FRAME_COUNT_CHANGED")
    shutil.copy2(repaired,out/"short.mp4")
    media=verify_video(out/"short.mp4","short")
    review,contact=review_frames(out/"short.mp4",out,"short")
    mpath=out/"short-manifest.json"; m=json.loads(mpath.read_text(encoding="utf-8"))
    m.update({"video_sha256":sha_file(out/"short.mp4"),"contact_sha256":sha_file(contact),
              "frame_sha256":[sha_file(x) for x in review],"media":media,
              "visual_repair":{"input_artifact_id":13757158570,"input_archive_sha256":REPAIR_ARCHIVE_SHA,
                 "original_video_sha256":REPAIR_SHORT_SHA,"audio_packet_sha256":audio_sha,
                 "audio_packets_preserved":True,"scene_frame_boundaries":boundaries,
                 "composition":"full_frame_9_16_editorial_focus_crops_no_blurred_padding"}})
    mpath.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if sha_file(out/"overview.mp4")!=REPAIR_OVERVIEW_SHA:
        raise ValueError("REPAIR_OVERVIEW_CHANGED")
    print("OWNER_TARGETED_SHORT_VISUAL_REPAIR_READY",m["video_sha256"],media,
          "AAC_PACKET_SHA",audio_sha,"OVERVIEW_UNCHANGED",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("operation",choices=["preflight","preview","asr","repair"]); p.add_argument("--source-sha",required=True); p.add_argument("--output",type=Path,default=Path("owner-productive-failure-media-output")); p.add_argument("--archive",type=Path); a=p.parse_args()
    if a.source_sha!=SOURCE_SHA: raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    if a.operation=="preflight": source_check(); print("SOURCE_PREFLIGHT_OK",SLUG,SOURCE_SHA,CANONICAL_SHA)
    elif a.operation=="preview": preview(a.output)
    elif a.operation=="asr": transcribe(a.output)
    else:
        if a.archive is None: raise SystemExit("EXACT_REPAIR_ARCHIVE_REQUIRED")
        repair_short(a.archive,a.output)
