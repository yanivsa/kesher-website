#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import oci

TERMINAL={"SUCCEEDED","FAILED","TIMED_OUT","CANCELED","EXPIRED"}
PLUGIN="Compute Instance Run Command"

def find_instance(compute, compartment_id, name):
    rows=compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live=[x for x in rows if x.lifecycle_state not in {"TERMINATED","TERMINATING"}]
    if not live: raise RuntimeError("OPENCLAW_DIAG_INSTANCE_NOT_FOUND")
    live.sort(key=lambda x:x.time_created, reverse=True)
    return live[0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--instance-name", required=True)
    ap.add_argument("--timeout", type=int, default=180)
    args=ap.parse_args()
    cfg=oci.config.from_file(args.config,"DEFAULT"); oci.config.validate_config(cfg)
    compartment=cfg["tenancy"]
    compute=oci.core.ComputeClient(cfg)
    agent=oci.compute_instance_agent.ComputeInstanceAgentClient(cfg)
    plugins=oci.compute_instance_agent.PluginClient(cfg)
    inst=find_instance(compute,compartment,args.instance_name)
    print(f"OCI_AGENT_DIAG_INSTANCE_STATE={inst.lifecycle_state}",flush=True)
    print(f"OCI_AGENT_DIAG_INSTANCE_ID={inst.id}",flush=True)
    try:
        p=plugins.get_instance_agent_plugin(instanceagent_id=inst.id, compartment_id=compartment, plugin_name=PLUGIN).data
        print(f"OCI_AGENT_DIAG_PLUGIN_STATUS={getattr(p,'status',None) or 'UNKNOWN'}",flush=True)
    except oci.exceptions.ServiceError as exc:
        print(f"OCI_AGENT_DIAG_PLUGIN_STATUS=ERROR_{exc.status}",flush=True)
    script=Path(args.script_file).read_text()
    details=oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment,
        execution_time_out_in_seconds=args.timeout,
        display_name="openclaw-readonly-diagnostic",
        target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(instance_id=inst.id),
        content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
            source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(source_type="TEXT", text=script),
            output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(output_type="TEXT"),
        ),
    )
    created=agent.create_instance_agent_command(details).data
    print(f"OCI_AGENT_DIAG_COMMAND_ID={created.id}",flush=True)
    deadline=time.time()+args.timeout+60
    last=None
    while time.time()<deadline:
        try:
            ex=agent.get_instance_agent_command_execution(instance_agent_command_id=created.id, instance_id=inst.id).data
        except oci.exceptions.ServiceError as exc:
            if exc.status==404:
                time.sleep(5); continue
            raise
        state=getattr(ex,"lifecycle_state",None); delivery=getattr(ex,"delivery_state",None)
        if (state,delivery)!=last:
            print(f"OCI_AGENT_DIAG_STATE={state} delivery={delivery}",flush=True); last=(state,delivery)
        content=getattr(ex,"content",None)
        exit_code=getattr(content,"exit_code",None) if content else None
        if state in TERMINAL or exit_code is not None:
            text=getattr(content,"text","") or ""; message=getattr(content,"message","") or ""
            print(f"OCI_AGENT_DIAG_EXIT_CODE={exit_code}",flush=True)
            if message: print("OCI_AGENT_DIAG_MESSAGE="+json.dumps(message[:1000]),flush=True)
            print("OCI_AGENT_DIAG_OUTPUT_BEGIN",flush=True); print(text,flush=True); print("OCI_AGENT_DIAG_OUTPUT_END",flush=True)
            return 0 if exit_code in (None,0) and state not in {"FAILED","TIMED_OUT","CANCELED","EXPIRED"} else 2
        time.sleep(5)
    print("OCI_AGENT_DIAG_TIMEOUT=true",flush=True)
    return 3

if __name__=="__main__": raise SystemExit(main())
