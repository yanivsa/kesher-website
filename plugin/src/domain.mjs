import resourceIndex from "../data/kesher-resources.json" with { type: "json" };

const TOPICS={money:"כסף והתנהלות כלכלית",household:"חלוקת עומס ומטלות בבית",parenting:"הורות וקבלת החלטות לגבי הילדים",extended_family:"גבולות מול המשפחה המורחבת",attention_connection:"זמן, נוכחות ותחושת חיבור",trust:"אמון וביטחון בקשר",intimacy:"קרבה ואינטימיות",recurring_other:"נושא שחוזר שוב ושוב"};
const SIGNALS={criticism:"בקשה או קושי נשמעים כביקורת",defensiveness:"נוצרת התגוננות במקום הקשבה",withdrawal:"אחד הצדדים נסגר או מתרחק",pursuit:"אחד הצדדים לוחץ להמשיך את השיחה",escalation:"הטון והעוצמה עולים במהירות",repetition:"אותו ויכוח חוזר בלי תוצאה חדשה",failed_repair:"יש ניסיון להתפייס אבל השינוי לא מחזיק",mistrust:"שאלות או בירורים נחווים כחוסר אמון",overload:"העומס גורם לבקשות להישמע כהאשמה"};
const ALLOWED_PATTERN_GOALS=new Set(["understand_pattern","deescalate","restart_conversation"]);
const ALLOWED_TOPICS=new Set(Object.keys(TOPICS));
const ALLOWED_SIGNALS=new Set(Object.keys(SIGNALS));
const PLAN_GOALS=new Set(["express_hurt","request_change","discuss_money","discuss_household","discuss_parenting","set_family_boundary","ask_for_connection","discuss_intimacy","repair_after_conflict"]);
const INTENSITY=new Set(["low","moderate","high"]),RISKS=new Set(["none","defensiveness","withdrawal","escalation"]),TONES=new Set(["gentle","direct","neutral"]);
const AGE=new Set(["preschool","elementary","preteen","teen"]);
const PARENTING_CHALLENGES=new Set(["tantrum","boundaries","sibling_conflict","screens","bedtime","morning_routine","cooperation","transition","parent_disagreement","emotional_regulation","teen_connection"]);
const PARENTING_GOALS=new Set(["deescalate","set_boundary","increase_cooperation","prepare_conversation","build_routine","repair_connection"]);
const RESPONSE_STYLE=new Set(["calm_brief","collaborative","firm_kind"]);
const ADHD_CHALLENGES=new Set(["morning_routine","task_initiation","working_memory","transitions","organization","frustration","executive_function","impulsivity","screen_transition","gifted_adhd"]);
const ADHD_GOALS=new Set(["reduce_friction","build_external_support","start_task","complete_transition","increase_independence","recover_after_escalation"]);
const SUPPORT=new Set(["light","structured","high_structure"]);
const RESOURCE_DOMAINS=new Set(["couples","parenting","parenting_adhd"]);
const RESOURCE_TOPICS=new Set(["communication","recurring_conflict","money","household","parenting_alignment","trust","intimacy","extended_family","boundaries","tantrum","siblings","screens","bedtime","morning_routine","teen","emotional_regulation","adhd_morning","executive_function","organization","task_initiation","transitions","working_memory","impulsivity","frustration","gifted_adhd","other"]);

function assertEnum(value,allowed,field){if(!allowed.has(value))throw new TypeError(`Invalid ${field}: ${value}`);}
function assertExactKeys(input,allowed){if(!input||typeof input!=="object"||Array.isArray(input))throw new TypeError("Tool input must be an object");for(const key of Object.keys(input))if(!allowed.has(key))throw new TypeError(`Unexpected field: ${key}`);}
const unique=(items)=>[...new Set(items)];

