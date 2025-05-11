# ----------------------------
# 1. مكتبات بايثون القياسية
# ----------------------------
import asyncio
import datetime
from datetime import datetime, timedelta
import functools
from functools import wraps, partial
import hashlib
import hmac
import io
import json
import logging
import os
import random
import re
import sqlite3
import string
import subprocess
import time
import uuid

# ----------------------------
# 2. مكتبات الطرف الثالث
# ----------------------------
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify

# ———— مكتبات Google API ————
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from simplegmail.query import construct_query
from contextlib import contextmanager
# ———— مكتبات Telegram Bot ————
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.error import Forbidden
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    JobQueue,
    ContextTypes,
    filters,
)

# ———— مكتبات التحقق من المعاملات ————
from payeer_api import PayeerAPI
from payeer_gmail_checker import get_recent_payeer_transactions
from syriatel_gmail_checker import get_recent_syriatel_transactions

# ----------------------------
# 3. تحميل المتغيرات من .env
# ----------------------------
load_dotenv()
TOKEN = os.getenv('TOKEN')
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

coinx_networks = {
    "trc20": "TX1234567890abcdef",
    "bep20": "0xABCDEF1234567890",
    "coinx": "coinx-wallet-0987",
    "assent": "assent-wallet-4567"
}
ADMIN_ID = 863274300 
ADMIN_ID1 = 1455755529
DATABASE_PATH = 'users.db'
@contextmanager
def get_db_connection():
    """
    Context manager للحصول على اتصال بقاعدة البيانات
    يغلق الاتصال تلقائيًا عند الخروج من الكتلة
    """
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """
    إنشاء جميع الجداول المطلوبة إذا لم تكن موجودة مسبقًا
    """
    # تعريف DDL لكل جدول
    table_definitions = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                username TEXT UNIQUE,
                balance REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                referral_code TEXT UNIQUE,
                referrer_id INTEGER,
                language TEXT,
                password TEXT,
                is_logged_in INTEGER DEFAULT 0
            );
        """,
        'referrals': """
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER
            );
        """,
        'accounts': """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_type TEXT,
                email TEXT UNIQUE,
                password TEXT,
                recovery TEXT,
                price REAL,
                added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'pending_requests': """
            CREATE TABLE IF NOT EXISTS pending_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                account_type TEXT,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'purchases': """
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
            );
        """,
        'banned_users': """
            CREATE TABLE IF NOT EXISTS banned_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                username TEXT UNIQUE
            );
        """,
        'currency_rates': """
            CREATE TABLE IF NOT EXISTS currency_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT UNIQUE,
                rate REAL
            );
        """,
        'refund_requests': """
            CREATE TABLE IF NOT EXISTS refund_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                status TEXT DEFAULT 'Pending'
            );
        """,
        'transactions': """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id TEXT UNIQUE,
                user_id INTEGER,
                method TEXT,
                amount REAL,
                status TEXT DEFAULT 'completed',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'refunded_accounts': """
            CREATE TABLE IF NOT EXISTS refunded_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                email TEXT,
                password TEXT,
                recovery TEXT,
                price REAL,
                refund_time TEXT
            );
        """,
        'unlock_prices': """
            CREATE TABLE IF NOT EXISTS unlock_prices (
                type TEXT PRIMARY KEY,
                price REAL
            );
        """,
    }

    # تنفيذ DDL لكل جدول
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # إنشاء الجداول
        for ddl in table_definitions.values():
            cursor.execute(ddl)
        conn.commit()

        # تهيئة أسعار العملات الافتراضية إذا لم تكن موجودة
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
            cursor.execute(
                "INSERT OR IGNORE INTO currency_rates (currency, rate) VALUES (?, ?)",
                (currency, rate)
            )
        conn.commit()

# إنشاء الجداول المطلوبة

def is_banned_by_username(username: str) -> bool:
    """
    يتحقق ما إذا كان المستخدم محظورًا بواسطة اسم المستخدم فقط.
    """
    if not username:
        return False
    query = "SELECT 1 FROM banned_users WHERE username = ?"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (username,))
        return cursor.fetchone() is not None


def require_not_banned(handler):
    """
    Decorator لمنع تنفيذ الـ handler إذا كان المستخدم محظورًا بواسطة اسم المستخدم فقط.
    """
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        username = update.effective_user.username
        if is_banned_by_username(username):
            if update.message:
                await update.message.reply_text("🚫 أنت محظور ولا يمكنك استخدام هذا الأمر.")
            return
        return await handler(update, context, *args, **kwargs)

    return wrapped


@require_not_banned
async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تغيير لغة المستخدم بناءً على اختياره من الأزرار.
    """
    text = update.message.text.strip()
    # عرض لوحة اختيار اللغة
    if text in ["/language", "تغيير اللغة", "Change Language"]:
        keyboard = [[KeyboardButton("🇸🇾 العربية"), KeyboardButton("🇬🇧 English")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🌍 اختر لغتك | Choose your language:", reply_markup=reply_markup)
        return

    # التأكد من اختيار لغة صحيحة
    if text not in ["🇸🇾 العربية", "🇬🇧 English"]:
        await update.message.reply_text("❌ يرجى اختيار لغة صحيحة من الأزرار.")
        return

    # تعيين كود اللغة
    language_code = "ar" if "العربية" in text else "en"
    username = context.user_data.get("username_login")
    # تحديث اللغة في قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE username = ?", (language_code, username))
        conn.commit()

    # رسالة تأكيد وفتح القائمة الرئيسية
    message = (
        "✅ تم تغيير اللغة إلى العربية." if language_code == "ar" else "✅ Language has been changed to English."
    )
    await update.message.reply_text(message)
    await main_menu(update, context, language_code)

def generate_referral_code(length: int = 6) -> str:
    """
    يولد كود إحالة مكوّن من أحرف كبيرة وأرقام بطول افتراضي 6.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choices(alphabet, k=length))
def get_user_language(username: str) -> str:
    """
    جلب لغة المستخدم من قاعدة البيانات بناءً على اسم المستخدم المخزن.
    """
    if not username:
        return "ar"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT language FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
    return row[0] if row and row[0] else "ar"
@require_not_banned
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نقطة الدخول الرئيسية: يعرض لوحة الإدارة للمسؤول أو القائمة الرئيسية للمستخدم أو يبدأ عملية التسجيل.
    يستخدم اسم المستخدم المخزن في context.user_data وليس اسم التليجرام.
    """
    user_id = update.effective_user.id
    # تنظيف الحالة السابقة
    context.user_data.pop("current_state", None)
    # جلب اسم المستخدم من الجلسة
    username = context.user_data.get("username_login")
    args = context.args

    # تحقق الحظر بناءً على اسم المستخدم
    if username:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM banned_users WHERE username = ?",
                (username,)
            )
            if cursor.fetchone():
                return

    # مسؤول البوت
    if user_id in (ADMIN_ID, ADMIN_ID1):
        await admin_panel(update, context)
        return

    # التحقق من وجود المستخدم في DB
    if username:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT language, is_logged_in FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
        if row:
            lang, is_logged_in = row
            lang = lang or "ar"
            if is_logged_in:
                await main_menu(update, context, lang)
            else:
                # طلب اختيار اللغة
                keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                try:
                    await update.message.reply_text(
                        "🌍 اختر لغتك | Choose your language:",
                        reply_markup=reply_markup
                    )
                except Forbidden:
                    pass
            return

    # مستخدم جديد أو جلسة جديدة
    referral_code = generate_referral_code()
    referrer_id = None
    if args:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE referral_code = ?",
                (args[0],)
            )
            ref = cursor.fetchone()
            if ref:
                referrer_id = ref[0]
                cursor.execute(
                    "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                    (referrer_id, user_id)
                )
                conn.commit()

    # حفظ بيانات التسجيل مؤقتًا
    context.user_data.update({
        "pending_user_id": user_id,
        "pending_referral_code": referral_code,
        "pending_referrer_id": referrer_id
    })
    # طلب اختيار اللغة
    keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    try:
        await update.message.reply_text(
            "🌍 اختر لغتك | Choose your language:",
            reply_markup=reply_markup
        )
    except Forbidden:
        pass


@require_not_banned
async def confirm_account_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تأكيد وإنشاء الحساب بعد تحديد اللغة.
    اسم المستخدم وكلمة المرور محفوظان في context.user_data.
    """
    # جلب البيانات المؤقتة
    user_id = context.user_data.get("pending_user_id")
    username = context.user_data.get("pending_username")
    password = context.user_data.get("pending_password")
    lang = context.user_data.get("language", "ar")
    referral_code = context.user_data.get("pending_referral_code")
    referrer_id = context.user_data.get("pending_referrer_id")

    if not (username and password):
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,)
        )
        exists = cursor.fetchone()
        if exists and context.user_data.get("username_login") != username:
            await update.message.reply_text(
                "⚠️ اسم المستخدم محجوز، اختر آخر.")
            return
        cursor.execute(
            "INSERT OR REPLACE INTO users "
            "(chat_id, username, password, language, referral_code, referrer_id, is_logged_in) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (user_id, username, password, lang, referral_code, referrer_id)
        )
        conn.commit()

    # تحديث الجلسة وتنظيف المتغيرات
    context.user_data["username_login"] = username
    for key in [
        "pending_user_id", "pending_username", "pending_password",
        "pending_referral_code", "pending_referrer_id", "current_state"
    ]:
        context.user_data.pop(key, None)

    await main_menu(update, context, lang)


@require_not_banned
async def request_custom_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    طلب اسم مستخدم مخصص.
    """
    lang = context.user_data.get("language", "ar")
    prompt = (
        "✍️ أرسل اسم المستخدم الذي ترغب به:" if lang == "ar"
        else "✍️ Please send your desired username:"
    )
    context.user_data["current_state"] = 'custom_handler'
    await update.message.reply_text(prompt)


@require_not_banned
async def process_custom_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة اسم المستخدم المخصص.
    """
    user_id = context.user_data.get("pending_user_id")
    username = update.message.text.strip()
    password = context.user_data.get("pending_password")
    lang = context.user_data.get("language", "ar")
    referral_code = context.user_data.get("pending_referral_code")
    referrer_id = context.user_data.get("pending_referrer_id")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,)
        )
        exists = cursor.fetchone()
        if exists and context.user_data.get("username_login") != username:
            await update.message.reply_text(
                "⚠️ اسم المستخدم محجوز، اختر آخر.")
            return
        cursor.execute(
            "INSERT OR REPLACE INTO users "
            "(chat_id, username, password, language, referral_code, referrer_id, is_logged_in) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (user_id, username, password, lang, referral_code, referrer_id)
        )
        conn.commit()

    # تنظيف الجلسة
    for key in [
        "pending_user_id", "pending_username", "pending_password",
        "pending_referral_code", "pending_referrer_id", "current_state"
    ]:
        context.user_data.pop(key, None)
    context.user_data["username_login"] = username

    await main_menu(update, context, lang)


@require_not_banned
async def login_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بدء طلب تسجيل الدخول.
    """
    lang = context.user_data.get("language", "ar")
    prompt = (
        "✍️ أرسل اسم المستخدم ثم كلمة المرور في سطرين متتاليين:" if lang == "ar"
        else "✍️ Send your username and password on two lines."
    )
    context.user_data["current_state"] = 'login_handler'
    await update.message.reply_text(prompt)


@require_not_banned
async def process_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة تسجيل الدخول.
    """
    lang = context.user_data.get("language", "ar")
    lines = update.message.text.strip().split("\n")
    if len(lines) != 2:
        msg = (
            "❌ يرجى إدخال اسم المستخدم وكلمة المرور بشكل صحيح." if lang == "ar"
            else "❌ Invalid format."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)
    username, password = lines

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chat_id FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE users SET is_logged_in = 1 WHERE username = ?",
                (username,)
            )
            conn.commit()
            context.user_data["username_login"] = username
            await update.message.reply_text(
                f"✅ تم تسجيل الدخول بنجاح. مرحبًا {username}!"
            )
            await main_menu(update, context, lang)
        else:
            msg = (
                "❌ فشل تسجيل الدخول. تحقق من البيانات." if lang == "ar"
                else "❌ Login failed. Check your credentials."
            )
            await update.message.reply_text(msg)
    context.user_data.pop("current_state", None)



