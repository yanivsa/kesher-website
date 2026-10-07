"""GET-only live reconciliation. No controller/worker mutation clients are imported.

Exact retained media receipts are observations, never upload/completion authority.
Missing credentials, expired artifacts and ambiguous identities remain unproven.
"""
from __future__ import annotations
import base64
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

from scripts.kesher_daily_pipeline import source_metadata, clean_article_html
from scripts.kesher_runtime.verification import SITE_URL, match_youtube_metadata, VerificationError

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a GitHub credential to an artifact storage host.

class ReadOnlyClient:
    def __init__(self, repo, token='', *, youtube_token='', youtube_key='', transport=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('REPOSITORY_INVALID')
        self.repo=repo;self.api='https://api.github.com/repos/'+repo
        self._token=token;self._youtube_token=youtube_token;self._youtube_key=youtube_key
        self._transport=transport;self.evidence=[]
    def request(self, method, url, *, raw=False):
        if method!='GET':raise ValueError('V6_READ_ONLY_GET_REQUIRED')
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('V6_READ_ONLY_URL_INVALID')
        headers={'User-Agent':'kesher-v6-read-only-shadow','Accept':'application/vnd.github+json'}
        if parsed.netloc=='api.github.com':
            if not parsed.path.startswith('/repos/'+self.repo+'/'):raise ValueError('V6_REPOSITORY_SCOPE_INVALID')
            if self._token:headers['Authorization']='Bearer '+self._token
        elif parsed.netloc=='www.googleapis.com' and parsed.path=='/youtube/v3/videos':
            if self._youtube_token:headers['Authorization']='Bearer '+self._youtube_token
        elif parsed.netloc!=urllib.parse.urlsplit(SITE_URL).netloc:
            raise ValueError('V6_READ_ONLY_HOST_INVALID')
        request=urllib.request.Request(url,headers=headers,method='GET')
        if self._transport:
            status,body,final_url=self._transport(request)
        else:
            opener=urllib.request.build_opener(NoRedirect())
            try:
                with opener.open(request,timeout=30) as response:
                    status=response.status;body=response.read(32*1024*1024+1);final_url=response.url
            except urllib.error.HTTPError as exc:
                status=exc.code;body=exc.read();final_url=url
                if status in (301,302,303,307,308):
                    location=exc.headers.get('Location','');dest=urllib.parse.urlsplit(location)
                    # Archive URLs are supplied by GitHub itself; download without
                    # any Authorization header, and never persist their signed query.
                    if parsed.netloc=='api.github.com' and parsed.path.endswith('/zip') and dest.scheme=='https' and not dest.username and not dest.password:
                        with urllib.request.urlopen(urllib.request.Request(location,method='GET'),timeout=30) as response:
                            status=response.status;body=response.read(32*1024*1024+1)
                    # Public route redirects are evidence of a route mismatch.
                    else:final_url=location
            except (urllib.error.URLError,TimeoutError,OSError):
                status=0;body=b'';final_url=url
        if len(body)>32*1024*1024:raise ValueError('V6_OBSERVATION_TOO_LARGE')
        self.evidence.append({'method':'GET','url':parsed.scheme+'://'+parsed.netloc+parsed.path,'status':status})
        if raw:return status,body,final_url
        if status!=200:return None
        return json.loads(body)
    def contents(self,path,ref):
        row=self.request('GET',self.api+'/contents/'+urllib.parse.quote(path,safe='/')+'?ref='+urllib.parse.quote(ref,safe=''))
        if isinstance(row,dict) and row.get('encoding')=='none' and re.fullmatch(r'[a-f0-9]{40}',str(row.get('sha') or '')):
            row=self.request('GET',self.api+'/git/blobs/'+row['sha'])
        if not isinstance(row,dict) or row.get('encoding')!='base64':return None
        return json.loads(base64.b64decode(row['content']))
    def media_receipts(self):
        items=[];coverage=[]
        for name in ('kesher-video-controller-state','kesher-short-v4-controller-state'):
            payload=self.request('GET',self.api+'/actions/artifacts?name='+name+'&per_page=100')
            if not isinstance(payload,dict):coverage.append({'name':name,'status':'unavailable'});continue
            rows=payload.get('artifacts') or []
            coverage.append({'name':name,'status':'complete' if payload.get('total_count',0)<=100 else 'bounded_incomplete','count':len(rows)})
            for artifact in rows:
                if artifact.get('expired'):continue
                status,raw,_=self.request('GET',self.api+'/actions/artifacts/'+str(int(artifact['id']))+'/zip',raw=True)
                if status!=200:continue
                try:
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        names=[n for n in archive.namelist() if n.endswith('/state.json') or n=='state.json']
                        if len(names)!=1:continue
                        info=archive.getinfo(names[0])
                        if info.file_size>8*1024*1024:continue
                        state=json.loads(archive.read(names[0]))
                    for item in state.get('items',[]):
                        if isinstance(item,dict):items.append(item)
                except (zipfile.BadZipFile,UnicodeDecodeError,ValueError,KeyError):continue
        return items,coverage
    def youtube(self,ids):
        if not ids or not (self._youtube_token or self._youtube_key):return {}
        query={'part':'snippet,status,processingDetails,fileDetails','id':','.join(sorted(ids))}
        if self._youtube_key:query['key']=self._youtube_key
        payload=self.request('GET','https://www.googleapis.com/youtube/v3/videos?'+urllib.parse.urlencode(query))
        if payload is None and self._youtube_key:
            query['part']='snippet,status'  # Owner-only fields may be unavailable to a public API key.
            payload=self.request('GET','https://www.googleapis.com/youtube/v3/videos?'+urllib.parse.urlencode(query))
        result={row['id']:row for row in (payload or {}).get('items',[])}
        if payload is not None:result['_lookup_complete']=True
        return result

def _media(kind,items,rows,slug,content_hash):
    expected_type='article_short' if kind=='short' else 'video_overview'
    exact=[i for i in items if i.get('type')==expected_type and (i.get('source') or {}).get('slug')==slug and (i.get('source') or {}).get('content_sha256')==content_hash and i.get('youtube_id')]
    identities={(i.get('id'),i['youtube_id']) for i in exact}
    if len(identities)>1:return {'status':'conflicting_exact_receipts','kind':kind}
    if not exact:return {'status':'identity_unproven','kind':kind}
    # Repeated archives of the same immutable receipt must also agree on source,
    # metadata and geometry. Never choose a timestamp-nearest competing claim.
    contracts={json.dumps({k:i.get(k) for k in ('source','youtube_metadata','dimensions','type')},sort_keys=True) for i in exact}
    if len(contracts)!=1:return {'status':'conflicting_exact_receipts','kind':kind}
    item=exact[0];video_id=item['youtube_id'];row=rows.get(video_id)
    result={'id':video_id,'url':'https://www.youtube.com/watch?v='+video_id,'kind':kind,'status':'remote_metadata_unavailable'}
    if not row:return result|{'status':'public_missing_or_inaccessible'} if rows.get('_lookup_complete') else result
    try:match_youtube_metadata(item,row)
    except (VerificationError,ValueError):return result|{'status':'metadata_mismatch'}
    privacy=(row.get('status') or {}).get('privacyStatus')
    result['privacy']=privacy
    if privacy!='public':return result|{'status':privacy if privacy in ('private','unlisted') else 'privacy_unproven'}
    if (row.get('processingDetails') or {}).get('processingStatus')!='succeeded':return result|{'status':'processing_unproven'}
    if kind=='short':
        streams=(row.get('fileDetails') or {}).get('videoStreams') or []
        dimensions={(s.get('widthPixels'),s.get('heightPixels')) for s in streams}
        if len(dimensions)!=1:return result|{'status':'public_geometry_unproven'}
        width,height=next(iter(dimensions))
        if type(width) is not int or type(height) is not int or width<=0 or height<=0:return result|{'status':'public_geometry_unproven'}
        result['dimensions']={'width':width,'height':height}
        if width>=height or abs(width/height-9/16)>0.03:return result|{'status':'geometry_mismatch'}
    return result|{'status':'public_verified'}

def reconcile_snapshot(*,target_slug,target_content_sha256,post,main_sha,public_status,public_url,public_body,state,media_items,youtube_rows,pr,check_runs,workflow_runs,timestamp):
    state=state if isinstance(state,dict) else {}
    source=source_metadata(post) if isinstance(post,dict) else None
    source_matches=bool(source and source['slug']==target_slug and source['content_sha256']==target_content_sha256)
    source_state={'status':'present' if source_matches else 'identity_mismatch' if source else 'missing','main_sha':main_sha}
    if source:source_state['observed_content_sha256']=source['content_sha256']
    expected_url=SITE_URL+'/blog/'+target_slug
    healthy=False
    if public_url!=expected_url:public_state='route_mismatch'
    elif public_status==200 and source_matches:
        canonical=re.search(r'<link\b(?=[^>]*\brel=[\"\']canonical[\"\'])(?=[^>]*\bhref=[\"\']([^\"\']+)[\"\'])[^>]*>',public_body,re.I)
        text=' '.join(clean_article_html(public_body).split());body=' '.join(clean_article_html(post['content']).split())
        healthy=bool(canonical and canonical.group(1)==expected_url and source['title'] in text and body and body in text)
        public_state='healthy' if healthy else 'route_or_content_mismatch'
    else:public_state='source_exists_not_deployed' if source_matches else 'missing'
    drift=[]
    delivered={'complete','completed','delivered','published','uploaded','verified'}
    bound=(state.get('source') or {}).get('slug')==target_slug and (state.get('source') or {}).get('content_sha256')==target_content_sha256
    if not bound:drift.append('orphaned_state')
    article=state.get('article') or {}
    if bound and article.get('status') in delivered and not healthy:drift.append('article_delivered_public_missing')
    if healthy and (not bound or article.get('status') not in delivered):drift.append('article_public_state_behind')
    media={kind:_media(kind,media_items,youtube_rows,target_slug,target_content_sha256) for kind in ('overview','short')}
    for kind,key in (('overview','long_video'),('short','short')):
        stage=state.get(key) or {};public=media[kind]['status']=='public_verified'
        if bound and stage.get('status') in delivered and media[kind]['status'] in ('private','unlisted','metadata_mismatch','geometry_mismatch','public_missing_or_inaccessible'):
            drift.append(kind+'_delivered_public_missing')
        elif bound and stage.get('status') in delivered and media[kind]['status'] in ('identity_unproven','remote_metadata_unavailable'):
            drift.append(kind+'_delivery_unproven')
        if public and (not bound or stage.get('status') not in delivered):drift.append(kind+'_public_state_behind')
    if healthy and (not bound or (state.get('long_video') or {}).get('status') in ('pending','waiting')):drift.append('upstream_complete_downstream_waiting')
    if media['overview']['status']=='public_verified' and (not bound or (state.get('short') or {}).get('status') in ('pending','waiting')):drift.append('upstream_complete_downstream_waiting')
    pr_state=None;blocked=False
    if isinstance(pr,dict):
        pr_state={k:pr.get(k) for k in ('number','state','draft','merged','target_matches')};head=(pr.get('head') or {}).get('sha');pr_state['head_sha']=head
        if pr.get('target_matches') is not True:drift.append('stale_pr')
        else:
            runs=[r for r in workflow_runs if r.get('head_sha')==head]
            checks=[c for c in check_runs if c.get('head_sha')==head]
            blocked=any(r.get('conclusion') in ('action_required','failure','cancelled','timed_out') for r in runs+checks)
            pr_state['check_conclusions']=[r.get('conclusion') for r in runs+checks]
            if blocked:drift.append('blocked_pr_checks')
    recommended='wait_for_maintainer' if blocked else 'reconcile_authoritative_state' if drift else 'observe'
    active=state.get('last_action') or state.get('next_action') or state.get('status')
    return dict(target_slug=target_slug,target_content_sha256=target_content_sha256,article_source_state=source_state,
                article_public_state={'status':public_state,'http_status':public_status,'url':expected_url},
                video_overview_state=media['overview'],short_state=media['short'],
                automation_state={'schema_version':state.get('schema_version'),'cycle':state.get('cycle'),'status':state.get('status'),'target_matches':bound},
                github_pr_state=pr_state,detected_drift=sorted(set(drift)),active_v5_decision=active,
                v6_recommended_decision=recommended,agreement=(active==recommended) if active else None,
                production_dispatch_enabled=False,production_state_written=False,provider_dispatch_enabled=False,upload_enabled=False,
                evidence=[],timestamp=timestamp)

def _post(posts,slug):
    rows=[p for p in (posts or []) if str(p.get('slug') or p.get('id'))==slug]
    if len(rows)>1:raise ValueError('V6_AMBIGUOUS_ARTICLE_SOURCE')
    return rows[0] if rows else None

def observe(client,*,slug,content_sha256,pr_number=None):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',slug) or not re.fullmatch(r'[a-f0-9]{64}',content_sha256):raise ValueError('V6_EXACT_TARGET_REQUIRED')
    main=client.request('GET',client.api+'/commits/main');main_sha=(main or {}).get('sha')
    if not main_sha:raise ValueError('V6_CURRENT_MAIN_UNAVAILABLE')
    posts=(client.contents('src/data/posts.json',main_sha) or [])+(client.contents('src/data/postsRecent.json',main_sha) or [])
    post=_post(posts,slug)
    state=client.contents('.kesher-controller/state.json','automation-state') or {}
    selected=pr_number or (state.get('article') or {}).get('pr_number')
    pr=None;checks=[];runs=[]
    if selected:
        pr=client.request('GET',client.api+'/pulls/'+str(int(selected)))
        if pr:
            head=pr['head']['sha']
            candidates=(client.contents('src/data/posts.json',head) or [])+(client.contents('src/data/postsRecent.json',head) or [])
            target=_post(candidates,slug)
            pr['target_matches']=bool(target and source_metadata(target)['content_sha256']==content_sha256)
            checks=(client.request('GET',client.api+'/commits/'+head+'/check-runs?per_page=100') or {}).get('check_runs',[])
            runs=(client.request('GET',client.api+'/actions/runs?head_sha='+head+'&per_page=100') or {}).get('workflow_runs',[])
    status,body,final_url=client.request('GET',SITE_URL+'/blog/'+slug,raw=True)
    items,coverage=client.media_receipts()
    ids={i['youtube_id'] for i in items if i.get('youtube_id') and (i.get('source') or {}).get('slug')==slug and (i.get('source') or {}).get('content_sha256')==content_sha256}
    rows=client.youtube(ids)
    result=reconcile_snapshot(target_slug=slug,target_content_sha256=content_sha256,post=post,main_sha=main_sha,
        public_status=status,public_url=final_url,public_body=body.decode('utf-8',errors='replace'),state=state,
        media_items=items,youtube_rows=rows,pr=pr,check_runs=checks,workflow_runs=runs,timestamp=datetime.now(timezone.utc).isoformat())
    result['evidence']=client.evidence;result['media_receipt_coverage']=coverage
    return result

def summary(report):
    return ('V6 read-only shadow: '+report['target_slug']+'\n\n'
            +'Article: '+report['article_public_state']['status']+'; Overview: '+report['video_overview_state']['status']+'; Short: '+report['short_state']['status']+'\n\n'
            +'Recommendation: '+report['v6_recommended_decision']+'\n\n'
            +'Drift: '+', '.join(report['detected_drift'])+'\n\nNO production dispatch or state writes.\n')