export function getConflictPattern(input){
  assertExactKeys(input,new Set(["topic","interaction_signals","goal"]));
  const {topic,interaction_signals,goal}=input;assertEnum(topic,ALLOWED_TOPICS,"topic");assertEnum(goal,ALLOWED_PATTERN_GOALS,"goal");
  if(!Array.isArray(interaction_signals)||interaction_signals.length<1||interaction_signals.length>4)throw new TypeError("interaction_signals must contain 1-4 items");
  for(const signal of interaction_signals)assertEnum(signal,ALLOWED_SIGNALS,"interaction_signals");
  const signals=unique(interaction_signals),cycle=signals.map(s=>SIGNALS[s]).slice(0,4),pair=new Set(signals);
  let label="מעגל שחוזר על עצמו";if(pair.has("criticism")&&pair.has("defensiveness"))label="ביקורת–התגוננות";else if(pair.has("pursuit")&&pair.has("withdrawal"))label="לחץ–התרחקות";else if(pair.has("escalation"))label="הסלמה מהירה";else if(pair.has("failed_repair"))label="תיקון שלא מחזיק";else if(signals[0]==="mistrust")label="בירור–חשדנות–התגוננות";
  const next=goal==="deescalate"?"בפעם הבאה שהמעגל מתחיל, עצרו קודם את ההסלמה וקבעו מתי חוזרים לנושא.":goal==="restart_conversation"?"פתחו מחדש בזמן רגוע עם בקשה אחת קונקרטית ובלי רשימת עבר.":"זהו יחד את הרגע הראשון שבו המעגל מתחיל ותארו אותו כבעיה משותפת.";
  return{pattern_label_he:label,summary_he:`בנושא ${TOPICS[topic]}, התיאור מצביע על מעגל שבו ${cycle.join(" → ")}. זה תיאור של האינטראקציה, לא אבחון.`,cycle_steps_he:cycle.length>=2?cycle:[cycle[0],"התגובה מחזקת את אותה תחושה ומחזירה את השיחה להתחלה"],next_step_he:next,avoid_he:unique([pair.has("criticism")?"להתחיל ב'אתה תמיד' או 'את אף פעם'":"להרחיב את הוויכוח לכל ההיסטוריה",pair.has("withdrawal")?"לרדוף אחרי תשובה בזמן הצפה":"לדרוש פתרון מלא בזמן עוצמה גבוהה","לאבחן או לתייג את בן או בת הזוג"]).slice(0,3)};
}

const GOAL_INTENT={express_hurt:"לשתף שנפגעת בלי להפוך את הפגיעה להאשמה",request_change:"לבקש שינוי אחד ברור ומעשי",discuss_money:"לדבר על כסף מתוך מטרה משותפת",discuss_household:"לחלק עומס בצורה מפורשת והוגנת יותר",discuss_parenting:"למצוא כלל הורי משותף",set_family_boundary:"להגדיר גבול זוגי מול המשפחה המורחבת",ask_for_connection:"לבקש יותר זמן או נוכחות",discuss_intimacy:"לפתוח נושא של קרבה בלי לחץ",repair_after_conflict:"לתקן אחרי ריב לפני שחוזרים לנושא"};
export function getConversationPlan(input){
  assertExactKeys(input,new Set(["topic","goal","emotional_intensity","interaction_risk","tone"]));
  const {topic,goal,emotional_intensity,interaction_risk,tone}=input;assertEnum(topic,ALLOWED_TOPICS,"topic");assertEnum(goal,PLAN_GOALS,"goal");assertEnum(emotional_intensity,INTENSITY,"emotional_intensity");assertEnum(interaction_risk,RISKS,"interaction_risk");assertEnum(tone,TONES,"tone");
  const prefix=tone==="direct"?"חשוב לי שנדבר בצורה ברורה על":tone==="gentle"?"יש משהו שחשוב לי לדבר עליו ברוגע:":"אני רוצה שנקדיש כמה דקות ל";
  const steps=["פתח במשפט אחד שמתאר את הנושא ואת המטרה, בלי 'תמיד' ו'אף פעם'.","תאר דוגמה אחת עדכנית ומה היא גורמת לך להרגיש או להזדקק, בלי לייחס כוונות.","בקש בקשה אחת קטנה שאפשר להסכים עליה או לשנות יחד."];
  if(emotional_intensity==="high")steps.unshift("בחרו זמן שבו שניכם פנויים יחסית; אם יש הצפה, חכו לרגיעה.");
  if(interaction_risk==="defensiveness")steps.push("שקף במשפט אחד מה שמעת לפני שאתה מסביר את הצד שלך.");else if(interaction_risk==="withdrawal")steps.push("אפשרו הפסקה אבל קבעו מתי חוזרים לשיחה.");else if(interaction_risk==="escalation")steps.push("אם הקצב עולה, עצרו לפני שממשיכים בפרטים.");
  return{opening_he:`${prefix} ${TOPICS[topic]}. המטרה שלי היא ${GOAL_INTENT[goal]}, לא לקבוע מי אשם.`,steps_he:steps.slice(0,5),pause_phrase_he:interaction_risk==="withdrawal"?"אני רואה שקשה להמשיך עכשיו. בוא נעצור ונחזור לזה בזמן שקבענו.":"השיחה מתחממת. חשוב לי להמשיך, אבל עדיף לקחת הפסקה קצרה ולחזור רגועים.",repair_phrase_he:"אני לא רוצה שנילחם אחד בשני. אם הניסוח שלי פגע, אני רוצה לנסח מחדש.",avoid_phrases_he:["אתה תמיד…","את אף פעם…","אם באמת היה אכפת לך…","אין טעם לדבר איתך"]};
}