@require_not_banned
async def logout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة نقرات أزرار تأكيد أو إلغاء تسجيل الخروج.
    """
    query = update.callback_query
    await query.answer()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    if query.data == "logout_confirm":
        # تحديث DB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_logged_in = 0 WHERE username = ?", (username,))
            conn.commit()
        # تنظيف الجلسة
        context.user_data.pop("username_login", None)
        text = ("✅ تم تسجيل الخروج بنجاح." if lang == "ar" else "✅ Logged out successfully.")
    else:
        text = ("❌ تم إلغاء العملية." if lang == "ar" else "❌ Logout canceled.")
    await query.edit_message_text(text)

@require_not_banned
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """
    القائمة الرئيسية للمستخدم بعد تسجيل الدخول.
    """
    username = context.user_data.get("username_login")
    messages = {
        "ar": f"👋 مرحبًا <b>{username}</b> في بوت بيع الحسابات!\nاختر من القائمة أدناه:",
        "en": f"👋 Welcome <b>{username}</b> to the account selling bot!\nChoose from the menu below:"
    }
    keyboard = [
        [KeyboardButton("فحص جيميل" if lang == "ar" else "cheak Gmail"), KeyboardButton("💰 الأرصدة" if lang == "ar" else "💰 Balances")],
        [KeyboardButton("شراء حساب" if lang == "ar" else "Buy Account")],
        [KeyboardButton("فك حساب" if lang == "ar" else "Unlock account"), KeyboardButton("بريد وهمي" if lang == "ar" else "📩 Temp Mail")],
        [KeyboardButton("استرجاع ايميل" if lang == "ar" else "Recover account"), KeyboardButton("حول" if lang == "ar" else "About")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(messages[lang], reply_markup=reply_markup, parse_mode="HTML")

@require_not_banned
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    لوحة تحكم الأدمن مع خياراته.
    """
    keyboard = [
        [KeyboardButton("عرض الإحصائيات"), KeyboardButton("إدارة الحسابات")],
        [KeyboardButton("تعديل رصيد"), KeyboardButton("إضافة رصيد")],
        [KeyboardButton("إضافة رصيد إحالة"), KeyboardButton("حظر حساب")],
        [KeyboardButton("عدد طلبات الشراء"), KeyboardButton("تحديد الأسعار")],
        [KeyboardButton("🛠️ تعديل اسعار فك حساب"), KeyboardButton("🔍 البحث عن مستخدم")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🔧 **لوحة تحكم الأدمن**:\nاختر من القائمة التالية:",
        reply_markup=reply_markup
    )

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
    """معالجة قرار تسجيل الخروج."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    if query.data == "logout_confirm":
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_logged_in = 0 WHERE username = ?", (username,))
            conn.commit()
        context.user_data.pop("username_login", None)
        keyboard = [[KeyboardButton("العربية"), KeyboardButton("English")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        msg = "✅ تم تسجيل خروجك.\n🌍 اختر لغتك للمتابعة:" if lang == "ar" else "✅ You have been logged out.\n🌍 Please choose your language:"
        await query.message.edit_text(msg)
        await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=reply_markup)
    else:
        msg = "❌ تم إلغاء تسجيل الخروج." if lang == "ar" else "❌ Logout cancelled."
        await query.message.edit_text(msg)


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
    """
    عرض قائمة الأرصدة: رصيد المستخدم، شحن، إهداء، أو العودة.
    """
    # جلب اسم المستخدم من الجلسة
    username = context.user_data.get("username_login")
    # جلب لغة المستخدم من قاعدة البيانات
    lang = get_user_language(username)

    # بناء لوحة الأزرار حسب اللغة
    keyboard = [
        [KeyboardButton("رصيدي" if lang == "ar" else "My Balance")],
        [KeyboardButton("شحن الرصيد" if lang == "ar" else "Recharge Balance")],
        [KeyboardButton("إهداء رصيد" if lang == "ar" else "Gift Balance")],
        [KeyboardButton("العودة" if lang == "ar" else "Back")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    message = "💰 اختر ما تريد:" if lang == "ar" else "💰 Choose an option:"
    await update.message.reply_text(message, reply_markup=reply_markup)

#############################3
@require_not_banned
async def request_emails_for_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب من الأدمن إدخال الإيميلات المراد حذفها مؤقتاً."""
    user_id = update.effective_user.id
    # صلاحية الأدمن
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    # وضع الحالة للتعامل مع حذف الإيميلات
    context.user_data["current_state"] = "delete_handler"
    await update.message.reply_text(
        "✍️ أرسل الإيميلات التي تريد حذفها، كل إيميل في سطر منفصل:"
    )

@require_not_banned
async def process_email_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حذف الإيميلات المُرسَلة وإنهاء الحالة المؤقتة."""
    user_id = update.effective_user.id
    # تحقق صلاحية الأدمن
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return

    # جمع الإيميلات وتنظيف الفراغات
    emails = [e.strip() for e in update.message.text.splitlines() if e.strip()]
    deleted = 0
    not_found = []

    # تنفيذ عملية الحذف داخل اتصال بقاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for email in emails:
            cursor.execute(
                "SELECT 1 FROM accounts WHERE email = ?", (email,)
            )
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM accounts WHERE email = ?", (email,)
                )
                deleted += 1
            else:
                not_found.append(email)
        conn.commit()

    # بناء رسالة النتيجة
    msg = f"✅ تم حذف {deleted} من أصل {len(emails)} إيميل."
    if not_found:
        msg += "\n❌ لم يتم العثور على:\n" + "\n".join(not_found)

    # إرسال النتيجة وتنظيف الحالة
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
@require_not_banned
async def add_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يضع البوت في وضع استقبال تفاصيل الحسابات مؤقتًا للأدمن.
    """
    user_id = update.effective_user.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "save_accounts"
    await update.message.reply_text(
        "📌 أرسل البيانات بالترتيب التالي، كل سطر كما هو:\n\n"
        "1️⃣ نوع الحساب\n"
        "2️⃣ السعر\n"
        "3️⃣ كلمة المرور\n"
        "4️⃣ البريد الاحتياطي (Recovery)\n"
        "5️⃣ الحسابات (كل سطر إيميل)\n\n"
        "🔹 **مثال:**\n"
        "Gmail Premium\n"
        "1500\n"
        "password123\n"
        "recovery@example.com\n"
        "email1@example.com\n"
        "email2@example.com"
    )

@require_not_banned
async def save_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يحفظ الحسابات التي أرسلها الأدمن ويوقف استقبال النصوص بعدها.
    يرسل إشعارًا للمستخدمين الذين طلبوا ذلك مرة واحدة لكل chat_id،
    ثم يعود مباشرة إلى لوحة الأدمن.
    """
    user_id = update.effective_user.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return

    # نظف المدخلات
    lines = [ln.strip() for ln in update.message.text.splitlines() if ln.strip()]
    if len(lines) < 5:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ فضلاً أرسل البيانات كاملةً:\n"
            "1️⃣ نوع الحساب\n2️⃣ السعر\n3️⃣ كلمة المرور\n"
            "4️⃣ البريد الاحتياطي\n5️⃣ الحسابات (كل سطر إيميل)"
        )

    account_type, price, pwd, recovery, *emails = lines
    duplicates = []

    # تعامل مع القاعدة
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # أدخِل أو اجمع المكررات
        for email in emails:
            cursor.execute("SELECT added_time FROM accounts WHERE email = ?", (email,))
            acc = cursor.fetchone()
            cursor.execute("SELECT purchase_time FROM purchases WHERE email = ?", (email,))
            pur = cursor.fetchone()

            if acc or pur:
                ts = (acc or pur)[0]
                duplicates.append(f"{email} – أول إضافة: {ts}")
            else:
                cursor.execute(
                    "INSERT INTO accounts (account_type, email, password, recovery, price, added_time) "
                    "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (account_type, email, pwd, recovery, price)
                )
        conn.commit()

        # جلب chat_id مميز لكل طلب
        cursor.execute(
            "SELECT DISTINCT chat_id FROM pending_requests WHERE account_type = ?",
            (account_type,)
        )
        waiting = [row[0] for row in cursor.fetchall()]

        # حذف جميع pending_requests لهذا النوع
        cursor.execute(
            "DELETE FROM pending_requests WHERE account_type = ?",
            (account_type,)
        )
        conn.commit()

    # إرسال الإشعارات مرة واحدة لكل chat_id
    for chat_id in waiting:
        try:
            await context.bot.send_message(
                chat_id,
                f"✅ حسابات «{account_type}» متاحة الآن!"
            )
        except Exception:
            pass

    # عرض المكررات إذا وجدت
    if duplicates:
        text = "⚠️ هذه الإيميلات مكررة:\n" + "\n".join(duplicates)
        if len(text) > 4000:
            bio = io.BytesIO(text.encode("utf-8"))
            bio.name = "duplicates.txt"
            await update.message.reply_document(
                document=bio,
                filename=bio.name,
                caption="⚠️ قائمة الازدواجيات"
            )
        else:
            await update.message.reply_text(text)

    success = len(emails) - len(duplicates)
    await update.message.reply_text(
        f"✅ أضفتَ {success} من {len(emails)} حسابًا بنجاح."
    )

    # نظف الحالة وارجع إلى لوحة الأدمن مباشرةً
    context.user_data.pop("current_state", None)
    await admin_panel(update, context)
@require_not_banned
async def show_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض الحسابات مجمعة حسب النوع/كلمة المرور/Recovery، 
    وإرسال ملف نصي بإيميلات كل مجموعة للأدمن.
    """
    user_id = update.effective_user.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    # جلب البيانات من قاعدة البيانات باستخدام مدير السياق
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT account_type, password, recovery, email
            FROM accounts
            ORDER BY account_type, password, recovery
        """)
        rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("❌ لا توجد حسابات متاحة حاليًا.")

    # تجميع الإيميلات حسب tuple (نوع الحساب، كلمة المرور، Recovery)
    from collections import defaultdict
    groups = defaultdict(list)
    for acct_type, pwd, rec, email in rows:
        groups[(acct_type, pwd, rec)].append(email)

    # إرسال كل مجموعة مع ملف الإيميلات الخاص بها
    for (acct_type, pwd, rec), emails in groups.items():
        count = len(emails)

        # رأس يصف المجموعة
        header = (
            f"📋 <b>نوع الحساب:</b> {acct_type}\n"
            f"🔢 <b>العدد:</b> {count}\n"
            f"🔑 <b>كلمة المرور:</b> {pwd}\n"
            f"📩 <b>Recovery:</b> {rec}\n\n"
            "⤵️ قائمة الإيميلات مرفقة في الملف أدناه:"
        )
        await update.message.reply_text(header, parse_mode="HTML")

        # تجهيز محتوى الملف
        content = "\n".join(emails)
        bio = io.BytesIO(content.encode("utf-8"))
        # تأكد من اسم ملف خالٍ من الفراغات والأحرف الخاصة
        safe_name = f"{acct_type}_{pwd}_{rec}".replace(" ", "_").replace("/", "-")
        bio.name = f"{safe_name}.txt"
        bio.seek(0)

        await update.message.reply_document(
            document=bio,
            filename=bio.name,
            caption=f"📂 إيميلات {acct_type} ({count} حساب)" 
        )

    # بعد الانتهاء، إعادة الأدمن إلى لوحة التحكم
    await admin_panel(update, context)

##########################################################################################################
#############################إضافة وتعديل الرصيد #######################################################
@require_not_banned
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت حالة انتظار لإضافة رصيد أساسي للأدمن.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "add_balance"
    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ بالشكل:\n\n"
        "@username 50.0"
    )

@require_not_banned
async def add_referral_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت حالة انتظار لإضافة رصيد إحالة للأدمن.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "add_referral"
    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ لإضافة رصيد الإحالة:\n\n"
        "@username 10.0"
    )

@require_not_banned
async def process_admin_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج كل من add_balance و add_referral_balance وفق current_action،
    ثم يخرج من حالة الانتظار ويرسل إشعارًا للمستخدم المتأثر فقط.
    """
    action = context.user_data.get("current_state")
    if action not in ("add_balance", "add_referral"):
        return  # ليس لدينا طلب قيد الانتظار

    text = update.message.text.strip().split()
    if len(text) != 2:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. استخدم: @username 50.0"
        )

    username, amt_str = text[0].lstrip("@"), text[1]
    try:
        amount = float(amt_str)
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ المبلغ يجب أن يكون رقمياً.")

    # احصل على chat_id للحساب أولاً فقط
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chat_id FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(f"⚠️ المستخدم @{username} غير مسجل.")
        target_chat_id = row[0]

        # حدّث أو حدّث رصيد الإحالة
        if action == "add_balance":
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE username = ?",
                (amount, username)
            )
        else:  # add_referral
            cursor.execute(
                "UPDATE users SET credit = credit + ? WHERE username = ?",
                (amount, username)
            )
        conn.commit()

    # نظف الحالة
    context.user_data.pop("current_state", None)

    # أكّد للأدمن
    kind = "الرصيد" if action == "add_balance" else "رصيد الإحالة"
    await update.message.reply_text(f"✅ تم إضافة {amount} إلى {kind} @{username}.")

    # أرسل إشعارًا للمستخدم المتأثر فقط
    notif = (
        f"💰 رصيدك زاد بمقدار {amount}." 
        if action == "add_balance"
        else f"🔗 رصيد الإحالة زاد بمقدار {amount}."
    )
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=notif)
    except Exception:
        pass

@require_not_banned
async def edit_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت في وضع انتظار لتعديل رصيد المستخدم.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "edit_balance"
    await update.message.reply_text(
        "✍️ أرسل اسم المستخدم والمبلغ الجديد للرصيد بالشكل:\n\n"
        "@username 100.0"
    )

@require_not_banned
async def process_edit_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج تعديل الرصيد بعد أمر edit_balance،
    ثم يخرج من حالة الانتظار ويرسل إشعاراً للمستخدم المعدَّل حسابه فقط.
    """
    action = context.user_data.get("current_state")
    if action != "edit_balance":
        return  # لا يوجد تعديل قيد الانتظار

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ الصيغة غير صحيحة. مثال: @username 100.0")

    username, amt_str = parts[0].lstrip("@"), parts[1]
    try:
        new_balance = float(amt_str)
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ المبلغ يجب أن يكون رقمياً.")

    # جلب chat_id لحساب واحد فقط
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chat_id FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(f"⚠️ المستخدم @{username} غير مسجل.")
        target_chat_id = row[0]

        # تعديل الرصيد
        cursor.execute(
            "UPDATE users SET balance = ? WHERE username = ?",
            (new_balance, username)
        )
        conn.commit()

    # نظف حالة الانتظار
    context.user_data.pop("current_state", None)

    # تأكيد للأدمن
    await update.message.reply_text(f"✅ تم تعديل رصيد @{username} إلى {new_balance}.")

    # إشعار المستخدم المتأثر فقط
    try:
        await context.bot.send_message(
            chat_id=target_chat_id,
            text=f"🔄 تم تحديث رصيد حسابك @{username} إلى {new_balance}."
        )
    except Exception:
        pass





###########################################################################################################
####################حظر حساب ###############################################################################
@require_not_banned
async def request_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت في وضع انتظار لحظر مستخدم.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "ban_user"
    await update.message.reply_text("✍️ أرسل اسم المستخدم الذي تريد حظره (بدون @):")

@require_not_banned
async def process_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج حظر المستخدم بعد request_ban_user،
    ثم يخرج من حالة الانتظار ويرجع للأدمن.
    """
    if context.user_data.get("current_state") != "ban_user":
        return  # لا يوجد حظر قيد المعالجة

    username = update.message.text.strip().lstrip("@")
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # تحقق من الحظر الحالي
        cursor.execute("SELECT 1 FROM banned_users WHERE username = ? LIMIT 1", (username,))
        if cursor.fetchone():
            msg = f"⚠️ @{username} محظورٌ بالفعل."
        else:
            # جلب chat_id للحساب
            cursor.execute("SELECT chat_id FROM users WHERE username = ? LIMIT 1", (username,))
            row = cursor.fetchone()
            if not row:
                msg = f"⚠️ المستخدم @{username} غير موجود."
            else:
                chat_id = row[0]
                cursor.execute(
                    "INSERT INTO banned_users (username, chat_id) VALUES (?, ?)",
                    (username, chat_id)
                )
                conn.commit()
                msg = f"✅ تم حظر @{username} بنجاح."

    # نظف الحالة وأرسل النتيجة ثم عد للأدمن
    context.user_data.pop("current_state", None)
    await update.message.reply_text(msg)
    await admin_panel(update, context)


