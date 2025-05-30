import sqlite3
import random
import string
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes,CallbackContext
import random
import string
import logging
from payeer_gmail_checker import get_recent_payeer_transactions
from syriatel_gmail_checker import get_recent_syriatel_transactions
import asyncio
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup ,InlineKeyboardButton , InlineKeyboardMarkup,BotCommandScopeChat,InlineQueryResultArticle,InputTextMessageContent,BotCommandScopeDefault
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes ,CallbackQueryHandler,JobQueue ,InlineQueryHandler
import subprocess
import json
from telegram import BotCommand
import requests
import uuid
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from simplegmail.query import construct_query
import os
import hmac
import hashlib
from telegram.error import Forbidden
import time
from functools import partial
from functools import wraps
from payeer_api import PayeerAPI
from dotenv import load_dotenv
import os
import io
load_dotenv()
TOKEN = os.getenv('TOKEN')
# قراءة القيم
GMAIL_CHECK_API_URL = os.getenv('GMAIL_CHECK_API_URL')
GMAIL_CHECK_API_TOKEN = os.getenv('GMAIL_CHECK_API_TOKEN')
BASE_URL = os.getenv('BASE_URL')
TEMP_MAIL_PASSWORD = os.getenv('TEMP_MAIL_PASSWORD')
ACCESS_ID = os.getenv('ACCESS_ID')
SECRET_KEY = os.getenv('SECRET_KEY')
BASE_URL_COINEX = os.getenv('BASE_URL_COINEX')
URI_COINEX = os.getenv('URI_COINEX')
METHOD_COINEX = os.getenv('METHOD_COINEX')
BODY_COINEX = os.getenv('BODY_COINEX')
async def set_bot_commands(application: Application):
    """إضافة الأوامر إلى قائمة البوت الرسمية (زر الثلاث نقاط ⋮)"""
    commands = [
        BotCommand("unban", "إلغاء الحظر")
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeChat(ADMIN_ID))
async def set_user_commands(application: Application):
    """إضافة الأوامر الرسمية لقائمة المستخدم العادي"""
    commands = [
        BotCommand("start", "تشغيل البوت"),
        BotCommand("balance", "عرض رصيدك"),
        BotCommand("logout", "تسجيل الخروج"),
        BotCommand("language", "تغيير اللغة")
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
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
coinx_networks = {
    "trc20": "TX1234567890abcdef",
    "bep20": "0xABCDEF1234567890",
    "coinx": "coinx-wallet-0987",
    "assent": "assent-wallet-4567"
}
ADMIN_ID = 863274300 
ADMIN_ID1 = 1455755529
#ADMIN_ID1 = 863274300
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول المطلوبة
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        username TEXT UNIQUE,
        balance REAL DEFAULT 0.0,
        credit REAL DEFAULT 0.0,
        referral_code TEXT UNIQUE,
        referrer_id INTEGER DEFAULT NULL,
        language TEXT DEFAULT NULL,
        password TEXT,
        is_logged_in INTEGER DEFAULT 0

    )
""")
def is_banned(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM banned_users WHERE chat_id = ?", (user_id,))
    return cursor.fetchone() is not None

def require_not_banned(handler):
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_chat.id
        if is_banned(user_id):
            # إذا أحببت، يمكنك إرسال رسالة تنبيهية:
            # await update.message.reply_text("🚫 أنت محظور ولا يمكنك استخدام هذا الأمر.")
            return  # نوقف تنفيذ الـ handler
        return await handler(update, context, *args, **kwargs)
    return wrapped
def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_type TEXT,
        email TEXT UNIQUE,
        password TEXT,
        recovery TEXT,
        price REAL,
        added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        account_type TEXT,
        request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_type TEXT,
        chat_id INTEGER,
        email TEXT UNIQUE,
        price REAL,
        password TEXT,
        recovery TEXT,
        purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        refund_requested INTEGER DEFAULT 0
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS banned_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id   INTEGER  UNIQUE,
        username TEXT UNIQUE
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        account_type TEXT,
        request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS currency_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        currency TEXT UNIQUE,
        rate REAL
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS refund_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        status TEXT DEFAULT 'Pending'
    )
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id TEXT UNIQUE,
    user_id INTEGER,
    method TEXT,
    amount REAL,
    status TEXT DEFAULT 'completed',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunded_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        email TEXT,
        password TEXT,
        recovery TEXT,
        price REAL,
        refund_time TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS unlock_prices (
    type TEXT PRIMARY KEY, 
    price REAL
);

""")
default_rates = [
    ("USDT", 10000),
    ("Dollar", 11500),
    ("SYP", 9700),
    ("Payeer", 10100),
    ("TRC20", 10000),
    ("BEP20", 10000),
    ("Bemo", 9500)
]

for currency, rate in default_rates:
    cursor.execute("INSERT OR IGNORE INTO currency_rates (currency, rate) VALUES (?, ?)", (currency, rate))

conn.commit()
@require_not_banned
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    context.user_data.pop("current_state", None)
    context.user_data.pop("referral_code",None)
    context.user_data.pop("referrer_id",None)
    username = context.user_data.get("username_login",None)
    args = context.args
    if user_id == ADMIN_ID or user_id ==ADMIN_ID1:
        await admin_panel(update, context)
        return
    cursor.execute("SELECT chat_id FROM banned_users WHERE username = ?", (username,))
    if cursor.fetchone():
        return

    # مسؤول البوت
   

    # التحقق من وجود المستخدم
    cursor.execute("SELECT chat_id, language, is_logged_in FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()

    if result:
        lang = result[1] or "ar"
        is_logged_in = result[2]
        print(is_logged_in == 1)
        if is_logged_in == 1:
            await main_menu(update, context, lang)
        else:
            # عرض اختيار اللغة من جديد
            keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            try:
                await update.message.reply_text("🌍 اختر لغتك | Choose your language:", reply_markup=reply_markup)
            except Forbidden:
                print(f"⚠️ المستخدم {user_id} حظر البوت.")
    else:
        # مستخدم جديد
        referral_code = generate_referral_code()
        referrer_id = None

        if args:
            ref_code = args[0]
            cursor.execute("SELECT id FROM users WHERE referral_code = ?", (ref_code,))
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referrer[0]
                cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, user_id))
                conn.commit()

        # حفظ بيانات التسجيل مؤقتًا في context
        context.user_data["referral_code"] = referral_code
        context.user_data["referrer_id"] = referrer_id
        context.user_data["username"] = username

        # طلب اختيار اللغة
        keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        try:
            await update.message.reply_text("🌍 اختر لغتك | Choose your language:", reply_markup=reply_markup)
        except Forbidden:
            print(f"⚠️ المستخدم {user_id} حظر البوت.")

@require_not_banned
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login", "")
    messages = {
        "ar": f"👋 مرحبًا <b>{username}</b> في بوت بيع الحسابات!\nاختر من القائمة أدناه:",
        "en": f"👋 Welcome <b>{username}</b> to the account selling bot!\nChoose from the menu below:"
    }

    # نصوص الأزرار
    btn_check   = "فحص جيميل (مجاني) 🕵‍♂🔥" if lang == "ar" else "Check Gmail (Free) 🕵‍♂🔥"
    btn_balances= "💰 الأرصدة"         if lang == "ar" else "💰 Balances"
    btn_buy     = "شراء حساب 🛒"        if lang == "ar" else "Buy Account 🛒"
    btn_temp    = "بريد وهمي (مجاني) ⌛🔥" if lang == "ar" else "📩 Temp Mail (Free) ⌛🔥"
    btn_unlock  = "فك حساب 🔓"          if lang == "ar" else "Unlock Account 🔓"
    btn_restore = "استرجاع ايميل ♻"     if lang == "ar" else "🔄 Restore Email ♻"
    btn_about   = "حول ℹ"              if lang == "ar" else "About ℹ"

    # بناء لوحة الأزرار
    keyboard = [
        [KeyboardButton(btn_check),    KeyboardButton(btn_balances)],
        [KeyboardButton(btn_buy)],
        [KeyboardButton(btn_temp),     KeyboardButton(btn_unlock)],
        [KeyboardButton(btn_restore),  KeyboardButton(btn_about)],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # إرسال الرسالة مع لوحة الأزرار
    await update.message.reply_text(
        messages[lang],
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
@require_not_banned
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("عرض الإحصائيات"), KeyboardButton("إدارة الحسابات")],
        [KeyboardButton("تعديل رصيد"), KeyboardButton("إضافة رصيد")],
        [KeyboardButton("إضافة رصيد إحالة") ,KeyboardButton("حظر حساب")],
        [KeyboardButton("عدد طلبات الشراء"),KeyboardButton("تحديد الأسعار")],
        [KeyboardButton("🛠️ تعديل اسعار فك حساب") ,KeyboardButton("🔍 البحث عن مستخدم")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔧 **لوحة تحكم الأدمن**:\nاختر من القائمة التالية:", reply_markup=reply_markup)
@require_not_banned
async def logout_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    text = "❓ هل أنت متأكد أنك تريد تسجيل الخروج؟" if lang == "ar" else "❓ Are you sure you want to log out?"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد" if lang == "ar" else "✅ Confirm", callback_data="logout_confirm")],
        [InlineKeyboardButton("❌ إلغاء" if lang == "ar" else "❌ Cancel", callback_data="logout_cancel")]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)
@require_not_banned
async def handle_logout_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    if query.data == "logout_confirm":
        # نحدث is_logged_in = 0
        cursor.execute("UPDATE users SET is_logged_in = 0 WHERE username = ?", (username,))
        conn.commit()

        context.user_data.pop("username_login", None)
        keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        msg = "✅ تم تسجيل خروجك.\n🌍 اختر لغتك للمتابعة:" if lang == "ar" else "✅ You have been logged out.\n🌍 Please choose your language:"
        await query.message.edit_text(msg)
        await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=reply_markup)

    elif query.data == "logout_cancel":
        msg = "❌ تم إلغاء تسجيل الخروج." if lang == "ar" else "❌ Logout cancelled."
        await query.message.edit_text(msg)
@require_not_banned
async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    text = update.message.text.strip()
    if text in ["/language", "تغيير اللغة", "Change Language"]:
        keyboard = [
            [KeyboardButton("🇸🇾 العربية"), KeyboardButton("🇬🇧 English")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🌍 اختر لغتك | Choose your language:", reply_markup=reply_markup)
        return

    if text not in ["🇸🇾 العربية", "🇬🇧 English"]:
        await update.message.reply_text("❌ يرجى اختيار لغة صحيحة من الأزرار.")
        return

    # تحديد كود اللغة
    language_code = "ar" if "العربية" in text else "en"
    username = context.user_data.get("username_login")
    # تحديث اللغة في قاعدة البيانات
    cursor.execute("UPDATE users SET language = ? WHERE username = ?", (language_code, username))
    conn.commit()

    # عرض رسالة تأكيد وفتح الواجهة
    message = "✅ تم تغيير اللغة إلى العربية." if language_code == "ar" else "✅ Language has been changed to English."
    await update.message.reply_text(message)
    await main_menu(update, context, language_code)

######################################################################################
@require_not_banned
async def general_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يوجّه الرسائل الواردة إلى المعالج المناسب
    بناءً على context.user_data['current_state'].
    """
    state = context.user_data.get("current_state")
    if state == "delete_handler":
        await process_email_deletion(update, context)
    elif state == "save_handler":
        await save_accounts(update, context)
    elif state == "balance_handler":
        await process_balance(update, context)
    elif state == "referral_handler":
        await process_referral_balance(update, context)
    elif state == "edit_handler":
        await process_edit_balance(update, context)
    elif state == "ban_handler":
        await ban_user(update, context)
    elif state == "rate_handler":
        await save_new_rates(update, context)
    elif state == "custom_handler":
        await process_custom_username(update, context)
    elif state == "login_handler":
        await process_login(update, context)
    elif state == "gift_handler":
        await process_gift_balance(update, context)
    elif state == "awaiting_payeer_txn":
        await process_payeer_txn_id(update, context)
    elif state == "awaiting_syriatel_txn":
        await process_syriatel_txn_id(update, context)
    elif state == "awaiting_bemo_txn":
        await process_bemo_txn_id(update, context)
    elif state == "retrieve_handler":
        await process_retrieve_email(update, context)
    elif state == "gmail_check_handler":
        await process_email_check(update, context)
    elif state == "unlock_handler":
        await process_unlock_email(update, context)
    elif state == "price_update_handler":
        await process_unlock_price_update(update, context)
    elif state == "search_handler":
        await process_username_search(update, context)
    else:
        user_id = update.effective_chat.id
        username = context.user_data.get("username_login")
        lang = get_user_language(username)
        messages = {
            "ar": "⚠️ الأمر غير صحيح. استخدم",
            "en": "⚠️ Invalid command. "
        }
        await update.message.reply_text(messages.get(lang, messages["en"]))


######################################إدارة الحسابات####################################################
@require_not_banned
async def show_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get("username_login")
    # جلب لغة المستخدم
    try:
        cursor.execute(
            "SELECT language FROM users WHERE username = ?", 
            (username,)
        )
        lang = cursor.fetchone()[0]
    except Exception:
        await update.message.reply_text("🚫 حدث خطأ داخلي، حاول مرة أخرى لاحقًا.")
        return

    # أولاً: عرض الرصيد تلقائيًا
    await check_balance(update, context)

    # ثم إعداد رسالة القائمة بدون زر "رصيدي"
    messages = {
        "ar": "الأرصدة: 🟥\nاختر ما يلي:",
        "en": "Balances: 🟥\nChoose one of the following:"
    }

    btn_charge = "شحن الرصيد – ⚡"    if lang == "ar" else "Recharge Balance – ⚡"
    btn_gift   = "إهداء رصيد – 🎁"    if lang == "ar" else "Gift Balance – 🎁"
    btn_back   = "العودة – ↩"        if lang == "ar" else "Back – ↩"

    keyboard = [
        [KeyboardButton(btn_charge),KeyboardButton(btn_gift)],
        [KeyboardButton(btn_back)],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        messages[lang],
        reply_markup=reply_markup
    )

#############################3
@require_not_banned
async def request_emails_for_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب من الأدمن إدخال الإيميلات المراد حذفها مؤقتاً."""
    user_id = update.effective_chat.id
    # صلاحية الأدمن
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = 'delete_handler'

    await update.message.reply_text(
        "✍️ أرسل الإيميلات التي تريد حذفها، كل إيميل في سطر منفصل:"
    )
@require_not_banned
async def process_email_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حذف الإيميلات المُرسَلة وإنهاء الحالة المؤقتة."""
    user_id = update.effective_chat.id
    # تحقق صلاحية الأدمن وحالة الانتظار
    if user_id not in (ADMIN_ID, ADMIN_ID1) :
        context.user_data.pop("current_state", None)
        return

    emails = update.message.text.splitlines()
    deleted, not_found = 0, []
    for e in emails:
        email = e.strip()
        if cursor.execute("SELECT 1 FROM accounts WHERE email = ?", (email,)).fetchone():
            cursor.execute("DELETE FROM accounts WHERE email = ?", (email,))
            deleted += 1
        else:
            not_found.append(email)
    conn.commit()

    # نظِّف الـ handler وحالة الانتظار
    # أرسل نتيجة العملية
    msg = f"✅ تم حذف {deleted} من أصل {len(emails)} إيميل."
    if not_found:
        msg += "\n❌ لم يتم العثور على:\n" + "\n".join(not_found)
    await update.message.reply_text(msg)
    context.user_data.pop("current_state", None)
@require_not_banned
async def return_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)
@require_not_banned
async def manage_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id != ADMIN_ID and user_id !=ADMIN_ID1:
        await update.message.reply_text("لا تملك الصلاحية لاستخدام هذا الأمر.")
        return

    keyboard = [
        [KeyboardButton("إضافة حسابات")],
        [KeyboardButton("عرض الحسابات")],
        [KeyboardButton("حذف الحسابات")],
         [KeyboardButton("العودة إلى قائمة الأدمن")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("إدارة الحسابات:\nاختر العملية التي تريد تنفيذها.", reply_markup=reply_markup)
@require_not_banned
async def add_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تفعيل استقبال نصوص إدخال الحسابات مؤقتاً للأدمن.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = 'save_handler'

    await update.message.reply_text(
        "📌 أرسل الحسابات بالترتيب التالي:\n\n"
        "1️⃣ نوع الحساب\n"
        "2️⃣ السعر\n"
        "3️⃣ كلمة المرور\n"
        "4️⃣ البريد الاحتياطي (Recovery)\n"
        "5️⃣ الحسابات (كل حساب في سطر منفصل)\n\n"
        "🔹 **مثال:**\n"
        "Gmail درجة أولى\n"
        "1500\n"
        "password123\n"
        "recovery@example.com\n"
        "email1@example.com\n"
        "email2@example.com"
    )

import io
@require_not_banned
async def save_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    حفظ الحسابات الواردة وإيقاف استقبال النصوص بعد الانتهاء.
    يرسل قائمة الإيميلات المكررة كملف نصي إذا تجاوزت الحد.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return

    lines = update.message.text.strip().splitlines()
    if len(lines) < 5:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ يرجى إرسال البيانات بالترتيب المطلوب:\n\n"
            "1️⃣ نوع الحساب\n"
            "2️⃣ السعر\n"
            "3️⃣ كلمة المرور\n"
            "4️⃣ البريد الاحتياطي (Recovery)\n"
            "5️⃣ الحسابات (كل حساب في سطر منفصل)"
        )

    account_type, price, password, recovery, *emails = lines
    duplicate_emails = []

    for email in emails:
        email = email.strip()
        exists_account = cursor.execute(
            "SELECT added_time FROM accounts WHERE email = ?", (email,)
        ).fetchone()
        exists_purchase = cursor.execute(
            "SELECT purchase_time FROM purchases WHERE email = ?", (email,)
        ).fetchone()

        if exists_account or exists_purchase:
            ts = exists_account[0] if exists_account else exists_purchase[0]
            duplicate_emails.append(f"{email} – أول إضافة: {ts}")
        else:
            cursor.execute(
                """
                INSERT INTO accounts (account_type, email, password, recovery, price, added_time)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (account_type, email, password, recovery, price)
            )
    conn.commit()

    # إشعار المستخدمين المنتظرين
    pending = cursor.execute(
        "SELECT chat_id FROM pending_requests WHERE account_type = ?", (account_type,)
    ).fetchall()
    for (chat_id,) in pending:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ الحساب من نوع {account_type} أصبح متاحًا الآن!"
            )
        except Exception as e:
            logging.error(f"تعذّر الإشعار للمستخدم {chat_id}: {e}")

    cursor.execute(
        "DELETE FROM pending_requests WHERE account_type = ?", (account_type,)
    )
    conn.commit()

    # إذا كان هناك مكررات، أرسلها (وقد تكون طويلة جداً)
    if duplicate_emails:
        text = "⚠️ بعض الإيميلات مكررة ولم تُضاف:\n\n" + "\n".join(duplicate_emails)
        # إذا النص أكبر من حد تيليجرام، أرسله كملف نصي
        if len(text) > 4000:
            bio = io.BytesIO(text.encode("utf-8"))
            bio.name = "duplicates.txt"
            bio.seek(0)
            await update.message.reply_document(
                document=bio,
                filename="duplicates.txt",
                caption="⚠️ قائمة الإيميلات المكررة"
            )
        else:
            await update.message.reply_text(text)

    success_count = len(emails) - len(duplicate_emails)
    await update.message.reply_text(
        f"✅ تم إضافة {success_count} حساب من نوع {account_type} بنجاح وإشعار المستخدمين المنتظرين!"
    )
    context.user_data.pop("current_state", None)