const PARENT_LABELS={tantrum:"התפרצות",boundaries:"גבולות",sibling_conflict:"מריבות אחים",screens:"מסכים",bedtime:"שעת שינה",morning_routine:"שגרת בוקר",cooperation:"שיתוף פעולה",transition:"מעברים",parent_disagreement:"פער בין ההורים",emotional_regulation:"ויסות רגשי",teen_connection:"קשר עם מתבגר"};
export function getParentingResponsePlan(input){
  assertExactKeys(input,new Set(["age_band","challenge","goal","response_style"]));
  const {age_band,challenge,goal,response_style}=input;assertEnum(age_band,AGE,"age_band");assertEnum(challenge,PARENTING_CHALLENGES,"challenge");assertEnum(goal,PARENTING_GOALS,"goal");assertEnum(response_style,RESPONSE_STYLE,"response_style");
  const label=PARENT_LABELS[challenge];
  const framing=challenge==="parent_disagreement"?"כשהורים נותנים מסרים שונים, הילד לומד לבדוק היכן הגבול גמיש. המטרה היא תיאום בין המבוגרים, לא גיוס הילד לצד אחד.":challenge==="tantrum"||challenge==="emotional_regulation"?"ברגע של הצפה הילד פחות פנוי ללמידה. קודם מורידים עוצמה, ואחר כך חוזרים לגבול או לשיחה.":`באתגר של ${label}, עדיף גבול קצר וצפוי עם פחות ויכוח ויותר עקביות.`;
  const steps=["נסחו מראש משפט אחד קצר שמתאר את הגבול או הצעד הבא.","צמצמו הסברים בזמן שהעוצמה גבוהה; חזרו על אותו מסר רגוע.","הציעו בחירה קטנה בתוך הגבול במקום לפתוח משא ומתן על עצם הגבול."];
  if(challenge==="sibling_conflict")steps.splice(1,1,"עצרו פגיעה, הפרידו אם צריך, ואל תמהרו לקבוע מי אשם לפני ששני הצדדים נרגעים.");
  if(challenge==="parent_disagreement")steps.splice(1,1,"מול הילד תנו מסר זמני אחיד, ואת הוויכוח בין ההורים העבירו לזמן פרטי.");
  if(challenge==="teen_connection")steps.splice(1,1,"החליפו חקירה בהזמנה קצרה לשיחה והשאירו פתח לחזור אליה בזמן אחר.");
  const phrase=response_style==="firm_kind"?"אני שומע שקשה לך, והגבול נשאר. אני כאן לעזור לך לעבור את זה.":response_style==="collaborative"?"אני רוצה שנמצא דרך שעובדת לשנינו בתוך הגבול הזה.":"אני איתך. עכשיו עושים צעד אחד קטן.";
  return{framing_he:framing,steps_he:steps,phrase_to_use_he:phrase,phrase_to_avoid_he:"אם לא תפסיק מיד, תראה מה יקרה לך.",follow_up_he:`אחרי שהמצב רגוע, בדקו מה אפשר לשנות מראש כדי שהפעם הבאה סביב ${label} תהיה צפויה וקלה יותר.`};
}