@require_not_banned
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يفتح أمر /unban @username لإلغاء حظر مستخدم مباشرة.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    args = context.args
    if not args:
        return await update.message.reply_text("❌ استخدم: /unban @username")

    username = args[0].lstrip("@")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM banned_users WHERE username = ?", (username,))
        if cursor.rowcount == 0:
            msg = f"⚠️ @{username} ليس محظورًا أو غير موجود."
        else:
            conn.commit()
            msg = f"✅ تم إلغاء حظر @{username} بنجاح."
    await update.message.reply_text(msg)
#############################################################################################################
##################################إحصائيات########################################################
@require_not_banned
async def accounts_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض إحصائيات الحسابات (عدد الحسابات لكل نوع)
    وعدد طلبات استرجاع الحسابات لكل نوع.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    # جلب الإحصائيات من قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # عدد الحسابات لكل نوع
        cursor.execute(
            "SELECT account_type, COUNT(*) AS cnt FROM accounts GROUP BY account_type"
        )
        stats = cursor.fetchall()
        # عدد طلبات الاسترجاع لكل نوع
        cursor.execute(
            "SELECT account_type, COUNT(*) AS cnt FROM pending_requests GROUP BY account_type"
        )
        pending = cursor.fetchall()

    # بناء الرسالة
    lines = ["📊 <b>إحصائيات الحسابات:</b>"]
    if stats:
        lines.append("\n📌 <b>عدد الحسابات لكل نوع:</b>")
        for acct_type, cnt in stats:
            lines.append(f"🔹 {acct_type}: {cnt} حساب")
    else:
        lines.append("\n❌ لا توجد حسابات مسجلة حاليًا.")

    lines.append("\n📦 <b>طلبات استرجاع الحسابات:</b>")
    if pending:
        for acct_type, cnt in pending:
            lines.append(f"🔻 {acct_type}: {cnt} طلب")
    else:
        lines.append("\n✅ لا توجد طلبات استرجاع حالية.")

    message = "\n".join(lines)
    await update.message.reply_text(message, parse_mode="HTML")

#######################################################################################################

@require_not_banned
async def ask_for_new_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت في وضع انتظار لإدخال أسعار العملات الجديدة للأدمن.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")
    context.user_data["current_state"] = "update_rates"
    await update.message.reply_text(
        "✍️ *Please enter the new rates in this format:*  \n"
        "`USDT - 10200`\n"
        "`Dollar - 11600`\n"
        "`SYP - 9800`\n"
        "`Payeer - 10100`\n"
        "`TRC20 - 10000`\n"
        "`BEP20 - 10000`\n"
        "`Bemo - 9500`\n\n"
        "✅ Send the list now:",
        parse_mode="Markdown"
    )

@require_not_banned
async def save_new_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج قائمة أسعار العملات ثم يخرج من وضع الانتظار ويعود للأدمن.
    """
    if context.user_data.get("current_state") != "update_rates":
        return

    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    lines = [ln.strip() for ln in update.message.text.splitlines() if ln.strip()]
    if not lines:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("❌ Please enter the rates correctly.")

    updated, failed = [], []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for line in lines:
            parts = line.split(" - ")
            if len(parts) != 2:
                failed.append(line)
                continue
            currency, rate_str = parts[0].strip(), parts[1].strip()
            try:
                rate = float(rate_str)
                cursor.execute(
                    "UPDATE currency_rates SET rate = ? WHERE currency = ?",
                    (rate, currency)
                )
                if cursor.rowcount:
                    updated.append(f"{currency}: {rate}")
                else:
                    failed.append(line)
            except Exception:
                failed.append(line)
        conn.commit()

    # بناء رسالة للمسؤول
    msg = ""
    if updated:
        msg += "✅ Updated rates:\n" + "\n".join(f"- {u}" for u in updated)
    if failed:
        msg += "\n\n⚠️ Failed to parse:\n" + "\n".join(f"- {f}" for f in failed)
    if not msg:
        msg = "⚠️ No valid lines were found."

    context.user_data.pop("current_state", None)
    await update.message.reply_text(msg, parse_mode="Markdown")
    await admin_panel(update, context)

#########################################################################################3
@require_not_banned
async def purchase_requests_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض عدد طلبات الشراء والاسترجاع اليومية والشهرية لكل نوع
    مع الحفاظ على current_state.
    """
    admin_id = update.effective_user.id
    if admin_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الأمر.")

    
    now = datetime.now()
    # بداية ونهاية اليوم
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)
    # بداية الشهر
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # استخدام اتصال قاعدة بيانات مُدار
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # طلبات الشراء اليوم
        cursor.execute(
            "SELECT account_type, COUNT(*) FROM purchases "
            "WHERE purchase_time >= ? AND purchase_time < ? "
            "GROUP BY account_type",
            (start_time, end_time)
        )
        daily = cursor.fetchall()

        # طلبات الشراء هذا الشهر
        cursor.execute(
            "SELECT account_type, COUNT(*) FROM purchases "
            "WHERE purchase_time >= ? "
            "GROUP BY account_type",
            (month_start,)
        )
        monthly = cursor.fetchall()

        # إجمالي كل الطلبات
        cursor.execute("SELECT COUNT(*) FROM purchases")
        total_requests = cursor.fetchone()[0]

        # استرجاعات اليوم
        cursor.execute(
            "SELECT COUNT(*) FROM refunded_accounts "
            "WHERE refund_time >= ? AND refund_time < ?",
            (start_time, end_time)
        )
        refunded_today = cursor.fetchone()[0]

        # استرجاعات هذا الشهر
        cursor.execute(
            "SELECT COUNT(*) FROM refunded_accounts "
            "WHERE refund_time >= ?",
            (month_start,)
        )
        refunded_month = cursor.fetchone()[0]

    # بناء الرسالة بصيغة HTML
    lines = [
        "📊 <b>إحصائيات الطلبات والاسترجاعات</b>",
        f"📦 <b>إجمالي الشراء:</b> {total_requests} طلب",
        "",
        f"🕛 <b>طلبات اليوم ({start_time.strftime('%Y-%m-%d')}):</b>"
    ]
    if daily:
        lines += [f"🔹 {acct}: {cnt} طلب" for acct, cnt in daily]
    else:
        lines.append("🔸 لا توجد طلبات شراء اليوم.")
    lines.append(f"♻️ <b>استرجاعات اليوم:</b> {refunded_today}")
    lines.append("")
    lines.append(f"🗓️ <b>طلبات الشهر ({month_start.strftime('%B %Y')}):</b>")
    if monthly:
        lines += [f"🔹 {acct}: {cnt} طلب" for acct, cnt in monthly]
    else:
        lines.append("🔸 لا توجد طلبات شراء هذا الشهر.")
    lines.append(f"♻️ <b>استرجاعات هذا الشهر:</b> {refunded_month}")

    # أرسل الرسالة وأزل الحالة
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


#############################################################زبون
#############################اللغة

def generate_password(length: int = 10) -> str:
    """
    يولد كلمة مرور عشوائية بطول افتراضي 10 أحرف، تشمل حروفًا وأرقامًا ورموز.
    """
    chars = string.ascii_letters + string.digits + "!#$%^&*()_+=-"
    return ''.join(random.choices(chars, k=length))


def generate_username(update: Update) -> str:
   
    # 1) Telegram username
    tg_username = update.effective_chat.username
    if tg_username:
        base = ''.join(ch for ch in tg_username if ch.isalnum())
    else:
        # 2) full name
        full_name = update.effective_chat.full_name or ''
        base = ''.join(ch for ch in full_name if ch.isalnum()) or None
    # 3) fallback
    if not base:
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        base = 'User' + suffix

    candidate = base
    suffix_num = 1
    # check uniqueness
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ? LIMIT 1", (candidate,))
        while cursor.fetchone():
            candidate = f"{base}{suffix_num}"
            suffix_num += 1
            cursor.execute("SELECT 1 FROM users WHERE username = ? LIMIT 1", (candidate,))
    return candidate
@require_not_banned
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1) تحقق من إذن الأدمن (او المستخدم العادي بعد تسجيله)
    #    هنا نفترض أن هذه الدالة متاحة لكل المستخدمين المسجلين
    #    لذا لا نعيد التحقق من ADMIN_ID

    # 2) تحقق من صحة اختيار اللغة
    if text not in ("العربية", "English"):
        return await update.message.reply_text("❌ يرجى اختيار لغة صحيحة من الأزرار.")

    # 3) ضبط الكود اللغوي في الجلسة
    lang = "ar" if text == "العربية" else "en"
    context.user_data["language"] = lang

    # 4) توليد بيانات الحساب مؤقتاً
    username = generate_username(update)
    password = generate_password()
    context.user_data["pending_username"] = username
    context.user_data["pending_password"] = password

    # 5) تحضير الرسالة والأزرار بلغة المستخدم
    if lang == "ar":
        msg = (
            f"🚀 سيتم إنشاء حساب LTE الخاص بك بالبيانات التالية:\n\n"
            f"👤 اسم المستخدم: <code>{username}</code>\n"
            f"🔑 كلمة المرور: <code>{password}</code>\n\n"
            "اضغط على \"👍🏻 موافق\" لإتمام العملية.\n"
            "إذا لديك حساب مسبقاً، اضغط على \"🚪 تسجيل دخول\".\n"
            "أو اضغط \"🤓 إدخال اسم مستخدم مخصص\" لاختيار اسم آخر."
        )
        buttons = [
            [KeyboardButton("👍🏻 موافق"), KeyboardButton("🚪 تسجيل دخول")],
            [KeyboardButton("🤓 إدخال اسم مستخدم مخصص")]
        ]
    else:
        msg = (
            f"🚀 Your LTE account will be created with:\n\n"
            f"👤 Username: <code>{username}</code>\n"
            f"🔑 Password: <code>{password}</code>\n\n"
            "Press \"👍🏻 Confirm\" to complete.\n"
            "If you already have an account, press \"🚪 Login\".\n"
            "Or press \"🤓 Custom Username\" to enter your own."
        )
        buttons = [
            [KeyboardButton("👍🏻 Confirm"), KeyboardButton("🚪 Login")],
            [KeyboardButton("🤓 Custom Username")]
        ]

    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

