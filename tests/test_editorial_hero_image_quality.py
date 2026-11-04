"""Regression gates: publish photographs that match a specific article, not vector placeholders."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.kesher_runtime import article_images

ROOT = Path(__file__).resolve().parents[1]


def load_worker(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / ".github" / "scripts" / filename
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class EditorialHeroQualityTests(unittest.TestCase):
    def test_publication_never_routes_to_local_vector_illustrations(self):
        v5 = load_worker("article-image-worker-v5.py", "hero_quality_v5")
        self.assertIsNot(v5.v4.local_fallback, v5.local_editorial_fallback)
        self.assertIs(v5.v4.local_fallback, v5.v4.v3.local_fallback)

    def test_preschool_requires_specific_scene(self):
        v4 = load_worker("article-image-worker-v4.py", "hero_quality_v4")
        post = {
            "id": "child-does-not-want-kindergarten",
            "title": "ילד לא רוצה ללכת לגן: מה עושים?",
            "category": "הנחיית הורים",
            "excerpt": "קושי בפרידה מההורים בכניסה לגן",
        }
        self.assertTrue(v4._requires_specific_visual_scene(post))
        self.assertGreater(
            v4._topic_score(post, "public/images/generated/blog/separation-anxiety-morning-dropoff.jpg"), 0
        )
        self.assertEqual(
            v4._topic_score(post, "public/images/generated/blog/defensiveness-in-relationships.jpg"), 0
        )

        # An available, valid, distinct but unrelated photograph is NOT a
        # fallback. The entire pipeline must fail closed in this case.
        with tempfile.TemporaryDirectory() as folder:
            picture = Path(folder) / "generic.jpg"
            picture.write_bytes(b"fixture-photograph")
            with mock.patch.object(v4, "_candidate_pool", return_value=[
                (0, "public/images/generated/blog/defensiveness-in-relationships.jpg"),
            ]), mock.patch.object(v4, "_trusted_candidate_path", return_value=picture), \\
                mock.patch.object(v4.core, "validate_candidate", return_value=(1200, 675, "jpg")):
                result = v4.local_fallback(
                    "yanivsa/kesher-website", post, "main", "", [],
                    existing_hashes=set(), existing_usage={}, last_used={},
                    banned_paths=set(),
                )
        self.assertIsNone(result)

    def test_visual_prompt_requires_a_real_kindergarten_scene(self):
        post = {
            "id": "child-does-not-want-kindergarten",
            "title": "ילד לא רוצה ללכת לגן",
            "excerpt": "הילד בוכה בפרידה בכניסה לגן",
        }
        scene = article_images.editorial_scene_direction(post)
        self.assertIn("kindergarten", scene)
        self.assertIn("educator", scene)
        prompt = article_images.image_prompt(post)
        self.assertIn("Required specific scene:", prompt)
        self.assertIn("no illustrations", prompt)
        self.assertIn("no generic stock-photo poses", prompt)

    def test_generic_parenting_not_treated_as_specific_scene(self):
        v4 = load_worker("article-image-worker-v4.py", "hero_quality_v4_generic")
        self.assertFalse(v4._requires_specific_visual_scene({
            "id": "helping-children-talk",
            "title": "איך לדבר עם הילדים",
            "excerpt": "תקשורת במשפחה",
        }))


if __name__ == "__main__":
    unittest.main()
