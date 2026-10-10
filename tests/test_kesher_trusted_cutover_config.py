"""Configuration identity guards for the trusted cutover service."""
import os
import unittest
from unittest.mock import patch

from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_trusted_cutover_service import TrustedCutoverServiceTests


class TrustedCutoverConfigTests(unittest.TestCase):
    def setUp(self):
        self.fixture = TrustedCutoverServiceTests("test_missing_required_configuration_refuses")
        self.fixture.setUp()
        self.module = self.fixture.load_module()

    def tearDown(self):
        self.fixture.tearDown()

    def test_owner_is_fixed_to_canonical_controller(self):
        env = dict(self.fixture.env, KESHER_CUTOVER_OWNER="another-owner")
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED"
        ):
            self.module.build()

    def test_oidc_audience_is_an_exact_https_origin(self):
        for audience in (
            "http://cutover.example",
            "https://cutover.example/path",
            "https://cutover.example?query=1",
            "https://cutover.example/#fragment",
            "https://",
        ):
            env = dict(self.fixture.env, KESHER_CUTOVER_OIDC_AUDIENCE=audience)
            with self.subTest(audience=audience), patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED"
            ):
                self.module.build()


if __name__ == "__main__":
    unittest.main()