#######################################################################################
#################################################################3حساباتي
@require_not_banned
async def show_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1) جلب user_id من اسم المستخدم المسجّل في الجلسة
    username = context.user_data.get("username_login")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        row = cursor.fetchone()
        if not row:
            return await update.message.reply_text("❌ خطأ: المستخدم غير مسجل.")
        user_db_id = row[0]

        # 2) جلب الحسابات بناءً على user_id
        cursor.execute(
            "SELECT email, password, purchase_time "
            "FROM purchases WHERE user_id = ? ORDER BY purchase_time DESC",
            (user_db_id,)
        )
        accounts = cursor.fetchall()

    if not accounts:
        return await update.message.reply_text("❌ لا يوجد لديك أي حسابات مشتراة.")

    now = datetime.now()
    lines = ["📂 حساباتك المتاحة (صلاحية 30 يوماً):"]
    for email, pwd, purchase_time in accounts:
        purchased = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
        expiry = purchased + timedelta(days=30)
        days_left = (expiry - now).days
        status = "✅ صالح" if days_left > 0 else "❌ منتهي الصلاحية"
        lines.append(
            f"\n📧 {email}"
            f"\n🔑 {pwd}"
            f"\n📅 تنتهي: {expiry.date()} ({days_left} يوماً متبقياً)"
            f"\n🔹 {status}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

######################################################################################إحالة صديق
@require_not_banned
async def referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض رابط الإحالة للمستخدم استنادًا إلى الكود المخزّن في قاعدة البيانات.
    """
    username = context.user_data.get("username_login")
    if not username:
        return await update.message.reply_text(
            "❌ خطأ: لم يتم تسجيل اسم المستخدم في الجلسة."
        )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT referral_code, language FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()

    if not row or not row[0]:
        return await update.message.reply_text(
            "❌ لا يمكن العثور على رمز الإحالة الخاص بك."
        )

    referral_code, lang = row
    bot_username = context.bot.username or ""
    referral_url = f"https://t.me/{bot_username}?start={referral_code}"

    if lang == "ar":
        text = (
            f"🔗 رابط الإحالة الخاص بك:\n\n"
            f"<code>{referral_url}</code>\n\n"
            "👥 انسخ الرابط وشاركه مع أصدقائك للحصول على مكافآت!"
        )
    else:
        text = (
            f"🔗 Your referral link:\n\n"
            f"<code>{referral_url}</code>\n\n"
            "👥 Copy and share with your friends to earn rewards!"
        )

    await update.message.reply_text(text, parse_mode="HTML")

#########################################################################################ؤصيدي
@require_not_banned
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض رصيد المستخدم، رصيد الإحالة، رابط الإحالة، وعدد الإحالات المسجَّلة عنه.
    """
    username = context.user_data.get("username_login")
    if not username:
        return await update.message.reply_text("❌ لم يتم العثور على اسم المستخدم في الجلسة.")

    # جلب بيانات المستخدم من قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, balance, credit, referral_code, language "
            "FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return await update.message.reply_text("❌ لم يتم العثور على بيانات حسابك.")

        user_db_id, balance, credit, referral_code, lang = row

        # حساب عدد الإحالات المسجّلة لهذا المستخدم
        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user_db_id,)
        )
        referral_count = cursor.fetchone()[0]

    # توليد رابط الإحالة
    bot_username = context.bot.username or ""
    referral_url = f"https://t.me/{bot_username}?start={referral_code}"

    # إعداد النص حسب اللغة
    if lang == "ar":
        text = (
            f"💰 <b>رصيدك:</b> <code>{balance:.2f} ل.س</code>\n"
            f"🎁 <b>رصيد الإحالة:</b> <code>{credit:.2f} ل.س</code>\n\n"
            f"🔗 <b>رابط الإحالة:</b>\n{referral_url}\n\n"
            f"👥 <b>عدد إحالاتك:</b> <code>{referral_count}</code>"
        )
    else:
        text = (
            f"💰 <b>Your balance:</b> <code>{balance:.2f} L.S</code>\n"
            f"🎁 <b>Referral balance:</b> <code>{credit:.2f} L.S</code>\n\n"
            f"🔗 <b>Your referral link:</b>\n{referral_url}\n\n"
            f"👥 <b>Total referrals:</b> <code>{referral_count}</code>"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

################################################################################################
@require_not_banned
async def show_currency_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض أسعار العملات الحالية بالاعتماد على جدول currency_rates،
    ويدعم العربية والإنجليزية حسب لغة المستخدم.
    """
    # جلب لغة المستخدم
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # جلب الأسعار من القاعدة
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT currency, rate FROM currency_rates ORDER BY currency"
        )
        rates = cursor.fetchall()

    if not rates:
        msg = (
            "❌ لم يتم ضبط أسعار العملات بعد." if lang == "ar"
            else "❌ Currency rates have not been set yet."
        )
        return await update.message.reply_text(msg)

    # بناء الرسالة بحسب اللغة
    if lang == "ar":
        header = "💱 <b>أسعار العملات الحالية:</b>\n\n"
        lines = [
            f"🔹 1 {currency} = {rate} ليرة سورية"
            for currency, rate in rates
        ]
    else:
        header = "💱 <b>Current Currency Rates:</b>\n\n"
        lines = [
            f"🔹 1 {currency} = {rate} SYP"
            for currency, rate in rates
        ]

    text = header + "\n".join(lines)
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

################################################################################################################
@require_not_banned
async def buy_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض أنواع الحسابات المتاحة مع عددها وأسعار العملات،
    ثم يطلب من المستخدم اختيار النوع.
    """
    username = context.user_data.get("username_login")
    # 1) جلب user_id واللغة
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, language FROM users WHERE username = ? LIMIT 1", (username,))
        row = cursor.fetchone()
        if not row:
            return await update.message.reply_text("❌ خطأ: المستخدم غير مسجَّل.")
        user_db_id, lang = row

        # 2) جلب عدد الحسابات المتاحة لكل نوع
        cursor.execute("SELECT account_type, COUNT(*) FROM accounts GROUP BY account_type")
        accounts = dict(cursor.fetchall())

        # 3) جلب أسعار العملات
        cursor.execute("SELECT currency, rate FROM currency_rates ORDER BY currency")
        rates = cursor.fetchall()

    # 4) بناء الرسالة
    header = {
        "ar": "💰 اختر نوع الحساب الذي ترغب بشرائه:\n\n📂 الحسابات المتاحة:\n",
        "en": "💰 Select the type of account to buy:\n\n📂 Available Accounts:\n"
    }[lang]

    lines = []
    for atype, label in [("G1", "Gmail First-Class"), ("G2", "Gmail Second-Class"),
                         ("out", "Outlook"), ("hot", "Hotmail")]:
        count = accounts.get(atype, 0)
        if lang == "ar":
            lines.append(f"🔹 {atype}: {count} حساب")
        else:
            lines.append(f"🔹 {atype}: {count} available")
    header += "\n".join(lines)

    if rates:
        header += "\n\n💱 " + ("أسعار العملات:" if lang=="ar" else "Current Currency Rates:") + "\n"
        for curr, rate in rates:
            if lang == "ar":
                header += f"🔹 1 {curr} = {rate} ليرة سورية\n"
            else:
                header += f"🔹 1 {curr} = {rate} SYP\n"

    # 5) عرض أزرار اختيار النوع
    buttons = [
        [KeyboardButton("شراء حساب Gmail درجة أولى" if lang=="ar" else "Buy Gmail First-Class")],
        [KeyboardButton("شراء حساب Gmail درجة ثانية" if lang=="ar" else "Buy Gmail Second-Class")],
        [KeyboardButton("شراء حساب Outlook" if lang=="ar" else "Buy Outlook")],
        [KeyboardButton("شراء حساب Hotmail" if lang=="ar" else "Buy Hotmail")],
        [KeyboardButton("العودة" if lang=="ar" else "Back")]
    ]

    await update.message.reply_text(
        header,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@require_not_banned
async def select_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يحوّل نص المستخدم إلى internal account_type،
    ثم يطلب منه تحديد الكمية.
    """
    text = update.message.text.strip()
    mapping = {
        "شراء حساب Gmail درجة أولى": "G1",
        "Buy Gmail First-Class": "G1",
        "شراء حساب Gmail درجة ثانية": "G2",
        "Buy Gmail Second-Class": "G2",
        "شراء حساب Outlook": "out",
        "Buy Outlook": "out",
        "شراء حساب Hotmail": "hot",
        "Buy Hotmail": "hot"
    }
    acct_type = mapping.get(text)
    if not acct_type:
        return await update.message.reply_text("❌ نوع الحساب غير معروف.")

    context.user_data["selected_account_type"] = acct_type
    lang = get_user_language(context.user_data.get("username_login"))

    prompt = "الرجاء تحديد العدد المطلوب:" if lang=="ar" else "Please choose quantity:"
    buttons = [
        [KeyboardButton("1"), KeyboardButton("3")],
        [KeyboardButton("5"), KeyboardButton("10")],
        [KeyboardButton("العودة" if lang=="ar" else "Back")]
    ]
    await update.message.reply_text(
        f"{prompt}",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@require_not_banned
async def process_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يتحقق من توفر الكمية، يحسب السعر الإجمالي،
    ثم يطلب تأكيد الشراء أو يخطِّر الأدمن بالنقص.
    """
    try:
        qty = int(update.message.text.strip())
    except ValueError:
        return await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")

    acct_type = context.user_data.get("selected_account_type")
    if not acct_type:
        return await update.message.reply_text("❌ لم يتم تحديد نوع الحساب.")

    username = context.user_data.get("username_login")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # جلب user_db_id, balance, credit, lang
        cursor.execute(
            "SELECT id, balance, credit, language FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return await update.message.reply_text("❌ خطأ في بيانات المستخدم.")
        user_db_id, balance, credit, lang = user_row

        # جلب الحسابات المتوفرة
        cursor.execute(
            "SELECT id, email, price, password, recovery FROM accounts "
            "WHERE account_type = ? ORDER BY added_time ASC LIMIT ?",
            (acct_type, qty)
        )
        available = cursor.fetchall()

    avail_cnt = len(available)
    if avail_cnt < qty:
        # نقص في المخزون
        notify = (
            f"⚠️ لا توجد سوى {avail_cnt} حساب، طلبت {qty}."
            if lang=="ar"
            else f"⚠️ Only {avail_cnt} available; you requested {qty}."
        )
        # إخطار الأدمن أيضاً
        await update.message.reply_text(notify)
        await context.bot.send_message(
            chat_id=ADMIN_ID1,
            text=(
                f"🚨 Shortage: {acct_type} – Requested {qty}, Available {avail_cnt}"
            )
        )
        return

    total_price = sum(row[2] for row in available)
    if (balance + credit) < total_price:
        msg = "❌ رصيدك غير كافٍ." if lang=="ar" else "❌ Insufficient funds."
        return await update.message.reply_text(msg)

    # حفظ معلومات الشراء مؤقتًا
    context.user_data["pending_purchase"] = {
        "user_db_id": user_db_id,
        "accounts": available,
        "total_price": total_price,
        "language": lang
    }
    confirm = (
        f"✅ سيتم خصم {total_price:.2f} ل.س لشراء {qty} حساب. موافق؟"
        if lang=="ar"
        else f"✅ {total_price:.2f} L.S will be deducted for {qty} accounts. Continue?"
    )
    buttons = [[
        KeyboardButton("تأكيد" if lang=="ar" else "Confirm"),
        KeyboardButton("إلغاء" if lang=="ar" else "Cancel")
    ]]
    await update.message.reply_text(
        confirm,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@require_not_banned
async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ينفّذ الشراء:
    - يخصم الرصيد
    - ينقل الحسابات إلى purchases (باستخدام user_id)
    - يحذفها من accounts
    """
    text = update.message.text.strip()
    pending = context.user_data.get("pending_purchase")
    if not pending:
        return  # لا هناك عملية قيد الانتظار

    lang = pending["language"]
    if text not in ("تأكيد", "Confirm"):
        context.user_data.pop("pending_purchase", None)
        return await update.message.reply_text(
            "❌ تم إلغاء العملية." if lang=="ar" else "❌ Purchase canceled."
        )

    user_db_id = pending["user_db_id"]
    accounts = pending["accounts"]
    total_price = pending["total_price"]

    # خصم الرصيد أولاً
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT balance, credit FROM users WHERE id = ? LIMIT 1",
            (user_db_id,)
        )
        bal, cred = cursor.fetchone()
        rem = total_price
        use_bal = min(bal, rem)
        bal -= use_bal
        rem -= use_bal
        cred -= rem
        cursor.execute(
            "UPDATE users SET balance = ?, credit = ? WHERE id = ?",
            (bal, cred, user_db_id)
        )

        # إدخال وتحريك الحسابات
        for acc_id, email, price, pwd, rec in accounts:
            cursor.execute(
                "INSERT INTO purchases (user_id, account_type, email, price, password, recovery) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_db_id, pending["accounts"][0][0], email, price, pwd, rec)
            )
            cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))

        conn.commit()

    context.user_data.pop("pending_purchase", None)
    done = (
        "✅ تم إتمام الشراء! استخدم /show_accounts لعرض حساباتك."
        if lang=="ar"
        else "✅ Purchase complete! Use /show_accounts to view your accounts."
    )
    await update.message.reply_text(done)

@require_not_banned
async def return_to_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context,'ar')
########################################################################################################################
@require_not_banned
async def ask_for_gift_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يدخل البوت في وضع انتظار لتحويل رصيد هدية:
    - يطلب من المستخدم إدخال @username والمبلغ
    - يخصم 1% رسماً
    """
    username = context.user_data.get("username_login")
    if not username:
        return await update.message.reply_text("❌ لم يتم العثور على اسم المستخدم في الجلسة.")

    lang = get_user_language(username)
    prompts = {
        "ar": (
            "✍️ أدخل اسم المستخدم والمبلغ لإهداء الرصيد بالشكل:\n\n"
            "`@username 5000`\n\n"
            "💡 سيتم خصم 1% رسوم تحويل."
        ),
        "en": (
            "✍️ Enter the username and amount to gift:\n\n"
            "`@username 5000`\n\n"
            "💡 A 1% transfer fee will apply."
        ),
    }

    context.user_data["current_state"] = "gift_balance"
    await update.message.reply_text(
        prompts[lang],
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@require_not_banned
async def process_gift_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج تحويل الرصيد بعد ask_for_gift_balance:
    - يتحقق من الصيغة
    - يحسب الرسوم (1%)
    - يخصم من المرسل ويضيف للمستقبل
    """
    if context.user_data.get("current_state") != "gift_balance":
        return

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: `@username 5000`", parse_mode="Markdown"
        )

    target_username = parts[0].lstrip("@")
    try:
        amount = float(parts[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(
            "❌ الصيغة غير صحيحة. مثال: `@username 5000`", parse_mode="Markdown"
        )

    sender_username = context.user_data.get("username_login")
    lang = get_user_language(sender_username)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # جلب رصيد المرسل
        cursor.execute(
            "SELECT id, balance FROM users WHERE username = ? LIMIT 1",
            (sender_username,)
        )
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text("❌ لم يتم العثور على بياناتك.")

        sender_id, sender_balance = row

        # جلب مستقبل الهدية
        cursor.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            (target_username,)
        )
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text("❌ اسم المستخدم غير مسجل.")
        recipient_id = row[0]

        fee = round(amount * 0.01, 2)
        total_cost = amount + fee

        if sender_balance < total_cost:
            context.user_data.pop("current_state", None)
            msg = "❌ رصيدك غير كافٍ لإتمام التحويل." if lang == "ar" else "❌ Insufficient balance."
            return await update.message.reply_text(msg)

        # تنفيذ التحويل
        cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (total_cost, sender_id)
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, recipient_id)
        )
        conn.commit()

    # رسائل تأكيد المرسل
    confirmations = {
        "ar": f"✅ تم إهداء {amount:.2f} ل.س إلى @{target_username} (تم خصم رسوم {fee:.2f} ل.س).",
        "en": f"✅ Successfully gifted {amount:.2f} L.S to @{target_username} (fee {fee:.2f} L.S)."
    }
    await update.message.reply_text(confirmations[lang], parse_mode="Markdown")

    # إشعار المستقبل
    notifications = {
        "ar": f"🎁 لقد استلمت {amount:.2f} ل.س من @{sender_username}!",
        "en": f"🎁 You have received {amount:.2f} L.S from @{sender_username}!"
    }
    try:
        await context.bot.send_message(chat_id=recipient_id, text=notifications[lang])
    except:
        pass

    context.user_data.pop("current_state", None)






############################################################################################################################
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
@require_not_banned
async def recharge_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض للمستخدم خيارات شحن الرصيد المتاحة بناءً على لغته،
    ويضبط current_action للانتظار إذا لزم الأمر لاحقًا.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # رسالة الاختيار حسب اللغة
    prompts = {
        "ar": "💰 اختر طريقة الدفع لشحن رصيدك:",
        "en": "💰 Select a payment method to recharge your balance:"
    }

    # تخطيط الأزرار حسب اللغة
    keyboard_ar = [
        [KeyboardButton("سيريتيل كاش"), KeyboardButton("Payeer")],
        [KeyboardButton("USDT"), KeyboardButton("CoinX")],
        [KeyboardButton("بيمو"), KeyboardButton("العودة")]
    ]
    keyboard_en = [
        [KeyboardButton("Syriatel Cash"), KeyboardButton("Payeer")],
        [KeyboardButton("USDT"), KeyboardButton("CoinX")],
        [KeyboardButton("Bemo"), KeyboardButton("Back")]
    ]

    # إرسال الرسالة
    await update.message.reply_text(
        prompts[lang],
        reply_markup=ReplyKeyboardMarkup(
            keyboard_ar if lang == "ar" else keyboard_en,
            resize_keyboard=True
        )
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
@require_not_banned
async def handle_coinx_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بعد اختيار CoinX، يطلب من المستخدم تحديد الشبكة،
    ثم يعرض عنوان المحفظة بلغة المستخدم وينتقل لانتظار txn_id.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    choice = update.message.text.strip().lower()

    networks = {
        "trc20": ("TX1234567890abcdef", "TRC20"),
        "bep20": ("0xABCDEF1234567890", "BEP20"),
        "coinx": ("coinx-wallet-0987", "كوين إكس"),
        "assent": ("assent-wallet-4567", "أسينت"),
    }

    if choice not in networks:
        err = "❌ شبكة غير معروفة." if lang == "ar" else "❌ Unknown network."
        return await update.message.reply_text(err)

    address, label_ar = networks[choice]
    label = label_ar if lang == "ar" else label_ar  # CoinX labels are identical

    prompt = (
        f"📤 الرجاء تحويل المبلغ إلى محفظة {label}:\n`{address}`\n\n🔢 ثم أرسل رقم المعاملة هنا:"
        if lang == "ar"
        else f"📤 Please transfer the amount to the {label} wallet:\n`{address}`\n\n🔢 Then send the transaction ID here:"
    )

    # اضبط الحالة لانتظار رقم المعاملة
    context.user_data["current_state"] = "awaiting_coinx_txn"
    await update.message.reply_text(prompt, parse_mode="Markdown", disable_web_page_preview=True)
@require_not_banned
async def process_coinx_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج Txn ID المرسل بعد اختيار CoinX:
    - يتحقق من عدم استخدام المعاملة مسبقاً
    - يستعلم من API عن تفاصيل الإيداع
    - يشحن رصيد المستخدم ويخزن المعاملة
    """
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    msgs = {
        "ar": {
            "confirmed": "✅ تم تأكيد المعاملة وشحن رصيدك بنجاح.",
            "exists":    "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في CoinX.",
            "error":     "⚠️ حدث خطأ أثناء الاتصال بـ CoinX. حاول مرة أخرى."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists":    "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found on CoinX.",
            "error":     "⚠️ Error connecting to CoinX. Please try again."
        }
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1) تحقق من الاستخدام السابق
        cursor.execute("SELECT 1 FROM transactions WHERE txn_id = ? LIMIT 1", (txn_id,))
        if cursor.fetchone():
            return await update.message.reply_text(msgs[lang]["exists"])

        # 2) استعلام API
        result = get_coinx_deposit_history(ACCESS_ID, SECRET_KEY, txn_id)
        if result.get("error"):
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(msgs[lang]["error"] + "\n" + result["error"])
        if not result.get("found"):
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(msgs[lang]["not_found"])

        amount = result["amount"]

        # 3) جلب معرف المستخدم من جدول users
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text("❌ خطأ داخلي: لم نعثر على حسابك.")

        user_db_id = row[0]

        # 4) تخزين المعاملة وشحن الرصيد
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, 'CoinX', ?)",
            (txn_id, user_db_id, amount)
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, user_db_id)
        )
        conn.commit()

    # 5) تأكيد للمستخدم وتنظيف الحالة
    await update.message.reply_text(f"{msgs[lang]['confirmed']}\n💰 {amount} USDT")
    context.user_data.pop("current_state", None)
@require_not_banned
async def payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض تعليمات الدفع لكل طريقة ويضبط الحالة المناسبة للانتظار.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    method = update.message.text.strip()

    # العودة للقائمة الرئيسية
    if method in ("العودة", "Back"):
        context.user_data.pop("current_action", None)
        return await main_menu(update, context, lang)

    # خريطة مبدئية لرسائل الدفع
    payment_info = {
        "ar": {
            "سيريتيل كاش":  "📌 قم بتحويل المبلغ إلى: `093XXXXXXX` ثم أرسل صورة الإيصال.",
            "Payeer":       "📌 أرسل المبلغ إلى حساب Payeer: `P1092176325`\n\n🔢 ثم أدخل رقم المعاملة هنا:",
            "USDT":         "📌 استخدم عنوان USDT TRC20: `TX1234567890abcdef` ثم أرسل Txn ID.",
            "بيمو":         "📌 قم بالتحويل إلى حساب Bemo: `BEMO-56789` ثم أرسل Txn ID والمبلغ في سطرين:",
            # CoinX يُعالج بشكل منفصل
        },
        "en": {
            "Syriatel Cash": "📌 Transfer to: `093XXXXXXX` then send the receipt image.",
            "Payeer":        "📌 Send to Payeer: `P1092176325`\n\n🔢 Then enter the Transaction ID:",
            "USDT":          "📌 Use USDT TRC20 address: `TX1234567890abcdef` then send Txn ID.",
            "Bemo":          "📌 Transfer to Bemo: `BEMO-56789` then send Txn ID and amount on two lines:",
        }
    }

    # CoinX: ننتقل لاختيار الشبكة
    if method in ("CoinX", "كوين إكس"):
        context.user_data["current_action"] = "awaiting_coinx_network"
        buttons = [
            [KeyboardButton("TRC20"), KeyboardButton("BEP20")],
            [KeyboardButton("CoinX"), KeyboardButton("Assent")],
            [KeyboardButton("العودة" if lang=="ar" else "Back")]
        ]
        prompt = "🔗 اختر شبكة التحويل:" if lang=="ar" else "🔗 Select transfer network:"
        return await update.message.reply_text(
            prompt,
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )

    # طرق الدفع الأخرى
    ar_methods = payment_info["ar"]
    en_methods = payment_info["en"]
    if lang == "ar" and method in ar_methods:
        key = method
    elif lang == "en" and method in en_methods:
        # نفصل بين "Syriatel Cash" و "سيريتيل كاش"
        key = method if lang=="en" else method
    else:
        return await update.message.reply_text(
            "❌ طريقة الدفع غير معروفة."
        )

    # حدد الحالة المنتظرة لكل طريقة
    state_map = {
        "سيريتيل كاش":    "awaiting_syriatel_txn",
        "Payeer":         "awaiting_payeer_txn",
        "USDT":           "awaiting_usdt_txn",
        "بيمو":           "awaiting_bemo_txn",
        "Syriatel Cash":  "awaiting_syriatel_txn",
        "Bemo":           "awaiting_bemo_txn"
    }
    context.user_data["current_state"] = state_map.get(method)

    # إرسال التعليمات
    text = payment_info[lang][method]
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

######################################################################3
@require_not_banned
async def process_bemo_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج رقم الحوالة والمبلغ المرسل عبر بيمو:
    - يتحقق من الصيغة (@awaiting_bemo_txn)
    - يفحص التكرار في جدول transactions
    - يرسل التفاصيل للإدارة بموافقة/رفض
    """
    # 1) تأكد أننا في الحالة الصحيحة
    if context.user_data.get("current_action") != "awaiting_bemo_txn":
        return

    text = update.message.text.strip()
    lines = text.splitlines()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    user_chat_id = update.effective_chat.id

    # 2) التحقق من الصيغة (سطرين: txn_id ثم المبلغ)
    if len(lines) < 2:
        context.user_data.pop("current_action", None)
        msg = (
            "❌ الرجاء إرسال رقم الحوالة ثم المبلغ في سطرين."
            if lang == "ar"
            else "❌ Please send the transaction ID and amount on two separate lines."
        )
        return await update.message.reply_text(msg)

    txn_id = lines[0].strip()
    try:
        amount_syp = float(lines[1].strip())
    except ValueError:
        context.user_data.pop("current_action", None)
        msg = "⚠️ المبلغ غير صحيح." if lang == "ar" else "⚠️ Invalid amount."
        return await update.message.reply_text(msg)

    # 3) فحص التكرار في قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, amount, timestamp FROM transactions WHERE txn_id = ? LIMIT 1",
            (txn_id,)
        )
        existing = cursor.fetchone()

    if existing:
        prev_user_id, prev_amount, prev_time = existing
        # جلب اسم المستخدم السابق
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE id = ? LIMIT 1", (prev_user_id,))
            row = cursor.fetchone()
        prev_username = row[0] if row else "N/A"

        # 4) تحذير الإدارة
        warn = (
            f"⚠️ <b>حوالة مكررة</b>\n\n"
            f"🔢 رقم الحوالة: <code>{txn_id}</code>\n"
            f"💰 المبلغ السابق: <b>{prev_amount:.2f}</b>\n"
            f"📅 التاريخ: <i>{prev_time}</i>\n\n"
            f"👤 شحنها سابقًا: <code>{prev_username}</code> (ID: <code>{prev_user_id}</code>)\n"
            f"🔔 محاولة جديدة من: <code>{username}</code> (ID: <code>{user_chat_id}</code>)"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID1,
            text=warn,
            parse_mode="HTML"
        )
        user_msg = (
            "⚠️ هذا الرقم تم استخدامه مسبقًا، ستتم مراجعة الإدارة."
            if lang == "ar"
            else "⚠️ This transaction ID was already used; admin will review."
        )
        context.user_data.pop("current_action", None)
        return await update.message.reply_text(user_msg)

    # 5) إرسال تفاصيل الحوالة للإدارة بالموافقة/رفض
    bemo_account = "BEMO-56789"
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ قبول", callback_data=f"bemo_accept_{user_chat_id}_{txn_id}_{amount_syp}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"bemo_reject_{user_chat_id}_{txn_id}")
    ]])
    admin_msg = (
        f"📥 <b>طلب شحن بيمو</b>\n\n"
        f"👤 المستخدم: <code>{username}</code> (Chat ID: <code>{user_chat_id}</code>)\n"
        f"📤 المحول إليه: <b>{bemo_account}</b>\n"
        f"🔢 رقم الحوالة: <code>{txn_id}</code>\n"
        f"💰 المبلغ: <b>{amount_syp:.2f}</b> SYP\n\n"
        f"⏳ في انتظار قرار الإدارة..."
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID1,
        text=admin_msg,
        parse_mode="HTML",
        reply_markup=buttons
    )

    # 6) إشعار المستخدم بالإرسال
    user_notify = (
        "✅ تم إرسال تفاصيل الحوالة للإدارة.\n⏳ سيتم الرد خلال 6 ساعات."
        if lang == "ar"
        else "✅ Transfer details sent to admin.\n⏳ Expect a response within 6 hours."
    )
    await update.message.reply_text(user_notify)
    context.user_data.pop("current_action", None)
@require_not_banned
async def bemo_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    قبول شحن بيمو:
    - يحوّل المبلغ من SYP إلى USD
    - يحدث رصيد المستخدم
    - يسجل المعاملة
    """
    query = update.callback_query
    await query.answer()

    # البيانات المرمّزة في callback_data: bemo_accept_<chat_id>_<txn_id>_<amount_syp>
    try:
        _, _, chat_id_str, txn_id, amount_syp_str = query.data.split("_", 4)
        chat_id = int(chat_id_str)
        amount_syp = float(amount_syp_str)
    except (ValueError, IndexError):
        return await query.edit_message_text("⚠️ البيانات المرسلة غير صحيحة.")

    # الخطوة 1: جلب سعر صرف SYP
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rate FROM currency_rates WHERE currency = 'SYP' LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return await query.edit_message_text("⚠️ لم يتم العثور على سعر صرف SYP.")
        rate = float(row[0])

        # الخطوة 2: حساب المبلغ بالدولار
        amount_usd = round(amount_syp / rate, 2)

        # الخطوة 3: جلب معرف المستخدم في القاعدة عبر chat_id
        cursor.execute("SELECT id FROM users WHERE chat_id = ? LIMIT 1", (chat_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return await query.edit_message_text("⚠️ لم يتم العثور على المستخدم في قاعدة البيانات.")
        user_db_id = user_row[0]

        # الخطوة 4: تحديث رصيد المستخدم
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount_usd, user_db_id)
        )

        # الخطوة 5: تسجيل المعاملة
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, ?, ?)",
            (txn_id, user_db_id, "Bemo", amount_usd)
        )

        conn.commit()

    # الخطوة 6: إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ تم تأكيد المعاملة عبر بيمو.\n💰 تم شحن رصيدك بمقدار {amount_usd} USD"
        )
    except:
        pass

    # الخطوة 7: تعديل رسالة الإدارة
    await query.edit_message_text("✅ تم شحن رصيد المستخدم بنجاح.")
