"""Local gateway provisioning checks, never provider exclusion attestation.

The independent administrator owns the factory, reviewed digest, native ports,
TLS ingress and durable volume. Passing this check proves configuration only;
the runtime must still obtain fresh native readbacks before every effect.
"""
import hashlib
import importlib.util
import re
from pathlib import Path
from urllib.parse import urlsplit

from .identity import require_sha
from .state import StateInvalid

REPOSITORY = 'yanivsa/kesher-website'
REPOSITORY_ID = 1239881973
REPOSITORY_NODE_ID = 'R_kgDOSecY9Q'
# Independently identified by the owner; not evidence of state or authority.
SUPERVISOR_TASK_ID = '6aa71096e1788191ae791be184322d69'


def validate_installation(application):
    from .control_planes import ControlPlaneConvergence
    from .cutover_auth import ActionsIdentity
    from .cutover_service import InvocationJournal
    from .exclusion import REQUIRED_RESOURCES
    from .production_cutover import CutoverRuntime
    try:
        spec=application.installation
        expected={'repo','repository_id','repository_node_id','supervisor_task_id','epoch','owner',
                  'reviewed_revision','https_origin','ledger_path','resource_bindings'}
        if not isinstance(spec,dict) or set(spec)!=expected:raise ValueError()
        if (spec['repo']!=REPOSITORY or type(spec['repository_id']) is not int
                or spec['repository_id']!=REPOSITORY_ID or spec['repository_node_id']!=REPOSITORY_NODE_ID
                or spec['supervisor_task_id']!=SUPERVISOR_TASK_ID):raise ValueError()
        require_sha(spec['reviewed_revision'],40)
        origin=urlsplit(spec['https_origin'])
        if (origin.scheme!='https' or not origin.hostname or origin.username or origin.password
                or origin.path or origin.query or origin.fragment
                or spec['https_origin'].endswith('/')):raise ValueError()
        if type(application.runtime) is not CutoverRuntime or type(application.identity) is not ActionsIdentity:
            raise ValueError()
        fence=application.runtime.fence; identity=application.identity; cp=fence.control_planes
        if (set(spec['resource_bindings'])!=set(REQUIRED_RESOURCES)
                or any(not isinstance(v,str) or not v.strip() or 'UNRESOLVED' in v
                       for v in spec['resource_bindings'].values())
                or spec['resource_bindings']['github']!=REPOSITORY_NODE_ID
                or fence.bindings!=spec['resource_bindings'] or fence.repo!=REPOSITORY
                or fence.epoch!=spec['epoch'] or fence.owner!=spec['owner']
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',spec['epoch'])
                or not isinstance(spec['owner'],str) or not spec['owner'].strip()
                or type(cp) is not ControlPlaneConvergence or cp.repo!=REPOSITORY
                or cp.supervisor_id!=SUPERVISOR_TASK_ID or cp.bindings!=fence.bindings
                or cp.epoch!=fence.epoch or cp.owner!=fence.owner
                or application.epoch!=spec['epoch'] or application.reviewed_revision!=spec['reviewed_revision']
                or identity.repo!=REPOSITORY or identity.repository_id!=str(REPOSITORY_ID)
                or identity.main_sha!=spec['reviewed_revision'] or identity.audience!=spec['https_origin']
                or not callable(application.review_check)):raise ValueError()
        ledger=Path(spec['ledger_path'])
        if (not ledger.is_absolute() or ledger.resolve()!=ledger or not ledger.is_file()
                or ledger.stat().st_mode & 0o077 or type(application.journal) is not InvocationJournal
                or application.journal.path!=str(ledger)):raise ValueError()
        application.journal.check()
    except (KeyError,TypeError,ValueError,AttributeError,OSError):
        raise StateInvalid('CUTOVER_INSTALLATION_BINDING_REQUIRED') from None


def load_factory(factory, root, approved_sha256):
    """Load one independently installed, hash-pinned module outside this checkout.

    The digest is an administrator CLI trust root, never an HTTP client value.
    OS ownership/read-only code mounts and review of transitive dependencies are
    still required. No network/storage initialization occurs in this loader.
    """
    try:
        require_sha(approved_sha256)
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*',factory):raise ValueError()
        module,name=factory.split(':'); directory=Path(root)
        checkout=Path(__file__).resolve().parents[2]
        if (not directory.is_absolute() or directory.resolve()!=directory
                or directory==checkout or checkout in directory.parents):raise ValueError()
        path=directory/(module+'.py')
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:raise ValueError()
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=approved_sha256:raise ValueError()
        # Execute the verified bytes, avoiding pyc reuse or a second mutable read.
        spec=importlib.util.spec_from_file_location('_kesher_installed_factory',path)
        loaded=importlib.util.module_from_spec(spec)
        exec(compile(raw,str(path),'exec'),loaded.__dict__)
        build=getattr(loaded,name)
        if not callable(build):raise ValueError()
        return build
    except (OSError,TypeError,ValueError,AttributeError):
        raise StateInvalid('CUTOVER_INDEPENDENT_FACTORY_REQUIRED') from None
