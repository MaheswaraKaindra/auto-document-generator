import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback")