@require_not_banned
async def bemo_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رفض شحن بيمو:
    - يرسل إشعارًا للمستخدم بأن الحوالة لم تُعثر
    - يعدل رسالة المسؤول لبيان الرفض
    """
    query = update.callback_query
    await query.answer()

    # استخرج chat_id ورقم الحوالة من callback_data
    try:
        _, _, chat_id_str, txn_id = query.data.split("_", 3)
        chat_id = int(chat_id_str)
    except (ValueError, IndexError):
        return await query.edit_message_text("⚠️ بيانات غير صحيحة.")

    # جلب لغة المستخدم لإرسال رسالة مناسبة
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 1) إشعار المستخدم
    user_msg = (
        f"❌ لم يتم العثور على حوالة Bemo بالرقم: {txn_id}."
        if lang == "ar"
        else f"❌ Bemo transfer not found for ID: {txn_id}."
    )
    await context.bot.send_message(chat_id, user_msg)

    # 2) تعديل رسالة المسؤول
    admin_msg = (
        "❌ تم رفض حوالة Bemo بنجاح."
        if lang == "ar"
        else "❌ Bemo transaction has been rejected."
    )
    await query.edit_message_text(admin_msg)


################################################################################################33
@require_not_banned
async def process_payeer_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج رقم المعاملة من Payeer بعد طلب رقم المعاملة:
    - يتأكد من عدم استخدام txn_id مسبقاً
    - يستدعي get_recent_payeer_transactions للتحقق من وجود المعاملة
    - يشحن رصيد المستخدم إذا وُجدت المعاملة ويسجلها
    """
    
    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    msgs = {
        "ar": {
            "confirmed": "✅ تم تأكيد الدفع وشحن رصيدك.",
            "exists":    "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في Payeer.",
            "error":     "⚠️ حدث خطأ أثناء التحقق من Payeer."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists":    "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Payeer.",
            "error":     "⚠️ Error while checking Payeer."
        }
    }

    # 2) افتح اتصال بقاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 3) تحقق من الاستخدام المسبق
        cursor.execute("SELECT 1 FROM transactions WHERE txn_id = ? LIMIT 1", (txn_id,))
        if cursor.fetchone():
            return await update.message.reply_text(msgs[lang]["exists"])

        # 4) جلب بيانات Payeer
        try:
            payeer_data = get_recent_payeer_transactions()
        except Exception as e:
            print("[ERROR] Payeer API check:", e)
            return await update.message.reply_text(msgs[lang]["error"])

        amount = payeer_data.get(txn_id)
        if amount is None:
            return await update.message.reply_text(msgs[lang]["not_found"])

        # 5) جلب معرف المستخدم من جدول users
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            return await update.message.reply_text("❌ خطأ داخلي: لم نعثر على حسابك.")
        user_db_id = user_row[0]

        # 6) تسجيل المعاملة وشحن الرصيد
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, 'Payeer', ?)",
            (txn_id, user_db_id, float(amount))
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (float(amount), user_db_id)
        )
        conn.commit()

    # 7) إرسال رسالة تأكيد للمستخدم
    await update.message.reply_text(
        f"{msgs[lang]['confirmed']}\n💰 {amount:.2f} USD",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    # 8) تنظيف الحالة
    context.user_data.pop("current_state", None)
@require_not_banned
async def process_syriatel_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج رقم المعاملة من Syriatel Cash:
    - يتحقّق من الحالة الحالية
    - يفحص التكرار في جدول transactions
    - يستدعي get_recent_syriatel_transactions()
    - يحوّل SYP إلى USD
    - يحدث رصيد المستخدم ويسجل المعاملة
    """
 

    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    msgs = {
        "ar": {
            "confirmed": "✅ تم تأكيد المعاملة وشحن رصيدك.",
            "exists":    "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في Syriatel Cash.",
            "rate_error":"⚠️ لم يتم العثور على سعر صرف SYP.",
            "error":     "⚠️ حدث خطأ أثناء التحقق من المعاملات."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists":    "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Syriatel Cash.",
            "rate_error":"⚠️ SYP exchange rate not found.",
            "error":     "⚠️ Error while checking transactions."
        }
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 2) فحص التكرار
        cursor.execute("SELECT 1 FROM transactions WHERE txn_id = ? LIMIT 1", (txn_id,))
        if cursor.fetchone():
            return await update.message.reply_text(msgs[lang]["exists"])

        try:
            # 3) جلب معاملات Syriatel الأخيرة
            transactions = get_recent_syriatel_transactions()
            amount_syp = transactions.get(txn_id)
        except Exception:
            return await update.message.reply_text(msgs[lang]["error"])

        if not amount_syp:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(msgs[lang]["not_found"])

        # 4) جلب سعر صرف SYP
        cursor.execute("SELECT rate FROM currency_rates WHERE currency = 'SYP' LIMIT 1")
        row = cursor.fetchone()
        if not row:
            context.user_data.pop("current_state", None)
            return await update.message.reply_text(msgs[lang]["rate_error"])

        rate = float(row[0])
        amount_usd = round(float(amount_syp) / rate, 2)

        # 5) تحديث رصيد المستخدم وتسجيل المعاملة
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            return await update.message.reply_text("❌ خطأ داخلي: لم نعثر على حسابك.")

        user_db_id = user_row[0]
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount_usd, user_db_id)
        )
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, 'Syriatel Cash', ?)",
            (txn_id, user_db_id, amount_usd)
        )
        conn.commit()

    # 6) تأكيد الرسالة وتنظيف الحالة
    await update.message.reply_text(
        f"{msgs[lang]['confirmed']}\n💰 {amount_usd} USD",
        parse_mode="Markdown"
    )
    context.user_data.pop("current_state", None)

@require_not_banned
async def process_payeer_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج رقم المعاملة المرسل بعد اختيار Payeer:
    - يتحقق من الحالة (awaiting_payeer_txn)
    - يتأكد من أن txn_id لم يستخدم من قبل
    - يستدعي get_recent_payeer_transactions للتحقق من وجود المعاملة ومقدارها
    - يشحن رصيد المستخدم ويسجل المعاملة
    """


    txn_id = update.message.text.strip()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    messages = {
        "ar": {
            "confirmed": "✅ تم تأكيد الدفع وشحن رصيدك.",
            "exists":    "⚠️ هذا الرقم تم استخدامه مسبقاً.",
            "not_found": "❌ لم يتم العثور على رقم المعاملة في Payeer.",
            "error":     "⚠️ حدث خطأ أثناء الاتصال بـ Payeer."
        },
        "en": {
            "confirmed": "✅ Transaction confirmed and your balance has been recharged.",
            "exists":    "⚠️ This transaction ID has already been used.",
            "not_found": "❌ Transaction ID not found in Payeer.",
            "error":     "⚠️ Error while contacting Payeer API."
        }
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 2) تحقق من الاستخدام المسبق
        cursor.execute("SELECT 1 FROM transactions WHERE txn_id = ? LIMIT 1", (txn_id,))
        if cursor.fetchone():
            await update.message.reply_text(messages[lang]["exists"])
            context.user_data.pop("current_state", None)
            return

        # 3) جلب تاريخ المعاملات من Payeer
        try:
            history = get_recent_payeer_transactions()
        except Exception as e:
            print("[ERROR] Payeer API:", e)
            await update.message.reply_text(messages[lang]["error"])
            context.user_data.pop("current_state", None)
            return

        amount = history.get(txn_id)
        if amount is None:
            await update.message.reply_text(messages[lang]["not_found"])
            context.user_data.pop("current_state", None)
            return

        # 4) جلب معرف المستخدم الداخلي
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        row = cursor.fetchone()
        if not row:
            await update.message.reply_text("❌ خطأ داخلي: لم نعثر على حسابك.")
            context.user_data.pop("current_state", None)
            return
        user_db_id = row[0]

        # 5) تسجيل المعاملة وشحن الرصيد
        cursor.execute(
            "INSERT INTO transactions (txn_id, user_id, method, amount) VALUES (?, ?, 'Payeer', ?)",
            (txn_id, user_db_id, float(amount))
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (float(amount), user_db_id)
        )
        conn.commit()

    # 6) الإشعار للمستخدم وتنظيف الحالة
    await update.message.reply_text(
        f"{messages[lang]['confirmed']}\n💰 {float(amount):.2f} USD",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    context.user_data.pop("current_state", None)

###############################################################################################3
@require_not_banned
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ينفّذ شراء الحسابات المعلقة في pending_purchase:
    - يخصم الرصيد (balance ثم credit)
    - ينقل الحسابات إلى purchases باستخدام user_id
    - يحذفها من accounts
    - يضيف مكافأة إحالة للداعي (10%)
    """
    pending = context.user_data.get("pending_purchase")
    if not pending:
        return await update.message.reply_text("❌ لا توجد عملية شراء معلقة.")

    qty         = pending["quantity"]
    acct_type   = pending["account_type"]
    total_price = pending["total_price"]
    username    = context.user_data.get("username_login")

    # جلب بيانات المستخدم
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, balance, credit, language, referrer_id "
            "FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return await update.message.reply_text("❌ خطأ: لم نعثر على حسابك.")
        user_db_id, balance, credit, lang, referrer_id = row

        # تحقق من كفاية الرصيد
        if balance + credit < total_price:
            return await update.message.reply_text("❌ رصيدك غير كافٍ لإتمام العملية.")

        # خصم الرصيد: أولاً balance ثم credit
        rem = total_price
        use_bal = min(balance, rem)
        balance -= use_bal
        rem     -= use_bal
        credit  = max(0, credit - rem)

        cursor.execute(
            "UPDATE users SET balance = ?, credit = ? WHERE id = ?",
            (balance, credit, user_db_id)
        )

        # جلب الحسابات المراد شراؤها
        cursor.execute(
            "SELECT id, email, password, recovery, price "
            "FROM accounts WHERE account_type = ? ORDER BY added_time ASC LIMIT ?",
            (acct_type, qty)
        )
        to_buy = cursor.fetchall()
        if len(to_buy) < qty:
            return await update.message.reply_text("❌ عفواً، الكمية المطلوبة لم تعد متوفرة.")

        # نقل كل حساب إلى جدول purchases وحذفه من accounts
        purchase_msgs = ["✅ تم الشراء بنجاح! إليك حساباتك:\n"]
        for acc_id, email, pwd, rec, unit_price in to_buy:
            cursor.execute(
                "INSERT INTO purchases (user_id, account_type, email, price, password, recovery) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_db_id, acct_type, email, unit_price, pwd, rec)
            )
            cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
            purchase_msgs.append(
                f"📧 {email}\n🔑 {pwd}\n📩 {rec}\n"
            )

        # مكافأة إحالة 10%
        if referrer_id:
            bonus = round(total_price * 0.10, 2)
            cursor.execute(
                "UPDATE users SET credit = credit + ? WHERE id = ?",
                (bonus, referrer_id)
            )

        conn.commit()

    # تنظيف الحالة
    context.user_data.pop("pending_purchase", None)

    # ربط الرسالة وتحويل للقائمة الرئيسية
    await update.message.reply_text(
        "\n".join(purchase_msgs),
        parse_mode="HTML"
    )
    await main_menu(update, context, lang)

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
    يعالج طلب استرجاع حساب:
    - يتحقق من الحالة (awaiting_refund)
    - يستخدم user_id الداخلي بدل chat_id
    - يتأكد من صلاحية المدة حسب النوع
    - يعلّم الطلب في purchases
    - يرسل للأدمن أزرار قبول/رفض
    """

    email = update.message.text.strip()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 2) جلب معرف المستخدم الداخلي
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            return await update.message.reply_text(
                "❌ خطأ: لم نعثر على حسابك." if lang=="ar" else "❌ Error: your account was not found."
            )
        user_db_id = user_row[0]

        # 3) جلب بيانات الشراء لهذا المستخدم والإيميل
        cursor.execute(
            "SELECT id, account_type, purchase_time, refund_requested "
            "FROM purchases WHERE email = ? AND user_id = ? LIMIT 1",
            (email, user_db_id)
        )
        purchase = cursor.fetchone()

    if not purchase:
        msg = (
            "❌ لم يتم العثور على هذا البريد في مشترياتك."
            if lang=="ar" else
            "❌ This email was not found in your purchases."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    purchase_id, acct_type, purchase_time, already_requested = purchase
    # 4) تحقق من تقديم طلب سابق
    if already_requested:
        msg = (
            "⚠️ تم تقديم طلب استرجاع مسبقاً لهذا الحساب."
            if lang=="ar" else
            "⚠️ Refund request has already been submitted for this account."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    # 5) تحقق من صلاحية المدة
    try:
        dt = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        msg = (
            "❌ خطأ في بيانات وقت الشراء."
            if lang=="ar" else
            "❌ Purchase time format error."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    days_allowed = 3 if acct_type == "G1" else 1
    if (datetime.now() - dt).days >= days_allowed:
        msg = (
            "⏳ انتهت المدة المسموح بها للاسترجاع."
            if lang=="ar" else
            "⏳ Refund period has expired."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    # 6) علّم طلب الاسترجاع في قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE purchases SET refund_requested = 1 WHERE id = ?",
            (purchase_id,)
        )
        conn.commit()

    # 7) أرسل إشعاراً للأدمن مع أزرار قبول/رفض
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ قبول",
                callback_data=f"accept_refund_{user_db_id}_{purchase_id}"
            ),
            InlineKeyboardButton(
                "❌ رفض",
                callback_data=f"reject_refund_{user_db_id}_{purchase_id}"
            )
        ]
    ])
    admin_text = (
        f"🔔 طلب استرجاع حساب\n"
        f"👤 المستخدم (ID): <code>{user_db_id}</code>\n"
        f"📧 البريد: <code>{email}</code>\n"
        f"📅 الشراء: <i>{purchase_time}</i>"
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID1,
        text=admin_text,
        parse_mode="HTML",
        reply_markup=kb
    )

    # 8) أرسل تأكيداً للمستخدم
    user_msg = (
        "♻️ تم تقديم طلب الاسترجاع بنجاح! في انتظار موافقة الإدارة."
        if lang=="ar" else
        "♻️ Refund request submitted successfully! Awaiting admin approval."
    )
    await update.message.reply_text(user_msg)

    # 9) نظِّف الحالة
    context.user_data.pop("current_state", None)

