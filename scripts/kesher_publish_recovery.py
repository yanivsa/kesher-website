#!/usr/bin/env python3
"""Bounded, exact-identity recovery for the single KESHER publisher queue.

Only the existing controller schedules retries. Receipts come from the exact
main-branch publisher run, not from an arbitrary workflow, title or artifact.
No media or article creation occurs in this coordinator.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import zipfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.kesher_cloud_publisher import GitHubActionsClient

WORKFLOW = 'kesher-publish-request.yml'
WORKFLOW_PATH = '.github/workflows/' + WORKFLOW
ACTIVE = {'queued', 'in_progress', 'waiting', 'requested', 'pending'}
MAX_RETRIES = 3
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
SHA = re.compile(r'[0-9a-f]{64}')
ID = re.compile(r'[1-9][0-9]*')
ISSUE_TITLE = re.compile(r'^Kesher Publish from Issue #([1-9][0-9]*):')
RECOVERY_TITLE = re.compile(r'^Kesher Publish recovery #([1-9][0-9]*)$')


def api(repo, endpoint, *, raw=False):
    args = ['gh', 'api']
    if raw:
        args += ['-H', 'Accept: application/vnd.github.raw+json']
    args.append(f'/repos/{repo}/{endpoint}')
    return json.loads(subprocess.check_output(args, text=True, timeout=45))


def valid_run(run):
    return (run.get('path', '').split('@')[0] == WORKFLOW_PATH
            and run.get('head_branch') == 'main'
            and run.get('status') == 'completed'
            and run.get('event') in {'issues', 'workflow_dispatch'})


def read_receipt(client, run):
    if not valid_run(run):
        raise ValueError('RECOVERY_RUN_NOT_TRUSTED')
    run_id = int(run['id'])
    try:
        data = client.get_run_artifact_zip(run_id, f'kesher-publish-result-{run_id}')
    except RuntimeError as exc:
        if str(exc).startswith('ARTIFACT_NOT_FOUND:'):
            return None
        raise
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo('kesher-publish-result.json')
        if info.file_size > 1024 * 1024:
            raise ValueError('RECOVERY_RECEIPT_TOO_LARGE')
        receipt = json.loads(archive.read(info))
    if not isinstance(receipt, dict):
        raise ValueError('RECOVERY_RECEIPT_INVALID')
    return receipt



def unstarted_receipt(run, jobs, issue_for):
    """Recover only a root whose mutating publisher step provably never ran."""
    if not valid_run(run) or run.get('conclusion') not in {'failure', 'cancelled', 'timed_out'}:
        return None
    if run.get('run_attempt', 1) != 1 or jobs.get('total_count') != len(jobs.get('jobs', [])):
        return None
    for job in jobs['jobs']:
        steps = job.get('steps') or []
        publisher = [step for step in steps if step.get('name') == 'Execute Kesher Cloud Publisher']
        if not publisher or any(step.get('conclusion') != 'skipped' for step in publisher):
            return None
    title = run.get('display_title', '')
    data = dict(request_root=str(run['id']), request_issue='', recovery_attempt=0,
                status='error', contract_complete=False, dry_run=False, stage_only=False)
    daily = re.fullmatch(r'Kesher Publish \(daily\) - (\d{4}-\d{2}-\d{2})', title)
    # Without a receipt, the dispatch inputs are unavailable. Only the
    # existing scheduler's bot dispatch is known to be live, not a manual
    # dry-run or staging request with the same run name.
    if run.get('event') == 'workflow_dispatch' and daily and (run.get('actor') or {}).get('login') == 'github-actions[bot]':
        return dict(data, action='daily', slot=daily.group(1))
    match = ISSUE_TITLE.match(title)
    if run.get('event') != 'issues' or not match:
        return None
    issue = issue_for(int(match.group(1)))
    if issue.get('state') != 'open' or issue.get('author_association') not in {'OWNER', 'MEMBER', 'COLLABORATOR'}:
        return None
    # Same single-line fields accepted by IssueOps. A changed issue is not
    # replayed without its original checkpoint.
    if issue.get('updated_at', '') > run.get('created_at', ''):
        return None
    topic = re.sub(r'^\[publish\]\s*|^publish:\s*|^הפעלת פרסום:\s*', '', issue.get('title', ''), flags=re.I).strip()
    action = 'run_now'
    slot = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Jerusalem')).date().isoformat()
    payload = dict(topic_brief=topic, idea_id='', primary_keyword='')
    for line in (issue.get('body') or '').splitlines():
        key, sep, value = line.partition(':')
        key, value = key.strip().lower(), value.strip()
        if not sep:
            continue
        if key == 'action':
            action = value
        elif key == 'slot':
            slot = value
        elif key in {'stage_only', 'dry_run'} and value.lower() == 'true':
            return None
        elif key in {'topic_brief', 'topic', 'brief'} and value:
            payload['topic_brief'] = value
        elif key in {'idea_id', 'slug'}:
            payload['idea_id'] = value
        elif key in {'primary_keyword', 'keyword'}:
            payload['primary_keyword'] = value
    if action != 'run_now' or not payload['topic_brief']:
        return None
    return dict(data, action=action, slot=slot, request_issue=match.group(1), request_payload=payload)


def complete_receipt(data, *, issue=None):
    """Never close an Issue on dry run, staging, missing links or false completion."""
    if not isinstance(data, dict) or data.get('contract_complete') is not True:
        return False
    if data.get('status') not in {'success', 'already_complete'} or data.get('action') not in {'daily', 'run_now', 'resume'}:
        return False
    if data.get('stage_only') is not False or data.get('dry_run') is not False:
        return False
    if issue is not None and str(data.get('request_issue', '')) != str(issue):
        return False
    slug = data.get('slug')
    source = data.get('source_sha256')
    if not isinstance(slug, str) or not SLUG.fullmatch(slug) or not isinstance(source, str) or not SHA.fullmatch(source):
        return False
    if data.get('article_url') != f'https://kesher.saharoni.com/blog/{slug}':
        return False
    long = re.fullmatch(r'https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})', str(data.get('long_video_url', '')))
    short = re.fullmatch(r'https://www\.youtube\.com/shorts/([A-Za-z0-9_-]{11})', str(data.get('short_video_url', '')))
    return bool(long and short and long.group(1) != short.group(1))


def retry_identity(receipt, run, lookup_run):
    """Verify lineage, reject legacy/incomplete identity, cap automatic retries."""
    if not isinstance(receipt, dict) or receipt.get('action') not in {'daily', 'run_now', 'resume'}:
        return None
    if receipt.get('dry_run') is not False or receipt.get('stage_only') is not False:
        return None
    root = str(receipt.get('request_root', ''))
    issue = str(receipt.get('request_issue', ''))
    attempt = receipt.get('recovery_attempt')
    slug = str(receipt.get('slug', ''))
    sha = str(receipt.get('source_sha256', ''))
    slot = str(receipt.get('slot', ''))
    if not ID.fullmatch(root) or (issue and not ID.fullmatch(issue)) or type(attempt) is not int or not 0 <= attempt < MAX_RETRIES:
        return None
    try:
        if datetime.strptime(slot, '%Y-%m-%d').date().isoformat() != slot:
            return None
    except ValueError:
        return None
    payload = {}
    if SLUG.fullmatch(slug) and SHA.fullmatch(sha):
        action = 'resume'
    elif not slug and not sha and receipt.get('action') == 'daily' and not issue:
        action = 'daily'
    elif not slug and not sha and receipt.get('action') == 'run_now' and issue:
        action = 'run_now'
        original = receipt.get('request_payload')
        if not isinstance(original, dict) or not original.get('topic_brief'):
            return None
        payload = {key: str(original.get(key, '')) for key in ('topic_brief', 'idea_id', 'primary_keyword')}
    else:
        return None
    root_run = run if root == str(run['id']) else lookup_run(int(root))
    if not valid_run(root_run):
        return None
    if (attempt == 0) != (root == str(run['id'])):
        return None
    if attempt and (run.get('event') != 'workflow_dispatch' or not RECOVERY_TITLE.fullmatch(run.get('display_title', ''))):
        return None
    if issue:
        match = ISSUE_TITLE.match(root_run.get('display_title', ''))
        if root_run.get('event') != 'issues' or not match or match.group(1) != issue:
            return None
    elif root_run.get('event') != 'workflow_dispatch':
        return None
    return {'action': action, 'slot': slot, 'target_slug': slug,
            'expected_source_sha': sha, 'issue_number': issue, 'request_root': root,
            'recovery_attempt': str(attempt + 1), 'stage_only': 'false', 'dry_run': 'false', **payload}


def choose_recovery(runs, receipt_for, lookup_run, issue_open, *, today, now):
    """Newest receipt per root wins; complete or exhausted roots cannot replay."""
    if any(r.get('status') in ACTIVE for r in runs):
        return None
    seen = set()
    for run in runs:
        if not valid_run(run):
            continue
        # Do not spend runner time enumerating ancient artifacts.
        updated = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
        if updated < now - timedelta(days=3):
            continue
        receipt = receipt_for(run)
        if not receipt:
            continue
        root = str(receipt.get('request_root', ''))
        if not ID.fullmatch(root) or root in seen:
            continue
        seen.add(root)
        issue = str(receipt.get('request_issue', ''))
        if issue and (not ID.fullmatch(issue) or not issue_open(int(issue))):
            continue
        # A valid completed issue that remains open (e.g. report failure) needs
        # only an exact audit/resume, not a replacement article.
        if complete_receipt(receipt) and not issue:
            continue
        if run.get('conclusion') not in {'failure', 'timed_out', 'cancelled', 'success'}:
            continue
        if updated > now - timedelta(minutes=5):
            continue
        target = retry_identity(receipt, run, lookup_run)
        if not target or not (today - timedelta(days=2) <= datetime.strptime(target['slot'], '%Y-%m-%d').date() <= today):
            continue
        # A pending retry may have been cancelled before it could save a receipt.
        # Bound repeat dispatches of the same parent even in that case.
        prior = sum(1 for r in runs if (m := RECOVERY_TITLE.fullmatch(r.get('display_title', ''))) and m.group(1) == str(run['id']))
        if prior >= MAX_RETRIES:
            continue
        return int(run['id']), target
    return None


def catalog_and_candidates(repo, slot):
    sha = api(repo, 'branches/main')['commit']['sha']
    occupied = set()
    for path in ('src/data/posts.json', 'src/data/postsRecent.json'):
        posts = api(repo, f'contents/{path}?ref={sha}', raw=True)
        if not isinstance(posts, list) or any(not isinstance(p, dict) or not isinstance(p.get('date'), str) for p in posts):
            raise ValueError(f'Invalid article catalog: {path}')
        occupied.update(p.get('slug') or p.get('id') or '<unknown>' for p in posts if p['date'] == slot)
    prs = api(repo, 'pulls?state=open&per_page=100')
    candidates = [p['number'] for p in prs if (p.get('head') or {}).get('ref', '').startswith('content/kesher-')
                  and f'Publication slot: `{slot}`' in (p.get('body') or '')]
    return occupied, candidates


def output(fields):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        for key, value in fields.items():
            delimiter = uuid.uuid4().hex
            stream.write(f'{key}<<{delimiter}\n{value}\n{delimiter}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['select', 'resolve', 'report'])
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--receipt')
    parser.add_argument('--issue', default='')
    args = parser.parse_args()
    repo = os.environ.get('GITHUB_REPOSITORY', 'yanivsa/kesher-website')
    if args.mode == 'report':
        try:
            data = json.loads(Path(args.receipt).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        valid = os.environ.get('PUBLISH_OUTCOME') == 'success' and complete_receipt(data, issue=args.issue)
        if valid:
            body = ('### ✅ תהליך הפרסום הושלם ואומת\n\n'
                    f'- מאמר: {data["article_url"]}\n- וידאו: {data["long_video_url"]}\n- שורט: {data["short_video_url"]}\n'
                    f'- מקור: `{data["source_sha256"]}`\n- ריצה: https://github.com/{repo}/actions/runs/{os.environ["GITHUB_RUN_ID"]}')
            subprocess.run(['gh', 'issue', 'close', args.issue, '--repo', repo, '--reason', 'completed', '--comment', body], check=True)
        else:
            print('::notice::Issue remains open: no complete three-link receipt.')
            subprocess.run(['gh', 'issue', 'comment', args.issue, '--repo', repo, '--body',
                f'טרם הושלם חוזה הפרסום המלא. הבקשה נשארת פתוחה. ריצה: https://github.com/{repo}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'], check=True)
            if os.environ.get('PUBLISH_OUTCOME') == 'success' and (
                not isinstance(data, dict) or not data.get('action') or
                (data.get('action') in {'daily', 'run_now', 'resume'} and not (data.get('stage_only') is True or data.get('dry_run') is True))
            ):
                return 1
        return 0
    client = GitHubActionsClient(os.environ['GH_TOKEN'], repo)
    lookup_run = lambda run_id: api(repo, f'actions/runs/{run_id}')
    def issue_open(num):
        item = api(repo, f'issues/{num}')
        return item.get('state') == 'open' and item.get('author_association') in {'OWNER', 'MEMBER', 'COLLABORATOR'}
    def receipt_for(run):
        receipt = read_receipt(client, run)
        if receipt is not None:
            return receipt
        if run.get('conclusion') in {'failure', 'cancelled', 'timed_out'} and not RECOVERY_TITLE.fullmatch(run.get('display_title', '')):
            return unstarted_receipt(run, api(repo, f"actions/runs/{run['id']}/jobs?filter=all&per_page=100"),
                                     lambda num: api(repo, f'issues/{num}'))
        return None

    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo('Asia/Jerusalem'))
    runs = api(repo, f'actions/workflows/{WORKFLOW}/runs?per_page=100')['workflow_runs']
    if args.mode == 'resolve':
        run = lookup_run(args.run_id)
        receipt = receipt_for(run)
        identity = retry_identity(receipt, run, lookup_run)
        if not identity or (identity['issue_number'] and not issue_open(int(identity['issue_number']))):
            raise ValueError('RECOVERY_IDENTITY_NOT_ADMITTED')
        if not (local.date() - timedelta(days=2) <= datetime.strptime(identity['slot'], '%Y-%m-%d').date() <= local.date()):
            raise ValueError('RECOVERY_SLOT_EXPIRED')
        # Ensure no other attempt of this root has already completed after the
        # selected parent. Concurrent publisher jobs remain serialized.
        for newer in runs:
            if newer.get('id') == args.run_id:
                break
            if valid_run(newer):
                other = read_receipt(client, newer)
                if other and str(other.get('request_root', '')) == identity['request_root']:
                    raise ValueError('RECOVERY_PARENT_SUPERSEDED')
        if identity['action'] == 'daily':
            occupied, candidates = catalog_and_candidates(repo, identity['slot'])
            if candidates:
                raise ValueError('RECOVERY_PLANNING_SLOT_HAS_OPEN_CANDIDATE')
        if identity['action'] == 'resume' and isinstance(receipt.get('candidate_post'), dict):
            path = Path(os.environ['RUNNER_TEMP']) / 'kesher-recovery-candidate.json'
            path.write_text(json.dumps(receipt['candidate_post'], ensure_ascii=False), encoding='utf-8')
            identity['article_json'] = str(path)
        output(identity)
        return 0
    if any(r.get('status') in ACTIVE for r in runs):
        output({'allow': 'false', 'reason': 'publisher_active'})
        return 0
    for worker in ('kesher-daily-video.yml', 'kesher-short-v4.yml', 'deploy.yml'):
        if any(r.get('status') in ACTIVE for r in api(repo, f'actions/workflows/{worker}/runs?per_page=30')['workflow_runs']):
            output({'allow': 'false', 'reason': 'child_active'})
            return 0
    slot = local.date().isoformat()
    occupied, candidates = catalog_and_candidates(repo, slot)
    # The scheduled 01:00 request is retried on a later canonical tick if it
    # was blocked by an in-flight IssueOps request. It never starts a second
    # article for a populated slot or an open candidate.
    daily_seen = any(r.get('display_title') == f'Kesher Publish (daily) - {slot}'
                     and (r.get('actor') or {}).get('login') == 'github-actions[bot]' for r in runs)
    if local.hour >= 1 and not occupied and not candidates and not daily_seen:
        output({'allow': 'true', 'slot': slot, 'recovery_run_id': ''})
        return 0
    choice = choose_recovery(runs, receipt_for, lookup_run, issue_open, today=local.date(), now=now)
    if choice:
        run_id, identity = choice
        if identity['action'] == 'daily':
            old_occupied, old_candidates = catalog_and_candidates(repo, identity['slot'])
            if old_candidates:
                output({'allow': 'false', 'reason': 'planning_slot_has_open_candidate'})
                return 0
        output({'allow': 'true', 'slot': identity['slot'], 'recovery_run_id': run_id})
        return 0
    output({'allow': 'false', 'reason': 'no_safe_work'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
