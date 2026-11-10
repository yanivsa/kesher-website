#!/usr/bin/env python3
"""Read-only offline replay of the September 17 article contract gaps.

Run from any directory. Requires the cached pulls.json and PR Git objects from
the forensic inventory. No API request, provider operation, repository mutation,
or credential is used. Run against the audited 55563f42 checkout to reproduce
the original failures; against repaired code the observations may change.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
PR804_HEAD = "fdd61ce839ad93f90c142a355bffe733df5d46f7"
PR804_BASE = "7ce3bdc2ed6260277a3424f17f8cdd8e36a25ea7"
PR804_IMAGE_COMMITS = [
    "a578b9f0e7921917cdf27d49c1101fb9c6e82148",
    "db5598a37f8d2cd5b6aa7230cfd8b58844d73e4f",
    PR804_HEAD,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--cache-root", type=Path,
                        default=Path.home() / ".codex/tmp/kesher-forensics-20260917")
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))

    def git_bytes(ref: str, path: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(repo), "show", f"{ref}:{path}"],
                                       stderr=subprocess.DEVNULL)

    def posts(ref: str) -> list[dict]:
        return json.loads(git_bytes(ref, "src/data/posts.json"))

    def load(relative: str, name: str):
        spec = importlib.util.spec_from_file_location(name, repo / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    pulls = json.loads((args.cache_root / "pulls.json").read_text())
    cached = next(p for p in pulls if p["number"] == 804)
    if cached["headRefOid"] != PR804_HEAD:
        raise SystemExit("Fixture drift: use the captured September 17 pulls.json, not a fresh API response")
    base_posts, head_posts = posts(PR804_BASE), posts(PR804_HEAD)
    base_ids = {p["id"] for p in base_posts}
    new_posts = [p for p in head_posts if p["id"] not in base_ids]
    assert len(new_posts) == 1
    post = new_posts[0]
    pr = {
        "number": 804, "state": "open", "draft": cached["isDraft"],
        "title": cached["title"], "body": cached["body"],
        "base": {"sha": PR804_BASE, "ref": "main", "repo": {"full_name": "yanivsa/kesher-website"}},
        "head": {"sha": PR804_HEAD, "ref": cached["headRefName"], "repo": {"full_name": "yanivsa/kesher-website"}},
    }
    files = [{"filename": p["path"]} for p in cached["files"]["nodes"]]

    def image_bytes(entry: dict) -> bytes:
        if "filename" in entry:
            return git_bytes(PR804_HEAD, entry["filename"])
        path = entry["raw_url"].split("/" + PR804_BASE + "/", 1)[1]
        return git_bytes(PR804_BASE, path)

    # Explicitly fail any accidental network access in imported production code.
    with patch("urllib.request.urlopen", side_effect=AssertionError("offline probe forbids network")):
        validator = load(".github/scripts/validate-article-pr.py", "forensic_article_validator")
        worker = load(".github/scripts/article-image-worker-v4.py", "forensic_article_worker")
        controller = load(".github/scripts/article-pr-controller.py", "forensic_article_controller")
        from scripts.kesher_content_controller_v3_entry import V3GitHubClient
        from scripts.kesher_article_contract import forbidden_article_paths

        errors = validator.evaluate(pr, files, [{"name": "verify", "conclusion": "success"}],
                                    base_posts, head_posts, image_bytes)
        worker.v3.core.github_content = lambda *a, **k: {
            "content": __import__("base64").b64encode(
                git_bytes(PR804_HEAD, "public" + post["image"])).decode()
        }
        present = worker.v3.trusted_image_present("yanivsa/kesher-website", pr, post, "unused")
        client = object.__new__(V3GitHubClient)
        client.api = "https://offline.invalid"
        with patch.object(client, "contents_json", side_effect=[base_posts, head_posts]), \
             patch.object(client, "request", return_value={"sha": "offline-existing-blob"}):
            ready = client.article_pr_image_ready(pr)

    # This is the exact path predicate in auto-close-stale-article-prs.yml at
    # 55563f42. Age is intentionally excluded: legitimate publication files
    # already prevent eligibility, however long the PR has been stale.
    stale_paths = [p["filename"] for p in files]
    stale_path_eligible = "src/data/posts.json" in stale_paths and all(
        p == "src/data/posts.json" or p.startswith("public/images/generated/blog/")
        for p in stale_paths)
    repeated = []
    for sha in PR804_IMAGE_COMMITS:
        record = next(p for p in posts(sha) if p["id"] == post["id"])
        repeated.append({"commit": sha, "image_sha256": hashlib.sha256(
            git_bytes(sha, "public" + record["image"])).hexdigest()})
    print(json.dumps({
        "fixture": {"pr": 804, "head": PR804_HEAD, "base": PR804_BASE, "article_id": post["id"]},
        "strict_gate_errors": errors,
        "legacy_cleanup_forbidden": controller.forbidden_paths(files),
        "canonical_contract_forbidden": forbidden_article_paths(stale_paths),
        "trusted_image_present": present,
        "controller_image_ready": ready,
        "legacy_stale_path_eligible": stale_path_eligible,
        "repeated_image_commits": repeated,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
