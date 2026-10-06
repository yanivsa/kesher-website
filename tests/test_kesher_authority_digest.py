import io
import base64
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.kesher_runtime.authority_topology import authority_path, code_manifest, executable_digest
from scripts.kesher_runtime.state import StateInvalid


class AuthorityDigestBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.put('scripts/controller.py', b'print("trusted")\n')

    def put(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def raster(self, color):
        from PIL import Image
        output = io.BytesIO()
        Image.new('RGB', (12, 8), color).save(output, format='PNG')
        return output.getvalue()

    def test_contract_generated_outputs_can_change_without_authority_change(self):
        outputs = {
            'src/data/posts.json': b'[{"id":"one","title":"first"}]',
            'src/data/postSummaries.json': b'[{"id":"one","title":"first"}]',
            'public/sitemap.xml': b'<urlset><url><loc>https://example.test/one</loc></url></urlset>',
            'public/rss.xml': b'<rss version="2.0"><channel><title>first</title></channel></rss>',
            'public/llms.txt': b'# first\n',
            'public/llms-full.txt': b'# first\n',
            'public/images/generated/blog/one.png': self.raster('red'),
        }
        for name, raw in outputs.items(): self.put(name, raw)
        before = executable_digest(self.root)
        for name, raw in outputs.items():
            self.put(name, self.raster('blue') if name.endswith('.png') else raw.replace(b'first', b'second').replace(b'/one', b'/two'))
        self.assertEqual(executable_digest(self.root), before)

    def test_all_execution_inputs_and_unknown_paths_remain_pinned(self):
        for name in ('scripts/controller.py', 'tests/test_guard.py', 'evaluators/guard.py',
                     '.github/workflows/writer.yml', 'package.json', 'package-lock.json',
                     'requirements.txt', 'uv.lock', 'security/guard.py',
                     'public/images/generated/blog/hidden.js', 'public/unknown.txt',
                     'public/images/unreviewed.png'):
            with self.subTest(name=name):
                self.assertTrue(authority_path(name))
                self.put(name, b'old\n')
                before = executable_digest(self.root)
                self.put(name, b'new\n')
                self.assertNotEqual(executable_digest(self.root), before)

    def test_publication_alias_symlink_is_rejected(self):
        path = self.root/'src/data/posts.json'
        path.parent.mkdir(parents=True)
        path.symlink_to(self.root/'scripts/controller.py')
        with self.assertRaises(StateInvalid): code_manifest(self.root)

    def test_executable_publication_data_is_rejected(self):
        path = self.put('src/data/posts.json', b'[]')
        path.chmod(0o755)
        with self.assertRaises(StateInvalid): code_manifest(self.root)

    def test_raster_extension_cannot_hide_program_or_truncated_image(self):
        for raw in (b'#!/bin/sh\ncurl example.test\n', self.raster('red')[:25]):
            with self.subTest(raw=raw[:12]):
                self.put('public/images/generated/blog/one.png', raw)
                with self.assertRaises(StateInvalid): code_manifest(self.root)

    def test_publication_json_must_be_data(self):
        for raw in (b'#!/usr/bin/env python\n', b'{"run":"python script.py"}', b'[NaN]'):
            with self.subTest(raw=raw):
                self.put('src/data/posts.json', raw)
                with self.assertRaises(StateInvalid): code_manifest(self.root)

    def test_malformed_publication_xml_is_an_authority_refusal(self):
        self.put('public/rss.xml',b'<rss><channel>')
        result=None
        try:code_manifest(self.root)
        except StateInvalid as exc:result=str(exc)
        except Exception:result='unclassified parser error'
        self.assertEqual(result,'AUTHORITY_INVALID_PUBLICATION_OUTPUT')

    def test_noncontract_images_are_not_exempt(self):
        self.assertTrue(authority_path('public/images/unknown.png'))
        self.assertTrue(authority_path('public/images/generated/blog/asset.svg'))
        self.assertTrue(authority_path('public/images/generated/blog/asset.py'))

    def observer(self, *, mode='100644', raw=b'[]', blob_sha=None):
        from scripts.kesher_runtime.authority_topology import GitHubAuthorityObserver
        from unittest.mock import Mock
        text = 'name: controller\non: workflow_dispatch\njobs:\n  control:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m scripts.kesher_runtime.controller_entry --mode live\n'
        name='.github/workflows/controller.yml'
        rules={'version':2,'protected_resources':['github.refs'],'registrations':{},'workflows':{name:{
            'role':'controller','definition_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'capabilities':['read','workflow_dispatch'],'resources':['github.refs'],
            'review':{'call_chain':{},'dispatches':[],'credentials':[], 'credential_services':{},
                      'note':'Exact fake controller review'}}}}
        self.put(name,text.encode())
        from scripts.kesher_runtime.control_planes import ACTOR_POLICY
        rules['control_plane_actors'] = copy.deepcopy(ACTOR_POLICY)
        self.put('scripts/kesher_runtime/authority_policy.json',json.dumps(rules).encode())
        tree=[{'path':p,'sha':sha,'type':'blob','mode':'100644'} for p,sha in code_manifest(self.root).items()]
        actual_sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        tree.append({'path':'src/data/posts.json','sha':blob_sha or actual_sha,'type':'blob','mode':mode})
        def request(method,path):
            self.assertEqual(method,'GET')
            if '/git/ref/heads/main' in path:return {'object':{'sha':'a'*40}}
            if '/git/trees/' in path:return {'sha':'b'*40,'truncated':False,'tree':copy.deepcopy(tree)}
            if '/git/blobs/' in path:return {'sha':actual_sha,'encoding':'base64','content':base64.b64encode(raw).decode()}
            if '/actions/workflows?' in path:return {'total_count':1,'workflows':[{'id':1,'path':name,'state':'active'}]}
            return {'total_count':0,'workflow_runs':[]}
        github=Mock();github.request.side_effect=request
        from tests.test_kesher_external_exclusion import protection_fixture
        real_fence,_=protection_fixture();real_fence.establish();external=real_fence.authority_observation()
        fence=Mock(spec=['assert_exclusive','observe']);fence.assert_exclusive.return_value=external
        fence.observe.return_value={'external':external,'key_binding':{},'approved_revision':{}}
        return GitHubAuthorityObserver(github,'owner/repo',self.root,fence=fence)

    def test_remote_changed_publication_bytes_are_validated_before_exemption(self):
        with self.assertRaises(StateInvalid): self.observer(raw=b'#!/usr/bin/env python\n')()

    def test_remote_publication_tree_modes_cannot_hide_executables_or_symlinks(self):
        for mode in ('100755','120000'):
            with self.subTest(mode=mode):
                with self.assertRaises(StateInvalid): self.observer(mode=mode)()

    def test_remote_publication_blob_must_match_immutable_tree_identity(self):
        with self.assertRaises(StateInvalid): self.observer(blob_sha='c'*40)()

    def test_regular_valid_remote_publication_can_advance_with_pinned_code(self):
        observation=self.observer(raw=b'[{"id":"new"}]')()
        self.assertEqual(observation['code_sha256'],executable_digest(self.root))

    def test_assertion_without_service_resource_proof_cannot_authorize_observer(self):
        observer=self.observer()
        observer.fence.assert_exclusive.return_value=None
        with self.assertRaises(StateInvalid): observer()

    def inert_links(self):
        targets={'.venv-dub/bin/python':'python3',
                 '.venv-dub/bin/python3':'/Library/Developer/CommandLineTools/usr/bin/python3',
                 '.venv-dub/bin/python3.9':'python3'}
        entries={}
        for name,target in targets.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to(target)
            raw=target.encode()
            entries[name]={'mode':'120000','link_target':target,
                'blob_sha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                'execution_reachable':False,
                'usage_review':{'reference_count':0,'reviewed_scopes':['.github/','scripts/','src/','tests/','package.json'],
                                'note':'Reviewed historical inert environment links; link targets are never followed.'}}
        self.put('scripts/kesher_runtime/authority_policy.json',json.dumps({'inert_git_links':entries}).encode())
        subprocess.run(['git','add','.venv-dub'],cwd=self.root,check=True)
        return entries

    def test_exact_reviewed_tracked_inert_links_are_pinned_without_dereference(self):
        entries=self.inert_links()
        result=code_manifest(self.root)
        for name,entry in entries.items():self.assertEqual(result[name],entry['blob_sha1'])

    def test_changed_reviewed_link_target_refuses_authority(self):
        self.inert_links();path=self.root/'.venv-dub/bin/python3'
        path.unlink();path.symlink_to('/unreviewed/python3')
        with self.assertRaises(StateInvalid):code_manifest(self.root)

    def test_inert_link_allowlist_does_not_cover_unknown_or_publication_links(self):
        self.inert_links()
        for name in ('scripts/unreviewed.py','src/data/posts.json'):
            with self.subTest(name=name):
                path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to('python3')
                with self.assertRaises(StateInvalid):code_manifest(self.root)
                path.unlink()

    def test_reviewed_storage_link_cannot_become_an_active_call_chain_input(self):
        from scripts.kesher_runtime.authority_topology import _regular
        self.inert_links()
        with self.assertRaises(StateInvalid):_regular(self.root,'.venv-dub/bin/python')


if __name__ == '__main__': unittest.main()
