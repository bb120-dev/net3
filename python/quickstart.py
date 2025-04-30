
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from simplegmail.query import construct_query
from datetime import datetime, timedelta
import re
from typing import Dict
import json
import os
client_id = os.getenv('CLIENT_ID') 
client_secret = os.getenv('CLIENT_SECRET')  
refresh_token = os.getenv('REFRESH_TOKEN')
creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri='https://oauth2.googleapis.com/token',
    client_id=client_id,
    client_secret=client_secret
)

# إنشاء خدمة Gmail
service = build('gmail', 'v1', credentials=creds)
service = build('gmail', 'v1', credentials=creds)

# تحديد التواريخ
today = datetime.now()
two_days_ago = today - timedelta(days=4)

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

# استعلام عن الرسائل الجديدة
query_params = 'newer_than:4d'
results = service.users().messages().list(userId='me', q=query_params).execute()

messages = results.get('messages', [])
# معالجة الرسائل
dict_data = {}
if messages:  # تأكد من أن هناك رسائل
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        
        # الحصول على معلومات الرسالة
        headers = msg['payload']['headers']
        for header in headers:
            if header['name'] == 'From' and 'Payeer.com' in header['value']:
                snippet = msg['snippet']
                info = extract_payeer_info(snippet)
                if info['id'] and info['amount']:  # تأكد من أن المعلومات ليست None
                    dict_data[info['id']] = info['amount']
json_data = json.dumps(dict_data)
print(json_data)
