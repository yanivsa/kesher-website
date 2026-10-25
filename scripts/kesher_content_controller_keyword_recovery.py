#!/usr/bin/env python3
"""Production wrapper that rejects owner ideas whose Primary Keyword is already owned.

This recovery layer is intentionally narrow: it runs before the stabilized V5 tick,
only while no article identity/PR/worker exists for the active idea. A collision must
be supported by both visible exact-keyword evidence and semantic slug evidence. The
rejected idea is archived and the next queued idea is claimed on the same publication
slot with a fresh article attempt budget.
"""

from __future__ import annotations

import copy
import json
import sys
from typing import Any

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_idea_queue as idea_queue
from scripts import kesher_primary_keyword_contract as keyword_contract

v5 = stabilized.v5


class KeywordConflictAdvancingController(stabilized.StabilizedRuntimeV5Controller):
    """Heal a terminal article cycle when the active Primary Keyword already exists."""

    @staticmethod
    def _post_slug(post: dict[str, Any]) -> str:
        return str(post.get("slug") or post.get("id") or "").strip()

    @classmethod
    def _published_primary_keyword_conflicts(
        cls,
        posts: list[dict[str, Any]],
        keyword: str,
    ) -> list[dict[str, Any]]:
        keyword = str(keyword or "").strip()
        if not keyword:
            return []

        conflicts: list[dict[str, Any]] = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            slug = cls._post_slug(post)
            if not slug:
                continue

            semantic_match, _ = keyword_contract.slug_represents_keyword(slug, keyword)
            if not semantic_match:
                continue

            title = str(post.get("title") or "")
            excerpt = str(post.get("excerpt") or "")
            content = str(post.get("content") or "")
            first_paragraph = keyword_contract.extract_first_paragraph(content)
            visible_match = (
                keyword_contract.matches_keyword(title, keyword)
                or keyword_contract.matches_keyword(excerpt, keyword)
                or keyword_contract.keyword_in_opening(first_paragraph, keyword)
            )
            if visible_match:
                conflicts.append(post)
        return conflicts

    def _article_identity_or_worker_exists(self, state: dict[str, Any]) -> bool:
        article = state.get("article") if isinstance(state.get("article"), dict) else {}
        durable_identity_fields = (
            "pr_number",
            "pr_url",
            "slug",
            "url",
            "quality_content_sha256",
            "current_pr_head_sha",
        )
        if article.get("live") is True or any(str(article.get(field) or "").strip() for field in durable_identity_fields):
            return True

        active = state.get("active_idea") if isinstance(state.get("active_idea"), dict) else {}
        slot = str(active.get("publication_slot") or state.get("cycle") or "").strip()
        try:
            if self.github.open_article_prs(slot):
                return True
        except Exception:
            # Fail closed if PR evidence cannot be read.
            return True

        try:
            worker = self.github.active_workflow_run(v5.core.ARTICLE_WORKFLOW, production_only=True)
        except TypeError:
            worker = self.github.active_workflow_run(v5.core.ARTICLE_WORKFLOW)
        except Exception:
            # Fail closed if worker evidence cannot be read.
            return True
        return bool(worker)

    @staticmethod
    def _reset_content_stages_for_replacement(state: dict[str, Any]) -> None:
        stage = v5.v3._stage_template
        state["article"] = stage()
        state["article"].update({"attempts": 0, "deploy_attempts": 0})
        state["image"] = stage()
        state["long_video"] = stage()
        state["short"] = stage()
        state.pop("video", None)
        state["pending_dispatches"] = {}
        state["processed_child_notifications"] = []

    def _advance_primary_keyword_conflict(self, state: dict[str, Any]) -> bool:
        """Reject one proven conflicting active idea and claim the next queued idea.

        Returns True only when state was durably changed. It deliberately runs before
        normal ARTICLE_ATTEMPTS_EXHAUSTED handling, so a collision that consumed an old
        three-attempt budget can self-heal after this code is deployed without a fourth
        attempt for the conflicting idea.
        """
        idea_queue.ensure_fields(state)
        active = state.get("active_idea")
        if not isinstance(active, dict) or str(active.get("status") or "") in {"complete", "rejected"}:
            return False
        if self._article_identity_or_worker_exists(state):
            return False

        keyword = str(active.get("required_primary_keyword") or "").strip()
        if not keyword:
            return False
        posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            return False
        conflicts = self._published_primary_keyword_conflicts(posts, keyword)
        if not conflicts:
            return False

        previous_status = str(state.get("status") or "")
        previous_error = copy.deepcopy(state.get("last_error"))
        previous_article = state.get("article") if isinstance(state.get("article"), dict) else {}
        prior_attempts = int(previous_article.get("attempts") or previous_article.get("attempt_count") or 0)
        conflict_slugs = [self._post_slug(post) for post in conflicts]

        rejected = copy.deepcopy(active)
        rejected.update({
            "status": "rejected",
            "rejected_at": v5.core.utc_now(),
            "rejection_code": "PRIMARY_KEYWORD_CONFLICT",
            "rejection_message": f"Primary Keyword already owned by published article(s): {', '.join(conflict_slugs)}",
            "conflicting_slugs": conflict_slugs,
            "prior_article_attempts": prior_attempts,
        })
        state["idea_history"].append(rejected)
        state["idea_history"] = state["idea_history"][-idea_queue.MAX_HISTORY:]
        state["active_idea"] = None

        cycle = str(state.get("cycle") or "").strip()
        replacement = idea_queue.claim_next(state, cycle, now_iso=v5.core.utc_now()) if cycle else None
        if replacement is None:
            state["status"] = "blocked"
            state["last_error"] = {
                "stage": "article",
                "code": "PRIMARY_KEYWORD_CONFLICT_NO_REPLACEMENT",
                "message": f"Rejected {rejected.get('idea_id')} because '{keyword}' already exists; no queued replacement is available",
                "at": v5.core.utc_now(),
            }
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": previous_status,
                "to": "blocked",
                "reason": "primary_keyword_conflict_rejected",
                "details": {
                    "rejected_idea_id": rejected.get("idea_id"),
                    "required_primary_keyword": keyword,
                    "conflicting_slugs": conflict_slugs,
                    "prior_article_attempts": prior_attempts,
                    "previous_error": previous_error,
                },
            })
            state["history"] = state["history"][-100:]
            state["updated_at"] = v5.core.utc_now()
            return True

        self._reset_content_stages_for_replacement(state)
        state["status"] = "article_needed"
        state["last_error"] = None
        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": previous_status,
            "to": "article_needed",
            "reason": "primary_keyword_conflict_advanced",
            "details": {
                "rejected_idea_id": rejected.get("idea_id"),
                "required_primary_keyword": keyword,
                "conflicting_slugs": conflict_slugs,
                "prior_article_attempts": prior_attempts,
                "previous_error": previous_error,
                "replacement_idea_id": replacement.get("idea_id"),
                "replacement_primary_keyword": replacement.get("required_primary_keyword"),
                "publication_slot": replacement.get("publication_slot"),
            },
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v5.core.utc_now()
        return True

    def tick(self):
        # Heal the collision before the stabilized controller evaluates terminal
        # article-attempt exhaustion. Persist first so nested/base tick() reloads
        # the replacement identity rather than the rejected idea.
        state = super().state()
        if self._advance_primary_keyword_conflict(state):
            self._active_state_ref = state
            self._safe_save_controller_state(state)
        return super().tick()


def install_runtime() -> None:
    stabilized.install_runtime()
    v5.V5Controller = KeywordConflictAdvancingController


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint

    retired_entrypoint()
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        import traceback

        traceback.print_exc()
        print(f"KESHER_CONTROLLER_KEYWORD_RECOVERY_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
