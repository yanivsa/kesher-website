#!/usr/bin/env python3
"""Reject newly introduced date/slug/PR-specific rescue workflows.

Reviewed historical exceptions are immutable by hash and remain subject to the
separate authority policy. An exception never grants dispatch or write authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

DATED = re.compile(r'(?:^|[-_])20\d{6}(?:[-_]|\.ya?ml$)')
EXACT_PR = re.compile(r'(?:^|[-_])(?:pr|pull-request)[-_]?\d+(?:[-_.]|$)')
EXACT_SLUG = re.compile(r'(?:^|-)exact-(?:[a-z0-9]+-)+[a-z0-9]+\.ya?ml$')


def check(root):
    root = Path(root)
    reviewed = json.loads((root/'config/kesher-workflow-governance.json').read_text())['grandfathered']
    failures=[]
    for path in sorted((root/'.github/workflows').glob('*.y*ml')):
        if not (DATED.search(path.name) or EXACT_SLUG.search(path.name) or EXACT_PR.search(path.name)):
            continue
        relative=str(path.relative_to(root))
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != reviewed.get(relative):
            failures.append(relative)
    return failures


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args()
    failures=check(args.root)
    print(json.dumps({'failure_class':'ONE_OFF_RECOVERY_WORKFLOW_FORBIDDEN' if failures else None,'paths':failures}))
    return 1 if failures else 0

if __name__=='__main__':raise SystemExit(main())
