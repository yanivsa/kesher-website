"""Shared read-only Jules settling gate without legacy media imports."""
from .identity import digest
from .jules import JulesError, session_name

SOURCE_CONTEXT = {'source': 'sources/github/yanivsa/kesher-website', 'githubRepoContext': {'startingBranch': 'main'}}


def assert_article_quiescent(context, api, pr: dict, *, settled_head_sha=None) -> list[str]:
    """A cached settling receipt never replaces the pre-mutation live read."""
    state = context.store.load().state
    settled_head_sha = settled_head_sha or pr['head']['sha']
    proofs = [receipt['evidence'] for command in state['commands'].values()
              if command['target'] == context.target.to_dict() and command['outcome'] == 'succeeded'
              for name, receipt in command['receipts'].items() if name == 'article_pr_settled'
              and receipt['evidence'].get('number') == pr['number']
              and receipt['evidence'].get('head_sha') == settled_head_sha]
    if not proofs:
        raise JulesError('JULES_PENDING')
    names = {name for proof in proofs for name in proof['sessions']}
    names.update(session_name(row) for row in api.sessions()
                 if row.get('title') == 'Kesher article ' + context.target.slot)
    for name in sorted(names):
        row = api.get(name)
        if (session_name(row) != name or row.get('sourceContext') != SOURCE_CONTEXT
                or row.get('title') != 'Kesher article ' + context.target.slot):
            raise JulesError('JULES_IDENTITY_MISMATCH')
        if row.get('state') not in {'COMPLETED', 'FAILED'}:
            raise JulesError('JULES_PENDING')
    evidence = {'number': pr['number'], 'head_sha': pr['head']['sha'],
                'settled_head_sha': settled_head_sha, 'sessions': sorted(names)}
    context.checkpoint('article_quiescence_' + digest(evidence)[:24], evidence, phase='STARTED')
    return sorted(names)