@require_not_banned
async def show_accounts1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الحسابات مُجمعة وإرسال الإيميلات في ملف نصي لكل مجموعة."""
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    cursor.execute("""
        SELECT account_type, email, password, recovery
        FROM accounts
        ORDER BY account_type, password, recovery
    """)
    rows = cursor.fetchall()
    if not rows:
        return await update.message.reply_text("❌ لا توجد حسابات متاحة حاليًا.")

    # جمّع الحسابات حسب النوع، كلمة المرور، والبريد الاحتياطي
    groups = {}
    for acct_type, email, pwd, rec in rows:
        key = (acct_type, pwd, rec)
        groups.setdefault(key, []).append(email)

    # لكل مجموعة: أرسل الوصف ثم ملف الإيميلات
    for (acct_type, pwd, rec), emails in groups.items():
        count = len(emails)
        header = (
            f"📋 **نوع الحساب:** {acct_type}\n"
            f"🔢 **عدد الحسابات:** {count}\n"
            f"🔑 **كلمة المرور:** {pwd}\n"
            f"📩 **البريد الاحتياطي:** {rec}\n\n"
            "⤵️ **قائمة الإيميلات مرفقة في الملف**"
        )
        await update.message.reply_text(header, parse_mode="Markdown")

        # جهّز الملف
        content = "\n".join(emails)
        bio = io.BytesIO(content.encode("utf-8"))
        bio.name = f"{acct_type}_{pwd}_{rec}.txt".replace(" ", "_")
        bio.seek(0)

        # أرسل الملف
        await update.message.reply_document(
            document=bio,
            filename=bio.name,
            caption=f"📂 إيميلات {acct_type} ({count} حساب)"
        )
##########################################################################################################
#############################إضافة وتعديل الرصيد #######################################################
@require_not_banned
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = 'balance_handler'
    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ الذي تريد إضافته بالشكل التالي:\n\n"
        "@username 50.0"
    )
@require_not_banned
async def add_referral_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تفعيل استقبال نصّي لإضافة رصيد الإحالة مؤقتاً للأدمن.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = 'referral_handler'

    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ لإضافته إلى رصيد الإحالة:\n\n"
        "@username 10.0"
    )
@require_not_banned
async def process_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة طلب إضافة الرصيد الأساسي وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: @username 50.0"
        )

    username, amt = parts[0].lstrip("@"), parts[1]
    try:
        amount = float(amt)
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ المبلغ يجب أن يكون رقمياً.")

    # جلب معرف المستخدم
    cursor.execute(
        "SELECT chat_id FROM users WHERE username = ? OR referral_code = ?",
        (username, username)
    )
    row = cursor.fetchone()
    if not row:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(f"⚠️ المستخدم {username} غير مسجل.")

    target_id = row[0]
    # تحديث الرصيد
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE username = ?",
        (amount, username)
    )
    conn.commit()
    context.user_data.pop("current_state", None)
    await update.message.reply_text(f"✅ تم إضافة {amount} إلى @{username}.")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💰 تم شحن رصيدك بمبلغ {amount}."
        )
    except:
        pass
@require_not_banned
async def process_referral_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة طلب إضافة رصيد الإحالة وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)

        return

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        context.user_data.pop("current_state", None)

        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة لإحالة: @username 10.0"
        )

    username, amt = parts[0].lstrip("@"), parts[1]
    try:
        amount = float(amt)
    except ValueError:
        context.user_data.pop("current_state", None)

        return await update.message.reply_text("❌ المبلغ يجب أن يكون رقمياً.")

    cursor.execute("SELECT chat_id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        context.user_data.pop("current_state", None)

        return await update.message.reply_text(f"⚠️ المستخدم {username} غير مسجل.")

    target_id = row[0]
    # تحديث رصيد الإحالة
    cursor.execute(
        "UPDATE users SET credit = credit + ? WHERE username = ?",
        (amount, username)
    )
    conn.commit()
    context.user_data.pop("current_state", None)


    await update.message.reply_text(f"✅ تم إضافة {amount} إلى رصيد الإحالة @{username}.")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🔗 رصيد الإحالة الخاص بك زاد بمقدار {amount}."
        )
    except:
        pass
@require_not_banned
async def edit_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تفعيل استقبال نصّي لتعديل رصيد المستخدم مؤقتاً للأدمن.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)

        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = 'edit_handler'

    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ الجديد للرصيد بالشكل التالي:\n\n"
        "@username 100.0"
    )
@require_not_banned
async def process_edit_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة طلب تعديل رصيد المستخدم وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: @username 100.0"
        )

    username, amt = parts[0].lstrip("@"), parts[1]
    try:
        new_balance = float(amt)
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ المبلغ يجب أن يكون رقمياً.")

    # جلب معرف المستخدم
    cursor.execute("SELECT chat_id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(f"⚠️ المستخدم {username} غير مسجل.")

    target_id = row[0]
    # تعديل الرصيد في قاعدة البيانات
    cursor.execute(
        "UPDATE users SET balance = ? WHERE username = ?",
        (new_balance, username)
    )
    conn.commit()
    context.user_data.pop("current_state", None)

    await update.message.reply_text(f"✅ تم تعديل رصيد @{username} إلى {new_balance}.")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🔄 تم تحديث رصيدك إلى {new_balance}."
        )
    except:
        pass








###########################################################################################################
####################حظر حساب ###############################################################################
@require_not_banned
async def request_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب من الأدمن إدخال اسم المستخدم لحظره مؤقتاً.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    context.user_data["current_state"] = 'ban_handler'

    await update.message.reply_text("✍️ أرسل اسم المستخدم الذي تريد حظره:")

@require_not_banned
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة حظر المستخدم بناءً على الاسم المدخل وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1) :
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    username_to_ban = update.message.text.strip()

    # تحقق إذا كان محظوراً سابقاً
    if cursor.execute(
        "SELECT 1 FROM banned_users WHERE username = ?", (username_to_ban,)
    ).fetchone():
        await update.message.reply_text("⚠️ هذا المستخدم محظور بالفعل.")
    else:
        # ابحث عن chat_id للمستخدم
        row = cursor.execute(
            "SELECT chat_id FROM users WHERE username = ?", (username_to_ban,)
        ).fetchone()
        if row:
            print('fgfdgdfgfdgdfgfdgfg')
            chat_id = row[0]
            cursor.execute(
                "INSERT INTO banned_users (username, chat_id) VALUES (?, ?)",
                (username_to_ban, chat_id)
            )
            conn.commit()
            await update.message.reply_text(f"✅ تم حظر المستخدم {username_to_ban} بنجاح!")
        else:
            await update.message.reply_text(f"⚠️ المستخدم {username_to_ban} غير موجود.")
    context.user_data.pop("current_state", None)
@require_not_banned
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر مستخدم والسماح له باستخدام البوت مجددًا"""
    user_id = update.effective_chat.id
    if user_id != ADMIN_ID and user_id !=ADMIN_ID1:
        await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
        return
    
    try:
        target_username = context.args[0].lstrip("@")  # إزالة "@" من البداية
        cursor.execute("DELETE FROM banned_users WHERE username = ?", (target_username,))
        conn.commit()
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم @{target_username}.")
    except IndexError:
        await update.message.reply_text("❌ يرجى إرسال اسم المستخدم بالشكل الصحيح: `/unban @username`")
