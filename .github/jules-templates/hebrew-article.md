אל תשאל שאלות. כתוב מאמר אחד בלבד בעברית ישראלית טבעית: Hook חזק, ואז BLUF, מבנה פרקטי עם כותרות ודוגמאות ו-CTA רך. יעד 700-1100 מילים. 

ביצוע 3 משימות מאוחדות בריצה יחידה אחת:
1. **מאמר ו-SEO:** כתיבת המאמר, הזנת תגיות `imageAlt` עשירות במילות מפתח (יועצת זוגית, הדרכת הורים, אשדוד, רווקות מאוחרת, רילוקיישן), ועדכון `src/data/posts.json`.
2. **תמונה מותאמת (3-Tier Pipeline):** הרצת `node scripts/generate-article-image.js <slug> <title> '<prompt>'`. המערכת תנסה AI / Gemini / DeepAI, ואם חסר או נכשל תבצע Fallback אוטומטי לתמונת איכות חופשית מ-Unsplash ותשמור ל-`public/images/generated/blog/<slug>.jpg`.
3. **וידאו תגובתי מלהיב ב-Remotion (Reels/Shorts לנייד):** הרצת `node scripts/render-article-video.js <slug>`. המערכת תייצר סרטון 9:16 צבעוני, מונפש ומלהיב המותאם לנייד, ותשמור ל-`public/videos/generated/<slug>.mp4` ותחבר את השדה `video` ב-`posts.json`.

הרץ npm ci ו-npm run check. פתח PR אמיתי מאוחד.
