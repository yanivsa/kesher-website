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
        
        # Check in a loop for up to 10 minutes
        max_wait = 600  # 10 minutes
        start_time = time.time()
        
        print("Checking if Audio/Video Overview generation is complete...")
        while time.time() - start_time < max_wait:
            result = client.call_tool("content_list", {
                "notebook_url": notebook_url
            })
            
            # Print status
            if result and "structuredContent" in result:
                data = result["structuredContent"].get("data", {})
                has_audio = data.get("hasAudioOverview", False)
                print(f"[{int(time.time() - start_time)}s] hasAudioOverview: {has_audio}")
                if has_audio:
                    print("Generation complete! Proceeding to download...")
                    break
            elif result and "content" in result:
                # Try parsing raw text if structuredContent is missing
                try:
                    raw_text = result["content"][0]["text"]
                    raw_data = json.loads(raw_text)
                    data = raw_data.get("data", {})
                    has_audio = data.get("hasAudioOverview", False)
                    print(f"[{int(time.time() - start_time)}s] hasAudioOverview (parsed): {has_audio}")
                    if has_audio:
                        print("Generation complete! Proceeding to download...")
                        break
                except Exception as parse_err:
                    print(f"Failed to parse content: {parse_err}")
            else:
                print("Could not retrieve content overview, retrying...")
                
            time.sleep(30)
        else:
            raise Exception("Timeout waiting for audio generation to complete on Google servers.")

        # Download the file
        print(f"Downloading video to {output_path}...")
        download_result = client.call_tool("content_download", {
            "content_type": "audio_overview",
            "output_path": output_path,
            "notebook_url": notebook_url
        })
        print("Download result:")
        print(json.dumps(download_result, indent=2, ensure_ascii=False))
        
        # If it succeeded, check file size
        if os.path.exists(output_path):
            print(f"SUCCESS! Downloaded file size: {os.path.getsize(output_path)} bytes")
        else:
            # Try "video" type as fallback
            print("Trying download as 'video' content type...")
            download_result = client.call_tool("content_download", {
                "content_type": "video",
                "output_path": output_path,
                "notebook_url": notebook_url
            })
            if os.path.exists(output_path):
                print(f"SUCCESS! Downloaded video size: {os.path.getsize(output_path)} bytes")
            else:
                print("Download failed: file not found on disk.")
                
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
