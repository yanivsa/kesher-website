"""Closed, explicitly reviewed workflow inventory. Names never imply safety.

Hashes bind the complete definitions and scripts (including inline/transitive
mutators). The policy is a reviewed trust root, not a heuristic code scanner.
Registered paths absent from that trust root are always a refusal.
"""
from pathlib import Path
import base64
import hashlib
import json
import re
import stat

from scripts.kesher_article_contract import ARTICLE_IMAGE_PREFIX, ARTICLE_PUBLICATION_PATHS, image_dimensions

from .identity import digest
from .state import StateInvalid

CAPABILITIES = {'read', 'artifact_write', 'branch_write', 'pr_write', 'merge', 'issue_write',
                'status_write', 'workflow_dispatch', 'state_write', 'jules_create', 'jules_continue',
                'provider_create', 'provider_continue', 'capability_write', 'youtube_upload',
                'youtube_metadata', 'cloudflare_write', 'image_provider_create', 'image_write', 'oci_write'}
ROLES = {'controller', 'worker', 'retired', 'diagnostic', 'separate_infrastructure'}
# Exact historical storage identities, reviewed unreachable from every workflow,
# package script, script, frontend and test entrypoint. Never dereference these.
INERT_GIT_LINK_TARGETS = {
    '.venv-dub/bin/python':'python3',
    '.venv-dub/bin/python3':'/Library/Developer/CommandLineTools/usr/bin/python3',
    '.venv-dub/bin/python3.9':'python3',
}
INERT_REVIEW_SCOPES = ['.github/', 'scripts/', 'src/', 'tests/', 'package.json']
CAPABILITY_RESOURCE = {
    'branch_write':'github', 'pr_write':'github', 'merge':'github', 'issue_write':'github',
    'status_write':'github', 'workflow_dispatch':'github', 'state_write':'github',
    'capability_write':'github', 'jules_create':'jules', 'jules_continue':'jules',
    'provider_create':'notebooklm', 'provider_continue':'notebooklm',
    'youtube_upload':'youtube', 'youtube_metadata':'youtube', 'cloudflare_write':'cloudflare',
    'image_provider_create':'image_provider', 'image_write':'github', 'oci_write':'oci',
}


def policy(root):
    return json.loads((Path(root)/'scripts/kesher_runtime/authority_policy.json').read_text())


def check_definitions(definitions, rules):
    import yaml
    if rules.get('version') != 2:
        raise StateInvalid('AUTHORITY_CAPABILITY_POLICY_REQUIRED')
    if set(definitions) != set(rules['workflows']):
        raise StateInvalid('AUTHORITY_UNCLASSIFIED_DEFINITION')
    rows = []
    for path, text in sorted(definitions.items()):
        entry = rules['workflows'][path]
        _review(entry)
        if hashlib.sha256(text.encode()).hexdigest() != entry.get('definition_sha256'):
            raise StateInvalid('AUTHORITY_UNREVIEWED_DEFINITION_CHANGE')
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise StateInvalid('AUTHORITY_INVALID_DEFINITION')
        role = entry['role']
        targets = entry['review']['dispatches']
        if any(target not in rules['workflows'] for target in targets):
            raise StateInvalid('AUTHORITY_UNCLASSIFIED_INDIRECT_DISPATCH')
        if targets and 'workflow_dispatch' not in entry['capabilities']:
            raise StateInvalid('AUTHORITY_FALSE_READONLY_DISPATCH')
        for target in targets:
            child = rules['workflows'][target]
            _review(child)
            if (not set(child['resources']) <= set(entry['resources'])
                    or not set(child['capabilities']) - {'read', 'artifact_write'} <= set(entry['capabilities'])):
                raise StateInvalid('AUTHORITY_INDIRECT_MUTATION_SCOPE_MISSING')
        if role == 'diagnostic' and (set(entry['capabilities']) - {'read', 'artifact_write'} or entry['resources']):
            raise StateInvalid('AUTHORITY_FALSE_READONLY_CLASSIFICATION')
        jobs = data.get('jobs', {})
        if not isinstance(jobs, dict) or not jobs or any(not isinstance(j,dict) for j in jobs.values()):
            raise StateInvalid('AUTHORITY_INVALID_DEFINITION')
        for permissions in [data.get('permissions'), *(j.get('permissions') for j in jobs.values())]:
            if permissions is None: continue
            if not isinstance(permissions, dict):
                if permissions == 'read-all': continue
                raise StateInvalid('AUTHORITY_UNREVIEWED_PERMISSIONS')
            for scope, level in permissions.items():
                if level != 'write': continue
                required = {'contents':'branch_write','pull-requests':'pr_write','actions':'workflow_dispatch',
                            'statuses':'status_write','issues':'issue_write'}.get(scope)
                if role == 'diagnostic' or required not in entry['capabilities']:
                    raise StateInvalid('AUTHORITY_FALSE_READONLY_PERMISSIONS')
        retired = all(j.get('if') == "${{ github.repository == '__KESHER_RETIRED__' }}" for j in jobs.values())
        if role == 'retired' and not retired:
            raise StateInvalid('AUTHORITY_LEGACY_DEFINITION_RUNNABLE')
        if role == 'controller' and 'scripts.kesher_runtime.controller_entry --mode live' not in text:
            raise StateInvalid('AUTHORITY_CONTROLLER_NOT_CANONICAL')
        # PyYAML's YAML 1.1 loader reads the GitHub `on` key as True.
        events = data.get('on', data.get(True))
        if role == 'worker':
            if (not isinstance(events, dict) or set(events) != {'workflow_dispatch'}
                    or set(events['workflow_dispatch'].get('inputs', {})) != {'command_id'}
                    or 'scripts.kesher_runtime.worker_entry claim' not in text):
                raise StateInvalid('AUTHORITY_WORKER_NOT_EXACT_COMMAND')
        rows.append({'path':path, 'role':role, 'sha256':hashlib.sha256(text.encode()).hexdigest(),
                     'capabilities':entry['capabilities'], 'resources':entry['resources'],
                     'definition_retired':retired, 'triggers': sorted(events) if isinstance(events, dict) else events})
    return rows


