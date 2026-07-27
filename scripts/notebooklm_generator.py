import sys
import time
import json
import os
sys.path.append('scripts')
from notebooklm_client import NotebookLMClient

def main():
    notebook_id = "e101e7d7-5305-45b3-a611-21a5475ceb63"
    notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
    youtube_url = "https://www.youtube.com/watch?v=06r1-_wBFDo"
    output_path = "/Users/ninja/Documents/Kesher/output/video_06r1-_wBFDo.mp4"
    
    # Make sure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    client = NotebookLMClient()
    try:
        client.connect()
        
        # Step 1: Add YouTube source
        print(f"Adding YouTube source: {youtube_url}...")
        add_result = client.call_tool("source_add", {
            "source_type": "youtube",
            "url": youtube_url,
            "notebook_url": notebook_url
        })
        print("Source add result:")
        print(json.dumps(add_result, indent=2, ensure_ascii=False))
        
        # Wait for processing/transcription to settle
        print("Waiting 30 seconds for NotebookLM to process the source...")
        time.sleep(30)
        
        # Step 2: Generate Video Overview
        print("Generating cinematic Video Overview...")
        prompt = """
תייצר סרטון ויראלי בעברית (ללא שימוש בשמות המקור, השתמש בשמות חלופיים כמו טליה ואדם) על פי המקור החדש שהוספנו. 
זו צריכה להיות גרסה אלטרנטיבית לסרטון Faceless, עם זווית ראייה שונה ומקרה שונה. 
הוידאו מיועד לערוץ יוטיוב 'קשר ייעוץ זוגי'.
"""
        gen_result = client.call_tool("content_generate", {
            "content_type": "video",
            "video_style": "cinematic",
            "custom_instructions": prompt,
            "language": "Hebrew",
            "notebook_url": notebook_url
        })
        print("Generation result:")
        print(json.dumps(gen_result, indent=2, ensure_ascii=False))
        
        # Wait a bit for processing to complete
        print("Waiting 15 seconds before starting download...")
        time.sleep(15)
        
        # Step 3: Download Generated Video
        print(f"Downloading video to {output_path}...")
        download_result = client.call_tool("content_download", {
            "content_type": "video",
            "output_path": output_path,
            "notebook_url": notebook_url
        })
        print("Download result:")
        print(json.dumps(download_result, indent=2, ensure_ascii=False))
        
        print("\n=== Success! Video generated and saved. ===")
        
    except Exception as e:
        print(f"\n[ERROR] Workflow failed: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
