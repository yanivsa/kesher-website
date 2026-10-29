from __future__ import annotations
import copy, os, unittest, tempfile
from pathlib import Path
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo
from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_idea_queue as ideas
TZ = ZoneInfo("Asia/Jerusalem")

class FakeGitHub:
    def __init__(self, state=None, posts=None):
        self.api = "https://api.github.com/repos/yanivsa/kesher-website"; self.ref = "main"
        self.saved_state=copy.deepcopy(state); self.posts=copy.deepcopy(posts or []); self.recent_posts=[]
        self.dispatches=[]; self.active={}; self.runs={}; self.video_state={"version":1,"items":[]}
    def load_controller_state(self): return copy.deepcopy(self.saved_state)
    def save_controller_state(self,state): self.saved_state=copy.deepcopy(state)
    def contents_json(self,path,ref="main"):
        if path=="src/data/posts.json": return copy.deepcopy(self.posts)
        if path=="src/data/postsRecent.json": return copy.deepcopy(self.recent_posts)
        raise AssertionError(path)
    def posts_on_main(self,ref="main"): return copy.deepcopy(self.posts)
    def open_article_prs(self,target_slot=None): return []
    def active_workflow_run(self,workflow,*,production_only=False): return copy.deepcopy(self.active.get(workflow))
    def workflow_run_by_id(self,run_id): return copy.deepcopy(self.runs.get(run_id))
    def article_result_for_run(self,run_id): return None
    def dispatch(self,workflow,inputs=None):
        payload=copy.deepcopy(inputs or {}); self.dispatches.append((workflow,payload))
        self.active[workflow]={"id":len(self.dispatches),"status":"in_progress","event":"workflow_dispatch"}
    def newest_video_state(self): return copy.deepcopy(self.video_state)
    def request(self, *args, **kwargs): return {}

class FakeSite:
    def get(self,url): return 404,""

