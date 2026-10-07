import ast
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

BASE_SHA = 'ac9eac28f4d7d6e4f89fca5e16bfa50014a7c84f'
PINS = [
    ('.github/workflows/ci.yml', 'call_chain', 'tests/test_kesher_optional_video_enrichment.py'),
    ('.github/workflows/kesher-content-controller-v6.yml', 'call_chain', 'tests/test_kesher_optional_video_enrichment.py'),
    ('.github/workflows/kesher-targeted-media-recovery-dispatch.yml', 'call_chain', '.github/kesher-media-recovery-request.json'),
    ('.github/workflows/kesher-goal-dispatch.yml', 'dispatch_bindings', '.github/workflows/kesher-short-v4.yml'),
    ('.github/workflows/kesher-targeted-media-recovery-dispatch.yml', 'dispatch_bindings', '.github/workflows/kesher-short-v4.yml'),
]
BROLL_ID = 'tests.test_production_contract_v3.ProductionContractV3Tests.test_free_stock_secrets_are_scoped_to_render_steps'

def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def recorded(entry, field, path):
    value = entry['review'][field][path]
    return value['definition_sha256'] if field == 'dispatch_bindings' else value

def method_bytes(root):
    path = root / 'tests/test_production_contract_v3.py'
    source = path.read_bytes()
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == BROLL_ID.rsplit('.', 1)[1])
    return b''.join(lines[node.lineno-1:node.end_lineno]), node.lineno, node.end_lineno

class PinCase(unittest.TestCase):
    def __init__(self, row):
        super().__init__('runTest')
        self.row = row
    def id(self):
        r = self.row
        return f"authority_pin[{r['workflow']}].review.{r['field']}[{r['path']}]"
    def __str__(self):
        return self.id()
    def runTest(self):
        self.assertEqual(self.row['recorded'], self.row['actual'])

def run_suite(suite, output):
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    Path(output).write_text(stream.getvalue())
    return {'tests_run': result.testsRun,
            'failures': [{'id': t.id(), 'traceback': tb} for t, tb in result.failures],
            'errors': [{'id': t.id(), 'traceback': tb} for t, tb in result.errors],
            'skipped': [(t.id(), reason) for t, reason in result.skipped]}

main = Path(sys.argv[1]).resolve()
pending = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3])
assert git(main, 'rev-parse', 'HEAD') == BASE_SHA
assert git(main, 'rev-parse', 'origin/main') == BASE_SHA
assert git(main, 'status', '--porcelain=v1') == ''
base_policy = json.loads((main/'scripts/kesher_runtime/authority_policy.json').read_bytes())
pending_policy = json.loads((pending/'scripts/kesher_runtime/authority_policy.json').read_bytes())
rows = []
for workflow, field, path in PINS:
    base_bytes = (main/path).read_bytes()
    pending_bytes = (pending/path).read_bytes()
    old = recorded(base_policy['workflows'][workflow], field, path)
    pending_old = recorded(pending_policy['workflows'][workflow], field, path)
    rows.append({'workflow': workflow, 'field': field, 'path': path, 'recorded': old,
                 'actual': digest(base_bytes), 'pending_recorded': pending_old,
                 'pending_actual': digest(pending_bytes),
                 'referenced_file_byte_identical': base_bytes == pending_bytes,
                 'recorded_leaf_identical': old == pending_old})
    assert base_bytes == pending_bytes and old == pending_old
    assert old != digest(base_bytes)
base_method, start, end = method_bytes(main)
pending_method, _, _ = method_bytes(pending)
assert base_method == pending_method
assert b'self.assertIn(\'KESHER_BROLL_ENABLED: "true"\', workflow)' in base_method
flags = {}
for workflow in ('.github/workflows/kesher-daily-video.yml', '.github/workflows/kesher-short-v4.yml'):
    a = [line.strip() for line in (main/workflow).read_bytes().splitlines() if line.strip().startswith(b'KESHER_BROLL_ENABLED:')]
    b = [line.strip() for line in (pending/workflow).read_bytes().splitlines() if line.strip().startswith(b'KESHER_BROLL_ENABLED:')]
    assert a == b and a and set(a) == {b'KESHER_BROLL_ENABLED: "false"'}
    flags[workflow] = [line.decode() for line in a]

