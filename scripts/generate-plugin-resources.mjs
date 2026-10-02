import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"..");
const sourcePath=path.join(root,"src/data/posts.json");
const outPath=path.join(root,"plugin/data/kesher-resources.json");
const source=JSON.parse(fs.readFileSync(sourcePath,"utf8"));
const posts=Array.isArray(source)?source:(source.posts??[]);

function postText(p){return JSON.stringify({title:p.title??"",category:p.category??"",tags:p.tags??[],summary:p.summary??"",description:p.description??""}).toLowerCase();}
function topicsFor(p,domain){
  const s=postText(p),t=new Set(),has=(re)=>re.test(s);
  if(domain==="couples"){
    if(has(/תקשורת|הקשב|שיחה|communication/))t.add("communication");
    if(has(/ריב|קונפליקט|בעיה תמיד|ויכוח/))t.add("recurring_conflict");
    if(has(/כסף|כלכל|תקציב/))t.add("money");
    if(has(/מטלות|עומס|mental load|חלוקת/))t.add("household");
    if(has(/אמון|בגידה|trust/))t.add("trust");
    if(has(/אינטימ|קרבה/))t.add("intimacy");
    if(has(/מסך|מסכ|טלפון|טאבלט/))t.add("screens");
    if(has(/משפחה המורחבת|משפחות המוצא|גבולות למשפחה/))t.add("extended_family");
    if(has(/הורות|ילדים|הורים/))t.add("parenting_alignment");
  }else{
    if(has(/גבול|סמכות|עונש/))t.add("boundaries");
    if(has(/התפרצ|זעם|צעק|טנטרום/))t.add("tantrum");
    if(has(/אחים|אחיות|מריבות אחים/))t.add("siblings");
    if(has(/מסך|מסכ|טלפון|טאבלט/))t.add("screens");
    if(has(/שינה|השכבה|הרדמה|bedtime/))t.add("bedtime");
    if(has(/בוקר|morning/))t.add(domain==="parenting_adhd"?"adhd_morning":"morning_routine");
    if(has(/מתבגר|teen/))t.add("teen");
    if(has(/ויסות|רגשי|חרדה|תסכול|כישלון|פרפקציונ/))t.add(domain==="parenting_adhd"?"frustration":"emotional_regulation");
    if(has(/שוטר הרע|פערים בחינוך|בין בני הזוג|סותרים/))t.add("parenting_alignment");
    if(domain==="parenting_adhd"){
      if(has(/תפקודים ניהוליים|executive/))t.add("executive_function");
      if(has(/התארג|ארגון|organ/))t.add("organization");
      if(has(/התחל|שיעורי בית|משימה/))t.add("task_initiation");
      if(has(/מעבר|transition/))t.add("transitions");
      if(has(/שוכח|זיכרון|remember/))t.add("working_memory");
      if(has(/אימפול/))t.add("impulsivity");
      if(has(/מחונ/))t.add("gifted_adhd");
    }
  }
  if(t.size===0)t.add("other");
  return [...t];
}
const resources=[];
for(const p of posts){
  const s=postText(p),cat=p.category??"";
  let domain=null;
  if(/adhd|הפרעת קשב|קשיי קשב|תפקודים ניהוליים|קשב וריכוז/.test(s))domain="parenting_adhd";
  else if(/הדרכת הורים|הנחיית הורים/.test(cat))domain="parenting";
  else if(/זוגיות|ייעוץ זוגי/.test(cat))domain="couples";
  if(!domain)continue;
  const slug=p.id;
  if(!slug||!p.title)continue;
  resources.push({slug,title:p.title,url:`https://kesher.saharoni.com/blog/${slug}`,domain,topics:topicsFor(p,domain),content_type:"article",date:p.date||null});
}
resources.sort((a,b)=>(b.date||"").localeCompare(a.date||"")||a.slug.localeCompare(b.slug));
const payload={schema_version:"1.0",generated_at:"2026-10-02",source:"src/data/posts.json",count:resources.length,resources};
const rendered=JSON.stringify(payload,null,2)+"\n";
if(process.argv.includes("--check")){
  const existing=fs.existsSync(outPath)?fs.readFileSync(outPath,"utf8"):"";
  if(existing!==rendered){
    console.error("plugin/data/kesher-resources.json is stale. Run node scripts/generate-plugin-resources.mjs");
    process.exit(1);
  }
  console.log(`PASS: Kesher resource index is current (${resources.length} resources).`);
}else{
  fs.mkdirSync(path.dirname(outPath),{recursive:true});
  fs.writeFileSync(outPath,rendered);
  console.log(`Generated ${resources.length} Kesher plugin resources.`);
}
