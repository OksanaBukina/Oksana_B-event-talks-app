"""
upload_to_drive.py
------------------
Upload a local file to Google Drive using the Drive API v3.

Prerequisites
-------------
1. Enable the Google Drive API in your Google Cloud project:
   https://console.cloud.google.com/apis/library/drive.googleapis.com

2. Configure the OAuth consent screen and create a Desktop OAuth 2.0 Client ID:
   https://console.cloud.google.com/auth/clients
   Download the JSON file and save it as 'credentials.json' in this directory.

3. Install dependencies:
   python -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

Usage
-----
  # Upload a file to the root of Drive:
  python upload_to_drive.py path/to/file.pdf

  # Upload to a specific Drive folder:
  python upload_to_drive.py path/to/file.pdf --folder-id <DRIVE_FOLDER_ID>

  # Convert a CSV to a Google Sheet during upload:
  python upload_to_drive.py data.csv --convert

  # Use a resumable upload (recommended for files > 5 MB):
  python upload_to_drive.py large_video.mp4 --resumable
"""

import argparse
import mimetypes
import os
import os.path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------
# 'drive.file' grants access only to files created/opened by this app.
# Change to 'drive' for full Drive access, but this requires broader consent.
# If you modify this list, delete token.json so a fresh token is issued.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Paths for OAuth token cache and credentials
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

# Chunk size used for resumable uploads (recommended: 5 MB)
RESUMABLE_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def get_credentials() -> Credentials:
    """
    Load or refresh OAuth 2.0 credentials.

    On the first run, a browser window opens so the user can authorize the
    application. The resulting token is cached in token.json for subsequent
    runs.

    Returns:
        google.oauth2.credentials.Credentials: Valid user credentials.

    Raises:
        FileNotFoundError: If credentials.json is not found.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"'{CREDENTIALS_PATH}' not found.\n"
            "Download your OAuth 2.0 client secret from the Google Cloud Console "
            "and save it as 'credentials.json' in the script directory."
        )

    creds = None

    # Re-use a previously saved token if it exists
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If no valid credentials, run the interactive OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Silently refresh an expired token
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Persist the token for future runs
        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def detect_mime_type(file_path: str) -> str:
    """
    Guess the MIME type of a file from its extension.

    Args:
        file_path: Local path to the file.

    Returns:
        A MIME type string, defaulting to 'application/octet-stream'.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def upload_file(
    service,
    file_path: str,
    folder_id: str | None = None,
    convert: bool = False,
    resumable: bool = False,
) -> dict:
    """
    Upload a local file to Google Drive.

    Args:
        service:    An authorized Google Drive API service object.
        file_path:  Path to the local file to upload.
        folder_id:  (Optional) Drive folder ID to upload into.
                    Uploads to the root of My Drive if omitted.
        convert:    If True, convert the file to the corresponding
                    Google Workspace format (e.g., XLSX -> Google Sheets).
        resumable:  If True, use a resumable upload session, which is more
                    reliable for large files or slow/unreliable connections.

    Returns:
        A dict containing the uploaded file's 'id', 'name', and 'webViewLink'.

    Raises:
        FileNotFoundError: If file_path does not exist.
        googleapiclient.errors.HttpError: On API errors.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_name = os.path.basename(file_path)
    mime_type = detect_mime_type(file_path)

    # File metadata sent to the API
    file_metadata: dict = {"name": file_name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    # Build the media upload object.
    # For resumable uploads the library will POST each chunk automatically.
    media = MediaFileUpload(
        file_path,
        mimetype=mime_type,
        resumable=resumable,
        chunksize=RESUMABLE_CHUNK_SIZE if resumable else -1,
    )

    if convert:
        # Drive v3 automatically converts when the uploaded MIME type maps to
        # a Google Workspace type (e.g., text/csv -> Google Sheets).
        print(
            "[info] Conversion requested. Drive will automatically convert "
            "supported formats (e.g., .docx -> Google Docs, .xlsx -> Sheets)."
        )

    request_kwargs: dict = {
        "body": file_metadata,
        "media_body": media,
        "fields": "id, name, webViewLink",
    }

    file_resource = service.files().create(**request_kwargs)

    if resumable:
        # Execute a resumable upload with progress reporting
        print(f"Starting resumable upload for '{file_name}' ...")
        response = None
        while response is None:
            status, response = file_resource.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"  Upload progress: {progress}%", end="\r")
        print()  # newline after progress line
    else:
        # Simple (single-request) upload
        response = file_resource.execute()

    return response


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a file to Google Drive using the Drive API v3.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file_path",
        help="Path to the local file you want to upload.",
    )
    parser.add_argument(
        "--folder-id",
        metavar="FOLDER_ID",
        default=None,
        help=(
            "Google Drive folder ID to upload into. "
            "Leave blank to upload to the root of My Drive."
        ),
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        default=False,
        help=(
            "Convert the file to the corresponding Google Workspace format "
            "(e.g., XLSX -> Google Sheets, DOCX -> Google Docs)."
        ),
    )
    parser.add_argument(
        "--resumable",
        action="store_true",
        default=False,
        help=(
            "Use a resumable upload session. Recommended for files larger "
            "than 5 MB or on unreliable network connections."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # -- Authenticate --
    try:
        creds = get_credentials()
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

    # -- Build the Drive service --
    try:
        service = build("drive", "v3", credentials=creds)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Failed to build Drive service: {exc}", file=sys.stderr)
        sys.exit(1)

    # -- Upload --
    try:
        file_name = os.path.basename(args.file_path)
        print(f"Uploading '{file_name}' ...")

        uploaded = upload_file(
            service=service,
            file_path=args.file_path,
            folder_id=args.folder_id,
            convert=args.convert,
            resumable=args.resumable,
        )

        print("\nUpload successful!")
        print(f"   File name : {uploaded.get('name')}")
        print(f"   File ID   : {uploaded.get('id')}")
        print(f"   View link : {uploaded.get('webViewLink', 'N/A')}")

    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
    except HttpError as exc:
        print(f"[error] Drive API error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
