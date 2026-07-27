#!/usr/bin/env python3
import os
import sys
import re
import json
import argparse
import urllib.request
import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def setup_gemini():
    """Configure Gemini API using environment variable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY is not set in environment or .env file.")
        api_key = input("Please enter your Gemini API Key (from Google AI Studio): ").strip()
        if not api_key:
            print("Error: Gemini API key is required to run analysis.")
            sys.exit(1)
    
    genai.configure(api_key=api_key)
    # Using gemini-1.5-flash as it is fast, cheap, and supports structured JSON outputs
    return genai.GenerativeModel("gemini-1.5-flash")

def search_youtube_free(query, max_results=3):
    """
    Search YouTube for a query without needing an API key.
    Extracts video IDs and titles using scraping and regex.
    """
    print(f"Searching YouTube for: '{query}'...")
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching YouTube search page: {e}")
        return []

    # Try to extract ytInitialData JSON
    json_pattern = re.compile(r'ytInitialData\s*=\s*({.+?});')
    match = json_pattern.search(html)
    if not match:
        json_pattern = re.compile(r'ytInitialData\s*=\s*({.+?})\s*;?\s*</script>')
        match = json_pattern.search(html)

    videos = []
    if match:
        try:
            data = json.loads(match.group(1))
            contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']
            for content in contents:
                if 'itemSectionRenderer' in content:
                    items = content['itemSectionRenderer']['contents']
                    for item in items:
                        if 'videoRenderer' in item:
                            v_renderer = item['videoRenderer']
                            video_id = v_renderer['videoId']
                            title = v_renderer['title']['runs'][0]['text']
                            
                            views = ""
                            if 'viewCountText' in v_renderer and 'simpleText' in v_renderer['viewCountText']:
                                views = v_renderer['viewCountText']['simpleText']
                            elif 'viewCountText' in v_renderer and 'runs' in v_renderer['viewCountText']:
                                views = "".join([r['text'] for r in v_renderer['viewCountText']['runs']])

                            videos.append({
                                'video_id': video_id,
                                'title': title,
                                'views': views,
                                'url': f"https://www.youtube.com/watch?v={video_id}"
                            })
                            if len(videos) >= max_results:
                                return videos
        except Exception as e:
            print(f"Error parsing search JSON structure, falling back to regex: {e}")
            
    # Fallback regex extraction of video IDs if JSON structure changes
    if not videos:
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        seen = set()
        unique_ids = [x for x in video_ids if not (x in seen or seen.add(x))]
        for vid in unique_ids[:max_results]:
            videos.append({
                'video_id': vid,
                'title': f"Video {vid}",
                'views': "N/A",
                'url': f"https://www.youtube.com/watch?v={vid}"
            })
            
    return videos

def get_transcript(video_id):
    """Fetch the transcript of a video in Hebrew or English."""
    print(f"Retrieving transcript for video: {video_id}...")
    try:
        api = YouTubeTranscriptApi()
        # Fetch the transcript directly, prioritizing Hebrew then English
        lines = api.fetch(video_id, languages=['iw', 'he', 'en'])
        text = " ".join([line.text for line in lines])
        return text
    except Exception as e:
        print(f"Error retrieving transcript for {video_id}: {e}")
        return None

def analyze_video_with_gemini(model, transcript, original_title):
    """Use Gemini to analyze transcript and generate structured JSON results."""
    print("Generating video overview and alternative script using Gemini...")
    
    prompt = f"""
אתה מומחה תוכן בכיר ושיווק דיגיטלי ביוטיוב, וכן יועץ זוגי ומשפחתי מנוסה מטעם המותג "קשר - ייעוץ זוגי ומשפחתי".
לפניך תמלול של סרטון יוטיוב ויראלי בנושאי זוגיות או הורות.

כותרת מקורית: {original_title}
תמלול הסרטון:
{transcript}

עליך להחזיר אובייקט JSON תואם למבנה המבוקש בעברית רהוטה ומקצועית:

המבנה הנדרש (JSON):
{{
  "video_overview": "סקירה כללית וסיכום התובנות המרכזיות מהסרטון המקורי בעברית.",
  "faceless_script": [
    {{
      "scene_number": 1,
      "visual_description": "תיאור ויזואלי של הסצנה (למשל Stock footage של זוג מתווכח במטבח, בגוונים חמים)",
      "voiceover": "הטקסט המדויק שהקריין יגיד בעברית בסצנה זו (קול טיפולי, רגוע וסמכותי)"
    }}
  ],
  "youtube_metadata": {{
    "titles": [
      "רעיון 1 לכותרת מושכת וויראלית (קליקבייט מבוסס ערך)",
      "רעיון 2 לכותרת מושכת וויראלית",
      "רעיון 3 לכותרת מושכת וויראלית"
    ],
    "description": "תיאור עשיר לסרטון החדש הכולל פסקת פתיחה, נקודות מרכזיות וקריאה לפעולה לבקר באתר של קשר (https://kesher.saharoni.com) או ליצור קשר.",
    "tags": ["תג 1", "תג 2", "תג 3 (לפחות 15 תגים פופולריים בעברית)"]
  }}
}}

