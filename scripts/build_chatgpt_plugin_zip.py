#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugin"


def package_files() -> list[Path]:
    roots = [
        PLUGIN_ROOT / "plugin.json",
        PLUGIN_ROOT / "mcp.json",
        PLUGIN_ROOT / "README.md",
    ]
    files = [path for path in roots if path.is_file()]
    for dirname in ("assets", "skills"):
        base = PLUGIN_ROOT / dirname
        if base.exists():
            files.extend(path for path in base.rglob("*") if path.is_file())
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical Kesher V2 ChatGPT plugin ZIP.")
    parser.add_argument(
        "--output",
        default=str(ROOT / "dist-artifacts" / "kesher-chatgpt-plugin-v2.zip"),
        help="Output ZIP path",
    )
    args = parser.parse_args()

    if not PLUGIN_ROOT.exists():
        raise SystemExit(f"Missing plugin root: {PLUGIN_ROOT}")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = package_files()
    if not files:
        raise SystemExit("Plugin package is empty")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, source.relative_to(PLUGIN_ROOT).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())
        required = {"plugin.json", "mcp.json"}
        missing = required - names
        if missing:
            raise SystemExit(f"Built ZIP is missing required files: {sorted(missing)}")
        skill_manifests = [name for name in names if name.startswith("skills/") and name.endswith("/SKILL.md")]
        if len(skill_manifests) != 3:
            raise SystemExit(f"Expected exactly 3 skill manifests; got {len(skill_manifests)}")
        forbidden_prefixes = ("src/", "tests/", "node_modules/", ".wrangler")
        if any(name.startswith(forbidden_prefixes) for name in names):
            raise SystemExit("Public plugin ZIP unexpectedly contains runtime/test dependencies")

    print(output)


if __name__ == "__main__":
    main()
