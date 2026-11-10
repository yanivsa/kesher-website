#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "chatgpt-plugin"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the skills-only ChatGPT plugin ZIP.")
    parser.add_argument(
        "--output",
        default=str(ROOT / "dist-artifacts" / "kesher-shira-saharoni-plugin.zip"),
        help="Output ZIP path",
    )
    args = parser.parse_args()

    output = Path(args.output).resolve()
    if not PLUGIN_ROOT.exists():
        raise SystemExit(f"Missing plugin root: {PLUGIN_ROOT}")

    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in PLUGIN_ROOT.rglob("*") if path.is_file())
    if not files:
        raise SystemExit("Plugin package is empty")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, source.relative_to(PLUGIN_ROOT).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())
        if "plugin.json" not in names:
            raise SystemExit("Built ZIP is missing plugin.json at archive root")
        if not any(name.startswith("skills/") and name.endswith("/SKILL.md") for name in names):
            raise SystemExit("Built ZIP contains no skill manifests")
        forbidden = {"mcp.json", ".mcp.json", ".app.json"}
        if names.intersection(forbidden):
            raise SystemExit("Skills-only ZIP unexpectedly contains MCP/app configuration")

    print(output)


if __name__ == "__main__":
    main()
