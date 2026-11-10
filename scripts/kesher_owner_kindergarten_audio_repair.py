#!/usr/bin/env python3
"""Private targeted repair: reuse exact reviewed Short speech; no new TTS."""
from __future__ import annotations
import argparse, hashlib, json, math, struct, subprocess, tempfile, wave, zipfile
from pathlib import Path

SLUG = 'child-not-playing-kindergarten'
SOURCE_SHA = '60374e686f7857610eeee5594af17f52a80223788650ef467ce27f5ec824dcaa'
ARCHIVE_ID = 13787755454
ARCHIVE_SHA = 'bfd6fca1b962555d34ae02e652ec02775ccfd9e3d21d43c2b4ade2557c5b6ccb'
OVERVIEW_SHA = 'bfbd515e6d852935298b8cfdde5b037a5eb1abced9e21e36d9271937449c369e'
SHORT_SHA = '9e798a40b8a11bf07314662ebe7dc789c9c3f9c3de41a010924616d78f172a09'
OLD = 'המטרה היא קשר, בחירה וביטחון, לא ילד מוחצן.'
NEW = 'המטרה היא ילד שמרגיש בטוח, לא ילד מוחצן.'
RATE = 44100
OVERVIEW_CUT = (3235176, 3376958)
SHORT_CUT = (1163799, 1290366)
KINDS = ('overview', 'short')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def command(*args):
    return subprocess.check_output([str(a) for a in args], stderr=subprocess.PIPE)

def pcm(path):
    return command('ffmpeg','-v','error','-i',path,'-map','0:a:0','-ac','1','-ar',RATE,'-f','s16le','-')

def video_packets(path):
    return command('ffmpeg','-v','error','-i',path,'-map','0:v:0','-c','copy','-f','h264','-')

def quiet_at(data, sample):
    radius=RATE//200
    chunk=data[(sample-radius)*2:(sample+radius)*2]
    vals=struct.unpack('<'+'h'*(len(chunk)//2),chunk)
    return math.sqrt(sum(v*v for v in vals)/len(vals))<180

def splice(original, short):
    a,b=OVERVIEW_CUT; c,d=SHORT_CUT
    require(len(original)%2==0 and len(short)%2==0 and b*2<len(original) and d*2<len(short),'PCM_BOUNDARY')
    require(all(quiet_at(data,n) for data,n in ((original,a),(original,b),(short,c),(short,d))),'CUT_NOT_SILENT')
    replacement=short[c*2:d*2]; extra=(b-a)-(d-c)
    require(extra>=0,'REPLACEMENT_TOO_LONG')
    left=extra//2
    result=original[:a*2]+b'\0'*(left*2)+replacement+b'\0'*((extra-left)*2)+original[b*2:]
    require(len(result)==len(original) and result[:a*2]==original[:a*2] and result[b*2:]==original[b*2:],'OUTSIDE_PCM_CHANGED')
    return result

def expected_names():
    names={'asr-review.json'}
    for k in KINDS:
        names.update((f'{k}.mp4',f'{k}-manifest.json',f'{k}-review-voice.wav',f'{k}-visual-contact-sheet.jpg',f'{k}-asr.txt'))
        names.update(f'{k}-frame-{i:02d}.jpg' for i in range(1,9))
    return names

def repair(archive,out):
    require(file_sha(archive)==ARCHIVE_SHA,'ARCHIVE_SHA_MISMATCH')
    require(not out.exists(),'OUTPUT_ALREADY_EXISTS')
    out.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        require(len(names)==len(set(names)) and set(names)==expected_names() and sum(x.file_size for x in z.infolist())<100_000_000,'ARCHIVE_FILE_SET')
        for n in names:
            (out/n).write_bytes(z.read(n))
    overview=out/'overview.mp4'; short=out/'short.mp4'
    require(file_sha(overview)==OVERVIEW_SHA and file_sha(short)==SHORT_SHA,'ORIGINAL_MEDIA_SHA')
    manifest_path=out/'overview-manifest.json'
    m=json.loads(manifest_path.read_text()); sm=json.loads((out/'short-manifest.json').read_text())
    require(all(x['source_slug']==SLUG and x['content_sha256']==SOURCE_SHA and x['public'] is False and x['uploaded'] is False for x in (m,sm)),'SOURCE_IDENTITY')
    require(m['script_segments'][-1].count(OLD)==1 and NEW in sm['script_segments'][-1],'SCRIPT_PHRASE_MISMATCH')
    oldpcm=pcm(overview); shortpcm=pcm(short); repaired=splice(oldpcm,shortpcm)
    oldvideo=video_packets(overview)
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td); wav=tmp/'repair.wav'; candidate=tmp/'overview.mp4'
        with wave.open(str(wav),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(repaired)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(overview),'-i',str(wav),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart',str(candidate)],check=True)
        require(video_packets(candidate)==oldvideo,'VIDEO_PACKETS_CHANGED')
        overview.write_bytes(candidate.read_bytes())
    require(file_sha(short)==SHORT_SHA,'SHORT_CHANGED')
    wav=out/'overview-review-voice.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(overview),'-map','0:a:0','-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)],check=True)
    probe=json.loads(command('ffprobe','-v','error','-show_streams','-show_format','-of','json',overview))
    vs=next(x for x in probe['streams'] if x['codec_type']=='video')
    require((vs['width'],vs['height'])==(1280,720) and abs(float(probe['format']['duration'])-m['media']['duration'])<0.15,'REPAIRED_MEDIA_DIMENSION_OR_DURATION')
    m['script_segments'][-1]=m['script_segments'][-1].replace(OLD,NEW)
    m['script_sha256']=sha('\n'.join(m['script_segments']).encode())
    m['video_sha256']=file_sha(overview);m['audio_sha256']=file_sha(wav)
    m['media']['duration']=round(float(probe['format']['duration']),3)
    m['targeted_audio_repair']={
        'input_artifact_id':ARCHIVE_ID,'input_archive_sha256':ARCHIVE_SHA,
        'original_overview_sha256':OVERVIEW_SHA,'unchanged_short_sha256':SHORT_SHA,
        'overview_cut_samples':list(OVERVIEW_CUT),'short_cut_samples':list(SHORT_CUT),
        'sample_rate':RATE,'video_packet_sha256':sha(oldvideo),
        'original_pcm_sha256':sha(oldpcm),'edited_pcm_sha256':sha(repaired),
        'outside_cut_pcm_sha256':sha(oldpcm[:OVERVIEW_CUT[0]*2]+oldpcm[OVERVIEW_CUT[1]*2:]),
        'outside_cut_pcm_preserved_before_aac_encode':True,'video_packets_preserved':True,
        'original_short_preserved':True,'method':'reuse exact independently transcribed Short sentence at silent boundaries; no new TTS',
    }
    manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'overview-asr.txt').unlink();(out/'asr-review.json').unlink()
    print('TARGETED_AUDIO_REPAIR_READY',m['video_sha256'],m['audio_sha256'],m['targeted_audio_repair'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();repair(a.archive,a.output)
