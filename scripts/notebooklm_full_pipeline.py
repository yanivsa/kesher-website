import sys
import time
import json
import os
sys.path.append('scripts')
from notebooklm_client import NotebookLMClient

def main():
    notebook_id = "e101e7d7-5305-45b3-a611-21a5475ceb63"
    notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}?hl=en"
    output_path = "/Users/ninja/Documents/Kesher/output/video_06r1-_wBFDo.mp4"
    
    # Make sure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    client = NotebookLMClient()
    try:
        client.connect()
        
        # Step 1: Trigger content generation (this will start it and wait internally)
        print("Starting Audio Overview generation (forcing English UI)...")
        prompt = """
תייצר סרטון ויראלי בעברית (ללא שימוש בשמות המקור, השתמש בשמות חלופיים כמו טליה ואדם) על פי המקור החדש שהוספנו. 
זו צריכה להיות גרסה אלטרנטיבית לסרטון Faceless, עם זווית ראייה שונה ומקרה שונה. 
הוידאו מיועד לערוץ יוטיוב 'קשר ייעוץ זוגי'.
"""
        # Call tool with large timeout (15 minutes)
        gen_result = client.call_tool("content_generate", {
            "content_type": "audio_overview",
            "custom_instructions": prompt,
            "language": "Hebrew",
            "notebook_url": notebook_url
        })
        
        print("Generation result:")
        print(json.dumps(gen_result, indent=2, ensure_ascii=False))
        
        # Check if success
        if gen_result and gen_result.get("success") or gen_result.get("status") == "ready":
            print("Audio overview generated successfully!")
        else:
            # Check if it failed but we want to try downloading anyway just in case
            print("Warning: generation tool reported failure, but we will attempt to download in case it finished.")

        # Step 2: Download the generated content
        print(f"Downloading generated audio/video to {output_path}...")
        download_result = client.call_tool("content_download", {
            "content_type": "audio_overview",
            "output_path": output_path,
            "notebook_url": notebook_url
        })
        print("Download result:")
        print(json.dumps(download_result, indent=2, ensure_ascii=False))
        
        # Verify file download
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"SUCCESS! File downloaded successfully to {output_path}")
            print(f"File size: {os.path.getsize(output_path)} bytes")
        else:
            # Try download with type "video"
            print("Download failed or empty. Trying with content_type='video'...")
            download_result = client.call_tool("content_download", {
                "content_type": "video",
                "output_path": output_path,
                "notebook_url": notebook_url
            })
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"SUCCESS! File downloaded as video to {output_path}")
                print(f"File size: {os.path.getsize(output_path)} bytes")
            else:
                print("Error: Could not retrieve the generated file.")
                
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