#############################################################################################################
##################################إحصائيات########################################################
@require_not_banned
async def accounts_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات الحسابات وعدد الحسابات المطلوبة للاسترجاع"""
    user_id = update.effective_chat.id
    if user_id != ADMIN_ID and user_id !=ADMIN_ID1:
        await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
        return
    
    # استعلام عن عدد الحسابات لكل نوع
    cursor.execute("SELECT account_type, COUNT(*) FROM accounts GROUP BY account_type")
    stats = cursor.fetchall()

    # استعلام عن الحسابات المطلوبة للاسترجاع
    cursor.execute("SELECT account_type, chat_id, request_time FROM pending_requests ORDER BY request_time DESC")
    requested_accounts = cursor.fetchall()
    
    message = "📊 **إحصائيات الحسابات:**\n\n"
    
    if stats:
        message += "📌 **عدد الحسابات لكل نوع:**\n"
        for stat in stats:
            message += f"🔹 **{stat[0]}** - {stat[1]} حساب\n"
    else:
        message += "❌ لا توجد حسابات مسجلة حاليًا.\n"

    message += "\n📦 **طلبات استرجاع الحسابات:**\n"
    
    if requested_accounts:
        for req in requested_accounts:
            message += f"🔻 **{req[0]}** - طلب من المستخدم `{req[1]}` في {req[2]}\n"
    else:
        message += "✅ لا توجد طلبات استرجاع حالية.\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")
#######################################################################################################
@require_not_banned
async def ask_for_new_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب إدخال الأسعار الجديدة مؤقتاً للأدمن.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 You do not have permission to use this command.")

    # نظّف أي Handler قديم وحالة انتظار سابقة
    context.user_data["current_state"] = 'rate_handler'

    # أرسل التعليمات
    await update.message.reply_text(
        "✍️ *Please enter the new rates in the following format:*\n\n"
        "USDT - 10200\n"
        "Dollar - 11600\n"
        "Syriatel Cash - 9800\n"
        "Payeer - 10100\n"
        "TRC20 - 10000\n"
        "BEP20 - 10000\n"
        "Bemo - 9500\n\n"
        "✅ Send the list now:",
        parse_mode="Markdown"
    )
@require_not_banned
async def save_new_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1) :
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    lines = update.message.text.strip().splitlines()
    if not lines:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ Please enter the rates correctly.")

    updated, failed = [], []
    for line in lines:
        try:
            currency, rate_str = line.split(" - ")
            rate = float(rate_str.strip())
            cursor.execute(
                "UPDATE currency_rates SET rate = ? WHERE currency = ?",
                (rate, currency.strip())
            )
            updated.append(f"{currency.strip()}: {rate}")
        except Exception:
            failed.append(line)

    conn.commit()

    # إعداد رسالة الرد
    msg = "✅ The following rates have been updated:\n" + "\n".join(updated)
    if failed:
        msg += "\n\n⚠️ The following lines were not understood:\n" + "\n".join(failed)

    await update.message.reply_text(msg)

    # نظّف Handler وحالة الانتظار
    context.user_data.pop("current_state", None)

#########################################################################################3
@require_not_banned
async def purchase_requests_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض عدد طلبات الشراء والاسترجاع اليومية والشهرية لكل نوع"""
    user_id = update.effective_chat.id
    if user_id != ADMIN_ID and user_id !=ADMIN_ID1:
        await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
        return

    now = datetime.now()

    # 🕛 اليوم من 00:00 إلى 24:00
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)

    # 🗓️ بداية الشهر الحالي
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ========== 📥 الطلبات ==========

    # 🔹 عدد طلبات الشراء اليوم
    cursor.execute("""
        SELECT account_type, COUNT(*) FROM purchases
        WHERE purchase_time >= ? AND purchase_time < ?
        GROUP BY account_type
    """, (start_time, end_time))
    daily = cursor.fetchall()

    # 🔸 عدد طلبات الشراء في الشهر
    cursor.execute("""
        SELECT account_type, COUNT(*) FROM purchases
        WHERE purchase_time >= ?
        GROUP BY account_type
    """, (month_start,))
    monthly = cursor.fetchall()

    # 📦 الإجمالي
    cursor.execute("SELECT COUNT(*) FROM purchases")
    total_requests = cursor.fetchone()[0]

    # ========== ♻️ الاسترجاعات ==========

    # 🔹 عدد استرجاعات اليوم
    cursor.execute("""
        SELECT COUNT(*) FROM refunded_accounts
        WHERE refund_time >= ? AND refund_time < ?
    """, (start_time, end_time))
    refunded_today = cursor.fetchone()[0]

    # 🔸 عدد استرجاعات الشهر
    cursor.execute("""
        SELECT COUNT(*) FROM refunded_accounts
        WHERE refund_time >= ?
    """, (month_start,))
    refunded_month = cursor.fetchone()[0]

    # 🧾 صياغة الرسالة
    message = f"📊 **إحصائيات الطلبات والاسترجاعات**\n\n"
    message += f"📦 **إجمالي الشراء:** {total_requests} طلب\n\n"

    message += f"🕛 **اليوم ({start_time.strftime('%Y-%m-%d')}) من 00:00 حتى 24:00:**\n"
    if daily:
        for account_type, count in daily:
            message += f"🔹 {account_type}: {count} طلب\n"
    else:
        message += "🔸 لا توجد طلبات شراء اليوم.\n"
    message += f"♻️ استرجاعات اليوم: {refunded_today}\n"

    message += f"\n🗓️ **الشهر الحالي ({month_start.strftime('%B %Y')}):**\n"
    if monthly:
        for account_type, count in monthly:
            message += f"🔹 {account_type}: {count} طلب\n"
    else:
        message += "🔸 لا توجد طلبات شراء هذا الشهر.\n"
    message += f"♻️ استرجاعات هذا الشهر: {refunded_month}"

    await update.message.reply_text(message, parse_mode="Markdown")

#############################################################زبون
#############################اللغة
def generate_username(update: Update) -> str:
    # 1) try Telegram username
    tg_username = update.effective_chat.username
    if tg_username:
        base = "".join(ch for ch in tg_username if ch.isalnum())
    else:
        # 2) try full name
        full_name = update.effective_chat.full_name or ""
        clean_name = "".join(ch for ch in full_name if ch.isalnum())
        if clean_name:
            base = clean_name
        else:
            # 3) fallback random
            suffix = "".join(random.choices(string.ascii_letters + string.digits, k=6))
            base = "User" + suffix

    # ensure unique in DB by appending numbers
    candidate = base
    suffix = 1
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (candidate,))
    while cursor.fetchone():
        candidate = f"{base}{suffix}"
        suffix += 1
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (candidate,))

    return candidate
def generate_password():
    chars = string.ascii_letters + string.digits + "!#$%^&*()_+=-"
    return ''.join(random.choices(chars, k=10))
@require_not_banned
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    chosen_language = update.message.text

    if chosen_language in ["العربية", "English"]:
        lang = "ar" if chosen_language == "العربية" else "en"
        context.user_data["language"] = lang

        username = generate_username(update)
        password = generate_password()

        context.user_data["pending_username"] = username
        context.user_data["pending_password"] = password

        msg = {
            "ar": f"🚀 سيتم إنشاء حساب LTE خاص بك باستخدام البيانات التالية 😇:\n\n👤 اسم المستخدم: <code>{username}</code>\n🔑 كلمة المرور: <code>{password}</code>\n\nاضغط على \"موافق 👍🏻\" لإتمام العملية\nإذا كنت تمتلك حساب LTE مسبقاً اضغط على \"تسجيل دخول 🚪\"\nإذا أردت اسم مستخدم مختلف اضغط على \"إدخال اسم مستخدم مخصص 🤓\"",
            "en": f"🚀 Your LTE account will be created with the following data 😇:\n\n👤 Username: <code>{username}</code>\n🔑 Password: <code>{password}</code>\n\nPress \"👍🏻 Confirm\" to complete\nIf you already have an account, press \"🚪 Login\"\nOr press \"🤓 Custom Username\" to enter your own."
        }

        keyboard = [[
            KeyboardButton("👍🏻 موافق" if lang == "ar" else "👍🏻 Confirm"),
            KeyboardButton("🚪 تسجيل دخول" if lang == "ar" else "🚪 Login")
        ], [
            KeyboardButton("🤓 إدخال اسم مستخدم مخصص" if lang == "ar" else "🤓 Custom Username")
        ]]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(msg[lang], parse_mode="HTML", reply_markup=reply_markup)

# --- تأكيد وإنشاء الحساب ---
@require_not_banned
async def confirm_account_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_chat.id
    username = context.user_data.get("pending_username")
    password = context.user_data.get("pending_password")
    lang = context.user_data.get("language", "ar")
    referral_code = generate_referral_code()
    print(referral_code)
    referrer_id = context.user_data.get("referrer_id")
    context.user_data["username_login"] = username
    if username and password:
        cursor.execute("SELECT chat_id FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        if existing and existing[0] != user_id:
            await update.message.reply_text("⚠️ اسم المستخدم هذا محجوز بالفعل، الرجاء اختيار اسم مستخدم آخر.")
            return
        cursor.execute("INSERT  INTO users (chat_id, username, password, language, referral_code, referrer_id,is_logged_in) VALUES (?, ?, ?, ?, ?, ?,?)",
                       (user_id, username, password, lang, referral_code, referrer_id,1))
        conn.commit()
        await main_menu(update, context, lang)

# --- اسم مستخدم مخصص ---
@require_not_banned
async def request_custom_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب اسم مستخدم مخصص مؤقتاً.
    """
    lang = context.user_data.get("language", "ar")
    prompt = (
        "✍️ أرسل اسم المستخدم الذي ترغب به:"
        if lang == "ar"
        else "✍️ Please send your desired username:"
    )

    context.user_data["current_state"] = 'custom_handler'
    await update.message.reply_text(prompt)
@require_not_banned
async def process_custom_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    

    username      = update.message.text.strip()
    password      = context.user_data.get("pending_password")
    lang          = context.user_data.get("language", "ar")
    referral_code = generate_referral_code()
    referrer_id   = context.user_data.get("referrer_id")

    cursor.execute("SELECT chat_id FROM users WHERE username = ?", (username,))
    existing = cursor.fetchone()
    if existing and existing[0] != user_id:
        await update.message.reply_text("⚠️ اسم المستخدم هذا محجوز بالفعل، الرجاء اختيار اسم مستخدم آخر.")
        return

    # 2. إذا لم يكن موجوداً أو كان هذا نفس المستخدم، أدخل أو حدّث السجل
    cursor.execute(
        """
        INSERT INTO users
        (chat_id, username, password, language, referral_code, referrer_id, is_logged_in)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (user_id, username, password, lang, referral_code, referrer_id)
    )
    conn.commit()

    # 3. نظّف حالة التسجيل السابقة وانتقل للقائمة الرئيسية
    context.user_data.pop("pending_username", None)
    context.user_data.pop("pending_password", None)
    context.user_data.pop("referral_code", None)
    context.user_data.pop("referrer_id", None)
    context.user_data.pop("current_state", None)
    context.user_data["username_login"] = username
    await main_menu(update, context, lang)
# --- تسجيل الدخول ---
@require_not_banned
async def login_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب تسجيل الدخول: استقبل اسم المستخدم وكلمة المرور في سطرين متتاليين.
    """
    user_id = update.effective_chat.id
    lang = context.user_data.get("language", "ar")
    prompt = (
        "✍️ أرسل اسم المستخدم ثم كلمة المرور في سطرين متتاليين:"
        if lang == "ar"
        else "✍️ Send your username and password on two lines."
    )
    context.user_data["current_state"] = 'login_handler'
    await update.message.reply_text(prompt)
@require_not_banned
async def process_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة بيانات تسجيل الدخول وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    lang = context.user_data.get("language", "ar")
    # استخراج السطرين: اسم المستخدم ثم كلمة المرور
    lines = update.message.text.strip().split("\n")
    if len(lines) != 2:
        msg_err = (
            "❌ يرجى إدخال اسم المستخدم وكلمة المرور بشكل صحيح."
            if lang == "ar"
            else "❌ Invalid format."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg_err)

    username, password = lines
    cursor.execute(
        "SELECT chat_id FROM users WHERE username = ? AND password = ?",
        (username, password)
    )
    result = cursor.fetchone()

    if result:
        # تسجيل الدخول وتحديث chat_id
        cursor.execute(
            "UPDATE users SET is_logged_in = 1 WHERE username = ?",
            (username,)
        )
        context.user_data["username_login"] = username
        conn.commit()
        await context.bot.send_message(
                chat_id=result[0],
                text=(
                    f"⚠️ تم تسجيل الدخول على الحساب '{username}' "
                    f"بواسطة المستخدم [{user_id}]."
                )
            )
        await main_menu(update, context, lang)
    else:
        msg_fail = (
            "❌ فشل تسجيل الدخول. تحقق من البيانات."
            if lang == "ar"
            else "❌ Login failed. Check your credentials."
        )
        await update.message.reply_text(msg_fail)

    # نظّف Handler وحالة الانتظار بعد المحاولة
    context.user_data.pop("current_state", None)
#######################################################################################
#################################################################3حساباتي
@require_not_banned
async def show_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    cursor.execute("SELECT email, password, purchase_time FROM purchases WHERE chat_id = ?", (user_id,))
    accounts = cursor.fetchall()

    if accounts:
        message = "📂 حساباتك المتاحة:\n\n"
        now = datetime.now()
        for email, password, purchase_time in accounts:
            purchase_date = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
            expiry_date = purchase_date + timedelta(days=30)
            days_left = (expiry_date - now).days
            status = "✅ صالح" if days_left > 0 else "❌ منتهي الصلاحية"
            message += f"📧 البريد الإلكتروني: `{email}`\n🔑 كلمة المرور: `{password}`\n📅 انتهاء الصلاحية: {expiry_date.strftime('%Y-%m-%d')} ({days_left} يوم متبقي)\n🔹 الحالة: {status}\n\n"
        await update.message.reply_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ لا يوجد لديك أي حسابات مشتراة.")
######################################################################################إحالة صديق
@require_not_banned
async def referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    cursor.execute("SELECT referral_code, language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    
    if result:
        referral_code, language = result
        referral_url = f"https://t.me/{context.bot.username}?start={referral_code}"
        
        messages = {
            "ar": f"🔗 رابط الإحالة الخاص بك:\n\n`{referral_url}`\n\n👥 انسخ الرابط وشاركه مع أصدقائك للحصول على مكافآت!",
            "en": f"🔗 Your referral link:\n\n`{referral_url}`\n\n👥 Copy the link and share it with your friends to earn rewards!"
        }
        
        msg = messages.get(language, messages["ar"])
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ لا يمكن العثور على رمز الإحالة الخاص بك.")
#########################################################################################ؤصيدي
@require_not_banned
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد، رابط الإحالة، وعدد الإحالات"""
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")

    # جلب بيانات المستخدم من قاعدة البيانات
    cursor.execute("SELECT id , balance, credit, referral_code, language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()

    if result:
        id, balance, credit, referral_code, language = result

        # حساب عدد الأشخاص الذين سجلوا باستخدام رابط الإحالة
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (id,))
        referral_count = cursor.fetchone()[0]
        cursor.execute("SELECT * FROM users ")
        referral_count1 = cursor.fetchall()
        print(referral_count1)
        # إنشاء رابط الإحالة
        referral_url = f"https://t.me/{context.bot.username}?start={referral_code}"

        # رسائل متعددة اللغات
        messages = {
            "ar": f"💰 **رصيدك:** `{balance:.2f} ل.س`\n"
                  f"🎁 **رصيد الإحالة:** `{credit:.2f} ل.س`\n\n"
                  f"🔗 **رابط الإحالة الخاص بك:**\n[{referral_url}]({referral_url})\n\n"
                  f"👥 **عدد الأشخاص المرتبطين بحسابك:** `{referral_count}`",
            
            "en": f"💰 **Your balance:** `{balance:.2f} L.S`\n"
                  f"🎁 **Referral balance:** `{credit:.2f} L.S`\n\n"
                  f"🔗 **Your referral link:**\n[{referral_url}]({referral_url})\n\n"
                  f"👥 **Total referrals:** `{referral_count}`"
        }

        msg = messages.get(language, messages["ar"])
        await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")
