#!/usr/bin/env python3
"""Private exact-media repair of identified pronunciation windows; video packets preserved."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, tempfile, zipfile
from pathlib import Path
from scripts import kesher_owner_separate_room_preview as p

ARCHIVE_SHA = "a56dea3b812f87a5cde9b81771235866a2c57b4c7f6977077371259312679b27"
QA_SHA = "d68e7c793bac219eb76ac0f2c0134b9d6cdafceafe4f2c4c97a08fa84f84f491"
QA_JSON_SHA = "564486e1bd154fb57c595279c03f3f46b34a4ed58cde800592a63687b07f628a"
RATE = 44100
# Quiet sample boundaries measured from the exact decoded original MP4 audio.
# Original G2P confirmed pa'ot instead of pa'ut, past-tense imperatives, and
# repeated actual ASR uncertainty on soft objects and the doctor instruction.
# All spoken words remain the approved script; only phonetic input is corrected.
CUTS = {
 "overview": [
  (7.1524, 10.4042, "חשוב להבדיל בין תינוק לבין פעוט או ילד גדול יותר.", "χaʃˈuv lehavdˈil bˈejn tinˈok levˈen paʔˈut ʔˈo jˈeled ɡadˈol jotˈeʁ."),
  (23.3991, 25.0626, "בלי כריות או חפצים רכים.", "blˈi kaʁijˈot ʔˈo χafatsˈim ʁakˈim."),
  (29.0059, 31.4145, "אצל פעוט שכבר מתאים למעבר,", "ʔetsˈel paʔˈut ʃekvˈaʁ matʔˈim lamaʔavˈaʁ,"),
  (33.6933, 36.4238, "שחקו יחד והראו לילד איפה תשבו בערב.", "saχakˈu jˈaχad vehaʁʔˈu lajˈeled ʔˈejfo tiʃvˈu baʔˈeʁev."),
  (39.6517, 41.4578, "בערב שמרו על טקס קבוע:", "baʔˈeʁev ʃimʁˈu ʔˈal tˈekes kavˈua."),
  (41.4578, 43.7518, "פיג׳מה, סיפור, חיבוק ולילה טוב.", "pidʒˈama, sipˈuʁ, χibˈuk velˈajla tˈov."),
  (43.7518, 46.9017, "אם הילד רגיל שאתם לידו, שבו בכיסא סמוך למיטה.", "ʔˈim hajˈeled ʁaɡˈil ʃeʔatˈem lejadˈo, ʃvˈu bekisˈe samˈuχ lamitˈa."),
  (63.881, 67.1977, "האטו; אם יש נחירות חזקות או קשיי נשימה, פנו לרופא.", "haʔetˈu; ʔˈim jˈeʃ neχiʁˈot χazakˈot ʔˈo kʃajˈej neʃimˈa, pnˈu laʁofˈe."),
 ],
 "short": [
  (4.529, 5.2976, "לתינוקות:", "letinokˈot."),
  (12.3219, 13.6071, "בלי חפצים רכים.", "blˈi χafatsˈim ʁakˈim."),
  (13.6071, 14.5398, "אצל פעוט:", "ʔetsˈel paʔˈut."),
  (16.0818, 19.3313, "שמרו על טקס ערב, ושבו לידו בהתחלה.", "ʃimʁˈu ʔˈal tˈekes ʔˈeʁev, uʃvˈu lejadˈo bahatχalˈa."),
 ],
}
def require(ok, message):
    if not ok:
        raise ValueError(message)
def sha(b):
    return hashlib.sha256(b).hexdigest()
def packet_hashes(video):
    x = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_packets","-show_data_hash","sha256","-show_entries","packet=data_hash","-of","json",str(video)],check=True,capture_output=True,text=True)
    return [z["data_hash"] for z in json.loads(x.stdout)["packets"]]
def pcm(video):
    import numpy as np
    x = subprocess.run(["ffmpeg","-v","error","-i",str(video),"-map","0:a:0","-ac","1","-ar",str(RATE),"-f","s16le","-"],check=True,capture_output=True)
    return np.frombuffer(x.stdout,dtype="<i2").copy()
def cut_samples(kind, length):
    cuts=[(round(a*RATE),round(b*RATE),text,phones) for a,b,text,phones in CUTS[kind]]
    require(all(0<=a<b<=length for a,b,_,_ in cuts) and all(x[1]<=y[0] for x,y in zip(cuts,cuts[1:])),"INVALID_REPAIR_CUTS")
    return cuts
def splice(original, replacements):
    import numpy as np
    edited=original.copy()
    for a,b,replacement in replacements:
        require(len(replacement)==b-a,"REPLACEMENT_LENGTH")
        for n in (a,b):
            require(float(np.max(np.abs(original[max(0,n-441):min(len(original),n+441)].astype(np.int32))))<700,"CUT_NOT_QUIET")
        edited[a:b]=replacement
    last=0
    for a,b,_ in replacements:
        require(np.array_equal(original[last:a],edited[last:a]),"OUTSIDE_PCM_CHANGED")
        last=b
    require(np.array_equal(original[last:],edited[last:]),"OUTSIDE_PCM_CHANGED")
    return edited
def fit_voice(tts, phones, length, old, tmp, seed):
    import numpy as np
    import soundfile as sf
    np.random.seed(seed)
    arr,sr=tts.synthesize(phones,lang="he",text_is_phonemes=True,normalize_text=False,total_step=12,speed=1.0)
    arr=np.asarray(arr,dtype=np.float32).reshape(-1)
    require(len(arr)>1000 and np.isfinite(arr).all(),"INVALID_REPAIR_VOICE")
    raw=tmp/"new.wav"; res=tmp/"resampled.wav"; paced=tmp/"paced.wav"
    sf.write(raw,arr,sr,subtype="PCM_16")
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(raw),"-ac","1","-ar",str(RATE),"-c:a","pcm_s16le",str(res)],check=True)
    y,_=sf.read(res,dtype="float32")
    active=np.flatnonzero(np.abs(y)>0.004)
    require(len(active)>100,"REPAIR_VOICE_SILENT")
    y=y[max(0,int(active[0])-441):min(len(y),int(active[-1])+442)]
    margin=round(0.025*RATE)
    target=length-2*margin
    require(target>0,"REPAIR_WINDOW_TOO_SHORT")
    ratio=len(y)/target
    # Pitch-preserving pacing only, bounded to prevent unnatural compression.
    if ratio>1.0 or ratio<0.82:
        require(0.70<=ratio<=1.35,"REPAIR_PACE_OUT_OF_RANGE")
        sf.write(res,y,RATE,subtype="PCM_16")
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(res),"-af",f"atempo={ratio:.8f}","-c:a","pcm_s16le",str(paced)],check=True)
        y,_=sf.read(paced,dtype="float32")
    require(len(y)<=length-2*round(0.008*RATE),"REPAIR_VOICE_DOES_NOT_FIT")
    fade=min(round(0.012*RATE),len(y)//4)
    y[:fade]*=np.linspace(0,1,fade); y[-fade:]*=np.linspace(1,0,fade)
    oldf=old.astype(np.float32)/32768.0
    scale=min(0.92/max(float(np.max(np.abs(y))),1e-6),max(0.65,min(1.5,float(np.sqrt(np.mean(oldf**2)))/max(float(np.sqrt(np.mean(y**2))),1e-6))))
    y*=scale
    result=np.zeros(length,dtype="<i2")
    start=(length-len(y))//2
    result[start:start+len(y)]=np.rint(np.clip(y,-0.98,0.98)*32767).astype("<i2")
    return result,{"original_synthesis_seconds":len(arr)/sr,"fitted_seconds":len(y)/RATE,"pace_ratio":ratio,"seed":seed}
def repair(archive, qa_archive, out):
    import numpy as np
    import soundfile as sf
    from blue_onnx import BlueTTS
    from huggingface_hub import snapshot_download,hf_hub_download
    from faster_whisper import WhisperModel
    from scripts.kesher_owner_positivity_asr import similarity
    require(p.sha_file(archive)==ARCHIVE_SHA and p.sha_file(qa_archive)==QA_SHA,"EXACT_ARCHIVE_REQUIRED")
    scripts,provenance=p.source_check(public=True)
    with zipfile.ZipFile(qa_archive) as z:
        require(z.namelist()==["targeted-audio-review.json"],"QA_ARCHIVE_SCOPE")
        q=z.read("targeted-audio-review.json")
    require(sha(q)==QA_JSON_SHA,"QA_REPORT_SHA")
    qa=json.loads(q)
    require(qa["source_slug"]==p.SLUG and qa["content_sha256"]==p.SOURCE_SHA and qa["asr_revision"]==p.IVRIT_REV,"QA_REPORT_IDENTITY")
    require(not out.exists(),"REPAIR_OUTPUT_EXISTS")
    out.mkdir(parents=True)
    expected={"asr-review.json"}
    for kind in p.KINDS:
        expected.update((f"{kind}.mp4",f"{kind}-manifest.json",f"{kind}-review-voice.wav",f"{kind}-visual-contact-sheet.jpg",f"{kind}-asr.txt"))
        expected.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1,9))
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist())==expected and len(z.namelist())==len(expected),"REPAIR_ARCHIVE_SCOPE")
        for n in expected:(out/n).write_bytes(z.read(n))
    for kind in p.KINDS:
        m=json.loads((out/f"{kind}-manifest.json").read_text())
        require(m["source_slug"]==p.SLUG and m["content_sha256"]==p.SOURCE_SHA and m["script_segments"]==scripts[kind] and m["public"] is False and m["uploaded"] is False,"REPAIR_SOURCE_IDENTITY")
        require(p.sha_file(out/f"{kind}.mp4")==p.FINAL_VIDEO_SHA[kind] and p.sha_file(out/f"{kind}-review-voice.wav")==p.FINAL_AUDIO_SHA[kind] and qa["media"][kind]["audio_sha256"]==p.FINAL_AUDIO_SHA[kind],"REPAIR_MEDIA_IDENTITY")
        require(m["voice_provenance"]["model_revision"]==p.MODEL_SHA and m["voice_provenance"]["g2p_revision"]==p.G2P_SHA and m["voice_provenance"]["weights_license"]=="MIT" and m["voice_provenance"]["reference_license"]=="CC BY 4.0","REPAIR_VOICE_RIGHTS")
    modeldir=Path(snapshot_download("notmax123/BlueTTS2.5-onnx",revision=p.MODEL_SHA,allow_patterns=["*.onnx","*.npz","*.json","voices/*.json"]))
    g2p=hf_hub_download("notmax123/RenikudPlus",filename="model_int8.onnx",revision=p.G2P_SHA)
    tts=BlueTTS(onnx_dir=str(modeldir),style_json=str(modeldir/"voices/libri_female_6147.json"),renikud_path=g2p)
    report={"source_slug":p.SLUG,"content_sha256":p.SOURCE_SHA,"input_archive_sha256":ARCHIVE_SHA,"input_qa_sha256":QA_JSON_SHA,"review":"QA_PENDING_OWNER_INTERPRETATION","human_listening":False,"media":{}}
    for kind in p.KINDS:
        video=out/f"{kind}.mp4";m=json.loads((out/f"{kind}-manifest.json").read_text());original=pcm(video);packets=packet_hashes(video)
        cuts=cut_samples(kind,len(original));replacements=[];details=[]
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            for i,(a,b,text,phones) in enumerate(cuts):
                require(text in " ".join(scripts[kind]),"REPAIR_SCRIPT_PHRASE_NOT_APPROVED")
                replacement,fit=fit_voice(tts,phones,b-a,original[a:b],tmp,20261111+i+(100 if kind=="short" else 0))
                replacements.append((a,b,replacement));details.append({"start_sample":a,"end_sample":b,"text":text,"phonemes":phones,"replacement_pcm_sha256":sha(replacement.tobytes()),**fit})
            edited=splice(original,replacements)
            wav=tmp/"edited.wav";candidate=tmp/"candidate.mp4"
            sf.write(wav,edited,RATE,subtype="PCM_16")
            subprocess.run(["ffmpeg","-v","error","-y","-i",str(video),"-i",str(wav),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","160k","-movflags","+faststart",str(candidate)],check=True)
            require(packet_hashes(candidate)==packets,"VIDEO_PACKETS_CHANGED")
            media=p.verify_video(candidate,kind)
            require(abs(media["duration"]-m["media"]["duration"])<0.15,"REPAIR_DURATION_CHANGED")
            video.write_bytes(candidate.read_bytes())
        wav=out/f"{kind}-review-voice.wav"
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(video),"-map","0:a:0","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],check=True)
        m["video_sha256"]=p.sha_file(video);m["audio_sha256"]=p.sha_file(wav);m["media"]=media
        m["targeted_audio_repair"]={"input_artifact_id":13813995846,"input_archive_sha256":ARCHIVE_SHA,"input_qa_artifact_id":13815352755,"input_qa_sha256":QA_JSON_SHA,"original_video_sha256":p.FINAL_VIDEO_SHA[kind],"original_pcm_sha256":sha(original.tobytes()),"edited_pcm_sha256":sha(edited.tobytes()),"video_packet_hashes_sha256":sha("\n".join(packets).encode()),"video_packets_preserved":True,"outside_cut_pcm_preserved_before_aac_encode":True,"sample_rate":RATE,"cuts":details,"method":"same licensed voice, explicit corrected phonemes, only identified quiet-boundary audio windows; no video rerender"}
        (out/f"{kind}-manifest.json").write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        report["media"][kind]={"video_sha256":m["video_sha256"],"audio_sha256":m["audio_sha256"],"cuts":details}
        print("TARGETED_PRONUNCIATION_REPAIR_READY",kind,m["video_sha256"],flush=True)
    # Fresh actual final-audio recognition, no automatic editorial approval.
    modelpath=snapshot_download(p.IVRIT_REPO,revision=p.IVRIT_REV,allow_patterns=["model.bin","config.json","tokenizer.json","vocabulary.json","preprocessor_config.json"])
    model=WhisperModel(modelpath,device="cpu",compute_type="int8",cpu_threads=4)
    for kind in p.KINDS:
        wav=out/f"{kind}-review-voice.wav";samples,sr=sf.read(wav,dtype="float32")
        def recognize(x):
            segs,_=model.transcribe(x,language="he",beam_size=5,condition_on_previous_text=False,vad_filter=False,word_timestamps=True)
            return " ".join(s.text.strip() for s in segs)
        full=recognize(samples);row=report["media"][kind];row["full_transcript"]=full;row["similarity"]=similarity(full," ".join(scripts[kind]))
        for detail in row["cuts"]:
            a=detail["start_sample"]/RATE;b=detail["end_sample"]/RATE
            detail["actual_repaired_audio_transcript"]=recognize(samples[max(0,round((a-.15)*sr)):min(len(samples),round((b+.15)*sr))])
        (out/f"{kind}-asr.txt").write_text(full+"\n",encoding="utf-8")
        print("REPAIRED_ACTUAL_AUDIO",kind,full,flush=True)
    (out/"asr-review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REPAIRED_AUDIO_EVIDENCE_READY_NO_PUBLICATION",flush=True)
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--archive",type=Path,required=True);a.add_argument("--qa-archive",type=Path,required=True);a.add_argument("--output",type=Path,required=True);x=a.parse_args();repair(x.archive,x.qa_archive,x.output)
