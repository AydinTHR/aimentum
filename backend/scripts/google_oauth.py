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
from pathlib import Path

# Run as a file path, Python puts scripts/ on the import path rather than the
# project root, so `app` resolves only through the editable install. Add the
# root explicitly: a setup script should work on a fresh clone, before anyone
# has installed anything.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envfile import set_key  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.calendar import SCOPES  # noqa: E402


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

    path = set_key("GOOGLE_OAUTH_REFRESH_TOKEN", credentials.refresh_token)
    print(f"\nRefresh token written to {path} (not printed: it grants calendar access).")
    print("Next: uv run python scripts/google_calendar_setup.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
