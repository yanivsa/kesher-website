#!/usr/bin/env python3
"""Find overwritten PR heads and review evidence across ALL PRs, not only merges."""
import argparse
import json
import subprocess
from pathlib import Path

from inventory_kesher_history import OUT, ROOT, api, save

SELECTIONS = {
    'timelineItems': ('itemTypes:[HEAD_REF_FORCE_PUSHED_EVENT],',
                      '__typename ... on HeadRefForcePushedEvent {createdAt beforeCommit {oid} afterCommit {oid}}'),
    'reviews': ('', 'id body state submittedAt commit {oid} author {login}'),
}


def main(cache):
    cursor, page, rows = None, 1, []
    fields = 'number title url '
    for connection, (extra, nodes) in SELECTIONS.items():
        fields += connection + '(first:100,' + extra.rstrip(',') + ') {' if extra else connection + '(first:100) {'
        fields += 'totalCount pageInfo {hasNextPage endCursor} nodes {' + nodes + '}} '
    while True:
        query = ('query($cursor:String) {repository(owner:"yanivsa",name:"kesher-website") {'
                 'pullRequests(first:30,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}) {'
                 'totalCount pageInfo {hasNextPage endCursor} nodes {' + fields + '}}}}')
        args = ['graphql', '-f', 'query=' + query]
        if cursor:
            args += ['-f', 'cursor=' + cursor]
        conn = api(cache, f'evolution-page-{page:03}', args)['data']['repository']['pullRequests']
        rows.extend(conn['nodes'])
        if not conn['pageInfo']['hasNextPage']:
            assert len({r['number'] for r in rows}) == conn['totalCount']
            break
        cursor, page = conn['pageInfo']['endCursor'], page + 1
    for pr in rows:
        for connection, (extra, selection) in SELECTIONS.items():
            value, extra_page = pr[connection], 1
            while value['pageInfo']['hasNextPage']:
                query = ('query($cursor:String) {repository(owner:"yanivsa",name:"kesher-website") {'
                         + f'pullRequest(number:{pr["number"]}) ' + '{'
                         + connection + '(first:100,' + extra + 'after:$cursor) {'
                         + 'pageInfo {hasNextPage endCursor} nodes {' + selection + '}}}}}')
                chunk = api(cache, f'evolution-pr-{pr["number"]}-{connection}-{extra_page}',
                    ['graphql', '-f', 'query=' + query, '-f', 'cursor=' + value['pageInfo']['endCursor']])
                more = chunk['data']['repository']['pullRequest'][connection]
                value['nodes'].extend(more['nodes'])
                value['pageInfo'] = more['pageInfo']
                extra_page += 1
    save(cache / 'pr-evolution.json', rows)
    overwritten = []
    for pr in rows:
        for event in pr['timelineItems']['nodes']:
            sha = (event.get('beforeCommit') or {}).get('oid')
            available = False
            if sha:
                available = subprocess.run(['git', 'cat-file', '-e', sha], cwd=ROOT, capture_output=True).returncode == 0
                if not available:
                    available = subprocess.run(['git', 'fetch', 'origin', sha], cwd=ROOT, capture_output=True).returncode == 0
                if available:
                    subprocess.run(['git', 'update-ref', f'refs/forensics/overwritten/{pr["number"]}/{sha}', sha], cwd=ROOT, check=True)
            overwritten.append({'pr': pr['number'], 'url': pr['url'], 'date': event.get('createdAt'),
                'before_sha': sha, 'after_sha': (event.get('afterCommit') or {}).get('oid'),
                'before_object_available': available})
    save(OUT / 'pr-evolution-index.json', {'pull_requests_scanned': len(rows),
        'overwritten_heads': overwritten,
        'reviews': [{'pr': r['number'], 'count': r['reviews']['totalCount'],
                     'commits': sorted({(n.get('commit') or {}).get('oid', '') for n in r['reviews']['nodes']})}
                    for r in rows if r['reviews']['totalCount']],
        'limitations': ['Unresolvable force-pushed commit objects are explicitly marked unavailable.',
                       'Raw review bodies stay in the private evidence cache.']})
    print(json.dumps({'prs': len(rows), 'force_pushes': len(overwritten),
                      'unavailable_heads': sum(not r['before_object_available'] for r in overwritten)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    main(args.cache)
