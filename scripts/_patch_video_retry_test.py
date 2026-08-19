#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/jules_video_reviewer.py')
text = path.read_text(encoding='utf-8')
old_signature = '''def validate_decision(decision: dict[str, Any], item: dict[str, Any], hashes: dict[str, Any]) -> None:\n'''
new_signature = '''def validate_decision(\n    decision: dict[str, Any],\n    item: dict[str, Any],\n    hashes: dict[str, Any],\n    *,\n    strict_schema: bool = False,\n) -> None:\n'''
if text.count(old_signature) != 1:
    raise SystemExit('validate_decision signature target not unique')
text = text.replace(old_signature, new_signature, 1)
old_tail = '''        if not isinstance(note, str) or len(re.findall(r"[\\u0590-\\u05ff]", note)) < 12:\n            raise ReviewError(f"Jules returned a weak or non-Hebrew {gate} note")\n\n\ndef validate_structured_contract'''
new_tail = '''        if not isinstance(note, str) or len(re.findall(r"[\\u0590-\\u05ff]", note)) < 12:\n            raise ReviewError(f"Jules returned a weak or non-Hebrew {gate} note")\n    if strict_schema:\n        validate_structured_contract(decision)\n\n\ndef validate_structured_contract'''
if text.count(old_tail) != 1:
    raise SystemExit('validate_decision tail target not unique')
text = text.replace(old_tail, new_tail, 1)
old_runtime = '''            validate_decision(decision, item, hashes)\n            validate_structured_contract(decision)\n            return decision, session\n'''
new_runtime = '''            validate_decision(decision, item, hashes, strict_schema=True)\n            return decision, session\n'''
if text.count(old_runtime) != 1:
    raise SystemExit('runtime validation target not unique')
path.write_text(text.replace(old_runtime, new_runtime, 1), encoding='utf-8')
