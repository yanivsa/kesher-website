#!/usr/bin/env python3
"""Offline pinned-history checks; no provider, network, GitHub write or merge."""
import argparse
import ast
import collections
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
DOCS = Path(__file__).resolve().parents[1]
PIN = 'c20c3a6ad92f8bac44ac5b8ede7363c414bf4ab2'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def functions(sha, path, names, namespace):
    source = git('show', f'{sha}:{path}').decode()
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert len(nodes) == len(names), (path, names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), namespace)
    return namespace


def flatten(value):
    if isinstance(value, list):
        for row in value:
            yield from flatten(row)
    elif isinstance(value, dict):
        yield value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    data = json.loads((DOCS/'guard-adjudications.json').read_text())
    sources = data['evidence_sources']
    counts = collections.Counter(row['type'] for row in sources.values())
    assert len(data['incidents']) == data['adjudication_summary']['incident_count']
    assert len(sources) == data['adjudication_summary']['evidence_source_count']
    for incident in data['incidents']:
        assert incident['source_ids'], incident['id']
        assert all(key in sources for key in incident['source_ids']), incident['id']
    for key, row in sources.items():
        if row['type'] == 'git_commit':
            assert git('cat-file', '-t', row['sha']).strip() == b'commit', key
        elif row['type'] == 'git_source':
            actual = git('rev-parse', f"{row['sha']}:{row['path']}").decode().strip()
            assert actual == row['blob_sha'], key
            content = git('show', f"{row['sha']}:{row['path']}").decode(errors='replace')
            assert all(symbol in content for symbol in row.get('symbols', [])), key
    if args.cache:
        pulls = {row['number']: row for row in flatten(json.loads((args.cache/'pulls.json').read_text()))}
        comments = {row['id']: row for row in flatten(json.loads((args.cache/'issue-comments.json').read_text()))}
        evolution = {row['number']: row for row in json.loads((args.cache/'pr-evolution.json').read_text())}
        for key, row in sources.items():
            if row['type'] == 'pull_request':
                assert pulls[row['number']]['url'] == row['url'], key
            elif row['type'] == 'issue_comment':
                observed = comments[row['id']]
                assert observed['html_url'] == row['url'] and observed['created_at'] == row['created_at'], key
                assert observed['user']['login'] == row['author'], key
            elif row['type'] == 'force_push_event':
                events = evolution[row['pr_number']]['timelineItems']['nodes']
                assert any(event.get('createdAt') == row['created_at'] and event.get('beforeCommit', {}).get('oid') == row['before_sha']
                           and event.get('afterCommit', {}).get('oid') == row['after_sha'] for event in events), key
    watcher = functions(PIN, '.github/scripts/watch-jules-session.py', {'terminal_output_contract'}, {})
    for outputs in [[], [{'changeSet': {}, 'pullRequest': {}}], [{'pullRequest': {'url': 'https://example.invalid/not-a-pr'}}]]:
        assert watcher['terminal_output_contract']({'outputs': outputs})[0] is True
    namespace = functions(PIN, 'tests/test_master_supervisor_live_qa.py', {'FakePrApi'}, {})
    runtime = functions(PIN, 'scripts/kesher_master_supervisor_live.py', {'_safe_recovery_pr_scope', 'try_finalize_recovery_pr'},
                        {'Any': Any, 'SupervisorError': RuntimeError})
    fake = namespace['FakePrApi']()
    fake.pr_files = lambda number: ['.github/workflows/ci.yml', 'tests/e2e/site.spec.ts']
    assert runtime['try_finalize_recovery_pr'](fake, 900)['merge_sha'] == 'merge-123' and fake.merged
    # Run the exact pinned regression only if its current source is identical.
    for path in ['scripts/kesher_content_controller.py', 'tests/test_kesher_content_controller.py']:
        assert (ROOT/path).read_bytes() == git('show', f'{PIN}:{path}'), path
    subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_kesher_content_controller.ControllerTests.test_github_client_conflict_requires_fresh_reconciliation'], cwd=ROOT, check=True)
    copied = git('show', '6a28a1e196b4db3bb2dfaf97e78b5b01ed35720e:public/images/generated/blog/fights-before-wedding.png')
    original = git('show', '6a28a1e196b4db3bb2dfaf97e78b5b01ed35720e:public/images/generated/blog/first-year-boundaries-origin-families.png')
    assert copied == original + b'\0'
    print(json.dumps({'source_types': dict(counts), 'incidents': len(data['incidents']),
                      'cached_identities_checked': bool(args.cache), 'behavioral_counterexamples': ['G06', 'G08', 'G10'],
                      'committed_regression_passed': 'G09', 'production_outcome': 'NOT_VERIFIED'}))


if __name__ == '__main__':
    main()
