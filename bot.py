import requests
import time
import re
import json
import random
import math
import hashlib
import sqlite3
import os
from collections import defaultdict
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta
from threading import Thread

# ==================== تنظیمات ====================
TOKEN = '194655556:dh_wYhbWn4M8Fsvptzj0n9SajWRPiFNrsh8'
BASE_URL = f'https://tapi.bale.ai/bot{TOKEN}'
BASE_JS_URL = "https://dls6.iran-onemovies-dcenter.com/DonyayeSerial/10_thous.js"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

BOT_USERNAME = "ZAR_FILM_bot"
BOT_NAME = "🎬 ZAR_FILM"
ADMIN_ID = 2106397157
CHANNEL_LINK = "https://ble.ir/zar_film"
CHANNEL_USERNAME = "@zar_film"
SUPPORT_LINK = "https://ble.ir/LoveOyou"
SUPPORT_USERNAME = "@LoveOyou"
VERSION = "4.0.0"

# حذف دیتابیس قدیمی برای شروع تازه
if os.path.exists("zar_film_database.db"):
    os.remove("zar_film_database.db")
    print("✅ دیتابیس قدیمی حذف شد")

# متغیرهای سراسری
GLOBAL_DATA_CACHE = None
VERSION_MAP = {"1": "🎬 زیرنویس فارسی", "2": "🎙️ دوبله فارسی", "3": "🔊 بدون زیرنویس"}

SEARCH_CACHE = {}
CACHE_EXPIRE = 300

reviews_db = defaultdict(lambda: {"reviews": [], "avg_rating": 0, "total_ratings": 0})
PENDING_REQUESTS = []
REQUESTS_DB = defaultdict(list)

DB_FILE = "zar_film_database.db"

# ساختار کامل کاربر
DEFAULT_USER = {
    "favorites": [], "history": [], "watchlist": [], "watched": [], "ratings": {},
    "stats": {"searches": 0, "downloads": 0, "shares": 0, "invites": 0, "last_active": None, "daily_streak": 0, "last_daily": None, "total_watch_time": 0, "comments_count": 0, "likes_received": 0},
    "settings": {"per_page": 10, "theme": "dark", "notify_new": True, "auto_delete": False, "language": "fa", "download_quality": "all", "show_spoiler": False},
    "current_session": None, "selected_item": None, "selected_season": None,
    "last_search": None, "level": 1, "exp": 0,
    "badges": ["🆕 تازه‌وارد"], "notifications": [], "temp_data": {},
    "referral_code": None, "referred_by": None, "invited_users": [],
    "daily_reminder": True, "favorite_genres": [], "watch_time": 0,
    "filters": {"year": None, "year_start": None, "year_end": None, "rating_min": None, "rating_max": None, "genre": None, "type": None, "country": None},
    "notes": {}, "reminders": []
}

user_data = defaultdict(lambda: DEFAULT_USER.copy())

bot_stats = {
    "total_users": 0, "active_today": 0, "total_searches": 0,
    "total_downloads": 0, "total_shares": 0, "total_comments": 0,
    "total_ratings": 0, "start_time": datetime.now(),
    "daily_active": set(), "errors": [], "popular_searches": defaultdict(int)
}

GENRES = [
    "🔥 اکشن", "😂 کمدی", "🎭 درام", "💕 عاشقانه", "👻 ترسناک",
    "🚀 علمی-تخیلی", "🧙 فانتزی", "🗺️ ماجراجویی", "🕵️ جنایی", "📜 تاریخی",
    "📖 بیوگرافی", "🎥 مستند", "⚔️ جنگی", "👨‍👩‍👧‍👦 خانوادگی", "🎵 موسیقی", "⚽ ورزشی"
]

COUNTRIES = ["🇺🇸 آمریکا", "🇬🇧 انگلستان", "🇫🇷 فرانسه", "🇩🇪 آلمان", "🇮🇹 ایتالیا", "🇪🇸 اسپانیا", "🇯🇵 ژاپن", "🇰🇷 کره جنوبی", "🇨🇳 چین", "🇮🇳 هند"]

# ==================== دیتابیس ====================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, data TEXT, created_at TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, imdb_code TEXT, user_id INTEGER, user_name TEXT, rating INTEGER, comment TEXT, date TEXT, likes INTEGER, dislikes INTEGER, reported INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, description TEXT, date TEXT, status TEXT, admin_note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_stats (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER, reason TEXT, date TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, message TEXT, date TEXT, recipients_count INTEGER)''')
    conn.commit()
    conn.close()
    print("✅ دیتابیس آماده شد")

