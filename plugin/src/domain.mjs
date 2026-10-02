const TOPICS = {
  money: "כסף והתנהלות כלכלית",
  household: "חלוקת עומס ומטלות בבית",
  parenting: "הורות וקבלת החלטות לגבי הילדים",
  extended_family: "גבולות מול המשפחה המורחבת",
  attention_connection: "זמן, נוכחות ותחושת חיבור",
  trust: "אמון וביטחון בקשר",
  intimacy: "קרבה ואינטימיות",
  recurring_other: "נושא שחוזר שוב ושוב"
};

const SIGNALS = {
  criticism: "בקשה או קושי נשמעים כביקורת",
  defensiveness: "נוצרת התגוננות במקום הקשבה",
  withdrawal: "אחד הצדדים נסגר או מתרחק",
  pursuit: "אחד הצדדים לוחץ להמשיך את השיחה",
  escalation: "הטון והעוצמה עולים במהירות",
  repetition: "אותו ויכוח חוזר בלי תוצאה חדשה",
  failed_repair: "יש ניסיון להתפייס אבל השינוי לא מחזיק",
  mistrust: "שאלות או בירורים נחווים כחוסר אמון",
  overload: "העומס גורם לבקשות להישמע כהאשמה"
};

const ALLOWED_PATTERN_GOALS = new Set(["understand_pattern","deescalate","restart_conversation"]);
const ALLOWED_TOPICS = new Set(Object.keys(TOPICS));
const ALLOWED_SIGNALS = new Set(Object.keys(SIGNALS));

function assertEnum(value, allowed, field) {
  if (!allowed.has(value)) throw new TypeError(`Invalid ${field}: ${value}`);
}

function unique(items) {
  return [...new Set(items)];
}

export function getConflictPattern({ topic, interaction_signals, goal }) {
  assertEnum(topic, ALLOWED_TOPICS, "topic");
  assertEnum(goal, ALLOWED_PATTERN_GOALS, "goal");
  if (!Array.isArray(interaction_signals) || interaction_signals.length < 1 || interaction_signals.length > 4) {
    throw new TypeError("interaction_signals must contain 1-4 items");
  }
  for (const signal of interaction_signals) assertEnum(signal, ALLOWED_SIGNALS, "interaction_signals");

  const signals = unique(interaction_signals);
  const topicLabel = TOPICS[topic];
  const cycle = signals.map((signal) => SIGNALS[signal]).slice(0, 4);

  const primary = signals[0];
  const pair = new Set(signals);
  let label = "מעגל שחוזר על עצמו";
  if (pair.has("criticism") && pair.has("defensiveness")) label = "ביקורת–התגוננות";
  else if (pair.has("pursuit") && pair.has("withdrawal")) label = "לחץ–התרחקות";
  else if (pair.has("escalation")) label = "הסלמה מהירה";
  else if (pair.has("failed_repair")) label = "תיקון שלא מחזיק";
  else if (primary === "mistrust") label = "בירור–חשדנות–התגוננות";

  const nextStep =
    goal === "deescalate"
      ? "בפעם הבאה שהמעגל מתחיל, עצרו את הדיון בתוכן ונסו קודם להוריד את העוצמה: משפט קצר שמכיר בקושי, בקשה להפסקה מוסכמת, וחזרה בזמן שקבעתם."
      : goal === "restart_conversation"
        ? "פתחו מחדש את הנושא בזמן רגוע, עם תיאור קצר של מה חשוב לכם ובקשה אחת קונקרטית, בלי רשימת אירועים מהעבר."
        : "נסו לזהות את הרגע הראשון שבו המעגל מתחיל — לפני שהטון עולה — ולתאר אותו יחד כבעיה משותפת במקום כהוכחה שמישהו 'אשם'.";

  const avoid = unique([
    pair.has("criticism") ? "להתחיל ב'אתה תמיד' או 'את אף פעם'" : "להרחיב את הוויכוח לכל ההיסטוריה של הקשר",
    pair.has("withdrawal") ? "לרדוף אחרי תשובה בזמן שהצד השני מוצף" : "לדרוש פתרון מלא בזמן שהעוצמה גבוהה",
    "לאבחן או לתייג את בן או בת הזוג"
  ]).slice(0, 3);

  return {
    pattern_label_he: label,
    summary_he: `בנושא ${topicLabel}, התיאור מצביע על מעגל תקשורתי שבו ${cycle.join(" → ")}. זה תיאור של האינטראקציה, לא אבחון של אף אחד מבני הזוג.`,
    cycle_steps_he: cycle.length >= 2 ? cycle : [cycle[0], "התגובה מחזקת את אותה תחושה ומחזירה את השיחה לנקודת ההתחלה"],
    next_step_he: nextStep,
    avoid_he: avoid
  };
}

