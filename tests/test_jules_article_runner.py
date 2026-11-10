from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner as runner
from scripts import jules_article_runner_v3 as runner_v3
from scripts.kesher_runtime import bridge_admission
from scripts.kesher_runtime.state import StateInvalid


class JulesArticleRunnerTests(unittest.TestCase):
    def test_current_policy_manifest_is_valid(self):
        policy = runner.load_policy()
        self.assertTrue(policy.startswith("# עדכון מחייב למדיניות מאמרי קשר"))
        meta = json.loads(runner.POLICY_META_PATH.read_text(encoding="utf-8"))
        self.assertEqual(meta["policy_version"], runner.ARTICLE_POLICY_VERSION)
        self.assertEqual(
            meta["git_blob_sha1"],
            runner.git_blob_sha1(runner.POLICY_PATH.read_bytes()),
        )

    def test_policy_loader_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.md"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(runner.ArticleRunnerError):
                runner.load_policy(path)

    def test_policy_loader_rejects_content_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            path.write_text("מדיניות תקינה", encoding="utf-8")
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION,
                        "git_blob_sha1": "0" * 40,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "content drift"):
                runner.load_policy(path, meta)

    def test_policy_loader_rejects_version_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            raw = "מדיניות תקינה".encode("utf-8")
            path.write_bytes(raw)
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION + 1,
                        "git_blob_sha1": runner.git_blob_sha1(raw),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "version mismatch"):
                runner.load_policy(path, meta)

    def test_prompt_injects_authoritative_policy_and_slot(self):
        marker = "UNIQUE_POLICY_MARKER_20260819"
        prompt = runner.build_prompt("2026-08-19", marker)
        self.assertIn(marker, prompt)
        self.assertIn("2026-08-19", prompt)
        self.assertIn("Article policy version: `1`", prompt)
        self.assertIn("BEGIN AUTHORITATIVE ARTICLE POLICY", prompt)
        self.assertIn("Article publication runs MUST NOT create a video", prompt)
        self.assertIn("Publish Kesher article:", prompt)
        self.assertIn("Never ask the user", prompt)

    def test_slot_duplicate_detection_is_exact(self):
        posts = [
            {"id": "a", "date": "2026-08-18"},
            {"id": "b", "date": "2026-08-19"},
        ]
        self.assertTrue(runner.article_exists_for_slot(posts, "2026-08-19"))
        self.assertFalse(runner.article_exists_for_slot(posts, "2026-08-20"))

    def test_runtime_prompt_is_short_task_wrapper_not_policy_duplication(self):
        policy = "POLICY_BODY_SENTINEL"
        prompt = runner.build_prompt("2026-08-19", policy)
        self.assertEqual(prompt.count(policy), 1)
        self.assertLess(len(prompt.replace(policy, "")), 2600)

    def test_create_session_uses_auto_create_pr_and_never_retries_post(self):
        with mock.patch.object(
            runner,
            "request_json",
            return_value={"name": "sessions/123", "url": "https://jules.google/session/123"},
        ) as request:
            session, url = runner.create_session("key", "prompt", "2026-08-19")

        self.assertEqual(session, "sessions/123")
        self.assertEqual(url, "https://jules.google/session/123")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], f"{runner.API_BASE}/sessions")
        self.assertEqual(args[3]["automationMode"], "AUTO_CREATE_PR")
        self.assertFalse(args[3]["requirePlanApproval"])
        self.assertEqual(kwargs["max_attempts"], 1)

    def test_existing_active_slot_session_is_reused_without_create(self):
        listed = {
            "sessions": [{
                "name": "sessions/oldest",
                "title": "Kesher article 2026-08-19",
                "state": "IN_PROGRESS",
                "createTime": "2026-08-19T04:00:00Z",
            }]
        }
        with mock.patch.object(runner, "request_json", return_value=listed) as request, mock.patch.object(
            runner, "create_session"
        ) as create:
            session = runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(session[0], "sessions/oldest")
        create.assert_not_called()
        self.assertEqual(request.call_args.args[0], "GET")

    def test_session_inventory_follows_all_documented_pages(self):
        first = {
            "sessions": [{
                "name": "sessions/unrelated",
                "title": "Kesher article 2026-08-18",
                "state": "IN_PROGRESS",
                "createTime": "2026-08-18T04:00:00Z",
            }],
            "nextPageToken": "page two/with spaces",
        }
        second = {
            "sessions": [{
                "name": "sessions/current",
                "title": "Kesher article 2026-08-19",
                "state": "PLANNING",
                "createTime": "2026-08-19T04:00:00Z",
            }]
        }
        with mock.patch.object(runner, "request_json", side_effect=[first, second]) as request:
            active = runner.list_active_slot_sessions("key", "2026-08-19")

        self.assertEqual([row["name"] for row in active], ["sessions/current"])
        self.assertEqual(request.call_count, 2)
        self.assertIn("pageToken=page+two%2Fwith+spaces", request.call_args_list[1].args[1])

    def test_repeated_session_page_token_fails_closed(self):
        repeated = {"sessions": [], "nextPageToken": "same"}
        with mock.patch.object(runner, "request_json", side_effect=[repeated, repeated]):
            with self.assertRaisesRegex(runner.ArticleRunnerError, "repeated a page token") as ctx:
                runner.list_active_slot_sessions("key", "2026-08-19")
        self.assertEqual(ctx.exception.code, "JULES_SESSION_LIST_ERROR")

    def test_duplicate_active_slot_sessions_fail_closed_without_delete(self):
        listed = {
            "sessions": [
                {
                    "name": "sessions/newer",
                    "title": "Kesher article 2026-08-19",
                    "state": "PLANNING",
                    "createTime": "2026-08-19T04:01:00Z",
                },
                {
                    "name": "sessions/oldest",
                    "title": "Kesher article 2026-08-19",
                    "state": "IN_PROGRESS",
                    "createTime": "2026-08-19T04:00:00Z",
                },
            ]
        }
        with mock.patch.object(runner, "request_json", return_value=listed) as request:
            with self.assertRaisesRegex(runner.ArticleRunnerError, "multiple active Jules sessions") as ctx:
                runner.recover_active_slot_session("key", "2026-08-19")

        self.assertEqual(ctx.exception.code, "JULES_DUPLICATE_SESSIONS")
        self.assertTrue(runner.retryable_code(ctx.exception.code))
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], "GET")

    def test_uncertain_create_response_recovers_same_session_before_retry(self):
        network = runner.ArticleRunnerError("JULES_NETWORK_ERROR", "response lost")
        with mock.patch.object(
            runner,
            "recover_active_slot_session",
            side_effect=[None, ("sessions/recovered", "")],
        ) as recover, mock.patch.object(
            runner, "create_session", side_effect=network
        ) as create:
            session = runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(session[0], "sessions/recovered")
        self.assertEqual(recover.call_count, 2)
        create.assert_called_once()

    def test_uncertain_create_without_recovery_is_retryable_but_safe(self):
        network = runner.ArticleRunnerError("JULES_NETWORK_ERROR", "response lost")
        with mock.patch.object(
            runner,
            "recover_active_slot_session",
            return_value=None,
        ), mock.patch.object(
            runner, "create_session", side_effect=network
        ), mock.patch.object(
            runner.time, "sleep"
        ):
            with self.assertRaisesRegex(runner.ArticleRunnerError, "create response was uncertain") as ctx:
                runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(ctx.exception.code, "JULES_CREATE_UNCERTAIN")
        self.assertTrue(runner.retryable_code(ctx.exception.code))

    def test_timeout_preserves_session_for_same_session_recovery_without_delete(self):
        with mock.patch.object(runner.time, "monotonic", side_effect=[0.0, 2.0]), mock.patch.object(
            runner, "request_json"
        ) as request:
            outcome, _, message = runner.poll("key", "sessions/123", timeout_seconds=1)

        self.assertEqual(outcome, "JULES_TIMEOUT_SESSION_ACTIVE")
        self.assertIn("left active", message)
        self.assertTrue(runner.retryable_code(outcome))
        request.assert_not_called()


    def test_prior_day_pr_does_not_block_when_contents_api_omits_inline_content(self):
        prior_posts = [
            {
                "id": "relationship-code-7500",
                "date": "2026-10-03",
                "title": "קוד 7500 בזוגיות",
                "content": "<p>תוכן</p>",
            }
        ]
        encoded = base64.b64encode(
            (json.dumps(prior_posts, ensure_ascii=False) + "\n").encode("utf-8")
        ).decode("ascii")

        def fake_request(method, url, headers, body=None, **kwargs):
            if url.endswith("/pulls?state=open&per_page=100"):
                return [
                    {
                        "number": 997,
                        "title": "Publish Kesher article: קוד 7500 בזוגיות",
                        "head": {"sha": "head997"},
                    }
                ]
            if url.endswith("/pulls/997/files?per_page=100"):
                return [
                    {
                        "filename": "src/data/posts.json",
                        "sha": "postsblob997",
                    }
                ]
            if "/contents/src/data/posts.json?ref=" in url:
                return {
                    "name": "posts.json",
                    "sha": "postsblob997",
                    "encoding": "none",
                    "content": "",
                }
            if url.endswith("/git/blobs/postsblob997"):
                return {
                    "sha": "postsblob997",
                    "encoding": "base64",
                    "content": encoded,
                }
            raise AssertionError(f"unexpected request: {method} {url}")

        with mock.patch.object(runner_v3.core, "request_json", side_effect=fake_request):
            matches = runner_v3.open_article_prs_for_slot("token", "2026-10-04")

        self.assertEqual(matches, [])