const ADHD_LABELS={morning_routine:"שגרת בוקר",task_initiation:"התחלת משימה",working_memory:"זיכרון עבודה",transitions:"מעברים",organization:"התארגנות וארגון",frustration:"תסכול מהיר",executive_function:"תפקודים ניהוליים",impulsivity:"עצירה לפני פעולה",screen_transition:"מעבר ממסך",gifted_adhd:"פער בין יכולת גבוהה להתארגנות"};
export function getAdhdParentingPlan(input){
  assertExactKeys(input,new Set(["age_band","challenge","goal","support_level"]));
  const {age_band,challenge,goal,support_level}=input;assertEnum(age_band,AGE,"age_band");assertEnum(challenge,ADHD_CHALLENGES,"challenge");assertEnum(goal,ADHD_GOALS,"goal");assertEnum(support_level,SUPPORT,"support_level");
  const label=ADHD_LABELS[challenge];
  const frame=`קושי ב${label} יכול להיראות כמו חוסר רצון גם כשהילד יודע מה צריך לעשות. כאן מתייחסים אליו כאתגר תפקודי שיכול להיעזר במבנה חיצוני — בלי לקבוע אבחנה.`;
  const adjustments=["הוציאו את השלבים מהראש אל הסביבה: רשימה קצרה, סימן חזותי או מקום קבוע לציוד.","הקטינו את נקודת ההתחלה לצעד ראשון ברור שאפשר לבצע מיד."];
  if(["transitions","screen_transition"].includes(challenge))adjustments.push("השתמשו בהתראה מוקדמת ובנקודת סיום ברורה במקום מעבר פתאומי.");
  if(["working_memory","organization","morning_routine"].includes(challenge))adjustments.push("הכינו מראש תחנה קבועה לציוד החוזר במקום להסתמך על תזכורות מילוליות.");
  if(support_level==="high_structure")adjustments.push("בנו רצף קבוע עם בדיקה קצרה בין שלבים והפחיתו תמיכה בהדרגה כשהרצף מתייצב.");
  const steps=["בחרו משימה אחת ולא את כל היום כפרויקט.","הגדירו מהו הצעד הראשון בלבד ובקשו להתחיל ממנו.","חזקו השלמה של התהליך או שימוש בכלי העזר, לא רק מהירות או צייתנות."];
  if(goal==="increase_independence")steps.push("העבירו אחריות בהדרגה: קודם המבוגר מצביע על הכלי, אחר כך הילד בודק אותו בעצמו.");
  if(goal==="recover_after_escalation")steps.unshift("אחרי הצפה, חזרו לתפקוד רק כשהעוצמה ירדה; לא מלמדים אסטרטגיה באמצע פיצוץ.");
  return{executive_function_frame_he:frame,environment_adjustments_he:adjustments.slice(0,4),parent_steps_he:steps.slice(0,5),phrase_he:"בוא נתחיל רק מהצעד הראשון. אני לא עושה במקומך, אני עוזר לך לראות מאיפה מתחילים.",avoid_he:["לייחס את הקושי לעצלנות או חוסר אכפתיות","להעמיס כמה הוראות בבת אחת","להשתמש באבחנה ככינוי או איום"],professional_support_note_he:"אם הקושי משמעותי ומתמשך בכמה מסגרות או פוגע בתפקוד, אפשר לשקול התייעצות עם איש מקצוע מוסמך. הכלי הזה אינו מאבחן ואינו נותן ייעוץ תרופתי."};
}

export function findKesherResource(input){
  assertExactKeys(input,new Set(["domain","topic","content_type"]));
  const {domain,topic,content_type}=input;assertEnum(domain,RESOURCE_DOMAINS,"domain");assertEnum(topic,RESOURCE_TOPICS,"topic");assertEnum(content_type,new Set(["any","article"]),"content_type");
  const scored=(resourceIndex.resources??[]).filter(r=>r.domain===domain&&(content_type==="any"||r.content_type===content_type)).map(r=>({r,score:(r.topics??[]).includes(topic)?3:topic==="other"?1:0})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score||String(b.r.date||"").localeCompare(String(a.r.date||"")));
  return{resources:scored.slice(0,3).map(({r})=>({slug:r.slug,title:r.title,url:r.url,domain:r.domain,topics:r.topics}))};
}