################################################################################################
@require_not_banned
async def show_currency_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أسعار العملات الحالية"""
    cursor.execute("SELECT currency, rate FROM currency_rates ORDER BY currency")
    rates = cursor.fetchall()

    if not rates:
        await update.message.reply_text("❌ لم يتم ضبط أسعار العملات بعد.")
        return
    
    message = "💱 **أسعار العملات الحالية:**\n\n"
    for currency, rate in rates:
        message += f"🔹 1 {currency} = {rate} ليرة سورية\n"
    
    
    await update.message.reply_text(message, parse_mode="Markdown")
################################################################################################################
@require_not_banned
async def buy_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get("username_login")

    # 1. جلب لغة المستخدم
    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    lang = row[0] if row else "ar"

    # 2. جلب عدد الحسابات المتوفّرة
    cursor.execute("SELECT account_type, COUNT(*) FROM accounts GROUP BY account_type")
    accounts = dict(cursor.fetchall())
    account_types = {
        "G1": accounts.get("G1", 0),
        "G2": accounts.get("G2", 0),
        "HOT": accounts.get("hot", 0),
        "OUT": accounts.get("out", 0)
    }

    # 3. جلب أسعار العملات
    cursor.execute("SELECT currency, rate FROM currency_rates ORDER BY currency")
    rates = cursor.fetchall()

    # 4. بناء الرسالة النصية
    if lang == "ar":
        header = "شراء حساب: 🟥"
        msg = "💰 اختر نوع الحساب الذي ترغب بشرائه:\n\n"
        msg += "📂 **الحسابات المتاحة:**\n"
        for acc, cnt in account_types.items():
            msg += f"🔹 **{acc}**: {cnt} حساب\n"
        if rates:
            msg += "\n💱 **أسعار العملات الحالية:**\n"
            for curr, rate in rates:
                msg += f"🔹 1 {curr} = {rate} ليرة سورية\n"

        keyboard = [
            [KeyboardButton("شراء حساب Gmail درجة أولى⭐🅶"),
             KeyboardButton("شراء حساب Gmail درجة ثانية🅶")],
            [KeyboardButton("شراء حساب 🅾Outlook"),
             KeyboardButton("شراء حساب 🅷Hotmail")],
            [KeyboardButton("العودة – ↩")]
        ]
    else:
        header = "Buy Account: 🟥"
        msg = "💰 Select the type of account you want to buy:\n\n"
        msg += "📂 **Available Accounts:**\n"
        for acc, cnt in account_types.items():
            msg += f"🔹 **{acc}**: {cnt} available\n"
        if rates:
            msg += "\n💱 **Current Currency Rates:**\n"
            for curr, rate in rates:
                msg += f"🔹 1 {curr} = {rate} SYP\n"

        keyboard = [
            [KeyboardButton("Buy Gmail First-Class Account ⭐🅶"),
             KeyboardButton("Buy Gmail Second-Class Account 🅶")],
            [KeyboardButton("Buy 🅾 Outlook Account"),
             KeyboardButton("Buy 🅷 Hotmail Account")],
            [KeyboardButton("Back – ↩")]
        ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # 5. عرض العنوان
    await update.message.reply_text(header)
    # 6. عرض التفاصيل (بـ Markdown) ثم الأزرار
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


@require_not_banned
async def select_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # 1. التعاطي مع زر العودة
    if text in ("العودة – ↩", "Back – ↩"):
        return await return_to_prev(update, context)

    # 2. تعيين mapping كامل بالنصوص مع الإيموجيات
    mapping = {
        "شراء حساب Gmail درجة أولى⭐🅶": "G1",
        "شراء حساب Gmail درجة ثانية🅶": "G2",
        "شراء حساب 🅾Outlook":           "out",
        "شراء حساب 🅷Hotmail":           "hot",
        "Buy Gmail First-Class Account ⭐🅶": "G1",
        "Buy Gmail Second-Class Account 🅶":  "G2",
        "Buy 🅾 Outlook Account":             "out",
        "Buy 🅷 Hotmail Account":             "hot",
    }

    internal_type = mapping.get(text)
    if not internal_type:
        return await update.message.reply_text("❌ نوع الحساب غير معروف.")

    context.user_data["selected_account_type"] = internal_type

    # 3. عرض لوحة لتحديد العدد
    qty_buttons = [
        [KeyboardButton("1"), KeyboardButton("3")],
        [KeyboardButton("5"), KeyboardButton("10")],
        [KeyboardButton("العودة – ↩") if context.user_data.get("lang","ar")=="ar"
             else KeyboardButton("Back – ↩")]
    ]
    reply_markup = ReplyKeyboardMarkup(qty_buttons, resize_keyboard=True)

    await update.message.reply_text(
        f"📦 تم اختيار: {text}\n\n🔢 حدد الكمية المطلوبة:",
        reply_markup=reply_markup
    )
@require_not_banned
async def process_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    try:
        quantity = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")
        return

    selected_type = context.user_data.get('selected_account_type')
    if not selected_type:
        await update.message.reply_text("❌ لم يتم تحديد نوع الحساب.")
        return

    # استعلام لمعرفة عدد الحسابات المتوفرة وسعر الحساب الواحد
    cursor.execute(
        "SELECT email, price FROM accounts WHERE account_type = ?",
        (selected_type,)
    )
    available_accounts = cursor.fetchall()

    available_count = len(available_accounts)
    if available_count == 0:
        await update.message.reply_text("❌ لا توجد حسابات متاحة من هذا النوع حالياً.")
        return

    price_per_account = available_accounts[0][1] if available_accounts else 0
    total_price = price_per_account * quantity
    username = context.user_data.get("username_login")

    # استعلام للحصول على رصيد الشحن ورصيد الإحالة ولغة المستخدم
    cursor.execute(
        "SELECT COALESCE(balance, 0), COALESCE(credit, 0), language FROM users WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    if not result:
        await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")
        return
    balance, credit, lang = result

    # التأكد من أن مجموع الرصيدين كافٍ لتغطية قيمة الشراء
    if (balance + credit) < total_price:
        await update.message.reply_text("❌ رصيدك غير كافٍ لإتمام العملية.")
        return

    messages = {
        "ar": {
            "confirm": f"✅ سيتم خصم {total_price:.2f} ل.س لشراء {quantity} حساب من نوع {selected_type}. هل تريد المتابعة؟",
            "not_available": f"⚠️ الكمية المطلوبة ({quantity}) غير متوفرة. المتاح: {available_count} حساب.",
            "notify_admin": f"🚨 نقص الحسابات: {selected_type} - مطلوب: {quantity}, متاح: {available_count}.",
            "select_account": "🔽 **اختر الحساب الذي تريد شراءه:**"
        },
        "en": {
            "confirm": f"✅ {total_price:.2f} L.S will be deducted to buy {quantity} {selected_type} accounts. Continue?",
            "not_available": f"⚠️ Requested quantity ({quantity}) is unavailable. Available: {available_count} accounts.",
            "notify_admin": f"🚨 Shortage Alert: {selected_type} - Requested: {quantity}, Available: {available_count}.",
            "select_account": "🔽 **Select the account you want to buy:**"
        }
    }
    if quantity == 1:
    # تخزين النوع والسعر لاستخدامهم لاحقًا في query_text
        context.user_data["selected_account_type"] = selected_type
        context.user_data["total_price"] = total_price

        # إرسال زر لتفعيل inline query (داخل نفس المحادثة)
        keyboard = [[InlineKeyboardButton("📋 الحسابات المتاحة", switch_inline_query_current_chat=f"buy_1_{selected_type}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(messages[lang]["select_account"], reply_markup=reply_markup)

    elif available_count >= quantity:
        # تخزين تفاصيل عملية الشراء المعلقة
        context.user_data["pending_purchase"] = {
            "quantity": quantity,
            "account_type": selected_type,
            "total_price": total_price
        }
        keyboard = [
            [KeyboardButton("تأكيد" if lang == "ar" else "Confirm"),
             KeyboardButton("إلغاء" if lang == "ar" else "Cancel")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(messages[lang]["confirm"], reply_markup=reply_markup)
    else:
        await update.message.reply_text(messages[lang]["not_available"])
        await context.bot.send_message(chat_id=ADMIN_ID1, text=messages[lang]["notify_admin"])
@require_not_banned
async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    email = update.message.text.replace("/buy_account", "").strip()
    
    # التحقق من وجود الحساب
    cursor.execute("SELECT id, password, recovery, price, account_type FROM accounts WHERE email = ?", (email,))
    account = cursor.fetchone()
    if not account:
        await update.message.reply_text("❌ الحساب غير متوفر.")
        return

    acc_id, password, recovery, price, account_type = account
    print(account_type)
    # جلب رصيد المستخدم
    cursor.execute("SELECT id , balance, credit FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    if not result:
        await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")
        return

    id,balance, credit = result
    total_funds = balance + credit

    if total_funds < price:
        await update.message.reply_text("❌ رصيدك غير كافٍ لإتمام عملية الشراء.")
        return

    # خصم الرصيد
    remaining = price
    new_balance = balance
    new_credit = credit

    if new_balance >= remaining:
        new_balance -= remaining
        remaining = 0
    else:
        remaining -= new_balance
        new_balance = 0
        new_credit = max(0, new_credit - remaining)

    # تحديث الرصيد في قاعدة البيانات
    cursor.execute(
        "UPDATE users SET balance = ?, credit = ? WHERE username = ?",
        (new_balance, new_credit, username)
    )

    # نقل الحساب إلى جدول المشتريات
    cursor.execute("""
        INSERT INTO purchases (chat_id, email, price, password, purchase_time, account_type)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """, (id, email, price, password, account_type))
    conn.commit()
    # حذف الحساب من جدول الحسابات المتاحة
    cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    conn.commit()
    cursor.execute(
        "SELECT balance, credit, language, referrer_id FROM users WHERE id = ?",
        (id,)
    )
    referrer_id = cursor.fetchone()[3]
    if referrer_id:
        bonus = price * 0.1
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id = ?", (bonus, referrer_id))
        conn.commit()

    await update.message.reply_text(
        f"✅ تم شراء الحساب:\n\n📧 {email}\n🔑 كلمة المرور: {password}\n📩 البريد الاحتياطي: {recovery}\n💰 السعر: {price} ل.س"
    )
@require_not_banned
async def buy_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شراء الحساب المحدد بعد اختيار المستخدم"""
    query = update.callback_query
    user_id = query.message.chat_id
    email = query.data.replace("buy_", "")

    # جلب بيانات الحساب
    cursor.execute("SELECT account_type, price, password, recovery FROM accounts WHERE email = ?", (email,))
    account_data = cursor.fetchone()

    if not account_data:
        await query.answer("❌ الحساب غير متوفر.")
        return

    account_type, price, password, recovery = account_data
    username = context.user_data.get("username_login")
    # جلب بيانات المستخدم
    cursor.execute("SELECT id, balance, credit, language FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if not user_data:
        await query.answer("❌ لم يتم العثور على بيانات حسابك.")
        return

    id,balance, credit, lang = user_data

    # التحقق من الرصيد
    if (balance + credit) < price:
        await query.answer("❌ رصيدك غير كافٍ لإتمام العملية.")
        return

    # خصم المبلغ من الرصيد
    if balance >= price:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (price, username))
    else:
        remaining_price = price - balance
        cursor.execute("UPDATE users SET balance = 0, credit = credit - ? WHERE username = ?", (remaining_price, username))

    # نقل الحساب إلى جدول المشتريات
    cursor.execute("""
        INSERT INTO purchases (chat_id, email, price, password, purchase_time)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (id, email, price, password))
    conn.commit()
    # حذف الحساب من جدول الحسابات المتاحة
    cursor.execute("DELETE FROM accounts WHERE email = ?", (email,))
    conn.commit()

    messages = {
        "ar": f"✅ **تم شراء الايميل بنجاح!**\n\n🔹 **الايميل:** `{email}`\n🔑 **كلمة المرور:** `{password}`\n📩 **البريد الاحتياطي:** `{recovery}`",
        "en": f"✅ **Account purchased successfully!**\n\n🔹 **Email:** `{email}`\n🔑 **Password:** `{password}`\n📩 **Recovery email:** `{recovery}`"
    }

    await query.message.edit_text(messages[lang], parse_mode="Markdown")
@require_not_banned
async def return_to_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context,'ar')
########################################################################################################################
@require_not_banned
async def ask_for_gift_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب إرسال اسم المستخدم والمبلغ لإهداء الرصيد مؤقتاً.
    """
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    # الحصول على لغة المستخدم
    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    lang = row[0] if row else "ar"

    # نظّف أي Handler قديم وحالة انتظار سابقة
    

    # رسالة التعليمات حسب اللغة
    prompts = {
        "ar": (
            "✍️ **أدخل اسم المستخدم والمبلغ المراد إهداؤه بالشكل التالي:**\n\n"
            "`@username 5000`\n\n"
            "💡 **سيتم خصم 1% من المبلغ كرسوم تحويل.**"
        ),
        "en": (
            "✍️ **Enter the username and amount to gift as follows:**\n\n"
            "`@username 5000`\n\n"
            "💡 **1% transfer fee will be deducted from the amount.**"
        )
    }
    context.user_data["current_state"] = 'gift_handler'
    await update.message.reply_text(prompts.get(lang, prompts["ar"]), parse_mode="Markdown")
@require_not_banned
async def process_gift_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة تحويل الرصيد مع خصم 1% رسوم وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    text = update.message.text.strip().split()
    username = context.user_data.get("username_login")
    if len(text) != 2:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: `@username 5000`", parse_mode="Markdown"
        )

    username1, amt_str = text[0].lstrip("@"), text[1]
    try:
        amount = float(amt_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: `@username 5000`", parse_mode="Markdown"
        )

    # جلب بيانات المرسل
    cursor.execute("SELECT id ,balance, language FROM users WHERE username = ?", (username,))
    sender = cursor.fetchone()
    if not sender:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")
    id, sender_balance, lang = sender

    # جلب بيانات المستلم
    cursor.execute("SELECT id FROM users WHERE username = ?", (username1,))
    recipient = cursor.fetchone()
    if not recipient:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ اسم المستخدم غير مسجل.")
    recipient_id = recipient[0]

    fee = amount * 0.01
    total = amount + fee
    if sender_balance < total:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ رصيدك غير كافٍ لإتمام عملية التحويل.")

    # تنفيذ التحويل
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ?",
        (total, sender[0])
    )
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, recipient_id)
    )
    conn.commit()

    # رسائل التأكيد
    confirmations = {
        "ar": f"✅ تم تحويل {amount:.2f} ل.س إلى @{username} بنجاح!\n💸 تم خصم {fee:.2f} ل.س رسوم.",
        "en": f"✅ Successfully transferred {amount:.2f} L.S to @{username}!\n💸 {fee:.2f} L.S was deducted as fee."
    }
    await update.message.reply_text(confirmations.get(lang, confirmations["ar"]), parse_mode="Markdown")

    # إشعار المستلم
    try:
        await context.bot.send_message(
            chat_id=recipient_id,
            text=f"🎁 You have received {amount:.2f} L.S from @{update.effective_user.username}!"
        )
    except:
        pass
    context.user_data.pop("current_state", None)