class _IsolatedPublicationCatalog(unittest.TestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        catalog = Path(directory.name) / "posts.json"
        catalog.write_text("[]", encoding="utf-8")
        # These cases exercise queue ownership/dispatch, not today's changing
        # production SEO catalog. Dedicated conflict suites cover that boundary.
        patcher = mock.patch.object(ideas, "_PUBLISHED_POST_FILES", (str(catalog),))
        patcher.start()
        self.addCleanup(patcher.stop)


class IdeaQueueTests(_IsolatedPublicationCatalog):
    def env(self): return {"KESHER_IDEA_ID":"potty-training-20261018-v1","KESHER_IDEA_TOPIC_BRIEF":"כתוב מאמר על גמילה מטיטול להורים לפעוטות.","KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD":"גמילה מטיטול"}
    def test_ingest_idempotent_and_conflict_fails(self):
        st={"cycle":"2026-10-18","status":"complete"}
        self.assertEqual(ideas.ingest_from_env(st,self.env(),now_iso="t1"),"queued")
        self.assertEqual(ideas.ingest_from_env(st,self.env(),now_iso="t2"),"duplicate")
        bad=self.env(); bad["KESHER_IDEA_TOPIC_BRIEF"]="אחר"
        with self.assertRaisesRegex(ideas.IdeaQueueError,"IDEA_ID_CONFLICT"): ideas.ingest_from_env(st,bad,now_iso="t3")
    def test_rollover_fifo_claim_and_dispatch_inputs(self):
        old={"idea_queue":[{"idea_id":"a","fingerprint":"1","topic_brief":"A","required_primary_keyword":"א","status":"queued"}],"idea_history":[]}
        new={"cycle":"2026-10-19"}; ideas.carry_forward(new,old)
        ideas.claim_next(new,"2026-10-19",now_iso="now")
        p=ideas.article_dispatch_inputs(new,{"slot":"2026-10-19"})
        self.assertIn("Required Primary Keyword: א",p["topic_brief"]); self.assertIn("Idea Request ID: a",p["topic_brief"])
    def test_finalize_records_three_outputs(self):
        st={"status":"complete","active_idea":{"idea_id":"a","status":"claimed"},"article":{"url":"article"},"long_video":{"youtube_url":"long"},"short":{"youtube_url":"short"}}
        self.assertTrue(ideas.finalize_if_complete(st,now_iso="done")); self.assertIsNone(st["active_idea"]); self.assertEqual(st["idea_history"][-1]["outputs"]["short_url"],"short")
    def test_workflow_exposes_owner_idea_inputs(self):
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/kesher-content-controller.yml").read_text(encoding="utf-8")
        for field in ("idea_id:", "topic_brief:", "required_primary_keyword:"):
            self.assertIn(field, workflow)
        self.assertIn("KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD", workflow)

    def test_retry_payload_for_active_idea_is_stable(self):
        st={"cycle":"2026-10-19","active_idea":{"idea_id":"potty","topic_brief":"מאמר גמילה","required_primary_keyword":"גמילה מטיטול","publication_slot":"2026-10-19","status":"claimed"}}
        a=ideas.article_dispatch_inputs(st,{"slot":"2026-10-19"})
        b=ideas.article_dispatch_inputs(st,{"slot":"2026-10-19"})
        self.assertEqual(a,b)

    def test_guarded_article_dispatch_claims_queue_and_adds_brief(self):
        gh=FakeGitHub(); ctrl=object.__new__(stabilized.StabilizedRuntimeV5Controller); ctrl.github=gh; ctrl.now=datetime(2026,10,19,0,36,tzinfo=TZ)
        state={"cycle":"2026-10-19","article":{"attempts":0},"idea_queue":[{"idea_id":"potty","fingerprint":"x","topic_brief":"מאמר גמילה","required_primary_keyword":"גמילה מטיטול","status":"queued"}],"idea_history":[],"active_idea":None,"pending_dispatches":{}}
        ctrl._active_state_ref=state
        raw=[]
        with mock.patch.object(ctrl,"_safe_save_controller_state",lambda s: None):
            ctrl._guarded_dispatch(state,core.ARTICLE_WORKFLOW,{"slot":"2026-10-19"},lambda w,i: raw.append((w,i)))
        self.assertEqual(len(raw),1); self.assertIn("Required Primary Keyword: גמילה מטיטול",raw[0][1]["topic_brief"]); self.assertEqual(state["active_idea"]["idea_id"],"potty")

class ScheduledIdeaRolloverTests(_IsolatedPublicationCatalog):
    def stage(self, *, status="pending"):
        return {
            "attempt_count": 0,
            "status": status,
            "last_error": None,
            "next_retry_at": None,
            "run_id": None,
            "processed_run_id": None,
            "provider_id": None,
            "failure_fingerprint": None,
            "same_failure_streak": 0,
            "failure_count_by_type": {},
        }

    def active_idea(self):
        return {
            "idea_id": "parenting-p1-child-poops-in-pants",
            "fingerprint": "fp-child-poops",
            "topic_brief": "ילד עושה קקי במכנסיים",
            "required_primary_keyword": "ילד עושה קקי במכנסיים",
            "run_now": False,
            "status": "claimed",
            "requested_at": "2026-10-19T10:07:32Z",
            "publication_slot": "2026-10-23",
            "claimed_at": "2026-10-23T11:21:21Z",
        }

    def active_cycle(self):
        article = self.stage(status="exhausted")
        article.update({
            "attempt_count": 1,
            "attempts": 1,
            "deploy_attempts": 0,
            "pr_number": 1182,
            "pr_url": "https://github.com/yanivsa/kesher-website/pull/1182",
            "current_pr_head_sha": "4d922a592dd7cd46d9ea4cbf2be9a026d2b9243e",
            "normalized_head_sha": "4d922a592dd7cd46d9ea4cbf2be9a026d2b9243e",
            "normalization_status": "complete",
            "merge_dispatch_count": 3,
            "merge_dispatch_at": "2026-10-23T12:06:28Z",
        })
        return {
            "schema_version": 5,
            "cycle": "2026-10-23",
            "status": "blocked",
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                "message": "PR #1182 exceeded maximum auto-merge dispatch budget (3 dispatches)",
            },
            "history": [],
            "backlog": [],
            "article": article,
            "image": self.stage(),
            "long_video": self.stage(),
            "short": self.stage(),
            "idea_queue": [],
            "idea_history": [],
            "active_idea": self.active_idea(),
        }

    def test_scheduled_claimed_cycle_survives_midnight_without_archival(self):
        previous = self.active_cycle()
        github = FakeGitHub(previous, [])
        controller = stabilized.StabilizedRuntimeV5Controller(
            github, FakeSite(), now=datetime(2026, 10, 24, 0, 10, tzinfo=TZ)
        )

        state = controller.state()

        self.assertEqual(state["cycle"], "2026-10-23")
        self.assertEqual(state["article"]["pr_number"], 1182)
        self.assertEqual(state["article"]["merge_dispatch_count"], 3)
        self.assertEqual(state["active_idea"]["publication_slot"], "2026-10-23")
        self.assertFalse(any(row.get("cycle") == "2026-10-23" for row in state.get("backlog", [])))

    def test_already_rolled_shell_restores_exact_incomplete_active_cycle_from_backlog(self):
        prior = self.active_cycle()
        backlog_row = {
            "cycle": "2026-10-23",
            "status": "blocked",
            "exact_slug": None,
            "content_sha256": None,
            "article": copy.deepcopy(prior["article"]),
            "long_video": copy.deepcopy(prior["long_video"]),
            "short": copy.deepcopy(prior["short"]),
            "terminal_state": {"blocked": True, "article_exhausted": True},
            "archived_at": "2026-10-23T21:00:54Z",
            "media": {},
        }
        current = {
            "schema_version": 5,
            "cycle": "2026-10-24",
            "status": "blocked",
            "last_error": {"stage": "controller", "code": "IDEA_SLOT_MISMATCH", "message": "IDEA_SLOT_MISMATCH"},
            "history": [],
            "backlog": [backlog_row],
            "article": {**self.stage(), "attempts": 0, "deploy_attempts": 0, "normalization_status": "pending"},
            "image": self.stage(),
            "long_video": self.stage(),
            "short": self.stage(),
            "idea_queue": [],
            "idea_history": [],
            "active_idea": self.active_idea(),
        }
        github = FakeGitHub(current, [])
        controller = stabilized.StabilizedRuntimeV5Controller(
            github, FakeSite(), now=datetime(2026, 10, 24, 19, 0, tzinfo=TZ)
        )

        state = controller.state()

        self.assertEqual(state["cycle"], "2026-10-23")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["article"]["pr_number"], 1182)
        self.assertEqual(state["article"]["merge_dispatch_count"], 3)
        self.assertEqual(state["last_error"]["code"], "ARTICLE_ATTEMPTS_EXHAUSTED")
        self.assertFalse(any(row.get("cycle") == "2026-10-23" for row in state.get("backlog", [])))
        self.assertTrue(any(row.get("reason") == "incomplete_active_cycle_restored_from_backlog" for row in state["history"]))

    def test_scheduled_active_cycle_selects_article_from_claimed_publication_slot_after_midnight(self):
        state = self.active_cycle()
        state["status"] = "article_live"
        state["article"].update({"status": "complete", "slug": "child-poops-in-pants"})
        posts = [{
            "id": "child-poops-in-pants",
            "date": "2026-10-23",
            "title": "ילד עושה קקי במכנסיים",
            "content": "<p>x</p>",
            "category": "הדרכת הורים",
            "excerpt": "x",
        }]
        github = FakeGitHub(state, posts)
        controller = stabilized.StabilizedRuntimeV5Controller(
            github, FakeSite(), now=datetime(2026, 10, 24, 1, 0, tzinfo=TZ)
        )

        matches = controller._reconcile_existing_current_day_article(state, posts)

        self.assertEqual(len(matches), 1)
        self.assertEqual(core.canonical_slug(matches[0]), "child-poops-in-pants")

    def test_scheduled_active_prior_slot_routes_open_pr_after_midnight(self):
        state = self.active_cycle()
        state["status"] = "article_normalizing"
        state["article"]["status"] = "running"
        state["article"]["merge_dispatch_count"] = 0
        state["article"]["normalization_status"] = "running"
        github = FakeGitHub(state, [])
        pr = {
            "number": 1182,
            "state": "open",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1182",
            "head": {"sha": "7baf8d39ad4173b9816b15b9e2b9df06c8e534cf"},
        }
        github.open_article_prs = mock.Mock(side_effect=lambda slot=None: [pr] if slot == "2026-10-23" else [])
        controller = stabilized.StabilizedRuntimeV5Controller(
            github, FakeSite(), now=datetime(2026, 10, 24, 1, 0, tzinfo=TZ)
        )
        controller._active_state_ref = state

        with mock.patch.object(controller, "_handle_open_article_pr", return_value=core.Action("wait", "handled")) as handler:
            action = controller._scheduled_active_article_phase(state)

        self.assertEqual(action.kind, "wait")
        github.open_article_prs.assert_called_with("2026-10-23")
        handler.assert_called_once_with(state, pr)


