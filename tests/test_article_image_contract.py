"""Behavioral regression coverage for trusted article/image proof consumers."""
from __future__ import annotations

import base64
import hashlib
import io
import importlib.util
import json
import struct
import sys
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from scripts.kesher_content_controller_v3_entry import V3GitHubClient
from scripts import kesher_article_contract as contract

ROOT = Path(__file__).resolve().parents[1]
HEAD = 'a' * 40
NEXT_HEAD = 'b' * 40
VISUAL = 'איור עריכתי מופשט בגוונים חמים עבור שיחה משפחתית תומכת'


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / '.github/scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def png(width=1200, height=675, shade=127):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + bytes([shade]) * width * 3) * height)) + chunk(b'IEND', b''))


def article_digest(post):
    # Independently constructed wire fixture, not the production proof builder.
    return hashlib.sha256(json.dumps(post, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class ArticleImageContractTests(unittest.TestCase):
    def setUp(self):
        self.worker = load('article-image-worker-v4')
        self.validator = load('validate-article-pr')
        self.cleanup = load('article-pr-controller')
        self.image = png()
        self.post = {
            'id': 'new-article', 'title': 'שיחה משפחתית תומכת',
            'content': '<p>' + 'מילה ' * 700 + '</p>' + '<h3>שאלה</h3>' * 5,
            'image': '/images/generated/blog/new-article.png', 'imageAlt': VISUAL,
        }
        self.base = [{'id': 'old-article'}]
        self.pr = {
            'number': 1, 'state': 'open', 'draft': False, 'title': 'Publish Kesher article: new-article',
            'base': {'sha': 'c' * 40, 'ref': 'main', 'repo': {'full_name': 'test/repo'}},
            'head': {'sha': HEAD, 'ref': 'article/new', 'repo': {'full_name': 'test/repo'}},
            'body': self.proof(),
        }
        self.files = [{'filename': p} for p in (
            'src/data/posts.json', 'public/rss.xml', 'public/images/generated/blog/new-article.png')]

    def proof(self, provider='Local', head=HEAD, **overrides):
        result, chain, source = {
            'Pixabay': ('stock', 'gemini-1/gemini-2/gemini-3/pexels/pixabay', 'https://pixabay.com/photos/example'),
            'Local': ('local_fallback', 'gemini-1/gemini-2/gemini-3/pexels/pixabay/local-curated', 'local://public/images/generated/blog/curated.png'),
            'Gemini': ('generated', 'gemini-1', 'https://ai.google.dev/models/gemini'),
                        'Pexels': ('stock', 'gemini-1/gemini-2/gemini-3/pexels', 'https://pexels.com/photo/example'),
        }[provider]
        fields = {
            'Image Pipeline Version': '2', 'Image Provider': provider, 'Image Attempt Chain': chain,
            'Image Generation Result': result, 'Image Source URL': source,
            'Image SHA-256': hashlib.sha256(self.image).hexdigest(), 'Image Dimensions': '1200x675',
            'Image Visual Match': VISUAL, 'Image Article ID': self.post['id'],
            'Image Article SHA-256': article_digest(self.post), 'Image Evidence Head': head,
        }
        fields.update(overrides)
        return '\n'.join(f'{key}: {value}' for key, value in fields.items())

    def worker_ready(self):
        payload = {'encoding': 'base64', 'content': base64.b64encode(self.image).decode()}
        def image_at_head(repo, path, ref, token):
            self.assertEqual((repo, path, ref),
                             ('test/repo', 'public' + self.post['image'], self.pr['head']['sha']))
            return payload
        with patch.object(self.worker.core, 'github_content', side_effect=image_at_head):
            return self.worker.trusted_image_present('test/repo', self.pr, self.post, 'unused')

    def controller_ready(self, payload=None):
        client = V3GitHubClient('test/repo', 'unused')
        payload = payload if payload is not None else {
            'sha': 'd' * 40, 'encoding': 'base64', 'content': base64.b64encode(self.image).decode(),
        }
        def posts_at_ref(path, ref):
            self.assertEqual(path, 'src/data/posts.json')
            return {self.pr['base']['sha']: self.base,
                    self.pr['head']['sha']: self.base + [self.post]}[ref]
        def image_at_head(method, url, **kwargs):
            self.assertEqual(method, 'GET')
            expected_path = quote('public' + self.post['image'], safe='/')
            self.assertIn(url, {
                f'{client.api}/contents/{expected_path}?ref={self.pr["head"]["sha"]}',
                f'{client.api}/git/blobs/{payload.get("sha", "")}',
            })
            return payload
        with patch.object(client, 'contents_json', side_effect=posts_at_ref), \
             patch.object(client, 'request', side_effect=image_at_head):
            return client.article_pr_image_ready(self.pr)

    def validate(self, **kwargs):
        return self.validator.evaluate(self.pr, self.files,
            kwargs.get('checks', [{'name': 'verify', 'conclusion': 'success', 'head_sha': HEAD}]),
            self.base, self.base + [self.post], kwargs.get('loader', lambda _: self.image))

    def test_all_providers_obey_one_contract_in_all_three_consumers(self):
        for provider in ('Local', 'Gemini', 'Pixabay', 'Pexels'):
            with self.subTest(provider=provider):
                if provider == 'Pexels':
                    self.post.update(imageCredit='צילום דרך Pexels', imageCreditUrl='https://pexels.com/photo/example')
                else:
                    self.post.pop('imageCredit', None); self.post.pop('imageCreditUrl', None)
                self.pr['body'] = self.proof(provider)
                self.assertTrue(self.worker_ready())
                self.assertTrue(self.controller_ready()[0])
                self.assertEqual(self.validate(), [])

    def test_content_gate_runs_before_ci_but_legacy_merge_gate_still_requires_ci(self):
        self.assertTrue(hasattr(self.validator, 'evaluate_content'), 'Missing independently callable content gate')
        check = self.validator.evaluate_content
        self.assertEqual(check(self.pr, self.files, self.base, self.base + [self.post], lambda _: self.image), [])
        self.assertIn('Fresh successful verify check is required on the current head', self.validate(checks=[]))
        self.post['content'] = '<p>קצר מדי</p>'
        self.pr['body'] = self.proof()
        errors = check(self.pr, self.files, self.base, self.base + [self.post], lambda _: self.image)
        self.assertTrue(any('700-1100' in error for error in errors))
        self.assertTrue(any('five H3' in error for error in errors))

    def test_rss_is_not_deleted_as_forbidden_by_cleanup(self):
        self.assertEqual(self.cleanup.forbidden_paths(self.files), [])
        self.assertEqual(self.cleanup.forbidden_paths([{'filename': '.github/workflows/evil.yml'}]),
                         ['.github/workflows/evil.yml'])

    def test_old_proof_rejected_after_article_head_or_image_changes(self):
        for mutation in ('article', 'head', 'image', 'path'):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.pr['body'] = self.proof('Local')
                if mutation == 'article':
                    self.post['content'] += '<p>מאמר שהשתנה</p>'
                elif mutation == 'head':
                    self.pr['head']['sha'] = NEXT_HEAD
                elif mutation == 'path':
                    self.post['image'] = '/images/generated/blog/copied.png'
                else:
                    self.image = png(shade=21)
                self.assertFalse(self.worker_ready())
                self.assertFalse(self.controller_ready()[0])
                self.assertTrue(self.validate())

    def test_existing_blob_without_image_bytes_is_not_ready(self):
        self.pr['body'] = self.proof('Local')
        self.assertEqual(self.worker.core.validate_candidate(self.image), (1200, 675, 'png'))
        self.assertFalse(self.controller_ready({'sha': 'd' * 40})[0])

    def test_reencoded_duplicate_pixels_cannot_evade_image_uniqueness(self):
        import io
        from PIL import Image
        buffer = io.BytesIO()
        with Image.open(io.BytesIO(self.image)) as image:
            image.save(buffer, format='PNG', compress_level=0)
        duplicate = buffer.getvalue()
        self.assertNotEqual(hashlib.sha256(duplicate).digest(), hashlib.sha256(self.image).digest())
        self.base[0]['image'] = '/images/generated/blog/old.png'
        errors = self.validate(loader=lambda entry: duplicate if 'raw_url' in entry else self.image)
        self.assertTrue(any('pixels' in error.lower() for error in errors), errors)
        used = {'pixels:' + self.worker.core.image_pixel_sha256(duplicate)}
        self.assertTrue(self.worker.core.candidate_is_duplicate(self.image, used))
        self.assertFalse(self.worker.core.candidate_is_duplicate(png(shade=0), used))

    def test_corrupt_or_header_only_images_are_rejected_even_with_matching_proof(self):
        # Keep the chunk checksum correct while breaking the compressed pixels:
        # a structural verifier alone would accept this image.
        corrupt_pixels = bytearray(self.image)
        idat = corrupt_pixels.index(b'IDAT')
        length = struct.unpack('>I', corrupt_pixels[idat - 4:idat])[0]
        corrupt_pixels[idat + 4] ^= 0xff
        corrupt_pixels[idat + 4 + length:idat + 8 + length] = struct.pack(
            '>I', zlib.crc32(corrupt_pixels[idat:idat + 4 + length]))
        images = {
            'header-only': b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 1200, 675) + b'fixture',
            'truncated-pixels': self.image[:len(self.image) // 2],
            'bad-crc': self.image[:-1] + bytes([self.image[-1] ^ 1]),
            'undecodable-pixels-valid-crc': bytes(corrupt_pixels),
        }
        for name, data in images.items():
            with self.subTest(image=name):
                self.image = data
                self.pr['body'] = self.proof('Local')
                self.assertFalse(self.worker_ready())
                self.assertFalse(self.controller_ready()[0])
                self.assertTrue(any('Image validation failed' in err for err in self.validate()))
                with self.assertRaisesRegex(RuntimeError, 'valid PNG/JPEG'):
                    self.worker.core.validate_candidate(data)

    def test_decoder_is_required_and_jpeg_pixels_are_accepted(self):
        from PIL import Image
        output = io.BytesIO()
        Image.new('RGB', (1200, 675), (96, 127, 150)).save(output, format='JPEG')
        self.image = output.getvalue()
        self.post['image'] = '/images/generated/blog/new-article.jpg'
        self.files[-1]['filename'] = 'public/images/generated/blog/new-article.jpg'
        self.pr['body'] = self.proof('Local')
        self.assertTrue(self.worker_ready())
        self.assertTrue(self.controller_ready()[0])
        self.assertEqual(self.validate(), [])
        with patch.dict(sys.modules, {'PIL': None}):
            with self.assertRaisesRegex(ValueError, 'decoder unavailable'):
                contract.image_dimensions(self.image)
        with self.assertRaises(ValueError):
            contract.image_dimensions(self.image[:-20])

    def test_valid_png_zero_padding_preserves_pixels_but_damaged_or_program_trailers_fail(self):
        self.assertEqual(contract.image_dimensions(self.image + b'\0'), (1200, 675))
        self.assertEqual(contract.image_pixel_sha256(self.image + b'\0'), contract.image_pixel_sha256(self.image))
        for data in (self.image + b'<script>run()</script>',
                     self.image[:-1] + bytes([self.image[-1] ^ 1]) + b'\0'):
            with self.subTest(trailer=data[-12:]), self.assertRaises(ValueError):
                contract.image_dimensions(data)

    def test_decoder_rejects_unsupported_formats_and_unsafe_settings(self):
        from PIL import Image, ImageFile
        output = io.BytesIO()
        Image.new('RGB', (1200, 675)).save(output, format='GIF')
        with self.assertRaises(ValueError):
            contract.image_dimensions(output.getvalue())
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 500_000):
            with self.assertRaises(ValueError):
                contract.image_dimensions(self.image)
        with patch.object(ImageFile, 'LOAD_TRUNCATED_IMAGES', True):
            with self.assertRaises(ValueError):
                contract.image_dimensions(self.image)

    def test_provider_chain_result_uri_and_duplicate_evidence_are_rejected(self):
        invalid = [
            {'Image Generation Result': 'stock'},
            {'Image Attempt Chain': 'gemini/local-editorial'},
            {'Image Source URL': 'local-editorial://other-article/0'},
            {'Image Source URL': 'https://example.com/not-an-editorial-source'},
            {'Image Article SHA-256': '0' * 64},
        ]
        for fields in invalid:
            with self.subTest(fields=fields):
                self.pr['body'] = self.proof(**fields)
                self.assertFalse(self.worker_ready())
                self.assertFalse(self.controller_ready()[0])
                self.assertTrue(self.validate())
        self.pr['body'] = self.proof('Local') + '\nImage SHA-256: ' + hashlib.sha256(self.image).hexdigest()
        self.assertFalse(self.worker_ready())
        self.assertFalse(self.controller_ready()[0])
        self.assertTrue(self.validate())

    def test_current_head_check_cannot_be_replaced_by_old_success(self):
        self.pr['body'] = self.proof('Local')
        self.files = [row for row in self.files if row['filename'] != 'public/rss.xml']
        errors = self.validate(checks=[{'name': 'verify', 'conclusion': 'success', 'head_sha': NEXT_HEAD}])
        self.assertTrue(any('current head' in err for err in errors), errors)

    def test_image_collision_and_missing_base_image_fail_closed(self):
        self.base[0]['image'] = '/images/generated/blog/old.png'
        self.assertTrue(any('collides' in err for err in self.validate()))
        def missing_old(entry):
            if 'filename' not in entry:
                raise FileNotFoundError('old.png')
            return self.image
        self.assertTrue(any('uniqueness' in err for err in self.validate(loader=missing_old)))

    def test_no_image_too_small_or_extra_image_are_rejected(self):
        self.pr['body'] = self.proof('Local')
        self.files.append({'filename': 'public/images/generated/blog/unreferenced.png'})
        self.assertTrue(any('exactly' in err for err in self.validate()))
        self.files.pop()
        self.image = png(320, 180)
        self.pr['body'] = self.proof('Local', **{'Image Dimensions': '320x180'})
        self.assertFalse(self.worker_ready())
        self.assertFalse(self.controller_ready()[0])
        self.assertTrue(any('small' in err for err in self.validate()))
        del self.post['image']
        self.assertTrue(any('no-image publication is forbidden' in err for err in self.validate()))

    def test_producer_emits_concrete_local_result_and_final_head_bound_proof(self):
        self.pr['body'] = ''
        head_posts = self.base + [self.post]
        candidate = self.worker.core.ImageCandidate('Local', self.image, 'png',
            'local://public/images/generated/blog/curated.png', VISUAL,
            ['gemini-1', 'gemini-2', 'gemini-3', 'pexels', 'pixabay', 'local-curated'])
        bodies = []
        with patch.object(self.worker.core, 'posts_at', side_effect=[self.base, head_posts]), \
             patch.object(self.worker.v3, 'choose_candidate', return_value=candidate), \
             patch.object(self.worker.core, 'patch_pr_body', side_effect=lambda _r, _n, body, _t: bodies.append(body)), \
             patch.object(self.worker.core, 'request_json', return_value=[]), \
             patch.object(self.worker.v3, 'commit_files', return_value=NEXT_HEAD):
            self.assertTrue(self.worker.ensure_image('test/repo', self.pr, 'unused'))
        self.assertIn('Image Generation Result: local_fallback', bodies[-1])
        self.assertIn('Image Article ID: new-article', bodies[-1])
        self.assertIn('Image Article SHA-256: ' + article_digest(head_posts[-1]), bodies[-1])
        self.post = head_posts[-1]
        self.assertIn('Image Evidence Head: ' + NEXT_HEAD, bodies[-1])
        self.pr['head']['sha'] = NEXT_HEAD
        self.pr['body'] = bodies[-1]
        self.assertTrue(self.worker_ready())

    def test_worker_refreshes_head_binding_without_regenerating_valid_pixels(self):
        self.pr['body'] = self.proof('Local')
        self.pr['head']['sha'] = NEXT_HEAD
        bodies = []
        payload = {'encoding': 'base64', 'content': base64.b64encode(self.image).decode()}
        with patch.object(self.worker.core, 'posts_at', side_effect=[self.base, self.base + [self.post]]), \
             patch.object(self.worker.core, 'github_content', return_value=payload), \
             patch.object(self.worker.v3, 'choose_candidate', side_effect=AssertionError('unnecessary regeneration')), \
             patch.object(self.worker.core, 'patch_pr_body', side_effect=lambda _r, _n, body, _t: bodies.append(body)):
            self.assertFalse(self.worker.ensure_image('test/repo', self.pr, 'unused'))
        self.assertEqual(len(bodies), 1)
        self.assertIn('Image Evidence Head: ' + NEXT_HEAD, bodies[0])
        self.pr['body'] = bodies[0]
        self.assertTrue(self.worker_ready())


if __name__ == '__main__':
    unittest.main()
