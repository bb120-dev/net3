import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')
refresh_token = os.getenv('refresh_token')
creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri='https://oauth2.googleapis.com/token',
    client_id=client_id,
    client_secret=client_secret
)

service = build('gmail', 'v1', credentials=creds)

def extract_payeer_info(text: str) -> Dict[str, str]:
    patterns = {
        "id": r"ID: (\d+)",
        "amount": r"Amount: (\d+(\.\d+)?)"
    }
    extracted_info = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        if match:
            extracted_info[key] = match.group(1).strip()
        else:
            extracted_info[key] = None
    return extracted_info

def get_recent_payeer_transactions() -> Dict[str, str]:
    today = datetime.now()
    four_days_ago = today - timedelta(days=4)

    query_params = 'newer_than:4d'
    results = service.users().messages().list(userId='me', q=query_params).execute()

    messages = results.get('messages', [])
    found = {}

    if messages:
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            for header in headers:
                if header['name'] == 'From' and 'Payeer.com' in header['value']:
                    snippet = msg.get('snippet', '')
                    info = extract_payeer_info(snippet)
                    if info['id'] and info['amount']:
                        found[info['id']] = info['amount']
    return found