**הנחיות חשובות לתסריט (faceless_script)**:
- התסריט חייב להיות מבוסס על הסרטון המקורי, אך להיות מזווית ראייה שונה (Different Angle), עם מקרה שונה (Different Scenario) ודמויות שונות (Different Characters) כדי למנוע העתקה וליצור גרסה אלטרנטיבית מקורית.
- התסריט צריך להתאים לערוץ "קשר ייעוץ זוגי ומשפחתי".
"""
    
    try:
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        return None

def format_markdown(data, original_title, video_id, original_url, views):
    """Format the JSON response into a beautiful Markdown report."""
    md = f"""# ניתוח סרטון מקור: {original_title}
- **מזהה סרטון**: `{video_id}`
- **קישור לסרטון מקורי**: {original_url}
- **כמות צפיות**: {views}

---

## 1. סקירה כללית (Video Overview)
{data.get('video_overview', '')}

---

## 2. תסריט אלטרנטיבי לסרטון Faceless (גרסה אלטרנטיבית)
*גרסה זו נוצרה מזווית שונה, מקרה אחר ודמויות שונות כדי ליצור תוכן מקורי ועשיר עבור ערוץ "קשר".*

"""
    
    for scene in data.get('faceless_script', []):
        md += f"### סצנה {scene.get('scene_number', 1)}\n"
        md += f"- **תיאור ויזואלי**: {scene.get('visual_description', '')}\n"
        md += f"- **קריינות (Voiceover)**: *\"{scene.get('voiceover', '')}\"*\n\n"
        
    metadata = data.get('youtube_metadata', {})
    md += """---

## 3. פרטי העלאה ליוטיוב (YouTube Metadata)

### הצעות לכותרות ויראליות:
"""
    for idx, title in enumerate(metadata.get('titles', []), 1):
        md += f"{idx}. **{title}**\n"
        
    md += f"""
### תיאור מומלץ (Description):
```text
{metadata.get('description', '')}
```

### תגים מוצעים (Tags):
`{", ".join(metadata.get('tags', []))}`
"""
    return md

def extract_video_id(url_or_id):
    """Extract 11-char video ID from YouTube URL or return it directly if already an ID."""
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11:
        return url_or_id
    
    patterns = [
        r'(?:v=|\/)([a-zA-Z0-9_-]{11})(?:&|$|\?)',
        r'youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'embed\/([a-zA-Z0-9_-]{11})',
        r'shorts\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
            
    return None

def main():
    parser = argparse.ArgumentParser(description="YouTube Viral Finder & Faceless Script Creator using Gemini")
    parser.add_argument("--query", type=str, help="Search query on YouTube (e.g. 'טיפים לזוגיות' or 'בעיות בהורות')")
    parser.add_argument("--url", type=str, help="Direct YouTube video URL or ID to analyze")
    parser.add_argument("--results", type=int, default=3, help="Number of search results to analyze (default: 3)")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory to save the generated files")
    
    args = parser.parse_args()
    
    # If no arguments provided, ask interactive questions
    if not args.query and not args.url:
        print("=== YouTube Faceless Creator Automation ===")
        print("1. Analyze a specific YouTube video (by URL/ID)")
        print("2. Search YouTube and analyze viral videos by keyword")
        choice = input("Select option (1 or 2): ").strip()
        if choice == '1':
            args.url = input("Enter YouTube Video URL or ID: ").strip()
        else:
            args.query = input("Enter search keywords (e.g. 'זוגיות הורות'): ").strip()
            args.results = int(input("How many videos to analyze (1-5, default 3): ") or 3)
            
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup Gemini model
    model = setup_gemini()
    
    videos_to_process = []
    
    if args.url:
        video_id = extract_video_id(args.url)
        if not video_id:
            print(f"Error: Could not extract video ID from '{args.url}'")
            sys.exit(1)
        videos_to_process.append({
            'video_id': video_id,
            'title': "Direct URL Video",
            'views': "N/A",
            'url': f"https://www.youtube.com/watch?v={video_id}"
        })
    elif args.query:
        videos_to_process = search_youtube_free(args.query, max_results=args.results)
        if not videos_to_process:
            print("No videos found or search failed.")
            sys.exit(1)
            
    print(f"\nProcessing {len(videos_to_process)} video(s):")
    for idx, video in enumerate(videos_to_process, 1):
        print(f"{idx}. {video['title']} (ID: {video['video_id']}, Views: {video['views']})")
        
    for video in videos_to_process:
        video_id = video['video_id']
        title = video['title']
        
        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            print(f"Skipping video {video_id} because no transcript could be retrieved.")
            continue
            
        # Analyze with Gemini (Structured JSON)
        data = analyze_video_with_gemini(model, transcript, title)
        if not data:
            print(f"Skipping video {video_id} because Gemini analysis failed.")
            continue
            
        # Safe filename prefix
        safe_title = "".join([c if c.isalnum() or c in " _-" else "_" for c in title])[:50]
        
        # Save JSON output (Structured)
        json_filepath = os.path.join(args.output_dir, f"metadata_{video_id}_{safe_title}.json")
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # Generate and save Markdown report
        markdown_content = format_markdown(data, title, video_id, video['url'], video['views'])
        md_filepath = os.path.join(args.output_dir, f"analysis_{video_id}_{safe_title}.md")
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
            
        print(f"✓ Structured data saved to: {json_filepath}")
        print(f"✓ Markdown report saved to: {md_filepath}\n")
        
    print("Workflow complete! Check your output directory.")

if __name__ == "__main__":
    main()