def inventory(root, rules):
    root = Path(root)
    rows = check_definitions({str(p.relative_to(root)):p.read_text() for p in (root/'.github/workflows').glob('*.y*ml')}, rules)
    for entry in rules['workflows'].values():
        for name, expected in entry['review']['call_chain'].items():
            path = _regular(root, name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise StateInvalid('AUTHORITY_UNREVIEWED_CALL_CHAIN_CHANGE')
    return rows


def _review(entry):
    try:
        caps, resources, review = entry['capabilities'], entry['resources'], entry['review']
        if (not isinstance(caps, list) or not caps or len(set(caps)) != len(caps)
                or not all(isinstance(c, str) and c for c in caps)
                or set(caps) - CAPABILITIES or entry['role'] not in ROLES
                or not isinstance(resources, list) or len(set(resources)) != len(resources)
                or not all(isinstance(r, str) and r for r in resources)
                or not isinstance(review['call_chain'], dict)
                or not isinstance(review['dispatches'], list)
                or not isinstance(review['credentials'], list)
                or not all(isinstance(c, str) and c for c in review['credentials'])
                or len(set(review['credentials'])) != len(review['credentials'])
                or not isinstance(review['credential_services'], dict)
                or not set(review['credential_services']) <= set(review['credentials'])
                or not all(service is None or isinstance(service, str) and service
                           for service in review['credential_services'].values())
                or not review['note']):
            raise ValueError('incomplete review')
        if set(caps)-{'read','artifact_write'} and not resources:
            raise ValueError('mutation resource scope required')
        scoped_services = {resource.split('.')[0] for resource in resources}
        if any(CAPABILITY_RESOURCE[cap] not in scoped_services for cap in set(caps)-{'read','artifact_write'}):
            raise ValueError('unrelated mutation resource scope')
        for name, sha in review['call_chain'].items():
            if not authority_path(name) or not re.fullmatch('[a-f0-9]{64}', sha):
                raise ValueError('invalid reviewed execution input')
    except (KeyError, TypeError, ValueError):
        raise StateInvalid('AUTHORITY_CAPABILITY_REVIEW_REQUIRED')


def classify_registered(rows, rules, *, separation=None, binding=None, protected_resources=None):
    result = []
    for row in rows:
        if row.get('path') not in rules['workflows']:
            if row.get('path') in rules.get('registrations', {}):
                # A retained identity is recorded for adjudication, not approved.
                # Disabled registration does not revoke old executions/tokens.
                raise StateInvalid('AUTHORITY_REGISTERED_DEFINITION_MISSING')
            raise StateInvalid('AUTHORITY_UNCLASSIFIED_REGISTERED_WORKFLOW')
        entry = rules['workflows'][row['path']]
        _review(entry)
        role = entry['role']
        needs_separation = role == 'separate_infrastructure'
        if needs_separation and not _separated(row, entry, separation, binding, protected_resources):
            role = 'retired'
        result.append({k:row[k] for k in ('id','path','state')} | {
            'role':role, 'configured_role':entry['role'], 'definition_present':True,
            'capabilities':entry['capabilities'], 'resources':entry['resources'],
            'separation_required':needs_separation})
    return result


def _separated(row, entry, separation, binding, protected_resources):
    if separation is None or row['path'] not in separation:
        return False
    proof = separation[row['path']]
    try:
        services = {resource.split('.')[0] for resource in entry['resources']}
        credential_services = entry['review']['credential_services']
        # Incomplete/unresolved metadata can record a retired writer. It cannot
        # authorize separation, nor can a service name substitute for evidence.
        if (not services or set(credential_services) != set(entry['review']['credentials'])
                or set(credential_services.values()) != services):
            raise ValueError('unresolved service credential review')
        expected = dict(binding or {}, workflow_id=row['id'], workflow_path=row['path'],
                        definition_sha256=entry['definition_sha256'],
                        review_sha256=digest(entry['review']), resources=entry['resources'])
        if (not binding or set(binding) != {'repo', 'policy_sha256', 'code_sha256', 'resource_bindings_sha256'}
                or not isinstance(protected_resources, dict) or not protected_resources
                or binding['resource_bindings_sha256'] != digest(protected_resources)
                or proof['binding'] != expected or not proof['receipt_id']
                or proof['kind'] != 'service_enforced_resource_separation'
                or not isinstance(proof['enforcements'], list) or not proof['enforcements']
                or not _identities(proof['effective_resource_ids'])
                or not _identities(proof['protected_resource_ids'])
                or not _identities(list(protected_resources.values()))
                or set(proof['protected_resource_ids']) != set(protected_resources.values())
                or set(proof['effective_resource_ids']) & set(proof['protected_resource_ids'])
                or proof['credentials'] != entry['review']['credentials']):
            raise ValueError('resource boundary mismatch')
        enforced_services = set()
        for enforcement in proof['enforcements']:
            service = enforcement['service']
            scopes = {resource for resource in entry['resources'] if resource.split('.')[0] == service}
            classes = {name for name, reviewed_service in credential_services.items() if reviewed_service == service}
            credentials = enforcement['credential_bindings']
            readback = enforcement['readback']
            if (service not in services or service in enforced_services
                    or not isinstance(enforcement['policy_id'], str) or not enforcement['policy_id'].strip()
                    or not isinstance(enforcement['revision'], str) or not enforcement['revision'].strip()
                    or not _identities(enforcement['resources']) or set(enforcement['resources']) != scopes
                    or not _identities(enforcement['credential_classes'])
                    or set(enforcement['credential_classes']) != classes
                    or not isinstance(credentials, dict) or set(credentials) != classes
                    or not all(_identities(ids) for ids in credentials.values())
                    or not _identities(enforcement['credential_ids'])
                    or set(enforcement['credential_ids']) != {identity for ids in credentials.values() for identity in ids}
                    or not isinstance(readback, dict) or enforcement['readback_sha256'] != digest(readback)
                    or any(readback.get(field) != enforcement[field] for field in
                           ('service', 'resources', 'credential_classes', 'credential_ids', 'credential_bindings'))
                    or readback.get('effective_resource_ids') != proof['effective_resource_ids']
                    or readback.get('denied_resource_ids') != proof['protected_resource_ids']):
                raise ValueError('missing service enforcement')
            enforced_services.add(service)
        if enforced_services != services:
            raise ValueError('incomplete service enforcement')
    except (KeyError, TypeError, ValueError):
        raise StateInvalid('AUTHORITY_RESOURCE_SEPARATION_INVALID')
    return True


def _identities(values):
    return (isinstance(values, list) and bool(values)
            and all(isinstance(value, str) and value.strip() and value.strip() == value for value in values)
            and len(set(values)) == len(values))


def authority_path(path):
    # An unknown path is pinned; only the shared publication contract is exempt.
    # This is a path classification, never a substitute for byte/mode validation.
    if not isinstance(path, str) or any(part in {'', '.', '..'} for part in path.split('/')):
        raise StateInvalid('AUTHORITY_INVALID_PATH')
    return not (path in ARTICLE_PUBLICATION_PATHS or
                (path.startswith(ARTICLE_IMAGE_PREFIX) and Path(path).suffix.lower() in {'.png','.jpg','.jpeg'}))


def _regular(root, name):
    authority_path(name)  # Refuse traversal before touching the filesystem.
    root = Path(root).resolve()
    path = root / name
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise StateInvalid('AUTHORITY_NONREGULAR_CODE_FILE')
        cursor = cursor.parent
    if not path.is_file():
        raise StateInvalid('AUTHORITY_NONREGULAR_CODE_FILE')
    return path


def _inert_link_sha(name, rules):
    """Pin an exact reviewed Git link as storage; never grant execution."""
    try:
        entry = rules['inert_git_links'][name]
        target = INERT_GIT_LINK_TARGETS[name]
        raw = target.encode()
        sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if (entry['mode'] != '120000' or entry['link_target'] != target or entry['blob_sha1'] != sha
                or entry['execution_reachable'] is not False or entry['usage_review']['reference_count'] != 0
                or entry['usage_review']['reviewed_scopes'] != INERT_REVIEW_SCOPES
                or not entry['usage_review']['note']):
            raise ValueError('unreviewed storage link')
        return sha
    except (KeyError, TypeError, ValueError) as exc:
        raise StateInvalid('AUTHORITY_NONREGULAR_CODE_FILE') from exc


def _publication_bytes(name, raw):
    try:
        if name.startswith(ARTICLE_IMAGE_PREFIX):
            image_dimensions(raw)
            return
        text = raw.decode('utf-8')
        if '\x00' in text or text.startswith('#!'):
            raise ValueError('executable/binary publication data')
        if name.endswith('.json'):
            def constant(value): raise ValueError('nonfinite JSON')
            data = json.loads(text, parse_constant=constant)
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise ValueError('publication records required')
        elif name.endswith('.xml'):
            from xml.etree import ElementTree
            if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
                raise ValueError('publication XML entities forbidden')
            root = ElementTree.fromstring(text)
            if root.tag.split('}')[-1] != ('rss' if name == 'public/rss.xml' else 'urlset'):
                raise ValueError('publication XML root mismatch')
    except (ValueError, UnicodeError, SyntaxError) as exc:
        raise StateInvalid('AUTHORITY_INVALID_PUBLICATION_OUTPUT') from exc


def _checkout_manifests(root):
    import subprocess
    root = Path(root)
    paths = subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],
        cwd=root,check=True,capture_output=True).stdout.decode().split('\0')
    rules = policy(root) if (root/'scripts/kesher_runtime/authority_policy.json').is_file() else {}
    code, publication = {}, {}
    for name in sorted(set(p for p in paths if p)):
        if name in rules.get('inert_git_links', {}):
            sha = _inert_link_sha(name, rules)
            path = root.resolve() / name
            cursor = path.parent
            while cursor != root.resolve():
                if cursor.is_symlink(): raise StateInvalid('AUTHORITY_NONREGULAR_CODE_FILE')
                cursor = cursor.parent
            if not path.is_symlink() or str(path.readlink()) != INERT_GIT_LINK_TARGETS[name]:
                raise StateInvalid('AUTHORITY_NONREGULAR_CODE_FILE')
            code[name] = sha
            continue
        path = _regular(root, name)
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if authority_path(name):
            code[name] = blob
        else:
            if path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                raise StateInvalid('AUTHORITY_EXECUTABLE_PUBLICATION_OUTPUT')
            _publication_bytes(name, raw)
            publication[name] = blob
    return code, publication


