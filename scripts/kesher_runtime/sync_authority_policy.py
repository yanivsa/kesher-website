#!/usr/bin/env python3
"""Explicit offline recertification of reviewed authority hash leaves.

Never invoked by production runtime. Updating hashes is not a capability review;
unknown definitions, missing inputs and symlink inputs refuse without any write.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def _input(root, name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'AUTHORITY_INPUT_UNSAFE: {name}')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'AUTHORITY_INPUT_SYMLINK: {name}')
    if not current.is_file():
        raise ValueError(f'AUTHORITY_INPUT_MISSING: {name}')
    return hashlib.sha256(current.read_bytes()).hexdigest()


def synchronize(root, *, update=False):
    root = Path(root).resolve()
    path = root / 'scripts/kesher_runtime/authority_policy.json'
    original = path.read_bytes()
    rules = json.loads(original)
    governed = rules['workflows']
    actual = {str(p.relative_to(root)) for p in (root/'.github/workflows').glob('*.y*ml')}
    if actual != set(governed):
        raise ValueError(f'AUTHORITY_DEFINITION_SET_MISMATCH: unknown={sorted(actual-set(governed))} missing={sorted(set(governed)-actual)}')
    changes = []
    def pin(container, key, file, location):
        value = _input(root, file)
        if container[key] != value:
            changes.append({'location':location,'path':file,'old':container[key],'new':value})
            container[key] = value
    for workflow, entry in sorted(governed.items()):
        pin(entry,'definition_sha256',workflow,f'{workflow}.definition_sha256')
        review = entry['review']
        for file in sorted(review.get('call_chain',{})):
            pin(review['call_chain'],file,file,f'{workflow}.review.call_chain[{file}]')
        for child, binding in sorted(review.get('dispatch_bindings',{}).items()):
            if child not in governed:
                raise ValueError(f'AUTHORITY_UNREVIEWED_CHILD: {workflow} -> {child}')
            pin(binding,'definition_sha256',child,f'{workflow}.review.dispatch_bindings[{child}].definition_sha256')
    if update and changes:
        if path.read_bytes() != original:
            raise ValueError('AUTHORITY_POLICY_CHANGED_DURING_SYNC')
        encoded = (json.dumps(rules,ensure_ascii=False,indent=2)+'\n').encode()
        fd, temporary = tempfile.mkstemp(prefix='.authority-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as handle:
                handle.write(encoded);handle.flush();os.fsync(handle.fileno())
            os.chmod(temporary,path.stat().st_mode & 0o777)
            os.replace(temporary,path)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true');mode.add_argument('--update',action='store_true')
    args=parser.parse_args()
    try:
        changes=synchronize(args.root,update=args.update)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(str(exc));return 2
    print(json.dumps({'status':'updated' if args.update else 'stale' if changes else 'matching','changes':changes},indent=2))
    return 1 if changes and not args.update else 0

if __name__=='__main__':
    raise SystemExit(main())
