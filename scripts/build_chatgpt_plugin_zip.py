#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugin"
INCLUDE_ROOT_FILES = ("plugin.json", "mcp.json")
INCLUDE_DIRS = ("skills", "assets")


def iter_package_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_ROOT_FILES:
        path = PLUGIN_ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing required plugin file: {path}")
        files.append(path)

    for dirname in INCLUDE_DIRS:
        root = PLUGIN_ROOT / dirname
        if not root.is_dir():
            raise SystemExit(f"Missing required plugin directory: {root}")
        files.extend(sorted(path for path in root.rglob("*") if path.is_file()))

    return sorted(set(files))


def validate_archive(names: set[str]) -> None:
    if "plugin.json" not in names:
        raise SystemExit("Built ZIP is missing plugin.json at archive root")
    if "mcp.json" not in names:
        raise SystemExit("Built ZIP is missing mcp.json at archive root")
    if not any(name.startswith("skills/") and name.endswith("/SKILL.md") for name in names):
        raise SystemExit("Built ZIP contains no skill manifests")
    if not any(name.startswith("assets/") for name in names):
        raise SystemExit("Built ZIP contains no assets")

    forbidden_prefixes = (
        "src/",
        "tests/",
        "contracts/",
        "evals/",
        "review/",
        "data/",
    )
    forbidden_files = {"package.json", "package-lock.json", "wrangler.jsonc"}
    leaked = sorted(
        name
        for name in names
        if name in forbidden_files or any(name.startswith(prefix) for prefix in forbidden_prefixes)
    )
    if leaked:
        raise SystemExit(f"Built ZIP includes non-portable implementation files: {leaked}")

    with (PLUGIN_ROOT / "plugin.json").open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    with (PLUGIN_ROOT / "mcp.json").open("r", encoding="utf-8") as fh:
        mcp = json.load(fh)

    if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        raise SystemExit("Unexpected plugin.json schema")
    if mcp.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json":
        raise SystemExit("Unexpected mcp.json schema")
    servers = mcp.get("mcpServers") or {}
    if set(servers) != {"kesher"}:
        raise SystemExit(f"Expected exactly one bundled MCP server named kesher, got: {sorted(servers)}")
    server = servers["kesher"]
    if server.get("type") != "streamable-http":
        raise SystemExit("Kesher MCP server must use streamable-http")
    url = server.get("url", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SystemExit("Kesher MCP server URL must be HTTPS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical Kesher V2 Agent Plugin ZIP.")
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
    files = iter_package_files()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, source.relative_to(PLUGIN_ROOT).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())
        validate_archive(names)

    print(output)


if __name__ == "__main__":
    main()
