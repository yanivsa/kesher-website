import base64
import copy
import json
import unittest
from unittest.mock import Mock

from scripts.kesher_runtime.observe import RepositoryObserver
from scripts.kesher_runtime.identity import SourceIdentity
from scripts.kesher_runtime.state import StateConflict, bind_source, new_state
from tests.test_kesher_canonical_state import CODE
from tests.test_kesher_media_publication import NOW

POST = {'id': 'today', 'date': '2026-09-22', 'title': 'כותרת', 'category': 'משפחה',
        'excerpt': 'תקציר בעברית', 'content': '<p>גוף מאמר בעברית</p>',
        'image': '/images/generated/blog/today.png', 'imageAlt': 'תיאור תמונה מפורט בעברית לצורך הבדיקה'}


class Reads:
    def __init__(self, posts): self.posts, self.calls, self.heads = posts, [], [CODE, CODE]
    def request(self, method, path, *args, **kwargs):
        self.calls.append((method, path))
        if path.endswith('/git/ref/heads/main'): return {'object': {'sha': self.heads.pop(0)}}
        if '/contents/src/data/posts.json?' in path:
            return {'encoding': 'base64', 'content': base64.b64encode(json.dumps(self.posts).encode()).decode()}
        if '/pulls?' in path: return []
        if '/deploy.yml/runs?' in path: return {'workflow_runs': []}
        raise AssertionError(path)


class RepositoryObservationTests(unittest.TestCase):
    def observer(self, github, **kw):
        return RepositoryObserver(github, 'owner/repo', inventory_reader=Mock(return_value=None),
                                  auditor=Mock(side_effect=AssertionError('No media exists')), clock=lambda: NOW, **kw)

    def test_read_only_snapshot_binds_revision_main_slot_and_incomplete_media(self):
        gh = Reads([POST])
        article = Mock(return_value={'status': 'verified', 'evidence': {'verified_at': NOW}})
        result = self.observer(gh, article_observer=article).read(new_state()).value
        self.assertEqual(result['state_revision'], 0)
        self.assertEqual(result['main_sha'], CODE)
        self.assertEqual(result['current_slot'], POST['date'])
        self.assertTrue(result['article_creation_allowed'])
        self.assertEqual(result['publications'][0]['media']['short']['status'], 'unknown')
        self.assertTrue(all(method == 'GET' for method, _ in gh.calls))
        article.assert_called_once()

    def test_old_untracked_posts_do_not_create_unrequested_historical_provider_work(self):
        old = {**POST, 'id': 'old', 'date': '2025-01-01'}
        result = self.observer(Reads([POST, old]), article_observer=Mock(return_value={'status': 'pending'})).read(new_state()).value
        self.assertEqual(len(result['publications']), 1)
        self.assertEqual(result['publications'][0]['source']['slug'], 'today')

    def test_adopted_backlog_is_reobserved_at_its_current_authoritative_hash(self):
        old = {**POST, 'id': 'old', 'date': '2026-09-21'}
        state = bind_source(new_state(), SourceIdentity(old['date'], old['id'], '0'*64), now=NOW)
        result = self.observer(Reads([POST, old]), article_observer=Mock(return_value={'status': 'pending'})).read(state).value
        actual = [row['source'] for row in result['publications'] if row['source']['slot'] == old['date']][0]
        self.assertNotEqual(actual['content_sha256'], '0'*64)

    def test_main_changed_during_remote_reads_discards_whole_snapshot(self):
        gh = Reads([POST]); gh.heads = [CODE, 'f'*40]
        with self.assertRaises(StateConflict):
            self.observer(gh, article_observer=Mock(return_value={'status': 'pending'})).read(new_state())

    def test_pr_read_failure_cannot_be_reinterpreted_as_no_existing_pr(self):
        gh = Reads([]); original = gh.request
        def failing(method, path, *args, **kw):
            if '/pulls?' in path: raise OSError('API unavailable')
            return original(method, path, *args, **kw)
        gh.request = failing
        with self.assertRaises(OSError): self.observer(gh).read(new_state())

    def test_unrelated_code_pr_cannot_enter_article_normalization_by_touching_posts(self):
        gh = Reads([])
        def get(method, path, *args, **kw):
            if '/pulls?' in path:
                return [{'number': 99, 'title': 'Refactor unrelated code', 'head': {'sha': 'b'*40}}]
            if '/files?' in path:
                return [{'filename': 'src/data/posts.json'}]
            raise AssertionError('Unrelated PR article contents must not be interpreted')
        gh.request = get
        self.assertEqual(self.observer(gh).article_prs([], POST['date']), [])

    def test_forged_image_body_and_green_named_checks_cannot_replace_trusted_image_receipt(self):
        import hashlib
        from scripts.kesher_article_contract import article_sha256, replace_image_evidence
        from tests.test_kesher_article_image_worker import candidate
        data = candidate()['data']; head = 'b'*40
        proof = {'Image Pipeline Version': '2', 'Image Provider': 'Gemini', 'Image Attempt Chain': 'gemini',
                 'Image Generation Result': 'generated', 'Image Source URL': 'https://example.org/image',
                 'Image SHA-256': hashlib.sha256(data).hexdigest(), 'Image Dimensions': '640x360',
                 'Image Visual Match': 'שני אנשים בשיחה רגועה בסלון בית מואר באור טבעי',
                 'Image Article ID': POST['id'], 'Image Article SHA-256': article_sha256(POST), 'Image Evidence Head': head}
        pr = {'number': 42, 'title': 'Publish Kesher article: test', 'body': replace_image_evidence('', proof),
              'base': {'ref': 'main'}, 'head': {'sha': head, 'repo': {'full_name': 'owner/repo'}}}
        gh = Reads([])
        def get(method, path, *args, **kw):
            if '/pulls?' in path: return [pr]
            if '/files?' in path: return [{'filename': 'src/data/posts.json'}]
            if '/contents/' in path:
                content = json.dumps([POST]).encode() if 'posts.json' in path else data
                return {'encoding': 'base64', 'content': base64.b64encode(content).decode()}
            if '/check-runs?' in path:
                return {'check_runs': [{'name': name, 'app': {'slug': 'github-actions'}, 'status': 'completed', 'conclusion': 'success'}
                                       for name in ['verify', 'validate', 'render-proof']]}
            raise AssertionError(path)
        gh.request = get
        self.assertEqual(self.observer(gh).article_prs([], POST['date'])[0]['status'], 'image_required')


if __name__ == '__main__': unittest.main()
