#!/usr/bin/env python3
"""Inspect failed pipeline runs, retries and referenced/representative outcomes.

Selection spans the complete retained run index. Raw logs remain private; the
durable index records failed steps, machine error codes, availability and hashes.
"""
import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

from inventory_kesher_history import OUT, REPO, ROOT, api, save

PIPELINE = re.compile(
    r'/(?:kesher-|(?:auto-merge|normalize|repair|auto-close-stale)-article|jules-(?:weekday|weekend)-article'
    r'|apply-(?:controller|keep-video|single-scheduler-video|video|weekend-video)|article-video|goal-e2e'
    r'|one-off-fix-article|one-time-(?:dispatch-missing-article|repair-missing-hero)'
    r'|s3-(?:pr802|v5)|tmp-(?:fix-pr763|repair-pr-(?:582|616)|video-overview)'
    r'|trigger-jules-article|youtube-oauth)')


def selected_runs(cache):
    rows = [json.loads(line) for line in gzip.decompress((OUT / 'workflow-run-index.jsonl.gz').read_bytes()).splitlines()]
    scope = json.loads((OUT / 'incident-index.json').read_text())
    scoped_prs = {i['number'] for i in scope['incidents'] if i['kind'] == 'pull_request'}
    prs = [p for p in json.loads((cache / 'pulls.json').read_text()) if p['number'] in scoped_prs]
    branches = {p['headRefName'] for p in prs}
    shas = {p['headRefOid'] for p in prs}
    shas.update(p['mergeCommit']['oid'] for p in prs if p.get('mergeCommit'))
    shas.update(c['commit']['oid'] for p in prs for c in p['commits']['nodes'])
    relevant = [r for r in rows if PIPELINE.search(r['path']) or (
        r['path'] in {'.github/workflows/ci.yml', '.github/workflows/deploy.yml'}
        and (r['head_sha'] in shas or r['head_branch'] in branches))]
    references = set()
    for name in ('pulls', 'issues', 'issue-comments', 'review-comments'):
        records = json.loads((cache / (name + '.json')).read_text())
        if records and isinstance(records[0], list):
            records = [r for page in records for r in page]
        for record in records:
            references.update(int(n) for n in re.findall(r'/actions/runs/(\d+)', record.get('body') or ''))
    selected = {}
    groups = collections.defaultdict(list)
    for row in relevant:
        reason = []
        if row['conclusion'] in ('failure', 'timed_out', 'startup_failure', 'cancelled', 'skipped'):
            reason.append('every_failed_cancelled_or_skipped_pipeline_run')
        if (row.get('run_attempt') or 1) > 1:
            reason.append('every_retried_pipeline_run')
        if row['id'] in references:
            reason.append('explicit_historical_reference')
        if reason:
            selected[row['id']] = {**row, 'selection_reasons': reason}
        groups[(row['path'], row['event'], row['conclusion'])].append(row)
    for group in groups.values():
        for row in (group[0], group[-1]):
            selected.setdefault(row['id'], {**row, 'selection_reasons': []})['selection_reasons'].append('first_or_last_workflow_event_outcome')
    for row in rows:
        if row['id'] in references:
            selected.setdefault(row['id'], {**row, 'selection_reasons': ['explicit_historical_reference']})
    return sorted(selected.values(), key=lambda r: (r['created_at'], r['id'])), len(relevant), references