############################################################################################################################
@require_not_banned
async def get_temp_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء بريد وهمي للمستخدم باستخدام API"""
    user_id = update.effective_chat.id

    headers = {"X-Api-Key": API_KEY}
    response = requests.get(f"{BASE_URL}/create", headers=headers)

    if response.status_code == 200:
        email_data = response.json()
        temp_email = email_data.get("email", "غير متاح")

        # حفظ البريد في بيانات المستخدم
        context.user_data["temp_email"] = temp_email

        await update.message.reply_text(f"✅ **تم إنشاء بريد وهمي لك:**\n📩 `{temp_email}`\n\n"
                                        "🔄 استخدم زر '📬 استلام الرسائل' لعرض الوارد.",
                                        parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ حدث خطأ أثناء إنشاء البريد. حاول مرة أخرى لاحقًا.")
#########################################################################################################3
def match_transaction_id_with_email(transaction_id: str) -> bool:
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

    service = build('gmail', 'v1', credentials=creds)
    query_params = 'newer_than:4d'
    results = service.users().messages().list(userId='me', q=query_params).execute()
    messages = results.get('messages', [])

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload']['headers']
        for header in headers:
            if header['name'] == 'From' and 'Payeer.com' in header['value']:
                snippet = msg['snippet']
                match = re.search(r"ID: (\d+)", snippet)
                if match and match.group(1).strip() == transaction_id:
                    return True
    return False
# ---------- دالة استخراج المبلغ من رقم المعاملة ----------
def get_amount_by_transaction_id(transaction_id: str) -> float:
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
    query_params = 'newer_than:4d'
    results = service.users().messages().list(userId='me', q=query_params).execute()
    messages = results.get('messages', [])

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload']['headers']
        for header in headers:
            if header['name'] == 'From' and 'Payeer.com' in header['value']:
                snippet = msg['snippet']
                id_match = re.search(r"ID: (\d+)", snippet)
                amount_match = re.search(r"Amount: (\d+(\.\d+)?)", snippet)
                if id_match and amount_match and id_match.group(1).strip() == transaction_id:
                    return float(amount_match.group(1))
    return 0.0
# ---------- دالة اختيار وسيلة الدفع ----------
@require_not_banned
async def recharge_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get("username_login")
    # 1. جلب لغة المستخدم
    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    lang = row[0] if row else "ar"

    # 2. بناء العنوان والصفوف حسب اللغة
    if lang == "ar":
        header = "شحن الرصيد:🟥"
        keyboard = [
            [KeyboardButton("سيريتيل كاش –")],
            [KeyboardButton("بايير 🅿 - Payeer")],
            [KeyboardButton("كوين اكس CoinX –")],
            [KeyboardButton("بنك بيمو –🏦")],
            [KeyboardButton("كريبتو 🌐")]
        ]
    else:
        header = "Recharge Balance:🟥"
        keyboard = [
            [KeyboardButton("Syriatel Cash –")],
            [KeyboardButton("Payeer 🅿")],
            [KeyboardButton("CoinX –")],
            [KeyboardButton("Bemo Bank –🏦")],
            [KeyboardButton("Crypto 🌐")]
        ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # 3. إرسال العنوان ثم لوحة الأزرار
    await update.message.reply_text(header)
    await update.message.reply_text(
        "💰 اختر طريقة الدفع:" if lang == "ar" else "💰 Select a payment method:",
        reply_markup=reply_markup
    )
def create_coinx_signature(method, uri, body, timestamp, secret_key):
    to_sign = f"{timestamp}{method.upper()}{uri}{body}"
    return hmac.new(secret_key.encode(), to_sign.encode(), hashlib.sha256).hexdigest()

def get_coinx_deposit_history(access_id, secret_key, transaction_id):
    import hmac
    import hashlib
    import time
    import requests
    from urllib.parse import urlencode

    timestamp = str(int(time.time() * 1000))
    method = "GET"
    uri = "/v2/assets/deposit-history"
    body = ""
    params = {"limit": "100"}
    query_string = "?" + urlencode(params)
    uri_with_query = uri + query_string
    full_url = "https://api.coinex.com" + uri_with_query

    # CoinEx requires latin-1 encoding for signature
    to_sign = f"{method}{uri_with_query}{body}{timestamp}"
    signature = hmac.new(secret_key.encode("latin-1"), to_sign.encode("latin-1"), hashlib.sha256).hexdigest().lower()

    headers = {
        "X-COINEX-KEY": access_id,
        "X-COINEX-SIGN": signature,
        "X-COINEX-TIMESTAMP": timestamp
    }

    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 0:
            deposit_history = data.get("data", [])
            for deposit in deposit_history:
                if deposit.get("tx_id") == transaction_id:
                    return {
                        "found": True,
                        "amount": float(deposit.get("amount", 0)),
                        "currency": deposit.get("currency"),
                        "tx_id": deposit.get("tx_id")
                    }
            return {"found": False}
        else:
            return {"error": data.get("message", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}
@require_not_banned
async def handle_coinx_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    username = context.user_data.get("username_login")
    networks = {
        "trc20": {
            "address": "TX1234567890abcdef",
            "label_ar": "TRC20",
            "label_en": "TRC20"
        },
        "bep20": {
            "address": "0xABCDEF1234567890",
            "label_ar": "BEP20",
            "label_en": "BEP20"
        },
        "coinx": {
            "address": "coinx-wallet-0987",
            "label_ar": "كوين إكس",
            "label_en": "CoinX"
        },
        "assent": {
            "address": "assent-wallet-4567",
            "label_ar": "أسينت",
            "label_en": "Assent"
        }
    }

    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[0] if result else "ar"

    if text not in networks:
        await update.message.reply_text("❌ شبكة غير معروفة.")
        return

    selected = networks[text]
    wallet_address = selected["address"]
    label = selected["label_ar"] if lang == "ar" else selected["label_en"]

    await update.message.reply_text(
        f"📤 الرجاء تحويل المبلغ إلى محفظة {label}:\n`{wallet_address}`\n\n🔢 ثم أرسل رقم المعاملة هنا:",
        parse_mode="Markdown"
    )
@require_not_banned
async def process_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE, network_label: str):
    user_id = update.effective_chat.id
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    print(f"[DEBUG] Received txn ID: {txn_id} from network {network_label}")

    cursor.execute("SELECT id, language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[1] if result else "ar"

    messages = {
        "ar": {
            "confirmed": "✅ تم تأكيد المعاملة بنجاح وشحن رصيدك.",
            "exists": "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في CoinX.",
            "error": "⚠️ حدث خطأ أثناء الاتصال بـ CoinX. حاول مرة أخرى."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists": "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in CoinX.",
            "error": "⚠️ Error connecting to CoinX. Please try again."
        }
    }

    # تحقق إذا المعاملة موجودة مسبقاً
    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    if cursor.fetchone():
        await update.message.reply_text(messages[lang]["exists"])
    else:
        try:
            result = get_coinx_deposit_history(ACCESS_ID, SECRET_KEY, txn_id)

            if result.get("error"):
                await update.message.reply_text(messages[lang]["error"] + "\n" + result["error"])
            elif not result.get("found"):
                await update.message.reply_text(messages[lang]["not_found"])
            else:
                amount = result["amount"]

                # 🟢 1. إدخال المعاملة
                cursor.execute(
                    "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?, ?)",
                    (txn_id, result[0], "CoinX", amount)
                )

                # 🟢 2. زيادة الرصيد في users
                cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE id = ?",
                    (amount, result[0])
                )

                conn.commit()

                # 🟢 3. إرسال رسالة تأكيد
                await update.message.reply_text(messages[lang]["confirmed"] + f"\n💰 {amount} USDT")

        except Exception as e:
            print("[ERROR] CoinX connection error:", str(e))
            await update.message.reply_text(messages[lang]["error"])
@require_not_banned
async def payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_id = update.effective_chat.id
    method = update.message.text.strip()
    username = context.user_data.get("username_login")
    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[0] if result else "ar"

    payment_info = {
        "ar": {
            "سيريتيل كاش": "📌 قم بتحويل المبلغ إلى الرقم: `093XXXXXXX` ثم أرسل إيصال الدفع.",
            "Payeer": "📌 أرسل المبلغ إلى حساب Payeer: `P1092176325`\n\n🔢 **ثم أدخل رقم المعاملة هنا:**",
            "USDT": "📌 استخدم عنوان USDT TRC20: `TX1234567890abcdef` للتحويل ثم أرسل الإيصال.",
            "بيمو": "📌 قم بالتحويل إلى حساب بيمو: `BEMO-56789` ثم أرسل الإيصال.",
            "العودة": "🔙 تم الرجوع إلى القائمة الرئيسية."
        },
        "en": {
            "Syriatel Cash": "📌 Transfer the amount to: `093XXXXXXX` then send the receipt.",
            "Payeer": "📌 Send the amount to Payeer account: `P1092176325`\n\n🔢 **Then enter the Transaction ID here:**",
            "USDT": "📌 Use USDT TRC20 address: `TX1234567890abcdef` for transfer then send the receipt.",
            "Bemo": "📌 Transfer to Bemo account: `BEMO-56789` then send the receipt.",
            "Back": "🔙 Returned to the main menu."
        }
    }

    if method in ["CoinX", "كوين إكس"]:
        context.user_data["current_state"] = 'awaiting_coinx_network'
        keyboard = [
            [KeyboardButton("bep20"), KeyboardButton("trc20")],
            [KeyboardButton("coinx"), KeyboardButton("assent")],
            [KeyboardButton("العودة" if lang == "ar" else "Back")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🔗 اختر شبكة التحويل:" if lang == "ar" else "🔗 Select the transfer network:",
            reply_markup=reply_markup
        )
        return

    if method == "Payeer":
        context.user_data["current_state"] = 'awaiting_payeer_txn'
        await update.message.reply_text(payment_info[lang][method], parse_mode="Markdown")
        return
    if method in ["سيريتيل كاش", "Syriatel Cash"]:
        context.user_data["current_state"] = 'awaiting_syriatel_txn'
        await update.message.reply_text(payment_info[lang][method], parse_mode="Markdown")
        return
    if method in ["بيمو", "Bemo"]:
        bemo_account = "BEMO-56789" 
        context.user_data["current_state"] = 'awaiting_bemo_txn'
        if lang == "ar":
            msg = (
                f"📌 قم بالتحويل إلى رقم الحساب التالي:\n"
                f"`{bemo_account}`\n\n"
                f"📨 ثم أرسل رقم الحوالة والمبلغ في سطرين متتاليين هكذا:\n"
                f"`123456789`\n`50000`\n\n"
                f"⏳ تأكيد العملية يتم يدويًا خلال 6 ساعات."
            )
        else:
            msg = (
                f"📌 Please transfer to the following account:\n"
                f"`{bemo_account}`\n\n"
                f"📨 Then send the transfer number and amount on two lines like this:\n"
                f"`123456789`\n`50000`\n\n"
                f"⏳ Confirmation will be done manually within 6 hours."
            )

        await update.message.reply_text(msg, parse_mode="Markdown")

        return

    if method in payment_info[lang]:
        await update.message.reply_text(payment_info[lang][method], parse_mode="Markdown")
        return

    await update.message.reply_text("❌ طريقة الدفع غير معروفة.")
######################################################################3
@require_not_banned
async def process_bemo_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
   
    user_id = update.effective_chat.id
    message_lines = update.message.text.strip().split("\n")
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    if True:
        if len(message_lines) < 2:
            context.user_data.pop("current_state", None)
            msg = "❌ الرجاء إرسال رقم الحوالة ثم المبلغ في سطرين." if lang == "ar" else "❌ Please send the transfer number and amount in two separate lines."
            await update.message.reply_text(msg)
            return

        txn_id = message_lines[0].strip()
        amount_syp = message_lines[1].strip()

        try:
            amount_syp = float(amount_syp)
        except:
            context.user_data.pop("current_state", None)
            await update.message.reply_text("⚠️ المبلغ غير صحيح." if lang == "ar" else "⚠️ Invalid amount.")
            return

        # تحقق مما إذا كان رقم الحوالة مستخدم سابقاً
        cursor.execute("SELECT user_id, amount, timestamp FROM transactions WHERE txn_id = ?", (txn_id,))
        existing = cursor.fetchone()

        if existing:
            prev_user_id, prev_amount, prev_time = existing
            cursor.execute("SELECT username FROM users WHERE id = ?", (prev_user_id,))
            row = cursor.fetchone()
            prev_username = row[0] if row else "N/A"

            msg = (
                f"⚠️ <b>تم استلام حوالة برقم مكرر</b>\n\n"
                f"🔁 رقم الحوالة: <code>{txn_id}</code>\n"
                f"💰 مبلغ الحوالة: <b>{prev_amount}</b> USD\n"
                f"📅 التاريخ: <i>{prev_time}</i>\n\n"
                f"👤 تم شحنها سابقًا للمستخدم:\n"
                f"<code>{prev_username}</code> (ID: <code>{prev_user_id}</code>)\n\n"
                f"🔔 تمت محاولة استخدامها مجددًا من قبل:\n"
                f"<code>{username}</code> (ID: <code>{user_id}</code>)"
            )

            await context.bot.send_message(chat_id=ADMIN_ID1, text=msg, parse_mode="HTML")

            warn_msg = "⚠️ رقم الحوالة تم استخدامه مسبقاً، وسيتم مراجعته من الإدارة." if lang == "ar" else \
                    "⚠️ This transfer number was used before. The admin will review it."

            await update.message.reply_text(warn_msg)
            context.user_data.pop("current_state", None)
            return

        # رقم الحساب المستلم للحوالة
        bemo_account = "BEMO-56789"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأكيد", callback_data=f"bemo_accept_{username}_{txn_id}_{amount_syp}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"bemo_reject_{username}_{txn_id}")
            ]
        ])

        msg = (
            f"📥 <b>طلب شحن عبر بيمو</b>\n\n"
            f"👤 المستخدم: <code>{username}</code> (ID: <code>{user_id}</code>)\n"
            f"📤 الحساب المحوَّل إليه: <b>{bemo_account}</b>\n"
            f"🔢 رقم الحوالة: <code>{txn_id}</code>\n"
            f"💰 المبلغ: <b>{amount_syp:.0f}</b> SYP\n\n"
            f"🕐 بانتظار مراجعة الإدارة..."
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID1,
            text=msg,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        notify_user = "✅ تم إرسال تفاصيل الحوالة إلى الإدارة.\n⏳ سيتم مراجعتها خلال 6 ساعات." if lang == "ar" \
            else "✅ Transfer details sent to the admin.\n⏳ Expect confirmation within 6 hours."

        await update.message.reply_text(notify_user)
        context.user_data.pop("current_state", None)
@require_not_banned
async def bemo_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, username, txn_id, amount_syp = query.data.split("_", 4)
    username = username
    amount_syp = float(amount_syp)

    # تحويل من SYP إلى USD
    cursor.execute("SELECT rate FROM currency_rates WHERE currency = 'SYP'")
    rate_row = cursor.fetchone()
    if not rate_row:
        await query.edit_message_text("⚠️ لم يتم العثور على سعر صرف.")
        return

    rate = float(rate_row[0])
    amount_usd = round(amount_syp / rate, 2)
    cursor.execute("SELECT id,chat_id FROM users WHERE username = ?",(username,))
    result = cursor.fetchone()
    # تحديث الرصيد
    cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount_usd, username))
    cursor.execute("INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?, ?)", (txn_id, result[0], "Bemo", amount_usd))
    conn.commit()

    await context.bot.send_message(result[1], f"✅ تم تأكيد المعاملة عبر بيمو.\n💰 تم شحن رصيدك: {amount_usd} USD")
    await query.edit_message_text("✅ تم شحن الرصيد بنجاح.")
@require_not_banned
async def bemo_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, username, txn_id = query.data.split("_", 3)
    cursor.execute("SELECT id,chat_id FROM users WHERE username = ?",(username,))
    result = cursor.fetchone()
    await context.bot.send_message(result[1], f"❌ لم يتم العثور على حوالة بيمو بالرقم: {txn_id}.")
    await query.edit_message_text("❌ تم رفض المعاملة.")

################################################################################################33
@require_not_banned
async def process_payeer_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    cursor.execute("SELECT id,language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[1] if result else "ar"
    messages = {
        "ar": {
            "confirmed": "✅ تم تأكيد الدفع وشحن رصيدك.",
            "exists": "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في Gmail.",
            "error": "⚠️ حدث خطأ أثناء التحقق من Gmail."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists": "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Gmail.",
            "error": "⚠️ Error while checking Gmail for transaction."
        }
    }

    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    if cursor.fetchone():
        await update.message.reply_text(messages[lang]["exists"])
    else:
        try:
            payeer_data = get_recent_payeer_transactions()
            amount = payeer_data.get(txn_id)

            if amount:
                cursor.execute(
                    "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?,  ?)",
                    (txn_id, result[0], "Payeer", float(amount))
                )
                cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE id = ?",
                    (float(amount), result[0])
                )
                conn.commit()
                await update.message.reply_text(messages[lang]["confirmed"] + f"\n💰 {amount} USD")
            else:
                await update.message.reply_text(messages[lang]["not_found"])
        except Exception as e:
            print("[ERROR] Gmail Payeer Check:", str(e))
            await update.message.reply_text(messages[lang]["error"])

    context.user_data.pop("current_state", None)
@require_not_banned
async def process_syriatel_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    cursor.execute("SELECT id, language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[1] if result else "ar"

    messages = {
        "ar": {
            "confirmed": "✅ تم تأكيد المعاملة وشحن رصيدك.",
            "exists": "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم العملية في Gmail.",
            "rate_error": "⚠️ لم يتم العثور على سعر الصرف.",
            "error": "⚠️ حدث خطأ أثناء التحقق من Gmail."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists": "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Gmail.",
            "rate_error": "⚠️ Exchange rate not found.",
            "error": "⚠️ Error while checking Gmail."
        }
    }

    # التحقق من التكرار
    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    if cursor.fetchone():
        await update.message.reply_text(messages[lang]["exists"])
        return

    try:
        transactions = get_recent_syriatel_transactions()
        amount_syp = transactions.get(txn_id)

        if not amount_syp:
            await update.message.reply_text(messages[lang]["not_found"])
            context.user_data.pop("current_state", None)
            return

        cursor.execute("SELECT rate FROM currency_rates WHERE currency = 'SYP'")
        rate_row = cursor.fetchone()

        if not rate_row:
            await update.message.reply_text(messages[lang]["rate_error"])
            context.user_data.pop("current_state", None)
            return

        rate = float(rate_row[0])
        amount_usd = round(float(amount_syp) / rate, 2)

        # تحديث الرصيد
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_usd, result[0]))
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?,  ?)",
            (txn_id, result[0], "Syriatel Cash", amount_usd)
        )
        conn.commit()

        await update.message.reply_text(messages[lang]["confirmed"] + f"\n💰 {amount_usd} USD")

    except Exception as e:
        print("[ERROR Syriatel]", str(e))
        await update.message.reply_text(messages[lang]["error"])

    context.user_data.pop("current_state", None)

@require_not_banned
async def process_payeer_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    cursor.execute("SELECT id,language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    lang = result[1] if result else "ar"

    messages = {
        "ar": {
            "confirmed": "✅ تم تأكيد الدفع وشحن رصيدك.",
            "exists": "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في Payeer.",
            "error": "⚠️ حدث خطأ أثناء الاتصال بـ Payeer."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists": "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Payeer.",
            "error": "⚠️ Error while contacting Payeer API."
        }
    }

    # تحقق من التكرار
    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    if cursor.fetchone():
        await update.message.reply_text(messages[lang]["exists"])
        context.user_data.pop("current_state", None)
        return

    try:
        payeer = PayeerAPI(account="PXXXXXX", api_id="YOUR_API_ID", api_pass="YOUR_API_PASS")
        history = payeer.get_history_info("0")  # جلب كل المعاملات

        if history.get("history"):
            for _id, txn in history["history"].items():
                if txn.get("id") == txn_id and txn.get("type") == "in":
                    amount = float(txn.get("credited", 0))
                    cursor.execute(
                        "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?, ?)",
                        (txn_id, result[0], "Payeer", amount)
                    )
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, result[0]))
                    conn.commit()
                    await update.message.reply_text(messages[lang]["confirmed"] + f"\n💰 {amount} USD")
                    context.user_data.pop("current_state", None)
                    break
            else:
                await update.message.reply_text(messages[lang]["not_found"])
        else:
            await update.message.reply_text(messages[lang]["not_found"])

    except Exception as e:
        print("[ERROR] Payeer API Check:", str(e))
        await update.message.reply_text(messages[lang]["error"])

    context.user_data.pop("current_state", None)

###############################################################################################3
@require_not_banned
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_purchase")
    if not pending:
        await update.message.reply_text("❌ لا توجد عملية شراء معلقة.")
        return

    quantity = pending["quantity"]
    account_type = pending["account_type"]
    total_price = pending["total_price"]
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    cursor.execute(
        "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    if not result:
        await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")
        return
    id,balance, credit, lang, referrer_id = result
    # التأكد من أن مجموع الرصيدين كافٍ لتغطية قيمة الشراء
    if (balance + credit) < total_price:
        await update.message.reply_text("❌ رصيدك غير كافٍ لإتمام العملية.")
        return

    # خصم المبلغ من رصيد الشحن أولاً، ثم استخدام رصيد الإحالة إذا لزم الأمر
    remaining = total_price
    new_balance = balance
    new_credit = credit

    if new_balance >= remaining:
        new_balance -= remaining
        remaining = 0
    else:
        remaining -= new_balance
        new_balance = 0
        new_credit = max(0, new_credit - remaining)
    
    cursor.execute(
        "UPDATE users SET balance = ?, credit = ? WHERE id = ?",
        (new_balance, new_credit, id)
    )
    cursor.execute(
        "SELECT id, email, password, recovery FROM accounts WHERE account_type = ? LIMIT ?",
        (account_type, quantity)
    )
    accounts = cursor.fetchall()
    if len(accounts) < quantity:
        await update.message.reply_text("❌ عفواً، الحسابات المطلوبة لم تعد متوفرة.")
        return

    purchase_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    purchase_message = "✅ تم الشراء بنجاح!\n\n"
    for acc in accounts:
        acc_id, email, password, recovery = acc
        cursor.execute(
            "INSERT INTO purchases (chat_id, email, price, password, purchase_time,account_type) VALUES (?, ?, ?, ?, ?,?)",
            (id, email, total_price/quantity, password, purchase_time,account_type)
        )
        cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
        purchase_message += f"✅ 🔹 الايميل: {email}\n🔑 كلمة المرور: {password}\n📩 الايميل الاحتياطي: {recovery}\n\n"

    conn.commit()

    # إضافة 8% إلى رصيد الإحالة للداعي (إذا كان موجودًا)
    if referrer_id:
        bonus = total_price * 0.1
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id = ?", (bonus, referrer_id))
        conn.commit()

    context.user_data.pop("pending_purchase", None)
    await update.message.reply_text(purchase_message)
    await main_menu(update, context,lang)
@require_not_banned
async def cancel_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_purchase" in context.user_data:
        context.user_data.pop("pending_purchase", None)
        await update.message.reply_text("❌ تم إلغاء عملية الشراء.")
        await main_menu(update, context)
    else:
        await update.message.reply_text("❌ لا توجد عملية شراء لإلغائها.")
        await main_menu(update, context,'ar')
#################################################################################################
@require_not_banned
async def show_retrieve_menu(update, context):
    keyboard = [[InlineKeyboardButton("📋 عرض الحسابات", switch_inline_query_current_chat="")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("⬇️ اضغط على الزر لعرض الحسابات القابلة للاسترجاع:", reply_markup=reply_markup)
@require_not_banned
async def show_retrieve_menu1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب عنوان البريد المطلوب استرجاعه مؤقتاً من المستخدم.
    """
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    prompt = (
        "✍️ أرسل البريد الإلكتروني الذي تريد استرجاعه:"
        if lang == "ar"
        else "✍️ Send the email address you want to recover:"
    )
    await update.message.reply_text(prompt)
    context.user_data["current_state"] = 'retrieve_handler'
