#!/usr/bin/env python3
"""Inventory trigger/side-effect candidates without evaluating workflow code."""
import json
import re
from pathlib import Path

import yaml

from inventory_kesher_history import OUT, ROOT, save


def main():
    records = []
    for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
        source = path.read_text()
        data = yaml.safe_load(source)
        triggers = data.get('on', data.get(True, {}))
        jobs = []
        for job_id, job in data.get('jobs', {}).items():
            commands = '\n'.join(str(s.get('run', '')) for s in job.get('steps', []))
            jobs.append({'id': job_id, 'if': job.get('if'), 'needs': job.get('needs'),
                'permissions': job.get('permissions'), 'concurrency': job.get('concurrency'),
                'checkout_refs': [s.get('with', {}).get('ref', '<event-default>')
                    for s in job.get('steps', []) if str(s.get('uses', '')).startswith('actions/checkout@')],
                'executed_scripts': sorted(set(re.findall(r'(?:scripts|\.github/scripts)/[\w./-]+\.(?:py|mjs|cjs|js|sh)', commands))),
                'dispatch_targets': sorted(set(re.findall(r'[\w-]+\.yml', commands))),
                'side_effect_candidates': [name for name, pattern in {
                    'git_push': r'git push', 'pr_write': r'gh pr (?:create|merge|close|edit|comment)',
                    'issue_write': r'gh issue (?:create|close|edit|comment)',
                    'workflow_dispatch': r'gh workflow run|/dispatches|dispatch_workflow',
                    'api_write': r'POST|PATCH|PUT|DELETE', 'deployment': r'wrangler|pages deploy',
                    'artifact_write': r'upload-artifact', 'cache_restore': r'actions/cache|download-artifact',
                }.items() if re.search(pattern, commands + '\n' + json.dumps(job))],
                'env_names': sorted(job.get('env', {}).keys()),
            })
        records.append({'path': str(path.relative_to(ROOT)), 'name': data.get('name'),
            'triggers': triggers, 'permissions': data.get('permissions'),
            'concurrency': data.get('concurrency'), 'jobs': jobs,
            'authority_verdict': 'UNKNOWN: static discovery requires transitive script and live-mode review'})
    save(OUT / 'workflow-authority-index.json', {'schema_version': 1, 'workflows': records})
    print(f'Indexed {len(records)} current workflow definitions')


if __name__ == '__main__':
    main()
