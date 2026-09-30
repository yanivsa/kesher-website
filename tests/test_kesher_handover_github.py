import base64
import copy
import hashlib
import json
import unittest
from unittest.mock import Mock, patch
from scripts.kesher_runtime.github import GitHubError
from scripts.kesher_runtime.handover_github import GitHubHandover
from scripts.kesher_runtime.identity import canonical_json
from scripts.kesher_runtime.state import StateConflict, StateInvalid
from tests import test_kesher_handover as fixtures


def blob_sha(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class GitService:
    """Git objects are immutable; updateRefs compares both refs atomically."""
    def __init__(self,document,main):
        raw=(canonical_json(document)+'\n').encode(); b=blob_sha(raw)
        self.blobs={b:raw}; self.trees={'c'*40:{'.kesher-controller/state.json':b,'unrelated.json':'d'*40}}
        self.commits={'a'*40:'c'*40}; self.refs={'main':main,'automation-state':'a'*40}
        self.calls=[]; self.serial=30; self.drop=False; self.race=None
    def oid(self):
        self.serial+=1; return f'{self.serial:040x}'
    def request(self,method,path,body=None):
        self.calls.append((method,path,body))
        tail=path.removeprefix('/repos/owner/repo')
        if method=='GET':
            if tail=='':return {'node_id':'repository-id'}
            if tail.startswith('/git/ref/heads/'):return {'object':{'sha':self.refs[tail.split('/')[-1]]}}
            if tail.startswith('/git/commits/'):
                sha=tail.split('/')[-1];return {'sha':sha,'tree':{'sha':self.commits[sha]}}
            if tail.startswith('/contents/'):
                commit=tail.split('?ref=')[1];b=self.trees[self.commits[commit]]['.kesher-controller/state.json']
                return {'sha':b,'encoding':'base64','content':base64.b64encode(self.blobs[b]).decode()}
        if method=='POST' and tail=='/git/blobs':
            raw=base64.b64decode(body['content']);sha=blob_sha(raw);self.blobs[sha]=raw;return {'sha':sha}
        if method=='POST' and tail=='/git/trees':
            tree=copy.deepcopy(self.trees[body['base_tree']]);tree.update({r['path']:r['sha'] for r in body['tree']})
            sha=self.oid();self.trees[sha]=tree;return {'sha':sha}
        if method=='POST' and tail=='/git/commits':
            sha=self.oid();self.commits[sha]=body['tree'];return {'sha':sha}
        if path=='/graphql':
            if self.race:self.race();self.race=None
            data=body['variables']['input'];updates=data['refUpdates']
            if any(self.refs[r['name'].removeprefix('refs/heads/')] != r['beforeOid'] for r in updates):
                return {'errors':[{'type':'STALE_DATA'}]}
            for r in updates:self.refs[r['name'].removeprefix('refs/heads/')]=r['afterOid']
            if self.drop:self.drop=False;raise GitHubError(None,'lost',uncertain=True)
            return {'data':{'updateRefs':{'clientMutationId':data['clientMutationId']}}}
        raise AssertionError((method,path))


class ProtectedGitService:
    """Resource gateway: every non-read is scoped to a verified control intent."""
    def __init__(self, case):
        self.case = case
        self.service = GitService(case.backend.document, case.backend.main)
        self.fence = case.backend.fence
        self.port = self.fence.ports['github']
        self.principal = self.fence.owner
        self.epoch = self.fence.epoch
        self.approval = copy.deepcopy(case.backend.observation['approved_revision'])
        self.code_sha256 = self.approval['code_sha256']
        self.transaction = None
        self.command_id = self.run_id = self.checkout_sha = None
        self.mutations = []

    def snapshot(self):
        commit = self.service.refs['automation-state']
        tree = self.service.commits[commit]
        sha = self.service.trees[tree]['.kesher-controller/state.json']
        return json.loads(self.service.blobs[sha]), sha, commit, tree

    def authorize(self, operation, previous, sha, proposed=None, workflow=None):
        if 'control_gate' not in (self.port.protection or {}):
            # Reproduce the original contract deadlock at the actual endpoint.
            self.port.mutate(self.principal, epoch=self.epoch, state=previous)
        from scripts.kesher_runtime.exclusion import require_control_operation
        require_control_operation(self.port.protection, operation, principal=self.principal,
            epoch=self.epoch, code_sha256=self.code_sha256, approval=self.approval,
            previous=previous, previous_sha=sha, main_sha=self.service.refs['main'],
            proposed=proposed, workflow=workflow, command_id=self.command_id,
            run_id=self.run_id, checkout_sha=self.checkout_sha)

    def request(self, method, path, body=None, **kwargs):
        if method == 'GET':
            if '/contents/' in path and path.endswith('?ref=automation-state'):
                path = path.removesuffix('automation-state') + self.service.refs['automation-state']
            return self.service.request(method, path, body)
        previous, sha, commit, tree = self.snapshot()
        tail = path.removeprefix('/repos/owner/repo')
        if method == 'POST' and tail == '/git/blobs':
            proposed = json.loads(base64.b64decode(body['content']))
            self.authorize('handover_cas', previous, sha, proposed)
            result = self.service.request(method, path, body)
            self.transaction = {'previous':previous, 'sha':sha, 'commit':commit,
                                'tree':tree, 'proposed':proposed, 'blob':result['sha']}
        elif method == 'POST' and tail in {'/git/trees', '/git/commits'}:
            tx = self.transaction
            if tx is None: raise StateInvalid('Missing protected state transaction')
            self.authorize('handover_cas', tx['previous'], tx['sha'], tx['proposed'])
            if tail == '/git/trees':
                if body != {'base_tree':tx['tree'], 'tree':[{'path':'.kesher-controller/state.json',
                        'mode':'100644','type':'blob','sha':tx['blob']}]}:
                    raise StateInvalid('Control gate only permits exact state path')
                result = self.service.request(method, path, body); tx['new_tree'] = result['sha']
            else:
                if body['tree'] != tx['new_tree'] or body['parents'] != [tx['commit']]:
                    raise StateInvalid('Control gate only permits exact state parent/tree')
                result = self.service.request(method, path, body); tx['new_commit'] = result['sha']
        elif method == 'POST' and path == '/graphql':
            tx = self.transaction
            self.authorize('handover_cas', tx['previous'], tx['sha'], tx['proposed'])
            expected = [
                {'name':'refs/heads/main','beforeOid':self.service.refs['main'],
                 'afterOid':self.service.refs['main'],'force':False},
                {'name':'refs/heads/automation-state','beforeOid':tx['commit'],
                 'afterOid':tx['new_commit'],'force':False}]
            if body['variables']['input']['refUpdates'] != expected:
                raise StateInvalid('Control gate cannot publish or rewrite another ref')
            result = self.service.request(method, path, body)
        elif method == 'PUT' and tail.startswith('/actions/workflows/') and tail.endswith('/disable'):
            wid = int(tail.split('/')[-2])
            workflow = next(w for w in self.case.backend.observation['workflows'] if w['id'] == wid)
            self.authorize('retire_workflow', previous, sha, workflow=workflow)
            workflow['state'] = 'disabled_manually'; result = None
        elif method == 'PUT' and tail == '/contents/.kesher-controller/state.json':
            if body['branch'] != 'automation-state' or body['sha'] != sha:
                raise StateConflict('Protected canonical state CAS is stale')
            written = json.loads(base64.b64decode(body['content']))
            if written['revision'] != previous['revision'] + 1:
                raise StateInvalid('Protected canonical revision mismatch')
            proposed = copy.deepcopy(written); proposed['revision'] = previous['revision']
            operation = 'controller_cas' if self.principal == 'kesher-canonical-controller' else 'worker_claim_cas'
            self.authorize(operation, previous, sha, proposed)
            raw = (canonical_json(written)+'\n').encode(); blob = blob_sha(raw)
            self.service.blobs[blob] = raw
            new_tree = self.service.oid(); self.service.trees[new_tree] = dict(self.service.trees[tree], **{'.kesher-controller/state.json':blob})
            new_commit = self.service.oid(); self.service.commits[new_commit] = new_tree
            self.service.refs['automation-state'] = new_commit
            result = {'content':{'sha':blob}}
        else:
            raise StateInvalid('No provider/publication/general mutation through control gate')
        self.mutations.append((method, path))
        return result


class GitHandoverTests(unittest.TestCase):
    def setUp(self):
        case=fixtures.HandoverTests();case.setUp();self.case=case
        self.service=GitService(case.backend.document,case.backend.main)
        self.fence=case.backend.fence
        self.backend=GitHubHandover(self.service,'owner/repo',observer=case.backend.observe,fence=self.fence)
        self.original=self.backend.load()
        case.coordinator().tick();self.proposed=case.backend.document
    def test_exact_refs_preserve_unrelated_tree_and_cas_once(self):
        result=self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
        self.assertEqual(self.backend.load().state,result.state)
        self.assertEqual(self.service.trees[result.tree_sha]['unrelated.json'],'d'*40)
        with self.assertRaises(StateConflict):self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
        self.assertEqual(self.backend.load().state,result.state)
    def test_main_and_state_races_do_not_change_state(self):
        for ref in ('main','automation-state'):
            with self.subTest(ref=ref):
                self.setUp();before=self.service.refs['automation-state']
                self.service.race=lambda:self.service.refs.update({ref:'f'*40})
                with self.assertRaises(StateConflict):self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
                self.assertEqual(self.service.refs['automation-state'],before if ref=='main' else 'f'*40)
    def test_success_with_lost_response_reload_adopts_without_transport_retry(self):
        self.service.drop=True
        with self.assertRaises(GitHubError):self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
        self.assertEqual(self.backend.load().state,self.proposed)
        self.assertEqual(sum(c[1]=='/graphql' for c in self.service.calls),1)
    def test_missing_or_lost_exclusive_fence_refuses_before_mutation(self):
        count=len(self.service.calls)
        with patch.object(self.fence,'assert_exclusive',side_effect=StateInvalid('fence lost')):
            with self.assertRaises(StateInvalid):self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
        self.assertEqual(len(self.service.calls),count)
        self.backend.fence=None
        with self.assertRaises(StateInvalid):self.backend.load()

    def test_fence_method_without_resource_evidence_cannot_authorize_git_write(self):
        count=len(self.service.calls)
        self.backend.fence=Mock(spec=['assert_exclusive'])
        self.backend.fence.assert_exclusive.return_value=None
        with self.assertRaises(StateInvalid):
            self.backend.save(self.original,self.proposed,main_sha=self.case.backend.main)
        self.assertEqual(len(self.service.calls),count)

    def protected_coordinator(self):
        from scripts.kesher_runtime.handover import Coordinator
        case = fixtures.HandoverTests(); case.setUp()
        gateway = ProtectedGitService(case)
        backend = GitHubHandover(gateway,'owner/repo',observer=case.backend.observe,fence=case.backend.fence)
        params = copy.deepcopy(case.params); params['controller_sha'] = backend.load().blob_sha
        c = Coordinator(backend,params,closure=case.closure,key=lambda:'synthetic-runtime-key-at-least-24-chars')
        return case,gateway,backend,c

    def test_protected_resource_drives_nine_phases_then_intent_and_claim_cas(self):
        from scripts.kesher_runtime.handover import PHASES
        from scripts.kesher_runtime.github import GitHubStateStore
        from scripts.kesher_runtime.state import plan_command, claim_command
        case,gateway,backend,c = self.protected_coordinator()
        phases = []
        for _ in range(50):
            phase = c.tick()
            if phase not in phases: phases.append(phase)
            if phase == 'VERIFIED': break
        self.assertEqual(phases,list(PHASES))
        count = len(gateway.mutations); self.assertEqual(c.tick(),'VERIFIED')
        self.assertEqual(len(gateway.mutations),count)
        store = GitHubStateStore(gateway,'owner/repo')
        loaded = store.load(); code = case.params['main_sha']; target = case.args['identity']
        proposed,cid = plan_command(loaded.state,target,'generate',1,{},code_sha=code,now=case.params['now'])
        gateway.principal = 'kesher-canonical-controller'
        saved = store.save(loaded,proposed)
        gateway.principal = 'canonical-worker'; gateway.command_id = cid
        gateway.run_id = '456/1'; gateway.checkout_sha = code
        proposed,_ = claim_command(saved.state,cid,'456/1',target,code_sha=code,now=case.params['now'])
        saved = store.save(saved,proposed)
        self.assertEqual(saved.state['commands'][cid]['owner']['run_id'],'456/1')
        with self.assertRaises(StateInvalid): gateway.port.mutate('stale-legacy',epoch=gateway.epoch,state=saved.state)
        with self.assertRaises(StateInvalid): gateway.request('POST','/repos/owner/repo/deployments',{})

    def test_protected_handover_rejects_stale_actor_epoch_code_and_competing_ref(self):
        for field,value in [('principal','stale-legacy'),('epoch','stale-epoch'),('code_sha256','f'*64)]:
            with self.subTest(field=field):
                _,gateway,_,c = self.protected_coordinator()
                setattr(gateway,field,value)
                before = gateway.service.refs['automation-state']
                with self.assertRaises(StateInvalid): c.tick()
                self.assertEqual(gateway.service.refs['automation-state'],before)
        _,gateway,backend,c = self.protected_coordinator()
        before = gateway.service.refs['automation-state']
        gateway.service.race = lambda:gateway.service.refs.update(main='f'*40)
        with self.assertRaises(StateConflict): c.tick()
        self.assertEqual(gateway.service.refs['automation-state'],before)


if __name__=='__main__':unittest.main()
