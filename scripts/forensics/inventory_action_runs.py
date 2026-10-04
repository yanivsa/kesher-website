#!/usr/bin/env python3
"""Capture every retained Actions run using bounded creation-time partitions.

GitHub limits filtered run searches to 1,000 results. Split dense intervals;
assert unique counts and write coverage instead of silently accepting truncation.
"""
import argparse
import collections
import datetime as dt
import gzip
import json
from pathlib import Path

from inventory_kesher_history import OUT, REPO, ROOT, api, save

FIELDS = ('id', 'name', 'path', 'run_number', 'run_attempt', 'event', 'status',
          'conclusion', 'created_at', 'updated_at', 'run_started_at', 'head_branch',
          'head_sha', 'display_title', 'html_url', 'workflow_id')


def stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def interval(cache, start, end, partitions):
    key = f"runs-{start:%Y%m%dT%H%M%S}-{end:%Y%m%dT%H%M%S}"
    endpoint = f"repos/{REPO}/actions/runs?per_page=100&created={stamp(start)}..{stamp(end)}"
    first = api(cache, key + '-001', [endpoint])
    count = first['total_count']
    if count > 1000:
        midpoint = start + dt.timedelta(seconds=int((end-start).total_seconds()//2))
        if midpoint >= end:
            raise RuntimeError('Cannot partition dense single-second interval')
        return (interval(cache, start, midpoint, partitions) +
                interval(cache, midpoint + dt.timedelta(seconds=1), end, partitions))
    rows = first['workflow_runs']
    for page in range(2, (count + 99)//100 + 1):
        rows.extend(api(cache, key + f'-{page:03}', [endpoint + f'&page={page}'])['workflow_runs'])
    unique = {row['id']: row for row in rows}
    if len(unique) != count:
        raise RuntimeError(f'Incomplete run interval {key}: {len(unique)}/{count}')
    partitions.append({'start': stamp(start), 'end': stamp(end), 'expected': count, 'captured': len(unique)})
    print(f"Actions {stamp(start)} .. {stamp(end)}: {len(unique)}", flush=True)
    return [{field: row.get(field) for field in FIELDS} for row in unique.values()]


def main(cache):
    repo = api(cache, 'repository', [f'repos/{REPO}'])
    snapshot_file = cache / 'actions-snapshot.json'
    if not snapshot_file.exists():
        save(snapshot_file, {'cutoff': stamp(dt.datetime.now(dt.timezone.utc))})
    cutoff = json.loads(snapshot_file.read_text())['cutoff']
    start, end = [dt.datetime.fromisoformat(v.replace('Z', '+00:00')) for v in [repo['created_at'], cutoff]]
    partitions = []
    rows = interval(cache, start, end, partitions)
    assert len(rows) == len({r['id'] for r in rows})
    rows.sort(key=lambda r: (r['created_at'], r['id']))
    OUT.mkdir(parents=True, exist_ok=True)
    data = ''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in rows).encode()
    (OUT / 'workflow-run-index.jsonl.gz').write_bytes(gzip.compress(data, mtime=0))
    workflows = collections.defaultdict(list)
    for row in rows:
        workflows[row['path']].append(row)
    summary = []
    for path, runs in sorted(workflows.items()):
        clean_path = path.split('@')[0]
        summary.append({'path': path, 'present_on_capture_main': (ROOT / clean_path).is_file(),
            'runs': len(runs), 'first': runs[0]['created_at'], 'last': runs[-1]['created_at'],
            'conclusions': dict(collections.Counter(r['conclusion'] for r in runs)),
            'events': dict(collections.Counter(r['event'] for r in runs)),
            'retried_runs': [r['id'] for r in runs if (r.get('run_attempt') or 1) > 1],
            'latest_run_id': runs[-1]['id']})
    save(OUT / 'workflow-run-coverage.json', {'cutoff': cutoff, 'total_retained_runs': len(rows),
        'partitions': partitions, 'workflows': summary,
        'limitations': ['Only GitHub-retained runs can be enumerated. Deleted runs are unavailable.',
            'Run attempts record the latest attempt; attempt job/log evidence is collected separately.',
            'An API workflow marked active does not imply its file remains on main or its trigger can mutate.']})
    print(f"Captured {len(rows)} unique runs across {len(summary)} workflow paths", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    main(args.cache)
