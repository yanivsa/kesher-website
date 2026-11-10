import unittest
from pathlib import Path
from scripts.kesher_owner_positivity_youtube_probe import SLUG,SHA,CHANNEL,KIND_MARKERS,MIDYEAR_SLUG,MIDYEAR_SHA,MIDYEAR_BODY_SHA,midyear_candidates,SEPARATE_ROOM_SLUG,SEPARATE_ROOM_SHA,SEPARATE_ROOM_BODY_SHA,separate_room_candidates,find_midyear_candidates
class PositivityYoutubeReadOnlyTests(unittest.TestCase):
    def test_bound_identity(self):
        self.assertEqual(SLUG,"positivity-resonance-marriage-micro-moments")
        self.assertEqual(SHA,"6bb5723bbadc7b78725e4cdb477857e7194cca47c1140f27d1c4f3921b6e2d5f")
        self.assertEqual(CHANNEL,"UCx5fEFvdVf28HLAR2dFW64Q")
        self.assertEqual(len(KIND_MARKERS),2)
    def test_midyear_exact_and_legacy_candidates(self):
        self.assertEqual(MIDYEAR_SLUG, "changing-kindergarten-midyear")
        self.assertEqual(MIDYEAR_SHA, "5b0d6c5e8ba2c7fb001d1b7944a4abca1dbe4d5b0248889466dca4225e393a1a")
        def record(vid, title, desc, privacy="public"):
            return {"id": vid, "snippet": {"channelId": CHANNEL, "title": title, "description": desc}, "status": {"privacyStatus": privacy}}
        rows = [record("abcdefghijk", "מעבר לגן באמצע השנה", ""),
                record("bcdefghijkl", "כותרת אחרת", "https://kesher.saharoni.com/blog/" + MIDYEAR_SLUG, "private"),
                record("cdefghijklm", "מעבר לגן עירייה", "transition-to-municipal-kindergarten"),
                record("defghijklmn", "כותרת ישנה", "content_sha256=" + MIDYEAR_BODY_SHA)]
        result = midyear_candidates(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["public_id"], "abcdefghijk")
        self.assertIsNone(result[1]["public_id"])
        self.assertIsNone(result[1]["title"])
        self.assertEqual(len(result[1]["id_fingerprint"]), 12)
        self.assertEqual(result[2]["public_id"], "defghijklmn")
        rows[0]["snippet"]["channelId"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_CHANNEL"):
            midyear_candidates(rows)

    def test_separate_room_exact_and_legacy_candidates(self):
        def record(vid, title, desc, privacy="public"):
            return {"id": vid, "snippet": {"channelId": CHANNEL, "title": title, "description": desc}, "status": {"privacyStatus": privacy}}
        rows = [record("abcdefghijk", "מעבר לחדר נפרד", ""),
                record("bcdefghijkl", "כותרת אחרת", "https://kesher.saharoni.com/blog/" + SEPARATE_ROOM_SLUG, "private"),
                record("cdefghijklm", "איך לעבור למיטת מעבר", "toddler-bed-transition"),
                record("defghijklmn", "כותרת ישנה", "content_sha256=" + SEPARATE_ROOM_BODY_SHA),
                record("efghijklmno", "איך לעזור לילד לישון בחדר שלו?", "")]
        result = separate_room_candidates(rows)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["public_id"], "abcdefghijk")
        self.assertIsNone(result[1]["public_id"])
        self.assertIsNone(result[1]["title"])
        self.assertEqual(len(result[1]["id_fingerprint"]), 12)
        self.assertEqual(result[2]["public_id"], "defghijklmn")
        self.assertEqual(result[3]["public_id"], "efghijklmno")
        rows[0]["snippet"]["channelId"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_CHANNEL"):
            separate_room_candidates(rows)
        with self.assertRaisesRegex(RuntimeError, "EXACT_USER_APPROVED_SOURCE_REQUIRED"):
            find_midyear_candidates(None, None, slug=SEPARATE_ROOM_SLUG, source_sha=MIDYEAR_SHA)

    def test_separate_room_script_bound_to_exact_source(self):
        import hashlib, json
        from scripts.kesher_daily_pipeline import clean_article_html, source_metadata
        plan = json.loads(Path("research/kesher-separate-room-media-20261110.json").read_text())
        posts = json.loads(Path("src/data/postsRecent.json").read_text())
        rows = [p for p in posts if p.get("slug") == SEPARATE_ROOM_SLUG]
        self.assertEqual(len(rows), 1)
        self.assertEqual(source_metadata(rows[0])["content_sha256"], SEPARATE_ROOM_SHA)
        self.assertEqual(hashlib.sha256(clean_article_html(rows[0]["content"]).encode()).hexdigest(), SEPARATE_ROOM_BODY_SHA)
        self.assertEqual((plan["source_slug"], plan["content_sha256"], plan["article_body_sha256"]),
                         (SEPARATE_ROOM_SLUG, SEPARATE_ROOM_SHA, SEPARATE_ROOM_BODY_SHA))
        self.assertEqual(plan["status"], "SCRIPT_ONLY_PRIVATE_RENDER_NOT_STARTED")
        for kind, count in (("overview", 6), ("short", 4)):
            self.assertEqual(len(plan["scripts"][kind]), count)
            text = " ".join(plan["scripts"][kind])
            self.assertIn("לפחות עד גיל חצי שנה", text)
            self.assertIn("עדיף עד גיל שנה", text)
            self.assertIn("הקישור בתיאור", text)
            self.assertNotRegex(text, r"[A-Za-z]")
        self.assertIn("אין גיל מדויק", " ".join(plan["scripts"]["overview"]))
        self.assertIn("בלי כריות", " ".join(plan["scripts"]["overview"]))

    def test_read_only_source(self):
        source=Path("scripts/kesher_owner_positivity_youtube_probe.py").read_text()
        for forbidden in ("videos().insert(", "videos().update(", "videos().delete(", "MediaFileUpload", "upload_only(", "workflow_dispatch", "https://www.googleapis.com/upload"):
            self.assertNotIn(forbidden,source)
if __name__=="__main__": unittest.main()
