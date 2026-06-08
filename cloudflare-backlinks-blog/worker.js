export default {
  async fetch(request, env, ctx) {
    const html = `<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מרכז משאבים ומאמרים: זוגיות והדרכת הורים</title>
    <meta name="description" content="מאמרים מקצועיים, טיפים ומשאבים בנושא ייעוץ זוגי והדרכת הורים ל-ADHD באשדוד והסביבה.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Rubik:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --bg: #fafafa;
            --card-bg: #ffffff;
            --text: #1f2937;
            --text-muted: #4b5563;
            --border: #e5e7eb;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text: #f8fafc;
                --text-muted: #cbd5e1;
                --border: #334155;
            }
        }
        body {
            font-family: 'Rubik', 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 0;
            line-height: 1.7;
        }
        header {
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: white;
            text-align: center;
            padding: 4rem 2rem;
            margin-bottom: 3rem;
            border-bottom: 1px solid var(--border);
        }
        header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 700;
        }
        header p {
            font-size: 1.2rem;
            opacity: 0.9;
            margin-top: 1rem;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }
        article {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2.5rem;
            margin-bottom: 3rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        article:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        article h2 {
            font-size: 1.8rem;
            color: var(--primary);
            margin-top: 0;
            margin-bottom: 1.5rem;
        }
        article p {
            margin-bottom: 1.5rem;
            color: var(--text-muted);
        }
        article a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            border-bottom: 2px solid transparent;
            transition: border-color 0.2s ease;
        }
        article a:hover {
            border-color: var(--primary);
        }
        .meta {
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            display: flex;
            gap: 1rem;
        }
        footer {
            text-align: center;
            padding: 3rem;
            margin-top: 5rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>מרכז משאבים ומאמרים חיצוניים</h1>
            <p>מאמרים מקצועיים ומידע בתחומי זוגיות והדרכת הורים</p>
        </div>
    </header>

    <div class="container">
        <!-- מאמר 1 -->
        <article>
            <h2>קשר במשבר: מתי כדאי לפנות לייעוץ זוגי ואיך לבחור את המטפל הנכון?</h2>
            <div class="meta">
                <span>מאת: שירה סהרוני</span>
                <span>•</span>
                <span>זמן קריאה: 3 דק'</span>
            </div>
            <p>שנים של חיים משותפים מביאות איתן לא פעם אתגרים מורכבים. שחיקה יומיומית, קשיים בתקשורת או שינויים במבנה המשפחתי עלולים ליצור מרחק בין בני הזוג. במקרים רבים, זוגות מוצאים את עצמם בלולאה אינסופית של ויכוחים מבלי להגיע לפתרון.</p>
            <p>אם אתם מחפשים <a href="https://kesher.saharoni.com" target="_blank" rel="dofollow">יועצת זוגית באשדוד מומלצת</a>, חשוב להבין שפנייה לייעוץ היא סימן לעוצמה ורצון לשפר את איכות החיים המשותפת, ולא הודאה בכישלון.</p>
            <h3>מתי כדאי לפנות לייעוץ זוגי?</h3>
            <p>1. <strong>כשעולה תחושת שחיקה וריחוק:</strong> מרגישים שאתם חיים כמו "שותפים לדירה" ולא כבני זוג? זהו אחד הסימנים המובהקים לצורך בחידוש החיבור הרגשי.</p>
            <p>2. <strong>ויכוחים חוזרים על אותם נושאים:</strong> כסף, חינוך הילדים, מטלות הבית — כשהנושאים הללו הופכים לזירת מלחמה קבועה.</p>
            <p>3. <strong>משבר אמון:</strong> לאחר בגידה, הסתרת סודות או פגיעה קשה באמון ההדדי, ליווי מקצועי הוא כמעט הכרחי כדי לבנות את היסודות מחדש.</p>
            <h3>איך בוחרים את המלווה המתאים?</h3>
            <p>כשמחפשים תמיכה מקצועית באזור המגורים שלכם, כגון <a href="https://kesher.saharoni.com/services/couples" target="_blank" rel="dofollow">ייעוץ זוגי באשדוד</a>, כדאי לשים לב להסמכה של המטפלת, לגישה הטיפולית שלה, ובעיקר לחיבור הבינאישי שנוצר איתה כבר בפגישה הראשונה. קליניקה נגישה פיזית באזור המגורים שלכם מקלה מאוד על ההתמדה בתהליך, שהיא המפתח להצלחה.</p>
        </article>

        <!-- מאמר 2 -->
        <article>
            <h2>לגדל ילד עם קשב וריכוז: איך הדרכת הורים משנה את האווירה בבית</h2>
            <div class="meta">
                <span>מאת: שירה סהרוני</span>
                <span>•</span>
                <span>זמן קריאה: 3 דק'</span>
            </div>
            <p>גידול ילדים הוא משימה מאתגרת בפני עצמה, אך כאשר מתווספת לתמונה אבחנת קשב וריכוז (ADHD), ההתמודדות היומיומית הופכת מורכבת בהרבה. הורים רבים מוצאים את עצמם בעומס רגשי מתמיד, מתוסכלים מהתפרצויות זעם ומחוסר שיתוף פעולה במטלות פשוטות כמו התארגנות בבוקר או הכנת שיעורי בית.</p>
            <p>לשם כך נועדה <a href="https://kesher.saharoni.com/services/parenting" target="_blank" rel="dofollow">הדרכת הורים ADHD אשדוד</a> — להעניק להורים את הכלים הפרקטיים להתמודד עם המאפיינים הייחודיים של הילד, ללא צורך במאבקי כוח בלתי פוסקים או עונשים שרק מגבירים את התסכול.</p>
            <h3>מה נותנת לכם הדרכת הורים מקצועית?</h3>
            <p>* <strong>הבנה מעמיקה של עולמו של הילד:</strong> מה שנראה לעיתים כעקשנות או חוצפה הוא לרוב קושי אמיתי בוויסות רגשי או בניהול זמן.</p>
            <p>* <strong>בניית שגרה מותאמת:</strong> כלים לעיצוב סדר יום ברור ומובנה שמפחית חרדה ומגדיל את שיתוף הפעולה.</p>
            <p>* <strong>חיזוק הקשר ההורי:</strong> כיצד להוביל את הבית מתוך סמכות הורית בריאה, חמלה וחיבור רגשי חזק.</p>
            <p>אם אתם מתמודדים עם אתגרים דומים ומחפשים ליווי מקצועי שיחזיר את השקט והביטחון המשפחתי, מומלץ לפנות למנחת הורים מנוסה המכירה את הקשיים הללו מקרוב.</p>
        </article>


        <!-- מאמר 4 באנגלית -->
        <article lang="en" dir="ltr">
            <h2>Navigating Love, Parenting, and ADHD: The Modern Family's Balancing Act</h2>
            <div class="meta">
                <span>By: Shira Saharoni</span>
                <span>•</span>
                <span>Read time: 3 min</span>
            </div>
            <p>Every long-term relationship experiences natural seasons of conflict, transition, and renegotiation. However, in modern households where parenting demands collide with executive functioning challenges like ADHD, these pressure points can quickly amplify into chronic marital distress.</p>
            <p>For English-speaking couples and families residing in Israel, accessing culturally attuned, language-fluent professional help is crucial. Many find that seeking a licensed <a href="https://kesher.saharoni.com" target="_blank" rel="dofollow">couples therapist Ashdod Israel</a> provides the safe space needed to restore mutual empathy and open dialogue.</p>
            <h3>The ADHD Factor in Couples Dynamics</h3>
            <p>When a child or partner is diagnosed with ADHD, it is never just an individual concern; it is a family system dynamic. Common challenges include:</p>
            <p>* <strong>The Parent-Child Trap:</strong> One partner takes on all administrative and scheduling duties, leading to resentment and a dynamic that feels more like parent-and-child than equal partners.</p>
            <p>* <strong>Emotional Dysregulation:</strong> ADHD often manifests as sudden emotional storms, which can leave spouses feeling walking on eggshells.</p>
            <p>* <strong>Chronic Overwhelm:</strong> Navigating school systems, homework, and routines in Israel can be overwhelming without specialized guidance.</p>
            <h3>Finding Integrated Solutions</h3>
            <p>The most effective approach often combines relationship counseling with specialized <a href="https://kesher.saharoni.com/services/parenting" target="_blank" rel="dofollow">parenting guidance ADHD Israel</a>. Learning practical behavioral strategies for the kids while simultaneously healing the adult partnership creates a unified parental front.</p>
        </article>
    </div>

    <footer>
        <div class="container">
            <p>כל הזכויות שמורות לשירה סהרוני — ייעוץ זוגי והדרכת הורים © 2026</p>
            <p>קישור לאתר הראשי: <a href="https://kesher.saharoni.com" target="_blank" rel="dofollow">kesher.saharoni.com</a></p>
        </div>
    </footer>
</body>
</html>
`;
    return new Response(html, {
      headers: {
        "content-type": "text/html;charset=UTF-8",
        "access-control-allow-origin": "*"
      }
    });
  }
};
