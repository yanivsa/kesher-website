import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawOfflineProofContractTests(unittest.TestCase):
    def test_strict_helper_proof_persists_cleanup_authorization(self):
        source = (ROOT / "scripts/oci_openclaw_helper_proof.py").read_text()
        tree = ast.parse(source)
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "state"
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "helper_proof_verified"
                for target in node.targets
            )
        ]
        self.assertEqual(len(assignments), 1)
        self.assertIs(assignments[0].value.value, True)

    def test_finish_accepts_repair_or_strict_proof(self):
        source = (ROOT / "scripts/oci_openclaw_offline_repair_v2.py").read_text()
        self.assertIn(
            'state.get("helper_repair_verified") or state.get("helper_proof_verified")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
