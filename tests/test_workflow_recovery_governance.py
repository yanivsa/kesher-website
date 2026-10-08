import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/kesher_runtime/workflow_governance.py'
class WorkflowRecoveryGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'.github/workflows').mkdir(parents=True)
        (self.root/'config').mkdir()
        (self.root/'config/kesher-workflow-governance.json').write_text(json.dumps({'grandfathered':{}}))
    def run_check(self,name):
        (self.root/'.github/workflows'/name).write_text('name: unit\njobs: {}\n')
        return subprocess.run([sys.executable,'-B',str(SCRIPT),'--root',str(self.root)],capture_output=True,text=True)
    def test_date_specific_rescue_is_rejected(self):
        result=self.run_check('owner-repair-20261007.yml');self.assertEqual(result.returncode,1);self.assertIn('ONE_OFF_RECOVERY_WORKFLOW_FORBIDDEN',result.stdout)
    def test_slug_specific_exact_rescue_is_rejected(self):
        self.assertEqual(self.run_check('kesher-exact-generic-topic-upload.yml').returncode,1)
    def test_pr_specific_rescue_is_rejected(self):
        self.assertEqual(self.run_check('owner-patch-pr9999.yml').returncode,1)
    def test_canonical_recovery_and_owner_named_canonical_workflow_are_allowed(self):
        self.assertEqual(self.run_check('kesher-targeted-media-recovery-dispatch.yml').returncode,0)
        self.assertEqual(self.run_check('owner-governance.yml').returncode,0)
    def test_grandfathering_does_not_allow_a_changed_legacy_workflow(self):
        import hashlib
        name='owner-repair-20260901.yml';path=self.root/'.github/workflows'/name;path.write_text('reviewed\n')
        (self.root/'config/kesher-workflow-governance.json').write_text(json.dumps({'grandfathered':{str(path.relative_to(self.root)):hashlib.sha256(path.read_bytes()).hexdigest()}}))
        result=subprocess.run([sys.executable,'-B',str(SCRIPT),'--root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(self.run_check(name).returncode,1)
