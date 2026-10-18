from __future__ import annotations
import copy, os, unittest
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

class FakeSite:
    def get(self,url): return 404,""

class IdeaQueueTests(unittest.TestCase):
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
