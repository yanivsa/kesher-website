#!/usr/bin/env python3
from pathlib import Path

policy_path = Path('.github/prompts/jules-remotion-video-upgrade.md')
policy = policy_path.read_text(encoding='utf-8')
heading = '# Durable Repo Policy: Kesher Remotion Video Upgrade & Review Policy\n'
replacement = heading + '\nPolicy-Version: 1\n'
if policy.count(heading) != 1:
    raise SystemExit('policy heading target not unique')
if 'Policy-Version:' not in policy:
    policy = policy.replace(heading, replacement, 1)
policy_path.write_text(policy, encoding='utf-8')

path = Path('scripts/jules_video_reviewer.py')
text = path.read_text(encoding='utf-8')

constants = 'REMOTION_POLICY_PATH = PROJECT_DIR / ".github" / "prompts" / "jules-remotion-video-upgrade.md"\n'
constants_new = constants + 'REVIEW_SCHEMA_VERSION = 1\nREMOTION_POLICY_VERSION = 1\n'
if 'REVIEW_SCHEMA_VERSION = ' not in text:
    if text.count(constants) != 1:
        raise SystemExit('reviewer constants target not unique')
    text = text.replace(constants, constants_new, 1)

old_loader = '''    if not policy:\n        raise ReviewError("Durable Remotion policy is empty")\n    return policy\n'''
new_loader = '''    if not policy:\n        raise ReviewError("Durable Remotion policy is empty")\n    versions = re.findall(r"(?m)^Policy-Version:\\s*(\\d+)\\s*$", policy)\n    if versions != [str(REMOTION_POLICY_VERSION)]:\n        raise ReviewError(\n            f"Durable Remotion policy version mismatch: expected {REMOTION_POLICY_VERSION}, found {versions}"\n        )\n    return policy\n'''
if 'Durable Remotion policy version mismatch' not in text:
    if text.count(old_loader) != 1:
        raise SystemExit('policy loader target not unique')
    text = text.replace(old_loader, new_loader, 1)

old_start = '''    return {\n        "item_id": item_id,\n'''
new_start = '''    return {\n        "schema_version": REVIEW_SCHEMA_VERSION,\n        "policy_version": REMOTION_POLICY_VERSION,\n        "item_id": item_id,\n'''
if text.count(old_start) != 1:
    raise SystemExit('review json start target not unique')
text = text.replace(old_start, new_start, 1)

old_obs = '''        "frame_observations": observations,\n        "visual_status": "approved or rejected",\n'''
new_obs = '''        "frame_observations": observations,\n        "decision": "approved or rejected",\n        "blocking_issues": [],\n        "recommendations": [],\n        "visual_status": "approved or rejected",\n'''
if text.count(old_obs) != 1:
    raise SystemExit('review json contract target not unique')
text = text.replace(old_obs, new_obs, 1)

old_important = '''IMPORTANT: Jules is a MANDATORY reviewer and strict publication gate. A video must not be uploaded unless the visual, semantic, and metadata gates are explicitly approved.\n\nApply these mandatory review dimensions:\n'''
new_important = '''IMPORTANT: Jules is a MANDATORY reviewer and strict publication gate. A video must not be uploaded unless the visual, semantic, and metadata gates are explicitly approved.\n\nMachine contract: return `schema_version={REVIEW_SCHEMA_VERSION}` and `policy_version={REMOTION_POLICY_VERSION}` exactly. `decision` MUST be `approved` only when visual, semantic and metadata statuses are all approved; otherwise it MUST be `rejected`. A rejected decision MUST contain at least one concrete `blocking_issues` object with `gate`, stable uppercase `code`, and factual Hebrew `message`. An approved decision MUST have an empty `blocking_issues` list. `recommendations` are optional non-blocking Hebrew improvements and never substitute for blocking issues.\n\nApply these mandatory review dimensions:\n'''
if text.count(old_important) != 1:
    raise SystemExit('prompt machine contract target not unique')
text = text.replace(old_important, new_important, 1)

marker = '\n\ndef obtain_validated_decision(\n'
contract_fn = r'''

def validate_structured_contract(decision: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version", "policy_version", "item_id",
        "manifest_sha256", "final_sha256", "transcript_sha256",
        "source_file_sha256", "visual_review_sha256", "frame_sha256",
        "frame_observations", "decision", "blocking_issues", "recommendations",
        "visual_status", "semantic_status", "metadata_status",
        "visual_note", "semantic_note", "metadata_note",
    }
    actual_keys = set(decision)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ReviewError(f"Jules review schema keys mismatch: missing={missing} extra={extra}")
    if decision.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ReviewError("Jules review schema_version mismatch")
    if decision.get("policy_version") != REMOTION_POLICY_VERSION:
        raise ReviewError("Jules review policy_version mismatch")

    statuses = [decision.get(f"{gate}_status") for gate in ("visual", "semantic", "metadata")]
    expected_decision = "approved" if statuses == ["approved", "approved", "approved"] else "rejected"
    if decision.get("decision") != expected_decision:
        raise ReviewError("Jules top-level decision is inconsistent with gate statuses")

    issues = decision.get("blocking_issues")
    if not isinstance(issues, list):
        raise ReviewError("Jules blocking_issues must be a list")
    if expected_decision == "approved" and issues:
        raise ReviewError("Approved Jules review must have no blocking_issues")
    if expected_decision == "rejected" and not issues:
        raise ReviewError("Rejected Jules review must include blocking_issues")
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != {"gate", "code", "message"}:
            raise ReviewError("Each Jules blocking issue must contain exactly gate, code and message")
        if issue.get("gate") not in {"visual", "semantic", "metadata"}:
            raise ReviewError("Jules blocking issue has invalid gate")
        if not isinstance(issue.get("code"), str) or not re.fullmatch(r"[A-Z0-9_]{3,64}", issue["code"]):
            raise ReviewError("Jules blocking issue code is invalid")
        message = issue.get("message")
        if not isinstance(message, str) or len(re.findall(r"[\u0590-\u05ff]", message)) < 8:
            raise ReviewError("Jules blocking issue message must be substantive Hebrew")

    recommendations = decision.get("recommendations")
    if not isinstance(recommendations, list) or len(recommendations) > 8:
        raise ReviewError("Jules recommendations must be a list of at most 8 items")
    for recommendation in recommendations:
        if not isinstance(recommendation, str) or len(re.findall(r"[\u0590-\u05ff]", recommendation)) < 8:
            raise ReviewError("Each Jules recommendation must be substantive Hebrew")
'''
if 'def validate_structured_contract(' not in text:
    if text.count(marker) != 1:
        raise SystemExit('contract function insertion marker not unique')
    text = text.replace(marker, contract_fn + marker, 1)

old_validate = '''            decision = parse_decision(message)\n            validate_decision(decision, item, hashes)\n            return decision, session\n'''
new_validate = '''            decision = parse_decision(message)\n            validate_decision(decision, item, hashes)\n            validate_structured_contract(decision)\n            return decision, session\n'''
if 'validate_structured_contract(decision)' not in text:
    if text.count(old_validate) != 1:
        raise SystemExit('runtime schema validation target not unique')
    text = text.replace(old_validate, new_validate, 1)

path.write_text(text, encoding='utf-8')
