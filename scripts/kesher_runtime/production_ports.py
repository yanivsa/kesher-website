"""Production prerequisites are refusals, never synthetic service receipts.

An authenticated gateway can enforce its own narrow operations, but cannot
invalidate a provider credential held elsewhere. These providers do not expose
the complete exclusion/readback contract required by this repository. A native
administrative operation (token deletion, session deletion, Actions disable)
must not be promoted to a six-resource fence. No file/boolean overrides exist.
"""
from .exclusion import REQUIRED_RESOURCES
from .state import StateInvalid

PREREQUISITES = {
    'github': 'Owner-admin retirement of personal PAT/OAuth/App/SSH/deploy-key grants; '
              'isolated gateway App credentials; service-enforced direct-write denial '
              'and complete grant/run readback, including old workflow tokens.',
    'jules': 'Account-admin key/repository-access retirement plus independent settling '
             'of every existing session; session deletion alone is not cancellation proof.',
    'notebooklm': 'Account-admin invalidation of all predecessor cookies, master tokens '
                  'and sessions on the exact notebook; an enforceable canonical gateway '
                  'and service readback. Enterprise IAM is not proof for a consumer notebook.',
    'youtube': 'Retire every predecessor OAuth grant and outstanding resumable capability '
               'on the exact channel; independently settle uploads; use a distinct canonical '
               'OAuth project behind a command gate. OAuth revocation alone is insufficient.',
    'cloudflare': 'Account-admin inventory of every member, global key, user/account token '
                  'and Pages integration; revoke predecessor authority and settle deployments; '
                  'isolate canonical credentials behind a command gate on exact account/project.',
    'image_provider': 'Identify the actual provider/project; invalidate every predecessor '
                      'key, session and issued bearer token; settle in-flight generations; '
                      'isolate canonical credentials behind a command gate with native readback.',
}


class PrerequisitePort:
    """A deliberately unavailable live port; cannot generate a proof or effect."""
    def __init__(self, resource, resource_id):
        if resource not in REQUIRED_RESOURCES or not isinstance(resource_id, str) or not resource_id:
            raise StateInvalid('CUTOVER_RESOURCE_ID_REQUIRED')
        self.resource, self.resource_id = resource, resource_id

    def _refuse(self):
        raise StateInvalid('CUTOVER_PREREQUISITE_' + self.resource.upper())

    def inspect(self, repo): self._refuse()
    def exclude(self, repo, observed_revision, policy): self._refuse()


def prerequisite_report():
    return {name: {'status': 'HUMAN_PREREQUISITE', 'requirement': reason}
            for name, reason in PREREQUISITES.items()}
