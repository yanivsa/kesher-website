"""Additional fail-closed identity/native-boundary regressions."""
import os
import unittest
from unittest.mock import patch

from scripts.kesher_runtime.production_ports import PrerequisitePort
from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_trusted_cutover_service import TrustedCutoverServiceTests


class TrustedCutoverHardeningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = TrustedCutoverServiceTests("test_missing_required_configuration_refuses")
        self.fixture.setUp()
        self.module = self.fixture.load_module()

    def tearDown(self):
        self.fixture.tearDown()

    def test_repository_is_fixed_to_kesher_repository(self):
        env = dict(self.fixture.env, KESHER_GITHUB_REPOSITORY="yanivsa/another-repository")
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED"
        ):
            self.module.build()

    def test_github_prerequisite_port_cannot_masquerade_as_native_boundary(self):
        native = __import__(self.fixture.native_name, fromlist=["build"])
        original = native.build

        def unavailable():
            bundle = self.fixture.native_bundle()
            bundle["github_boundary"] = PrerequisitePort("github", "repository-id")
            return bundle

        try:
            native.build = unavailable
            with patch.dict(os.environ, self.fixture.env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_REAL_NATIVE_PORT_REQUIRED"
            ):
                self.module.build()
        finally:
            native.build = original

    def test_missing_native_factory_is_reported_as_native_prerequisite(self):
        env = dict(self.fixture.env, KESHER_CUTOVER_NATIVE_FACTORY="")
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_NATIVE_FACTORY_REQUIRED"
        ):
            self.module.build()

    def test_epoch_cannot_contain_whitespace_or_shell_like_separators(self):
        for epoch in ("epoch with spaces", "epoch\nsecond", "epoch\tsecond"):
            env = dict(self.fixture.env, KESHER_CUTOVER_EPOCH=epoch)
            with self.subTest(epoch=repr(epoch)), patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED"
            ):
                self.module.build()


if __name__ == "__main__":
    unittest.main()
