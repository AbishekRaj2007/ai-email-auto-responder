from __future__ import print_function
import os
import os.path
import base64
import re
from email.mime.text import MIMEText
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from groq import Groq

# ---------------- LOAD ENV ----------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------- CONFIG ----------------
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
LABEL_NAME = "AUTO_REPLIED"
ALLOWED_EMAIL = "someone@gmail.com"   # 👈 only this email gets reply

# ---------------- GROQ CLIENT ----------------
groq_client = Groq(api_key=GROQ_API_KEY)

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

# ---------------- GROQ AI ----------------
def generate_ai_reply(sender, subject):
    prompt = f"""
You are a professional email assistant.

Write a polite, concise, professional reply to this email.

From: {sender}
Subject: {subject}

The reply should:
- Acknowledge receipt
- Be friendly and professional
- Not ask unnecessary questions
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You write professional email replies."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    return response.choices[0].message.content.strip()

# ---------------- EMAIL SEND ----------------
def create_reply(to_email, subject, ai_body):
    message = MIMEText(ai_body)
    message['to'] = to_email
    message['subject'] = "Re: " + subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_reply(service, to_email, subject, ai_body):
    service.users().messages().send(
        userId='me',
        body=create_reply(to_email, subject, ai_body)
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

        sender = extract_email(email.get('From', ''))
        subject = email.get('Subject', '(No Subject)')
        label_ids = msg_data.get('labelIds', [])

        print("From:", sender)
        print("Subject:", subject)

        if label_id in label_ids:
            print("[SKIP] Already replied\n")
            continue

        if sender.lower() != ALLOWED_EMAIL.lower():
            print("[SKIP] Sender not allowed\n")
            continue

        print("[AI] Generating reply...")
        ai_reply = generate_ai_reply(sender, subject)

        send_reply(service, sender, subject, ai_reply)
        mark_replied(service, msg['id'], label_id)

        print("[REPLIED] AI auto-reply sent\n")

# ---------------- RUN ----------------
if __name__ == '__main__':
    service = authenticate_gmail()
    read_and_reply(service)
