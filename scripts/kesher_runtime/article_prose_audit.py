"""Report-only Hebrew prose audit for the exact trusted article candidate.

This module intentionally never decides publication validity. It reuses the
already bound canonical candidate, invokes the trusted local Node heuristic,
and emits GitHub-friendly evidence. Any audit/runtime failure is reported as
unavailable and returns success so editorial heuristics cannot block delivery.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = ROOT / 'scripts/hebrew-prose-audit.cjs'
VALID_RISKS = {'low', 'watch', 'medium', 'high'}


def _run_prose_audit(post, runner=None):
    if runner is None:
        runner = subprocess.run
    try:
        completed = runner(
            ['node', str(AUDIT_SCRIPT), '--post-stdin', '--format=json'],
            input=json.dumps(post, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            cwd=ROOT,
        )
        if completed.returncode != 0:
            raise ValueError('audit process failed')
        payload = json.loads(completed.stdout)
        if (not isinstance(payload, dict)
                or payload.get('risk') not in VALID_RISKS
                or type(payload.get('riskPoints')) is not int
                or not isinstance(payload.get('findings'), list)
                or not isinstance(payload.get('advisories'), list)):
            raise ValueError('audit output invalid')
        return {'status': 'ok', **payload}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        return {'status': 'unavailable', 'risk': 'unknown', 'reason': type(exc).__name__}


def _emit(result):
    print('ARTICLE_PROSE_AUDIT:' + json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    if result.get('status') != 'ok':
        print('::warning title=Hebrew prose audit::report-only audit unavailable; publication is unaffected')
        return
    categories = sorted({str(item.get('category', '')) for item in result.get('findings', []) if item.get('category')})
    suffix = ','.join(categories) if categories else 'none'
    print(f"::notice title=Hebrew prose audit::risk={result['risk']}; findings={suffix}; report-only")


def report_candidate(command_id):
    try:
        from .article_validation import GitArticleCandidate, _candidate
        from .worker_entry import actions_admission

        context = actions_admission(command_id, attach=True).context
        git = GitArticleCandidate(Path.cwd())
        _, value, _ = _candidate(context, context.store.github, git, require_saved=True)
        result = _run_prose_audit(value['post'])
    except Exception as exc:  # Report-only boundary: never convert an editorial signal into a gate.
        result = {'status': 'unavailable', 'risk': 'unknown', 'reason': type(exc).__name__}
    _emit(result)
    return result


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or not args[0]:
        _emit({'status': 'unavailable', 'risk': 'unknown', 'reason': 'InvalidCommand'})
        return 0
    try:
        report_candidate(args[0])
    except Exception as exc:  # Last-resort report-only boundary.
        _emit({'status': 'unavailable', 'risk': 'unknown', 'reason': type(exc).__name__})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
