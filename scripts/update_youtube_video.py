import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    
    title = "למה בעלך לא משתף אותך? (הטעות שנשים עושות בלי לשים לב)"
    description = """האם את מרגישה שבעלך נעול כמו קיר ולא משתף אותך ברגשות שלו? 
בסרטון זה נחשוף את שורש הבעיה לפי מחקריה של ברנה בראון, נציג מקרה קלאסי של התנגשות תקשורתית בין בני זוג, ונלמד אתכם 3 כלים מעשיים ליצירת מרחב בטוח שיאפשר לבן הזוג להיפתח ולשתף מבלי לפחד מביקורת.

לתיאום שיחת ייעוץ אישית/זוגית ומאמרים נוספים:
בקרו באתר של 'קשר - ייעוץ זוגי ומשפחתי': https://kesher.saharoni.com

אם מצאתם ערך בסרטון, אל תשכחו לעשות לייק, להירשם לערוץ ולשתף אותו!"""
    tags = [
        "תקשורת בזוגיות",
        "שיח רגשי",
        "ייעוץ זוגי",
        "טיפול זוגי",
        "למה הוא לא מדבר",
        "איך לגרום לגבר להיפתח",
        "ברנה בראון",
        "שלום בית",
        "קשר ייעוץ זוגי",
        "פגיעות בזוגיות",
        "הקשבה ללא שיפוטיות",
        "בעיות זוגיות",
        "חיבור רגשי",
        "ייעוץ משפחתי",
        "תקשורת מקרבת"
    ]
    
    # Call YOUTUBE_UPDATE_VIDEO via COMPOSIO_MULTI_EXECUTE_TOOL
    result = client.call_tool("COMPOSIO_MULTI_EXECUTE_TOOL", {
        "sync_response_to_workbench": False,
        "current_step": "UPDATING_VIDEO_METADATA",
        "memory": {},
        "tools": [
            {
                "tool_slug": "YOUTUBE_UPDATE_VIDEO",
                "connected_account_id": "youtube_ransom-winish",
                "arguments": {
                    "videoId": "Fg5-kTsLdRg",
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "22",
                    "privacyStatus": "public"
                }
            }
        ]
    })
    print("Update Video Response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