@require_not_banned
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج الاستعلامات الداخلية:
    - "buy_1_<type>": يعرض حتى 50 حساباً من النوع المحدد مع إخفاء جزء من الإيميل
    - "" (فارغ): يعرض حسابات المستخدم المؤهلة للاسترجاع
    """
    query = update.inline_query
    text = query.query.strip()
    results = []

    # شراء حساب واحد: inline query يبدأ بـ "buy_1_"
    if text.startswith("buy_1_"):
        acct_type = text.replace("buy_1_", "", 1)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email, price FROM accounts "
                "WHERE account_type = ? ORDER BY added_time ASC LIMIT 50",
                (acct_type,)
            )
            rows = cursor.fetchall()

        if not rows:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ لا يوجد حسابات متاحة",
                    input_message_content=InputTextMessageContent("❌ لا يوجد حسابات حالياً.")
                )
            )
        else:
            for email, price in rows:
                local, domain = email.split("@", 1)
                hidden = (local[:-4] + "****") if len(local) > 4 else ("****" + local[-1])
                title = f"{hidden}@{domain} – {price:.2f} ل.س ({acct_type})"
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=title,
                        input_message_content=InputTextMessageContent(f"/buy_account {email}")
                    )
                )

    # استعلام الاسترجاع (فراغ): يدرج حسابات المستخدم المؤهلة
    elif text == "":
        username = context.user_data.get("username_login")
        lang = get_user_language(username)
        now = datetime.now()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,))
            row = cursor.fetchone()
            if not row:
                purchases = []
            else:
                user_db_id = row[0]
                cursor.execute(
                    "SELECT id, account_type, email, purchase_time "
                    "FROM purchases WHERE user_id = ? AND refund_requested = 0",
                    (user_db_id,)
                )
                purchases = cursor.fetchall()

        for purchase_id, acct_type, email, purchase_time in purchases:
            dt = datetime.strptime(purchase_time, "%Y-%m-%d %H:%M:%S")
            period = 3 if acct_type == "G1" else 1
            if (now - dt).days >= period:
                continue

            if email.endswith("@gmail.com"):
                if not await check_gmail_account(email):
                    continue

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"♻️ استرجاع {email}",
                    input_message_content=InputTextMessageContent(f"/request_refund {email}")
                )
            )

        if not results:
            no_refund = (
                "❌ لا يوجد لديك حسابات قابلة للاسترجاع."
                if lang == "ar" else
                "❌ You have no accounts eligible for refund."
            )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=no_refund,
                    input_message_content=InputTextMessageContent(no_refund)
                )
            )

    else:
        # تجاهل أي استعلامات أخرى
        return

    await query.answer(results[:50], cache_time=0)




@require_not_banned
async def request_refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تنفيذ طلب استرجاع الحساب:
    - يتلقى '/request_refund <purchase_id> <email>'
    - يتحقق من أن الشراء يخص المستخدم (باستخدام user_id داخلي)
    - يمنع التكرار
    - يعلّم refund_requested
    - يرسل للأدمن زر قبول/رفض
    """
    text = update.message.text.strip()
    if not text.startswith("/request_refund"):
        return

    parts = text.split()
    if len(parts) != 3:
        return await update.message.reply_text(
            "❌ صيغة خاطئة. استخدم: /request_refund <purchase_id> <email>"
        )
    _, purchase_id_str, email = parts

    # تحقق من صحة purchase_id
    try:
        purchase_id = int(purchase_id_str)
    except ValueError:
        return await update.message.reply_text("❌ رقم الطلب غير صالح.")

    # جلب user_id الداخلي ولغة المستخدم
    username = context.user_data.get("username_login")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, language FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return await update.message.reply_text("❌ خطأ داخلي: لم نعثر على حسابك.")
        user_db_id, lang = user_row

        # تحقق أن هذا الطلب يخص المستخدم ولم يُطلب استرجاعه قبل
        cursor.execute(
            "SELECT refund_requested FROM purchases WHERE id = ? AND user_id = ? LIMIT 1",
            (purchase_id, user_db_id)
        )
        purchase_row = cursor.fetchone()
        if not purchase_row:
            msg = (
                "❌ هذا الحساب ليس من مشترياتك."
                if lang == "ar"
                else "❌ This purchase does not belong to you."
            )
            return await update.message.reply_text(msg)
        if purchase_row[0] == 1:
            msg = (
                "⚠️ لقد أرسلت طلب استرجاع مسبقًا لهذا الحساب."
                if lang == "ar"
                else "⚠️ You have already submitted a refund request for this account."
            )
            return await update.message.reply_text(msg)

        # علّم طلب الاسترجاع
        cursor.execute(
            "UPDATE purchases SET refund_requested = 1 WHERE id = ?",
            (purchase_id,)
        )
        conn.commit()

    # إرسال طلب الاسترجاع للأدمن مع أزرار قبول/رفض
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ قبول", callback_data=f"accept_refund_{user_db_id}_{purchase_id}"
            ),
            InlineKeyboardButton(
                "❌ رفض", callback_data=f"reject_refund_{user_db_id}_{purchase_id}"
            )
        ]
    ])
    admin_text = (
        f"🔔 طلب استرجاع حساب\n"
        f"👤 المستخدم (ID): <code>{user_db_id}</code>\n"
        f"📧 البريد: <code>{email}</code>\n"
        f"🆔 رقم الطلب: <code>{purchase_id}</code>"
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID1,
        text=admin_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    # تأكيد الإرسال للمستخدم
    confirmation = (
        "📩 تم إرسال طلب الاسترجاع إلى الإدارة للمراجعة."
        if lang == "ar"
        else "📩 Your refund request has been sent to admin for review."
    )
    await update.message.reply_text(confirmation)

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
@require_not_banned
async def accept_refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    قبول طلب استرجاع:
    - يفك الـ callback_data لاستخراج user_db_id و purchase_id و email
    - يتحقق من وجود السجل في purchases
    - يعيد سعر الحساب إلى رصيد المستخدم
    - يسجل العملية في refunded_accounts
    - يحذف السجل من purchases
    - يرسل تفاصيل الحساب إلى المستخدم الفعلي (باستخدام chat_id من users)
    """
    query = update.callback_query
    await query.answer()

    # callback_data متوقع: "accept_refund_{user_db_id}_{purchase_id}_{email}"
    parts = query.data.split("_", 3)
    if len(parts) < 4:
        return await query.edit_message_text("⚠️ بيانات الطلب غير صحيحة.")
    _, _, user_db_id_str, rest = parts
    try:
        purchase_id_str, email = rest.split("_", 1)
        user_db_id = int(user_db_id_str)
        purchase_id = int(purchase_id_str)
    except ValueError:
        return await query.edit_message_text("⚠️ بيانات الطلب غير صحيحة.")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # جلب تفاصيل الشراء
        cursor.execute(
            "SELECT email, password, recovery, price FROM purchases "
            "WHERE id = ? AND user_id = ? LIMIT 1",
            (purchase_id, user_db_id)
        )
        row = cursor.fetchone()
        if not row:
            return await query.edit_message_text(f"❌ الحساب {email} غير موجود أو تم استرجاعه بالفعل.")

        email_db, pwd, recov, price = row

        # جلب chat_id لإرسال الرسالة للمستخدم
        cursor.execute("SELECT chat_id FROM users WHERE id = ? LIMIT 1", (user_db_id,))
        chat_row = cursor.fetchone()
        if not chat_row:
            return await query.edit_message_text("❌ لم يتم العثور على المستخدم لإرسال الرسالة.")
        chat_id = chat_row[0]

        # إعادة الرصيد إلى المستخدم
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (price, user_db_id)
        )
        # تسجيل في refunded_accounts
        cursor.execute(
            "INSERT INTO refunded_accounts (chat_id, email, password, recovery, price, refund_time) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (chat_id, email_db, pwd, recov, price)
        )
        # حذف من purchases
        cursor.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
        conn.commit()

    # إشعار المستخدم
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ تم قبول طلب استرجاع الحساب!\n\n"
            f"📧 البريد: {email_db}\n"
            f"🔑 كلمة المرور: {pwd}\n"
            f"📩 الايميل الاحتياطي: {recov}\n"
            f"💰 المبلغ المسترد: {price:.2f} ل.س"
        )
    )

    # تعديل رسالة الأدمن لبيان القبول
    await query.edit_message_text(f"🔔 تم قبول طلب الاسترجاع للحساب: {email_db}.")
@require_not_banned
async def reject_refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رفض طلب استرجاع:
    - يلغي علامة `refund_requested` في purchases
    - يخطر المستخدم بالرفض
    - يعدل رسالة الأدمن
    """
    query = update.callback_query
    await query.answer()

    # callback_data: "reject_refund_<user_db_id>_<purchase_id>"
    parts = query.data.split("_", 3)
    if len(parts) < 4:
        return await query.edit_message_text("⚠️ بيانات الطلب غير صحيحة.")
    _, _, user_db_id_str, purchase_id_str = parts

    try:
        user_db_id = int(user_db_id_str)
        purchase_id = int(purchase_id_str)
    except ValueError:
        return await query.edit_message_text("⚠️ بيانات الطلب غير صحيحة.")

    # 1) إعادة حالة refund_requested إلى 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE purchases SET refund_requested = 0 "
            "WHERE id = ? AND user_id = ?",
            (purchase_id, user_db_id)
        )
        # جلب chat_id ولغة المستخدم لإرسال الإشعار
        cursor.execute(
            "SELECT chat_id, language FROM users WHERE id = ? LIMIT 1",
            (user_db_id,)
        )
        user_row = cursor.fetchone()
        conn.commit()

    if user_row:
        chat_id, lang = user_row
        # 2) إخطار المستخدم بالرفض
        user_msg = (
            f"❌ تم رفض طلب استرجاع الحساب (ID: {purchase_id}).\n⚠️ الحساب لا يزال صالحاً."
            if lang == "ar"
            else
            f"❌ Your refund request (ID: {purchase_id}) was rejected.\n⚠️ The account remains active."
        )
        try:
            await context.bot.send_message(chat_id, user_msg)
        except:
            pass

    # 3) تعديل رسالة الأدمن لبيان الرفض
    await query.edit_message_text("🔔 تم رفض طلب الاسترجاع بنجاح.")

