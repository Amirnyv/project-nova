"""Google OAuth helpers for Nova Connections."""

import os

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


GOOGLE_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleOAuthError(Exception):
    """Google OAuth configuration or authorization failed."""


def _client_config():
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise GoogleOAuthError(
            "Google OAuth is not configured."
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def create_authorization_url(redirect_uri, state):
    flow = Flow.from_client_config(
        _client_config(),
        scopes=GOOGLE_OAUTH_SCOPES,
        state=state,
    )

    flow.redirect_uri = redirect_uri

    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return authorization_url, returned_state, flow.code_verifier


def finish_authorization(
    redirect_uri,
    state,
    authorization_response,
    code_verifier
):
    flow = Flow.from_client_config(
        _client_config(),
        scopes=GOOGLE_OAUTH_SCOPES,
        state=state,
    )

    flow.redirect_uri = redirect_uri
    flow.code_verifier = code_verifier

    flow.fetch_token(
        authorization_response=authorization_response
    )

    credentials = flow.credentials

    oauth2 = build(
        "oauth2",
        "v2",
        credentials=credentials,
        cache_discovery=False,
    )

    profile = (
        oauth2.userinfo()
        .get()
        .execute()
    )

    credential_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "scopes": list(credentials.scopes or []),
        "expiry": (
            credentials.expiry.isoformat()
            if credentials.expiry
            else None
        ),
    }

    return profile, credential_data
