from __future__ import print_function
import os.path
import base64
import re
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------- CONFIG ----------------
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
LABEL_NAME = "AUTO_REPLIED"
ALLOWED_EMAIL = "rrabishekraj18@gmail.com"   # 👈 ONLY THIS MAIL WILL GET REPLY

# ---------------- AUTH ----------------
def authenticate_gmail():
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

# ---------------- LABEL ----------------
def get_or_create_label(service):
    labels = service.users().labels().list(userId='me').execute().get('labels', [])

    for label in labels:
        if label['name'] == LABEL_NAME:
            return label['id']

    label_body = {
        "name": LABEL_NAME,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show"
    }

    label = service.users().labels().create(
        userId='me',
        body=label_body
    ).execute()

    return label['id']

# ---------------- HELPERS ----------------
def extract_email(from_header):
    match = re.search(r'<(.+?)>', from_header)
    return match.group(1) if match else from_header

def create_reply(to_email, subject):
    body = (
        "Hello,\n\n"
        "Thank you for reaching out. This is an automated response confirming "
        "that your email has been received.\n\n"
        "Best regards"
    )

    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = "Re: " + subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_reply(service, to_email, subject):
    service.users().messages().send(
        userId='me',
        body=create_reply(to_email, subject)
    ).execute()

def mark_replied(service, msg_id, label_id):
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={
            "addLabelIds": [label_id],
            "removeLabelIds": ['UNREAD']
        }
    ).execute()

# ---------------- MAIN LOGIC ----------------
def read_and_reply(service):
    label_id = get_or_create_label(service)

    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX', 'UNREAD'],
        maxResults=5
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        print("No new emails.")
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

        sender_raw = email.get('From', '')
        sender = extract_email(sender_raw)
        subject = email.get('Subject', '(No Subject)')
        label_ids = msg_data.get('labelIds', [])

        print("From:", sender)
        print("Subject:", subject)

        # Skip if already replied
        if label_id in label_ids:
            print("[SKIP] Already replied\n")
            continue

        # 🔒 ONLY REPLY TO SPECIFIC EMAIL
        if sender.lower() != ALLOWED_EMAIL.lower():
            print("[SKIP] Sender not allowed\n")
            continue

        send_reply(service, sender, subject)
        mark_replied(service, msg['id'], label_id)

        print("[REPLIED] Auto reply sent\n")

# ---------------- RUN ----------------
if __name__ == '__main__':
    service = authenticate_gmail()
    read_and_reply(service)