const PLAN_GOALS = new Set([
  "express_hurt","request_change","discuss_money","discuss_household","discuss_parenting",
  "set_family_boundary","ask_for_connection","discuss_intimacy","repair_after_conflict"
]);
const INTENSITY = new Set(["low","moderate","high"]);
const RISKS = new Set(["none","defensiveness","withdrawal","escalation"]);
const TONES = new Set(["gentle","direct","neutral"]);

const GOAL_INTENT = {
  express_hurt: "לשתף שנפגעת בלי להפוך את הפגיעה להאשמה",
  request_change: "לבקש שינוי אחד ברור ומעשי",
  discuss_money: "לדבר על כסף מתוך מטרה משותפת ולא מתוך מאבק על מי צודק",
  discuss_household: "לחלק עומס בצורה מפורשת והוגנת יותר",
  discuss_parenting: "למצוא כלל הורי משותף גם כשיש פער בגישה",
  set_family_boundary: "להגדיר גבול זוגי מול המשפחה המורחבת",
  ask_for_connection: "לבקש יותר זמן או נוכחות בלי להציג את הצד השני ככישלון",
  discuss_intimacy: "לפתוח נושא של קרבה בלי לחץ, דרישה או בושה",
  repair_after_conflict: "לתקן אחרי ריב לפני שחוזרים לפתור את הנושא עצמו"
};

export function getConversationPlan({ topic, goal, emotional_intensity, interaction_risk, tone }) {
  assertEnum(topic, ALLOWED_TOPICS, "topic");
  assertEnum(goal, PLAN_GOALS, "goal");
  assertEnum(emotional_intensity, INTENSITY, "emotional_intensity");
  assertEnum(interaction_risk, RISKS, "interaction_risk");
  assertEnum(tone, TONES, "tone");

  const topicLabel = TOPICS[topic];
  const prefix = tone === "direct" ? "חשוב לי שנדבר בצורה ברורה על" : tone === "gentle" ? "יש משהו שחשוב לי לדבר עליו ברוגע:" : "אני רוצה שנקדיש כמה דקות ל";
  const opening = `${prefix} ${topicLabel}. המטרה שלי היא ${GOAL_INTENT[goal]}, לא לקבוע מי אשם.`;

  const steps = [
    "פתח במשפט אחד שמתאר את הנושא ואת המטרה, בלי 'תמיד' ו'אף פעם'.",
    "תאר דוגמה אחת עדכנית ומה היא גורמת לך להרגיש או להזדקק, בלי לייחס כוונות לצד השני.",
    "בקש בקשה אחת קטנה שאפשר להסכים עליה או לשנות אותה יחד."
  ];

  if (emotional_intensity === "high") {
    steps.unshift("בחרו זמן שבו שניכם פנויים יחסית; אם כבר יש הצפה, אל תתחילו את השיחה עכשיו.");
  }

  if (interaction_risk === "defensiveness") {
    steps.push("לפני שאתה עונה לטיעון נגדי, נסה לשקף במשפט אחד מה שמעת ורק אחר כך הסבר את הצד שלך.");
  } else if (interaction_risk === "withdrawal") {
    steps.push("הסכימו מראש שאפשר לקחת הפסקה, אבל קבעו מתי חוזרים לשיחה כדי שהפסקה לא תהפוך להיעלמות.");
  } else if (interaction_risk === "escalation") {
    steps.push("אם הקול או הקצב עולים, עצרו לפני שממשיכים בפרטים; חזרה לנושא אחרי רגיעה עדיפה על ניצחון בריב.");
  }

  const pause =
    interaction_risk === "withdrawal"
      ? "אני רואה שקשה לנו להמשיך עכשיו. בוא נעצור ונחזור לזה בשעה שקבענו, כדי שלא נוותר על הנושא."
      : "אני מרגיש שהשיחה מתחממת. חשוב לי להמשיך, אבל עדיף שניקח הפסקה קצרה ונחזור לזה רגועים יותר.";

  return {
    opening_he: opening,
    steps_he: steps.slice(0, 5),
    pause_phrase_he: pause,
    repair_phrase_he: "אני לא רוצה שנילחם אחד בשני. אם הניסוח שלי פגע, אני רוצה לנסח מחדש ולהישאר עם הנושא.",
    avoid_phrases_he: ["אתה תמיד…", "את אף פעם…", "אם באמת היה אכפת לך…", "אין טעם לדבר איתך"]
  };
}
