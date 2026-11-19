import json
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")

if not api_key:
    sys.exit("FAIL: GEMINI_API_KEY is not set in your .env file.")
if not model:
    sys.exit("FAIL: GEMINI_MODEL is not set in your .env file.")

client = genai.Client(api_key=api_key)

print(f"Model: {model}")
print("Test 1: plain text request...")
try:
    response = client.models.generate_content(
        model=model, contents="Reply with exactly the word: ready"
    )
    print("  OK ->", (response.text or "").strip())
except Exception as e:
    sys.exit(f"  FAIL: {type(e).__name__}: {e}")

print("Test 2: strict JSON output...")
prompt = (
    "Caption: 'Filmed in Mumbai on 3 May 2025.' "
    "Transcript: 'It is snowing heavily here in Oslo.' "
    'Return ONLY JSON: {"contradiction": true or false, '
    '"quoted_span": "exact words from the transcript or caption", '
    '"reason": "one sentence"}'
)
try:
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text)
    print("  OK ->", json.dumps(data, indent=2))
except Exception as e:
    sys.exit(f"  FAIL: {type(e).__name__}: {e}")

print("\nAll checks passed. Your LLM setup is ready.")