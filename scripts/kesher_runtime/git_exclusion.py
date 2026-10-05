"""Offline-capable GitHub exclusion port. No default live credential gateway.

    Epoch acquisition uses documented atomic GraphQL updateRefs beforeOid CAS on
the existing automation-state ref, with a no-op main comparison. Actions PUT
disable/POST cancel have no CAS: they are subordinate durable reconciliation.
Git ownership does not revoke PATs/apps/keys or protect an external provider.
Activation still requires an independently installed resource-side gateway.
"""
import base64
import copy
import hashlib
import json

from .github import GitHubError, _unique_object
from .handover_github import GitHubHandover, Snapshot, UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

ANCHOR_MESSAGE = 'state: Kesher exclusion epoch\n'


def no_legacy_incident(state):
    if any(i.get('kind') == 'legacy_authority_violation' and i.get('status') == 'open'
           for i in state.get('incidents', {}).values()):
        raise StateInvalid('LEGACY_AUTHORITY_INCIDENT_OPEN')


def require_exclusion_actions(state, anchor, *, principal, epoch, authenticated_code_sha256,
                              approval, operation, workflow_id, workflow_path, current_run=None):
    """Resource-side bootstrap Actions guard; arguments come from the gateway.

    The gateway reads actual state/anchor/run, authenticates principal+code and
    independently installs approval. Caller-supplied state/review is forbidden.
    It denies all non-retirement effects. Cancel is checked against the latest
    exact attempt at the actual endpoint, never just a caller's prior GET.
    """
    from .authority_topology import run_identity
    no_legacy_incident(state)
    try:
        require_sha(authenticated_code_sha256)
        require_sha(approval['code_sha256']); require_sha(approval['resource_policy_sha256'])
        ledger = state['github_exclusion']
        entry = ledger['drains'][str(workflow_id)]
        if (principal != anchor['owner'] or epoch != anchor['epoch'] or ledger['epoch'] != epoch
                or ledger['anchor'] != anchor['commit_sha'] or approval['repo'] != anchor['repo']
                or approval['main_sha'] != anchor['main_sha']
                or approval['resource_policy_sha256'] != anchor['policy_sha256']
                or authenticated_code_sha256 != approval['code_sha256']
                or 'handover' in state or state.get('schema_version') != 5
                or entry['workflow_id'] != workflow_id or entry['workflow_path'] != workflow_path
                or entry['epoch'] != epoch or entry['proof'] is not None):
            raise StateInvalid('GITHUB_EXCLUSION_ACTION_DENIED')
        if operation == 'disable':
            if (entry['observed_disabled'] or not entry['disable']['attempts']
                    or entry['disable']['attempts'][-1] != {'outcome':'intent'}):
                raise StateInvalid('GITHUB_EXCLUSION_DISABLE_INTENT_REQUIRED')
        elif operation == 'cancel':
            exact = run_identity(current_run)
            row = entry['runs'][f"{exact['id']}:{exact['run_attempt']}"]
            if (row['identity'] != exact or row['cancel'] != {'outcome':'intent'}
                    or exact['workflow_id'] != workflow_id or exact['path'] != workflow_path
                    or current_run['status'] == 'completed'):
                raise StateInvalid('GITHUB_EXCLUSION_CANCEL_INTENT_REQUIRED')
        else: raise StateInvalid('GITHUB_EXCLUSION_OPERATION_DENIED')
    except (KeyError,TypeError,ValueError) as exc:
        raise StateInvalid('GITHUB_EXCLUSION_ACTION_DENIED') from exc
    return operation


