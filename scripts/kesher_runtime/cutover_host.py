"""Administrator-owned installation and read-only preflight for the existing gateway.

Configuration and native ports live on the persistent host, never in Actions or
an HTTP request. No default port, approval generator or permissive observer exists.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

from .authority_topology import (GitHubAuthorityObserver, classify_registered, executable_digest,
                                 inventory, policy)
from .cutover_auth import ActionsIdentity, github_jwks
from .cutover_service import CutoverApplication, InvocationJournal
from .exclusion import ExclusionFence, REQUIRED_RESOURCES
from .github import _unique_object
from .handover_github import GitHubHandover
from .identity import digest, require_sha
from .live_cutover import build_runtime
from .production_cutover import reconcile_registrations
from .state import StateInvalid
from .sync_authority_policy import synchronize


@dataclass
class NativePorts:
    github: object
    boundary: object
    external_ports: dict
    separation_observer: object
    key: object
    key_binding: object
    review_check: object
    authority_observer: object


@dataclass
class Installation:
    root: Path
    repo: str
    repository_id: str
    epoch: str
    owner: str
    gateway_url: str
    ledger: Path
    review: dict
    material: dict
    closure: dict
    bindings: dict
    registrations: dict
    native: NativePorts


class ReadOnlyGitHub:
    def __init__(self, github): self.github = github

    def request(self, method, path, body=None, **kwargs):
        if method != 'GET' or body is not None:
            raise StateInvalid('CUTOVER_PREFLIGHT_MUTATION_DENIED')
        return self.github.request(method, path, **kwargs)


def read_snapshot(github, repo):
    return GitHubHandover(ReadOnlyGitHub(github), repo, observer=None, fence=None).read_snapshot()


def health(installation):
    return {'service':'kesher-cutover', 'epoch':installation.epoch,
            'reviewed_revision':installation.review['main_sha'],
            'code_sha256':installation.review['code_sha256'],
            'policy_sha256':installation.review['policy_sha256']}


def https_origin(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or
            url.query or url.fragment or url.path not in {'','/'}):
        raise StateInvalid('CUTOVER_PINNED_HTTPS_GATEWAY_REQUIRED')
    return value.rstrip('/')


def probe_gateway(origin):
    from .cutover_entry import NoRedirect
    with urllib.request.build_opener(NoRedirect()).open(origin+'/healthz', timeout=20) as response:
        return json.loads(response.read(4096), object_pairs_hook=_unique_object)


def reviewed_installation(i):
    n, review = i.native, i.review
    if (not isinstance(n, NativePorts) or set(n.external_ports) != set(REQUIRED_RESOURCES)-{'github'}
            or n.boundary is None or any(not callable(getattr(n, name)) for name in
               ('separation_observer','key','key_binding','review_check','authority_observer'))):
        raise StateInvalid('CUTOVER_COMPLETE_NATIVE_PORTS_REQUIRED')
    n.review_check()  # Independent custody/adapter review; never a client flag.
    https_origin(i.gateway_url)
    for name in ('code_sha256','policy_sha256','closed_evidence_sha256','closure_sha256',
                 'migration_material_sha256','registrations_sha256','key_binding_sha256','legacy_body_sha256'):
        require_sha(review[name])
    for name in ('main_sha','legacy_commit_sha','legacy_blob_sha'): require_sha(review[name],40)
    for value in i.closure.values(): require_sha(value)
    checkout = subprocess.check_output(['git','rev-parse','HEAD'],cwd=i.root,text=True).strip()
    rules = policy(i.root)
    definitions = inventory(i.root, rules)
    if (review['repo'] != i.repo or checkout != review['main_sha'] or synchronize(i.root)
            or review['code_sha256'] != executable_digest(i.root)
            or review['policy_sha256'] != digest({'policy':rules,'definitions':definitions})
            or review['migration_material_sha256'] != digest(i.material)
            or review['closure_sha256'] != digest(i.closure)
            or review['closed_evidence_sha256'] != i.closure['retained_evidence']
            or digest(i.material['retained_evidence']) != i.closure['retained_evidence']
            or review['registrations_sha256'] != digest(i.registrations)
            or set(i.bindings) != set(REQUIRED_RESOURCES)
            or set(i.registrations) != set(rules['workflows'])|set(rules.get('registrations',{}))):
        raise StateInvalid('CUTOVER_INDEPENDENT_INSTALLED_REVIEW_REQUIRED')
    metadata = n.key_binding()
    key = n.key()
    if (metadata.get('name') != 'NOTEBOOKLM_STATE_KEY' or metadata.get('available') is not True
            or not metadata.get('updated_at') or digest(metadata) != review['key_binding_sha256']
            or not isinstance(key,str) or len(key)<24):
        raise StateInvalid('CUTOVER_RUNTIME_KEY_BINDING_REQUIRED')
    # Deliberately never return/log the sealing key.
    del key
    InvocationJournal(i.ledger).inspect()
    pinned = json.loads(json.dumps(rules))
    for path, identity in i.registrations.items():
        if path in pinned['workflows']:
            old = pinned['workflows'][path].get('registration_id')
            if old is not None and old != identity: raise StateInvalid('CUTOVER_REGISTRATION_REBOUND')
            pinned['workflows'][path]['registration_id'] = identity
        elif pinned['registrations'][path]['id'] != identity:
            raise StateInvalid('CUTOVER_REGISTRATION_REBOUND')
    return pinned, metadata


def preflight(i, *, probe=probe_gateway):
    """No journal claim, exclusion, migration write, dispatch or provider call."""
    rules, _ = reviewed_installation(i)
    github = ReadOnlyGitHub(i.native.github)
    api = '/repos/'+i.repo
    if github.request('GET',api+'/git/ref/heads/main')['object']['sha'] != i.review['main_sha']:
        raise StateInvalid('CUTOVER_EXACT_REVIEWED_MAIN_REQUIRED')
    if str(github.request('GET',api)['id']) != i.repository_id:
        raise StateInvalid('CUTOVER_REPOSITORY_ID_REQUIRED')
    if probe(https_origin(i.gateway_url)) != health(i):
        raise StateInvalid('CUTOVER_GATEWAY_UNAVAILABLE_OR_UNREVIEWED')
    snapshot = read_snapshot(github, i.repo)
    if (snapshot.state.get('schema_version') != 5 or 'handover' in snapshot.state
            or 'github_exclusion' in snapshot.state
            or snapshot.commit_sha != i.review['legacy_commit_sha']
            or snapshot.blob_sha != i.review['legacy_blob_sha']
            or digest(snapshot.state) != i.review['legacy_body_sha256']):
        raise StateInvalid('CUTOVER_EXACT_LEGACY_SNAPSHOT_REQUIRED')
    observer = GitHubAuthorityObserver(github, i.repo, i.root, fence=None)
    registered, runs = observer.current_inventory(rules)
    reconcile_registrations(registered, rules)
    if runs: raise StateInvalid('CUTOVER_COMPETING_WRITER_RUNNING')
    separation = i.native.separation_observer()
    binding = {k:i.review[k] for k in ('repo','policy_sha256','code_sha256')}
    binding['resource_bindings_sha256'] = digest(i.bindings)
    rows = classify_registered(registered, rules, active_runs=runs, runs_complete=True,
        separation=separation.get('proofs'),binding=binding,protected_resources=i.bindings)
    if (sum(r['role']=='controller' for r in rows) != 1
            or any(r['state'] != 'active' for r in rows if r['role'] in {'controller','worker','handover'})
            or any(r['state'] not in {'disabled_manually','disabled_inactivity'}
                   for r in rows if r['role']=='retired')):
        raise StateInvalid('CUTOVER_WORKFLOW_AVAILABILITY_OR_RETIREMENT_REQUIRED')
    fence = ExclusionFence(i.repo,i.epoch,i.owner,
                          dict(i.native.external_ports,github=i.native.boundary),i.bindings)
    observations = {}
    for resource in REQUIRED_RESOURCES:
        row = fence._inspect(resource)
        if row['actors'] or row.get('protection') not in (None, fence._policy(resource)):
            raise StateInvalid('CUTOVER_EXTERNAL_WRITER_OR_COMPETING_EPOCH')
        observations[resource] = row
    # Validate pure migration preparation, preserving the closed evidence floor.
    from .live_cutover import OriginalMigrationInputs
    from .migration import prepare_migration
    # Material must contain the exact reviewed main publications, not merely
    # whatever sources an older controller snapshot happened to mention.
    from .article_verification import GitHubArticleReader
    from scripts.kesher_daily_pipeline import source_metadata
    from .migration import _post_freeze_sources
    posts = json.loads(GitHubArticleReader(github,i.repo).content(i.review['main_sha'],'src/data/posts.json'),
                       object_pairs_hook=_unique_object)
    if 'post_freeze_boundary' not in i.material:
        raise StateInvalid('MIGRATION_POST_FREEZE_REVIEW_REQUIRED')
    from .identity import SourceIdentity
    from datetime import datetime
    from zoneinfo import ZoneInfo
    frozen = snapshot.state['cycle']
    cutover = datetime.fromisoformat(i.material['now']).astimezone(ZoneInfo('Asia/Jerusalem')).date().isoformat()
    requested = {(s['date'],s['slug']) for s in i.material['sources']}
    # Old unrelated posts may not satisfy today's provider-language contract.
    # Validate every window candidate and every material reference, without
    # converting unrelated historical posts into provider/backlog inputs.
    exact_sources = [source_metadata(post) for post in posts if
        frozen <= post['date'] <= cutover or (post['date'],post.get('slug') or post['id']) in requested]
    exact_by_key = {SourceIdentity(s['date'],s['slug'],s['content_sha256']).key:s for s in exact_sources}
    catchup = _post_freeze_sources(snapshot.state,exact_by_key,i.material['now'],i.material['post_freeze_boundary'])
    material_sources = {SourceIdentity(s['date'],s['slug'],s['content_sha256']).key:s for s in i.material['sources']}
    if any(material_sources.get(SourceIdentity(s['date'],s['slug'],s['content_sha256']).key) != s for s in catchup):
        raise StateInvalid('CUTOVER_EXACT_POST_FREEZE_MAIN_SOURCES_REQUIRED')
    if (len(exact_by_key) != len(exact_sources) or len(material_sources) != len(i.material['sources'])
            or material_sources != exact_by_key):
        raise StateInvalid('CUTOVER_EXACT_MAIN_SOURCE_MATERIAL_REQUIRED')
    supplier = OriginalMigrationInputs(github,i.repo,main_sha=i.review['main_sha'],material=i.material,
                                      approved_digest=i.review['migration_material_sha256'])
    prepared = prepare_migration(**supplier(snapshot))
    if prepared['migration']['status'] != 'prepared' or prepared['commands']:
        raise StateInvalid('CUTOVER_MIGRATION_PREPARATION_INVALID')
    # Final ref readbacks detect drift. They do not substitute for the native fence.
    fresh = read_snapshot(github, i.repo)
    if (fresh.commit_sha != snapshot.commit_sha or fresh.blob_sha != snapshot.blob_sha or
            github.request('GET',api+'/git/ref/heads/main')['object']['sha'] != i.review['main_sha']):
        raise StateInvalid('CUTOVER_PREFLIGHT_REFS_CHANGED')
    return {'status':'READY_FOR_CUTOVER_REVIEW','main_sha':i.review['main_sha'],
            'schema_version':5,'legacy_commit_sha':snapshot.commit_sha,'legacy_blob_sha':snapshot.blob_sha,
            'workflow_count':len(rows),'resource_observation_sha256':digest(observations),
            'production_activated':False,'public_completion_inferred':False}


def build_application(i):
    rules, metadata = reviewed_installation(i)
    runtime = build_runtime(github=i.native.github,repo=i.repo,root=i.root,epoch=i.epoch,owner=i.owner,
        bindings=i.bindings,boundary=i.native.boundary,external_ports=i.native.external_ports,
        review=i.review,key_binding=metadata,registered_bindings=i.registrations,
        separation_observer=i.native.separation_observer,material=i.material,closure=i.closure,key=i.native.key)
    def check():
        reviewed_installation(i)
        if i.native.github.request('GET','/repos/'+i.repo+'/git/ref/heads/main')['object']['sha'] != i.review['main_sha']:
            raise StateInvalid('CUTOVER_REVIEWED_MAIN_CHANGED')
        verify_cutover_lineage(i,runtime.fence.ports['github'].epoch)
    app = CutoverApplication(runtime=runtime,identity=ActionsIdentity(i.native.github,repo=i.repo,
        repository_id=i.repository_id,main_sha=i.review['main_sha'],audience=https_origin(i.gateway_url)),
        journal=InvocationJournal(i.ledger),epoch=i.epoch,reviewed_revision=i.review['main_sha'],review_check=check)
    app.health = lambda: (InvocationJournal(i.ledger).inspect(), health(i))[1]
    app.authority = lambda token: authority_observation(i,token)
    return app


def verify_cutover_lineage(i, epoch):
    """A fresh invocation cannot silently approve a different legacy snapshot.

    Owned anchor descendants are the normal interrupted drain/import path; the
    existing epoch validates immutable ancestry/identity. Never require the
    original ref to remain HEAD after an authorized durable step.
    """
    github=ReadOnlyGitHub(i.native.github)
    loaded=read_snapshot(github,i.repo)
    if loaded.commit_sha == i.review['legacy_commit_sha']:
        if (loaded.blob_sha != i.review['legacy_blob_sha'] or
                digest(loaded.state) != i.review['legacy_body_sha256'] or
                loaded.state.get('schema_version') != 5 or 'handover' in loaded.state or
                'github_exclusion' in loaded.state):
            raise StateInvalid('CUTOVER_EXACT_LEGACY_SNAPSHOT_REQUIRED')
        return
    anchor=epoch.authority()
    if anchor['before_oid'] != i.review['legacy_commit_sha']:
        raise StateInvalid('CUTOVER_UNREVIEWED_LEGACY_LINEAGE')
    from .article_verification import GitHubArticleReader
    raw=GitHubArticleReader(github,i.repo).content(i.review['legacy_commit_sha'],'.kesher-controller/state.json')
    if (hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != i.review['legacy_blob_sha'] or
            digest(json.loads(raw,object_pairs_hook=_unique_object)) != i.review['legacy_body_sha256']):
        raise StateInvalid('CUTOVER_EXACT_LEGACY_SNAPSHOT_REQUIRED')


def authority_observation(i, token, *, jwks=github_jwks):
    """Fresh native observation only; no fence acquisition, ledger claim or write.

    After VERIFIED, generated publication changes may advance main. The native
    observer still pins executable bytes/policy and resource protection. An old
    worker head is accepted only when require_authority proves its exact command
    ownership. The cutover identity remains restricted to the original main SHA.
    """
    from .authority_client import CANONICAL_WORKFLOWS
    from .handover import require_authority
    authenticator=ActionsIdentity(ReadOnlyGitHub(i.native.github),repo=i.repo,repository_id=i.repository_id,
        main_sha=i.review['main_sha'],audience=https_origin(i.gateway_url),
        workflows=CANONICAL_WORKFLOWS,environment=None,jwks=jwks)
    claims=authenticator.authenticate(token,allow_unpinned_head=True)
    reviewed_installation(i)
    observation = i.native.authority_observer()
    if (observation.get('code_sha256') != i.review['code_sha256']
            or observation.get('policy_sha256') != i.review['policy_sha256']
            or observation.get('approved_revision',{}).get('closed_evidence_sha256') !=
               i.review['closed_evidence_sha256']):
        raise StateInvalid('CUTOVER_UNREVIEWED_LIVE_AUTHORITY')
    require_authority(read_snapshot(i.native.github,i.repo).state,observation)
    try:
        rows = [r for r in observation['active_runs']
                if str(r['id']) == claims['run_id'] and str(r['run_attempt']) == claims['run_attempt']]
        if len(rows) != 1: raise ValueError('observed live invocation required')
        # Authenticated claims grant nothing until exact native run ownership,
        # current main and complete VERIFIED resource admission also pass.
        identity = ActionsIdentity(ReadOnlyGitHub(i.native.github),repo=i.repo,repository_id=i.repository_id,
            main_sha=rows[0]['head_sha'],main_ref_sha=observation['main_sha'],
            audience=https_origin(i.gateway_url),workflows=CANONICAL_WORKFLOWS,environment=None,jwks=jwks)
        identity.verify(token)
    except (ValueError,KeyError,IndexError,TypeError):
        raise StateInvalid('CUTOVER_ACTIONS_IDENTITY_DENIED') from None
    return observation


def _document(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:
        raise StateInvalid('CUTOVER_ADMINISTRATOR_OWNED_FILE_REQUIRED')
    return json.loads(path.read_text(),object_pairs_hook=_unique_object)


def load_installation(path):
    config = _document(path)
    expected = {'version','root','repo','repository_id','epoch','owner','gateway_url','ledger','review',
                'material','closure','bindings','registrations','ports_factory'}
    if (set(config) != expected or config['version'] != 1 or config['repo'] != 'yanivsa/kesher-website'
            or not Path(config['root']).is_absolute() or not Path(config['ledger']).is_absolute()):
        raise StateInvalid('CUTOVER_INSTALLED_CONFIGURATION_REQUIRED')
    documents = {k:_document(config[k]) for k in ('review','material','closure','bindings','registrations')}
    module, name = config['ports_factory'].split(':',1)
    spec = importlib.util.find_spec(module)
    if (not spec or not spec.origin or hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest() !=
            documents['review']['ports_factory_sha256']):
        raise StateInvalid('CUTOVER_REVIEWED_NATIVE_FACTORY_REQUIRED')
    # Only a separately installed reviewed module; no HTTP or workflow input selects it.
    native = getattr(importlib.import_module(module),name)()
    return Installation(**{k:config[k] for k in ('repo','repository_id','epoch','owner','gateway_url')},
        root=Path(config['root']),ledger=Path(config['ledger']),native=native,**documents)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('action',choices=('preflight','serve'))
    parser.add_argument('--port',type=int,default=8789)
    args = parser.parse_args(argv)
    try:
        installation = load_installation(args.config)
        if args.action == 'preflight': print(json.dumps(preflight(installation))); return 0
        from http.server import HTTPServer
        from .cutover_service import handler
        HTTPServer(('127.0.0.1',args.port),handler(build_application(installation))).serve_forever()
        return 0
    except Exception as exc:
        # Private material and credential-bearing exception text never enter logs.
        safe_codes = {'CUTOVER_COMPLETE_NATIVE_PORTS_REQUIRED','CUTOVER_PINNED_HTTPS_GATEWAY_REQUIRED',
            'CUTOVER_INDEPENDENT_INSTALLED_REVIEW_REQUIRED','CUTOVER_RUNTIME_KEY_BINDING_REQUIRED',
            'CUTOVER_INVOCATION_LEDGER_UNAVAILABLE','CUTOVER_REGISTRATION_REBOUND',
            'CUTOVER_EXACT_REVIEWED_MAIN_REQUIRED','CUTOVER_REPOSITORY_ID_REQUIRED',
            'CUTOVER_GATEWAY_UNAVAILABLE_OR_UNREVIEWED','CUTOVER_EXACT_LEGACY_SNAPSHOT_REQUIRED',
            'CUTOVER_COMPETING_WRITER_RUNNING','CUTOVER_WORKFLOW_AVAILABILITY_OR_RETIREMENT_REQUIRED',
            'CUTOVER_EXTERNAL_WRITER_OR_COMPETING_EPOCH','MIGRATION_POST_FREEZE_REVIEW_REQUIRED',
            'MIGRATION_POST_FREEZE_BOUNDARY_INVALID_OR_AMBIGUOUS',
            'CUTOVER_EXACT_POST_FREEZE_MAIN_SOURCES_REQUIRED','CUTOVER_EXACT_MAIN_SOURCE_MATERIAL_REQUIRED',
            'CUTOVER_ADMINISTRATOR_OWNED_FILE_REQUIRED','CUTOVER_REVIEWED_NATIVE_FACTORY_REQUIRED'}
        code=str(exc) if isinstance(exc,StateInvalid) and str(exc) in safe_codes else 'CUTOVER_HOST_BLOCKED'
        print(code+': independently verify installation prerequisites',file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
