import os
import re
import base64
from typing import Dict
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# إعداد بيانات Google OAuth من environment variables
CLIENT_ID = os.getenv('client_id')
CLIENT_SECRET = os.getenv('client_secret')
REFRESH_TOKEN = os.getenv('refresh_token')
creds = Credentials(
    None,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
)
service = build("gmail", "v1", credentials=creds)
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

# ✅ جلب نص الرسالة من Gmail (يدعم multipart)
def get_message_body(msg):
    try:
        if 'data' in msg['payload']['body']:
            data = msg['payload']['body']['data']
        else:
            data = msg['payload']['parts'][0]['body']['data']
        decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        return decoded
    except Exception as e:
        return f"[خطأ في قراءة الرسالة]: {str(e)}"

# ✅ دالة رئيسية لجلب تحويلات سيريتيل من Gmail
def get_syriatel_transactions_from_gmail():
    print("📥 جاري البحث عن تحويلات سيريتيل في Gmail...")
    found = {}

    try:
        query = 'from:"SMS Forwarder"'  # أو من التطبيق نفسه
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            body = get_message_body(msg)

            # محاولة استخراج المبلغ ورقم العملية
            info = extract_syriatel_info(body)
            if info["id"] and info["amount"]:
                found[info["id"]] = info["amount"]

    except Exception as e:
        print("❌ خطأ أثناء جلب الرسائل:", e)

    return found

# ✅ تجربة الكود
if __name__ == "__main__":
    transactions = get_syriatel_transactions_from_gmail()
    if transactions:
        print("✅ تم العثور على العمليات التالية:")
        for tx_id, amount in transactions.items():
            print(f"🔢 رقم العملية: {tx_id} | 💰 المبلغ: {amount} SYP")
    else:
        print("❌ لم يتم العثور على تحويلات سيريتيل.")