#!/usr/bin/env python3
"""Private targeted Overview CTA repair; exact Short voice, no new TTS."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, tempfile, wave, zipfile
from pathlib import Path
from scripts import kesher_owner_midyear_kindergarten_preview as preview
from scripts import kesher_owner_midyear_kindergarten_repair as prior

ARCHIVE_ID=13796284317
ARCHIVE_SHA="1bf0c28f2c9006416cfca78d92981a45025c210eb0662c9c173ab16ca77fe1c7"
OVERVIEW_SHA=prior.OVERVIEW_SHA
SHORT_SHA="ca2c1f9f5ad64b8de93d5956dda543a1530cec988aef70185ee2ee230ae981e4"
OVERVIEW_CUT=(3542112,3637368)
SHORT_CUT=(1096326,1186290)
OLD="למאמר המלא, הקישור בתיאור."
NEW="המאמר המלא בקישור בתיאור."
RATE=prior.RATE
require=prior.require
sha=prior.sha
file_sha=prior.file_sha

def expected_names():
    names={"asr-review.json"}
    for kind in ("overview","short"):
        names.update((f"{kind}.mp4",f"{kind}-manifest.json",f"{kind}-review-voice.wav",f"{kind}-visual-contact-sheet.jpg",f"{kind}-asr.txt"))
        names.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1,9))
    return names

def splice(original,short):
    a,b=OVERVIEW_CUT;c,d=SHORT_CUT
    require(b*2<len(original) and d*2<len(short) and all(prior.quiet_at(data,n) for data,n in ((original,a),(original,b),(short,c),(short,d))),"CUT_NOT_SILENT")
    replacement=short[c*2:d*2]; extra=(b-a)-(d-c)
    require(extra>=0,"REPLACEMENT_TOO_LONG")
    left=extra//2
    result=original[:a*2]+b"\0"*(left*2)+replacement+b"\0"*((extra-left)*2)+original[b*2:]
    require(len(result)==len(original) and result[:a*2]==original[:a*2] and result[b*2:]==original[b*2:],"OUTSIDE_PCM_CHANGED")
    return result

def repair(archive,out):
    require(file_sha(archive)==ARCHIVE_SHA,"ARCHIVE_SHA_MISMATCH")
    require(not out.exists(),"OUTPUT_ALREADY_EXISTS")
    out.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        require(len(names)==len(set(names)) and set(names)==expected_names() and sum(x.file_size for x in z.infolist())<100_000_000,"ARCHIVE_FILE_SET")
        for n in names:
            (out/n).write_bytes(z.read(n))
    overview=out/"overview.mp4";short=out/"short.mp4"
    require(file_sha(overview)==OVERVIEW_SHA and file_sha(short)==SHORT_SHA,"ORIGINAL_MEDIA_SHA")
    scripts,provenance=preview.source_check(public=True)
    om=json.loads((out/"overview-manifest.json").read_text());sm=json.loads((out/"short-manifest.json").read_text())
    require(all(x["source_slug"]==preview.SLUG and x["content_sha256"]==preview.SOURCE_SHA and x["public"] is False and x["uploaded"] is False and x["source_file_sha256"]==file_sha(preview.RESEARCH) for x in (om,sm)),"SOURCE_IDENTITY")
    require(om["script_segments"]==scripts["overview"] and sm["script_segments"]==scripts["short"]+[prior.CLOSING] and OLD in om["script_segments"][-1] and NEW in sm["script_segments"][-2],"SCRIPT_PHRASE_MISMATCH")
    oldpcm=prior.pcm(overview);shortpcm=prior.pcm(short);edited=splice(oldpcm,shortpcm)
    original_video=prior.packet_hashes(overview,"v:0")
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td);wav=tmp/"repair.wav";candidate=tmp/"overview.mp4"
        with wave.open(str(wav),"wb") as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(edited)
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(overview),"-i",str(wav),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","128k","-movflags","+faststart",str(candidate)],check=True)
        require(prior.packet_hashes(candidate,"v:0")==original_video,"VIDEO_PACKETS_CHANGED")
        overview.write_bytes(candidate.read_bytes())
    require(file_sha(short)==SHORT_SHA,"SHORT_CHANGED")
    wav=out/"overview-review-voice.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(overview),"-map","0:a:0","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],check=True)
    media=preview.verify_video(overview,"overview")
    require(abs(media["duration"]-om["media"]["duration"])<0.15,"DURATION_CHANGED")
    om["script_segments"][-1]=om["script_segments"][-1].replace(OLD,NEW)
    om["script_sha256"]=sha("\n".join(om["script_segments"]).encode())
    om["video_sha256"]=file_sha(overview);om["audio_sha256"]=file_sha(wav);om["media"]=media
    om["targeted_cta_repair"]={"input_artifact_id":ARCHIVE_ID,"input_archive_sha256":ARCHIVE_SHA,"original_overview_sha256":OVERVIEW_SHA,"unchanged_short_sha256":SHORT_SHA,"overview_cut_samples":list(OVERVIEW_CUT),"short_cut_samples":list(SHORT_CUT),"sample_rate":RATE,"video_packet_hashes_sha256":sha("\n".join(original_video).encode()),"original_pcm_sha256":sha(oldpcm),"edited_pcm_sha256":sha(edited),"outside_cut_pcm_sha256":sha(oldpcm[:OVERVIEW_CUT[0]*2]+oldpcm[OVERVIEW_CUT[1]*2:]),"outside_cut_pcm_preserved_before_aac_encode":True,"video_packets_preserved":True,"original_short_preserved":True,"method":"replace incomplete CTA with exact independently transcribed Short sentence at silent boundaries; no new TTS"}
    (out/"overview-manifest.json").write_text(json.dumps(om,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for n in ("overview-asr.txt","short-asr.txt","asr-review.json"):
        (out/n).unlink()
    print("TARGETED_OVERVIEW_CTA_REPAIR_READY",om["video_sha256"],om["targeted_cta_repair"],flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--archive",type=Path,required=True);a.add_argument("--output",type=Path,required=True);args=a.parse_args();repair(args.archive,args.output)