#######################################################3
@require_not_banned
async def show_about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض معلومات حول البوت مع خيارات FAQ وContact Support والعودة.
    """
    # 1) جلب اسم المستخدم واللغة
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 2) إعداد الأزرار والنص حسب اللغة
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

    # 3) عرض القائمة
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

@require_not_banned
async def show_about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض قائمة 'حول البوت' مع خيارات FAQ وContact Support والعودة.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    if lang == "ar":
        text = "ℹ️ اختر أحد الخيارات:"
        buttons = [
            [KeyboardButton("📄 الأسئلة الشائعة"), KeyboardButton("📞 تواصل مع الدعم")],
            [KeyboardButton("العودة")]
        ]
    else:
        text = "ℹ️ Please choose an option:"
        buttons = [
            [KeyboardButton("📄 FAQ"), KeyboardButton("📞 Contact Support")],
            [KeyboardButton("Back")]
        ]

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )

@require_not_banned
async def contact_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يرسل زرًا للتواصل مع الأدمن عبر رابط تليجرام.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)
    ADMIN_USERNAME = 'A5K68R'
    admin_username = ADMIN_USERNAME  # مثال: "A5K68R" بدون "@"
    url = f"https://t.me/{admin_username}"

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
    """
    يعرض الأسئلة الشائعة (FAQ) باللغة المناسبة.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    if lang == "ar":
        faq_text = (
            "📄 *الأسئلة الشائعة:*\n\n"
            "❓ *ما هي فائدة البوت؟*\n"
            "✅ يساعدك البوت على شراء حسابات وإدارة طلباتك بسهولة.\n\n"
            "❓ *ما هو عمل البوت؟*\n"
            "✅ يعرض أنواع الحسابات المتاحة ويتيح الشراء، الاسترجاع، وفك الحساب.\n\n"
            "❓ *هل يمكن استرجاع الرصيد؟*\n"
            "✅ نعم، يمكنك طلب استرجاع خلال فترة محددة إذا واجهت مشكلة.\n\n"
            "❓ *كيف أتواصل مع الدعم؟*\n"
            "✅ اضغط على \"📞 تواصل مع الدعم\" في قائمة 'حول البوت'."
        )
    else:
        faq_text = (
            "📄 *Frequently Asked Questions:*\n\n"
            "❓ *What is the benefit of this bot?*\n"
            "✅ It helps you purchase accounts and manage your requests easily.\n\n"
            "❓ *What does the bot do?*\n"
            "✅ Shows available account types and allows purchase, refunds, and unlocks.\n\n"
            "❓ *Can I get a refund?*\n"
            "✅ Yes, you can request a refund within a limited period if you face issues.\n\n"
            "❓ *How do I contact support?*\n"
            "✅ Tap \"📞 Contact Support\" in the 'About Bot' menu."
        )

    await update.message.reply_text(faq_text, parse_mode="Markdown", disable_web_page_preview=True)

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

    await update.message.reply_text(f"📧 تم إنشاء بريد وهمي لك: {email}\n\n📭 سيتم إعلامك عند وصول أول رسالة.")

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
    """
    يعرض أسعار فك الحسابات (Gmail, Hotmail, Outlook) باللغة المناسبة،
    ويضبط الحالة لانتظار اختيار المستخدم.
    """
    # 1) جلب اسم المستخدم واللغة
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 2) جلب الأسعار من قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT type, price FROM unlock_prices WHERE type IN (?, ?, ?)",
            ("gmail", "hotmail", "outlook")
        )
        rows = cursor.fetchall()
    prices = {t: p for t, p in rows}
    gmail_price = prices.get("gmail", 0.0)
    hotmail_price = prices.get("hotmail", 0.0)
    outlook_price = prices.get("outlook", 0.0)

    # 3) إعداد الرسالة والأزرار حسب اللغة
    if lang == "ar":
        text = (
            "🔓 اختر نوع الحساب الذي تريد فكه:\n\n"
            f"📧 Gmail: {gmail_price} ل.س\n"
            f"🔥 Hotmail: {hotmail_price} ل.س\n"
            f"📨 Outlook: {outlook_price} ل.س"
        )
        options = ["Gmail", "Hotmail", "Outlook", "العودة"]
    else:
        text = (
            "🔓 Choose the type of account to unlock:\n\n"
            f"📧 Gmail: {gmail_price} SYP\n"
            f"🔥 Hotmail: {hotmail_price} SYP\n"
            f"📨 Outlook: {outlook_price} SYP"
        )
        options = ["Gmail", "Hotmail", "Outlook", "Back"]

    keyboard = [[KeyboardButton(opt)] for opt in options]

    # 4) حدد الحالة للانتظار
    context.user_data["current_action"] = "awaiting_unlock_choice"

    # 5) أرسل الرسالة مع لوحة الأزرار
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

