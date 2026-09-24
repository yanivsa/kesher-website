"""Assemble an independent, read-only, revision-bound production observation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scripts.kesher_article_contract import image_proof_errors
from scripts.kesher_article_normalizer import normalization_required
from scripts.kesher_daily_pipeline import source_metadata
from .article_verification import ArticlePublicVerifier, ArticleVerificationError, GitHubArticleReader, SourceSnapshot
from .controller import Observation
from .github import GitHubError
from .identity import MediaIdentity, SlotIdentity, SourceIdentity, digest, require_sha
from .media_observer import observe_media
from .media_publication import MediaVerificationError
from .outbox import workflow_for
from .state import StateConflict, StateInvalid, validate_state


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def article_window(now: str) -> bool:
    # Preserve the proven Israel/Friday/Saturday policy during cutover. These
    # are pure scheduling/read functions, never the legacy controller runtime.
    from scripts.kesher_content_controller import article_window_open, fetch_ashdod_sunset
    local = datetime.fromisoformat(now).astimezone(ZoneInfo('Asia/Jerusalem'))
    sunset = fetch_ashdod_sunset(local.date()) if local.isoweekday() == 6 else None
    return article_window_open(local, sunset)


class RepositoryObserver:
    def __init__(self, github, repo: str, *, inventory_reader, auditor, article_observer=None,
                 clock=utc_now, window=article_window):
        self.github, self.repo = github, repo
        self.reader = GitHubArticleReader(github, repo)
        self.inventory_reader, self.auditor = inventory_reader, auditor
        self.article_observer = article_observer or self._article
        self.clock, self.window = clock, window
        self._content = {}

    def content(self, sha: str, path: str) -> bytes:
        key = (sha, path)
        if key not in self._content:
            self._content[key] = self.reader.content(sha, path)
        return self._content[key]

    def pages(self, path: str, field: str | None = None) -> list:
        rows = []
        for page in range(1, 101):
            response = self.github.request('GET', f'/repos/{self.repo}/{path}&per_page=100&page={page}')
            batch = response[field] if field else response
            if not isinstance(batch, list):
                raise StateInvalid('Incomplete GitHub collection')
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise StateInvalid('GitHub inventory exceeded bounded pagination')

    def _article(self, source: SourceIdentity, post: dict, main: str, now: str) -> dict:
        try:
            snapshot = SourceSnapshot(main, main, post, self.content(main, 'public' + post['image']))
            verifier = ArticlePublicVerifier(lambda sha, slug: snapshot, lambda sha: self._deployment)
            evidence = verifier.verify(source, main, verified_at=now)
            return {'status': 'verified', 'evidence': evidence}
        except ArticleVerificationError as exc:
            code = exc.failure_class
            if code == 'ARTICLE_PUBLIC_TRANSIENT':
                return {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}
            if code == 'ARTICLE_DEPLOY_UNVERIFIED':
                return {'status': 'pending', 'failure_class': 'ARTICLE_NOT_PUBLIC'}
            # A redeploy can repair the public route/build/content, but never
            # bless invalid source or hero policy. Those require code/content repair.
            repairable = {'ARTICLE_PUBLIC_HTTP', 'ARTICLE_PUBLIC_ROUTE', 'ARTICLE_MANIFEST_MISMATCH', 'ARTICLE_CONTENT_MISMATCH'}
            return {'status': 'failed', 'failure_class': 'ARTICLE_NOT_PUBLIC' if code in repairable else code}
        except (GitHubError, OSError):
            return {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}

    def article_prs(self, posts: list[dict], current_slot: str, state: dict | None = None,
                    main_sha: str | None = None) -> list[dict]:
        from .article_image_worker import image_receipt_matches
        from .article_validation import validation_for_pr
        result = []
        base_ids = {post['id'] for post in posts}
        for pr in self.pages('pulls?state=open'):
            if not str(pr.get('title') or '').startswith('Publish Kesher article:'):
                continue
            # Scope from changed files before reading any article or image from
            # unrelated code PRs (#843); errors never mean an absent article PR.
            paths = [row['filename'] for row in self.pages(f'pulls/{pr["number"]}/files?')]
            if 'src/data/posts.json' not in paths:
                continue
            head = pr['head']['sha']; require_sha(head, 40)
            head_posts = json.loads(self.content(head, 'src/data/posts.json'))
            candidates = [post for post in head_posts if post.get('id') not in base_ids]
            for post in candidates:
                slot = SlotIdentity(post['date']).slot
                if slot > current_slot:
                    continue
                row = {'number': pr['number'], 'head_sha': head, 'body_sha256': digest(pr.get('body') or ''),
                       'slot': slot, 'status': 'ci_pending'}
                result.append(row)
                if (pr.get('base', {}).get('ref') != 'main' or (pr.get('head', {}).get('repo') or {}).get('full_name') != self.repo
                        or sum(candidate.get('date') == slot for candidate in candidates) != 1):
                    row['status'] = 'ci_failed'; continue
                if normalization_required(posts, head_posts, slot, paths):
                    row['status'] = 'normalize_required'; continue
                image = str(post.get('image') or '')
                data = None
                if image.startswith('/images/generated/blog/') and '..' not in image.split('/'):
                    try:
                        data = self.content(head, 'public' + image)
                    except GitHubError as exc:
                        if exc.status != 404:
                            raise
                if data is None or image_proof_errors(post, pr.get('body') or '', head, data):
                    row['status'] = 'image_required'; continue
                if not image_receipt_matches(state, slot, pr['number'], head, post, data, pr.get('body') or ''):
                    row['status'] = 'image_required'; continue
                if not image_receipt_matches(state, slot, pr['number'], head, post, data, pr.get('body') or '', base_sha=main_sha):
                    row['status'] = 'normalize_required'; continue
                if pr.get('draft'):
                    row['status'] = 'ci_failed'; continue
                validation = validation_for_pr(state, self.github, self.repo, slot, pr, main_sha)
                row['status'] = {'verified': 'ready_to_merge', 'absent': 'ci_required',
                                 'pending': 'ci_pending', 'failed': 'ci_failed', 'unknown': 'ci_unknown'}[validation['status']]
                if validation['status'] == 'failed' and validation.get('failure_class') == 'TRANSIENT_API':
                    row['status'] = 'ci_required'
                if validation.get('evidence'):
                    row['validation'] = validation['evidence']
        return result

    def runs(self, state: dict) -> list[dict]:
        result = []
        for command in state['commands'].values():
            if command['outcome'] != 'pending' or not command['owner']:
                continue
            run_id, attempt = command['owner']['run_id'].split('/')
            row = self.github.request('GET', f'/repos/{self.repo}/actions/runs/{run_id}/attempts/{attempt}')
            if (str(row.get('id')) != run_id or str(row.get('run_attempt')) != attempt
                    or row.get('head_sha') != command['code_sha'] or row.get('head_branch') != 'main'
                    or row.get('event') != 'workflow_dispatch'
                    or row.get('display_title') != 'kesher-command:' + command['id']
                    or row.get('path', '').split('@')[0] != '.github/workflows/' + workflow_for(command)):
                raise StateInvalid('Exact worker observation has wrong run/attempt/workflow/code identity')
            result.append({'command_id': command['id'], 'run_id': command['owner']['run_id'],
                           'code_sha': command['code_sha'], 'status': row['status'], 'conclusion': row['conclusion']})
        return result

    def read(self, state: dict) -> Observation:
        validate_state(state)
        now = self.clock()
        current_slot = datetime.fromisoformat(now).astimezone(ZoneInfo('Asia/Jerusalem')).date().isoformat()
        main = self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha']; require_sha(main, 40)
        posts = json.loads(self.content(main, 'src/data/posts.json'))
        prs = self.article_prs(posts, current_slot, state, main_sha=main)
        runs = self.runs(state)
        self._deployment = self.reader.deployment(main)
        try:
            inventory = self.inventory_reader(now=now)
        except (OSError, RuntimeError, MediaVerificationError):
            inventory = None  # Unknown, never permission to generate another upload.
        slots = {current_slot}
        backlog = [slot for slot in state['slots'] if slot < current_slot and state['slots'][slot].get('source_key')]
        if backlog:
            slots.add(min(backlog, key=lambda slot: (state['slots'][slot].get('observed_at', ''), slot)))
        publications = []
        for post in posts:
            if post.get('date') not in slots:
                continue
            source = source_metadata(post)
            target = SourceIdentity(source['date'], source['slug'], source['content_sha256'])
            article = self.article_observer(target, post, main, now)
            media = {}
            for kind in ('overview', 'short'):
                try:
                    media[kind] = observe_media(state, MediaIdentity(target, kind), source,
                        inventory=inventory, now=now, audit=self.auditor)
                except (GitHubError, OSError):
                    media[kind] = {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}
                except (StateInvalid, ValueError):
                    media[kind] = {'status': 'failed', 'failure_class': 'MEDIA_LINEAGE_INVALID'}
            publications.append({'source': target.to_dict(), 'main_sha': main, 'article': article, 'media': media})
        if self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha'] != main:
            raise StateConflict('Authoritative main changed during public observation')
        # Keep the start time: slow observations must expire rather than acquiring
        # a fresh timestamp that misrepresents old inventory or public responses.
        present = {row['source']['slot'] for row in publications}
        return Observation({'state_revision': state['revision'], 'main_sha': main, 'observed_at': now,
            'current_slot': current_slot, 'article_creation_allowed': self.window(now),
            'publications': publications, 'runs': runs, 'article_prs': prs,
            'missing_slots': sorted(slots - present - {current_slot})})
