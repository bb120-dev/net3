import os
import re
import base64
from typing import Dict
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# إعداد بيانات الاعتماد
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


# استخراج المعلومات من النص
def extract_syriatel_info(text: str) -> Dict[str, str]:
    patterns = {
        "amount": r"تم تعبئة.*?بـ\s*([\d.,]+)\s*ل\.س",
        "id": r"رقم عملية التعبئة\s*(\d{10,})"
    }
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        extracted[key] = match.group(1).strip() if match else None
    return extracted

# قراءة محتوى الرسالة
def get_message_body(msg) -> str:
    try:
        if 'data' in msg['payload']['body']:
            data = msg['payload']['body']['data']
        else:
            data = msg['payload']['parts'][0]['body']['data']
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    except:
        return ""

# استخراج المعاملات
def get_recent_syriatel_transactions() -> Dict[str, str]:
    found = {}
    try:
        query = 'from:"SMS Forwarder"'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            body = get_message_body(msg)
            if any(k in body for k in ["تم تعبئة", "ل.س", "رقم عملية التعبئة"]):
                info = extract_syriatel_info(body)
                if info["id"] and info["amount"]:
                    found[info["id"]] = info["amount"]
    except Exception as e:
        print("❌ Gmail error:", e)

    return found