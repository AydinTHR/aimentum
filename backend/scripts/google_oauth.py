"""One-time Google Calendar authorization.

Run this once on your own machine. It opens a browser, asks you to authorize
your own Google account, and prints a refresh token for the backend's env.
There is no user-facing OAuth in this product: the only account it ever
connects to is the owner's, and this script is how that happens (ADR-0005).

    uv run python scripts/google_oauth.py

Needs GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET from a Desktop
type OAuth client. Set the consent screen to In production before running:
in Testing mode Google expires refresh tokens after seven days, and the
agent would silently lose calendar access every week.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import settings
from app.services.calendar import SCOPES


def main() -> int:
    client_id = settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret
    if not client_id or not client_secret:
        print(
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in "
            "backend/.env first (Desktop type OAuth client).",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )
    # access_type=offline plus prompt=consent is what actually returns a
    # refresh token; without the prompt Google reuses a prior grant and
    # returns none, which looks like a bug in this script but is not.
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not credentials.refresh_token:
        print(
            "Google returned no refresh token. Revoke this app's access at "
            "https://myaccount.google.com/permissions and run again.",
            file=sys.stderr,
        )
        return 1

    print("\nPaste this into backend/.env:\n")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}")
    print("\nThen run scripts/google_calendar_setup.py to create the calendar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