@require_not_banned
async def process_retrieve_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة طلب استرجاع البريد وإنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    email = update.message.text.strip()
    
    cursor.execute(
        "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    # جلب بيانات الشراء
    cursor.execute("""
        SELECT id, account_type, purchase_time, refund_requested
        FROM purchases
        WHERE email = ? AND chat_id = ?
    """, (email, result[0]))
    row = cursor.fetchone()

    if not row:
        msg = (
            "❌ لم يتم العثور على هذا البريد في مشترياتك."
            if lang == "ar"
            else "❌ This email was not found in your purchases."
        )
    else:
        purchase_id, acct_type, purchase_time, refunded = row
        if refunded:
            msg = (
                "⚠️ تم تقديم طلب استرجاع مسبقاً لهذا الحساب."
                if lang == "ar"
                else "⚠️ Refund request has already been submitted."
            )
        else:
            try:
                dt = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
            except:
                msg = (
                    "❌ خطأ في بيانات وقت الشراء."
                    if lang == "ar"
                    else "❌ Purchase time format error."
                )
                await update.message.reply_text(msg)
                context.user_data.pop("current_state", None)
                return

            allowed = 3 if acct_type == "G1" else 1
            if (datetime.now() - dt).days >= allowed:
                msg = (
                    "⏳ انتهت المدة المسموح بها للاسترجاع."
                    if lang == "ar"
                    else "⏳ Refund period has expired."
                )
            else:
                # علّم طلب الاسترجاع
                cursor.execute(
                    "UPDATE purchases SET refund_requested = 1 WHERE id = ?",
                    (purchase_id,)
                )
                conn.commit()
                msg = (
                    "♻️ تم تقديم طلب الاسترجاع بنجاح!"
                    if lang == "ar"
                    else "♻️ Refund request submitted successfully!"
                )
                # أرسل للأدمن أزرار القبول/الرفض
                kb = [
                    [InlineKeyboardButton(f"✅ قبول {email}", callback_data=f"accept_refund_{username}_{purchase_id}_{email}")],
                    [InlineKeyboardButton(f"❌ رفض {email}", callback_data=f"reject_refund_{username}_{email}")]
                ]
                await context.bot.send_message(
                    chat_id=ADMIN_ID1,
                    text=(
                        "🔔 طلب استرجاع حساب\n"
                        f"👤 المستخدم: {user_id}\n"
                        f"📧 البريد: {email}"
                    ),
                    reply_markup=InlineKeyboardMarkup(kb)
                )

    await update.message.reply_text(msg)
    context.user_data.pop("current_state", None)
@require_not_banned
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query
    query_text = query.query.strip()
    user_id = query.from_user.id
    now = datetime.now()

    results = []
    print(query_text)
    if query_text.startswith("buy_1_"):
        selected_type = query_text.replace("buy_1_", "").strip()
        cursor.execute("SELECT email, price FROM accounts WHERE account_type = ?", (selected_type,))
        accounts = cursor.fetchall()[:50]
       
        if not accounts:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ لا يوجد حسابات متاحة",
                    input_message_content=InputTextMessageContent("❌ لا يوجد حسابات حالياً.")
                )
            )
        else:
            for email, price in accounts:
                hidden_email = email.split("@")[0][:-4] + "****"
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"{hidden_email} - {price} ل.س ({selected_type})",
                        input_message_content=InputTextMessageContent(f"/buy_account {email}")
                    )
                )

    elif query_text == "":
        username = context.user_data.get("username_login")
        cursor.execute(
            "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
            (username,)
        )
        result = cursor.fetchone()
        cursor.execute("""
            SELECT id, account_type, email, purchase_time, refund_requested
            FROM purchases 
            WHERE chat_id = ?  
        """, (result[0],))
        purchases = cursor.fetchall()
        print(purchases)
        for acc_id, account_type, email, purchase_time, requested in purchases:
            print(requested)
            if int(requested) == 1:
                continue

            # ✅ تجاوز المدة المسموحة؟ تجاهله
            purchase_dt = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
            period = 3 if account_type == "G1" else 1
            print((now - purchase_dt).days >= period)
            if (now - purchase_dt).days >= period:
                continue

            # ✅ اختبار حالة Gmail إن وجد
            if email.endswith("@gmail.com"):
                if not await check_gmail_account(email):
                    continue  # لا نعرض الحساب النشط

            # ✅ إضافته لقائمة النتائج
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"♻️ استرجاع {email}",
                    input_message_content=InputTextMessageContent(f"/request_refund {acc_id} {email}")
                )
            )
        if not results:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ لا يوجد حسابات مؤهلة للاسترجاع",
                    input_message_content=InputTextMessageContent("❌ لا يوجد لديك حسابات قابلة للاسترجاع.")
                )
            )

    # ✅ تجاهل أي شيء آخر
    else:
        return

    await update.inline_query.answer(results[:50], cache_time=0)


