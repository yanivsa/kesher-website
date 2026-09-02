const ORIGIN = 'https://my.nownownow.com';
const BRIDGE_KEY = 'm7Kp4Rz2Qv';
const SHIRA_PERSON_ID = '473901';
const noStoreHeaders = {'content-type':'application/json; charset=utf-8','cache-control':'no-store, max-age=0'};
const formBody = (v: Record<string,string>) => { const b=new URLSearchParams(); for (const [k,x] of Object.entries(v)) b.set(k,x); return b; };
const nnnFetch = (path:string, init:RequestInit={}) => fetch(`${ORIGIN}${path}`, {...init, redirect:'manual', cache:'no-store'});
const postForm = (path:string, values:Record<string,string>, cookie:string) => nnnFetch(path,{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded;charset=UTF-8',cookie:`ok=${cookie}`,'user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'},body:formBody(values)});
const extractInputValue=(html:string,name:string)=>{const e=name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');return new RegExp(`<input[^>]*name=["']${e}["'][^>]*value=["']([^"']*)["']`,'i').exec(html)?.[1]??new RegExp(`<input[^>]*value=["']([^"']*)["'][^>]*name=["']${e}["']`,'i').exec(html)?.[1]??null;};
const extractOkCookie=(r:Response)=>/(?:^|,|;)\s*ok=([^;]+)/i.exec(r.headers.get('set-cookie')||'')?.[1]??null;
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:noStoreHeaders});

async function requestLoginLink(){
  const r=await nnnFetch('/f',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded;charset=UTF-8','user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'},body:formBody({email:'yanivashdod@gmail.com'})});
  const body=await r.text();
  return json({ok:r.status>=200&&r.status<400,status:r.status,loginEmailRequested:/check/i.test(body)||r.status<400});
}

async function bootstrap(token:string){
  if(!/^[A-Za-z0-9_-]{8,64}$/.test(token)) return json({ok:false,error:'invalid token format'},400);
  const welcome=await nnnFetch(`/e?t=${encodeURIComponent(token)}&cb=${Date.now()}`,{headers:{'user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'}});
  const welcomeHtml=await welcome.text();
  const extracted=extractInputValue(welcomeHtml,'i');
  const personId=extracted&&/^\d+$/.test(extracted)?extracted:SHIRA_PERSON_ID;
  const login=await nnnFetch('/e',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded;charset=UTF-8','user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'},body:formBody({t:token,i:personId})});
  const cookie=extractOkCookie(login);
  if(!cookie) return json({ok:false,error:'login token rejected',status:login.status,location:login.headers.get('location'),welcomeRecognized:!!extracted},502);
  const where=await postForm('/where',{city:'Ashdod',state:'',country:'IL'},cookie);
  const urlsHtml=await (await nnnFetch('/urls',{headers:{cookie:`ok=${cookie}`,'user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'}})).text();
  let urlAdded=false; if(!urlsHtml.includes('kesher.saharoni.com')){await postForm('/urls',{url:'https://kesher.saharoni.com'},cookie);urlAdded=true;}
  const answers:Array<[string,string]>=[
    ['title','Couples counselor, parenting facilitator & certified mediator'],
    ['liner','I support couples, parents and families through communication, conflict, parenting challenges and major life transitions.'],
    ['why','I want to help people understand what is happening between them and build practical, respectful ways to move forward together.'],
    ['thought','Complex relationship and family challenges become more workable when we make them clear, practical and human.'],
    ['red','Children: The Challenge — Rudolf Dreikurs & Vicki Soltz']
  ];
  const profileStatuses:Record<string,number>={}; for(const [qcode,answer] of answers){profileStatuses[qcode]=(await postForm('/profile',{qcode,answer},cookie)).status;}
  let photoStatus:number|null=null,photoUploaded=false; const src=await fetch('https://kesher.saharoni.com/images/shira_revava_poster.jpg',{cache:'no-store'}); if(src.ok){const fd=new FormData();fd.append('photo',await src.blob(),'shira-saharoni.jpg');const p=await nnnFetch('/photo',{method:'POST',headers:{cookie:`ok=${cookie}`,'user-agent':'Kesher-Saharoni-NNN-Setup/1.0'},body:fd});photoStatus=p.status;photoUploaded=p.status>=200&&p.status<400;}
  const profileHtml=await (await nnnFetch('/profile',{headers:{cookie:`ok=${cookie}`,'user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'}})).text();
  const photoHtml=await (await nnnFetch('/photo',{headers:{cookie:`ok=${cookie}`,'user-agent':'Kesher-Saharoni-NNN-Setup/1.0','cache-control':'no-cache'}})).text();
  return json({ok:true,personId,loginStatus:login.status,locationStatus:where.status,urlAdded,profileStatuses,profileComplete:!profileHtml.includes('name="qcode"')&&!profileHtml.includes('Professional title?'),photoUploaded,photoStatus,photoPageShowsImage:/<img\b/i.test(photoHtml),permanentProfile:'https://nownownow.com/p/Y5Gp'});
}

export const onRequestPost:PagesFunction=async({request})=>{try{const p=await request.json() as {key?:string;token?:string;requestLink?:boolean};if(p.key!==BRIDGE_KEY)return json({ok:false,error:'forbidden'},403);return p.requestLink?requestLoginLink():bootstrap((p.token||'').trim());}catch(e){return json({ok:false,error:e instanceof Error?e.message:String(e)},500);}};
export const onRequestGet:PagesFunction=async({request})=>{try{const u=new URL(request.url);if(u.searchParams.get('key')!==BRIDGE_KEY)return json({ok:false,error:'forbidden'},403);if(u.searchParams.get('requestLink')==='1')return requestLoginLink();return bootstrap((u.searchParams.get('t')||'').trim());}catch(e){return json({ok:false,error:e instanceof Error?e.message:String(e)},500);}};
