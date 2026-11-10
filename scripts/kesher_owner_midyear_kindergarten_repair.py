#!/usr/bin/env python3
"""Targeted private Short duration repair; reuse exact existing voice and video."""
from __future__ import annotations
import argparse, hashlib, json, math, struct, subprocess, tempfile, wave, zipfile
from pathlib import Path
from scripts import kesher_owner_midyear_kindergarten_preview as preview

ARCHIVE_ID = 13796052703
ARCHIVE_SHA = "a6f26cffc976ff89074f84ecf21c582c30a186870c955fa77c24d765e9128e9d"
OVERVIEW_SHA = "e33c65f89e0864b02a927c9c7f0db152baaab2319171d43124db8f9a6ddbe607"
SHORT_SHA = "02a334cff504fe90308703c7bafb8889e16ad031bd4287de3819e2b1f1590f84"
RATE = 44100
CUT = (3384675, 3527118)
CLOSING = "המטרה היא ילד שמרגיש בטוח גם כשהסביבה משתנה."
PHOTO_INDEX = 7

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    return preview.sha_file(path)

def command(*args):
    return subprocess.check_output([str(a) for a in args], stderr=subprocess.PIPE)

def pcm(path):
    return command("ffmpeg","-v","error","-i",path,"-map","0:a:0","-ac","1","-ar",RATE,"-f","s16le","-")

def packet_hashes(path, stream):
    raw=command("ffprobe","-v","error","-select_streams",stream,"-show_packets","-show_data_hash","sha256","-show_entries","packet=data_hash","-of","json",path)
    values=[x["data_hash"] for x in json.loads(raw)["packets"]]
    require(bool(values) and all(x.startswith("SHA256:") for x in values),"PACKET_HASH_MISSING")
    return values

def quiet_at(data, sample):
    radius=RATE//200
    chunk=data[(sample-radius)*2:(sample+radius)*2]
    vals=struct.unpack("<"+"h"*(len(chunk)//2),chunk)
    return bool(vals) and math.sqrt(sum(v*v for v in vals)/len(vals))<180

def exact_cut(data):
    a,b=CUT
    require(b*2<len(data) and quiet_at(data,a) and quiet_at(data,b),"CUT_NOT_SILENT")
    return data[a*2:b*2]

def expected_names():
    return {"overview.mp4","short.mp4","overview-manifest.json","overview-review-voice.wav","short-review-voice.wav","overview-visual-contact-sheet.jpg"} | {f"overview-frame-{i:02d}.jpg" for i in range(1,9)}

def repair(archive,out):
    require(file_sha(archive)==ARCHIVE_SHA,"ARCHIVE_SHA_MISMATCH")
    require(not out.exists(),"OUTPUT_ALREADY_EXISTS")
    out.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        require(len(names)==len(set(names)) and set(names)==expected_names() and sum(x.file_size for x in z.infolist())<100_000_000,"ARCHIVE_FILE_SET")
        for n in names:
            (out/n).write_bytes(z.read(n))
    overview=out/"overview.mp4"; short=out/"short.mp4"
    require(file_sha(overview)==OVERVIEW_SHA and file_sha(short)==SHORT_SHA,"ORIGINAL_MEDIA_SHA")
    scripts,provenance=preview.source_check(public=True)
    om=json.loads((out/"overview-manifest.json").read_text())
    require(om["source_slug"]==preview.SLUG and om["content_sha256"]==preview.SOURCE_SHA and om["canonical_content_sha256"]==preview.CANONICAL_SHA and om["article_body_sha256"]==preview.BODY_SHA and om["public"] is False and om["uploaded"] is False and om["video_sha256"]==OVERVIEW_SHA and om["source_file_sha256"]==file_sha(preview.RESEARCH) and om["script_segments"]==scripts["overview"] and om["visual_sources"]==provenance["images"],"SOURCE_IDENTITY")
    require(CLOSING in scripts["overview"][-1],"SOURCE_CLOSING_MISSING")
    original_video=packet_hashes(short,"v:0"); original_audio=packet_hashes(short,"a:0")
    cut=exact_cut(pcm(overview))
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td); wav=tmp/"closing.wav"; tail=tmp/"tail.mp4"; candidate=tmp/"short.mp4"
        with wave.open(str(wav),"wb") as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(cut)
        photo=preview.ROOT/provenance["images"][PHOTO_INDEX]["path"]
        preview.encode_scene(photo,wav,tail,"short",len(cut)/(RATE*2)+0.05,False)
        preview.join_scenes([short,tail],candidate)
        final_video=packet_hashes(candidate,"v:0"); final_audio=packet_hashes(candidate,"a:0")
        require(final_video[:len(original_video)]==original_video and final_audio[:len(original_audio)]==original_audio,"ORIGINAL_SHORT_PACKET_PREFIX_CHANGED")
        short.write_bytes(candidate.read_bytes())
    require(file_sha(overview)==OVERVIEW_SHA,"OVERVIEW_CHANGED")
    wav=out/"short-review-voice.wav"
    subprocess.run(["ffmpeg","-hide_banner","-v","error","-y","-i",str(short),"-map","0:a:0","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],check=True)
    media=preview.verify_video(short,"short")
    frames,contact=preview.review_frames(short,out,"short")
    segments=scripts["short"]+[CLOSING]
    m={"source_slug":preview.SLUG,"content_sha256":preview.SOURCE_SHA,"canonical_content_sha256":preview.CANONICAL_SHA,"article_body_sha256":preview.BODY_SHA,"kind":"short","media_item_id":f"owner-short-20261110-{preview.SOURCE_SHA[:12]}","source_file":str(preview.RESEARCH.relative_to(preview.ROOT)),"source_file_sha256":file_sha(preview.RESEARCH),"script_segments":segments,"script_sha256":sha("\n".join(segments).encode()),"visual_sources":provenance["images"],"voice_provenance":om["voice_provenance"],"voice_model":om["voice_model"],"video_sha256":file_sha(short),"audio_sha256":file_sha(wav),"audio_review_source":"decoded_final_mp4_audio","contact_sha256":file_sha(contact),"frame_sha256":[file_sha(x) for x in frames],"media":media,"composition":"native_full_frame_9_16_no_padding","owner_editorial_qa":"PENDING_GENUINE_INDEPENDENT_REVIEW","uploaded":False,"public":False,"targeted_duration_repair":{"input_artifact_id":ARCHIVE_ID,"input_archive_sha256":ARCHIVE_SHA,"original_short_sha256":SHORT_SHA,"unchanged_overview_sha256":OVERVIEW_SHA,"overview_cut_samples":list(CUT),"sample_rate":RATE,"source_pcm_sha256":sha(cut),"original_video_packet_count":len(original_video),"original_audio_packet_count":len(original_audio),"original_video_packet_hashes_sha256":sha("\n".join(original_video).encode()),"original_audio_packet_hashes_sha256":sha("\n".join(original_audio).encode()),"original_video_and_audio_packets_preserved":True,"closing_sentence":CLOSING,"photo_index":PHOTO_INDEX,"method":"append exact existing Overview sentence and native vertical scene; no new TTS or original media rerender"}}
    (out/"short-manifest.json").write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TARGETED_SHORT_DURATION_REPAIR_READY",m["video_sha256"],m["media"],m["targeted_duration_repair"],flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--archive",type=Path,required=True);a.add_argument("--output",type=Path,required=True);args=a.parse_args();repair(args.archive,args.output)
