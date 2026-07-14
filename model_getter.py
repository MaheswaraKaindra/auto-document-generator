import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("--- DAFTAR MODEL YANG TERSEDIA UNTUK API KEY ANDA ---")
try:
    for m in client.models.list():
        if m.supported_actions and "generateContent" in m.supported_actions:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