class IdeaRunNowTests(_IsolatedPublicationCatalog):
    def pacifier_env(self):
        return {
            "KESHER_IDEA_ID": "pacifier-weaning-20261018-v1",
            "KESHER_IDEA_TOPIC_BRIEF": "כתוב מאמר עברי מעשי להורים בנושא גמילה ממוצץ, כולל עיתוי, הכנה, גבולות, לילות ונסיגה.",
            "KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD": "גמילה ממוצץ",
            "KESHER_IDEA_RUN_NOW": "true",
        }

    def complete_state(self):
        stage={"attempt_count":0,"status":"complete","last_error":None,"next_retry_at":None,"run_id":None,"processed_run_id":None,"provider_id":None,"failure_fingerprint":None,"same_failure_streak":0,"failure_count_by_type":{}}
        return {
            "schema_version":5,"cycle":"2026-10-18","status":"complete","last_error":None,"history":[],"backlog":[],
            "article":{**stage,"attempts":0,"deploy_attempts":0,"slug":"today","url":"https://kesher.saharoni.com/blog/today","live":True},
            "image":copy.deepcopy(stage),
            "long_video":{**copy.deepcopy(stage),"youtube_url":"https://youtu.be/long-old"},
            "short":{**copy.deepcopy(stage),"youtube_url":"https://youtu.be/short-old"},
            "idea_queue":[{"idea_id":"potty","fingerprint":"old","topic_brief":"מאמר גמילה מטיטול","required_primary_keyword":"גמילה מטיטול","status":"queued"}],
            "idea_history":[],"active_idea":None,
        }

    def test_run_now_ingest_is_priority_and_does_not_drop_existing_queue(self):
        st=self.complete_state()
        result=ideas.ingest_from_env(st,self.pacifier_env(),now_iso="now")
        self.assertEqual(result,"run_now_queued")
        self.assertEqual([row["idea_id"] for row in st["idea_queue"]],["pacifier-weaning-20261018-v1","potty"])
        self.assertTrue(st["idea_queue"][0]["run_now"])

    def test_run_now_tick_dispatches_article_for_current_israel_day(self):
        st=self.complete_state()
        posts=[{"id":"today","date":"2026-10-18","title":"היום","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"}]
        gh=FakeGitHub(st,posts)
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,18,15,0,tzinfo=TZ))
        with mock.patch.dict(os.environ,self.pacifier_env(),clear=False):
            state,action=ctrl.tick()
        self.assertEqual(action.kind,"dispatch_article")
        article_dispatches=[row for row in gh.dispatches if row[0]==core.ARTICLE_WORKFLOW]
        self.assertEqual(len(article_dispatches),1)
        self.assertEqual(article_dispatches[0][1]["slot"],"2026-10-18")
        self.assertIn("Required Primary Keyword: גמילה ממוצץ",article_dispatches[0][1]["topic_brief"])
        self.assertEqual(state["active_idea"]["idea_id"],"pacifier-weaning-20261018-v1")
        self.assertEqual(state["active_idea"]["publication_slot"],"2026-10-18")
        self.assertEqual([row["idea_id"] for row in state["idea_queue"]],["potty"])
        self.assertEqual(state["status"],"article_generating")

    def test_run_now_when_utc_and_israel_dates_differ(self):
        st=self.complete_state()
        st["cycle"]="2026-10-19"
        posts=[{"id":"today","date":"2026-10-19","title":"היום","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"}]
        gh=FakeGitHub(st,posts)
        # 22:30 UTC on 2026-10-18 is 01:30 IDT on 2026-10-19 in Israel
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,19,1,30,tzinfo=TZ))
        with mock.patch.dict(os.environ,self.pacifier_env(),clear=False):
            state,action=ctrl.tick()
        self.assertEqual(action.kind,"dispatch_article")
        article_dispatches=[row for row in gh.dispatches if row[0]==core.ARTICLE_WORKFLOW]
        self.assertEqual(len(article_dispatches),1)
        self.assertEqual(article_dispatches[0][1]["slot"],"2026-10-19")
        self.assertEqual(state["active_idea"]["publication_slot"],"2026-10-19")

    def test_run_now_near_midnight(self):
        st_before=self.complete_state()
        gh_before=FakeGitHub(st_before,[])
        ctrl_before=stabilized.StabilizedRuntimeV5Controller(gh_before,FakeSite(),now=datetime(2026,10,18,23,55,tzinfo=TZ))
        with mock.patch.dict(os.environ,self.pacifier_env(),clear=False):
            state_before,action_before=ctrl_before.tick()
        self.assertEqual(state_before["active_idea"]["publication_slot"],"2026-10-18")

        st_after=self.complete_state()
        st_after["cycle"]="2026-10-19"
        gh_after=FakeGitHub(st_after,[])
        ctrl_after=stabilized.StabilizedRuntimeV5Controller(gh_after,FakeSite(),now=datetime(2026,10,19,0,5,tzinfo=TZ))
        with mock.patch.dict(os.environ,self.pacifier_env(),clear=False):
            state_after,action_after=ctrl_after.tick()
        self.assertEqual(state_after["active_idea"]["publication_slot"],"2026-10-19")

    def test_run_now_reconciles_multiple_articles_same_day_without_duplicates(self):
        st=self.complete_state()
        st["active_idea"]={"idea_id":"pacifier","topic_brief":"מוצץ","required_primary_keyword":"גמילה ממוצץ","run_now":True,"publication_slot":"2026-10-18","status":"claimed"}
        st["article"]={"attempt_count":1,"attempts":1,"status":"running","slug":"pacifier-weaning"}
        st["owner_cycle_archive"]=[{"article":{"slug":"today"}}]
        posts=[
            {"id":"today","date":"2026-10-18","title":"היום","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"},
            {"id":"pacifier-weaning","date":"2026-10-18","title":"גמילה ממוצץ","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"},
        ]
        gh=FakeGitHub(st,posts)
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,18,15,0,tzinfo=TZ))
        ctrl._active_state_ref=st
        reconciled=ctrl._reconcile_existing_current_day_article(st,posts)
        self.assertEqual(len(reconciled),1)
        self.assertEqual(core.canonical_slug(reconciled[0]),"pacifier-weaning")

    def test_run_now_ignores_archived_articles_before_new_article_is_merged(self):
        st=self.complete_state()
        st["active_idea"]={"idea_id":"pacifier","topic_brief":"מוצץ","required_primary_keyword":"גמילה ממוצץ","run_now":True,"publication_slot":"2026-10-18","status":"claimed"}
        st["article"]={"attempts":0}
        st["owner_cycle_archive"]=[{"article":{"slug":"today"}}]
        posts=[
            {"id":"today","date":"2026-10-18","title":"היום","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"},
        ]
        gh=FakeGitHub(st,posts)
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,18,15,0,tzinfo=TZ))
        ctrl._active_state_ref=st
        reconciled=ctrl._reconcile_existing_current_day_article(st,posts)
        self.assertEqual(len(reconciled),0)

    def test_run_now_active_cycle_survives_midnight_rollover(self):
        st=self.complete_state()
        st["status"]="article_generating"
        st["active_idea"]={"idea_id":"pacifier","topic_brief":"מוצץ","required_primary_keyword":"גמילה ממוצץ","run_now":True,"publication_slot":"2026-10-19","status":"claimed"}
        st["article"]={"attempt_count":1,"attempts":1,"status":"running","run_id":99}
        gh=FakeGitHub(st,[])
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,19,0,10,tzinfo=TZ))
        state=ctrl.state()
        self.assertEqual(state["cycle"],"2026-10-18")
        self.assertEqual(state["active_idea"]["publication_slot"],"2026-10-19")
        self.assertEqual(state["article"]["run_id"],99)

    def test_run_now_child_slot_is_accepted_as_authoritative(self):
        st=self.complete_state()
        st["active_idea"]={"idea_id":"pacifier","topic_brief":"מוצץ","required_primary_keyword":"גמילה ממוצץ","run_now":True,"publication_slot":"2026-10-19","status":"claimed"}
        gh=FakeGitHub(st,[])
        gh.runs[123]={"id":123,"event":"workflow_dispatch","path":".github/workflows/kesher-article-generation.yml","conclusion":"success","run_attempt":1}
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,18,15,0,tzinfo=TZ))
        ctrl._active_state_ref=st
        with mock.patch.dict(os.environ,{"KESHER_TRIGGER_EVENT":"workflow_dispatch","KESHER_CHILD_WORKFLOW":"Kesher Article Generation","KESHER_CHILD_RUN_ID":"123","KESHER_CHILD_CONCLUSION":"success","KESHER_CHILD_SLOT":"2026-10-19"},clear=False):
            valid,reason=ctrl._validate_child_notification(st)
        self.assertTrue(valid,reason)

    def test_run_now_article_selection_uses_publication_slot_not_today(self):
        st=self.complete_state()
        st["active_idea"]={"idea_id":"pacifier","topic_brief":"מוצץ","required_primary_keyword":"גמילה ממוצץ","run_now":True,"publication_slot":"2026-10-19","status":"claimed"}
        posts=[
            {"id":"today","date":"2026-10-18","title":"היום","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"},
            {"id":"pacifier-weaning","date":"2026-10-19","title":"גמילה ממוצץ","content":"<p>x</p>","category":"הדרכת הורים","excerpt":"x"},
        ]
        gh=FakeGitHub(st,posts)
        ctrl=stabilized.StabilizedRuntimeV5Controller(gh,FakeSite(),now=datetime(2026,10,18,15,0,tzinfo=TZ))
        ctrl._active_state_ref=st
        picked=ctrl._selected_article(posts,state=st)
        self.assertEqual(core.canonical_slug(picked),"pacifier-weaning")

    def test_workflow_exposes_run_now_input(self):
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/kesher-content-controller.yml").read_text(encoding="utf-8")
        self.assertIn("run_now:",workflow)
        self.assertIn("KESHER_IDEA_RUN_NOW",workflow)

    def test_queued_idea_promoted_to_run_now_when_dispatched_with_run_now_flag(self):
        st = {"cycle": "2026-10-18", "status": "complete", "idea_queue": [], "idea_history": [], "active_idea": None}
        env = {
            "KESHER_IDEA_ID": "potty",
            "KESHER_IDEA_TOPIC_BRIEF": "מאמר גמילה מטיטול",
            "KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD": "גמילה מטיטול",
        }
        res1 = ideas.ingest_from_env(st, env, now_iso="t1")
        self.assertEqual(res1, "queued")
        self.assertEqual(len(st["idea_queue"]), 1)
        self.assertFalse(st["idea_queue"][0].get("run_now"))

        env_run_now = dict(env, KESHER_IDEA_RUN_NOW="true")
        res2 = ideas.ingest_from_env(st, env_run_now, now_iso="t2")
        self.assertEqual(res2, "run_now_queued")
        self.assertTrue(st["idea_queue"][0].get("run_now"))
        self.assertEqual(st["idea_queue"][0]["idea_id"], "potty")

    def test_finalize_records_slug_and_urls(self):
        st = {
            "status": "complete",
            "active_idea": {"idea_id": "potty", "status": "claimed"},
            "article": {"slug": "potty-training", "url": "https://kesher.saharoni.com/blog/potty-training"},
            "long_video": {"youtube_url": "https://youtu.be/long"},
            "short": {"youtube_url": "https://youtu.be/short"},
        }
        self.assertTrue(ideas.finalize_if_complete(st, now_iso="now"))
        self.assertIsNone(st["active_idea"])
        out = st["idea_history"][-1]["outputs"]
        self.assertEqual(out["slug"], "potty-training")
        self.assertEqual(out["article_url"], "https://kesher.saharoni.com/blog/potty-training")

    def test_reconcile_existing_current_day_article_excludes_prior_same_date_cycle(self):
        st = self.complete_state()
        st["cycle"] = "2026-10-19"
        st["idea_history"] = [{
            "idea_id": "pacifier",
            "outputs": {"slug": "pacifier-weaning", "article_url": "https://kesher.saharoni.com/blog/pacifier-weaning"},
        }]
        st["article"] = {}
        posts = [
            {"id": "pacifier-weaning", "date": "2026-10-19", "title": "מוצץ", "content": "<p>x</p>", "category": "הדרכת הורים", "excerpt": "x"},
        ]
        ctrl = stabilized.StabilizedRuntimeV5Controller(FakeGitHub(st, posts), FakeSite(), now=datetime(2026, 10, 19, 10, 0, tzinfo=TZ))
        candidates = ctrl._reconcile_existing_current_day_article(st, posts)
        # Should NOT adopt pacifier-weaning for a new uninitialized article cycle on the same day
        self.assertEqual(candidates, [])

    def test_run_now_allowed_when_queue_at_capacity(self):
        st = {"cycle": "2026-10-19", "status": "complete", "idea_queue": [], "idea_history": [], "active_idea": None}
        for i in range(ideas.MAX_QUEUE):
            st["idea_queue"].append({
                "idea_id": f"idea-{i}",
                "fingerprint": f"fp-{i}",
                "topic_brief": f"brief-{i}",
                "required_primary_keyword": f"kw-{i}",
                "run_now": False,
                "status": "queued",
            })
        self.assertEqual(len(st["idea_queue"]), ideas.MAX_QUEUE)
        # Regular ingest raises IDEA_QUEUE_FULL
        regular_env = {
            "KESHER_IDEA_ID": "new-idea",
            "KESHER_IDEA_TOPIC_BRIEF": "חדש",
            "KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD": "גמילה ממוצץ",
        }
        with self.assertRaisesRegex(ideas.IdeaQueueError, "IDEA_QUEUE_FULL"):
            ideas.ingest_from_env(st, regular_env, now_iso="now")
        # run_now ingest succeeds and places item at front
        run_now_env = dict(regular_env, KESHER_IDEA_RUN_NOW="true")
        result = ideas.ingest_from_env(st, run_now_env, now_iso="now")
        self.assertEqual(result, "run_now_queued")
        self.assertEqual(st["idea_queue"][0]["idea_id"], "new-idea")

    def test_controller_recovers_from_idea_queue_full_block(self):
        st = self.complete_state()
        st["cycle"] = "2026-10-19"
        st["status"] = "blocked"
        st["last_error"] = {"stage": "controller", "code": "IDEA_QUEUE_FULL", "message": "IDEA_QUEUE_FULL"}
        gh = FakeGitHub(st, [])
        ctrl = stabilized.StabilizedRuntimeV5Controller(gh, FakeSite(), now=datetime(2026, 10, 19, 10, 0, tzinfo=TZ))
        with mock.patch.dict(os.environ, {}, clear=True):
            state, action = ctrl.tick()
        reasons = [h.get("reason") for h in state.get("history", [])]
        self.assertIn("idea_queue_full_recovery", reasons)

    def test_invalid_idea_dispatch_does_not_block_complete_state(self):
        st = self.complete_state()
        st["cycle"] = "2026-10-19"
        gh = FakeGitHub(st, [])
        ctrl = stabilized.StabilizedRuntimeV5Controller(gh, FakeSite(), now=datetime(2026, 10, 19, 10, 0, tzinfo=TZ))
        bad_env = {
            "KESHER_IDEA_ID": "INVALID IDEA ID WITH SPACES",
            "KESHER_IDEA_TOPIC_BRIEF": "מאמר",
            "KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD": "גמילה ממוצץ",
        }
        with mock.patch.dict(os.environ, bad_env, clear=True):
            state, action = ctrl.tick()
        self.assertEqual(action.kind, "rejected")
        self.assertNotEqual(state["status"], "blocked")
        self.assertEqual(state["last_error"]["code"], "IDEA_ID_INVALID")

