from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()

print("--- DAFTAR MODEL YANG TERSEDIA UNTUK API KEY ANDA ---")
try:
    for m in client.models.list():
        print(m.id)
except Exception as e:
    print(f"Error: {e}")