def code_manifest(root):
    return _checkout_manifests(root)[0]


def executable_digest(root):
    return digest(code_manifest(root))


class GitHubAuthorityObserver:
    """Complete exact API inventory under a caller-owned external fence.

    The fence supplies key metadata and a complete inventory of unowned external
    writers. An empty list must be proven by that service, never defaulted here.
    Its lifetime must span admission and the ensuing mutation, not just read().
    """
    def __init__(self, github, repo, root, *, fence):
        self.github, self.repo, self.root, self.fence = github, repo, Path(root), fence

    def __call__(self):
        from .exclusion import validate_external
        if self.fence is None:
            raise StateInvalid('AUTHORITY_EXCLUSIVE_FENCE_REQUIRED')
        protection = validate_external(self.fence.assert_exclusive(self.repo), self.repo)
        rules = policy(self.root)
        definitions = inventory(self.root, rules)
        main = self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha']
        # Compare immutable Git tree entries, including absent/new executables.
        tree = self.github.request('GET', f'/repos/{self.repo}/git/trees/{main}?recursive=1')
        if tree.get('truncated') is not False or tree.get('sha') is None:
            raise StateInvalid('AUTHORITY_INCOMPLETE_CODE_TREE')
        actual, publication = _checkout_manifests(self.root)
        expected = self.review_tree(tree, publication, rules)
        if actual != expected:
            raise StateInvalid('AUTHORITY_CHECKOUT_CODE_DIFFERS_FROM_MAIN')
        fence = self.fence.observe(self.repo)
        if validate_external(fence['external'], self.repo) != protection:
            raise StateInvalid('AUTHORITY_RESOURCE_PROTECTION_CHANGED')
        binding = {'repo':self.repo, 'policy_sha256':digest({'policy':rules,'definitions':definitions}),
                   'code_sha256':digest(expected)}
        separation = fence.get('resource_separation')
        resources = None
        if separation:
            resources = fence['external']['resource_bindings']
            binding['resource_bindings_sha256'] = digest(resources)
        rows = classify_registered(self.pages('actions/workflows','workflows'),rules,
                                   separation=separation, binding=binding, protected_resources=resources)
        if {w['path'] for w in rows} != set(rules['workflows']):
            raise StateInvalid('AUTHORITY_REGISTERED_DEFINITION_MISMATCH')
        runs = {}
        for status in ('queued','in_progress','waiting','pending','requested'):
            for run in self.pages('actions/runs?status='+status,'workflow_runs'):
                if run.get('status') == 'completed': continue
                key = (run['id'],run['run_attempt'])
                if key in runs and runs[key] != run:
                    raise StateInvalid('AUTHORITY_RUN_INVENTORY_CHANGED')
                runs[key] = run
        if validate_external(self.fence.assert_exclusive(self.repo), self.repo) != protection:
            raise StateInvalid('AUTHORITY_RESOURCE_PROTECTION_CHANGED')
        return {'main_sha':main,'policy_sha256':digest({'policy':rules,'definitions':definitions}),
                'code_sha256':digest(expected),'definitions_valid':True,'inventory_complete':True,
                'runs_complete':True,'workflows':rows,'active_runs':list(runs.values()),
                'external':fence['external'],'key_binding':fence['key_binding'],
                'approved_revision':fence['approved_revision']}

    def review_tree(self, tree, publication, rules):
        """Validate omitted output bytes against immutable service identities."""
        expected, seen = {}, set()
        for row in tree['tree']:
            name = row['path']
            authority_path(name)
            if name in seen:
                raise StateInvalid('AUTHORITY_DUPLICATE_CODE_TREE_ENTRY')
            seen.add(name)
            if row['type'] == 'tree': continue
            if name in rules.get('inert_git_links', {}):
                if (row['type'] != 'blob' or row.get('mode') != '120000'
                        or row['sha'] != _inert_link_sha(name, rules)):
                    raise StateInvalid('AUTHORITY_NONREGULAR_CODE_TREE_FILE')
                expected[name] = row['sha']
                continue
            if row['type'] != 'blob' or row.get('mode') not in {'100644', '100755'}:
                raise StateInvalid('AUTHORITY_NONREGULAR_CODE_TREE_FILE')
            if authority_path(name):
                expected[name] = row['sha']
                continue
            if row['mode'] != '100644':
                raise StateInvalid('AUTHORITY_EXECUTABLE_PUBLICATION_OUTPUT')
            if publication.get(name) == row['sha']: continue
            # Changed publication data need not match an old checkout, but must
            # still be regular validated outputs of the pinned shared contract.
            blob = self.github.request('GET', f'/repos/{self.repo}/git/blobs/{row["sha"]}')
            try:
                if blob['encoding'] != 'base64': raise ValueError('blob encoding')
                raw = base64.b64decode(''.join(blob['content'].split()), validate=True)
                actual = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                if blob['sha'] != row['sha'] or actual != row['sha']:
                    raise ValueError('blob identity')
            except (KeyError, TypeError, ValueError) as exc:
                raise StateInvalid('AUTHORITY_PUBLICATION_BLOB_INVALID') from exc
            _publication_bytes(name, raw)
        return expected

    def pages(self, path, field):
        rows, total = [], None
        separator = '&' if '?' in path else '?'
        for page in range(1,101):
            response = self.github.request('GET',f'/repos/{self.repo}/{path}{separator}per_page=100&page={page}')
            count, batch = response.get('total_count'), response.get(field)
            if type(count) is not int or count < 0 or not isinstance(batch,list) or (total is not None and total != count):
                raise StateInvalid('AUTHORITY_INCOMPLETE_PAGINATION')
            total = count; rows.extend(batch)
            if len({r['id'] for r in rows}) != len(rows):
                raise StateInvalid('AUTHORITY_DUPLICATE_INVENTORY_ENTRY')
            if len(batch) < 100:
                if len(rows) != total: raise StateInvalid('AUTHORITY_INCOMPLETE_INVENTORY')
                return rows
        raise StateInvalid('AUTHORITY_INVENTORY_LIMIT')