def get_user_balance(username: str) -> tuple[float, float]:
    """
    يعيد الرصيد المتاح (balance) ورصيد الإحالة (credit) للمستخدم 
    بناءً على اسم المستخدم، مع تعويض القيم None بــ 0.0.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT balance, credit FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()

    if not row:
        return 0.0, 0.0

    balance, credit = row
    return (balance or 0.0), (credit or 0.0)


def get_user_language(username: str) -> str:
    """
    يعيد اللغة المخزنة للمستخدم (ar أو en) بناءً على اسم المستخدم.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT language FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()

    if not row or not row[0]:
        return "ar"
    return row[0]
# === اختيار نوع الحساب للفك ===

@require_not_banned
async def unlock_account_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يطلب من المستخدم اختيار نوع البريد لفك الحساب،
    ثم ينتقل لانتظار بيانات الاعتماد.
    """
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 1) إعداد رسالة الاختيار
    prompts = {
        "ar": "🔓 اختر نوع الحساب الذي تريد فكه:\n1️⃣ Gmail\n2️⃣ Hotmail\n3️⃣ Outlook",
        "en": "🔓 Choose the account type to unlock:\n1️⃣ Gmail\n2️⃣ Hotmail\n3️⃣ Outlook"
    }
    buttons_ar = [["Gmail"], ["Hotmail"], ["Outlook"], ["العودة"]]
    buttons_en = [["Gmail"], ["Hotmail"], ["Outlook"], ["Back"]]

    await update.message.reply_text(
        prompts[lang],
        reply_markup=ReplyKeyboardMarkup(
            buttons_ar if lang=="ar" else buttons_en,
            resize_keyboard=True
        )
    )

    # 2) اضبط الحالة للانتظار
    context.user_data["current_state"] = "awaiting_unlock_type"


@require_not_banned
async def process_unlock_email(update: Update, context: ContextTypes.DEFAULT_TYPE):

    account_type = update.message.text.strip().lower()
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 2) تحقق من صحة النوع
    if account_type not in ("gmail", "hotmail", "outlook"):
        # أعد الطلب إذا كان خاطئًا
        msg = (
            "❌ اختر نوعًا صحيحًا: Gmail, Hotmail أو Outlook"
            if lang=="ar" else
            "❌ Please choose a valid type: Gmail, Hotmail or Outlook"
        )
        return await update.message.reply_text(msg)

    # 3) خزن النوع وانتقل لانتظار الإيميل وكلمة المرور
    context.user_data["unlock_type"] = account_type
    context.user_data["current_state"] = "awaiting_unlock_credentials"

    prompt = (
        "✉️ أرسل البريد وكلمة المرور في سطرين:\n\nexample@gmail.com\nmypassword123"
        if lang=="ar" else
        "✉️ Please send email and password on two lines:\n\nexample@gmail.com\nmypassword123"
    )
    await update.message.reply_text(prompt)


@require_not_banned
async def finalize_unlock_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
 
    text = update.message.text.strip()
    parts = text.split("\n", 1)
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    # 2) تحقق من الصيغة (سطرين)
    if len(parts) != 2:
        err = (
            "❌ الرجاء إرسال البريد وكلمة المرور كل في سطر منفصل."
            if lang=="ar" else
            "❌ Please send email and password on separate lines."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(err)

    email, password = parts[0].strip(), parts[1].strip()
    acct_type = context.user_data.get("unlock_type")

    # 3) جلب الرصيد
    balance, credit = get_user_balance(username)

    # 4) جلب السعر من قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT price FROM unlock_prices WHERE type = ? LIMIT 1",
            (acct_type,)
        )
        row = cursor.fetchone()
    price = row[0] if row else 0.0

    # 5) تحقق من كفاية الرصيد
    if balance + credit < price:
        msg = (
            "❌ رصيدك غير كافٍ لإتمام العملية."
            if lang=="ar" else
            "❌ Insufficient balance to complete the operation."
        )
        context.user_data.pop("current_state", None)
        return await update.message.reply_text(msg)

    # 6) أرسل تأكيد الاستلام للمستخدم
    wait_msg = (
        "⌛️ تم استلام طلبك. يرجى انتظار مراجعة الإدارة..."
        if lang=="ar" else
        "⌛️ Your request has been received. Please wait for admin review..."
    )
    await update.message.reply_text(wait_msg)

    # 7) أرسل طلب الأدمن مع أزرار Confirm/Reject
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ تأكيد فك الحساب",
            callback_data=f"unlock_confirm_{username}_{acct_type}_{email}"
        ),
        InlineKeyboardButton(
            "❌ رفض الطلب",
            callback_data=f"unlock_reject_{username}_{acct_type}_{email}"
        )
    ]])
    admin_msg = (
        f"🔔 طلب فك حساب جديد\n\n"
        f"👤 المستخدم: @{username}\n"
        f"📧 الإيميل: `{email}`\n"
        f"🔑 كلمة المرور: `{password}`\n"
        f"📦 النوع: {acct_type.title()}\n"
        f"💰 السعر: {price:.2f} ل.س"
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID1,
        text=admin_msg,
        parse_mode="Markdown",
        reply_markup=buttons
    )

    # 8) نظف الحالة
    context.user_data.pop("current_state", None)
    context.user_data.pop("unlock_type", None)









@require_not_banned
async def handle_unlock_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    # 1) فك البيانات من callback_data
    parts = query.data.split("_", 4)
    if len(parts) != 5:
        return await query.edit_message_text("⚠️ بيانات الطلب غير صحيحة.")
    _, _, target_username, acct_type, email = parts

    # 2) جلب السعر من قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT price FROM unlock_prices WHERE type = ? LIMIT 1",
            (acct_type,)
        )
        row = cursor.fetchone()
        if not row:
            return await query.edit_message_text("⚠️ نوع الحساب غير موجود.")
        price = row[0]

        # 3) جلب رصيد المستخدم
        cursor.execute(
            "SELECT balance FROM users WHERE username = ? LIMIT 1",
            (target_username,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return await query.edit_message_text(f"❌ المستخدم @{target_username} غير موجود.")
        balance = user_row[0] or 0.0

        # 4) التحقق من كفاية الرصيد
        if balance < price:
            # إخطار الإدارة والمستخدم
            await query.edit_message_text("❌ رصيد المستخدم غير كافٍ لفك الحساب.")
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"❌ لم يتم تنفيذ فك الحساب لـ `{email}` بسبب نقص الرصيد."
            )
            return

        # 5) خصم السعر وتحديث القاعدة
        new_balance = balance - price
        cursor.execute(
            "UPDATE users SET balance = ? WHERE username = ?",
            (new_balance, target_username)
        )
        conn.commit()

    # 6) إخطار المستخدم بنجاح العملية
    lang = get_user_language(target_username)
    user_msg = (
        f"✅ تم فك الحساب بنجاح! 📧 {email}"
        if lang == "ar"
        else f"✅ Your account has been unlocked successfully! 📧 {email}"
    )
    # البحث عن chat_id لتبليغ المستخدم
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM users WHERE username = ? LIMIT 1", (target_username,))
        chat_row = cursor.fetchone()
    if chat_row:
        await context.bot.send_message(chat_id=chat_row[0], text=user_msg)

    # 7) تعديل رسالة الأدمن لتأكيد النجاح
    await query.edit_message_text(
        f"✅ تم تأكيد فك `{email}` وخصم {price:.2f} ل.س من @{target_username}."
    )

# === عند ضغط الأدمن "رفض" ===
@require_not_banned
async def handle_unlock_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, _, user_id, email = query.data.split("_", 3)
        user_id = int(user_id)
        username = context.user_data.get("username_login")
        lang = get_user_language(username)

        msg = (
            f"❌ تم رفض طلب فك الحساب للإيميل: {email}.\nيرجى التأكد من البيانات أو التواصل مع الإدارة."
            if lang == "ar"
            else f"❌ Your unlock request for {email} was rejected.\nPlease check your data or contact support."
        )

        await context.bot.send_message(chat_id=user_id, text=msg)
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
async def ask_for_unlock_price_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يهيئ حالة انتظار تحديث أسعار فك الحساب للأدمن، ثم يطلب إرسال القائمة.
    """
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الخيار.")
    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    prompt = (
        "✍️ أرسل الأسعار بالشكل التالي (نوع: سعر):\n"
        "gmail: 100\n"
        "hotmail: 150\n"
        "outlook: 200"
        if lang == "ar"
        else
        "✍️ Send new prices in `type: price` format:\n"
        "gmail: 100\n"
        "hotmail: 150\n"
        "outlook: 200"
    )
    context.user_data["current_action"] = "awaiting_unlock_price_update"
    await update.message.reply_text(prompt, parse_mode="Markdown")


@require_not_banned
async def process_unlock_price_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_id = update.effective_chat.id
    if user_id not in (ADMIN_ID, ADMIN_ID1):
        context.user_data.pop("current_state", None)
        return await update.message.reply_text("🚫 لا تملك الصلاحية لاستخدام هذا الخيار.")

    username = context.user_data.get("username_login")
    lang = get_user_language(username)

    lines = update.message.text.strip().splitlines()
    updated, failed = [], []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for line in lines:
            parts = line.split(":", 1)
            if len(parts) != 2:
                failed.append(line)
                continue
            acct_type = parts[0].strip().lower()
            try:
                price = float(parts[1].strip())
            except ValueError:
                failed.append(line)
                continue

            if acct_type not in ("gmail", "hotmail", "outlook"):
                failed.append(line)
                continue

            cursor.execute(
                "INSERT OR REPLACE INTO unlock_prices(type, price) VALUES(?,?)",
                (acct_type, price)
            )
            updated.append(f"{acct_type}: {price}")

        conn.commit()

    # تجهيز الرد للمستخدم
    header = "✅ تم تحديث الأسعار التالية:\n" if lang == "ar" else "✅ Updated prices:\n"
    response = header + "\n".join(updated)
    if failed:
        sep = "\n\n⚠️ لم يتم فهم السطور التالية:\n" if lang == "ar" else "\n\n⚠️ Could not parse:\n"
        response += sep + "\n".join(failed)

    context.user_data.pop("current_state", None)
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
    """
    يبحث عن مستخدم حسب اسمه في جدول users ويعرض:
    - المعرف الداخلي (id)
    - الرصيد (balance)
    - رصيد الإحالة (credit)
    - اللغة (language)
    """
    username = update.message.text.strip()

    # 1) استعلام عن المستخدم بالمعرف الداخلي بدلاً من chat_id
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, balance, credit, language FROM users WHERE username = ? LIMIT 1",
            (username,)
        )
        row = cursor.fetchone()

    # 2) بناء الرسالة
    if row:
        user_id, balance, credit, lang = row
        msg = (
            f"👤 معلومات المستخدم:\n\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💰 الرصيد: {balance:.2f} ل.س\n"
            f"🎁 رصيد الإحالة: {credit:.2f} ل.س\n"
            f"🌐 اللغة: {lang}"
        )
    else:
        msg = "❌ لم يتم العثور على هذا المستخدم."

    # 3) إرسال الرد وتنظيف الحالة
    await update.message.reply_text(msg, parse_mode="HTML")
    context.user_data.pop("current_action", None)





def main():
    init_db()
    app = Application.builder().token(TOKEN).post_init(post_init).build()


    app.add_handler(CommandHandler("start", start))
    #إدارة الحسابات للادمن
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
    app.add_handler(MessageHandler(filters.Regex("^(رصيدي|My Balance)$"), check_balance))
    #####################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(أسعار الحسابات|Account Prices)$"), show_currency_rates))
    ##########################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(شراء حساب|Buy Account)$"), buy_account))
    app.add_handler(MessageHandler(filters.Regex("^(شراء حساب Gmail درجة أولى|شراء حساب Gmail درجة ثانية|شراء حساب Outlook|شراء حساب Hotmail|Buy Gmail First-Class Account|Buy Gmail Second-Class Account|Buy Outlook Account|Buy Hotmail Account)$"), select_account_type))
    app.add_handler(MessageHandler(filters.Regex("^(1|3|5|10)$"), process_quantity)) 
    app.add_handler(CallbackQueryHandler(buy_accounts, pattern="^buy_"))
    app.add_handler(MessageHandler(filters.Regex("^(العودة|Back)$"), return_to_prev))
    ##########################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(إهداء رصيد|Gift Balance)$"), ask_for_gift_balance))
    ############################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(بريد وهمي|Temp Mail)$"), create_temp_mail))
    ##############################################################################################################
    app.add_handler(MessageHandler(filters.Regex("^(شحن الرصيد|Recharge Balance)$"), recharge_balance))
    app.add_handler(MessageHandler(filters.Regex("^(سيريتيل كاش|Payeer|USDT|CoinX|بيمو|Syriatel Cash|Payeer|USDT|CoinX|Bemo)$"), payment_details))
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
    app.add_handler(MessageHandler(filters.Regex("^(حول|ِAbout)$"), show_about_bot))
    app.add_handler(MessageHandler(filters.Regex("^(📞 تواصل مع الدعم|📞 Contact Support)$"), contact_admin_handler))
    app.add_handler(MessageHandler(filters.Regex("^(📄 الأسئلة الشائعة|📄 FAQ)$"), show_faq))

    app.add_handler(CommandHandler("confirm_buy", confirm_buy))
    ######################################3
    app.add_handler(MessageHandler(filters.Regex("^(فحص جيميل|Check Gmail)$"), request_emails_for_check))
    ######################################################3
    app.add_handler(MessageHandler(filters.Regex("^(فك حساب|Unlock account)$"), Unlock_account))
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
    app.add_handler(MessageHandler(filters.Regex("^(💰 الأرصدة|💰 Balances)$"), show_balance_menu))
    app.add_handler(MessageHandler(filters.Regex("^(🔍 البحث عن مستخدم)$"), ask_for_username_to_search))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, general_handler)
    )
    app.run_polling(timeout=10, poll_interval=1, allowed_updates=Update.ALL_TYPES)
if __name__ == "__main__":
    main()
