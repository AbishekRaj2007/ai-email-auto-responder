from __future__ import print_function
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail read + send permission
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def authenticate_gmail():
    creds = None

    # Load existing token if available
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, start OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def read_latest_emails(service):
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=5
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        print("No emails found.")
        return

    for msg in messages:
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject']
        ).execute()

        headers = msg_data['payload']['headers']
        email = {h['name']: h['value'] for h in headers}

        print("From:", email.get('From'))
        print("Subject:", email.get('Subject'))
        print("-" * 40)


if __name__ == '__main__':
    service = authenticate_gmail()
    read_latest_emails(service)
