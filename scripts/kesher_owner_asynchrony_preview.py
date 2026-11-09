#!/usr/bin/env python3
"""OWNER-direct private KESHER audiovisual previews. Never uploads or approves media."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = "gifted-asynchronous-development-inner-loneliness"
SOURCE_SHA = "7b6ae2e8dc3182d798edbf19c2d95e576b02ab093c5e2bf04bad91113a716a00"
RESEARCH = ROOT / "research/kesher-gifted-asynchrony-20261109.md"
PHOTOS = ROOT / "research/kesher-asynchrony-photo-provenance.json"
ARTICLE = "https://kesher.saharoni.com/blog/" + SLUG
FPS = 25
SOURCE_KINDS = ("overview", "short")
MODEL_SHA = "95feb5d0cbfc8e5a95bffb067d03537cbf35be3e"
G2P_SHA = "679c56ca449d41873fb8ff7711ddf7563d28198f"

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

def source_scripts():
    doc = RESEARCH.read_text(encoding="utf-8")
    if f"source_slug: {SLUG}" not in doc or f"content_sha256: {SOURCE_SHA}" not in doc:
        raise ValueError("SOURCE_IDENTITY_MISMATCH")
    overview = re.findall(r'^Scene [1-5], [^\n]*?: "([^"\n]+)"', doc, re.M)
    short = re.findall(r'^[1-5]\. "([^"\n]+)"', doc, re.M)
    if len(overview) != 5 or len(short) != 5:
        raise ValueError(f"OWNER_SOURCE_SCRIPT_MISMATCH overview={len(overview)} short={len(short)}")
    forbidden = ("פי עשר", "עשרות אחוזים", "המחקר מוכיח שכולם", "כל ילד מחונן בודד")
    if any(phrase in "\n".join(overview+short) for phrase in forbidden):
        raise ValueError("UNSUPPORTED_UNIVERSAL_CLAIM")
    return {"overview": overview, "short": short}

def source_check(*, public=False):
    entries = json.loads((ROOT / "src/data/postsRecent.json").read_text(encoding="utf-8"))
    selected = [x for x in entries if x.get("slug") == SLUG]
    if len(selected) != 1 or selected[0].get("image") != "/images/blog/gifted-asynchrony-parent-child-hero.jpg":
        raise ValueError("ARTICLE_SOURCE_NOT_UNIQUE_OR_IMAGE_MISMATCH")
    parser = TextExtractor()
    parser.feed(selected[0]["content"])
    current_sha = sha_bytes(html.unescape("\n\n".join(parser.parts)).encode("utf-8"))
    if current_sha != SOURCE_SHA:
        raise ValueError(f"ARTICLE_SOURCE_SHA_MISMATCH {current_sha}")
    scripts = source_scripts()
    provenance = json.loads(PHOTOS.read_text(encoding="utf-8"))
    if provenance.get("source_slug") != SLUG or provenance.get("content_sha256") != SOURCE_SHA:
        raise ValueError("PHOTO_PROVENANCE_SOURCE_MISMATCH")
    images = provenance["images"]
    if len(images) != 3 or len({x.get("path") for x in images}) != len(images):
        raise ValueError("THREE_UNIQUE_IMAGES_REQUIRED")
    for item in images:
        path = str(item.get("path", ""))
        if not re.fullmatch(r"public/images/blog/[a-z0-9-]+\.jpg", path):
            raise ValueError("PHOTO_UNSAFE_PATH")
        src = ROOT / path
        if src.is_symlink() or not src.is_file() or sha_file(src) != item["sha256"]:
            raise ValueError("PHOTO_MISSING_OR_CHANGED")
        if item.get("generated_for") != SLUG or not str(item.get("license_url", "")).startswith("https://openai.com/"):
            raise ValueError("PHOTO_RIGHTS_PROVENANCE_REQUIRED")
    if public:
        import requests
        page = requests.get(ARTICLE, timeout=30, headers={"User-Agent": "Kesher-Owner-Direct-Preview/1"})
        if (page.status_code != 200 or selected[0]["title"] not in page.text
                or f'rel="canonical" href="{ARTICLE}"' not in page.text
                or selected[0]["image"].lstrip("/") not in page.text):
            raise ValueError("PUBLIC_ARTICLE_NOT_VERIFIED")
    return scripts, provenance

def run(args, *, quiet=False):
    proc = subprocess.run([str(x) for x in args], text=True,
                          capture_output=quiet, check=True, timeout=900)
    return proc.stdout.strip() if quiet else ""

def length(path: Path):
    return float(run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",str(path)],quiet=True))

def make_image(src: Path, target: Path, kind: str):
    from PIL import Image, ImageFilter, ImageOps
    im = Image.open(src).convert("RGB")
    size = (1280, 720) if kind == "overview" else (1080, 1920)
    if kind == "overview":
        if im.height > im.width:
            # Keep the full original portrait, including eyes and face, rather than
            # cropping a tall source into a chin-only 16:9 close-up.
            background = ImageOps.fit(im, size, method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(38))
            foreground = ImageOps.contain(im, (size[0] - 32, size[1] - 32), method=Image.Resampling.LANCZOS)
            background.paste(foreground, ((size[0] - foreground.width) // 2, (size[1] - foreground.height) // 2))
            panel = background
        else:
            panel = ImageOps.fit(im, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    else:
        background = ImageOps.fit(im, size, method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(35))
        foreground = ImageOps.contain(im, (1060, 1530), method=Image.Resampling.LANCZOS)
        background.paste(foreground, ((size[0]-foreground.width)//2, (size[1]-foreground.height)//2))
        panel = background
    panel.save(target, "JPEG", quality=92, optimize=True)

def encode_scene(photo: Path, wav: Path, dest: Path, kind: str, seconds: float, reverse: bool):
    w,h = ((1280,720) if kind=="overview" else (1080,1920))
    zoom = ("min(zoom+0.00014,1.085)" if not reverse else "if(eq(on,0),1.075,max(zoom-0.00012,1.0))")
    expr = ("zoompan=z='" + zoom + "':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            + f"d=1:s={w}x{h}:fps={FPS},format=yuv420p[v]")
    run(["ffmpeg","-hide_banner","-v","error","-y","-loop","1","-framerate",str(FPS),
         "-i",str(photo),"-i",str(wav),"-filter_complex",expr,
         "-map","[v]","-map","1:a","-t",f"{seconds:.4f}",
         "-c:v","libx264","-preset","veryfast","-crf","23",
         "-c:a","aac","-b:a","128k","-movflags","+faststart",str(dest)])
    if not dest.is_file() or dest.stat().st_size < 10000:
        raise RuntimeError("EMPTY_SCENE")

def join_scenes(parts: list[Path], dest: Path):
    lst = dest.with_suffix(".ffconcat")
    lines = ["ffconcat version 1.0"]
    for part in parts:
        lines.append("file '" + str(part.resolve()) + "'")
    lst.write_text("\n".join(lines)+"\n",encoding="utf-8")
    run(["ffmpeg","-hide_banner","-v","error","-y","-safe","0","-f","concat","-i",str(lst),
         "-c","copy","-movflags","+faststart",str(dest)])

def merge_wavs(paths: list[Path], dest: Path):
    import numpy as np
    import soundfile as sf
    audio = []
    rate = None
    for p in paths:
        data,sr = sf.read(p,dtype="float32")
        if rate is not None and sr != rate:
            raise ValueError("VOICE_SAMPLE_RATE_CHANGED")
        rate = sr
        audio.append(data.reshape(-1))
        audio.append(np.zeros(round(sr*0.11),dtype="float32"))
    sf.write(str(dest),np.concatenate(audio),rate,subtype="PCM_16")

def review_frames(video: Path, directory: Path, kind: str):
    from PIL import Image,ImageOps
    runtime = length(video)
    samples = []
    for i in range(8):
        seconds = (i + 0.5) * runtime / 8
        frame = directory / f"{kind}-frame-{i+1:02d}.jpg"
        run(["ffmpeg","-hide_banner","-v","error","-y","-ss",f"{seconds:.3f}",
             "-i",str(video),"-frames:v","1",str(frame)])
        samples.append(frame)
    width,height = ((480,270) if kind=="overview" else (270,480))
    sheet = Image.new("RGB",(width*4,height*2),"#f4f4f4")
    for i,p in enumerate(samples):
        im=Image.open(p).convert("RGB")
        tile=ImageOps.fit(im,(width,height),method=Image.Resampling.LANCZOS)
        sheet.paste(tile,((i%4)*width,(i//4)*height))
    out=directory/f"{kind}-visual-contact-sheet.jpg"
    sheet.save(out,quality=88)
    return samples,out

def verify_video(video: Path, kind: str):
    details=json.loads(run(["ffprobe","-v","error","-show_streams","-show_format",
                            "-of","json",str(video)],quiet=True))
    video_stream=next(x for x in details["streams"] if x["codec_type"]=="video")
    audio_stream=next(x for x in details["streams"] if x["codec_type"]=="audio")
    dim=((1280,720) if kind=="overview" else (1080,1920))
    if (int(video_stream["width"]),int(video_stream["height"])) != dim or video_stream["codec_name"]!="h264" or audio_stream["codec_name"]!="aac":
        raise ValueError("INVALID_MEDIA_FORMAT")
    seconds=float(details["format"]["duration"])
    if not (60<seconds<160 if kind=="overview" else 28<seconds<95):
        raise ValueError(f"INVALID_DURATION {kind} {seconds}")
    run(["ffmpeg","-hide_banner","-v","error","-i",str(video),"-f","null","-"])
    return {"width":dim[0],"height":dim[1],"duration":round(seconds,3),"codecs":["h264","aac"]}

def preview(out: Path):
    scripts, provenance = source_check(public=True)
    if out.exists():
        raise ValueError("PREVIEW_DESTINATION_EXISTS")
    out.mkdir(parents=True)
    # Reuse the previously reviewed MIT/CC-BY voice renderer, but not its Vantage topic/script.
    sys.path.insert(0,str(ROOT/"scripts"))
    import kesher_owner_vantage_short as voice_module
    all_scenes=[(f"{kind}-{i+1}",text) for kind in SOURCE_KINDS for i,text in enumerate(scripts[kind])]
    voice_module.SCENES=all_scenes
    voices,durations,voice_info=voice_module.speak(out)
    if len(voices)!=10 or (voice_info["model_revision"]!=MODEL_SHA or voice_info["g2p_revision"]!=G2P_SHA
                           or voice_info["weights_license"]!="MIT" or voice_info["reference_license"]!="CC BY 4.0"
                           or voice_info["g2p_license"]!="Apache-2.0"):
        raise ValueError("LICENSED_TTS_PROVENANCE_CHANGED")
    for kind_index,kind in enumerate(SOURCE_KINDS):
        loc=out/kind
        loc.mkdir()
        voicepaths=voices[kind_index*5:(kind_index+1)*5]
        durations_kind=durations[kind_index*5:(kind_index+1)*5]
        segments=[]
        for i in range(5):
            photo_index=[0,2,1,0,2][i] if kind=="overview" else [2,0,1,2,0][i]
            original=ROOT/provenance["images"][photo_index]["path"]
            canvas=loc/f"visual-{i+1:02d}.jpg"
            make_image(original,canvas,kind)
            segment=loc/f"segment-{i+1:02d}.mp4"
            encode_scene(canvas,voicepaths[i],segment,kind,durations_kind[i]+0.05,reverse=(i%2==1))
            segments.append(segment)
        result=out/f"{kind}.mp4"
        join_scenes(segments,result)
        voice_wav=out/f"{kind}-review-voice.wav"
        merge_wavs(voicepaths,voice_wav)
        meta=verify_video(result,kind)
        frames,contact=review_frames(result,out,kind)
        manifest={
          "source_slug":SLUG,"content_sha256":SOURCE_SHA,"kind":kind,
          "media_item_id":f"owner-{kind}-20261109-{SOURCE_SHA[:12]}",
          "source_file":"research/kesher-gifted-asynchrony-20261109.md",
          "source_file_sha256":sha_file(RESEARCH),
          "script_segments":scripts[kind],
          "script_sha256":sha_bytes("\n".join(scripts[kind]).encode()),
          "visual_sources":provenance["images"],
          "voice_provenance":voice_info,
          "voice_model":"BlueTTS2.5-onnx:libri_female_6147",
          "video_sha256":sha_file(result),
          "audio_sha256":sha_file(voice_wav),
          "contact_sha256":sha_file(contact),
          "frame_sha256":[sha_file(x) for x in frames],
          "media":meta,
          "owner_editorial_qa":"PENDING_GENUINE_INDEPENDENT_REVIEW",
          "uploaded":False,"public":False
        }
        (out/f"{kind}-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"OWNER_PREVIEW_READY {kind} item={manifest['media_item_id']} sha={manifest['video_sha256']} seconds={meta['duration']} qa=PENDING",flush=True)
    print("PRIVATE_PREVIEWS_READY_NO_UPLOAD",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=["preflight","preview"])
    p.add_argument("--source-sha",required=True)
    p.add_argument("--output",type=Path,default=Path("owner-asynchrony-media-output"))
    a=p.parse_args()
    if a.source_sha!=SOURCE_SHA:
        raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    if a.operation=="preflight":
        source_check(public=False)
        print("SOURCE_PREFLIGHT_OK",SLUG,SOURCE_SHA)
    else:
        preview(a.output)
