from urllib.parse import urlencode

import requests

from app.core.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_OAUTH_REDIRECT_URI
from app.domain.exceptions import SourceAuthError

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
SCOPE = "repo"


def build_authorize_url(state: str) -> str:
    """Scaffold: butuh GITHUB_CLIENT_ID (daftarkan GitHub OAuth App dulu) di .env agar valid."""
    if not GITHUB_CLIENT_ID:
        raise SourceAuthError("GITHUB_CLIENT_ID belum di-set - daftarkan GitHub OAuth App dulu")
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> str:
    """Scaffold: butuh GITHUB_CLIENT_ID + GITHUB_CLIENT_SECRET di .env agar valid."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise SourceAuthError("GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET belum di-set")

    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    access_token = payload.get("access_token")
    if not access_token:
        raise SourceAuthError(f"Gagal menukar code dengan access token: {payload}")
    return access_token
