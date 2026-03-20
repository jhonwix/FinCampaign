"""
Knowledge Base Search Tool — self-signed JWT + httpx (no oauth2.googleapis.com)
=================================================================================
Problem: google-cloud-discoveryengine SDK authenticates via service account
credentials that require token exchange at oauth2.googleapis.com. If that endpoint
is unreachable (firewall / network restriction), the call blocks 120 s then fails.

Solution: build a self-signed JWT locally using google.auth.crypt + google.auth.jwt.
The JWT is signed with the service account private key and sent as a Bearer token.
No network call is needed to obtain the token — no oauth2.googleapis.com dependency.

The JWT is cached for 55 minutes and refreshed automatically.
"""
import json
import sys
import time
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import httpx  # noqa: E402
from google.auth import crypt as google_auth_crypt  # noqa: E402
from google.auth import jwt as google_auth_jwt  # noqa: E402

from config import settings  # noqa: E402

_BASE_URL = "https://discoveryengine.googleapis.com/v1"
_AUDIENCE = "https://discoveryengine.googleapis.com/"
_TOKEN_TTL = 3600        # JWT lifetime in seconds (Google max = 1 hour)
_TOKEN_REFRESH = 55 * 60 # refresh after 55 minutes to avoid expiry mid-request
_HTTP_TIMEOUT = 15       # fast-fail if service is unreachable

# ── Singleton state ───────────────────────────────────────────────────────────
_http_client: httpx.Client | None = None
_jwt_token: str = ""
_jwt_expires_at: float = 0.0
_signer: google_auth_crypt.RSASigner | None = None
_sa_email: str = ""


def _load_signer() -> None:
    """Load the service account signer once (reads the JSON key file)."""
    global _signer, _sa_email
    if _signer is not None:
        return
    try:
        with open(settings.service_account_path) as f:
            sa_info = json.load(f)
        _signer = google_auth_crypt.RSASigner.from_service_account_info(sa_info)
        _sa_email = sa_info["client_email"]
    except Exception as e:
        _signer = None
        _sa_email = ""


def _get_jwt_token() -> str:
    """Return a valid self-signed JWT, creating / refreshing as needed."""
    global _jwt_token, _jwt_expires_at
    if time.time() < _jwt_expires_at:
        return _jwt_token

    _load_signer()
    if _signer is None:
        return ""

    now = int(time.time())
    payload = {
        "iss": _sa_email,
        "sub": _sa_email,
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    raw = google_auth_jwt.encode(_signer, payload)
    _jwt_token = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    _jwt_expires_at = now + _TOKEN_REFRESH
    return _jwt_token


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=_HTTP_TIMEOUT)
    return _http_client


def _serving_config_path() -> str:
    return (
        f"projects/{settings.google_cloud_project}"
        f"/locations/global/collections/default_collection"
        f"/dataStores/{settings.vertex_ai_datastore_id}"
        f"/servingConfigs/default_config"
    )


def search_financial_kb(query: str) -> str:
    """Search the financial products knowledge base for product eligibility criteria,
    interest rate ranges, credit score requirements, DTI thresholds, tone guidelines,
    and compliance policies. Use this before generating any campaign message."""
    token = _get_jwt_token()
    if not token:
        return "[Search unavailable: service account not configured]"

    url = f"{_BASE_URL}/{_serving_config_path()}:search"
    payload = {
        "query": query,
        "pageSize": 3,
        "contentSearchSpec": {
            "snippetSpec": {
                "returnSnippet": True,
                "maxSnippetCount": 3,
            },
            "summarySpec": {
                "summaryResultCount": 3,
                "includeCitations": False,
            },
        },
    }

    try:
        client = _get_http_client()
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        snippets = []
        for result in data.get("results", []):
            doc = result.get("document", {})
            derived = doc.get("derivedStructData", {})
            for item in derived.get("snippets", []):
                text = item.get("snippet", "").strip()
                if text:
                    link = derived.get("link", "")
                    prefix = f"[{link}] " if link else ""
                    snippets.append(f"{prefix}{text}")

        if not snippets:
            return "[No relevant policies found — use base model knowledge]"

        return (
            "--- Knowledge Base Results ---\n"
            + "\n\n".join(f"• {s}" for s in snippets)
            + "\n---"
        )
    except Exception as e:
        return f"[Search unavailable: {e}]"
