#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import oci

DG_NAME = "OpenClawRunCommandInstances"
POLICY_NAME = "OpenClawRunCommandPolicy"
DESCRIPTION = "Least-privilege OCI Run Command execution policy for disposable OpenClaw maintenance instances"


def wait_dynamic_group(identity, dynamic_group_id: str, timeout: int = 180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = identity.get_dynamic_group(dynamic_group_id).data
        if obj.lifecycle_state == "ACTIVE":
            return obj
        if obj.lifecycle_state in {"DELETED", "DELETING"}:
            raise RuntimeError(f"OPENCLAW_RUN_COMMAND_DG_BAD_STATE_{obj.lifecycle_state}")
        time.sleep(3)
    raise TimeoutError("OPENCLAW_RUN_COMMAND_DG_ACTIVE_TIMEOUT")


def ensure_dynamic_group(identity, tenancy_id: str):
    desired_rule = f"ALL {{instance.compartment.id = '{tenancy_id}'}}"
    rows = identity.list_dynamic_groups(
        compartment_id=tenancy_id,
        name=DG_NAME,
    ).data
    rows = [x for x in rows if x.lifecycle_state not in {"DELETED", "DELETING"}]

    if not rows:
        obj = identity.create_dynamic_group(
            oci.identity.models.CreateDynamicGroupDetails(
                compartment_id=tenancy_id,
                name=DG_NAME,
                description=DESCRIPTION,
                matching_rule=desired_rule,
            )
        ).data
        obj = wait_dynamic_group(identity, obj.id)
        print("OPENCLAW_RUN_COMMAND_DYNAMIC_GROUP_CREATED=true", flush=True)
        return obj

    obj = rows[0]
    if obj.matching_rule != desired_rule or obj.description != DESCRIPTION:
        obj = identity.update_dynamic_group(
            obj.id,
            oci.identity.models.UpdateDynamicGroupDetails(
                description=DESCRIPTION,
                matching_rule=desired_rule,
            ),
        ).data
        obj = wait_dynamic_group(identity, obj.id)
        print("OPENCLAW_RUN_COMMAND_DYNAMIC_GROUP_UPDATED=true", flush=True)
    else:
        obj = wait_dynamic_group(identity, obj.id)
        print("OPENCLAW_RUN_COMMAND_DYNAMIC_GROUP_EXISTS=true", flush=True)
    return obj


def ensure_policy(identity, tenancy_id: str):
    statement = (
        f"Allow dynamic-group {DG_NAME} to use "
        "instance-agent-command-execution-family in tenancy "
        "where request.instance.id=target.instance.id"
    )
    rows = identity.list_policies(
        compartment_id=tenancy_id,
        name=POLICY_NAME,
    ).data
    rows = [x for x in rows if x.lifecycle_state not in {"DELETED", "DELETING"}]

    if not rows:
        identity.create_policy(
            oci.identity.models.CreatePolicyDetails(
                compartment_id=tenancy_id,
                name=POLICY_NAME,
                description=DESCRIPTION,
                statements=[statement],
            )
        )
        print("OPENCLAW_RUN_COMMAND_POLICY_CREATED=true", flush=True)
    else:
        obj = rows[0]
        if list(obj.statements or []) != [statement] or obj.description != DESCRIPTION:
            identity.update_policy(
                obj.id,
                oci.identity.models.UpdatePolicyDetails(
                    description=DESCRIPTION,
                    statements=[statement],
                ),
            )
            print("OPENCLAW_RUN_COMMAND_POLICY_UPDATED=true", flush=True)
        else:
            print("OPENCLAW_RUN_COMMAND_POLICY_EXISTS=true", flush=True)

    # OCI documents that new IAM policies typically take effect within about
    # ten seconds. The helper is deliberately created only after this pause, so
    # it belongs to the dynamic group from its first agent poll.
    time.sleep(15)
    print("OPENCLAW_RUN_COMMAND_IAM_READY=true", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(cfg)
    tenancy_id = cfg["tenancy"]
    identity = oci.identity.IdentityClient(cfg)

    ensure_dynamic_group(identity, tenancy_id)
    ensure_policy(identity, tenancy_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
