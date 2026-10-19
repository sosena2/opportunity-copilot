import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

candidates = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

working = []
for model in candidates:
    for attempt in range(2):
        try:
            r = client.models.generate_content(
                model=model, contents="Say hello in one word."
            )
            print(f"WORKS: {model} -> {r.text.strip()}")
            working.append(model)
            break
        except Exception as e:
            msg = str(e)
            if "404" in msg:
                print(f"SKIP (not available): {model}")
                break
            if "429" in msg:
                print(f"SKIP (limit or no free quota): {model}")
                break
            print(f"BUSY: {model}, retrying...")
            time.sleep(4)

print("\nWorking models:", working)