"""Durable article pixels, conditional Git update, and recoverable PR evidence.

Optional remote image calls are attempted once per exact editorial record.
An unanswered generation falls through; it never authorizes another generation.
Selected bytes live in content-addressed Git blobs before the PR changes.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from scripts.kesher_article_contract import (IMAGE_PROVIDER_ORDER, IMAGE_PROVIDER_RULES,
    article_sha256, exact_field, image_dimensions, image_pixel_sha256, image_proof_errors, replace_image_evidence)
from .github import GitHubError
from .identity import SlotIdentity, digest, require_sha
from .jules import JulesError
from .state import ClaimRejected, StateInvalid
from .article_normalize_worker import GitNormalization
from scripts.kesher_article_contract import ARTICLE_PUBLICATION_PATHS, forbidden_article_paths
from scripts.kesher_article_normalizer import extract_target_article, normalized_posts


def _prior(context, name):
    state = context.store.load().state
    context._owned(state)
    rows = [row['effects'][name] for row in state['commands'].values()
            if row['target'] == context.target.to_dict() and name in row['effects']]
    requests = {row['request_sha256']: row['request'] for row in rows}
    if len(requests) > 1:
        raise StateInvalid('Conflicting exact article image intents')
    return copy.deepcopy(next(iter(requests.values()), None))


def image_receipt_matches(state, slot, number, head, post, data, body, *, base_sha=None):
    """Mutable PR prose cannot assert a trusted provider execution by itself."""
    if not state or image_proof_errors(post, body, head, data):
        return False
    for command in state['commands'].values():
        if command['target'] != SlotIdentity(slot).to_dict() or command['operation'] != 'attach_image':
            continue
        for name, effect in command['effects'].items():
            receipt = effect['receipt']
            if not name.startswith('image_branch_') or not receipt:
                continue
            proof = receipt.get('image_evidence') or {}
            if (receipt.get('pr_number') == number and receipt.get('new_head_sha') == head
                    and (base_sha is None or effect['request'].get('main_sha') == base_sha)
                    and proof == effect['request'].get('image_evidence')
                    and proof.get('Image Article SHA-256') == article_sha256(post)
                    and proof.get('Image SHA-256') == hashlib.sha256(data).hexdigest()
                    and all(exact_field(body, label) == value for label, value in proof.items())):
                return True
    return False


def _editorial(post):
    value = copy.deepcopy(post)
    value.pop('image', None); value.pop('imageAlt', None)
    if not re.fullmatch(r'[\w-]+', str(value.get('id', '')), re.UNICODE):
        raise JulesError('ARTICLE_PR_IDENTITY_MISMATCH')
    return value


def _evidence(post, candidate, head):
    width, height = image_dimensions(candidate['data'])
    return {'Image Pipeline Version': '2', 'Image Provider': candidate['provider'],
            'Image Attempt Chain': '/'.join(candidate['attempts']),
            'Image Generation Result': IMAGE_PROVIDER_RULES[candidate['provider']][0],
            'Image Source URL': candidate['source_url'],
            'Image SHA-256': hashlib.sha256(candidate['data']).hexdigest(),
            'Image Dimensions': f'{width}x{height}', 'Image Visual Match': candidate['visual_match'],
            'Image Article ID': str(post['id']), 'Image Article SHA-256': article_sha256(post),
            'Image Evidence Head': head}


def _with_image(post, candidate):
    return dict(_editorial(post), image='/images/generated/blog/' + post['id'] + '.' + candidate['extension'],
                imageAlt=candidate['visual_match'])


def _descriptor(candidate):
    data = candidate['data']
    return {key: candidate[key] for key in ('provider', 'extension', 'source_url', 'visual_match', 'attempts')} | {
        'blob_sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
        'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}


def _restore(descriptor, blobs):
    data = blobs.get(descriptor['blob_sha'])
    if data is None:
        return None
    candidate = {key: descriptor[key] for key in ('provider', 'extension', 'source_url', 'visual_match', 'attempts')}
    candidate['data'] = data
    if _descriptor(candidate) != descriptor:
        raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
    return candidate


def _valid(post, candidate, used):
    try:
        data = candidate['data']
        if len(data) > 8 * 1024 * 1024 or candidate['extension'] != ('png' if data.startswith(b'\x89PNG') else 'jpg'):
            return False
        proof = _evidence(_with_image(post, candidate), candidate, 'a'*40)
        if image_proof_errors(_with_image(post, candidate), replace_image_evidence('', proof), 'a'*40, data):
            return False
        return (hashlib.sha256(data).hexdigest() not in used and 'pixels:' + image_pixel_sha256(data) not in used)
    except (ValueError, KeyError, TypeError):
        return False


def select_image(context, post, pr_number, providers, blobs, existing_hashes):
    """Resume the approved provider chain without repeating uncertain remote work."""
    post = _editorial(post)
    if not isinstance(context.target, SlotIdentity) or post.get('date') != context.target.slot:
        raise ClaimRejected('Image candidate needs the exact article slot')
    key = digest([pr_number, article_sha256(post)])[:24]
    for index, provider in enumerate(IMAGE_PROVIDER_ORDER):
        suffix = key + '_' + str(index)
        name, blob_name = 'image_candidate_' + suffix, 'image_blob_' + suffix
        request = {'contract': 'article-image-v1', 'pr_number': pr_number,
                   'article_sha256': article_sha256(post), 'provider': provider}
        decision = context.begin_effect(name, request)
        if decision.receipt:
            if decision.receipt['status'] != 'selected':
                continue
            candidate = _restore(decision.receipt['image'], blobs)
            if candidate is None:
                raise JulesError('ARTICLE_IMAGE_OUTPUT_MISSING')
            if _valid(post, candidate, existing_hashes):
                return candidate
            continue
        descriptor = _prior(context, blob_name)
        candidate = _restore(descriptor, blobs) if descriptor else None
        if candidate is None and (decision.execute or provider.startswith('local-')):
            # Local render/copy is deterministic and safe to reconstruct. Remote
            # generation or verification is never repeated after an unknown call.
            candidate = providers[provider](post, existing_hashes)
            if candidate:
                candidate = dict(candidate, attempts=list(IMAGE_PROVIDER_ORDER[:index + 1]))
                if IMAGE_PROVIDER_RULES.get(candidate.get('provider'), (None, None))[1] != provider:
                    raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
                if not _valid(post, candidate, existing_hashes):
                    candidate = None
                else:
                    proposed = _descriptor(candidate)
                    if descriptor and descriptor != proposed:
                        raise JulesError('ARTICLE_DERIVATION_CHANGED')
                    descriptor = proposed
                    context.begin_effect(blob_name, descriptor)
                    try:
                        if blobs.put(candidate['data']) != descriptor['blob_sha']:
                            raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
                    except OSError:
                        pass
                    candidate = _restore(descriptor, blobs)
        if candidate is None:
            context.complete_effect(name, {'status': 'unavailable',
                'reason': 'no_accepted_output' if decision.execute else 'unanswered_remote_attempt'})
            continue
        if not _valid(post, candidate, existing_hashes):
            raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
        context.begin_effect(blob_name, descriptor)
        context.complete_effect(blob_name, {'blob_sha': descriptor['blob_sha'], 'sha256': descriptor['sha256']})
        context.complete_effect(name, {'status': 'selected', 'image': descriptor})
        return candidate
    raise JulesError('ARTICLE_IMAGE_UNAVAILABLE')


def attach_image(context, pr, branch, pull, choose, *, prove_quiescent):
    command = context._owned(context.store.load().state)
    if not isinstance(context.target, SlotIdentity) or command['operation'] != 'attach_image':
        raise ClaimRejected('Exact article image command required')
    expected = command['inputs']; old = expected.get('pr_head_sha'); require_sha(old, 40)
    if (pr.get('state') != 'open' or pr.get('draft') or str(pr.get('number')) != expected.get('pr_number')
            or pr.get('base', {}).get('ref') != 'main'
            or (pr.get('head', {}).get('repo') or {}).get('full_name') != context.store.repo
            or not str(pr.get('title', '')).startswith('Publish Kesher article:')):
        raise JulesError('ARTICLE_PR_CHANGED')
    ref = pr['head']['ref']
    if not isinstance(ref, str) or not ref or ref in {'main', 'automation-state'}:
        raise JulesError('ARTICLE_PR_IDENTITY_MISMATCH')
    name = 'image_branch_' + digest([pr['number'], old, context.code_sha])[:32]
    previous = _prior(context, name)
    if previous is None:
        state = context.store.load().state
        matches = {effect_name: effect['request'] for row in state['commands'].values()
                   if row['target'] == context.target.to_dict()
                   for effect_name, effect in row['effects'].items()
                   if effect_name.startswith('image_branch_')
                   and effect['request'].get('pr_number') == pr['number']
                   and effect['request'].get('new_head_sha') == old}
        if len(matches) > 1:
            raise StateInvalid('Multiple image updates claim the same PR head')
        if matches:
            name, previous = next(iter(matches.items()))
            old = previous['old_head_sha']
    allowed = {old, previous['new_head_sha'] if previous else old}
    if pr['head']['sha'] not in allowed or (previous and previous['branch'] != ref):
        raise JulesError('ARTICLE_PR_CHANGED')
    actual = branch.head(ref)
    if actual not in allowed:
        raise JulesError('ARTICLE_PR_CHANGED')
    # Even body-only reconciliation rereads session state. A known image ref
    # update is tied to the old-head settling receipt by this saved intent.
    prove_quiescent(pr)
    if not previous or actual == old:
        post = branch.article(main_sha=context.code_sha, head_sha=old, slot=context.target.slot)
        candidate = choose(post)
        prepared_at = previous['prepared_at'] if previous else command['created_at']
        prepared = branch.prepare(main_sha=context.code_sha, head_sha=old, post=post, candidate=candidate,
                                  slot=context.target.slot, pr_number=pr['number'], prepared_at=prepared_at)
        for field in ('new_head_sha', 'tree_sha'): require_sha(prepared[field], 40)
        proof = _evidence(prepared['post'], candidate, prepared['new_head_sha'])
        if image_proof_errors(prepared['post'], replace_image_evidence('', proof), prepared['new_head_sha'], candidate['data']):
            raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
        request = {'pr_number': pr['number'], 'branch': ref, 'old_head_sha': old,
                   'main_sha': context.code_sha, 'prepared_at': prepared_at,
                   'new_head_sha': prepared['new_head_sha'], 'tree_sha': prepared['tree_sha'], 'image_evidence': proof}
        if previous and request != previous:
            raise JulesError('ARTICLE_DERIVATION_CHANGED')
    else:
        request = previous
    context.begin_effect(name, request)
    if branch.head(ref) != request['new_head_sha']:
        prove_quiescent(pr)
        if branch.head(ref) != old:
            raise JulesError('ARTICLE_PR_CHANGED')
        try:
            branch.push(ref, old, request['new_head_sha'])
        except OSError:
            pass
        if branch.head(ref) != request['new_head_sha']:
            raise JulesError('TRANSIENT_API' if branch.head(ref) == old else 'ARTICLE_PR_CHANGED')
    current = pull.get()
    if current['head']['sha'] != request['new_head_sha'] or current.get('state') != 'open':
        raise JulesError('ARTICLE_PR_CHANGED')
    desired = replace_image_evidence(current.get('body') or '', request['image_evidence'])
    if desired != current.get('body'):
        prove_quiescent(current)
        # This idempotent body update never initiates provider work. The branch
        # intent already persists every evidence field for a lost PATCH reply.
        try:
            pull.patch_body(desired)
        except OSError:
            pass
        current = pull.get()
        if current.get('body') != desired:
            raise JulesError('TRANSIENT_API')
    if current['head']['sha'] != request['new_head_sha'] or branch.head(ref) != request['new_head_sha']:
        raise JulesError('ARTICLE_PR_CHANGED')
    result = {key: request[key] for key in ('pr_number', 'old_head_sha', 'new_head_sha', 'tree_sha', 'image_evidence')}
    context.complete_effect(name, result)
    return result


class GitHubImageBlobs:
    def __init__(self, github, repo): self.github, self.repo = github, repo

    def get(self, sha):
        require_sha(sha, 40)
        try:
            row = self.github.request('GET', f'/repos/{self.repo}/git/blobs/{sha}')
        except GitHubError as exc:
            if exc.status == 404: return None
            raise
        if row.get('sha') != sha or row.get('encoding') != 'base64' or not 0 < row.get('size', 0) <= 8 * 1024 * 1024:
            raise JulesError('ARTICLE_IMAGE_OUTPUT_INVALID')
        return base64.b64decode(row['content'].replace('\n', ''), validate=True)

    def put(self, data):
        row = self.github.request('POST', f'/repos/{self.repo}/git/blobs',
                                  {'content': base64.b64encode(data).decode('ascii'), 'encoding': 'base64'})
        return row['sha']


class GitImageBranch:
    def __init__(self, root, *, generator=None):
        self.git = GitNormalization(Path(root), generator=generator)
        self.root = self.git.root

    def head(self, ref): return self.git.head(ref)

    def push(self, ref, old, new): return self.git.push(ref, old, new)

    def article(self, *, main_sha, head_sha, slot):
        require_sha(main_sha, 40); require_sha(head_sha, 40)
        if self.git._git('rev-parse', 'HEAD') != main_sha or self.git._git('status', '--porcelain'):
            raise JulesError('ARTICLE_TRUSTED_CHECKOUT_REQUIRED')
        self.git._git('fetch', '--no-tags', 'origin', head_sha)
        base = json.loads(self.git._git('show', main_sha + ':src/data/posts.json'))
        head = json.loads(self.git._git('show', head_sha + ':src/data/posts.json'))
        post = extract_target_article(base, head, slot)
        paths = self.git._git('diff', '--name-only', main_sha, head_sha).splitlines()
        if head != normalized_posts(base, post) or forbidden_article_paths(paths):
            raise JulesError('ARTICLE_NORMALIZATION_REQUIRED')
        return _editorial(post)

    def used_hashes(self):
        used = set()
        for post in json.loads((self.root / 'src/data/posts.json').read_text(encoding='utf-8')):
            image = post.get('image')
            if not image: continue
            path = (self.root / 'public' / image.lstrip('/')).resolve()
            if not str(image).startswith('/images/') or not path.is_relative_to(self.root / 'public/images'):
                raise JulesError('ARTICLE_IMAGE_INVENTORY_INVALID')
            data = path.read_bytes()
            used.add(hashlib.sha256(data).hexdigest())
            used.add('pixels:' + image_pixel_sha256(data))
        return used

    def prepare(self, *, main_sha, head_sha, post, candidate, slot, pr_number, prepared_at):
        if self.article(main_sha=main_sha, head_sha=head_sha, slot=slot) != _editorial(post):
            raise JulesError('ARTICLE_PR_CHANGED')
        base = json.loads(self.git._git('show', main_sha + ':src/data/posts.json'))
        post = _with_image(post, candidate)
        image_path = 'public' + post['image']
        output = self.root / image_path
        if output.exists():
            # A new publication cannot replace any trusted base image, even an
            # unassigned one. Article ids are unique; collisions are incidents.
            raise JulesError('ARTICLE_IMAGE_PATH_CONFLICT')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(candidate['data'])
        (self.root / 'src/data/posts.json').write_text(json.dumps(normalized_posts(base, post), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.git.generator()
        if forbidden_article_paths(self.git._git('diff', '--name-only').splitlines()):
            raise JulesError('ARTICLE_DERIVATION_INVALID')
        with tempfile.TemporaryDirectory(prefix='kesher-image-index-') as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'),
                       GIT_AUTHOR_NAME='Kesher Article Image Worker', GIT_AUTHOR_EMAIL='actions@users.noreply.github.com',
                       GIT_COMMITTER_NAME='Kesher Article Image Worker', GIT_COMMITTER_EMAIL='actions@users.noreply.github.com',
                       GIT_AUTHOR_DATE=prepared_at, GIT_COMMITTER_DATE=prepared_at)
            self.git._git('read-tree', main_sha, env=env)
            self.git._git('add', '-f', '-A', '--', *sorted(ARTICLE_PUBLICATION_PATHS), image_path, env=env)
            tree = self.git._git('write-tree', env=env)
            commit = self.git._git('commit-tree', tree, '-p', main_sha, '-m', f'Attach Kesher article image {slot} PR #{pr_number}', env=env)
        return {'new_head_sha': commit, 'tree_sha': tree, 'post': post}


class GitHubImagePull:
    def __init__(self, github, repo, number):
        self.github, self.path = github, f'/repos/{repo}/pulls/{number}'

    def get(self): return self.github.request('GET', self.path)

    def patch_body(self, body): return self.github.request('PATCH', self.path, {'body': body})