def save_all_data():
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        c = conn.cursor()
        for chat_id, data in user_data.items():
            if isinstance(chat_id, int):
                c.execute("INSERT OR REPLACE INTO users (chat_id, data, last_seen) VALUES (?, ?, ?)", (chat_id, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()))
        c.execute("DELETE FROM reviews")
        for imdb_code, rev_data in reviews_db.items():
            for rev in rev_data["reviews"]:
                c.execute("INSERT INTO reviews (imdb_code, user_id, user_name, rating, comment, date, likes, dislikes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (imdb_code, rev["user_id"], rev["user_name"], rev["rating"], rev["comment"], rev["date"], rev.get("likes", 0), rev.get("dislikes", 0)))
        c.execute("DELETE FROM requests")
        for req in PENDING_REQUESTS:
            c.execute("INSERT INTO requests (id, user_id, title, description, date, status) VALUES (?, ?, ?, ?, ?, ?)", (req["id"], req["user_id"], req["title"], req["description"], req["date"], req["status"]))
        c.execute("INSERT OR REPLACE INTO bot_stats VALUES (?, ?)", ("total_users", str(bot_stats["total_users"])))
        c.execute("INSERT OR REPLACE INTO bot_stats VALUES (?, ?)", ("total_searches", str(bot_stats["total_searches"])))
        c.execute("INSERT OR REPLACE INTO bot_stats VALUES (?, ?)", ("total_downloads", str(bot_stats["total_downloads"])))
        c.execute("INSERT OR REPLACE INTO bot_stats VALUES (?, ?)", ("total_shares", str(bot_stats["total_shares"])))
        c.execute("INSERT OR REPLACE INTO bot_stats VALUES (?, ?)", ("start_time", bot_stats["start_time"].isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"خطا در ذخیره: {e}")

def load_all_data():
    global user_data, reviews_db, PENDING_REQUESTS, bot_stats
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT chat_id, data FROM users")
        for row in c.fetchall():
            if isinstance(row[0], int) and row[1]:
                user_data[row[0]] = json.loads(row[1])
        c.execute("SELECT * FROM reviews")
        reviews_db.clear()
        for row in c.fetchall():
            reviews_db[row[1]]["reviews"].append({"user_id": row[2], "user_name": row[3], "rating": row[4], "comment": row[5], "date": row[6], "likes": row[7], "dislikes": row[8]})
            update_review_average(row[1])
        c.execute("SELECT * FROM requests ORDER BY id")
        PENDING_REQUESTS = []
        for row in c.fetchall():
            PENDING_REQUESTS.append({"id": row[0], "user_id": row[1], "title": row[2], "description": row[3], "date": row[4], "status": row[5]})
        c.execute("SELECT key, value FROM bot_stats")
        for key, value in c.fetchall():
            if key == "total_users": bot_stats["total_users"] = int(value)
            elif key == "total_searches": bot_stats["total_searches"] = int(value)
            elif key == "total_downloads": bot_stats["total_downloads"] = int(value)
            elif key == "total_shares": bot_stats["total_shares"] = int(value)
            elif key == "start_time": bot_stats["start_time"] = datetime.fromisoformat(value)
        conn.close()
        print("✅ دیتا بارگذاری شد")
    except Exception as e:
        print(f"خطا در بارگذاری: {e}")

# ==================== توابع API ====================
def get_updates(offset=0):
    url = f'{BASE_URL}/getUpdates?offset={offset}&timeout=20'
    try:
        return requests.get(url, timeout=25).json()
    except:
        return {"result": []}

def send_message(chat_id, text, parse_mode=None, reply_markup=None, disable_web_page_preview=False):
    data = {'chat_id': chat_id, 'text': text, 'disable_web_page_preview': disable_web_page_preview}
    if parse_mode:
        data['parse_mode'] = parse_mode
    if reply_markup:
        data['reply_markup'] = reply_markup
    try:
        return requests.post(f'{BASE_URL}/sendMessage', json=data, timeout=10).json()
    except:
        return None

def edit_message_text(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
    if parse_mode:
        data['parse_mode'] = parse_mode
    if reply_markup:
        data['reply_markup'] = reply_markup
    try:
        requests.post(f'{BASE_URL}/editMessageText', json=data, timeout=10)
    except:
        pass

def answer_callback(callback_id, text=None, show_alert=False):
    data = {'callback_query_id': callback_id}
    if text:
        data['text'] = text
        data['show_alert'] = show_alert
    try:
        requests.post(f'{BASE_URL}/answerCallbackQuery', json=data, timeout=5)
    except:
        pass

# ... (بقیه کد خیلی طولانی است، برای جلوگیری از خطا، کد کامل را بعداً آپلود می‌کنم اما فعلاً main functions)

if __name__ == "__main__":
    main()