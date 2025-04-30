from flask import Flask, request, jsonify
import re
import sqlite3

DATABASE_NAME = 'C:\Users\HP\Desktop\Bot\users.db'
app = Flask(__name__)

# دالة لإدخال السجل في قاعدة البيانات
def insert_record(value, numbertransfer):
    """Insert a new record into the table."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    insert_sql = '''
    INSERT INTO records (value, numbertransfer)
    VALUES (?, ?);
    '''
    
    cursor.execute(insert_sql, (value, numbertransfer))
    conn.commit()
    conn.close()

# استقبال الرسائل عبر POST
@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    message = data.get('message')
    
    if not message:
        return jsonify({'status': 'No message provided'}), 400

    # نمط البحث لاستخراج الكمية ورقم العملية
    pattern = r"(?:ب(?:مبلغ|ـ)\s*(\d+)\s*ل\.س|رقم(?: عملية التعبئة| العملية)?\s*(\d+))"
    
    # البحث عن الأرقام في الرسالة
    matches = re.findall(pattern, message)
    
    # التحقق من وجود تطابقات
    if matches:
        result = {}
        
        # تقسيم النتائج حسب النوع (الكمية ورقم العملية)
        for match in matches:
            if match[0]:  # إذا كان هذا التطابق هو المبلغ
                result['quantity'] = int(match[0])
            if match[1]:  # إذا كان هذا التطابق هو رقم العملية
                result['processNumber'] = int(match[1])
        
        # التحقق من وجود الكمية ورقم العملية في النتيجة
        if 'quantity' in result and 'processNumber' in result:
            # طباعة وإدخال القيم في قاعدة البيانات
            print(result)
            insert_record(result['quantity'], result['processNumber'])
            return jsonify({'status': 'Message received', 'message': message}), 200
        else:
            return jsonify({'status': 'Message incomplete, missing values'}), 400
    else:
        return jsonify({'status': 'No match found for message', 'message': message}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
