#!/usr/bin/env python3
"""Read-only state/artifact capture: persist JSON evidence, never auth files."""
import argparse
import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from inventory_kesher_history import OUT, REPO, ROOT, api, save


def main(cache):
    manifest = {'state_stores': [], 'artifact_snapshots': [], 'failures': []}
    for label, ref, path in [
        ('controller', 'automation-state', '.kesher-controller/state.json'),
        ('supervisor', 'automation-supervisor-state', '.kesher-master-supervisor/state.json')]:
        response = api(cache, 'live-' + label, [f'repos/{REPO}/contents/{path}?ref={ref}'])
        state = json.loads(base64.b64decode(response['content']))
        save(cache / f'state-{label}.json', state)
        manifest['state_stores'].append({'name': label, 'ref': ref, 'path': path,
            'blob_sha': response['sha'], 'schema_version': state.get('schema_version'),
            'cycle': state.get('cycle'), 'status': state.get('status'), 'updated_at': state.get('updated_at'),
            'incident_count': len(state.get('incidents', {})), 'command_count': len(state.get('commands', {}))})
    for name in ['kesher-video-state', 'kesher-short-v4-state']:
        response = api(cache, 'live-artifacts-' + name,
                       [f'repos/{REPO}/actions/artifacts?name={name}&per_page=100', '--paginate', '--slurp'])
        rows = [r for p in response for r in p['artifacts'] if not r['expired']]
        rows.sort(key=lambda r: r['created_at'], reverse=True)
        for row in rows[:3]:
            aid = row['id']
            target = cache / f'artifact-{aid}-states.json'
            if target.exists():
                states = json.loads(target.read_text())
            else:
                proc = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{aid}/zip'],
                                      cwd=ROOT, capture_output=True, check=False)
                if proc.returncode:
                    manifest['failures'].append({'artifact_id': aid, 'reason': 'archive_download_failed'})
                    continue
                with zipfile.ZipFile(io.BytesIO(proc.stdout)) as archive:
                    states = {n: json.loads(archive.read(n)) for n in archive.namelist()
                              if n.rsplit('/', 1)[-1] == 'state.json'}
                save(target, states)
            for path, state in states.items():
                manifest['artifact_snapshots'].append({'name': name, 'artifact_id': aid,
                    'created_at': row['created_at'], 'workflow_run': row.get('workflow_run'),
                    'state_path': path, 'state_sha256': hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
                    'items': [{'id': i.get('id'), 'media_kind': i.get('media_kind', i.get('kind')),
                               'source_slug': (i.get('source') or {}).get('slug'),
                               'source_content_sha256': (i.get('source') or {}).get('content_sha256'),
                               'status': i.get('status'), 'uploaded': i.get('uploaded'),
                               'youtube_id': i.get('youtube_id'), 'youtube_url': i.get('youtube_url'),
                               'technical_verified': i.get('technical_verified')}
                              for i in state.get('items', []) if isinstance(i, dict)]})
    save(OUT / 'live-evidence-manifest.json', manifest)
    print(json.dumps({'stores': manifest['state_stores'],
        'artifact_snapshots': len(manifest['artifact_snapshots']), 'failures': manifest['failures']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    main(args.cache)