class GitExclusionEpoch:
    """Exact Git authority anchor, recovered by immutable anchor and ancestry.

    Acquisition adds one commit with the SAME state tree and a canonical
    identity in its message. The actual CAS winner, not a dangling candidate
    commit or an Actions acknowledgment, owns the epoch. No new branch/store.
    A trusted gateway must prohibit ref rewrites and unauthorized descendants;
    a Git record alone is not a credential-revocation receipt.
    """
    def __init__(self, github, repo, *, epoch, owner, resource_id, main_sha, policy_sha256):
        require_sha(main_sha,40); require_sha(policy_sha256)
        if not all(isinstance(x,str) and x for x in (repo,epoch,owner,resource_id)):
            raise StateInvalid('GITHUB_EPOCH_IDENTITY_REQUIRED')
        self.github, self.repo = github, repo
        self.identity = dict(repo=repo,epoch=epoch,owner=owner,resource_id=resource_id,
                             main_sha=main_sha,policy_sha256=policy_sha256)
        self.api = '/repos/' + repo
        self.reader = GitHubHandover(github,repo,observer=None,fence=None)

    def _commit(self, sha):
        require_sha(sha,40)
        row = self.github.request('GET',self.api+'/git/commits/'+sha)
        if row.get('sha') != sha or not isinstance(row.get('parents'),list):
            raise StateInvalid('GITHUB_EPOCH_COMMIT_INVALID')
        require_sha(row['tree']['sha'],40)
        for p in row['parents']: require_sha(p['sha'],40)
        return row

    def _anchor(self, sha, row=None):
        row = row or self._commit(sha)
        message = row.get('message')
        if not isinstance(message,str) or not message.startswith(ANCHOR_MESSAGE):
            raise StateInvalid('GITHUB_EPOCH_ANCHOR_INVALID')
        record = json.loads(message[len(ANCHOR_MESSAGE):],object_pairs_hook=_unique_object)
        if (set(record) != set(self.identity) | {'before_oid','tree_sha','ref'}
                or record['ref'] != 'refs/heads/automation-state'
                or [p['sha'] for p in row['parents']] != [record['before_oid']]
                or record['tree_sha'] != row['tree']['sha']
                or self._commit(record['before_oid'])['tree']['sha'] != row['tree']['sha']):
            raise StateInvalid('GITHUB_EPOCH_ANCHOR_INVALID')
        for key,value in self.identity.items():
            if record[key] != value: raise StateInvalid('GITHUB_EPOCH_ALREADY_OWNED')
        return dict(record,commit_sha=sha)

    def observe(self):
        if self.github.request('GET',self.api)['node_id'] != self.identity['resource_id']:
            raise StateInvalid('GITHUB_EPOCH_RESOURCE_ID_MISMATCH')
        main = self.github.request('GET',self.api+'/git/ref/heads/main')['object']['sha']
        if main != self.identity['main_sha']: raise StateInvalid('GITHUB_EPOCH_MAIN_CHANGED')
        current = self.github.request('GET',self.api+'/git/ref/heads/automation-state')['object']['sha']
        require_sha(current,40)
        loaded = self.reader.read_snapshot()
        if loaded.commit_sha != current: raise StateInvalid('GITHUB_EPOCH_REF_CHANGED_DURING_READBACK')
        if 'github_exclusion' in loaded.state:
            ledger = loaded.state['github_exclusion']
            if (not isinstance(ledger,dict) or ledger.get('epoch') != self.identity['epoch']):
                raise StateInvalid('GITHUB_EPOCH_LEDGER_IDENTITY_INVALID')
            anchor = self._anchor(ledger['anchor'])
            comparison = self.github.request('GET',self.api+'/compare/'+anchor['commit_sha']+'...'2µÕÉÉ•¹Ð¬œýÁ•É}Á…”ôÄ™Á…”ôÄœ¤(€€€€€€€€€€€¥˜€¡½µÁ…É¥Í½¸¹•Ð ‰…Í•}½µµ¥Ðœ±íô¤¹•Ð Í¡„œ¤€„ô…¹¡½Él½µµ¥Ñ}Í¡„t(€€€€€€€€€€€€€€€€€€€½È½µÁ…É¥Í½¸¹•Ð µ•É•}‰…Í•}½µµ¥Ðœ±íô¤¹•Ð Í¡„œ¤€„ô…¹¡½Él½µµ¥Ñ}Í¡„t(€€€€€€€€€€€€€€€€€€€½ÈÑåÁ”¡½µÁ…É¥Í½¸¹•Ð ‰•¡¥¹‘}‰äœ¤¤¥Ì¹½Ð¥¹Ð½È½µÁ…É¥Í½¹l‰•¡¥¹‘}‰ät€„ô€À(€€€€€€€€€€€€€€€€€€€½ÈÑåÁ”¡½µÁ…É¥Í½¸¹•Ð …¡•…‘}‰äœ¤¤¥Ì¹½Ð¥¹Ð(€€€€€€€€€€€€€€€€€€€½È€¡ÕÉÉ•¹Ð€ôô…¹¡½Él½µµ¥Ñ}Í¡„t…¹(€€€€€€€€€€€€€€€€€€€€€€€€¡½µÁ…É¥Í½¸¹•Ð ÍÑ…ÑÕÌœ¤€„ô€¥‘•¹Ñ¥…°œ½È½µÁ…É¥Í½¹l…¡•…‘}‰ät€„ô€À¤¤(€€€€€€€€€€€€€€€€€€€½È€¡ÕÉÉ•¹Ð€„ô…¹¡½Él½µµ¥Ñ}Í¡„t…¹(€€€€€€€€€€€€€€€€€€€€€€€€¡½µÁ…É¥Í½¸¹•Ð ÍÑ…ÑÕÌœ¤€„ô€…¡•…œ½È½µÁ…É¥Í½¹l…¡•…‘}‰ät€ð€Ä¤¤¤è(€€€€€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}9!=I}9=Q}9MQ=Hœ¤(€€€€€€€€€€€¥˜€¡Í•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ Pœ±Í•±˜¹…Á¤¬œ½¥Ð½É•˜½¡•…‘Ì½…ÕÑ½µ…Ñ¥½¸µÍÑ…Ñ”œ¥l½‰©•ÐulÍ¡„t€„ôÕÉÉ•¹Ð(€€€€€€€€€€€€€€€€€€€½ÈÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ Pœ±Í•±˜¹…Á¤¬œ½¥Ð½É•˜½¡•…‘Ì½µ…¥¸œ¥l½‰©•ÐulÍ¡„t€„ôÍ•±˜¹¥‘•¹Ñ¥Ñålµ…¥¹}Í¡„t¤è(€€€€€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}I}!9}UI%9}I	,œ¤(€€€€€€€€€€€É•ÑÕÉ¸ìÕÉÉ•¹Ñ}É•˜œéÕÉÉ•¹Ð°…¹¡½Èœé…¹¡½Éô(€€€€€€€Í¡„°Í••¸€ôÕÉÉ•¹Ð°Í•Ð ¤(€€€€€€€™½È|¥¸É…¹” ÔÄÈ¤è(€€€€€€€€€€€¥˜Í¡„¥¸Í••¸èÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}9MQIe}%9Y1%œ¤(€€€€€€€€€€€Í••¸¹…‘¡Í¡„¤ìÉ½Ü€ôÍ•±˜¹}½µµ¥Ð¡Í¡„¤(€€€€€€€€€€€µ•ÍÍ…”€ôÉ½Ü¹•Ð µ•ÍÍ…”œ¤(€€€€€€€€€€€¥˜¹½Ð¥Í¥¹ÍÑ…¹”¡µ•ÍÍ…”±ÍÑÈ¤èÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}=55%Q}%9Y1%œ¤(€€€€€€€€€€€¥˜µ•ÍÍ…”¹ÍÑ…ÉÑÍÝ¥Ñ ¡9!=I}5MM¤è(€€€€€€€€€€€€€€€É•ÑÕÉ¸ìÕÉÉ•¹Ñ}É•˜œéÕÉÉ•¹Ð°…¹¡½ÈœéÍ•±˜¹}…¹¡½È¡Í¡„±É½Ü¥ô(€€€€€€€€€€€¥˜±•¸¡É½ÝlÁ…É•¹ÑÌt¤€ø€ÄèÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}5I}9MQIe}IUMœ¤(€€€€€€€€€€€¥˜¹½ÐÉ½ÝlÁ…É•¹ÑÌtèÉ•ÑÕÉ¸ìÕÉÉ•¹Ñ}É•˜œéÕÉÉ•¹Ð°…¹¡½Èœé9½¹•ô(€€€€€€€€€€€Í¡„€ôÉ½ÝlÁ…É•¹ÑÌulÁulÍ¡„t(€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}9MQIe}%9=5A1Qœ¤((€€€‘•˜…ÕÑ¡½É¥Ñä¡Í•±˜¤è(€€€€€€€É½Ü€ôÍ•±˜¹½‰Í•ÉÙ” ¤(€€€€€€€¥˜É½Ýl…¹¡½Èt¥Ì9½¹”èÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}9=Q}EU%Iœ¤(€€€€€€€É•ÑÕÉ¸É½Ýl…¹¡½Èt((€€€‘•˜}…Ì¡Í•±˜°‰•™½É”°…™Ñ•È¤è(€€€€€€€É•Á½}¥€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ Pœ±Í•±˜¹…Á¤¥l¹½‘•}¥t(€€€€€€€¥˜É•Á½}¥€„ôÍ•±˜¹¥‘•¹Ñ¥ÑålÉ•Í½ÕÉ•}¥tèÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}IM=UI}%}5%M5Q œ¤(€€€€€€€É•ÅÕ•ÍÐ€ôìÉ•Á½Í¥Ñ½Éå%œéÉ•Á½}¥°(€€€€€€€€€€€€±¥•¹Ñ5ÕÑ…Ñ¥½¹%œé‘¥•ÍÐ¡ì‰•™½É”œé‰•™½É”°…™Ñ•Èœé…™Ñ•È°¥‘•¹Ñ¥ÑäœéÍ•±˜¹¥‘•¹Ñ¥Ñåô¤°(€€€€€€€€€€€€É•™UÁ‘…Ñ•Ìœél(€€€€€€€€€€€€€€€ì¹…µ”œèÉ•™Ì½¡•…‘Ì½µ…¥¸œ°‰•™½É•=¥œéÍ•±˜¹¥‘•¹Ñ¥Ñålµ…¥¹}Í¡„t°(€€€€€€€€€€€€€€€€€…™Ñ•É=¥œéÍ•±˜¹¥‘•¹Ñ¥Ñålµ…¥¹}Í¡„t°™½É”œé…±Í•ô°(€€€€€€€€€€€€€€€ì¹…µ”œÎÉ•™Ì½¡•…‘Ì½…ÕÑ½µ…Ñ¥½¸µÍÑ…Ñ”œ°‰•™½É•=¥œé‰•™½É”°…™Ñ•É=¥œé…™Ñ•È°™½É”œé…±Í•õuô(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ A=MPœ°œ½É…Á¡Å°œ±ìÅÕ•ÉäœéUAQ}IL°Ù…É¥…‰±•Ìœéì¥¹ÁÕÐœéÉ•ÅÕ•ÍÑõô¤(€€€€€€€¥˜É•ÍÕ±Ð¹•Ð •ÉÉ½ÉÌœ¤èÉ…¥Í”MÑ…Ñ•½¹™±¥Ð %Q!U	}a1UM%=9}I}M}I)Qœ¤(€€€€€€€¥˜É•ÍÕ±Ð¹•Ð ‘…Ñ„œ±íô¤¹•Ð ÕÁ‘…Ñ•I•™Ìœ±íô¤¹•Ð ±¥•¹Ñ5ÕÑ…Ñ¥½¹%œ¤€„ôÉ•ÅÕ•ÍÑl±¥•¹Ñ5ÕÑ…Ñ¥½¹%tè(€€€€€€€€€€€É…¥Í”¥Ñ!Õ‰ÉÉ½È¡9½¹”°¥Ð•á±ÕÍ¥½¸…­¹½Ý±•‘µ•¹Ðµ¥ÍÍ¥¹œì¥¹ÍÁ•Ð•á…ÐÉ•˜œ±Õ¹•ÉÑ…¥¸õQÉÕ”¤((€€€‘•˜…ÅÕ¥É”¡Í•±˜°½‰Í•ÉÙ•‘}É•˜¤è(€€€€€€€É•ÅÕ¥É•}Í¡„¡½‰Í•ÉÙ•‘}É•˜°ÐÀ¤(€€€€€€€É½Ü€ôÍ•±˜¹½‰Í•ÉÙ” ¤(€€€€€€€¥˜É½ÝlÕÉÉ•¹Ñ}É•˜t€„ô½‰Í•ÉÙ•‘}É•˜èÉ…¥Í”MÑ…Ñ•½¹™±¥Ð %Q!U	}A=!}I}MQ1œ¤(€€€€€€€¥˜É½Ýl…¹¡½ÈtèÉ•ÑÕÉ¸É½Ýl…¹¡½Èt(€€€€€€€±½…‘•€ôÍ•±˜¹É•…‘•È¹É•…‘}Í¹…ÁÍ¡½Ð ¤(€€€€€€€¹½}±•…å}¥¹¥‘•¹Ð¡±½…‘•¹ÍÑ…Ñ”¤(€€€€€€€¥˜€¡±½…‘•¹½µµ¥Ñ}Í¡„€„ô½‰Í•ÉÙ•‘}É•˜½È±½…‘•¹ÍÑ…Ñ”¹•Ð Í¡•µ…}Ù•ÉÍ¥½¸œ¤€„ô€Ô(€€€€€€€€€€€€€€€½È€¡…¹‘½Ù•Èœ¥¸±½…‘•¹ÍÑ…Ñ”½È€¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ¥¸±½…‘•¹ÍÑ…Ñ”¤è(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}%9%Q%1}M9AM!=Q}%9Y1%œ¤(€€€€€€€É•½É€ô‘¥Ð¡Í•±˜¹¥‘•¹Ñ¥Ñä±‰•™½É•}½¥õ½‰Í•ÉÙ•‘}É•˜±ÑÉ••}Í¡„õ±½…‘•¹ÑÉ••}Í¡„°(€€€€€€€€€€€€€€€€€€€€€É•˜ôÉ•™Ì½¡•…‘Ì½…ÕÑ½µ…Ñ¥½¸µÍÑ…Ñ”œ¤(€€€€€€€½µµ¥Ð€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ A=MPœ±Í•±˜¹…Á¤¬œ½¥Ð½½µµ¥ÑÌœ±ì(€€€€€€€€€€€€µ•ÍÍ…”œé9!=I}5MM­…¹½¹¥…±}©Í½¸¡É•½É¤¬ÑÉ•”œé±½…‘•¹ÑÉ••}Í¡„°Á…É•¹ÑÌœím½‰Í•ÉÙ•‘}É•™uô¥lÍ¡„t(€€€€€€€É•ÅÕ¥É•}Í¡„¡½µµ¥Ð°ÐÀ¤(€€€€€€€Í•±˜¹}…Ì¡½‰Í•ÉÙ•‘}É•˜±½µµ¥Ð¤(€€€€€€€…¹¡½È€ôÍ•±˜¹…ÕÑ¡½É¥Ñä ¤(€€€€€€€¥˜…¹¡½Él½µµ¥Ñ}Í¡„t€„ô½µµ¥ÐèÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}A=!}I	-}!9œ¤(€€€€€€€É•ÑÕÉ¸…¹¡½È((€€€‘•˜ÝÉ¥Ñ•}‘½Õµ•¹Ð¡Í•±˜°±½…‘•°ÁÉ½Á½Í•°€¨°µ•ÍÍ…”¤è(€€€€€€€€ˆˆ‰%¹Ñ•É¹…°ÁÉ¥µ¥Ñ¥Ù”¸…Ñ•Ý…äµÕÍÐ…ÕÑ¡½É¥é”Ñ¡”ÍÕÁÁ±¥•¹…ÉÉ½Ü¥¹Ñ•¹Ð¸((€€€€€€€)½ÕÉ¹…°…¹¥¹¥‘•¹Ð…±±•ÉÌÙ…±¥‘…Ñ”•á…Ð…±±½Ý•‘¥™™•É•¹•Ì™¥ÉÍÐ¸(€€€€€€€É•Í …¹¡½ÈÉ•…Á±ÕÌ…Ñ½µ¥ŒÉ•˜½µ…¥¸LÉ•©•ÑÌÍÑ…±”‘•Í•¹‘…¹ÑÌ¸(€€€€€€€€ˆˆˆ(€€€€€€€¥˜¹½Ð¥Í¥¹ÍÑ…¹”¡±½…‘•±M¹…ÁÍ¡½Ð¤½È±½…‘•¹ÍÑ½É•}­•ä€„ôÍ•±˜¹É•…‘•È¹ÍÑ½É•}­•äè(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}a1UM%=9}M9AM!=Q}%9Y1%œ¤(€€€€€€€Í•±˜¹…ÕÑ¡½É¥Ñä ¤(€€€€€€€É…Ü€ô€¡…¹½¹¥…±}©Í½¸¡ÁÉ½Á½Í•¤¬q¸œ¤¹•¹½‘” ¤(€€€€€€€‰±½ˆ€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ A=MPœ±Í•±˜¹…Á¤¬œ½¥Ð½‰±½‰Ìœ±ì½¹Ñ•¹Ðœé‰…Í”ØÐ¹ˆØÑ•¹½‘”¡É…Ü¤¹‘•½‘” ¤°•¹½‘¥¹œœè‰…Í”ØÐô¥lÍ¡„t(€€€€€€€¥˜‰±½ˆ€„ô¡…Í¡±¥ˆ¹Í¡„Ä¡ˆ‰±½ˆ€œ­ÍÑÈ¡±•¸¡É…Ü¤¤¹•¹½‘” ¤­ˆpÀœ­É…Ü¤¹¡•á‘¥•ÍÐ ¤è(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}a1UM%=9}]I%QQ9}	1=	}%9Y1%œ¤(€€€€€€€ÑÉ•”€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ A=MPœ±Í•±˜¹…Á¤¬œ½¥Ð½ÑÉ••Ìœ±ì‰…Í•}ÑÉ•”œé±½…‘•¹ÑÉ••}Í¡„°ÑÉ•”œémìÁ…Ñ œéÍ•±˜¹É•…‘•È¹Á…Ñ °µ½‘”œèœÄÀÀØÐÐœ°ÑåÁ”œè‰±½ˆœ°Í¡„œé‰±½‰õuô¥lÍ¡„t(€€€€€€€É•ÅÕ¥É•}Í¡„¡ÑÉ•”°ÐÀ¤(€€€€€€€½µµ¥Ð€ôÍ•±˜¹¥Ñ¡Õˆ¹É•ÅÕ•ÍÐ A=MPœ±Í•±˜¹…Á¤¬œ½¥Ð½½µµ¥ÑÌœ±ìµ•ÍÍ…”œéµ•ÍÍ…”°ÑÉ•”œéÑÉ•”°Á…É•¹ÑÌœém±½…‘•¹½µµ¥Ñ}Í¡…uô¥lÍ¡„t(€€€€€€€É•ÅÕ¥É•}Í¡„¡½µµ¥Ð°ÐÀ¤ìÍ•±˜¹…ÕÑ¡½É¥Ñä ¤ìÍ•±˜¹}…Ì¡±½…‘•¹½µµ¥Ñ}Í¡„±½µµ¥Ð¤(€€€€€€€É•ÑÕÉ¸M¹…ÁÍ¡½Ð¡½Áä¹‘••Á½Áä¡ÁÉ½Á½Í•¤±‰±½ˆ±±½…‘•¹ÍÑ½É•}­•ä±½µµ¥Ð±ÑÉ•”¤(()±…ÍÌ¥ÑÉ…¥¹)½ÕÉ¹…°è(€€€€ˆˆ‰=¹±ä‘É…¥¸±•‘•È¡…¹•Ì‰•™½É”AIAI°½¸Ñ¡”½É¥¥¹…°ÍÑ…Ñ”Á…Ñ ¸ˆˆˆ(€€€‘•˜}}¥¹¥Ñ}|¡Í•±˜°•Á½ ¤èÍ•±˜¹•Á½ €ô•Á½ ((€€€‘•˜É•…‘}Í¹…ÁÍ¡½Ð¡Í•±˜¤èÉ•ÑÕÉ¸Í•±˜¹•Á½ ¹É•…‘•È¹É•…‘}Í¹…ÁÍ¡½Ð ¤((€€€‘•˜¥¹¥Ñ¥…±¥é”¡Í•±˜¤è(€€€€€€€…¹¡½È€ôÍ•±˜¹•Á½ ¹…ÕÑ¡½É¥Ñä ¤ì±½…‘•€ôÍ•±˜¹É•…‘}Í¹…ÁÍ¡½Ð ¤(€€€€€€€¹½}±•…å}¥¹¥‘•¹Ð¡±½…‘•¹ÍÑ…Ñ”¤(€€€€€€€¥˜€¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ¥¸±½…‘•¹ÍÑ…Ñ”èÉ•ÑÕÉ¸Í•±˜¹±½… ¤(€€€€€€€¥˜±½…‘•¹½µµ¥Ñ}Í¡„€„ô…¹¡½Él½µµ¥Ñ}Í¡„tèÉ…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}a1UM%=9}U9aAQ}AI}1I}]I%Qœ¤(€€€€€€€ÁÉ½Á½Í•€ô½Áä¹‘••Á½Áä¡±½…‘•¹ÍÑ…Ñ”¤(€€€€€€€ÁÉ½Á½Í•‘l¥Ñ¡Õ‰}•á±ÕÍ¥½¸t€ôì•Á½ œé…¹¡½Él•Á½ t°…¹¡½Èœé…¹¡½Él½µµ¥Ñ}Í¡„t°(€€€€€€€€€€€€±•…å}‰½‘å}Í¡„ÈÔØœé‘¥•ÍÐ¡±½…‘•¹ÍÑ…Ñ”¤°‘É…¥¹Ìœéíõô(€€€€€€€É•ÑÕÉ¸Í•±˜¹•Á½ ¹ÝÉ¥Ñ•}‘½Õµ•¹Ð¡±½…‘•±ÁÉ½Á½Í•±µ•ÍÍ…”ôÍÑ…Ñ”è-•Í¡•È•á±ÕÍ¥½¸‘É…¥¸¥¹¥Ñ¥…±¥é•œ¤((€€€‘•˜±½…¡Í•±˜¤è(€€€€€€€…¹¡½È€ôÍ•±˜¹•Á½ ¹…ÕÑ¡½É¥Ñä ¤ì±½…‘•€ôÍ•±˜¹É•…‘}Í¹…ÁÍ¡½Ð ¤(€€€€€€€¹½}±•…å}¥¹¥‘•¹Ð¡±½…‘•¹ÍÑ…Ñ”¤(€€€€€€€±•‘•È€ô±½…‘•¹ÍÑ…Ñ”¹•Ð ¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ±íô¤(€€€€€€€¥˜€¡±•‘•È¹•Ð •Á½ œ¤€„ô…¹¡½Él•Á½ t½È±•‘•È¹•Ð …¹¡½Èœ¤€„ô…¹¡½Él½µµ¥Ñ}Í¡„t½È¹½Ð¥Í¥¹ÍÑ…¹”¡±•‘•È¹•Ð ‘É…¥¹Ìœ¤±‘¥Ð¤¤è(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}a1UM%=9}1I}%9Y1%œ¤(€€€€€€€¥˜€¡…¹‘½Ù•Èœ¹½Ð¥¸±½…‘•¹ÍÑ…Ñ”…¹‘¥•ÍÐ¡í¬éØ™½È¬±Ø¥¸±½…‘•¹ÍÑ…Ñ”¹¥Ñ•µÌ ¤¥˜¬€„ô€¥Ñ¡Õ‰}•á±ÕÍ¥½¸ô¤€„ô±•‘•È¹•Ð ±•…å}‰½‘å}Í¡„ÈÔØœ¤è(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}a1UM%=9}U9aAQ}1e}5UQQ%=8œ¤(€€€€€€€É•ÑÕÉ¸±½…‘•((€€€‘•˜Í…Ù”¡Í•±˜°±½…‘•°ÁÉ½Á½Í•¤è(€€€€€€€€ŒI”µÉ•…Ñ¡”±•‘•È…¹½Ý¹••Á½ ì¹•Ù•ÈÉ•‰¥¹„ÍÑ…±”Í¹…ÁÍ¡½Ð¸(€€€€€€€™É•Í €ôÍ•±˜¹±½… ¤(€€€€€€€¥˜™É•Í ¹½µµ¥Ñ}Í¡„€„ô±½…‘•¹½µµ¥Ñ}Í¡„èÉ…¥Í”MÑ…Ñ•½¹™±¥Ð %Q!U	}I%9}M9AM!=Q}MQ1œ¤(€€€€€€€½±°¹•Ü€ô±½…‘•¹ÍÑ…Ñ”¹•Ð ¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ¤°ÁÉ½Á½Í•¹•Ð ¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ¤(€€€€€€€¥˜€ ¡…¹‘½Ù•Èœ¥¸±½…‘•¹ÍÑ…Ñ”½È±½…‘•¹ÍÑ…Ñ”¹•Ð Í¡•µ…}Ù•ÉÍ¥½¸œ¤€„ô€Ô(€€€€€€€€€€€€€€€½Èí¬éØ™½È¬±Ø¥¸±½…‘•¹ÍÑ…Ñ”¹¥Ñ•µÌ ¤¥˜¬€„ô€¥Ñ¡Õ‰}•á±ÕÍ¥½¸ô€„ôí¬éØ™½È¬±Ø¥¸ÁÉ½Á½Í•¹¥Ñ•µÌ ¤¥˜¬€„ô€¥Ñ¡Õ‰}•á±ÕÍ¥½¸ô(€€€€€€€€€€€€€€€½È¹½Ð¥Í¥¹ÍÑ…¹”¡¹•Ü±‘¥Ð¤½ÈÍ•Ð¡¹•Ü¤€„ôÍ•Ð¡½±¤(€€€€€€€€€€€€€€€½Èí¬éØ™½È¬±Ø¥¸½±¹¥Ñ•µÌ ¤¥˜¬€„ô€‘É…¥¹Ìô€„ôí¬éØ™½È¬±Ø¥¸¹•Ü¹¥Ñ•µÌ ¤¥˜¬€„ô€‘É…¥¹Ìô(€€€€€€€€€€€€€€€½È¹½Ð¥Í¥¹ÍÑ…¹”¡¹•Ýl‘É…¥¹Ìt±‘¥Ð¤½È¹½ÐÍ•Ð¡½±‘l‘É…¥¹Ìt¤€ðôÍ•Ð¡¹•Ýl‘É…¥¹Ìt¤¤è(€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}I%9}]I%Q}=UQ}=}M=Aœ¤(€€€€€€€™½ÈÝ¥±•¹ÑÉä¥¸½±‘l‘É…¥¹Ìt¹¥Ñ•µÌ ¤è(€€€€€€€€€€€ÕÁ‘…Ñ•€ô¹•Ýl‘É…¥¹ÌumÝ¥‘t(€€€€€€€€€€€¥˜€¡ÕÁ‘…Ñ•¹•Ð •Á½ œ¤€„ô•¹ÑÉä¹•Ð •Á½ œ¤½ÈÕÁ‘…Ñ•¹•Ð Ý½É­™±½Ý}¥œ¤€„ô•¹ÑÉä¹•Ð Ý½É­™±½Ý}¥œ¤¤è(€€€€€€€€€€€€€€€É…¥Í”MÑ…Ñ•%¹Ù…±¥ %Q!U	}I%9}%9Q%Qe}!9œ¤(€€€€€€€™É½´€¹¥Ñ¡Õ‰}‘É…¥¸¥µÁ½ÉÐÙ…±¥‘…Ñ•}‘É…¥¹}ÑÉ…¹Í¥Ñ¥½¸(€€€€€€€Ù…±¥‘…Ñ•}‘É…¥¹}ÑÉ…¹Í¥Ñ¥½¸¡½±‘l‘É…¥¹Ìt±¹•Ýl‘É…¥¹Ìt¤(€€€€€€€É•ÑÕÉ¸Í•±˜¹•Á½ ¹ÝÉ¥Ñ•}‘½Õµ•¹Ð¡±½…‘•±ÁÉ½Á½Í•±µ•ÍÍ…”ôÍÑ…Ñ”è-•Í¡•È•á±ÕÍ¥½¸‘É…¥¸¡•­Á½¥¹Ðœ¤(()‘•˜É•½É‘}‘•¹¥•‘}±•…å}ÝÉ¥Ñ”¡•Á½ °€¨°…Ñ½È°ÁÉ½Á½Í•°‰•™½É•}Í¡„°¹½Ü¤è(€€€€ˆˆ‰QÉÕÍÑ•…Ñ•Ý…ä¡½½¬…™Ñ•È…ÕÑ¡•¹Ñ¥…Ñ•±•…äÝÉ¥Ñ”‘•¹¥…°¸((€€€%Ð‘½•Ì¹½Ð•á•ÕÑ”½ÈÉ•ÑÉäÑ¡”…ÑÑ•µÁÑ•ÝÉ¥Ñ”¸¸¥¹¥‘•¹ÐLÉ•ÍÁ½¹Í”(€€€±½ÍÌ¥ÌÉ•½¹¥±•‰äÍÑ…‰±”¥¹¥‘•¹Ð¥‘•¹Ñ¥Ñä½¸„±…Ñ•È¥¹Ù½…Ñ¥½¸¸L(€€€½¹™±¥Ð‰±½­ÌÑ¡”…Ñ•Ý…äÕ¹Ñ¥°•á…Ð¥¹¥‘•¹ÐÁ•ÉÍ¥ÍÑ•¹”¥ÌÉ•…‰…¬¸(€€€€ˆˆˆ(€€€™É½´€¹±•…å}É•Ñ¥É•µ•¹Ð¥µÁ½ÉÐÉ•½É‘}±•…å}É•©•Ñ¥½¸(€€€•Á½ ¹…ÕÑ¡½É¥Ñä ¤ì±½…‘•€ô•Á½ ¹É•…‘•È¹É•…‘}Í¹…ÁÍ¡½Ð ¤(€€€¥˜€¥Ñ¡Õ‰}•á±ÕÍ¥½¸œ¹½Ð¥¸±½…‘•¹ÍÑ…Ñ”…¹€¡…¹‘½Ù•Èœ¹½Ð¥¸±½…‘•¹ÍÑ…Ñ”è(€€€€€€€±½…‘•€ô¥ÑÉ…¥¹)½ÕÉ¹…°¡•Á½ ¤¹¥¹¥Ñ¥…±¥é” ¤(€€€É•½É‘•€ôÉ•½É‘}±•…å}É•©•Ñ¥½¸¡±½…‘•¹ÍÑ…Ñ”±…Ñ½Èõ…Ñ½È±•Á½ õ•Á½ ¹¥‘•¹Ñ¥Ñål•Á½ t°(€€€€€€€ÁÉ½Á½Í•õÁÉ½Á½Í•±‰•™½É•}Í¡„õ‰•™½É•}Í¡„±ÕÉÉ•¹Ñ}Í¡„õ±½…‘•¹½µµ¥Ñ}Í¡„±¹½Üõ¹½Ü¤(€€€¥˜É•½É‘•€ôô±½…‘•¹ÍÑ…Ñ”èÉ•ÑÕÉ¸±½…‘•(€€€É•ÑÕÉ¸•Á½ ¹ÝÉ¥Ñ•}‘½Õµ•¹Ð¡±½…‘•±É•½É‘•±µ•ÍÍ…”ôÍÑ…Ñ”èÉ•©•Ñ•±•…ä…ÕÑ¡½É¥Ñä¥¹¥‘•¹Ðœ¤(()±…ÍÌ¥Ñ!Õ‰I•Í½ÕÉ•á±ÕÍ¥½¸è(€€€€ˆˆ‰½µÁ½Í”É•…°•Á½ L°•á…ÐÑ¥½¹Ì‘É…¥¸…¹„ÑÉÕÍÑ•‘•¹ä…Ñ•Ý…ä¸((€€€Õ…É‘€€¥Ì…¸¥¹‘•Á•¹‘•¹Ñ±ä¥¹ÍÑ…±±•°…ÕÑ¡•¹Ñ¥…Ñ•É•Í½ÕÉ”•¹‘Á½¥¹Ð(€€€¥µÁ±•µ•¹Ñ¥¹œ¥¹ÍÁ•Ð½•á±Õ‘”ì¥ÐµÕÍÐÉ•Ù½­”½±Ý½É­™±½Ü½…ÁÀ½AP½‘•Á±½äµ­•ä(€€€É…¹ÑÌ…¹•¹™½É”¹…ÉÉ½Ü¥Ð½Ñ¥½¹Ì½Á•É…Ñ¥½¹Ì…ÐÑ¡”…ÑÕ…°•¹‘Á½¥¹ÑÌ¸(€€€9½Ñ¡¥¹œ¥¸Ñ¡¥Ì…‘…ÁÑ•È™…‰É¥…Ñ•ÌÑ¡…Ð•¹™½É•µ•¹Ð¸9¼Õ…É°Á…ÉÑ¥…°(€€€É•Ù½…Ñ¥½¸°Õ¹­¹½Ý¸É•¥ÍÑÉ…Ñ¥½¸½ÈÍÑ…±”ÉÕ¸µ•…¹Ì¹¼•á±ÕÍ¥½¸É••¥ÁÐ¸(€€€É•¥ÍÑ•É•‘€É•ÑÕÉ¹Ì¥¹‘•Á•¹‘•¹Ñ±äÉ•Ù¥•Ý••á…Ð%½Á…Ñ ‰¥¹‘¥¹ÌìÑ¡”(€€€Ñ¥½¹ÌÉ•…‘•È½µÁ…É•Ì¥ÑÌ½µÁ±•Ñ”¥¹Ù•¹Ñ½Éä……¥¹ÍÐÑ¡•´½¸•Ù•ÉäÍÑ•À¸(€€€€ˆˆˆ(€€€‘•˜}}¥¹¥Ñ}|¡Í•±˜°¥Ñ¡Õˆ°É•Á¼°€¨°µ…¥¹}Í¡„°Á½±¥ä°ÉÕ±•Ì°É•¥ÍÑ•É•°Õ…É°Í•Á…É…Ñ¥½¸õ9½¹”°(€€€€€€€€€€€€€€€€Í•Á…É…Ñ¥½¹}‰¥¹‘¥¹œõ9½¹”°ÁÉ½Ñ•Ñ•‘}É•Í½ÕÉ•Ìõ9½¹”¤è(€€€€€€€™É½´€¹¥Ñ¡Õ‰}‘É…¥¸¥µÁ½ÉÐ¥Ñ¡Õ‰É…¥¸(€€€€€€€™É½´€¹…ÕÑ¡½É¥Ñå}Ñ½Á½±½ä¥µÁ½ÉÐÙ…±¥‘…Ñ•}É•¥ÍÑ•É•‘}¥¹Ù•¹Ñ½Éä(€€€€€€€™É½´€¹•á±ÕÍ¥½¸¥µÁ½ÉÐIEU%I}IM=UIL°9=9%1}Q°=9QI=1}Q(€€€€€€€‰…Í•}­•åÌ€ôìÉ•Á¼œ°É•Í½ÕÉ”œ°É•Í½ÕÉ•}¥œ°•Á½ œ°½Ý¹•Èœ°‘•™…Õ±Ñ}…ÕÑ¡½É¥Ñäœ°(€€€€€€€€€€€€€€€€€€€€€ÁÉ½Ñ•Ñ¥½¹}µ•Ñ¡½œ°ÁÉ•‘••ÍÍ½É}…ÕÑ¡½É¥Ñå}‘•¹¥•œ°½Ù•É•‘}É•‘•¹Ñ¥…±}±…ÍÍ•Ìœ°(€€€€€€€€€€€€€€€€€€€€€…¹½¹¥…±}…Ñ”œ°½¹ÑÉ½±}…Ñ”ô(€€€€€€€µ•Ñ¡½€ôÁ½±¥ä¹•Ð ÁÉ½Ñ•Ñ¥½¹}µ•Ñ¡½œ¤(€€€€€€€•áÁ•Ñ•‘}­•åÌ€ô‰…Í•}­•åÌð€¡ìMÄ