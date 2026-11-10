"""Hermetic identity and no-publish OWNER tests."""
import unittest
from pathlib import Path
from scripts import kesher_owner_asynchrony_preview as m

class OwnerAsynchronyPreview(unittest.TestCase):
    def test_source_and_three_original_photos(self):
        scripts, photos = m.source_check(public=False)
        self.assertEqual(len(scripts["overview"]), 5)
        self.assertEqual(len(scripts["short"]), 5)
        self.assertEqual(len(photos["images"]), 3)
        self.assertEqual(m.SOURCE_SHA, "7b6ae2e8dc3182d798edbf19c2d95e576b02ab093c5e2bf04bad91113a716a00")
    def test_tall_portrait_not_crop_to_chin(self):
        from tempfile import TemporaryDirectory
        from PIL import Image, ImageDraw
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "tall.jpg"
            out = Path(tmp) / "landscape.jpg"
            im = Image.new("RGB", (300, 900), "#ff0000")
            ImageDraw.Draw(im).rectangle((0, 450, 299, 899), fill="#0000ff")
            im.save(original, quality=95)
            m.make_image(original, out, "overview")
            reviewed = Image.open(out)
            self.assertEqual(reviewed.size, (1280, 720))
            top = reviewed.getpixel((640, 30))
            bottom = reviewed.getpixel((640, 690))
            self.assertGreater(top[0], top[2] * 2)
            self.assertGreater(bottom[2], bottom[0] * 2)
    def test_motion_filter_output_frame_driven(self):
        """Prevent static-slide regression: zoom must advance with output frame 'on'."""
        for kind in ("overview", "short"):
            for reverse in (False, True):
                expr = m.motion_filter(kind, 6.5, reverse)
                self.assertIn("*on", expr)
                self.assertIn("zoompan=", expr)
                self.assertIn("d=1", expr)
                self.assertIn("format=yuv420p[v]", expr)
        self.assertNotEqual(m.motion_filter("short", 6.5, False),
                            m.motion_filter("short", 6.5, True))
    def test_animated_scene_changes_over_time(self):
        """Decode two actual video frames, not just trust an FFmpeg success code."""
        import subprocess
        import numpy as np
        import soundfile as sf
        from tempfile import TemporaryDirectory
        from PIL import Image, ImageDraw, ImageChops, ImageStat
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, wav, video = root/"source.png", root/"voice.wav", root/"moving.mp4"
            picture = Image.new("RGB", (520, 520), "#113755")
            draw = ImageDraw.Draw(picture)
            draw.ellipse((30, 60, 260, 460), fill="#f2a12a")
            draw.rectangle((300, 30, 510, 250), fill="#c6187a")
            picture.save(src)
            sr = 22050
            wave = (0.06*np.sin(2*np.pi*330*np.arange(sr*4)/sr)).astype("float32")
            sf.write(wav, wave, sr, subtype="PCM_16")
            m.encode_scene(src, wav, video, "overview", 3.5, reverse=False)
            images = []
            for sec in (0.5, 3.0):
                result = subprocess.run(
                    ["ffmpeg","-v","error","-ss",str(sec),"-i",str(video),
                     "-frames:v","1","-vf","scale=240:135","-f","image2pipe",
                     "-vcodec","png","pipe:1"],
                    capture_output=True, check=True, timeout=35)
                from io import BytesIO
                images.append(Image.open(BytesIO(result.stdout)).convert("RGB"))
            difference = ImageChops.difference(*images)
            self.assertGreater(sum(ImageStat.Stat(difference).mean)/3, 1.5)

    def test_preview_is_nonpublishing(self):
        src = Path(m.__file__).read_text(encoding="utf-8")
        for value in ("YOUTUBE_CLIENT_SECRET","youtube.upload","videos().insert(","owner_publish"):
            self.assertNotIn(value,src)
    def test_evidence_safe_hebrew_scripts(self):
        scripts=m.source_scripts()
        text="\n".join(scripts["overview"]+scripts["short"])
        self.assertIn("מחוננות אינה גורמת בהכרח",text)
        self.assertIn("מותר לכעוס, אסור לשבור",text)
        for phrase in ("פי עשר","המחקר מוכיח שכולם","עשרות אחוזים"):
            self.assertNotIn(phrase,text)

if __name__=="__main__":
    unittest.main()