# ✅ تنفيذ طلب الاسترجاع فور اختيار الحساب
@require_not_banned
async def request_refund(update: Update, context: CallbackContext):
    """إرسال طلب استرجاع الحساب إلى الأدمن"""
    
    message_text = update.message.text.strip()
    print(message_text)
    username = context.user_data.get("username_login")
    if message_text.startswith("/request_refund"):
        _, acc_id, email = message_text.split(" ")
        print(email)
        user_id = update.message.chat_id
        
        cursor.execute(
            "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
            (username,)
        )
        result = cursor.fetchone()
        # ✅ منع تكرار الطلب لنفس الحساب
        cursor.execute("SELECT refund_requested FROM purchases WHERE email = ? AND chat_id = ?", (email, result[0]))
        result = cursor.fetchone()
        
        if not result:
            await update.message.reply_text(f"❌ الحساب غير موجود.")
            return

        if result[0] == 1:  # إذا كان `refund_requested` = 1، يعني أنه طلب بالفعل.
            await update.message.reply_text(f"⚠️ لقد قمت بالفعل بإرسال طلب استرجاع لهذا الحساب: {email}.")
            return

        # ✅ تحديث حالة `refund_requested` إلى 1
        cursor.execute("UPDATE purchases SET refund_requested = 1 WHERE email = ? AND chat_id = ?", (email, result[0]))
        conn.commit()

        # ✅ إرسال الطلب إلى الأدمن مع أزرار الرد
        keyboard = [
            [InlineKeyboardButton(f"✅ قبول {email}", callback_data=f"accept_refund_{username}_{acc_id}_{email}")],
            [InlineKeyboardButton(f"❌ رفض {email}", callback_data=f"reject_refund_{username}_{email}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=ADMIN_ID1,
            text=f"🔔 **طلب استرجاع حساب**\n\n👤 **المستخدم:** {username}\n📧 **البريد:** {email}\n📌 **هل تريد قبول الطلب؟**",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        await update.message.reply_text(f"📩 تم إرسال طلب الاسترجاع إلى الإدارة للمراجعة.")

# ✅ التحقق مما إذا كان حساب Gmail مغلقًا أو غير نشط باستخدام API

async def check_gmail_account(email):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    }

    data = {
        "mails": [email],
        "mailtype": 0,
        "token": GMAIL_CHECK_API_TOKEN
    }

    try:
        response = requests.post(GMAIL_CHECK_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if result["status"] == "success":
                if email in result["goodlist"]:
                    return False  # الحساب لا يزال يعمل
                if email in result["badlist"]:
                    return True  # الحساب غير نشط أو محذوف
        print("⚠️ خطأ في API:", result.get("message", "غير معروف"))
    except Exception as e:
        print(f"⚠️ خطأ أثناء الاتصال بـ Gmail Check API: {e}")

    return False

# ✅ قبول طلب الاسترجاع
@require_not_banned
async def accept_refund(update: Update, context: CallbackContext):
    query = update.callback_query
    
    await query.answer()
    data = query.data.split("_")
    print(data)
    username = data[2]
    email = data[4]
    cursor.execute(
        "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    cursor.execute("SELECT email, password, recovery, price FROM purchases WHERE email = ? AND chat_id = ?", (email, result[0]))
    account_info = cursor.fetchone()
    print("account_info = ", account_info)
    if not account_info:
        await query.message.edit_text(f"❌ الحساب {email} غير موجود أو تم استرجاعه بالفعل.")
        return

    email = account_info[0]
    password = account_info[1]
    recovery = account_info[2]
    price = account_info[3]
    cursor.execute("SELECT balance FROM users WHERE id = ?", (result[0],))
    user_data = cursor.fetchone()

    if user_data:
        current_balance = user_data[0] or 0.0
        new_balance = current_balance + price
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, result[0]))
    else:
        # إنشاء مستخدم جديد إذا ما كان موجود (اختياري حسب منطقك)
        cursor.execute("INSERT INTO users (chat_id, balance) VALUES (?, ?)", (user_id, price))
    cursor.execute(
        "SELECT chat_id FROM users WHERE username = ?",
        (username,)
    )
    user_id =cursor.fetchone()[0]
    # ✅ إرسال البيانات إلى المستخدم
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ **تم قبول طلب استرجاع الحساب**\n\n📧 **البريد:** {email}\n🔑 **كلمة المرور:** {password}\n📩 **البريد الاحتياطي:** {recovery}\n💰 **السعر:** {price:.2f} ل.س"
    )
    cursor.execute("""
        INSERT INTO refunded_accounts (chat_id, email, password, recovery, price, refund_time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (result[0], email, password, recovery, price, datetime.now()))

    conn.commit()
    # ✅ حذف الحساب من الجدول
    cursor.execute("DELETE FROM purchases WHERE email = ? AND chat_id = ?", (email, result[0]))
    conn.commit()

    await query.message.edit_text(f"🔔 **تم قبول طلب الاسترجاع للحساب:** {email}.")
# ✅ رفض طلب الاسترجاع
@require_not_banned
async def reject_refund(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    username = data[2]
    email = data[3]
    cursor.execute(
        "SELECT id,balance, credit, language, referrer_id FROM users WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    # ✅ تحديث `refund_requested` إلى 0 ليتمكن المستخدم من طلب الاسترجاع مرة أخرى لاحقًا
    cursor.execute("UPDATE purchases SET refund_requested = 0 WHERE email = ? AND chat_id = ?", (email, result[0]))
    conn.commit()
    cursor.execute(
        "SELECT chat_id FROM users WHERE username = ?",
        (username,)
    )
    user_id =cursor.fetchone()[0]
    await context.bot.send_message(chat_id=user_id, text=f"❌ **تم رفض طلب استرجاع الحساب:** {email}.\n\n⚠️ الحساب لا يزال يعمل.")
    await query.message.edit_text(f"🔔 **تم رفض طلب الاسترجاع للحساب:** {email}.")
#######################################################3
@require_not_banned
async def show_about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    lang = get_user_language(user_id)

    if lang == "ar":
        keyboard = [
            [KeyboardButton("📄 الأسئلة الشائعة"), KeyboardButton("📞 تواصل مع الدعم")],
            [KeyboardButton("العودة")]
        ]
        text = "ℹ️ اختر أحد الخيارات:"
    else:
        keyboard = [
            [KeyboardButton("📄 FAQ"), KeyboardButton("📞 Contact Support")],
            [KeyboardButton("Back")]
        ]
        text = "ℹ️ Please choose an option:"

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)
@require_not_banned
async def contact_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    lang = get_user_language(user_id)

    admin_username = "A5K68R"  # بدون @
    url = f"https://t.me/{admin_username}"  # ✅ الآمن والأفضل

    if lang == "ar":
        text = "👤 للتواصل مع الدعم اضغط على الزر أدناه:"
        button_text = "💬 تواصل مع الأدمن"
    else:
        text = "👤 To contact support, click the button below:"
        button_text = "💬 Contact Admin"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(button_text, url=url)]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)
@require_not_banned
async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    lang = get_user_language(user_id)

    if lang == "ar":
        faq_text = (
            "📄 *الأسئلة الشائعة:*\n\n"
            "❓ *ما هي فائدة البوت؟*\n"
            "✅ يساعدك البوت على شراء حسابات وخدمات وإدارة طلباتك بسهولة.\n\n"
            "❓ *ما هو عمل البوت؟*\n"
            "✅ يعرض أنواع حسابات متاحة للشراء، ويتيح لك تقديم طلبات فك، استرجاع أو دعم فني.\n\n"
            "❓ *هل يمكن استرجاع الرصيد؟*\n"
            "✅ نعم، إذا لم يتم تنفيذ الخدمة أو واجهت مشكلة يمكن طلب استرجاع خلال فترة محددة.\n\n"
            "❓ *كيف أتواصل مع الدعم؟*\n"
            "✅ من خلال زر \"📞 تواصل مع الدعم\" في القائمة الرئيسية."
        )
    else:
        faq_text = (
            "📄 *Frequently Asked Questions:*\n\n"
            "❓ *What is the benefit of the bot?*\n"
            "✅ The bot helps you purchase accounts and manage your requests easily.\n\n"
            "❓ *What does the bot do?*\n"
            "✅ It shows available account types for purchase, and allows refund, unlock, or support requests.\n\n"
            "❓ *Can I get a refund?*\n"
            "✅ Yes, if the service wasn't delivered or you faced an issue, you can request a refund within a limited time.\n\n"
            "❓ *How do I contact support?*\n"
            "✅ Just press \"📞 Contact Support\" from the main menu."
        )

    await update.message.reply_text(faq_text, parse_mode="Markdown")

#################################################################################################3
def random_username(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
def get_domain():
    res = requests.get(f"{BASE_URL}/domains")
    res.raise_for_status()
    domains = res.json()["hydra:member"]
    return domains[0]["domain"]

def create_account(email, password):
    payload = {"address": email, "password": password}
    res = requests.post(f"{BASE_URL}/accounts", json=payload)
    if res.status_code != 201 and res.status_code != 422:
        res.raise_for_status()
def get_token(email, password):
    payload = {"address": email, "password": password}
    res = requests.post(f"{BASE_URL}/token", json=payload)
    res.raise_for_status()
    return res.json()["token"]

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{BASE_URL}/messages", headers=headers)
    res.raise_for_status()
    return res.json()["hydra:member"]
def get_message_details(token, message_id):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{BASE_URL}/messages/{message_id}", headers=headers)
    res.raise_for_status()
    return res.json()
@require_not_banned
async def create_temp_mail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id

    username = random_username()
    domain = get_domain()
    email = f"{username}@{domain}"

    create_account(email, TEMP_MAIL_PASSWORD)
    token = get_token(email, TEMP_MAIL_PASSWORD)

    context.user_data['temp_mail_token'] = token
    context.user_data['temp_mail_email'] = email

    await update.message.reply_text(
    f"📧 تم إنشاء بريد وهمي لك: {email}\n\n"
    f"⏳ مدة صلاحية البريد: ساعتان\n"
    f"📭 جميع الرسائل التي تصلك على هذا البريد ستظهر هنا تلقائيًا"
    )
    # Start monitoring the inbox
    asyncio.create_task(monitor_inbox(update, context, token))
@require_not_banned
async def monitor_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    user_id = update.effective_chat.id
    checked_ids = set()

    for _ in range(60):  # Check for 60 iterations (≈ 5-10 min)
        await asyncio.sleep(5)
        try:
            messages = get_messages(token)
            for msg in messages:
                if msg["id"] in checked_ids:
                    continue
                checked_ids.add(msg["id"])
                full_msg = get_message_details(token, msg["id"])
                sender = full_msg["from"]["address"]
                subject = full_msg.get("subject", "(No Subject)")
                body = full_msg.get("text", "(No Content)")

                content = f"📥 *وصلتك رسالة جديدة:*👤 *من:* `{sender}`📝 *العنوان:* `{subject}`📨 *المحتوى:*\n{body}"

                await context.bot.send_message(chat_id=user_id, text=content, parse_mode="Markdown")
                return  # Stop after first message is delivered

        except Exception as e:
            print(f"❌ خطأ أثناء فحص البريد: {e}")
            break
########################################################################################################
@require_not_banned
async def request_emails_for_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    context.user_data["current_state"] = 'gmail_check_handler'

    await update.message.reply_text("✍️ أرسل الإيميلات التي تريد فحصها، كل إيميل في سطر منفصل:")
import aiohttp
async def check_gmail_account_async(email: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    data = {
        "mails": [email],
        "mailtype": 0,
        "token": GMAIL_CHECK_API_TOKEN
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GMAIL_CHECK_API_URL, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("status") == "success":
                        if email in result.get("goodlist", []):
                            return f"✅ {email} لا يزال يعمل"
                        elif email in result.get("badlist", []):
                            return f"❌ {email} غير نشط أو محذوف"
                        else:
                            return f"⚠️ {email}: غير معروف الحالة"
                    else:
                        return f"⚠️ API Error: {result.get('message', 'غير معروف')}"
    except Exception as e:
        return f"⚠️ خطأ في الاتصال بـ API: {str(e)}"

    return f"⚠️ {email}: لم يتم التحقق"
@require_not_banned
async def process_email_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    emails = update.message.text.strip().split("\n")
    results = []

    for email in emails:
        email = email.strip()
        if email:
            result = await check_gmail_account_async(email)
            results.append(result)

    context.user_data.pop("current_state", None)
    await update.message.reply_text("\n".join(results))
#########################################################################
@require_not_banned
async def unlock_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = context.user_data.get("username_login")

    try:
        # 1. جلب لغة المستخدم
        cursor.execute(
            "SELECT language FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        lang = row[0] if row else "ar"

        # 2. جلب الأسعار
        cursor.execute("""
            SELECT type, price
            FROM unlock_prices
            WHERE type IN ('gmail', 'hotmail', 'outlook')
        """)
        prices = {t: p for t, p in cursor.fetchall()}
        gmail_price = prices.get('gmail', 0.0)
        hotmail_price = prices.get('hotmail', 0.0)
        outlook_price = prices.get('outlook', 0.0)

        # 3. إعداد الرسالة والأزرار
        if lang == "ar":
            msg = (
                "فك قفل ايميل: 🟥\n"
                f" 🅶 Gmail: {gmail_price} دولار\n"
                f" 🅷 Hotmail: {hotmail_price} دولار\n"
                f" 🅾 Outlook: {outlook_price} دولار"
            )
            gmail_btn = "Gmail"
            hot_btn   = "Hotmail"
            out_btn   = "Outlook"
            back_btn  = "العودة – ↩"
        else:
            msg = (
                "Unlock Email: 🟥\n"
                f" 🅶 Gmail: ${gmail_price}\n"
                f" 🅷 Hotmail: ${hotmail_price}\n"
                f" 🅾 Outlook: ${outlook_price}"
            )
            gmail_btn = "Gmail"
            hot_btn   = "Hotmail"
            out_btn   = "Outlook"
            back_btn  = "Back – ↩"

        # 4. بناء لوحة الأزرار (من دون أسعار)
        keyboard = [
            [KeyboardButton(gmail_btn)],
            [KeyboardButton(hot_btn)],
            [KeyboardButton(out_btn)],
            [KeyboardButton(back_btn)],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        # 5. إرسال الرسالة مع الأزرار
        await update.message.reply_text(msg, reply_markup=reply_markup)

    except Forbidden:
        # المستخدم حظر البوت
        print(f"⚠️ المستخدم {user_id} حظر البوت.")
    except Exception as e:
        # أي خطأ آخر في التنفيذ
        print(f"❌ خطأ داخلي عند فك القفل: {e}")
        await update.message.reply_text("🚫 حدث خطأ، حاول مرة أخرى لاحقًا.")

def get_user_balance(username):
    cursor.execute("SELECT balance,credit FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    return result[0] ,result[1]
def get_user_language(username):
    cursor.execute("SELECT language FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    return result[0] if result else "ar"

# === اختيار نوع الحساب للفك ===
@require_not_banned
async def unlock_account_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    استقبال نوع الحساب المطلوب فكه مؤقتاً ثم الانتظار لإدخال البريد وكلمة المرور.
    """
    user_id = update.effective_chat.id
    context.user_data["current_state"] = 'unlock_handler'
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    messages = {
        "ar": (
            "✉️ الرجاء اختيار نوع البريد الإلكتروني:\n"
            "1️⃣ Gmail\n"
            "2️⃣ Hotmail\n"
            "3️⃣ Outlook"
        ),
        "en": (
            "✉️ Please choose the email type:\n"
            "1️⃣ Gmail\n"
            "2️⃣ Hotmail\n"
            "3️⃣ Outlook"
        )
    }
    account_type = update.message.text.strip().lower()
    if account_type not in ("gmail", "hotmail", "outlook"):
        return  await update.message.reply_text(messages.get(lang, messages["ar"]))


    # رسالة التعليمات حسب اللغة
    
    prompt = (
        "✉️ أرسل البريد وكلمة المرور في سطرين:\n\nexample@gmail.com\nmypassword123"
        if lang == "ar"
        else "✉️ Please send email and password on two lines:\n\nexample@gmail.com\nmypassword123"
    )
    await update.message.reply_text(prompt)
@require_not_banned
async def process_unlock_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة بيانات فك الحساب وإرسال طلب للمشرف ثم إنهاء حالة الانتظار.
    """
    user_id = update.effective_chat.id
    parts = update.message.text.strip().split("\n")
    username = context.user_data.get("username_login")
    if len(parts) != 2:
        lang = get_user_language(username)
        err = (
            "❌ الرجاء إرسال البريد وكلمة المرور كل في سطر منفصل."
            if lang == "ar"
            else "❌ Please send email and password on separate lines."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(err)

    email, password = parts[0].strip(), parts[1].strip()
    acct_type = context.user_data.get("unlock_type", "gmail")
    balance, credit = get_user_balance(username)
    cursor.execute("SELECT price FROM unlock_prices WHERE type = ?", (acct_type,))
    row = cursor.fetchone()
    price = row[0] if row else 0.0

    lang = get_user_language(username)
    if balance + credit < price:
        msg = (
            "❌ رصيدك غير كافٍ لإتمام العملية."
            if lang == "ar"
            else "❌ Insufficient balance to complete the operation."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    # أرسل تأكيد الاستلام
    wait = (
        "⌛️ تم استلام طلبك. يرجى انتظار مراجعة الإدارة..."
        if lang == "ar"
        else "⌛️ Your request has been received. Please wait for admin review..."
    )
    await update.message.reply_text(wait)

    # إعداد الرسالة للمشرف مع أزرار التأكيد/الرفض
    username_part = update.effective_user.username or str(user_id)
    kb = [
        [
            InlineKeyboardButton("✅ تأكيد فك الحساب",
                                 callback_data=f"unlock_confirm_{username}_{acct_type}_{email}"),
            InlineKeyboardButton("❌ رفض الطلب",
                                 callback_data=f"unlock_reject_{username}_{acct_type}_{email}")
        ]
    ]
    admin_msg = (
        f"🔔 طلب فك حساب جديد\n\n"
        f"👤 المستخدم: @{username} (ID: {user_id})\n"
        f"📧 الإيميل: `{email}`\n"
        f"🔑 كلمة المرور: `{password}`\n"
        f"📦 النوع: {acct_type.title()}\n"
        f"💰 السعر: {price}"
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID1,
        text=admin_msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    context.user_data.pop("current_state", None)








# === عند ضغط الأدمن "تأكيد" ===
@require_not_banned
async def handle_unlock_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        print(query.data.split("_", 4))
        _, _, username, account_type, email = query.data.split("_", 4)
        
        

        cursor.execute("SELECT price FROM unlock_prices WHERE type = ?", (account_type,))
        try:
            price = cursor.fetchone()[0]
            if not price:
                price = 0
        except:
            price = 0
        cursor.execute("SELECT chat_id, balance FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            await query.edit_message_text("❌ المستخدم غير موجود.")
            return

        balance = row[1]
        if balance < price:
            await query.edit_message_text("❌ الرصيد غير كافٍ.")
            await context.bot.send_message(chat_id=row[0], text="❌ لم يتم تنفيذ الطلب بسبب نقص الرصيد.")
            return

        new_balance = balance - price
        cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
        conn.commit()
        lang = get_user_language(username)
        msg = (
            f"✅ تم تأكيد عملية فك الحساب بنجاح للإيميل: {email}"
            if lang == "ar"
            else f"✅ Unlock process confirmed successfully for: {email}"
        )
        await context.bot.send_message(chat_id=row[0], text=msg)
        await query.edit_message_text(f"✅ تم تأكيد الطلب وخصم {price}$ من المستخدم.")
    except Exception as e:
        await query.edit_message_text(f"⚠️ خطأ: {e}")

# === عند ضغط الأدمن "رفض" ===
@require_not_banned
async def handle_unlock_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, _, username, email = query.data.split("_", 3)
        lang = get_user_language(username)

        msg = (
            f"❌ تم رفض طلب فك الحساب للإيميل: {email}.\nيرجى التأكد من البيانات أو التواصل مع الإدارة."
            if lang == "ar"
            else f"❌ Your unlock request for {email} was rejected.\nPlease check your data or contact support."
        )
        cursor.execute("SELECT chat_id, balance FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        await context.bot.send_message(chat_id=row[0], text=msg)
        await query.edit_message_text("❌ تم رفض الطلب.")
    except Exception as e:
        await query.edit_message_text(f"⚠️ خطأ: {e}")

################################################################################3
@require_not_banned
async def request_unlock_price_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id != ADMIN_ID and user_id !=ADMIN_ID1:
        await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الخيار.")
        return
    context.user_data["current_state"] = 'price_update_handler'

    await update.message.reply_text("✏️ أرسل الأسعار الجديدة بهذا الشكل:\n\n"
                                    "`gmail:1.25`\n"
                                    "`hotmail:0.75`\n"
                                    "`outlook:0.65`\n\n"
                                    "📌 كل نوع في سطر منفصل.",
                                    parse_mode="Markdown")
@require_not_banned
async def process_unlock_price_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if (user_id != ADMIN_ID and user_id !=ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الخيار.")

    lines = update.message.text.strip().split("\n")
    print(lines)
    updated = []
    failed = []

    for line in lines:
        try:
            acc_type, value = line.strip().split(":")
            acc_type = acc_type.lower()
            price = float(value)

            if acc_type not in ["gmail", "hotmail", "outlook"]:
                failed.append(line)
                continue

            cursor.execute("""
                INSERT OR REPLACE INTO unlock_prices (type, price)
                VALUES (?, ?)
            """, (acc_type, price))
            conn.commit()

            updated.append(f"{acc_type}: {price}")
        except Exception:
            failed.append(line)

    conn.commit()
    context.user_data.pop("current_state", None)
    response = "✅ تم تحديث الأسعار التالية:\n" + "\n".join(updated)
    if failed:
        response += "\n\n⚠️ لم يتم فهم السطور التالية:\n" + "\n".join(failed)

    await update.message.reply_text(response)
async def post_init(app: Application):
    await set_user_commands(app)
    await set_bot_commands(app)
@require_not_banned
async def ask_for_username_to_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب اسم المستخدم للبحث عنه مؤقتاً.
    """
    user_id = update.effective_chat.id
    context.user_data["current_state"] = 'search_handler'
    await update.message.reply_text("✍️ أرسل اسم المستخدم الذي تريد البحث عنه:")

@require_not_banned
async def process_username_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    cursor.execute(
        "SELECT chat_id, balance, credit, language FROM users WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()

    if row:
        chat_id, balance, credit, lang = row
        msg = (
            f"👤 معلومات المستخدم:\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"💰 الرصيد: {balance} USD\n"
            f"🎁 رصيد الإحالة: {credit} USD\n"
            f"🌐 اللغة: {lang}"
        )
    else:
        msg = "❌ لم يتم العثور على هذا المستخدم."

    await update.message.reply_text(msg, parse_mode="HTML")

    context.user_data.pop("current_state", None)








def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r'^(حول ℹ|About ℹ)$'), show_about_bot))
    app.add_handler(MessageHandler(filters.Regex(r'^(فحص جيميل \(مجاني\) 🕵‍♂🔥|Check Gmail \(Free\) 🕵‍♂🔥)$'), request_emails_for_check))
    
    app.add_handler(MessageHandler(filters.Regex(r'^(شراء حساب 🛒|Buy Account 🛒)$'), buy_account))
    app.add_handler(MessageHandler(filters.Regex(r'^(📩 Temp Mail \(Free\) ⌛🔥|بريد وهمي \(مجاني\) ⌛🔥)$'), create_temp_mail))
    app.add_handler(MessageHandler(filters.Regex(r'^(فك حساب 🔓|Unlock Account 🔓)$'), unlock_account))
    app.add_handler(MessageHandler(filters.Regex(r'^(🔄 Restore Email ♻|استرجاع ايميل ♻)$'), show_retrieve_menu1))
    app.add_handler(MessageHandler(filters.Regex(r'^(🛠️ تعديل اسعار فك حساب|🛠️ Edit Unlock Prices)$'), request_unlock_price_update))
    app.add_handler(MessageHandler(filters.Regex("^(💰 الأرصدة|💰 Balances)$"), show_balance_menu))
    app.add_handler(
    MessageHandler(
        filters.Regex(r'^(إهداء رصيد – 🎁|Gift Balance – 🎁)$'),
        ask_for_gift_balance
    )
    )

    # Back to previous menu
    app.add_handler(
        MessageHandler(
            filters.Regex(r'^(العودة – ↩|Back – ↩)$'),
            return_to_prev
        )
    )

    # Recharge Balance
    app.add_handler(
        MessageHandler(
            filters.Regex(r'^(شحن الرصيد – ⚡|Recharge Balance – ⚡)$'),
            recharge_balance
        )
    )
    app.add_handler(
    MessageHandler(
        filters.Regex(
            r'^(شراء حساب Gmail درجة أولى⭐🅶|'
            r'شراء حساب Gmail درجة ثانية🅶|'
            r'شراء حساب 🅾Outlook|'
            r'شراء حساب 🅷Hotmail|'
            r'Buy Gmail First-Class Account ⭐🅶|'
            r'Buy Gmail Second-Class Account 🅶|'
            r'Buy 🅾 Outlook Account|'
            r'Buy 🅷 Hotmail Account)$'
        ),
        select_account_type
    )
    )
    app.add_handler(
    MessageHandler(
        filters.Regex(
            r'^(سيريتيل كاش –|بايير 🅿 - Payeer|كوين اكس CoinX –|بنك بيمو –🏦|كريبتو 🌐|'
            r'Syriatel Cash –|Payeer 🅿|CoinX –|Bemo Bank –🏦|Crypto 🌐)$'
        ),
        payment_details
    )
    )
    app.add_handler(MessageHandler(filters.Regex("^(إدارة الحسابات)$"), manage_accounts))
    app.add_handler(MessageHandler(filters.Regex("^(إضافة حسابات)$"), add_accounts))
    app.add_handler(MessageHandler(filters.Regex("^(عرض الحسابات)$"), show_accounts1)) 
    app.add_handler(MessageHandler(filters.Regex("^(حذف الحسابات)$"), request_emails_for_deletion))

    app.add_handler(MessageHandler(filters.Regex("^(العودة إلى قائمة الأدمن)$"), return_to_main))
    ####################################################################################################
    ########################الرصيد الخاص بالإحالة والعادي#############################################
    app.add_handler(MessageHandler(filters.Regex("^(إضافة رصيد)$"), add_balance))
    app.add_handler(MessageHandler(filters.Regex("^(إضافة رصيد إحالة)$"), add_referral_balance))
    app.add_handler(MessageHandler(filters.Regex("^(تعديل رصيد)$"), edit_balance))
    ####################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(حظر حساب)$"), request_ban_user))
    ##################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(عرض الإحصائيات)$"), accounts_statistics))
    #################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(تحديد الأسعار)$"), ask_for_new_rates))
    ################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(عدد طلبات الشراء)$"), purchase_requests_count))
    app.add_handler(CommandHandler("unban", unban_user))
    ####################################################################################################
    #app.add_handler(MessageHandler(filters.Regex("^(العربية|English)$"), set_language))
    ###################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(حساباتي|My Accounts)$"), show_accounts))
    app.add_handler(MessageHandler(filters.Regex("^(إحالة صديق|Refer a Friend)$"), referral_link))
    app.add_handler(MessageHandler(filters.Regex("^(رصيدي|My Balance)$"), check_balance))
    ######################################################################################################
    
    #####################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(أسعار الحسابات|Account Prices)$"), show_currency_rates))
    ##########################################################################################
    #app.add_handler(MessageHandler(filters.Regex("^(شراء حساب|Buy Account)$"), buy_account))
    
    app.add_handler(MessageHandler(filters.Regex("^(1|3|5|10)$"), process_quantity)) 
    app.add_handler(CallbackQueryHandler(buy_accounts, pattern="^buy_"))
    
    ##########################################################################################################
    
    ############################################################################################################
    ##############################################################################################################
    
    
    app.add_handler(MessageHandler(filters.Regex("^(bep20|trc20|coinx|assent)$"), handle_coinx_network))
    app.add_handler(CallbackQueryHandler(bemo_accept, pattern="^bemo_accept_"))
    app.add_handler(CallbackQueryHandler(bemo_reject, pattern="^bemo_reject_"))

    #######################################################################################3
    app.add_handler(MessageHandler(filters.Regex("^(تأكيد|Confirm)$"), confirm_purchase))
    app.add_handler(MessageHandler(filters.Regex("^(إلغاء|Cancel)$"), cancel_purchase))
    #####################################تأكد من العمل########################
    app.add_handler(MessageHandler(filters.Regex("^(استرجاع ايميل)$"), show_retrieve_menu1))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    #####################################################################
    # app.add_handler(InlineQueryHandler(query_text))
    app.add_handler(MessageHandler(filters.Regex("^/request_refund .*"), request_refund))
    app.add_handler(MessageHandler(filters.Regex("^/buy_account .*"), confirm_buy))
    app.add_handler(CallbackQueryHandler(accept_refund, pattern="^accept_refund_"))
    app.add_handler(CallbackQueryHandler(reject_refund, pattern="^reject_refund_"))
    #app.add_handler(CallbackQueryHandler(hide_accounts, pattern="^hide_accounts$"))
    #app.add_handler(MessageHandler(filters.Regex("^(حول|ِAbout)$"), show_about_bot))
    app.add_handler(MessageHandler(filters.Regex("^(📞 تواصل مع الدعم|📞 Contact Support)$"), contact_admin_handler))
    app.add_handler(MessageHandler(filters.Regex("^(📄 الأسئلة الشائعة|📄 FAQ)$"), show_faq))

    app.add_handler(CommandHandler("confirm_buy", confirm_buy))
    ######################################3
    app.add_handler(MessageHandler(filters.Regex("^(فحص جيميل|Check Gmail)$"), request_emails_for_check))
    ######################################################3
    app.add_handler(MessageHandler(filters.Regex("^(فك حساب|Unlock account)$"), unlock_account))
    app.add_handler(MessageHandler(filters.Regex("^(Gmail|Hotmail|Outlook)$"), unlock_account_type_handler))
    app.add_handler(CallbackQueryHandler(handle_unlock_confirm, pattern="^unlock_confirm_"))
    app.add_handler(CallbackQueryHandler(handle_unlock_reject, pattern="^unlock_reject_"))
    #############################33
    app.add_handler(MessageHandler(filters.Regex("^🛠️ تعديل اسعار فك حساب$"), request_unlock_price_update))
    app.add_handler(MessageHandler(filters.Regex("^(العربية|English)$"), set_language))
    app.add_handler(MessageHandler(filters.Regex("^(🇸🇾 العربية|🇬🇧 English)$"), change_language))

    app.add_handler(MessageHandler(filters.Regex("^(👍🏻 موافق|👍🏻 Confirm)$"), confirm_account_creation))
    app.add_handler(MessageHandler(filters.Regex("^(🤓 إدخال اسم مستخدم مخصص|🤓 Custom Username)$"), request_custom_username))
    app.add_handler(MessageHandler(filters.Regex("^(🚪 تسجيل دخول|🚪 Login)$"), login_request))
    app.add_handler(CommandHandler("logout", logout_request))
    app.add_handler(CallbackQueryHandler(handle_logout_decision, pattern="^logout_"))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("language", change_language))
    
    app.add_handler(MessageHandler(filters.Regex("^(🔍 البحث عن مستخدم)$"), ask_for_username_to_search))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, general_handler)
    )
    app.run_polling(timeout=10, poll_interval=1, allowed_updates=Update.ALL_TYPES)
if __name__ == "__main__":
    main()