class ManualArticleBridgeTests(unittest.TestCase):
    paths = (
        'kesher-article-generation.yml',
        'normalize-article-pr.yml',
        'kesher-article-image.yml',
        'auto-merge-article-prs.yml',
    )

    def invocation(self, name):
        return {'GITHUB_REPOSITORY': runner.REPO, 'GITHUB_REF': 'refs/heads/main',
                'GITHUB_EVENT_NAME': 'workflow_dispatch',
                'GITHUB_WORKFLOW_REF': runner.REPO + '/.github/workflows/' + name + '@refs/heads/main'}

    def test_exact_manual_article_bridges_are_admitted_only_before_cutover(self):
        for name in self.paths:
            with self.subTest(workflow=name):
                bridge_admission.require_invocation(self.invocation(name))
                bridge_admission.require_bridge({'schema_version': 5})

    def test_schema_and_exclusion_markers_refuse_even_when_empty(self):
        for state in ({'schema_version': 6}, {'schema_version': 4}, {'schema_version': '5'},
                      {'schema_version': 5.0}, {}, {'schema_version': 5, 'handover': None},
                      {'schema_version': 5, 'handover': {}},
                      {'schema_version': 5, 'github_exclusion': None},
                      {'schema_version': 5, 'github_exclusion': {}}):
            with self.subTest(state=state), self.assertRaises(StateInvalid):
                bridge_admission.require_bridge(state)

    def test_exact_invocation_refuses_wrong_repository_branch_event_or_path(self):
        for name in self.paths:
            env = self.invocation(name)
            for change in ({'GITHUB_REPOSITORY': 'other/repo'}, {'GITHUB_REF': 'refs/heads/repair'},
                           {'GITHUB_REF': 'refs/tags/main'}, {'GITHUB_EVENT_NAME': 'push'},
                           {'GITHUB_EVENT_NAME': 'schedule'},
                           {'GITHUB_WORKFLOW_REF': runner.REPO + '/.github/workflows/kesher-master-supervisor.yml@refs/heads/main'},
                           {'GITHUB_WORKFLOW_REF': env['GITHUB_WORKFLOW_REF'].replace('@refs/heads/main', '@refs/heads/repair')}):
                with self.subTest(workflow=name, change=change), self.assertRaises(StateInvalid):
                    bridge_admission.require_invocation(env | change)
            with self.assertRaises(StateInvalid):
                bridge_admission.require_invocation(env, dispatcher=True)

    def test_unwritable_legacy_state_is_not_admitted(self):
        with mock.patch('scripts.kesher_runtime.handover.require_legacy_writable',
                        side_effect=StateInvalid('LEGACY_AUTHORITY_FENCED')) as writable:
            with self.assertRaises(StateInvalid):
                bridge_admission.require_bridge({'schema_version': 5})
            writable.assert_called_once()

    def test_invalid_invocation_never_reads_state_and_valid_invocation_only_reads(self):
        for name in self.paths:
            with mock.patch.dict(os.environ, self.invocation(name) | {'GITHUB_REF': 'refs/heads/other'}, clear=True), \
                 mock.patch.object(bridge_admission, 'GitHub') as client:
                self.assertEqual(bridge_admission.main([]), 1)
                client.assert_not_called()
            with mock.patch.dict(os.environ, self.invocation(name), clear=True), \
                 mock.patch.object(bridge_admission, 'GitHub'), \
                 mock.patch.object(bridge_admission, 'GitHubHandover') as handover:
                handover.return_value.read_snapshot.return_value.state = {'schema_version': 5}
                self.assertEqual(bridge_admission.main([]), 0)
                self.assertEqual(handover.return_value.method_calls,
                                 [mock.call.read_snapshot()])

    def test_workflows_are_manual_main_only_with_admission_before_credentials(self):
        import yaml
        bound = "${{ github.event_name == 'workflow_dispatch' && github.repository == 'yanivsa/kesher-website' && github.ref == 'refs/heads/main' }}"
        for name in self.paths:
            text = (Path('.github/workflows') / name).read_text()
            workflow = yaml.safe_load(text)
            self.assertEqual(set(workflow.get('on', workflow.get(True))), {'workflow_dispatch'})
            self.assertIn('bounded manual emergency bridge', text.lower())
            for job in workflow['jobs'].values():
                self.assertEqual(job['if'], bound)
                self.assertFalse(any('secrets.' in str(value) for value in job.get('env', {}).values()))
                steps = job['steps']
                gates = [index for index, step in enumerate(steps)
                         if 'scripts.kesher_runtime.bridge_admission' in step.get('run', '')]
                self.assertEqual(len(gates), 1)
                gate = gates[0]
                self.assertFalse(steps[gate].get('continue-on-error', False))
                for index, step in enumerate(steps):
                    if any('secrets.' in str(value) for value in step.get('env', {}).values()):
                        self.assertGreater(index, gate)
                    if 'always()' in str(step.get('if', '')):
                        self.assertIn("steps.bridge_admission.outcome == 'success'", step['if'])

    def test_only_exact_article_components_join_emergency_roles(self):
        from scripts.kesher_runtime.authority_topology import check_definitions, policy
        root = Path(__file__).resolve().parents[1]
        rules = policy(root)
        definitions = {str(p.relative_to(root)): p.read_text()
                       for p in (root / '.github/workflows').glob('*.yml')}
        rows = {row['path']: row for row in check_definitions(definitions, rules)}
        for name in self.paths:
            self.assertEqual(rows['.github/workflows/' + name]['role'], 'emergency_bridge')
        for name in ('kesher-master-supervisor.yml', 'kesher-backlog-media-recovery.yml'):
            self.assertTrue(rows['.github/workflows/' + name]['definition_retired'])
        self.assertEqual(sum(row['role'] == 'controller' for row in rows.values()), 1)

    def test_recent_main_article_blocks_generation_before_pr_lookup(self):
        recent = json.loads(Path('src/data/postsRecent.json').read_text())
        self.assertTrue(recent)
        with mock.patch.dict(os.environ, {'KESHER_TEST_MODE': 'false'}), \
             mock.patch.object(runner_v3, 'open_article_prs_for_slot') as lookup:
            self.assertEqual(runner_v3.preflight(recent[0]['date'], 'token'), 'ARTICLE_ALREADY_PUBLISHED')
            lookup.assert_not_called()

    def test_missing_recent_catalog_fails_before_any_pr_or_provider_request(self):
        original = Path.read_text
        def read(path, *args, **kwargs):
            if path.name == 'postsRecent.json':
                raise FileNotFoundError('missing reviewed publication catalog')
            return original(path, *args, **kwargs)
        with mock.patch.dict(os.environ, {'KESHER_TEST_MODE': 'false'}), \
             mock.patch.object(Path, 'read_text', read), \
             mock.patch.object(runner_v3, 'open_article_prs_for_slot') as lookup:
            with self.assertRaises(runner.ArticleRunnerError):
                runner_v3.preflight('2026-10-11', 'token')
            lookup.assert_not_called()

    def test_invalid_recent_catalog_and_duplicate_identity_fail_closed(self):
        historical = json.loads(Path('src/data/posts.json').read_text())
        original = Path.read_text
        for recent in ({'not': 'a list'}, [historical[0]], [{'date': '2026-10-11'}]):
            def read(path, *args, **kwargs):
                if path.name == 'postsRecent.json':
                    return json.dumps(recent)
                return original(path, *args, **kwargs)
            with self.subTest(recent=recent), \
                 mock.patch.object(Path, 'read_text', read), \
                 self.assertRaises(runner.ArticleRunnerError):
                runner_v3._load_local_posts()


if __name__ == "__main__":
    unittest.main()
