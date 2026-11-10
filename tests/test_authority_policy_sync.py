import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/kesher_runtime/sync_authority_policy.py'

class AuthorityPolicySyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.workflow='.github/workflows/canonical.yml'
        path=self.root/self.workflow;path.parent.mkdir(parents=True);path.write_text('name: canonical\njobs: {}\n')
        self.code=self.root/'scripts/worker.py';self.code.parent.mkdir();self.code.write_text('value = 1\n')
        self.policy=self.root/'scripts/kesher_runtime/authority_policy.json';self.policy.parent.mkdir()
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.policy.write_text(json.dumps({'workflows':{self.workflow:{'role':'diagnostic','definition_sha256':digest(path),'review':{'call_chain':{'scripts/worker.py':digest(self.code)},'dispatch_bindings':{self.workflow:{'definition_sha256':digest(path)}}}}}},indent=2)+'\n')
    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(SCRIPT),'--root',str(self.root),*args],capture_output=True,text=True)
    def test_matching_hashes_pass_without_writes(self):
        before=self.policy.read_bytes();result=self.run_cli('--check')
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,self.policy.read_bytes())
    def test_stale_governed_workflow_fails_with_exact_path_without_writes(self):
        (self.root/self.workflow).write_text('name: changed\njobs: {}\n');before=self.policy.read_bytes()
        result=self.run_cli('--check')
        self.assertEqual(result.returncode,1,result.stderr);self.assertIn(self.workflow,result.stdout);self.assertEqual(before,self.policy.read_bytes())
    def test_update_repairs_all_governed_hashes_and_is_idempotent(self):
        self.code.write_text('value = 2\n');(self.root/self.workflow).write_text('name: changed\njobs: {}\n')
        result=self.run_cli('--update');self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(self.policy.read_text())['workflows'][self.workflow]
        self.assertEqual(value['definition_sha256'],hashlib.sha256((self.root/self.workflow).read_bytes()).hexdigest())
        self.assertEqual(value['review']['call_chain']['scripts/worker.py'],hashlib.sha256(self.code.read_bytes()).hexdigest())
        self.assertEqual(value['role'],'diagnostic')
        before=self.policy.read_bytes();self.assertEqual(self.run_cli('--update').returncode,0);self.assertEqual(before,self.policy.read_bytes())
        self.assertEqual(self.run_cli('--check').returncode,0)
    def test_unknown_workflow_and_symlink_refuse_even_in_update_mode(self):
        (self.root/'.github/workflows/unreviewed.yml').write_text('name: unknown\n');before=self.policy.read_bytes()
        self.assertNotEqual(self.run_cli('--update').returncode,0);self.assertEqual(before,self.policy.read_bytes())
        (self.root/'.github/workflows/unreviewed.yml').unlink();self.code.unlink();self.code.symlink_to('/etc/hosts')
        self.assertNotEqual(self.run_cli('--update').returncode,0);self.assertEqual(before,self.policy.read_bytes())
