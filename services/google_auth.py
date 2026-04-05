"""
Google OAuth2 pour GA4 et GSC.

Deux modes :
1. Service Account (usage interne) — fichier JSON de credentials
2. OAuth2 refresh token (futurs clients) — client_id/secret + refresh token

Les credentials sont partagees entre GA4Client et GSCClient.
"""

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

logger = logging.getLogger("diffusionbot.google_auth")

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


def get_credentials_from_service_account(service_account_file: str) -> Credentials:
    """Auth via service account (fichier JSON). Usage interne."""
    path = Path(service_account_file)
    if not path.exists():
        raise FileNotFoundError(f"Fichier service account introuvable: {path}")

    creds = service_account.Credentials.from_service_account_file(
        str(path), scopes=SCOPES
    )
    logger.info(f"Google auth: service account charge ({creds.service_account_email})")
    return creds


def get_credentials_from_refresh_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> Credentials:
    """Auth via OAuth2 refresh token (futurs clients)."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    logger.info("Google auth: token rafraichi via refresh token")
    return creds


def get_google_credentials(
    service_account_file: str = "",
    client_id: str = "",
    client_secret: str = "",
    refresh_token: str = "",
) -> Credentials | None:
    """
    Retourne les credentials Google selon ce qui est configure.
    Priorite: service account > OAuth2 refresh token.
    """
    if service_account_file:
        try:
            return get_credentials_from_service_account(service_account_file)
        except Exception as e:
            logger.error(f"Erreur service account: {e}")

    if client_id and client_secret and refresh_token:
        try:
            return get_credentials_from_refresh_token(client_id, client_secret, refresh_token)
        except Exception as e:
            logger.error(f"Erreur OAuth2 refresh: {e}")

    logger.warning("Google auth: aucune methode d'authentification configuree")
    return None
