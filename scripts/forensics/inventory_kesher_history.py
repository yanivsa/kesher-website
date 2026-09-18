#!/usr/bin/env python3
"""Read-only, restartable GitHub/Git inventory; never runs production workers.

Raw API responses stay in an explicit external cache. Committed indexes separate
machine-discovered claims/candidates from human-verified forensic conclusions.
Requires authenticated `gh`; no credentials are read or written by this script.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

REPO = "yanivsa/kesher-website"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/forensics/2026-09-autonomous-stabilization"
ANCHORS = {182,239,416,541,542,557,561,583,588,646,659,660,661,680,709,718,
           726,727,728,729,732,735,737,740,741,743,744,745,749,750,751,755,
           760,761,762,763,764,775,777,796,802,804,808,812,814,817,818,822,
           823,824,825,826,827,829,831,832,833,842,843,849,850,851,852,853,
           857,858,859,860,861,863,864,865}
SIGNALS = re.compile(r"controller|supervis|watchdog|notebooklm|youtube|remotion|"
    r"article|short\b|video|hero|content.production|content.pipeline|source.identity|"
    r"media|jules.*(?:repair|health|stall|audit)|automation.gat|workflow.*(?:retry|stale)|"
    r"oauth|invalid_grant|guard.*weaken|axe|accessibility.*(?:disable|rule)", re.I)
UNRELATED = re.compile(r"openclaw|\boci\b|tailscale|wolt|google.ads|booking.tracking", re.I)
PATH_SIGNAL = re.compile(r"(?:controller|supervisor|kesher_|article|youtube|video|short|"
    r"remotion|notebooklm|automation.gates|production.contract|single.scheduler|"
    r"image.worker|image.fallback|jules.*(?:runner|health|policy)|normalize)", re.I)
STAGES = {
    "article": r"article|hero|image|normaliz|post\.json",
    "deployment": r"deploy|prerender|canonical|404|unicode|route",
    "overview": r"video|overview|notebooklm|remotion",
    "short": r"short\b|portrait|9:16",
    "publication": r"youtube|upload|metadata|public.verif|oauth|invalid_grant",
    "control_recovery": r"controller|supervis|state|retry|reconcil|watchdog|jules|workflow",
}
FAMILIES = {
    "identity": r"identity|content.sha|exact.target|same.slug|source.bind|wrong.*(?:item|video|short)",
    "stale_state_cache": r"stale|cache|restor|state.history|artifact",
    "ownership_concurrency": r"scheduler|concurrency|overlap|owner|race|supervisor|controller",
    "deduplication": r"duplicate|dedup|idempot|adopt",
    "bounded_recovery": r"retry|stalled|timeout|exhaust|recovery|backoff",
    "public_completion": r"public|metadata|upload|processing|deploy|404|completion",
    "guard_integrity": r"test|validator|axe|accessibility|quality.gate|policy|contract",
    "auth": r"auth|oauth|scope|403|invalid_grant",
    "product_evolution": r"voice|duration|signature|native.short|outro|overlay",
    "article_image": r"hero|image|unsplash|pexels|deepai|gemini",
}


def command(args: list[str]) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def api(cache: Path, key: str, args: list[str]):
    path = cache / (key + ".json")
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(4):
        try:
            data = json.loads(command(["gh", "api", *args]))
            if isinstance(data, dict) and data.get("errors"):
                raise RuntimeError(str(data["errors"]))
            save(path, data)
            return data
        except subprocess.CalledProcessError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def collect(cache: Path):
    fields = """number title body url createdAt updatedAt closedAt mergedAt state isDraft
      headRefName headRefOid baseRefName author {login} mergeCommit {oid}
      files(first:100) {totalCount pageInfo {hasNextPage endCursor} nodes {path additions deletions}}
      commits(first:100) {totalCount pageInfo {hasNextPage endCursor}
        nodes {commit {oid message committedDate parents(first:2) {nodes {oid}}}}}
      comments {totalCount} reviews {totalCount}
      labels(first:30) {nodes {name}}"""
    pulls, cursor, page, expected = [], None, 1, None
    while True:
        query = "query($cursor:String) {repository(owner:\"yanivsa\",name:\"kesher-website\") {" + \
            "pullRequests(first:40,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}) {" + \
            "totalCount pageInfo {hasNextPage endCursor} nodes {" + fields + "}}}}"
        args = ["graphql", "-f", "query=" + query]
        if cursor:
            args += ["-f", "cursor=" + cursor]
        conn = api(cache, f"pulls-page-{page:03}", args)["data"]["repository"]["pullRequests"]
        pulls.extend(conn["nodes"])
        expected = conn["totalCount"]
        print(f"PR inventory: {len(pulls)}/{expected}", flush=True)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor, page = conn["pageInfo"]["endCursor"], page + 1
    assert len({p['number'] for p in pulls}) == expected, "PR pagination incomplete"
    for pr in pulls:
        for connection, selection in [
            ("files", "path additions deletions"),
            ("commits", "commit {oid message committedDate parents(first:2) {nodes {oid}}}")]:
            value, extra = pr[connection], 1
            while value["pageInfo"]["hasNextPage"]:
                query = ('query($cursor:String) {repository(owner:"yanivsa",name:"kesher-website") {'
                    + f'pullRequest(number:{pr["number"]}) ' + '{'
                    + connection + '(first:100,after:$cursor) {'
                    + 'pageInfo {hasNextPage endCursor} nodes {' + selection + '}}}}}')
                chunk = api(cache, f"pr-{pr['number']}-{connection}-{extra}",
                    ["graphql", "-f", "query=" + query, "-f", "cursor=" + value['pageInfo']['endCursor']])
                more = chunk['data']['repository']['pullRequest'][connection]
                value['nodes'].extend(more['nodes'])
                value['pageInfo'] = more['pageInfo']
                extra += 1
            assert len(value['nodes']) == value['totalCount'], f"incomplete {pr['number']} {connection}"
    save(cache / "pulls.json", pulls)
    issues = []
    for page in range(1, 10000):
        rows = api(cache, f"issues-page-{page:03}",
                   [f"repos/{REPO}/issues?state=all&sort=created&direction=asc&per_page=100&page={page}"])
        issues.extend(i for i in rows if 'pull_request' not in i)
        if len(rows) < 100:
            break
    save(cache / "issues.json", issues)
    for name, endpoint in [
        ("issue-comments", "issues/comments"), ("review-comments", "pulls/comments"),
        ("workflows", "actions/workflows"), ("branches", "branches")]:
        pages = api(cache, name, [f"repos/{REPO}/{endpoint}?per_page=100", "--paginate", "--slurp"])
        print(f"Collected {name}: {len(pages)} pages", flush=True)
    history = command(["git", "log", "--all", "--date=iso-strict", "--format=%x1e%H%x1f%aI%x1f%P%x1f%s", "--name-only"])
    (cache / "git-history.txt").write_text(history)
    (cache / "refs.txt").write_text(command(["git", "show-ref"]))
    (cache / "deleted-paths.txt").write_text(command(["git", "log", "--all", "--diff-filter=D", "--format=%H %aI %s", "--name-only"]))
    save(cache / "capture.json", {"captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
         "repository": REPO, "main_sha": command(["git", "rev-parse", "origin/main"]).strip(),
         "pull_requests": len(pulls), "issues": len(issues),
         "git_commits": len(history.split('\x1e')) - 1})


def flatten(cache: Path, name: str):
    return [row for page in json.loads((cache / (name + '.json')).read_text()) for row in page]


def build(cache: Path):
    pulls = json.loads((cache / 'pulls.json').read_text())
    issues = json.loads((cache / 'issues.json').read_text())
    comments = flatten(cache, 'issue-comments') + flatten(cache, 'review-comments')
    by_number = {}
    for c in comments:
        url = c.get('issue_url', c.get('pull_request_url', ''))
        if url:
            by_number.setdefault(int(url.rsplit('/', 1)[-1]), []).append(c)
    rows, excluded = [], []
    for kind, records in [('pull_request', pulls), ('issue', issues)]:
        for record in records:
            n = record['number']
            files = [f['path'] for f in record.get('files', {}).get('nodes', [])]
            commits = [c['commit'] for c in record.get('commits', {}).get('nodes', [])]
            text = '\n'.join([record['title'], record.get('body') or '', *files,
                              *(c['message'] for c in commits),
                              *(c.get('body') or '' for c in by_number.get(n, []))])
            matches = sorted(set(m.group(0).lower() for m in SIGNALS.finditer(text)))
            scoped_files = [f for f in files if PATH_SIGNAL.search(f) and not UNRELATED.search(f)]
            scope = n in ANCHORS or bool(scoped_files) or bool(matches and not UNRELATED.search(record['title']))
            if not scope:
                excluded.append({'kind': kind, 'number': n, 'title': record['title'],
                                 'reason': 'No primary pipeline signal, or unrelated infrastructure title without pipeline files'})
                continue
            body = record.get('body') or ''
            claim_lines = [l for l in body.splitlines() if re.search(r'caus|because|previous|fix|fail|prevent|bug|stale|incorrect', l, re.I)]
            rows.append({
                'kind': kind, 'number': n, 'date': record.get('createdAt', record.get('created_at')),
                'title': record['title'], 'url': record.get('url') if kind == 'pull_request' else record.get('html_url'),
                'state': record['state'], 'merged_at': record.get('mergedAt'), 'draft': record.get('isDraft', False),
                'stage': [key for key, pattern in STAGES.items() if re.search(pattern, text, re.I)],
                'symptom': {'claim': record['title'], 'confidence': 'UNKNOWN', 'basis': 'title; awaits incident review'},
                'root_cause_claim': {'excerpts': claim_lines[:12], 'confidence': 'UNKNOWN', 'basis': 'author claim; not independently proven'},
                'affected_files': files, 'controllers_workflows': [f for f in files if 'workflow' in f or 'controller' in f or 'supervisor' in f],
                'regression_tests': {'candidate_files': [f for f in files if 'test' in f.lower() or 'spec' in f.lower()], 'added_verified': None},
                'later_behavior_changed_by': [], 'recurrence_verified': None,
                'failure_family_candidates': [key for key, pattern in FAMILIES.items() if re.search(pattern, text, re.I)],
                'related_incident_ids': sorted({int(v) for v in re.findall(r'(?:#|/(?:issues|pull)/)(\d+)\b', text)} - {n}),
                'current_relevance': 'UNKNOWN: pending contract and runtime reconciliation',
                'commits': [{'sha': c['oid'], 'date': c['committedDate'], 'subject': c['message'].splitlines()[0]} for c in commits],
                'comment_count': len(by_number.get(n, [])), 'discovery_signals': matches, 'review_status': 'indexed_not_adjudicated',
            })
    rows.sort(key=lambda r: (r['date'], r['number']))
    for row in rows:
        paths = set(row['controllers_workflows'])
        row['later_same_file_candidates'] = [other['number'] for other in rows
            if other['date'] > row['date'] and paths.intersection(other['controllers_workflows'])]
    capture = json.loads((cache / 'capture.json').read_text())
    save(OUT / 'incident-index.json', {'schema_version': 1, 'capture': capture,
        'method': 'Complete PR and Issue pagination; title/body/individual-commit message/changed-path/comment scope discovery. Candidate links are not proven causality.',
        'incidents': rows})
    save(OUT / 'scope-exclusions.json', {'schema_version': 1, 'records': excluded})
    save(OUT / 'coverage.json', {**capture, 'indexed_records': len(rows), 'excluded_records': len(excluded),
         'issue_and_review_comments': len(comments), 'deep_review_complete': False,
         'known_limits': ['Issue/PR index is complete discovery, not completed incident adjudication.',
             'Actions run inventory and unavailable log/artifact accounting are separate pending passes.',
             'Deleted remote branches are represented only where retained Git objects or PR commits remain.',
             'Same-file and keyword links are candidates, not claims of recurrence or root cause.'],
         'raw_capture_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cache.glob('*.json'))}})
    (OUT / 'README.md').write_text('# KESHER autonomous stabilization forensics\n\n'
        'Status: inventory in progress; no production-stability claim.\n\n'
        '`incident-index.json` contains every discovered pipeline-related PR/Issue, including closed/unmerged and draft work. '
        '`scope-exclusions.json` makes exclusions reviewable. UNKNOWN and null fields explicitly require adjudication. '
        'Keyword, file-overlap, and author-claim evidence must not be promoted to proven root causes.\n\n'
        'Reproduce using `python3 scripts/forensics/inventory_kesher_history.py --cache <private-cache> collect` '
        'then `... build`. A fresh directory produces a fresh snapshot; an existing cache resumes that snapshot. '
        'Raw API data remains outside Git. No generation, upload, repair session, workflow dispatch, or secret access occurs.\n')
    print(json.dumps({'indexed': len(rows), 'excluded': len(excluded), 'coverage': capture}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('command', choices=['collect', 'build'])
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    {'collect': collect, 'build': build}[args.command](args.cache)