def inspect_run(cache, run):
    rid = run['id']
    target = cache / f'run-evidence-{rid}.json'
    if target.exists():
        return {**json.loads(target.read_text()), 'selection_reasons': run['selection_reasons']}
    result = {**run, 'attempts': [], 'artifacts': [], 'availability_errors': []}
    for attempt in range(1, (run.get('run_attempt') or 1) + 1):
        try:
            pages = api(cache, f'run-{rid}-attempt-{attempt}-jobs',
                [f'repos/{REPO}/actions/runs/{rid}/attempts/{attempt}/jobs?per_page=100', '--paginate', '--slurp'])
            jobs = [j for p in pages for j in p['jobs']]
            result['attempts'].append({'attempt': attempt, 'jobs': [
                {k: job.get(k) for k in ('id', 'name', 'status', 'conclusion', 'started_at', 'completed_at', 'steps', 'html_url')}
                for job in jobs]})
        except (subprocess.CalledProcessError, ValueError, KeyError):
            result['availability_errors'].append(f'jobs_attempt_{attempt}_unavailable')
    try:
        pages = api(cache, f'run-{rid}-artifacts',
                    [f'repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100', '--paginate', '--slurp'])
        result['artifacts'] = [{k: a.get(k) for k in ('id', 'name', 'expired', 'size_in_bytes', 'created_at', 'expires_at')}
                               for page in pages for a in page['artifacts']]
    except (subprocess.CalledProcessError, ValueError, KeyError):
        result['availability_errors'].append('artifact_listing_unavailable')
    proc = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/runs/{rid}/logs'], cwd=ROOT, capture_output=True)
    if proc.returncode:
        result['availability_errors'].append('logs_unavailable')
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(proc.stdout)) as archive:
                texts = [(n, archive.read(n).decode('utf-8', errors='replace')) for n in archive.namelist() if not n.endswith('/')]
            codes, exceptions = set(), set()
            for name, text in texts:
                codes.update(re.findall(r'\b(?:KESHER|VIDEO|SHORT|ARTICLE|YOUTUBE|NOTEBOOKLM|JULES|GITHUB|MASTER|REMOTION|IMAGE|SOURCE|UPLOAD|PROVIDER|AUTH)_[A-Z][A-Z0-9_]{2,}\b', text))
                exceptions.update(re.findall(r'\b[A-Za-z]+(?:Error|Exception):', text))
            raw = '\n'.join('\nFILE ' + n + '\n' + text for n, text in texts).encode()
            logs_path = cache / 'logs' / f'{rid}.txt.gz'
            logs_path.parent.mkdir(exist_ok=True)
            logs_path.write_bytes(gzip.compress(raw, mtime=0))
            result['logs'] = {'available': True, 'archive_sha256': hashlib.sha256(proc.stdout).hexdigest(),
                'text_sha256': hashlib.sha256(raw).hexdigest(), 'files': [n for n, _ in texts],
                'code_candidates': sorted(codes), 'exception_types': sorted(exceptions),
                'note': 'Codes also appear in echoed scripts; a match alone does not prove the executed failure.'}
        except zipfile.BadZipFile:
            result['availability_errors'].append('logs_archive_invalid')
    save(target, result)
    return result


def main(cache, max_new_runs=None):
    selected, relevant_count, references = selected_runs(cache)
    print(f'Inspecting {len(selected)} runs from {relevant_count} pipeline runs', flush=True)
    cached = [row for row in selected if (cache / f"run-evidence-{row['id']}.json").exists()]
    missing = [row for row in selected if not (cache / f"run-evidence-{row['id']}.json").exists()]
    missing.sort(key=lambda row: (row['conclusion'] in {'skipped', 'cancelled'}, row['created_at'], row['id']))
    batch = missing if max_new_runs is None else missing[:max_new_runs]
    pending = missing[len(batch):]
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(inspect_run, cache, row) for row in cached + batch]
        for completed in concurrent.futures.as_completed(futures):
            records.append(completed.result())
            if len(records) % 50 == 0:
                print(f'Run evidence {len(records)}/{len(selected)}', flush=True)
    records.sort(key=lambda r: (r['created_at'], r['id']))
    data = ''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in records).encode()
    (OUT / 'workflow-run-evidence.jsonl.gz').write_bytes(gzip.compress(data, mtime=0))
    save(OUT / 'workflow-run-evidence-coverage.json', {
        'pipeline_runs': relevant_count, 'inspected_runs': len(records),
        'selected_runs': len(selected), 'pending_run_ids': [row['id'] for row in pending],
        'selection': ['Every failed/timed-out/startup-failed/cancelled/skipped pipeline run', 'Every retried pipeline run',
            'Every referenced run present in the captured run index', 'First/last of each workflow/event/conclusion combination'],
        'pipeline_scope': 'Pipeline definitions including historical one-off mutators; shared CI/deploy runs only when bound by SHA or branch to an indexed scope-candidate PR',
        'referenced_runs_not_retained_in_index': sorted(references - {r['id'] for r in records}),
        'logs_available': sum(bool(r.get('logs')) for r in records),
        'availability_errors': dict(collections.Counter(e for r in records for e in r['availability_errors'])),
        'limitations': ['Expired/deleted logs and artifacts cannot be reconstructed.',
            'Step summaries are not exposed by the REST jobs API; logs and retained artifacts are recorded separately.',
            'Machine code matches are candidates until executed lines are reviewed.']})
    print(f'Finished {len(records)} run evidence records', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--max-new-runs', type=int, help='Bound a batch to stay within API allowance; later runs resume cached work')
    args = parser.parse_args()
    main(args.cache, args.max_new_runs)
