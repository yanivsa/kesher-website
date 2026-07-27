import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    
    code = """
try:
    import urllib.request
    import os
    import sys
    
    print("Step 1: Downloading file to sandbox...")
    url = "https://tmpfiles.org/dl/wUwIahWHNbfM/kesher-second-unique.mp4"
    file_path = "/tmp/studio_video_second.mp4"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req) as response:
        with open(file_path, "wb") as out_file:
            out_file.write(response.read())
            
    print("Download completed. File size:", os.path.getsize(file_path))
    
    print("Step 2: Uploading to S3...")
    res, err = upload_local_file(file_path)
    if err:
        print("Upload error:", err)
    else:
        print("Upload success! s3key:", res.get("s3key"))
        s3_key = res["s3key"]
        
        print("Step 3: Triggering YouTube video upload...")
        title = "הילד לא הבעיה: הגבול הסמוי שמפרק את הבית (בדיקה ייחודית)"
        description = \"\"\"לפעמים המריבה בבית נראית כאילו היא סביב ילד שלא מקשיב, שיעורי בית, מסכים או שעת שינה. אבל מתחת לפני השטח מסתתר משהו עמוק יותר: גבולות לא ברורים בין ההורים עצמם.
בסרטון הזה נבחן דרך סיפור משפחתי חדש איך חוסר תיאום רגשי בין ההורים יוצר בלבול, מאבקי כוח ועייפות בבית, ואיך אפשר להתחיל לבנות גבול רגוע ובריא יותר.

לתיאום שיחת ייעוץ אישית/זוגית ומאמרים נוספים:
בקרו באתר של 'קשר - ייעוץ זוגי ומשפחתי': https://kesher.saharoni.com

אם מצאתם ערך בסרטון, אל תשכחו לעשות לייק, להירשם לערוץ ולשתף אותו!\"\"\"
        tags = [
            "תקשורת בזוגיות",
            "הורות",
            "הדרכת הורים",
            "גבולות לילדים",
            "ייעוץ זוגי",
            "שלום בית",
            "קשר ייעוץ זוגי"
        ]
        
        yt_res, yt_err = run_composio_tool("YOUTUBE_UPLOAD_VIDEO", {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
            "privacyStatus": "private",  # Upload as private!
            "videoFilePath": {
                "name": "studio_video_second.mp4",
                "mimetype": "video/mp4",
                "s3key": s3_key
            }
        })
        if yt_err:
            print("YouTube upload error:", yt_err)
        else:
            print("YouTube upload success:", yt_res)
except Exception as e:
    import traceback
    print("EXCEPTION OCCURRED:")
    traceback.print_exc(file=sys.stdout)
"""

    print("Executing code in remote workbench...")
    result = client.call_tool("COMPOSIO_REMOTE_WORKBENCH", {
        "code_to_execute": code,
        "sync_response_to_workbench": False
    })
    
    print("\n--- Workbench Output ---")
    if result and "content" in result:
        text_content = result["content"][0].get("text", "")
        try:
            parsed = json.loads(text_content)
            print("STDOUT:")
            print(parsed.get("data", {}).get("stdout", ""))
            print("STDERR:")
            print(parsed.get("data", {}).get("stderr", ""))
        except Exception:
            print(text_content)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

finally:
    client.disconnect()