os.chdir(main)
sys.path.insert(0, str(main))
suite = unittest.TestSuite([PinCase(row) for row in rows])
suite.addTests(unittest.defaultTestLoader.loadTestsFromName(BROLL_ID))
six = run_suite(suite, str(output.with_suffix('.six.log')))
assert six['tests_run'] == 6 and len(six['failures']) == 6 and not six['errors'] and not six['skipped']
previous = json.loads((pending/'docs/forensics/2026-10-07-pending-review-identity/validation.json').read_text())['full_python']
consumer_ids = sorted(set(name.split(' (', 1)[0] for name in previous['failures'] + previous['errors']))
consumers = run_suite(unittest.defaultTestLoader.loadTestsFromNames(consumer_ids), str(output.with_suffix('.consumers.log')))
assert git(main, 'status', '--porcelain=v1') == ''
all_stale = []
for workflow, entry in base_policy['workflows'].items():
    review = entry['review']
    for field in ('call_chain', 'dispatch_bindings'):
        for path in review.get(field, {}):
            actual = digest((main/path).read_bytes()) if (main/path).is_file() else 'MISSING'
            expected = recorded(entry, field, path)
            if actual != expected:
                all_stale.append({'workflow': workflow, 'field': field, 'path': path,
                                  'recorded': expected, 'actual': actual})
unknown_definitions = sorted({str(p.relative_to(main)) for p in (main/'.github/workflows').glob('*.y*ml')} - set(base_policy['workflows']))
unknown = []
for path in unknown_definitions:
    a = (main/path).read_bytes()
    b = (pending/path).read_bytes()
    assert a == b and path not in pending_policy['workflows']
    unknown.append({'path': path, 'sha256': digest(a), 'byte_identical': True, 'unclassified_in_both_policies': True})
proof = {'main_sha': BASE_SHA, 'main_worktree': str(main), 'main_clean_before': True,
         'main_clean_after': True, 'pending_worktree': str(pending),
         'selected_five_pins': rows, 'broll': {'id': BROLL_ID,
         'path': 'tests/test_production_contract_v3.py', 'start_line': start, 'end_line': end,
         'assertion_line': start + next(i for i,line in enumerate(base_method.splitlines()) if b'KESHER_BROLL_ENABLED:' in line),
         'method_sha256': digest(base_method), 'method_byte_identical': True,
         'exact_assertion': 'self.assertIn(\'KESHER_BROLL_ENABLED: "true"\', workflow)',
         'current_flags': flags, 'pr_1073_merge_sha': '8df5219f3ce60c70487927721e7a43caec8eced5'},
         'six_baseline_checks': six, 'original_full_gate_consumers': consumers,
         'main_additional_stale_pins': [r for r in all_stale if (r['workflow'], r['field'], r['path']) not in PINS],
         'all_six_baseline_reproduced': True, 'additional_unclassified_baseline_definitions': unknown,
         'comparison': 'All five recorded hash leaves and referenced files are byte-identical. The B-roll test method and disabled flags are byte-identical. Aggregate tracebacks may be masked by the same unclassified one-off workflow or earlier stale daily-video dispatch pins on main; they are retained rather than claimed identical.',
         'production_state_written': False, 'media_generation_or_upload': False}
output.write_text(json.dumps(proof, indent=2)+'\n')
print('BASELINE_MAIN', BASE_SHA)
print('BASELINE_CLEAN_BEFORE_AFTER YES')
print('SIX_BASELINE_CHECKS', six['tests_run'], 'EXPECTED_FAILURES', len(six['failures']), 'ERRORS', len(six['errors']))
print('BYTE_IDENTICAL_SELECTED_PINS', len(rows))
print('BYTE_IDENTICAL_BROLL_METHOD YES')
print('ORIGINAL_FULL_GATE_CONSUMERS', consumers['tests_run'], 'FAILURE_ENTRIES', len(consumers['failures']), 'ERROR_ENTRIES', len(consumers['errors']))
print('ADDITIONAL_MAIN_STALE_PINS', len(proof['main_additional_stale_pins']))
