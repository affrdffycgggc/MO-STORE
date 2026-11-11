import os
import sys
import json
import time
import hashlib
import secrets
import sqlite3
import threading
import re
import uuid
import requests
import qrcode
import io
import base64
import traceback
import socket
import csv
import random
import math
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from urllib.parse import quote, urlencode, unquote
from html import unescape as html_unescape

from flask import (
    Flask, request, session, redirect, url_for,
    render_template_string, jsonify, send_file, make_response, abort, Response,
)
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    CallbackQuery, Message, WebAppInfo, ReactionType
)
from markupsafe import Markup
from jinja2 import Environment, DictLoader

# ==============================================================================
# الإعدادات الأساسية
# ==============================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8243016747:AAFYo-4xGD35o22f1eEEjtvD1lW5r3J39Vs")
ADMIN_IDS = [8410208108]

API_BASE_URL = os.environ.get("API_BASE_URL", "https://mousa-card.com")
API_KEY = os.environ.get("API_KEY", "1-d5am8ulj6-dXwbL9vYCxzeojEJ2ivjMfk3oFIUsRQgwjDZvUkKXfBCCkWbC-vR")
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 80))

FORCE_JOIN_CHANNEL_ID = "-1003868265171"
FORCE_JOIN_CHANNEL_LINK = "https://t.me/ishhan1"
FORCE_JOIN_CHANNEL_USERNAME = "@ishhan1"
BOT_USERNAME = "ishhan1"

SYNC_FETCH_PRODUCT_DETAILS = True
SYNC_CLEAN_ORPHANS = True
SYNC_PARALLEL_WORKERS = 10
SYNC_DETAILS_CHUNK_SIZE = 40
SYNC_MAX_TREE_NODES = 5000
SYNC_MAX_TREE_DEPTH = 20
SYNC_CRAWL_DELAY = 0.05
ORDER_CHECK_INTERVAL = 45
AUTO_SYNC_HOURS = 6

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

WEB_URL = os.environ.get("WEB_URL", "https://mo-store-fhrf.onrender.com")
DB_PATH = os.environ.get("DB_PATH", "mo_store_v200_pro.db")
IMAGES_DIR = os.environ.get("IMAGES_DIR", "mo_store_images_v200_pro")

DEBUG_API = False
DEBUG_SYNC = True
os.makedirs(IMAGES_DIR, exist_ok=True)

CURRENCY = "ل.س"
CURRENCY_CODE = "SYP"

API_ERROR_CODES = {
    120: "API Token مطلوب", 121: "API Token غير صالح", 122: "غير مسموح باستخدام API",
    123: "عنوان IP غير مسموح", 130: "الموقع في وضع الصيانة", 100: "رصيد غير كافٍ في حساب API",
    105: "حقل مطلوب مفقود", 106: "الكمية غير مسوحة", 107: "معرف اللاعب محظور",
    108: "المصادقة الثنائية مطلوبة", 109: "المنتج محذوف أو غير موجود", 110: "المنتج غير متاح حالياً",
    111: "أعد المحاولة بعد دقيقة", 112: "الكمية أصغر من الحد الأدنى", 113: "الكمية أكبر من الحد الأقصى",
    114: "خطأ في البيانات المدخلة", 500: "خطأ داخلي في الخادم"
}

SUPPORTER_PERMS = ["manage_orders", "manage_topups", "manage_users", "manage_products", "manage_tickets", "manage_chats"]

def debug_print(msg, level="INFO  Untitled5:100 - subertecno.py:100"):
    if DEBUG_API or DEBUG_SYNC:
        prefix = {"INFO": "[INFO]", "WARN": "[WARN]", "ERROR": "[ERROR]", "SUCCESS": "[SUCCESS]", "SYNC": "[SYNC]"}.get(level, "[INFO]")
        print(f"{prefix} {msg}  Untitled5:103 - subertecno.py:103", flush=True)

def safe_int(val, default=0, min_val=0, max_val=999999999):
    try:
        if val is None or isinstance(val, bool): return default
        result = int(float(val))
        if result < min_val: return default
        if result > max_val: return default
        return result
    except Exception: return default

def clamp_int(val, default=1, max_val=999999999):
    try:
        v = int(float(val))
        return min(max(1, v), max_val)
    except Exception: return default

def db_int(val, default=0, max_val=999999999):
    try:
        if val is None or isinstance(val, bool): return default
        v = int(float(val))
        return min(max(default, v), max_val)
    except Exception: return default

def safe_float(val, default=0.0):
    try:
        if val is None or isinstance(val, bool): return default
        return float(str(val).replace(",", "").strip())
    except Exception: return default

def row_to_dict(row):
    if row is None: return None
    if isinstance(row, dict): return row
    if isinstance(row, sqlite3.Row): return {key: row[key] for key in row.keys()}
    return dict(row)

def strip_html_tags(html_text):
    if not html_text or not isinstance(html_text, str): return ""
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<br\s*/?>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'</p>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<p[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = html_unescape(clean)
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    clean = re.sub(r' {2,}', ' ', clean)
    return clean.strip()

def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

# ==============================================================================
# قاعدة البيانات
# ==============================================================================

class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self._local = threading.local()
        self._settings_cache = {}
        self._settings_cache_ts = 0
        self._settings_cache_lock = threading.Lock()
        self._settings_cache_ttl = 30
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-64000")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.execute("PRAGMA busy_timeout=15000")
            self._local.conn.execute("PRAGMA temp_store=MEMORY")
            self._local.conn.execute("PRAGMA mmap_size=268435456")
            self._local.conn.execute("PRAGMA wal_autocheckpoint=1000")
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
        c = conn.cursor()

        c.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE, username TEXT UNIQUE, phone TEXT, email TEXT, 
                password_hash TEXT, salt TEXT, balance REAL DEFAULT 0.0, loyalty_points INTEGER DEFAULT 0, min_balance REAL DEFAULT 0.0, 
                role TEXT DEFAULT 'user', permissions TEXT DEFAULT '[]', is_banned INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, 
                is_vip INTEGER DEFAULT 0, vip_level INTEGER DEFAULT 0, total_orders INTEGER DEFAULT 0, total_spent REAL DEFAULT 0.0, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_login TEXT, last_activity TEXT, failed_login_attempts INTEGER DEFAULT 0, 
                locked_until TEXT, last_login_ip TEXT, last_user_agent TEXT, avatar_path TEXT, bio TEXT, preferred_language TEXT DEFAULT 'ar', 
                newsletter_subscribed INTEGER DEFAULT 1, two_factor_enabled INTEGER DEFAULT 0, achievements TEXT DEFAULT '[]', 
                contests_won INTEGER DEFAULT 0, referral_code TEXT, referred_by INTEGER, ban_reason TEXT,
                wheel_spins INTEGER DEFAULT 0, total_wheel_spins INTEGER DEFAULT 0, total_wheel_winnings REAL DEFAULT 0.0,
                force_join_checked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS user_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token TEXT UNIQUE NOT NULL, ip_address TEXT, user_agent TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, used INTEGER DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS push_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token TEXT NOT NULL, device_type TEXT DEFAULT 'android', device_id TEXT DEFAULT '', is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_used TEXT, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS telegram_link_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, used INTEGER DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, image_path TEXT, image_url TEXT, api_category_id TEXT, parent_id TEXT DEFAULT '0', sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, is_featured INTEGER DEFAULT 0, icon TEXT, color TEXT, meta_title TEXT, meta_description TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, api_product_id TEXT UNIQUE, name TEXT NOT NULL, description TEXT, category_id INTEGER, original_price REAL NOT NULL DEFAULT 0, sell_price REAL NOT NULL DEFAULT 0, image_path TEXT, image_url TEXT, all_images TEXT, quantity_type TEXT DEFAULT 'unlimited', quantity INTEGER DEFAULT 0, min_quantity INTEGER DEFAULT 1, max_quantity INTEGER DEFAULT 0, qty_options TEXT, step_quantity INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1, is_featured INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, views INTEGER DEFAULT 0, sales_count INTEGER DEFAULT 0, requires_player_id INTEGER DEFAULT 0, player_id_label TEXT DEFAULT 'معرف اللاعب', product_type TEXT DEFAULT 'digital', requires_shipping INTEGER DEFAULT 0, required_fields TEXT, instructions TEXT, api_raw_data TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL);
            CREATE TABLE IF NOT EXISTS payment_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, account_number TEXT, account_name TEXT, payment_link TEXT, qr_code_base64 TEXT, image_path TEXT, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS shipping_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, price REAL DEFAULT 0, estimated_days TEXT, wallet_link TEXT, wallet_number TEXT, qr_code_base64 TEXT, image_path TEXT, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS wallet_topup_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, account_number TEXT, account_name TEXT, wallet_link TEXT, qr_code_base64 TEXT, image_path TEXT, min_amount REAL DEFAULT 0, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, instructions TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS wallet_topup_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT UNIQUE, user_id INTEGER NOT NULL, method_id INTEGER, amount REAL NOT NULL, transaction_number TEXT, status TEXT DEFAULT 'pending', admin_notes TEXT, confirmed_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, confirmed_at TEXT, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS purchase_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT UNIQUE, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1, unit_price REAL NOT NULL, total_price REAL NOT NULL, api_order_id TEXT, api_response TEXT, player_id TEXT, order_uuid TEXT, shipping_method_id INTEGER, shipping_price REAL DEFAULT 0, transaction_number TEXT, payment_amount REAL DEFAULT 0, customer_info TEXT, status TEXT DEFAULT 'pending', delivered_data TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (product_id) REFERENCES products(id));
            CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, ad_type TEXT DEFAULT 'text', title TEXT, content TEXT, image_path TEXT, image_url TEXT, link_url TEXT, position TEXT DEFAULT 'top', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, start_date TEXT, end_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount REAL NOT NULL, transaction_type TEXT NOT NULL, description TEXT, reference_id TEXT, balance_after REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS bot_states (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT NOT NULL, message TEXT NOT NULL, notification_type TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0, is_broadcast INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS support_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT UNIQUE, user_id INTEGER NOT NULL, subject TEXT, status TEXT DEFAULT 'open', priority TEXT DEFAULT 'normal', created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS support_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL, user_id INTEGER NOT NULL, message TEXT NOT NULL, is_from_admin INTEGER DEFAULT 0, image_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS maintenance (id INTEGER PRIMARY KEY AUTOINCREMENT, is_active INTEGER DEFAULT 0, start_time TEXT, end_time TEXT, duration_minutes INTEGER DEFAULT 60, message TEXT, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS maintenance_images (id INTEGER PRIMARY KEY AUTOINCREMENT, image_path TEXT NOT NULL, title TEXT, sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS user_favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id));
            CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL, is_from_admin INTEGER DEFAULT 0, is_read INTEGER DEFAULT 0, image_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS password_reset_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT UNIQUE, user_id INTEGER, username TEXT, email TEXT, phone TEXT, status TEXT DEFAULT 'pending', new_password TEXT, admin_notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, resolved_at TEXT);
            CREATE TABLE IF NOT EXISTS user_badges (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, badge_type TEXT, awarded_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS user_status_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, status_type TEXT, description TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS gift_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, name TEXT NOT NULL, description TEXT, price REAL NOT NULL DEFAULT 0, image_path TEXT, image_url TEXT, is_active INTEGER DEFAULT 1, is_sold INTEGER DEFAULT 0, sold_to_user_id INTEGER, sold_at TEXT, order_id TEXT, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS sync_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, sync_type TEXT, started_at TEXT, completed_at TEXT, categories_count INTEGER DEFAULT 0, products_count INTEGER DEFAULT 0, updated_count INTEGER DEFAULT 0, merged_count INTEGER DEFAULT 0, errors_count INTEGER DEFAULT 0, errors_details TEXT, details TEXT, status TEXT DEFAULT 'running');
            CREATE TABLE IF NOT EXISTS api_error_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT, error_message TEXT, request_data TEXT, response_data TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS cart_items (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1, selected_option TEXT, custom_fields TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (product_id) REFERENCES products(id));
            CREATE TABLE IF NOT EXISTS recently_viewed (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, viewed_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id));
            CREATE TABLE IF NOT EXISTS product_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, rating INTEGER DEFAULT 5, comment TEXT, is_approved INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS discount_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, discount_type TEXT DEFAULT 'percentage', discount_value REAL DEFAULT 0, min_order REAL DEFAULT 0, max_uses INTEGER DEFAULT 0, uses_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, expires_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS product_comparisons (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id));
            CREATE TABLE IF NOT EXISTS price_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, target_price REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS search_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS stock_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, threshold INTEGER DEFAULT 5, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS product_tags (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, tag TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS blog_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, slug TEXT UNIQUE, content TEXT, excerpt TEXT, image_path TEXT, author_id INTEGER, is_published INTEGER DEFAULT 0, views INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS faqs (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL, category TEXT, sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS site_pages (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, slug TEXT UNIQUE, content TEXT, is_published INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS banners (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, image_path TEXT, link_url TEXT, position TEXT DEFAULT 'home', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, start_date TEXT, end_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS refunds (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, user_id INTEGER, amount REAL, reason TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, description TEXT, ip_address TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS wishlist_shares (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, share_token TEXT UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS product_specifications (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, spec_name TEXT, spec_value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS newsletter_subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, user_id INTEGER, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS seo_settings (id INTEGER PRIMARY KEY AUTOINCREMENT, page_url TEXT, meta_title TEXT, meta_description TEXT, meta_keywords TEXT, og_image TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS system_settings (id INTEGER PRIMARY KEY AUTOINCREMENT, setting_key TEXT UNIQUE, setting_value TEXT, description TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS contests (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, prize TEXT, start_date TEXT, end_date TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS contest_participants (id INTEGER PRIMARY KEY AUTOINCREMENT, contest_id INTEGER NOT NULL, user_id INTEGER NOT NULL, joined_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(contest_id, user_id));
            CREATE TABLE IF NOT EXISTS user_achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, achievement_type TEXT NOT NULL, achievement_name TEXT, description TEXT, icon TEXT, earned_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, achievement_type));
            CREATE TABLE IF NOT EXISTS product_offers (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, offer_title TEXT, offer_description TEXT, discount_percentage REAL DEFAULT 0, original_price REAL DEFAULT 0, offer_price REAL DEFAULT 0, is_active INTEGER DEFAULT 1, start_date TEXT, end_date TEXT, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS wheel_gifts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, amount REAL DEFAULT 0, color TEXT DEFAULT '#7c3aed', icon TEXT DEFAULT '🎁', probability REAL DEFAULT 0, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS wheel_spins (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, gift_id INTEGER, result TEXT DEFAULT 'lose', amount_won REAL DEFAULT 0, spin_date TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (gift_id) REFERENCES wheel_gifts(id));
            CREATE TABLE IF NOT EXISTS spin_reward_thresholds (id INTEGER PRIMARY KEY AUTOINCREMENT, threshold_amount REAL NOT NULL, spins_awarded INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS broadcast_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, message TEXT, image_path TEXT, sent_by INTEGER, total_sent INTEGER DEFAULT 0, total_failed INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS channel_management (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, description TEXT, performed_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)

        try:
            cols = c.execute("PRAGMA table_info(products)").fetchall()
            col_names = [col[1] for col in cols]
            migration_cols = {
                'parent_product_id': "INTEGER DEFAULT NULL", 'is_featured': "INTEGER DEFAULT 0", 'api_parent_id': "TEXT DEFAULT NULL",
                'sync_hash': "TEXT DEFAULT NULL", 'product_api_type': "TEXT DEFAULT 'package'", 'discount_percentage': "REAL DEFAULT 0",
                'badge_text': "TEXT DEFAULT ''", 'badge_color': "TEXT DEFAULT ''", 'is_variant': "INTEGER DEFAULT 0",
                'stock_quantity': "INTEGER DEFAULT -1", 'instructions': "TEXT DEFAULT ''", 'meta_title': "TEXT DEFAULT ''",
                'meta_description': "TEXT DEFAULT ''", 'video_url': "TEXT DEFAULT ''", 'warranty': "TEXT DEFAULT ''",
                'brand': "TEXT DEFAULT ''", 'sku': "TEXT DEFAULT ''", 'tags': "TEXT DEFAULT ''",
            }
            for col_name, col_def in migration_cols.items():
                if col_name not in col_names:
                    c.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
        except Exception as e:
            print(f"[DB] Products migration check error: {e}", flush=True)

        try:
            cols_user = c.execute("PRAGMA table_info(users)").fetchall()
            user_col_names = [col[1] for col in cols_user]
            user_migrations = {
                'loyalty_points': "INTEGER DEFAULT 0", 'avatar_path': "TEXT DEFAULT ''", 'bio': "TEXT DEFAULT ''", 'preferred_language': "TEXT DEFAULT 'ar'",
                'newsletter_subscribed': "INTEGER DEFAULT 1", 'two_factor_enabled': "INTEGER DEFAULT 0", 'is_vip': "INTEGER DEFAULT 0", 'vip_level': "INTEGER DEFAULT 0",
                'achievements': "TEXT DEFAULT '[]'", 'contests_won': "INTEGER DEFAULT 0", 'referral_code': "TEXT DEFAULT ''", 'referred_by': "INTEGER DEFAULT NULL",
                'ban_reason': "TEXT DEFAULT ''", 'wheel_spins': "INTEGER DEFAULT 0", 'total_wheel_spins': "INTEGER DEFAULT 0", 'total_wheel_winnings': "REAL DEFAULT 0.0",
                'force_join_checked': "INTEGER DEFAULT 0",
            }
            for col_name, col_def in user_migrations.items():
                if col_name not in user_col_names:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except Exception as e:
            print(f"[DB] Users migration error: {e}", flush=True)

        try:
            cols_cat = c.execute("PRAGMA table_info(categories)").fetchall()
            cat_col_names = [col[1] for col in cols_cat]
            cat_migrations = {
                'is_featured': "INTEGER DEFAULT 0", 'api_parent_id': "TEXT DEFAULT '0'", 'icon': "TEXT DEFAULT ''", 'color': "TEXT DEFAULT ''",
                'meta_title': "TEXT DEFAULT ''", 'meta_description': "TEXT DEFAULT ''",
            }
            for col_name, col_def in cat_migrations.items():
                if col_name not in cat_col_names:
                    c.execute(f"ALTER TABLE categories ADD COLUMN {col_name} {col_def}")
        except Exception as e:
            print(f"[DB] Category migration error: {e}", flush=True)

        try:
            cols_ship = c.execute("PRAGMA table_info(shipping_methods)").fetchall()
            ship_col_names = [col[1] for col in cols_ship]
            if 'wallet_number' not in ship_col_names:
                c.execute("ALTER TABLE shipping_methods ADD COLUMN wallet_number TEXT DEFAULT ''")
            if 'price_usd' not in ship_col_names:
                c.execute("ALTER TABLE shipping_methods ADD COLUMN price_usd REAL DEFAULT 0")
            if 'currency_type' not in ship_col_names:
                c.execute("ALTER TABLE shipping_methods ADD COLUMN currency_type TEXT DEFAULT 'SYP'")
        except Exception as e:
            print(f"[DB] Shipping migration error: {e}", flush=True)

        try:
            cols_tu = c.execute("PRAGMA table_info(wallet_topup_methods)").fetchall()
            tu_col_names = [col[1] for col in cols_tu]
            if 'wallet_link' not in tu_col_names:
                c.execute("ALTER TABLE wallet_topup_methods ADD COLUMN wallet_link TEXT DEFAULT ''")
            if 'currency_type' not in tu_col_names:
                c.execute("ALTER TABLE wallet_topup_methods ADD COLUMN currency_type TEXT DEFAULT 'SYP'")
        except Exception as e:
            print(f"[DB] Topup methods migration error: {e}", flush=True)

        try:
            cols_req = c.execute("PRAGMA table_info(wallet_topup_requests)").fetchall()
            req_col_names = [col[1] for col in cols_req]
            if 'currency_type' not in req_col_names:
                c.execute("ALTER TABLE wallet_topup_requests ADD COLUMN currency_type TEXT DEFAULT 'SYP'")
            if 'original_amount' not in req_col_names:
                c.execute("ALTER TABLE wallet_topup_requests ADD COLUMN original_amount REAL DEFAULT 0")
        except Exception as e:
            print(f"[DB] Topup requests migration error: {e}", flush=True)

        c.execute("""CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            topup_request_id INTEGER,
            reward_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'awarded',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referred_id),
            FOREIGN KEY (referrer_id) REFERENCES users(id),
            FOREIGN KEY (referred_id) REFERENCES users(id)
        )""")

        c.executescript("""
            CREATE INDEX IF NOT EXISTS idx_gift_codes_active ON gift_codes(is_active, is_sold);
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
            CREATE INDEX IF NOT EXISTS idx_products_parent ON products(parent_product_id);
            CREATE INDEX IF NOT EXISTS idx_products_api ON products(api_product_id);
            CREATE INDEX IF NOT EXISTS idx_products_is_variant ON products(is_variant);
            CREATE INDEX IF NOT EXISTS idx_orders_user ON purchase_orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON purchase_orders(status);
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);
            CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
            CREATE INDEX IF NOT EXISTS idx_categories_api ON categories(api_category_id);
            CREATE INDEX IF NOT EXISTS idx_categories_api_parent ON categories(api_parent_id);
            CREATE INDEX IF NOT EXISTS idx_maint_images ON maintenance_images(is_active);
            CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
            CREATE INDEX IF NOT EXISTS idx_recently_viewed ON recently_viewed(user_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_product ON product_reviews(product_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_approved ON product_reviews(is_approved);
            CREATE INDEX IF NOT EXISTS idx_discount_active ON discount_codes(is_active);
            CREATE INDEX IF NOT EXISTS idx_comparisons_user ON product_comparisons(user_id);
            CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
            CREATE INDEX IF NOT EXISTS idx_products_sell_price ON products(sell_price);
            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
            CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read);
            CREATE INDEX IF NOT EXISTS idx_banners_active ON banners(is_active);
            CREATE INDEX IF NOT EXISTS idx_blog_published ON blog_posts(is_published);
            CREATE INDEX IF NOT EXISTS idx_faqs_active ON faqs(is_active);
            CREATE INDEX IF NOT EXISTS idx_activity_logs_user ON activity_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_product_tags_product ON product_tags(product_id);
            CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts(user_id);
            CREATE INDEX IF NOT EXISTS idx_stock_alerts_product ON stock_alerts(product_id);
            CREATE INDEX IF NOT EXISTS idx_contests_active ON contests(is_active);
            CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id);
            CREATE INDEX IF NOT EXISTS idx_product_offers_active ON product_offers(is_active);
            CREATE INDEX IF NOT EXISTS idx_product_offers_product ON product_offers(product_id);
            CREATE INDEX IF NOT EXISTS idx_wheel_gifts_active ON wheel_gifts(is_active);
            CREATE INDEX IF NOT EXISTS idx_wheel_spins_user ON wheel_spins(user_id);
            CREATE INDEX IF NOT EXISTS idx_spin_thresholds_active ON spin_reward_thresholds(is_active);
            CREATE INDEX IF NOT EXISTS idx_broadcast_messages ON broadcast_messages(created_at);
        """)

        defaults = {
            "profit_percentage": "15", "price_exchange_rate": "15000", "maintenance_mode": "off", "maintenance_end_time": "0", "maintenance_message": "الموقع تحت الصيانة، سعود قريباً!",
            "default_min_balance": "0", "api_base_url": API_BASE_URL, "api_key": API_KEY, "store_name": "MO STORE", "store_logo": "", "site_icon": "", "site_background": "",
            "store_description": "وجهتك الأولى لشراء البطاقات الرقمية والشحن بأسعار تنافسية", "welcome_message": "مرحباً بك في MO STORE! نوفر لك أفضل البطاقات الرقمية والشحن بأسعار تنافسية وخدمة سريعة وآمنة.",
            "welcome_popup_title": "أهلاً وسهلاً بك في MO STORE!", "welcome_popup_message": "نحن سعيدون بزيارتك! اكتشف مجموعتنا الواسعة من البطاقات الرقمية والشحن بأسعار تنافسية وخدمة فورية.",
            "welcome_popup_image": "", "currency": CURRENCY, "currency_code": CURRENCY_CODE, "auto_purchase": "on", "last_sync": "0", "last_full_sync": "0", "bot_web_url": WEB_URL, "min_topup_amount": "0",
            "max_login_attempts": "5", "lockout_duration": "30", "support_whatsapp": "https://wa.me/963999999999", "support_telegram": "https://t.me/yourtelegram", "force_join_group": FORCE_JOIN_CHANNEL_ID,
            "force_join_group_id": FORCE_JOIN_CHANNEL_ID, "force_join_group_link": FORCE_JOIN_CHANNEL_LINK, "force_join_enabled": "1",
            "site_entry_notif_title": "مرحباً بك في متجرنا الراقي!",
            "site_entry_notif_message": "تصفح أحدث المنتجات والبطاقات الرقمية بأفضل الأسعار. استمتع بتجربة تسوق سريعة وآمنة وفورية!", "loyalty_points_per_currency": "1", "loyalty_points_name": "نقاط الولاء",
            "show_related_products": "1", "show_recently_viewed": "1", "show_product_reviews": "1", "primary_color": "#7c3aed", "secondary_color": "#06b6d4", "accent_color": "#ec4899", "enable_reviews": "1",
            "enable_comparison": "1", "enable_price_alerts": "1", "enable_search_history": "1", "enable_loyalty": "1", "enable_discounts": "1", "enable_cart": "1", "enable_wishlist_sharing": "1", "enable_product_videos": "1",
            "enable_blog": "1", "enable_faqs": "1", "enable_newsletter": "1", "enable_gestures": "1", "enable_sound_effects": "1", "enable_haptic_feedback": "1", "enable_dark_mode": "1", "enable_animations": "1", "enable_particles": "1",
            "min_shipping_charge": "0", "min_order_amount": "0", "free_shipping_threshold": "0", "min_topup_amount": "1000", "enable_stock_alerts": "1", "stock_alert_threshold": "5", "topup_commission": "0", "enable_guest_checkout": "1",
            "enable_product_comparison": "1", "enable_advanced_search": "1", "enable_filter_sidebar": "1", "enable_infinite_scroll": "0", "seo_title": "MO STORE - متجر البطاقات الرقمية", "seo_description": "أفضل متجر لشراء البطاقات الرقمية والشحن",
            "seo_keywords": "بطاقات, شحن, رقمية, games, cards", "footer_text": "© 2025 MO STORE - جميع الحقوق محفوظة", "enable_live_chat": "1", "enable_chatbot": "0", "chatbot_welcome": "مرحباً! كيف يمكنني مساعدتك؟",
            "social_facebook": "", "social_instagram": "", "social_twitter": "", "social_youtube": "", "social_tiktok": "", "social_snapchat": "", "social_discord": "", "enable_age_verification": "0", "age_verification_message": "هل أنت فوق 18 عاماً؟",
            "enable_cookie_banner": "1", "cookie_message": "نستخدم ملفات تعريف الارتباط لتحسين تجربتك", "enable_promo_bar": "1", "promo_bar_text": "خصم 20% على جميع المنتجات لفترة محدودة!", "promo_bar_link": "", "promo_bar_color": "#7c3aed",
            "enable_countdown_timer": "0", "countdown_end_date": "", "countdown_title": "عرض ينتهي قريباً!", "enable_flash_sales": "0", "flash_sale_discount": "30", "enable_bulk_discounts": "0", "bulk_discount_threshold": "5",
            "bulk_discount_percentage": "10", "enable_loyalty_tiers": "1", "tier_bronze_min": "0", "tier_silver_min": "50000", "tier_gold_min": "200000", "tier_platinum_min": "500000", "enable_referral_program": "1", "referral_bonus": "5000",
            "referral_discount": "5", "enable_product_qa": "1", "enable_product_discussions": "0", "enable_wishlist_notifications": "1", "enable_price_drop_alerts": "1", "enable_back_in_stock_alerts": "1", "enable_order_tracking": "1",
            "enable_delivery_estimates": "1", "enable_product_bundles": "0", "enable_gift_wrapping": "0", "gift_wrap_price": "2000", "enable_contests": "1", "enable_achievements": "1", "vip_threshold": "100000", "vip_benefits": "خصم 5% على جميع المنتجات",
            "enable_popup_notifications": "1", "popup_notif_duration": "5", "enable_wheel": "1", "wheel_spin_threshold": "50000",
            "show_user_count": "0", "enable_offers_section": "1", "enable_quick_actions": "1", "enable_channel_management": "1",
            "bot_username": BOT_USERNAME
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        c.execute("INSERT OR IGNORE INTO shipping_methods (name, description, price, estimated_days, is_active, sort_order, currency_type) VALUES ('توصيل عادي', '2-3 أيام', 5000, '2-3 أيام', 1, 1, 'SYP')")
        c.execute("INSERT OR IGNORE INTO shipping_methods (name, description, price, estimated_days, is_active, sort_order, currency_type) VALUES ('توصيل سريع', '24 ساعة', 10000, '24 ساعة', 1, 2, 'SYP')")

        existing_wheel = c.execute("SELECT COUNT(*) as cnt FROM wheel_gifts").fetchone()
        if existing_wheel and existing_wheel["cnt"] == 0:
            default_gifts = [
                ("جائزة كبرى 100,000", 100000, "#ef4444", "💎", 1, 1),
                ("جائزة 50,000", 50000, "#f59e0b", "🏆", 2, 2),
                ("جائزة 25,000", 25000, "#10b981", "🎁", 3, 3),
                ("جائزة 10,000", 10000, "#06b6d4", "💰", 5, 4),
                ("جائزة 5,000", 5000, "#7c3aed", "⭐", 10, 5),
                ("حظ أوفر", 0, "#64748b", "🎲", 20, 6),
                ("حظ أوفر", 0, "#64748b", "🎲", 20, 7),
                ("حظ أوفر", 0, "#64748b", "🎲", 39, 8),
            ]
            for name, amount, color, icon, prob, sort in default_gifts:
                c.execute("INSERT INTO wheel_gifts (name, amount, color, icon, probability, is_active, sort_order) VALUES (?, ?, ?, ?, ?, 1, ?)",
                          (name, amount, color, icon, prob, sort))

        existing_thresholds = c.execute("SELECT COUNT(*) as cnt FROM spin_reward_thresholds").fetchone()
        if existing_thresholds and existing_thresholds["cnt"] == 0:
            c.execute("INSERT INTO spin_reward_thresholds (threshold_amount, spins_awarded, is_active) VALUES (50000, 1, 1)")
            c.execute("INSERT INTO spin_reward_thresholds (threshold_amount, spins_awarded, is_active) VALUES (100000, 3, 1)")
            c.execute("INSERT INTO spin_reward_thresholds (threshold_amount, spins_awarded, is_active) VALUES (200000, 5, 1)")

        conn.commit()
        conn.close()

    def execute(self, query, params=(), fetch=False, fetchone=False, commit=True):
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = None
            if fetchone: result = cursor.fetchone()
            elif fetch: result = cursor.fetchall()
            if commit: conn.commit()
            if not fetchone and not fetch: return cursor
            return result
        except Exception as e:
            conn.rollback()
            raise e

    def executescript(self, script):
        conn = self._get_conn()
        conn.executescript(script)
        conn.commit()

    def get_setting(self, key, default=None):
        now = time.time()
        with self._settings_cache_lock:
            if (now - self._settings_cache_ts) > self._settings_cache_ttl:
                self._settings_cache = {}
                self._settings_cache_ts = now
            if key in self._settings_cache:
                return self._settings_cache[key]
        
        row = self.execute("SELECT value FROM settings WHERE key = ?", (key,), fetchone=True)
        val = row["value"] if row else default
        
        with self._settings_cache_lock:
            self._settings_cache[key] = val
        return val

    def set_setting(self, key, value):
        with self._settings_cache_lock:
            self._settings_cache[key] = str(value)
            self._settings_cache_ts = time.time()
        self.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
            (key, str(value))
        )

    def log_api_error(self, endpoint, error_message, request_data="", response_data=""):
        try:
            self.execute("INSERT INTO api_error_logs (endpoint, error_message, request_data, response_data) VALUES (?, ?, ?, ?)",
                         (endpoint[:200], error_message[:500], str(request_data)[:1000], str(response_data)[:1000]))
        except Exception: pass

    def log_activity(self, user_id, action, description="", ip_address=""):
        try:
            self.execute("INSERT INTO activity_logs (user_id, action, description, ip_address) VALUES (?, ?, ?, ?)", (user_id, action, description, ip_address))
        except Exception: pass

    def start_sync_log(self, sync_type="full"):
        now = datetime.now().isoformat()
        self.execute("INSERT INTO sync_logs (sync_type, started_at, status) VALUES (?, ?, 'running')", (sync_type, now))
        row = self.execute("SELECT id FROM sync_logs WHERE started_at=? ORDER BY id DESC LIMIT 1", (now,), fetchone=True)
        return row["id"] if row else None

    def complete_sync_log(self, log_id, categories=0, products=0, updated=0, merged=0, errors=None, details=""):
        if errors is None: errors = []
        self.execute(
            "UPDATE sync_logs SET completed_at=?, categories_count=?, products_count=?, updated_count=?, merged_count=?, errors_count=?, errors_details=?, details=?, status='completed' WHERE id=?",
            (datetime.now().isoformat(), categories, products, updated, merged, len(errors), json.dumps(errors[:50], ensure_ascii=False), details, log_id)
        )

db = Database()

def ensure_virtual_topup_methods():
    existing = db.execute("SELECT COUNT(*) as c FROM wallet_topup_methods", fetchone=True)
    if existing and existing["c"] > 0: return
    virtual_methods = [
        ("شام كاش (ل.س)", "0991234567", "MO STORE", "حوّل المبلغ إلى رقم محفظة شام كاش التالي ثم أرسل رقم العملية. يجب تحويل المبلغ بالليرة السورية.", 0, "SYP"),
        ("USDT (TRC20)", "TXYZ1234567890abcdefghijklmnop", "MO STORE", "أرسل عملات USDT على شبكة TRC20 إلى العنوان التالي. سيتم تحويل المبلغ تلقائياً لليرة السورية حسب سعر الصرف الحالي.", 0, "USD"),
        ("بنك سوريا الدولي (ل.س)", "0123-4567-8901-2345", "MO STORE", "حوّل المبلغ إلى الحساب البنكي التالي باسم MO STORE ثم أرسل إيصال التحويل. المبلغ يجب أن يكون بالليرة السورية.", 0, "SYP"),
        ("واتساب كاش (ل.س)", "0998765432", "MO STORE", "تواصل معنا عبر واتساب لتحويل المبلغ وإرسال رقم العملية. المبلغ بالليرة السورية.", 0, "SYP"),
        ("Binance USDT", "TBinanceXYZ1234567890", "MO STORE", "أرسل عملات USDT إلى محفظة Binance التالية. سيتم التحويل التلقائي لليرة السورية.", 0, "USD"),
    ]
    for name, acc, acc_name, instr, min_amt, cur_type in virtual_methods:
        db.execute("""INSERT INTO wallet_topup_methods 
                      (name, account_number, account_name, min_amount, qr_code_base64, instructions, is_active, sort_order, currency_type) 
                      VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)""",
                   (name, acc, acc_name, min_amt, None, instr, cur_type))

def _hash_password(password, salt=None):
    if salt is None: salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return pw_hash.hex(), salt

def _verify_password(password, pw_hash, salt):
    new_hash, _ = _hash_password(password, salt)
    return secrets.compare_digest(new_hash, pw_hash)

# ==============================================================================
# عميل API ومحرك المزامنة
# ==============================================================================

def unwrap_products_response(data):
    if data is None: return None
    if isinstance(data, list): return data
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], (list, dict)): return data["data"]
        return data
    return data

class MousaCardAPI:
    def __init__(self):
        self.base_url = db.get_setting("api_base_url", API_BASE_URL).rstrip('/')
        self.api_key = db.get_setting("api_key", API_KEY)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=1, pool_block=False)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({
            "api-token": self.api_key, "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "MOStoreBot/200.0", "Connection": "keep-alive", "Accept-Encoding": "gzip, deflate",
        })
        self._cache = {}
        self._cache_timeout = 300
        self._cache_lock = threading.Lock()
        self._last_error = None
        self._last_status = None
        self._last_response = None

    def _request(self, method, endpoint, data=None, params=None, retries=2, use_cache=False, cache_key=None):
        url = f"{self.base_url}{endpoint}" if endpoint.startswith('/') else f"{self.base_url}/{endpoint}"
        if use_cache and cache_key:
            with self._cache_lock:
                cached = self._cache.get(cache_key)
                if cached and time.time() - cached[1] < self._cache_timeout: return cached[0]
        self._last_error = None
        self._last_response = None
        last_exception = None
        for attempt in range(retries + 1):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, timeout=10)
                else:
                    post_data = data if data is not None else params
                    resp = self.session.post(url, json=post_data, params=None, timeout=10)
                self._last_status = resp.status_code
                self._last_response = resp
                if resp.status_code == 200:
                    try:
                        json_data = resp.json()
                        self._last_response = json_data
                        if use_cache and cache_key:
                            with self._cache_lock:
                                self._cache[cache_key] = (json_data, time.time())
                        return json_data
                    except Exception as e:
                        self._last_error = f"JSON parse error: {e}"
                        db.log_api_error(endpoint, self._last_error, str(params)[:500], resp.text[:500])
                        return None
                else:
                    try:
                        err_data = resp.json()
                        err_code = err_data.get("error_code") or err_data.get("code") if isinstance(err_data, dict) else None
                        msg = API_ERROR_CODES.get(err_code, f"HTTP {resp.status_code}: {str(err_data)[:300]}") if err_code else f"HTTP {resp.status_code}: {resp.text[:300]}"
                        self._last_error = msg
                        self._last_response = err_data if isinstance(err_data, dict) else None
                    except Exception:
                        self._last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                    db.log_api_error(endpoint, self._last_error, str(params)[:500])
                    if resp.status_code == 429 and attempt < retries:
                        time.sleep(1)
                        continue
                    return None
            except requests.exceptions.Timeout:
                self._last_error = "انتهت مهلة الاتصال بـ API"
                last_exception = self._last_error
                if attempt < retries:
                    time.sleep(0.3)
                    continue
            except requests.exceptions.ConnectionError:
                self._last_error = "فشل الاتصال بخادم API"
                last_exception = self._last_error
                if attempt < retries:
                    time.sleep(0.3)
                    continue
            except Exception as e:
                self._last_error = str(e)[:200]
                last_exception = self._last_error
                if attempt < retries:
                    time.sleep(0.3)
                    continue
        if last_exception: db.log_api_error(endpoint, last_exception, str(params)[:500])
        return None

    def get_profile(self):
        return self._request("GET", "/client/api/profile", use_cache=True, cache_key="profile")

    def get_products(self, products_id=None, base=None):
        params = {}
        if products_id: params["products_id"] = products_id
        if base: params["base"] = base
        return self._request("GET", "/client/api/products", params=params)

    def get_all_products_full(self):
        raw = self.get_products()
        unwrapped = unwrap_products_response(raw)
        if unwrapped is None: return []
        if isinstance(unwrapped, dict) and "id" in unwrapped and "name" in unwrapped: return [unwrapped]
        if isinstance(unwrapped, list): return [x for x in unwrapped if isinstance(x, dict) and x.get("id") is not None and x.get("name")]
        return []

    def get_products_by_ids(self, id_list):
        if not id_list: return []
        ids_str = ",".join(str(i) for i in id_list)
        raw = self.get_products(products_id=ids_str)
        unwrapped = unwrap_products_response(raw)
        if isinstance(unwrapped, dict) and "id" in unwrapped: return [unwrapped]
        if isinstance(unwrapped, list): return [x for x in unwrapped if isinstance(x, dict) and x.get("id") is not None]
        return []

    def get_content(self, category_id=0):
        try: cid = int(category_id)
        except Exception: return None
        raw = self._request("GET", f"/client/api/content/{cid}")
        if raw is None: return None
        node = raw
        for _ in range(5):
            if isinstance(node, dict) and "categories" not in node and "products" not in node and "data" in node and isinstance(node["data"], (dict, list)):
                node = node["data"]
            else: break
        if isinstance(node, dict):
            cats = node.get("categories") or []
            prods = node.get("products") or []
            return {"categories": cats if isinstance(cats, list) else [], "products": prods if isinstance(prods, list) else []}
        if isinstance(node, list):
            cats, prods = [], []
            for item in node:
                if not isinstance(item, dict): continue
                if any(k in item for k in ("price", "params", "product_type", "qty_values", "base_price", "category_name")):
                    prods.append(item)
                elif ("name" in item) or ("title" in item):
                    cats.append(item)
            return {"categories": cats, "products": prods}
        return None

    def create_order(self, product_id, qty=1, player_id="", order_uuid=None, extra_params=None, phone=""):
        if order_uuid is None: order_uuid = str(uuid.uuid4())
        actual_product_id = str(product_id)
        post_data = {"qty": db_int(qty, 1), "order_uuid": order_uuid}
        if player_id and str(player_id).strip():
            post_data["playerId"] = str(player_id).strip()
            post_data["player_id"] = str(player_id).strip()
        
        phone_value = ""
        if phone and str(phone).strip():
            phone_value = str(phone).strip()
        elif extra_params and isinstance(extra_params, dict):
            for k, v in extra_params.items():
                if v and str(v).strip():
                    k_lower = str(k).lower()
                    if k_lower in ["phone", "phone_number", "mobile", "tel", "telephone", "number"] or "هاتف" in str(k) or "جوال" in str(k):
                        phone_value = str(v).strip()
                        break
        if phone_value: post_data["phone"] = phone_value
        
        if extra_params and isinstance(extra_params, dict):
            for k, v in extra_params.items():
                if k == "variant_api_id" and v: actual_product_id = str(v); break
            for k, v in extra_params.items():
                if v is not None and str(v).strip():
                    k_lower = str(k).lower()
                    if k_lower not in ["player_id", "playerid", "phone", "phone_number", "mobile", "tel", "telephone", "qty", "order_uuid", "variant_api_id", "selected_option_label", "selected_option_price"]:
                        if k not in post_data: post_data[str(k)] = str(v).strip()
        
        result = self._request("POST", f"/client/api/newOrder/{actual_product_id}/params", data=post_data, retries=1)
        
        if not result:
            result = self._request("GET", f"/client/api/newOrder/{actual_product_id}/params", params=post_data, retries=1)
        
        if result and isinstance(result, dict):
            err_code = result.get("error_code") or result.get("code") or result.get("status_code")
            status_val = result.get("status", "")
            
            if err_code:
                try:
                    code_int = int(err_code)
                    if code_int in API_ERROR_CODES:
                        result["error"] = True
                        result["error_message"] = API_ERROR_CODES[code_int]
                        self._last_error = API_ERROR_CODES[code_int]
                except Exception: pass
            
            if status_val and str(status_val).lower() in ("error", "reject", "rejected", "failed"):
                result["error"] = True
                if not self._last_error:
                    self._last_error = result.get("message", "تم رفض الطلب من API")
        
        return result, order_uuid

    def check_orders(self, order_ids):
        if not order_ids: return []
        formatted_ids = [f"ID_{str(o)}" if not str(o).startswith("ID_") else str(o) for o in order_ids]
        orders_str = "[" + ",".join(formatted_ids) + "]"
        raw = self._request("GET", "/client/api/check", params={"orders": orders_str})
        if raw is None: return []
        if isinstance(raw, dict):
            if "data" in raw and isinstance(raw["data"], list): return raw["data"]
            return [raw]
        if isinstance(raw, list): return raw
        return []

    def _deep_search_delivered(self, obj, order_id):
        if not obj: return ""
        if isinstance(obj, dict):
            for key in ("delivered", "delivery", "codes", "pins", "cards", "replay", "replay_api", "data", "result", "items", "accounts"):
                val = obj.get(key)
                if val:
                    if isinstance(val, (list, dict)):
                        if key in ("delivered", "delivery", "codes", "pins", "cards", "replay", "replay_api", "items", "accounts"):
                            return json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else str(val)
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    res = self._deep_search_delivered(v, order_id)
                    if res: return res
        elif isinstance(obj, list):
            for item in obj:
                res = self._deep_search_delivered(item, order_id)
                if res: return res
        return ""

PRODUCT_SYNC_COLUMNS = [
    "api_product_id", "name", "description", "category_id", "original_price", "sell_price", "image_url", "qty_options", 
    "min_quantity", "max_quantity", "step_quantity", "product_api_type", "quantity_type", "requires_player_id", 
    "player_id_label", "required_fields", "api_raw_data", "is_active", "is_variant", "sort_order", "instructions", "stock_quantity"
]

class SyncEngine:
    def __init__(self):
        self.api = MousaCardAPI()
        self.errors = []
        self.stats = {"cats_new": 0, "cats_updated": 0, "prods_new": 0, "prods_updated": 0, "families": 0, "singles": 0, "total_options": 0, "fields": 0, "uncategorized": 0}

    def _insert_product_row(self, data):
        cols, vals = [], []
        for col in PRODUCT_SYNC_COLUMNS:
            if col in data:
                cols.append(col)
                vals.append(data[col])
        if not cols: return None
        cur = db.execute(f"INSERT INTO products ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})", tuple(vals))
        return cur.lastrowid if cur and hasattr(cur, 'lastrowid') else None

    def _update_product_row(self, db_id, data):
        cols, vals = [], []
        for col in PRODUCT_SYNC_COLUMNS:
            if col in data:
                cols.append(f"{col} = ?")
                vals.append(data[col])
        if not cols: return
        vals.append(db_id)
        db.execute(f"UPDATE products SET {', '.join(cols)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(vals))

    def _compute_sell(self, api_price):
        try: profit = float(db.get_setting("profit_percentage", "15") or 0)
        except Exception: profit = 15.0
        try: p = float(api_price)
        except Exception: p = 0.0
        return round(p * (1.0 + profit / 100.0), 2) if p > 0 else 0.0

    def _parse_price(self, v):
        if v is None or isinstance(v, bool): return 0.0
        if isinstance(v, (int, float)):
            try:
                f = float(v)
                return f if f == f and abs(f) != float('inf') and f > 0 else 0.0
            except Exception: return 0.0
        if isinstance(v, dict):
            for pk in ('amount', 'value', 'cost', 'sell', 'price', 'total'):
                if pk in v:
                    p = self._parse_price(v[pk])
                    if p > 0: return p
            return 0.0
        
        cleaned = str(v).replace(",", "").replace("،", "").replace("$", "").replace("ل.س", "").replace("SYP", "").replace("USD", "").replace("ليرة", "").replace("سوري", "").strip()
        try:
            f = float(cleaned)
            return f if f == f and f > 0 else 0.0
        except Exception:
            for n in re.findall(r'[\d.]+', cleaned):
                try:
                    f = float(n)
                    if f > 0: return f
                except Exception: continue
        return 0.0

    def _extract_product_price(self, raw):
        for k in ("price", "sell_price", "base_price", "cost", "amount"):
            if k in raw:
                p = self._parse_price(raw[k])
                if p > 0: return p
        return 0.0

    def _extract_qty_limits(self, raw):
        min_q, max_q, step_q = 1, 0, 1
        qv = raw.get("qty_values")
        if isinstance(qv, dict):
            if "min" in qv: min_q = db_int(qv["min"], 1, 999999999)
            if "max" in qv: max_q = db_int(qv["max"], 0, 999999999)
            if "step" in qv: step_q = db_int(qv["step"], 1, 999999999)
            return min_q, max_q, step_q
        if qv is None and "qty_values" in raw: return 1, 0, 1
        min_q = db_int(raw.get("min_quantity") or raw.get("min_qty") or 1, 1, 999999999)
        max_q = db_int(raw.get("max_quantity") or raw.get("max_qty") or 0, 0, 999999999)
        step_q = db_int(raw.get("step_quantity") or raw.get("step") or 1, 1, 999999999)
        return min_q, max_q, step_q

    def _build_required_fields(self, raw):
        params = raw.get("params")
        fields = []
        if isinstance(params, list):
            for i, p in enumerate(params):
                label = str(p.get("label") or p.get("name") or "").strip() if isinstance(p, dict) else str(p).strip() if p is not None else ""
                if not label or label.lower() in ("none", "null", "nan"): continue
                fields.append({"key": f"field_{i}", "label": label, "type": "text", "required": True})
        return fields

    def _extract_instructions(self, raw):
        for k in ("instructions", "description", "details", "notes", "how_to_use"):
            v = raw.get(k)
            if v and isinstance(v, str) and v.strip(): return strip_html_tags(v)
            if isinstance(v, list): return strip_html_tags(" ".join(str(x) for x in v))
        return ""

    def _parse_real_option_arrays(self, raw):
        OPTION_ARRAY_KEYS = ("options", "packages", "variants", "denominations", "services", "sub_products", "child_products", "plans", "tiers", "cards", "vouchers", "price_list")
        for key in OPTION_ARRAY_KEYS:
            arr = raw.get(key)
            if not isinstance(arr, list) or not arr: continue
            opts = []
            for it in arr:
                if isinstance(it, dict):
                    label = it.get("label") or it.get("name") or it.get("title") or ""
                    price = self._parse_price(it.get("price") or it.get("amount") or it.get("cost") or it.get("sell_price"))
                    api_id = it.get("id") or it.get("api_id") or it.get("product_id") or None
                    qty = it.get("qty") or it.get("quantity")
                    available = bool(it.get("available", True))
                    if not label: continue
                    opt = {"label": str(label).strip(), "base": price, "price": self._compute_sell(price) if price > 0 else None, "available": available}
                    if api_id: opt["api_id"] = str(api_id)
                    if qty: opt["qty"] = db_int(qty, 1)
                    opts.append(opt)
                elif isinstance(it, (int, float)):
                    try:
                        if float(it) > 0: opts.append({"label": str(it), "qty": db_int(it, 1)})
                    except Exception: pass
                elif isinstance(it, str) and it.strip():
                    opts.append({"label": it.strip()})
            if opts:
                opts.sort(key=lambda o: natural_key(o.get("label") or ""))
                return opts
        return []

    def _full_image_url(self, path_or_url):
        if not path_or_url or not isinstance(path_or_url, str): return ""
        v = path_or_url.strip()
        if v.startswith(("http://", "https://", "data:")): return v
        return self.api.base_url + "/" + v.lstrip('/')

    def _extract_image(self, raw):
        for k in ("image_url", "category_img", "image", "img", "img_url", "image_path", "thumbnail", "thumb", "photo", "icon", "picture", "logo"):
            v = raw.get(k)
            if v and isinstance(v, str) and v.strip(): return self._full_image_url(v)
        return ""

    def _crawl_tree(self):
        cat_raws = {}
        cat_parent_hints = {}
        cat_depths = {}
        products_by_cat = {}
        seen_product_in_cat = {}
        queue = deque([("0", 0)])
        visited = set()
        while queue and len(visited) < SYNC_MAX_TREE_NODES:
            api_id, depth = queue.popleft()
            if api_id in visited or depth > SYNC_MAX_TREE_DEPTH: continue
            visited.add(api_id)
            content = self.api.get_content(api_id)
            if not isinstance(content, dict): continue
            for c in (content.get("categories") or []):
                if not isinstance(c, dict): continue
                cid = str(c.get("id") or c.get("category_id") or "")
                if not cid or cid == "0": continue
                if api_id != "0": cat_parent_hints.setdefault(cid, set()).add(api_id)
                if cid not in cat_raws:
                    cat_raws[cid] = c
                    cat_depths[cid] = depth
                elif depth > cat_depths.get(cid, -1):
                    cat_raws[cid] = c
                    cat_depths[cid] = depth
                elif str(c.get("parent_id") or "0") != "0" and str(cat_raws[cid].get("parent_id") or "0") == "0":
                    cat_raws[cid] = c
                if cid not in visited and all(cid != q[0] for q in queue):
                    queue.append((cid, depth + 1))
            plist = content.get("products") or []
            bucket = products_by_cat.setdefault(api_id, [])
            seen_set = seen_product_in_cat.setdefault(api_id, set())
            for p in plist:
                if not isinstance(p, dict) or p.get("id") is None: continue
                pid = str(p["id"])
                if pid in seen_set: continue
                seen_set.add(pid)
                bucket.append((pid, p))
            if SYNC_CRAWL_DELAY > 0: time.sleep(SYNC_CRAWL_DELAY)
        return cat_raws, cat_parent_hints, products_by_cat

    def _resolve_parents(self, cat_raws, cat_parent_hints):
        resolved = {}
        for cid, raw in cat_raws.items():
            parent_id = str(raw.get("parent_id") or "0")
            if parent_id == cid: parent_id = "0"
            if parent_id != "0" and parent_id in cat_raws:
                resolved[cid] = parent_id
                continue
            hints = cat_parent_hints.get(cid, set())
            valid_hints = [h for h in hints if h != "0" and h != cid and h in cat_raws]
            if len(valid_hints) == 1:
                parent_id = valid_hints[0]
            elif len(valid_hints) > 1:
                best = None
                for h in valid_hints:
                    h_raw_parent = str(cat_raws[h].get("parent_id") or "0")
                    if h_raw_parent == "0" or h_raw_parent not in cat_raws:
                        best = h
                        break
                if best: parent_id = best
                else: parent_id = valid_hints[0]
            else:
                parent_id = "0"
            if parent_id != "0" and parent_id not in cat_raws: parent_id = "0"
            resolved[cid] = parent_id
        return resolved

    def _save_categories(self, cat_raws, resolved_parents):
        existing_rows = db.execute("SELECT id, api_category_id FROM categories WHERE api_category_id IS NOT NULL", fetch=True)
        api_to_local = {str(r["api_category_id"]): r["id"] for r in (existing_rows or []) if r["api_category_id"]}
        for api_id, raw in sorted(cat_raws.items(), key=lambda kv: (db_int(kv[1].get("sort_order"), 0, 999999999), str(kv[1].get("name") or ""))):
            name = str(raw.get("name") or raw.get("title") or f"قسم {api_id}").strip()
            image_url = self._extract_image(raw)
            sort_order = db_int(raw.get("sort_order"), 0, 999999999)
            if api_id in api_to_local:
                db.execute("UPDATE categories SET name=?, image_url=COALESCE(NULLIF(?,''), image_url), sort_order=?, is_active=1 WHERE id=?", (name, image_url, sort_order, api_to_local[api_id]))
                self.stats["cats_updated"] += 1
            else:
                cur = db.execute("INSERT INTO categories (name, image_url, api_category_id, parent_id, api_parent_id, sort_order, is_active) VALUES (?, ?, ?, '0', '0', ?, 1)", (name, image_url, api_id, sort_order))
                new_id = cur.lastrowid if cur and hasattr(cur, 'lastrowid') else None
                if not new_id:
                    row = db.execute("SELECT id FROM categories WHERE api_category_id=?", (api_id,), fetchone=True)
                    new_id = row["id"] if row else None
                if new_id:
                    api_to_local[api_id] = new_id
                    self.stats["cats_new"] += 1
        for api_id in cat_raws:
            local_id = api_to_local.get(api_id)
            if not local_id: continue
            parent_api = resolved_parents.get(api_id, "0")
            parent_val = "0"
            if parent_api != "0" and parent_api in api_to_local:
                chain = {api_id}
                cur, ok = parent_api, True
                for _ in range(20):
                    if cur in chain: ok = False; break
                    if cur == "0": break
                    chain.add(cur)
                    cur = resolved_parents.get(cur, "0")
                if ok: parent_val = parent_api
            db.execute("UPDATE categories SET parent_id=?, api_parent_id=? WHERE id=?", (parent_val, parent_api, local_id))
        return api_to_local

    def run(self):
        log_id = db.start_sync_log("full")
        started = time.time()
        try:
            cat_raws, cat_parent_hints, products_by_cat = self._crawl_tree()
            resolved_parents = self._resolve_parents(cat_raws, cat_parent_hints)
            api_to_local = self._save_categories(cat_raws, resolved_parents)
            
            name_to_cat_api = {}
            for cid, r in cat_raws.items():
                nm = str(r.get("name") or "").strip()
                if nm and nm not in name_to_cat_api: name_to_cat_api[nm] = cid
            
            all_items = self.api.get_all_products_full()
            index_by_id = {str(p["id"]): p for p in all_items}
            pid_to_cat, pid_order, order_counter = {}, {}, 0
            for cat_api, plist in products_by_cat.items():
                for pid, praw in plist:
                    if pid not in index_by_id: index_by_id[pid] = praw
                    prev = pid_to_cat.get(pid)
                    if prev is None: pid_to_cat[pid] = cat_api
                    elif prev == "0" and cat_api != "0": pid_to_cat[pid] = cat_api
                    if pid not in pid_order:
                        pid_order[pid] = order_counter
                        order_counter += 1
            all_ids = list(index_by_id.keys())
            
            if SYNC_FETCH_PRODUCT_DETAILS and all_ids:
                chunks = [all_ids[i:i + SYNC_DETAILS_CHUNK_SIZE] for i in range(0, len(all_ids), SYNC_DETAILS_CHUNK_SIZE)]
                detailed_map = {}
                with ThreadPoolExecutor(max_workers=SYNC_PARALLEL_WORKERS) as pool:
                    futures = {pool.submit(self.api.get_products_by_ids, ch): ch for ch in chunks}
                    for fut in as_completed(futures):
                        try:
                            items = fut.result()
                            if isinstance(items, list):
                                for it in items:
                                    if isinstance(it, dict) and it.get("id") is not None: detailed_map[str(it["id"])] = it
                        except Exception as e:
                            self.errors.append(f"details chunk error: {e}")
                for pid, det in detailed_map.items():
                    if pid in index_by_id:
                        merged = dict(index_by_id[pid])
                        merged.update(det)
                        index_by_id[pid] = merged
                    else: index_by_id[pid] = det
            
            groups, singles = {}, []
            for pid in all_ids:
                raw = index_by_id[pid]
                cname = str(raw.get("category_name") or "").strip()
                if not cname or cname.lower() in ("none", "null"):
                    singles.append(pid)
                    continue
                g = groups.setdefault(cname, {"name": cname, "members": []})
                g["members"].append(pid)
            
            seen_api_keys = set()
            for g in groups.values():
                if len(g["members"]) >= 2:
                    try: self._save_family(g, index_by_id, pid_to_cat, api_to_local, name_to_cat_api, seen_api_keys, pid_order)
                    except Exception as e: self.errors.append(f"save family '{g['name']}': {e}")
            for g in groups.values():
                if len(g["members"]) == 1:
                    pid = g["members"][0]
                    try: self._save_single(index_by_id[pid], pid, pid_to_cat, api_to_local, name_to_cat_api, seen_api_keys, pid_order)
                    except Exception as e: self.errors.append(f"save single {pid}: {e}")
            for pid in singles:
                try: self._save_single(index_by_id[pid], pid, pid_to_cat, api_to_local, name_to_cat_api, seen_api_keys, pid_order)
                except Exception as e: self.errors.append(f"save standalone {pid}: {e}")
            
            deactivated = 0
            if SYNC_CLEAN_ORPHANS and seen_api_keys:
                all_rows = db.execute("SELECT id, api_product_id FROM products WHERE api_product_id IS NOT NULL", fetch=True) or []
                for r in all_rows:
                    if str(r["api_product_id"]) not in seen_api_keys:
                        db.execute("UPDATE products SET is_active=0 WHERE id=?", (r["id"],))
                        deactivated += 1
            
            elapsed = round(time.time() - started, 1)
            db.set_setting("last_sync", str(int(time.time())))
            db.set_setting("last_full_sync", str(int(time.time())))
            total_cats = self.stats["cats_new"] + self.stats["cats_updated"]
            total_products_saved = self.stats["families"] + self.stats["singles"]
            summary = (f"cats={total_cats}, items={len(all_ids)}, محفوظ={total_products_saved} (عائلات={self.stats['families']}, مستقلة={self.stats['singles']}), إجمالي الخيارات={self.stats['total_options']}, حقول={self.stats['fields']}, بلا قسم={self.stats['uncategorized']}, deactivated={deactivated}, errors={len(self.errors)}, time={elapsed}s")
            if log_id:
                db.complete_sync_log(log_id, categories=total_cats, products=self.stats["prods_new"], updated=self.stats["prods_updated"], merged=self.stats["families"], errors=self.errors, details=summary)
            return summary
        except Exception as e:
            err = f"خطأ عام في المزامنة: {e}"
            self.errors.append(err)
            if log_id:
                db.complete_sync_log(log_id, errors=self.errors, details=err)
            return f"FAILED: {err}"

    def _place_category(self, member_pids, index_by_id, pid_to_cat, api_to_local, name_to_cat_api):
        votes = {}
        for pid in member_pids:
            c = pid_to_cat.get(pid)
            if c and c != "0": votes[c] = votes.get(c, 0) + 1
        if votes:
            best = max(votes.items(), key=lambda kv: kv[1])[0]
            if best in api_to_local: return api_to_local[best]
        for pid in member_pids:
            parent = str(index_by_id[pid].get("parent_id") or "0")
            if parent not in ("0", "None", "null", "") and parent in api_to_local: return api_to_local[parent]
        if member_pids:
            first = index_by_id[member_pids[0]]
            cname = str(first.get("category_name") or "").strip()
            if cname:
                capi = name_to_cat_api.get(cname)
                if capi and capi in api_to_local: return api_to_local[capi]
        return None

    def _save_family(self, g, index_by_id, pid_to_cat, api_to_local, name_to_cat_api, seen_api_keys, pid_order):
        members = sorted(g["members"], key=lambda p: pid_order.get(p, 999999))
        cname = g["name"]
        fam_key = f"FAM::{cname}"
        seen_api_keys.add(fam_key)
        first = index_by_id[members[0]]
        cat_local = self._place_category(members, index_by_id, pid_to_cat, api_to_local, name_to_cat_api)
        if not cat_local: self.stats["uncategorized"] += 1
        options, seen_opt = [], set()
        for pid in members:
            raw = index_by_id[pid]
            label = str(raw.get("name") or "").strip()
            if not label: continue
            base = self._extract_product_price(raw)
            sell = self._compute_sell(base)
            key = f"{pid}|{label}"
            if key in seen_opt: continue
            seen_opt.add(key)
            available = bool(raw.get("available", True))
            options.append({"label": label, "base": base, "price": sell if sell > 0 else None, "api_id": pid, "available": available})
        for pid in members:
            for o in self._parse_real_option_arrays(index_by_id[pid]):
                key = f"{o.get('api_id', '')}|{o.get('label', '')}"
                if key in seen_opt: continue
                seen_opt.add(key)
                options.append(o)
        options.sort(key=lambda o: natural_key(o.get("label") or ""))
        fields = self._build_required_fields(first)
        ptype = str(first.get("product_type") or "package").lower()
        image_url = self._extract_image(first)
        if not image_url:
            for pid in members:
                image_url = self._extract_image(index_by_id[pid])
                if image_url: break
        available_any = any(o.get("available", True) for o in options) if options else bool(first.get("available", True))
        instructions = self._extract_instructions(first)
        description = strip_html_tags(first.get("description") or first.get("instructions") or "")
        min_prices = [o["price"] for o in options if o.get("price")]
        sell_final = round(safe_float(min(min_prices) if min_prices else 0.0), 2)
        base_first = round(safe_float(self._extract_product_price(first)), 2)
        sort_hint = db_int(min(pid_order.get(p, 999999) for p in members), 999999, 999999999)
        row = {
            "api_product_id": fam_key, "name": cname, "description": description, "category_id": cat_local if cat_local else None, "original_price": base_first,
            "sell_price": sell_final, "image_url": image_url, "qty_options": json.dumps(options, ensure_ascii=False) if options else None,
            "min_quantity": 1, "max_quantity": 1, "step_quantity": 1, "product_api_type": ptype, "quantity_type": "package",
            "requires_player_id": 1 if fields else 0, "player_id_label": fields[0]["label"] if fields else "معرف اللاعب",
            "required_fields": json.dumps(fields, ensure_ascii=False) if fields else None, "api_raw_data": json.dumps({"family_members": members, "sample": {k: first.get(k) for k in ("params", "product_type", "qty_values")}}, ensure_ascii=False, default=str)[:5000],
            "is_active": 1, "is_variant": 0, "sort_order": sort_hint, "instructions": instructions, "stock_quantity": 1 if available_any else 0
        }
        existing = db.execute("SELECT id FROM products WHERE api_product_id=?", (fam_key,), fetchone=True)
        if existing:
            self._update_product_row(existing["id"], row)
            self.stats["prods_updated"] += 1
        else:
            new_id = self._insert_product_row(row)
            if new_id: self.stats["prods_new"] += 1
            else: self.stats["prods_updated"] += 1
        self.stats["families"] += 1
        self.stats["total_options"] += len(options)
        self.stats["fields"] += len(fields)

    def _save_single(self, raw, pid, pid_to_cat, api_to_local, name_to_cat_api, seen_api_keys, pid_order):
        seen_api_keys.add(pid)
        name = str(raw.get("name") or raw.get("title") or f"منتج {pid}").strip()
        cat_local = self._place_category([pid], {pid: raw}, pid_to_cat, api_to_local, name_to_cat_api)
        if not cat_local: self.stats["uncategorized"] += 1
        base_price = round(safe_float(self._extract_product_price(raw)), 2)
        sell = self._compute_sell(base_price)
        native_opts = self._parse_real_option_arrays(raw)
        fields = self._build_required_fields(raw)
        min_q, max_q, step_q = self._extract_qty_limits(raw)
        ptype = str(raw.get("product_type") or "package").lower()
        image_url = self._extract_image(raw)
        available = bool(raw.get("available", True))
        instructions = self._extract_instructions(raw)
        description = strip_html_tags(raw.get("description") or raw.get("instructions") or "")
        if native_opts:
            prices = [o["price"] for o in native_opts if o.get("price")]
            sell_final = round(min(prices) if prices else sell, 2)
        else:
            sell_final = round(sell,2)
        row = {
            "api_product_id": pid, "name": name, "description": description, "category_id": cat_local if cat_local else None, "original_price": base_price,
            "sell_price": sell_final, "image_url": image_url, "qty_options": json.dumps(native_opts, ensure_ascii=False) if native_opts else None,
            "min_quantity": min_q, "max_quantity": max_q, "step_quantity": step_q, "product_api_type": ptype, "quantity_type": "amount" if ptype == "amount" else "package",
            "requires_player_id": 1 if fields else 0, "player_id_label": fields[0]["label"] if fields else "معرف اللاعب",
            "required_fields": json.dumps(fields, ensure_ascii=False) if fields else None, "api_raw_data": json.dumps(raw, ensure_ascii=False, default=str)[:15000],
            "is_active": 1, "is_variant": 0, "sort_order": db_int(pid_order.get(pid, 999999), 999999, 999999999), "instructions": instructions, "stock_quantity": 1 if available else 0
        }
        existing = db.execute("SELECT id FROM products WHERE api_product_id=?", (pid,), fetchone=True)
        if existing:
            self._update_product_row(existing["id"], row)
            self.stats["prods_updated"] += 1
        else:
            new_id = self._insert_product_row(row)
            if new_id: self.stats["prods_new"] += 1
            else: self.stats["prods_updated"] += 1
        self.stats["singles"] += 1
        self.stats["total_options"] += len(native_opts)
        self.stats["fields"] += len(fields)

api_client = MousaCardAPI()

# ==============================================================================
# دوال مساعدة
# ==============================================================================

def generate_qr_base64(data):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None

def save_image_from_bytes(image_bytes, prefix="img"):
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}_{int(time.time())}.jpg"
    filepath = os.path.join(IMAGES_DIR, filename)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(filepath, "JPEG", quality=85)
        return filename
    except Exception:
        try:
            with open(filepath, "wb") as f: f.write(image_bytes)
            return filename
        except Exception: return None

def download_image(url):
    if not url: return None
    if url.startswith("data:"):
        try:
            header, encoded = url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            return save_image_from_bytes(image_bytes, "b64img")
        except Exception: return None
    if not url.startswith("http"): return None
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200: return save_image_from_bytes(resp.content, "sync_img")
    except Exception as e:
        debug_print(f"Failed to download image {url}: {e}", "WARN")
    return None

def format_price(price):
    cur = "SYP"
    try:
        if 'currency' in session and session['currency']:
            cur = session['currency']
        else:
            cur = db.get_setting("currency", CURRENCY)
    except RuntimeError:
        cur = db.get_setting("currency", CURRENCY)
    except Exception:
        cur = db.get_setting("currency", CURRENCY)
    if cur not in ("USD", "SYP"):
        cur = "SYP"
        
    try:
        p = float(price or 0)
        if cur == "USD":
            rate = float(db.get_setting("price_exchange_rate", "15000") or 15000)
            if rate > 0:
                p_usd = p / rate
                return f"{p_usd:,.2f} $"
        if p >= 1000: return f"{p:,.0f} ل.س"
        return f"{p:,.2f} ل.س"
    except:
        return "0 ل.س"

def convert_usd_to_syp(usd_amount):
    try:
        rate = float(db.get_setting("price_exchange_rate", "1") or 1)
    except Exception:
        rate = 1.0
    try:
        usd = float(usd_amount or 0)
    except Exception:
        usd = 0.0
    return round(usd * rate, 2)

def format_shipping_price(sm):
    currency = db.get_setting("currency", CURRENCY)
    if sm is not None and not isinstance(sm, dict):
        try:
            sm = row_to_dict(sm)
        except Exception:
            sm = {}
    if sm is None:
        sm = {}
    try:
        price_usd = float(sm.get("price_usd") or 0)
    except Exception:
        price_usd = 0.0
    try:
        price_syp = float(sm.get("price") or 0)
    except Exception:
        price_syp = 0.0
    
    if price_usd > 0:
        converted = convert_usd_to_syp(price_usd)
        return f"{converted:,.0f} {currency} (~{price_usd:.2f}$)", converted
    else:
        return f"{price_syp:,.0f} {currency}", price_syp

def is_admin(telegram_id): return telegram_id in ADMIN_IDS

def get_supporter_perms_keyboard(selected_perms):
    markup = InlineKeyboardMarkup(row_width=1)
    perms_set = set(selected_perms)
    
    def perm_btn(text, perm, icon_str="⚙️"):
        prefix = "✅ " if perm in perms_set else "⬜ "
        return InlineKeyboardButton(prefix + icon_str + " " + text, callback_data=f"admin_perm_toggle_{perm}")
    
    markup.add(perm_btn("إدارة المنتجات", "manage_products", "📦"))
    markup.add(perm_btn("إدارة الطلبات والشحن", "manage_orders", "🚚"))
    markup.add(perm_btn("شحن المحفظة", "manage_topups", "💰"))
    markup.add(perm_btn("إدارة المستخدمين", "manage_users", "👥"))
    markup.add(perm_btn("تذاكر الدعم", "manage_tickets", "📞"))
    markup.add(perm_btn("محادثات الدعم", "manage_chats", "💬"))
    
    markup.add(InlineKeyboardButton("💾 حفظ الصلاحيات", callback_data="admin_save_perms"))
    markup.add(InlineKeyboardButton("❌ إلغاء", callback_data="admin_cancel"))
    return markup

def get_supporter_panel_keyboard(perms):
    markup = InlineKeyboardMarkup(row_width=2)
    perms_set = set(perms)
    
    if "manage_products" in perms_set:
        markup.add(
            InlineKeyboardButton("📦 ➕ إضافة منتج", callback_data="admin_add_product"),
            InlineKeyboardButton("📦 📋 إدارة المنتجات", callback_data="admin_list_products")
        )
        markup.add(
            InlineKeyboardButton("📦 🔄 مزامنة منتج", callback_data="admin_sync_product"),
            InlineKeyboardButton("📦 🔍 بحث منتج", callback_data="admin_search_product")
        )
        markup.add(
            InlineKeyboardButton("🏷️ 🎁 إدارة العروض", callback_data="admin_offers"),
            InlineKeyboardButton("🏷️ ➕ عرض جديد", callback_data="admin_add_offer_btn")
        )
        markup.add(
            InlineKeyboardButton("📂 ➕ إضافة قسم", callback_data="admin_add_category"),
            InlineKeyboardButton("📂 📋 إدارة الأقسام", callback_data="admin_list_categories")
        )
        markup.add(InlineKeyboardButton("🔄 💲 إعادة حساب الأسعار", callback_data="admin_recalc_prices"))

    if "manage_orders" in perms_set:
        markup.add(
            InlineKeyboardButton("📋 📦 جميع الطلبات", callback_data="admin_orders"),
            InlineKeyboardButton("🚚 ✅ موافقة طلبات الشحن", callback_data="admin_shipping_approvals")
        )
        markup.add(
            InlineKeyboardButton("📊 📈 إحصائيات المبيعات", callback_data="admin_sales_stats"),
            InlineKeyboardButton("💰 📋 المعاملات", callback_data="admin_transactions")
        )
        markup.add(
            InlineKeyboardButton("📤 📋 تصدير الطلبات", callback_data="admin_export_orders"),
            InlineKeyboardButton("🚚 📋 طرق الشحن", callback_data="admin_shipping")
        )
        markup.add(
            InlineKeyboardButton("💳 📋 طرق الدفع", callback_data="admin_payments"),
            InlineKeyboardButton("🚚 ➕ طريقة شحن (ل.س)", callback_data="admin_add_shipping_btn")
        )
        markup.add(
            InlineKeyboardButton("🚚 💵 طريقة شحن بالدولار", callback_data="admin_add_shipping_usd_btn"),
            InlineKeyboardButton("💳 ➕ طريقة دفع جديدة", callback_data="admin_add_payment_btn")
        )

    if "manage_topups" in perms_set:
        markup.add(
            InlineKeyboardButton("💰 📋 طلبات الشحن", callback_data="admin_topup_requests"),
            InlineKeyboardButton("📥 📋 شحن المحفظة", callback_data="admin_topup_methods")
        )
        markup.add(
            InlineKeyboardButton("📥 ➕ طريقة شحن محفظة (ل.س)", callback_data="admin_add_topup_btn"),
            InlineKeyboardButton("📥 💵 طريقة شحن محفظة (دولار)", callback_data="admin_add_topup_usd_btn")
        )

    if "manage_users" in perms_set:
        markup.add(
            InlineKeyboardButton("👥 📋 إدارة المستخدمين", callback_data="admin_users"),
            InlineKeyboardButton("🔒 📋 المستخدمون المحظورون", callback_data="admin_banned_users")
        )
        markup.add(
            InlineKeyboardButton("🎁 💰 تعديل رصيد", callback_data="admin_edit_balance"),
            InlineKeyboardButton("👤 🔍 بحث مستخدم", callback_data="admin_search_user")
        )
        markup.add(
            InlineKeyboardButton("⭐ 📋 مستخدمو VIP", callback_data="admin_vip_users"),
            InlineKeyboardButton("➕ 🛡️ إضافة داعم", callback_data="admin_add_supporter")
        )
        markup.add(InlineKeyboardButton("👥 📋 قائمة الداعمين", callback_data="admin_list_supporters"))

    if "manage_tickets" in perms_set:
        markup.add(InlineKeyboardButton("📞 🎫 تذاكر الدعم", callback_data="admin_support"))
        
    if "manage_chats" in perms_set:
        markup.add(InlineKeyboardButton("💬 💬 محادثات الدعم", callback_data="admin_chats"))
        
    markup.add(InlineKeyboardButton("↩️ رجوع للرئيسية", callback_data="user_back_to_main"))
    return markup

def check_supporter_permission(user_id, callback_data):
    if is_admin(user_id): return True
    user = db.execute("SELECT role, permissions FROM users WHERE telegram_id=?", (user_id,), fetchone=True)
    if not user or user["role"] != "supporter": return False
    
    if callback_data in ["admin_back", "admin_cancel", "user_back_to_main"]:
        return True
        
    perms = (user["permissions"] or "").split(",")
    
    if "manage_orders" in perms and any(callback_data == c or callback_data.startswith(c) for c in [
        "admin_orders", "admin_shipping_approvals", "admin_export_orders", "admin_sales_stats", 
        "admin_transactions", "admin_ship_approve_", "admin_ship_reject_", 
        "admin_shipping", "admin_add_shipping_btn", "admin_add_shipping_usd_btn", 
        "admin_payments", "admin_add_payment_btn", "admin_add_shipping", 
        "admin_add_shipping_usd", "admin_add_payment", "admin_set_method_img", 
        "admin_skip_method_img", "admin_set_numeric"
    ]):
        return True
        
    if "manage_topups" in perms and any(callback_data == c or callback_data.startswith(c) for c in [
        "admin_topup_requests", "admin_topup_methods", "admin_add_topup_btn", 
        "admin_add_topup_usd_btn", "admin_approve_top_", "admin_reject_top_", 
        "admin_del_topup_", "admin_add_topup", "admin_add_topup_usd"
    ]):
        return True
        
    if "manage_users" in perms and any(callback_data == c or callback_data.startswith(c) for c in [
        "admin_users", "admin_banned_users", "admin_edit_balance", "admin_search_user", 
        "admin_quick_edit_bal_", "admin_ban_", "admin_unban_", "admin_vip_users", 
        "admin_add_supporter", "admin_list_supporters", "admin_save_perms", 
        "admin_perm_toggle_", "admin_edit_balance_amount", "admin_select_supporter_perms"
    ]):
        return True
        
    if "manage_products" in perms and any(callback_data == c or callback_data.startswith(c) for c in [
        "admin_add_product", "admin_list_products", "admin_sync_product", "admin_search_product", 
        "admin_offers", "admin_add_offer_btn", "admin_stop_offer_", "admin_add_category", 
        "admin_list_categories", "admin_move_subcat", "admin_recalc_prices",
        "admin_add_gift_btn", "admin_gifts", "admin_add_gift", "admin_add_offer",
        "admin_add_discount", "admin_discounts", "admin_add_blog", "admin_add_faq", 
        "admin_add_contest", "admin_add_category"
    ]):
        return True
        
    if "manage_tickets" in perms and callback_data == "admin_support":
        return True
        
    if "manage_chats" in perms and callback_data == "admin_chats":
        return True
        
    return False

def is_admin_or_supporter(user_id, callback_data):
    if is_admin(user_id): return True
    return check_supporter_permission(user_id, callback_data)

def get_or_create_user(telegram_id, username=None, referrer_id=None):
    user = db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,), fetchone=True)
    if user:
        if username and user["username"] != username:
            try:
                db.execute("UPDATE users SET username=? WHERE telegram_id=?", (username, telegram_id))
                user = db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,), fetchone=True)
            except Exception: pass
        return row_to_dict(user)
    uname = username or f"tg_{telegram_id}"
    base_uname = uname
    counter = 1
    while True:
        exists = db.execute("SELECT id FROM users WHERE username = ?", (uname,), fetchone=True)
        if not exists: break
        uname = f"{base_uname}_{counter}"
        counter += 1
        if counter > 100:
            uname = f"tg_{telegram_id}_{uuid.uuid4().hex[:6]}"
            break
    referral_code = f"REF{telegram_id}_{uuid.uuid4().hex[:6].upper()}"
    try:
        db.execute("INSERT INTO users (telegram_id, username, balance, min_balance, referral_code, referred_by) VALUES (?, ?, 0, ?, ?, ?)", 
                    (telegram_id, uname, float(db.get_setting("default_min_balance", "0")), referral_code, referrer_id))
    except Exception:
        uname = f"u_{telegram_id}_{uuid.uuid4().hex[:8]}"
        db.execute("INSERT INTO users (telegram_id, username, balance, min_balance, referral_code, referred_by) VALUES (?, ?, 0, ?, ?, ?)", 
                    (telegram_id, uname, float(db.get_setting("default_min_balance", "0")), referral_code, referrer_id))
    user = db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,), fetchone=True)
    return row_to_dict(user) if user else None

_vip_cache = {"data": {}, "ts": 0, "lock": threading.Lock()}
VIP_CACHE_TTL = 60

def check_vip_status(user_id):
    now = time.time()
    with _vip_cache["lock"]:
        if (now - _vip_cache["ts"]) > VIP_CACHE_TTL:
            _vip_cache["data"] = {}
            _vip_cache["ts"] = now
        cached = _vip_cache["data"].get(user_id)
        if cached is not None:
            return cached
    
    user = db.execute("SELECT total_spent, is_vip, vip_level FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user:
        result = (False, 0)
    else:
        vip_threshold = float(db.get_setting("vip_threshold", "100000"))
        is_vip = user["is_vip"] == 1 or (user["total_spent"] or 0) >= vip_threshold
        if is_vip and user["is_vip"] == 0:
            db.execute("UPDATE users SET is_vip=1 WHERE id=?", (user_id,))
        level = 0
        spent = user["total_spent"] or 0
        if spent >= float(db.get_setting("tier_platinum_min", "500000")): level = 4
        elif spent >= float(db.get_setting("tier_gold_min", "200000")): level = 3
        elif spent >= float(db.get_setting("tier_silver_min", "50000")): level = 2
        elif spent >= float(db.get_setting("tier_bronze_min", "0")): level = 1
        result = (is_vip, level)
    
    with _vip_cache["lock"]:
        _vip_cache["data"][user_id] = result
    return result

def get_vip_level_name(level):
    names = {0: "عادي", 1: "برونزي", 2: "فضي", 3: "ذهبي", 4: "بلاتيني"}
    return names.get(level, "عادي")

def get_vip_badge(level):
    badges = {0: "", 1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}
    return badges.get(level, "")

def create_notification(user_id, title, message, ntype="info", broadcast=False):
    db.execute("INSERT INTO notifications (user_id, title, message, notification_type, is_broadcast) VALUES (?, ?, ?, ?, ?)", (user_id if not broadcast else None, title, message, ntype, 1 if broadcast else 0))

def _send_telegram_async(chat_id, text, parse_mode="HTML"):
    def _send():
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode)
        except Exception as e:
            debug_print(f"Telegram send failed to {chat_id}: {e}", "WARN")
    threading.Thread(target=_send, daemon=True).start()

def send_user_notification(user_id, title, message):
    create_notification(user_id, title, message, "info", broadcast=False)
    user = db.execute("SELECT telegram_id FROM users WHERE id=?", (user_id,), fetchone=True)
    if user and user["telegram_id"]:
        _send_telegram_async(user["telegram_id"], f"🔔 <b>{title}</b>\n\n{message}")
    
    try:
        if hasattr(app, '_send_push_to_user'):
            app._send_push_to_user(user_id, title, message, {
                "type": "notification",
                "user_id": str(user_id),
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        debug_print(f"Push notification error: {e}", "WARN")

def send_broadcast_telegram(title, message, image_path=None):
    def _send_batch(users, title, message, image_path):
        sent, failed = 0, 0
        for u in users:
            try:
                if u["telegram_id"]:
                    if image_path:
                        full_path = os.path.join(IMAGES_DIR, image_path)
                        if os.path.exists(full_path):
                            with open(full_path, 'rb') as photo:
                                bot.send_photo(u["telegram_id"], photo, caption=f"📢 <b>{title}</b>\n\n{message}")
                        else:
                            bot.send_message(u["telegram_id"], f"📢 <b>{title}</b>\n\n{message}")
                    else:
                        bot.send_message(u["telegram_id"], f"📢 <b>{title}</b>\n\n{message}")
                    sent += 1
                    time.sleep(0.05)
            except Exception:
                failed += 1
        debug_print(f"Broadcast TG: sent={sent}, failed={failed}", "INFO")
        
        db.execute("INSERT INTO broadcast_messages (title, message, image_path, total_sent, total_failed) VALUES (?, ?, ?, ?, ?)",
                   (title, message, image_path, sent, failed))
    
    create_notification(None, title, message, "info", broadcast=True)
    users = db.execute("SELECT telegram_id FROM users WHERE is_banned=0 AND telegram_id IS NOT NULL", fetch=True) or []
    threading.Thread(target=_send_batch, args=(users, title, message, image_path), daemon=True).start()
    
    try:
        if hasattr(app, '_send_push_to_all_users'):
            def _send_push_broadcast():
                app._send_push_to_all_users(title, message, {
                    "type": "broadcast",
                    "title": title,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                })
            threading.Thread(target=_send_push_broadcast, daemon=True).start()
    except Exception as e:
        debug_print(f"Push broadcast error: {e}", "WARN")
    
    return None, None

def send_notification_to_user(user_id, title, message):
    create_notification(user_id, title, message, "admin", broadcast=False)
    user = db.execute("SELECT telegram_id FROM users WHERE id=?", (user_id,), fetchone=True)
    if user and user["telegram_id"]:
        _send_telegram_async(user["telegram_id"], f"🔔 <b>{title}</b>\n\n{message}")
    
    try:
        if hasattr(app, '_send_push_to_user'):
            app._send_push_to_user(user_id, title, message, {
                "type": "admin_notification",
                "user_id": str(user_id),
                "title": title,
                "message": message
            })
    except Exception as e:
        debug_print(f"Push notification error: {e}", "WARN")

def notify_support_users(title, message):
    notified_ids = set()
    supporters = db.execute("SELECT id, telegram_id FROM users WHERE role IN ('admin', 'supporter')", fetch=True) or []
    for s in supporters:
        send_notification_to_user(s["id"], title, message)
        notified_ids.add(s["id"])
        if s["telegram_id"]:
            _send_telegram_async(s["telegram_id"], f"🔔 <b>{title}</b>\n\n{message}")
    
    for admin_tg_id in ADMIN_IDS:
        admin_user = db.execute("SELECT id FROM users WHERE telegram_id=?", (admin_tg_id,), fetchone=True)
        if admin_user and admin_user["id"] not in notified_ids:
            send_notification_to_user(admin_user["id"], title, message)
            notified_ids.add(admin_user["id"])
        elif not admin_user:
            admin_user = get_or_create_user(admin_tg_id)
            if admin_user and admin_user["id"] not in notified_ids:
                send_notification_to_user(admin_user["id"], title, message)
                notified_ids.add(admin_user["id"])

def add_transaction(user_id, amount, ttype, description="", reference_id=""):
    user = db.execute("SELECT balance FROM users WHERE id = ?", (user_id,), fetchone=True)
    balance_after = (user["balance"] if user else 0) + amount
    db.execute("INSERT INTO transactions (user_id, amount, transaction_type, description, reference_id, balance_after) VALUES (?, ?, ?, ?, ?, ?)", (user_id, amount, ttype, description, reference_id, balance_after))

def add_loyalty_points(user_id, amount):
    points_per = float(db.get_setting("loyalty_points_per_currency", "1"))
    points = int(amount * points_per)
    if points > 0:
        db.execute("UPDATE users SET loyalty_points = loyalty_points + ? WHERE id = ?", (points, user_id))
    return points

def is_maintenance_active():
    row = db.execute("SELECT * FROM maintenance WHERE is_active = 1 ORDER BY id DESC LIMIT 1", fetchone=True)
    if not row: return False, None
    if row["end_time"]:
        try:
            end_ts = datetime.fromisoformat(row["end_time"])
            if datetime.now() > end_ts: return False, None
        except Exception: pass
    return True, row_to_dict(row)

def get_maintenance_remaining():
    row = db.execute("SELECT * FROM maintenance WHERE is_active = 1 ORDER BY id DESC LIMIT 1", fetchone=True)
    if not row or not row["end_time"]: return 0
    try:
        end_ts = datetime.fromisoformat(row["end_time"])
        remaining = (end_ts - datetime.now()).total_seconds()
        return max(0, int(remaining))
    except Exception: return 0

def start_maintenance(duration, message):
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration) if duration > 0 else None
    db.execute("INSERT INTO maintenance (is_active, start_time, end_time, duration_minutes, message) VALUES (1, ?, ?, ?, ?)", 
               (start_time.isoformat(), end_time.isoformat() if end_time else None, duration, message))
    db.set_setting("maintenance_mode", "on")
    db.set_setting("maintenance_message", message)

def stop_maintenance():
    db.execute("UPDATE maintenance SET is_active=0 WHERE is_active=1")
    db.set_setting("maintenance_mode", "off")

def get_maintenance_images():
    images = db.execute("SELECT * FROM maintenance_images WHERE is_active=1 ORDER BY sort_order ASC, id ASC", fetch=True) or []
    return [dict(img) for img in images]

def add_maintenance_image(image_path, title=""):
    db.execute("INSERT INTO maintenance_images (image_path, title, is_active, sort_order) VALUES (?, ?, 1, 0)", (image_path, title))

def delete_maintenance_image(image_id):
    img = db.execute("SELECT image_path FROM maintenance_images WHERE id=?", (image_id,), fetchone=True)
    if img:
        try:
            filepath = os.path.join(IMAGES_DIR, img["image_path"])
            if os.path.exists(filepath): os.remove(filepath)
        except Exception: pass
    db.execute("DELETE FROM maintenance_images WHERE id=?", (image_id,))

def get_active_gifts():
    gifts = db.execute("SELECT * FROM gift_codes WHERE is_active=1 AND is_sold=0 ORDER BY id DESC", fetch=True) or []
    return [dict(g) for g in gifts]

def add_gift_code(name, description, price, code, image_path=None, created_by=None):
    db.execute("INSERT INTO gift_codes (name, description, price, code, image_path, is_active, is_sold, created_by) VALUES (?, ?, ?, ?, ?, 1, 0, ?)", (name, description, price, code, image_path, created_by))

def buy_gift_code(gift_id, user_id):
    gift = db.execute("SELECT * FROM gift_codes WHERE id=? AND is_active=1 AND is_sold=0", (gift_id,), fetchone=True)
    if not gift: return None, "كود الهدية غير متاح أو تم بيعه"
    user = db.execute("SELECT balance FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return None, "المستخدم غير موجود"
    if user["balance"] < gift["price"]:
        return None, f"رصيدك غير كافٍ. سعر الهدية {format_price(gift['price'])} ورصيدك الحالي {format_price(user['balance'])}"
    order_id = f"GIFT-{uuid.uuid4().hex[:12].upper()}"
    db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (gift["price"], user_id))
    db.execute("UPDATE gift_codes SET is_sold=1, sold_to_user_id=?, sold_at=CURRENT_TIMESTAMP, order_id=? WHERE id=?", (user_id, order_id, gift_id))
    db.execute("UPDATE users SET total_orders = total_orders + 1, total_spent = total_spent + ? WHERE id = ?", (gift["price"], user_id))
    add_transaction(user_id, -gift["price"], "gift_purchase", f"شراء كود هدية: {gift['name']}", order_id)
    add_loyalty_points(user_id, gift["price"])
    check_vip_status(user_id)
    return dict(gift), order_id

def get_product_images(product):
    images = []
    if product.get("image_url"): images.append({"type": "remote", "url": product["image_url"]})
    if product.get("all_images"):
        try:
            all_imgs = json.loads(product["all_images"])
            if isinstance(all_imgs, list):
                for img in all_imgs:
                    if isinstance(img, str) and img.startswith("http"):
                        if not any(i["url"] == img for i in images):
                            images.append({"type": "remote", "url": img})
        except Exception: pass
    return images if images else [{"type": "placeholder", "url": ""}]

def parse_qty_options(qty_options_str):
    if not qty_options_str: return []
    try:
        opts = json.loads(qty_options_str)
        if isinstance(opts, list):
            result = []
            for opt in opts:
                if isinstance(opt, dict):
                    label = opt.get("label") or opt.get("name") or ""
                    price = opt.get("price")
                    api_id = opt.get("api_id") or opt.get("product_id")
                    qty = opt.get("qty")
                    if label:
                        result.append({"label": str(label).strip(), "price": price, "qty": qty, "api_id": str(api_id) if api_id else None})
            return result
    except Exception: pass
    return []

def parse_required_fields(required_fields_str):
    if not required_fields_str: return []
    try:
        fields = json.loads(required_fields_str)
        if isinstance(fields, list):
            normalized = []
            for f in fields:
                if isinstance(f, str):
                    normalized.append({"name": f, "label": f, "type": "text", "placeholder": f"أدخل {f}", "required": True, "hint": "", "options": None})
                elif isinstance(f, dict):
                    name = f.get("name") or f.get("key") or "field"
                    label = f.get("label") or f.get("name") or "حقل"
                    ftype = f.get("type") or "text"
                    normalized.append({
                        "name": name, "label": label, "type": ftype, "placeholder": f.get("placeholder") or "",
                        "required": f.get("required", True), "hint": f.get("hint") or "", "options": f.get("options")
                    })
            return normalized
    except Exception: pass
    return []

_categories_cache = {"data": None, "ts": 0, "lock": threading.Lock()}
CATEGORIES_CACHE_TTL = 60

def get_hierarchical_categories():
    now = time.time()
    with _categories_cache["lock"]:
        if _categories_cache["data"] is not None and (now - _categories_cache["ts"]) < CATEGORIES_CACHE_TTL:
            return _categories_cache["data"]
    
    all_cats = db.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order ASC, name ASC, id ASC", fetch=True) or []
    all_cats_dicts = [dict(c) for c in all_cats]
    cat_dict_by_api = {}
    for c in all_cats_dicts:
        api_id = str(c.get("api_category_id") or "")
        if api_id and api_id != "None": cat_dict_by_api[api_id] = c

    def build_subcats(parent_api_id, visited):
        result = []
        for c in all_cats_dicts:
            api_id = str(c.get("api_category_id") or "")
            c_parent = str(c.get("parent_id") or "0")
            if c_parent == parent_api_id and api_id and api_id not in visited and api_id != parent_api_id:
                visited.add(api_id)
                c_dict = dict(c)
                c_dict["subcategories"] = build_subcats(api_id, visited.copy())
                result.append(c_dict)
        return result

    root_cats = []
    visited_global = set()
    for c in all_cats_dicts:
        parent_id = str(c.get("parent_id") or "0")
        api_id = str(c.get("api_category_id") or "")
        if (parent_id == "0" or parent_id == "None" or parent_id == "" or parent_id not in cat_dict_by_api) and api_id not in visited_global:
            visited_global.add(api_id)
            c_dict = dict(c)
            c_dict["subcategories"] = build_subcats(api_id, visited_global.copy())
            root_cats.append(c_dict)
    
    with _categories_cache["lock"]:
        _categories_cache["data"] = root_cats
        _categories_cache["ts"] = now
    
    return root_cats

def invalidate_categories_cache():
    with _categories_cache["lock"]:
        _categories_cache["data"] = None
        _categories_cache["ts"] = 0

_subcat_ids_cache = {}

def get_all_subcategory_ids(cat_id):
    if cat_id in _subcat_ids_cache:
        return _subcat_ids_cache[cat_id]
    
    result = [cat_id]
    all_cats = db.execute("SELECT id, api_category_id, parent_id FROM categories WHERE is_active=1", fetch=True) or []

    def find_children(parent_api_id):
        children_ids = []
        for c in all_cats:
            if str(c["parent_id"] or "0") == str(parent_api_id):
                children_ids.append(c["id"])
                child_api_id = str(c["api_category_id"] or "0")
                if child_api_id: children_ids.extend(find_children(child_api_id))
        return children_ids

    cat_dict = {c["id"]: c for c in all_cats}
    cat = cat_dict.get(cat_id)
    if cat:
        api_id = str(cat["api_category_id"] or "0")
        result.extend(find_children(api_id))
    
    result = list(set(result))
    _subcat_ids_cache[cat_id] = result
    return result

_product_count_cache = {"data": {}, "ts": 0, "lock": threading.Lock()}
PRODUCT_COUNT_CACHE_TTL = 120

def get_products_count_for_category(cat_id):
    now = time.time()
    with _product_count_cache["lock"]:
        if (now - _product_count_cache["ts"]) < PRODUCT_COUNT_CACHE_TTL:
            return _product_count_cache["data"].get(cat_id, 0)
    
    all_ids = get_all_subcategory_ids(cat_id)
    if not all_ids:
        return 0
    placeholders = ','.join('?' for _ in all_ids)
    count = db.execute(f"SELECT COUNT(*) as c FROM products WHERE category_id IN ({placeholders}) AND is_active=1", all_ids, fetchone=True)
    result = count["c"] if count else 0
    
    with _product_count_cache["lock"]:
        if (now - _product_count_cache["ts"]) >= PRODUCT_COUNT_CACHE_TTL:
            _product_count_cache["data"] = {}
            _product_count_cache["ts"] = now
        _product_count_cache["data"][cat_id] = result
    
    return result

def recalculate_all_prices():
    profit = float(db.get_setting("profit_percentage", "15"))
    db.execute("UPDATE products SET sell_price=ROUND(original_price * (1 + ? / 100.0), 2) WHERE original_price > 0", (profit,))
    products = db.execute("SELECT id, qty_options FROM products WHERE qty_options IS NOT NULL AND qty_options != ''", fetch=True) or []
    for p in products:
        try:
            opts = json.loads(p["qty_options"])
            if isinstance(opts, list):
                updated = False
                for opt in opts:
                    if isinstance(opt, dict) and opt.get("base") is not None:
                        base = float(opt["base"])
                        if base > 0:
                            new_price = round(base * (1.0 + profit / 100.0), 2)
                            opt["price"] = new_price
                            updated = True
                if updated:
                    db.execute("UPDATE products SET qty_options=? WHERE id=?", (json.dumps(opts, ensure_ascii=False), p["id"]))
        except Exception as e:
            debug_print(f"Error updating options for product {p['id']}: {e}", "WARN")
    return db.execute("SELECT COUNT(*) as c FROM products WHERE original_price > 0", fetchone=True)["c"]

_ads_cache = {"data": None, "ts": 0, "lock": threading.Lock()}
ADS_CACHE_TTL = 120

def get_top_ads():
    now = time.time()
    with _ads_cache["lock"]:
        if _ads_cache["data"] is not None and (now - _ads_cache["ts"]) < ADS_CACHE_TTL:
            return _ads_cache["data"]
    
    ads_images = db.execute("SELECT * FROM ads WHERE is_active=1 AND position='top' AND ad_type='image' ORDER BY sort_order LIMIT 10", fetch=True) or []
    ads_text = db.execute("SELECT * FROM ads WHERE is_active=1 AND position='top' AND ad_type='text' ORDER BY sort_order LIMIT 5", fetch=True) or []
    result = ([dict(a) for a in ads_images], [dict(a) for a in ads_text])
    
    with _ads_cache["lock"]:
        _ads_cache["data"] = result
        _ads_cache["ts"] = now
    return result

def get_user_full_info(user_id):
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return None
    user_dict = dict(user)
    orders = db.execute("SELECT po.*, p.name as product_name FROM purchase_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.user_id=? ORDER BY po.created_at DESC LIMIT 50", (user_id,), fetch=True) or []
    user_dict["orders"] = [dict(o) for o in orders]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user_id,), fetch=True) or []
    user_dict["transactions"] = [dict(t) for t in transactions]
    topups = db.execute("SELECT * FROM wallet_topup_requests WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,), fetch=True) or []
    user_dict["topup_requests"] = [dict(t) for t in topups]
    tickets = db.execute("SELECT t.*, (SELECT COUNT(*) FROM support_messages WHERE ticket_id=t.id) as messages_count FROM support_tickets t WHERE t.user_id=? ORDER BY t.created_at DESC", (user_id,), fetch=True) or []
    user_dict["support_tickets"] = [dict(t) for t in tickets]
    favs = db.execute("SELECT p.name, p.id FROM user_favorites f JOIN products p ON f.product_id=p.id WHERE f.user_id=?", (user_id,), fetch=True) or []
    user_dict["favorites"] = [dict(f) for f in favs]
    chats = db.execute("SELECT * FROM chat_messages WHERE user_id=? ORDER BY created_at DESC LIMIT 30", (user_id,), fetch=True) or []
    user_dict["chat_messages"] = [dict(c) for c in chats]
    notifs = db.execute("SELECT * FROM notifications WHERE user_id=? OR is_broadcast=1 ORDER BY created_at DESC LIMIT 20", (user_id,), fetch=True) or []
    user_dict["notifications"] = [dict(n) for n in notifs]
    
    is_vip, vip_level = check_vip_status(user_id)
    user_dict["is_vip"] = is_vip
    user_dict["vip_level"] = vip_level
    user_dict["vip_level_name"] = get_vip_level_name(vip_level)
    user_dict["vip_badge"] = get_vip_badge(vip_level)
    
    achievements = db.execute("SELECT * FROM user_achievements WHERE user_id=? ORDER BY earned_at DESC", (user_id,), fetch=True) or []
    user_dict["achievements"] = [dict(a) for a in achievements]
    
    completed_orders, pending_orders, failed_orders, total_spent = 0, 0, 0, 0
    for o in orders:
        if o["status"] == "completed":
            completed_orders += 1
            total_spent += o["total_price"]
        elif o["status"] == "pending": pending_orders += 1
        elif o["status"] == "failed": failed_orders += 1
    approved_topups, pending_topups, total_topup_amount = 0, 0, 0
    for t in topups:
        if t["status"] == "approved":
            approved_topups += 1
            total_topup_amount += t["amount"]
        elif t["status"] == "pending": pending_topups += 1
    open_tickets = sum(1 for t in tickets if t["status"] == "open")
    stats = {
        "total_orders": len(orders), "completed_orders": completed_orders, "pending_orders": pending_orders, "failed_orders": failed_orders,
        "total_spent": total_spent, "total_topups": len(topups), "approved_topups": approved_topups, "pending_topups": pending_topups,
        "total_topup_amount": total_topup_amount, "total_tickets": len(tickets), "open_tickets": open_tickets, "loyalty_points": user_dict.get("loyalty_points", 0) or 0,
        "is_vip": is_vip, "vip_level": vip_level, "vip_level_name": get_vip_level_name(vip_level), "vip_badge": get_vip_badge(vip_level),
        "contests_won": user_dict.get("contests_won", 0) or 0, "achievements_count": len(achievements),
        "wheel_spins": user_dict.get("wheel_spins", 0) or 0,
    }
    user_dict["stats"] = stats
    return user_dict

def build_order_details_text(order, product_name, username=""):
    text = f"🚚 <b>طلب شحن جديد يحتاج موافقة</b>\n\n"
    text += f"👤 المستخدم: {username or '?'}\n📦 المنتج: {product_name or '?'}\n🔢 الكمية: {order.get('quantity', 1)}\n💵 سعر الوحدة: {format_price(order.get('unit_price', 0))}\n💰 سعر المنتج: {format_price(order.get('unit_price', 0) * order.get('quantity', 1))}\n"
    if order.get('shipping_method_id'):
        sm = db.execute("SELECT name, wallet_link, wallet_number, price, price_usd, currency_type FROM shipping_methods WHERE id=?", (order["shipping_method_id"],), fetchone=True)
        if sm:
            sm = row_to_dict(sm)
            text += f"🚚 طريقة الشحن: {sm['name']}\n"
            if sm.get('wallet_link'):
                text += f"🔗 رابط المحفظة: {sm['wallet_link']}\n"
            if sm.get('wallet_number'):
                text += f"🔢 رقم المحفظة: <code>{sm['wallet_number']}</code>\n"
    text += f"🚚 سعر الشحن: {format_price(order.get('shipping_price', 0))}\n💰 الإجمالي: {format_price(order.get('total_price', 0))}\n💸 المبلغ المدفوع: {format_price(order.get('payment_amount', 0))}\n🔢 رقم العملية: <code>{order.get('transaction_number', '-')}</code>\n"
    if order.get('player_id'): text += f"🎮 معرّف اللاعب: <code>{order['player_id']}</code>\n"
    if order.get('customer_info'):
        try:
            custom_fields = json.loads(order["customer_info"])
            if custom_fields and isinstance(custom_fields, dict):
                text += f"\n📋 <b>الحقول المخصصة:</b>\n"
                for k, v in custom_fields.items():
                    if v and str(v).strip(): text += f"  • {k}: <code>{v}</code>\n"
        except Exception: pass
    text += f"\n📋 رقم الطلب: <code>{order.get('order_id', '')}</code>\n📅 التاريخ: {str(order.get('created_at', ''))[:16]}\n"
    return text

def build_topup_details_text(topup, username=""):
    method = db.execute("SELECT * FROM wallet_topup_methods WHERE id=?", (topup.get("method_id"),), fetchone=True)
    if method is not None:
        method = row_to_dict(method)
    method_name = method["name"] if method else "غير محدد"
    account_number = method["account_number"] if method else "غير محدد"
    wallet_link = method.get("wallet_link", "") if method else ""
    instructions = method["instructions"] if method else ""
    currency_type = topup.get("currency_type", "SYP")
    original_amount = topup.get("original_amount", 0)
    final_amount = topup.get("amount", 0)
    
    text = f"📥 <b>طلب شحن محفظة جديد (تفاصيل كاملة)</b>\n\n"
    text += f"👤 المستخدم: {username or '?'}\n"
    text += f"💳 طريقة الشحن: {method_name}\n"
    if account_number and account_number != "None":
        text += f"🔢 رقم المحفظة/الحساب: <code>{account_number}</code>\n"
    if wallet_link:
        text += f"🔗 رابط المحفظة: {wallet_link}\n"
    
    if currency_type == "USD":
        text += f"💵 المبلغ المرسل (USD): <code>{original_amount} $</code>\n"
        text += f"💰 المبلغ المحوّل (ل.س): <code>{format_price(final_amount)}</code>\n"
    else:
        text += f"💰 المبلغ المطلوب: {format_price(final_amount)}\n"
        
    text += f"🔢 رقم العملية: <code>{topup.get('transaction_number', '-')}</code>\n"
    if instructions:
        text += f"📝 التعليمات: {instructions}\n"
    text += f"\n📋 رقم الطلب: <code>{topup.get('request_id', '')}</code>\n"
    text += f"📅 التاريخ: {str(topup.get('created_at', ''))[:16]}\n"
    return text

def get_related_products(product_id, category_id, limit=5):
    if not category_id: return []
    prods = db.execute("SELECT id, name, sell_price, image_url, image_path FROM products WHERE category_id=? AND is_active=1 AND id!=? ORDER BY sales_count DESC, views DESC LIMIT ?", (category_id, product_id, limit), fetch=True) or []
    return [dict(p) for p in prods]

def get_recently_viewed(user_id, limit=5):
    if not user_id: return []
    prods = db.execute("SELECT p.id, p.name, p.sell_price, p.image_url, image_path FROM recently_viewed r JOIN products p ON r.product_id=p.id WHERE r.user_id=? AND p.is_active=1 ORDER BY r.viewed_at DESC LIMIT ?", (user_id, limit), fetch=True) or []
    return [dict(p) for p in prods]

def add_recently_viewed(user_id, product_id):
    if not user_id or not product_id: return
    try:
        db.execute("INSERT OR REPLACE INTO recently_viewed (user_id, product_id, viewed_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (user_id, product_id))
    except Exception: pass

def check_force_join(user_id):
    force_enabled = db.get_setting("force_join_enabled", "1")
    if force_enabled != "1":
        return True, None
    
    channel_id = db.get_setting("force_join_group_id", FORCE_JOIN_CHANNEL_ID)
    channel_link = db.get_setting("force_join_group_link", FORCE_JOIN_CHANNEL_LINK)
    
    if not channel_id or channel_id == "0":
        return True, None
    
    try:
        member = bot.get_chat_member(channel_id, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            db.execute("UPDATE users SET force_join_checked=1 WHERE telegram_id=?", (user_id,))
            return True, None
        else:
            return False, channel_link
    except Exception as e:
        debug_print(f"Force join check error: {e}", "WARN")
        try:
            time.sleep(0.5)
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                db.execute("UPDATE users SET force_join_checked=1 WHERE telegram_id=?", (user_id,))
                return True, None
            else:
                return False, channel_link
        except Exception as e2:
            debug_print(f"Force join second check error: {e2}", "WARN")
            db.execute("UPDATE users SET force_join_checked=0 WHERE telegram_id=?", (user_id,))
            return True, None

def get_product_reviews(product_id, limit=10):
    reviews = db.execute("SELECT r.*, u.username FROM product_reviews r LEFT JOIN users u ON r.user_id=u.id WHERE r.product_id=? AND r.is_approved=1 ORDER BY r.created_at DESC LIMIT ?", (product_id, limit), fetch=True) or []
    return [dict(r) for r in reviews]

def get_product_rating(product_id):
    row = db.execute("SELECT AVG(rating) as avg, COUNT(*) as count FROM product_reviews WHERE product_id=? AND is_approved=1", (product_id,), fetchone=True)
    if row and row["count"] > 0: return {"avg": round(row["avg"], 1), "count": row["count"]}
    return {"avg": 0, "count": 0}

def export_orders_to_csv():
    orders = db.execute("""
        SELECT po.order_id, po.status, po.quantity, po.unit_price, po.total_price, po.shipping_price, po.payment_amount, po.transaction_number, 
               po.player_id, po.created_at, po.completed_at, p.name as product_name, u.username, u.telegram_id, u.phone
        FROM purchase_orders po LEFT JOIN products p ON po.product_id=p.id LEFT JOIN users u ON po.user_id=u.id ORDER BY po.created_at DESC
    """, fetch=True) or []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['رقم الطلب', 'الحالة', 'المنتج', 'الكمية', 'سعر الوحدة', 'الإجمالي', 'سعر الشحن', 'المبلغ المدفوع', 'رقم العملية', 'معرف اللاعب', 'المستخدم', 'تيليجرام ID', 'الهاتف', 'تاريخ الإنشاء', 'تاريخ الإكمال'])
    for o in orders:
        writer.writerow([o['order_id'], o['status'], o['product_name'] or '', o['quantity'], o['unit_price'], o['total_price'], o['shipping_price'] or 0, o['payment_amount'] or 0, o['transaction_number'] or '', o['player_id'] or '', o['username'] or '', o['telegram_id'] or '', o['phone'] or '', o['created_at'] or '', o['completed_at'] or ''])
    output.seek(0)
    return output.getvalue()

def check_low_stock_products():
    threshold = int(db.get_setting("stock_alert_threshold", "5"))
    low_stock = db.execute("SELECT id, name, stock_quantity FROM products WHERE is_active=1 AND stock_quantity >= 0 AND stock_quantity < ?", (threshold,), fetch=True) or []
    return [dict(p) for p in low_stock]

def get_featured_products(limit=10):
    prods = db.execute("SELECT * FROM products WHERE is_active=1 AND is_featured=1 ORDER BY sales_count DESC LIMIT ?", (limit,), fetch=True) or []
    return [dict(p) for p in prods]

def get_best_sellers(limit=10):
    prods = db.execute("SELECT * FROM products WHERE is_active=1 AND sales_count > 0 ORDER BY sales_count DESC LIMIT ?", (limit,), fetch=True) or []
    return [dict(p) for p in prods]

def get_new_arrivals(limit=10):
    prods = db.execute("SELECT * FROM products WHERE is_active=1 ORDER BY created_at DESC LIMIT ?", (limit,), fetch=True) or []
    return [dict(p) for p in prods]

def get_cart_count(user_id):
    if not user_id: return 0
    row = db.execute("SELECT COUNT(*) as c FROM cart_items WHERE user_id=?", (user_id,), fetchone=True)
    return row["c"] if row else 0

def get_cart_items(user_id):
    if not user_id: return []
    items = db.execute("SELECT c.*, p.name, p.sell_price, p.image_url, p.image_path, p.stock_quantity FROM cart_items c JOIN products p ON c.product_id=p.id WHERE c.user_id=? AND p.is_active=1 ORDER BY c.created_at DESC", (user_id,), fetch=True) or []
    return [dict(i) for i in items]

def add_to_cart(user_id, product_id, quantity=1, selected_option="", custom_fields=""):
    if not user_id: return False
    existing = db.execute("SELECT id, quantity FROM cart_items WHERE user_id=? AND product_id=? AND selected_option=?", (user_id, product_id, selected_option), fetchone=True)
    if existing:
        db.execute("UPDATE cart_items SET quantity=quantity+? WHERE id=?", (quantity, existing["id"]))
    else:
        db.execute("INSERT INTO cart_items (user_id, product_id, quantity, selected_option, custom_fields) VALUES (?, ?, ?, ?, ?)", (user_id, product_id, quantity, selected_option, custom_fields))
    return True

def remove_from_cart(cart_id, user_id):
    db.execute("DELETE FROM cart_items WHERE id=? AND user_id=?", (cart_id, user_id))

def clear_cart(user_id):
    db.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))

def get_comparison_items(user_id):
    if not user_id: return []
    items = db.execute("SELECT p.* FROM product_comparisons pc JOIN products p ON pc.product_id=p.id WHERE pc.user_id=? AND p.is_active=1", (user_id,), fetch=True) or []
    return [dict(i) for i in items]

def toggle_comparison(user_id, product_id):
    if not user_id: return False
    existing = db.execute("SELECT id FROM product_comparisons WHERE user_id=? AND product_id=?", (user_id, product_id), fetchone=True)
    if existing:
        db.execute("DELETE FROM product_comparisons WHERE id=?", (existing["id"],))
        return False
    else:
        count = db.execute("SELECT COUNT(*) as c FROM product_comparisons WHERE user_id=?", (user_id,), fetchone=True)["c"]
        if count >= 4: return None
        db.execute("INSERT INTO product_comparisons (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        return True

def get_faqs():
    faqs = db.execute("SELECT * FROM faqs WHERE is_active=1 ORDER BY sort_order ASC", fetch=True) or []
    return [dict(f) for f in faqs]

def get_blog_posts(limit=10):
    posts = db.execute("SELECT * FROM blog_posts WHERE is_published=1 ORDER BY created_at DESC LIMIT ?", (limit,), fetch=True) or []
    return [dict(p) for p in posts]

def get_blog_post(slug):
    post = db.execute("SELECT * FROM blog_posts WHERE slug=? AND is_published=1", (slug,), fetchone=True)
    if post:
        db.execute("UPDATE blog_posts SET views=views+1 WHERE id=?", (post["id"],))
        return dict(post)
    return None

_stats_cache = {"data": None, "ts": 0, "lock": threading.Lock()}
STATS_CACHE_TTL = 60

def get_site_stats():
    now = time.time()
    with _stats_cache["lock"]:
        if _stats_cache["data"] is not None and (now - _stats_cache["ts"]) < STATS_CACHE_TTL:
            return _stats_cache["data"]
    
    stats = {
        "products": db.execute("SELECT COUNT(*) as c FROM products WHERE is_active=1", fetchone=True)["c"],
        "categories": db.execute("SELECT COUNT(*) as c FROM categories", fetchone=True)["c"],
        "orders": db.execute("SELECT COUNT(*) as c FROM purchase_orders", fetchone=True)["c"],
        "completed": db.execute("SELECT COUNT(*) as c FROM purchase_orders WHERE status='completed'", fetchone=True)["c"],
        "pending_topups": db.execute("SELECT COUNT(*) as c FROM wallet_topup_requests WHERE status='pending'", fetchone=True)["c"],
        "pending_shipping": db.execute("SELECT COUNT(*) as c FROM purchase_orders WHERE status='pending' AND shipping_method_id IS NOT NULL", fetchone=True)["c"],
        "gifts": db.execute("SELECT COUNT(*) as c FROM gift_codes WHERE is_active=1 AND is_sold=0", fetchone=True)["c"],
        "total_revenue": db.execute("SELECT COALESCE(SUM(total_price), 0) as s FROM purchase_orders WHERE status='completed'", fetchone=True)["s"],
        "total_topup": db.execute("SELECT COALESCE(SUM(amount), 0) as s FROM wallet_topup_requests WHERE status='approved'", fetchone=True)["s"],
        "active_reviews": db.execute("SELECT COUNT(*) as c FROM product_reviews WHERE is_approved=1", fetchone=True)["c"],
        "pending_reviews": db.execute("SELECT COUNT(*) as c FROM product_reviews WHERE is_approved=0", fetchone=True)["c"],
        "discount_codes": db.execute("SELECT COUNT(*) as c FROM discount_codes WHERE is_active=1", fetchone=True)["c"],
        "banners": db.execute("SELECT COUNT(*) as c FROM banners WHERE is_active=1", fetchone=True)["c"],
        "blog_posts": db.execute("SELECT COUNT(*) as c FROM blog_posts WHERE is_published=1", fetchone=True)["c"],
        "faqs": db.execute("SELECT COUNT(*) as c FROM faqs WHERE is_active=1", fetchone=True)["c"],
        "support_tickets_open": db.execute("SELECT COUNT(*) as c FROM support_tickets WHERE status='open'", fetchone=True)["c"],
        "unread_chats": db.execute("SELECT COUNT(DISTINCT user_id) as c FROM chat_messages WHERE is_from_admin=0 AND is_read=0", fetchone=True)["c"],
        "active_contests": db.execute("SELECT COUNT(*) as c FROM contests WHERE is_active=1", fetchone=True)["c"],
        "vip_users": db.execute("SELECT COUNT(*) as c FROM users WHERE is_vip=1", fetchone=True)["c"],
        "active_offers": db.execute("SELECT COUNT(*) as c FROM product_offers WHERE is_active=1", fetchone=True)["c"],
        "banned_users": db.execute("SELECT COUNT(*) as c FROM users WHERE is_banned=1", fetchone=True)["c"],
        "wheel_gifts": db.execute("SELECT COUNT(*) as c FROM wheel_gifts WHERE is_active=1", fetchone=True)["c"],
        "total_wheel_spins": db.execute("SELECT COUNT(*) as c FROM wheel_spins", fetchone=True)["c"],
    }
    
    with _stats_cache["lock"]:
        _stats_cache["data"] = stats
        _stats_cache["ts"] = now
    return stats

def get_active_contests():
    contests = db.execute("SELECT * FROM contests WHERE is_active=1 AND (end_date IS NULL OR end_date > datetime('now')) ORDER BY created_at DESC", fetch=True) or []
    return [dict(c) for c in contests]

def join_contest(contest_id, user_id):
    existing = db.execute("SELECT id FROM contest_participants WHERE contest_id=? AND user_id=?", (contest_id, user_id), fetchone=True)
    if existing: return False, "أنت مشترك في هذه المسابقة بالفعل"
    db.execute("INSERT INTO contest_participants (contest_id, user_id) VALUES (?, ?)", (contest_id, user_id))
    return True, "تم الانضمام للمسابقة بنجاح!"

def get_user_achievements(user_id):
    achievements = db.execute("SELECT * FROM user_achievements WHERE user_id=? ORDER BY earned_at DESC", (user_id,), fetch=True) or []
    return [dict(a) for a in achievements]

def check_and_award_achievements(user_id):
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return []
    new_achievements = []
    total_orders = user["total_orders"] or 0
    total_spent = user["total_spent"] or 0
    loyalty_points = user["loyalty_points"] or 0
    achievement_checks = [
        ("first_order", "أول طلب", "✅", "أكملت أول طلب لك", total_orders >= 1),
        ("ten_orders", "متسوق محترف", "🛒", "أكملت 10 طلبات", total_orders >= 10),
        ("fifty_orders", "عميل مميز", "👑", "أكملت 50 طلب", total_orders >= 50),
        ("big_spender", "مسؤول كبير", "💎", "أنفقت أكثر من 100000", total_spent >= 100000),
        ("loyalty_100", "نقاط الولاء", "⭐", "جمعت 100 نقطة ولاء", loyalty_points >= 100),
        ("loyalty_1000", "ولاء ذهبي", "🏆", "جمعت 1000 نقطة ولاء", loyalty_points >= 1000),
    ]
    for ach_type, name, icon, desc, condition in achievement_checks:
        if condition:
            existing = db.execute("SELECT id FROM user_achievements WHERE user_id=? AND achievement_type=?", (user_id, ach_type), fetchone=True)
            if not existing:
                db.execute("INSERT OR IGNORE INTO user_achievements (user_id, achievement_type, achievement_name, description, icon) VALUES (?, ?, ?, ?, ?)", (user_id, ach_type, name, desc, icon))
                new_achievements.append({"type": ach_type, "name": name, "icon": icon, "description": desc})
    return new_achievements

def get_active_product_offer(product_id):
    offer = db.execute("SELECT * FROM product_offers WHERE product_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 1", (product_id,), fetchone=True)
    return dict(offer) if offer else None

def get_all_active_offers():
    offers = db.execute("""
        SELECT po.*, p.name as product_name, p.sell_price as current_price, p.image_path, p.image_url
        FROM product_offers po 
        JOIN products p ON po.product_id=p.id 
        WHERE po.is_active=1 AND p.is_active=1
        ORDER BY po.created_at DESC
    """, fetch=True) or []
    return [dict(o) for o in offers]

def create_product_offer(product_id, title, description, discount_percentage, created_by=None):
    product = db.execute("SELECT sell_price FROM products WHERE id=?", (product_id,), fetchone=True)
    if not product: 
        return False, "المنتج غير موجود"
    
    original_price = float(product["sell_price"] or 0)
    if original_price <= 0:
        return False, "سعر المنتج غير صحيح"
    
    discount_percentage = float(discount_percentage)
    if discount_percentage <= 0 or discount_percentage > 99:
        return False, "نسبة الخصم غير صحيحة (يجب أن تكون بين 1 و 99)"
    
    offer_price = round(original_price * (1 - discount_percentage / 100), 2)
    
    db.execute("UPDATE product_offers SET is_active=0 WHERE product_id=?", (product_id,))
    
    db.execute("""INSERT INTO product_offers 
                  (product_id, offer_title, offer_description, discount_percentage, original_price, offer_price, is_active, start_date, created_by) 
                  VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
               (product_id, title, description, discount_percentage, original_price, offer_price, 
                datetime.now().isoformat(), created_by))
    
    db.execute("UPDATE products SET discount_percentage=? WHERE id=?", (discount_percentage, product_id))
    
    return True, f"تم إنشاء العرض بنجاح! السعر الجديد: {format_price(offer_price)}"

def deactivate_offer(offer_id):
    offer = db.execute("SELECT product_id FROM product_offers WHERE id=?", (offer_id,), fetchone=True)
    if offer:
        db.execute("UPDATE product_offers SET is_active=0 WHERE id=?", (offer_id,))
        db.execute("UPDATE products SET discount_percentage=0 WHERE id=?", (offer["product_id"]))
    return True

def get_wheel_gifts():
    gifts = db.execute("SELECT * FROM wheel_gifts WHERE is_active=1 ORDER BY sort_order ASC", fetch=True) or []
    return [dict(g) for g in gifts]

def add_wheel_gift(name, amount, color, icon, created_by=None):
    db.execute("INSERT INTO wheel_gifts (name, amount, color, icon, probability, is_active, sort_order, created_by) VALUES (?, ?, ?, ?, 0, 1, 0, ?)",
               (name, amount, color, icon, created_by))

def delete_wheel_gift(gift_id):
    db.execute("DELETE FROM wheel_gifts WHERE id=?", (gift_id,))

def toggle_wheel_gift_status(gift_id):
    g = db.execute("SELECT is_active FROM wheel_gifts WHERE id=?", (gift_id,), fetchone=True)
    if g:
        new_status = 0 if g["is_active"] == 1 else 1
        db.execute("UPDATE wheel_gifts SET is_active=? WHERE id=?", (new_status, gift_id))
        return new_status
    return None

def spin_wheel(user_id):
    user = db.execute("SELECT wheel_spins FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return None, "المستخدم غير موجود"
    if user["wheel_spins"] <= 0: return None, "لا توجد دورات متاحة"
    
    db.execute("UPDATE users SET wheel_spins = wheel_spins - 1, total_wheel_spins = total_wheel_spins + 1 WHERE id=?", (user_id,))
    
    gifts = get_wheel_gifts()
    if not gifts:
        db.execute("UPDATE users SET wheel_spins = wheel_spins + 1 WHERE id=?", (user_id,))
        return None, "لا توجد هدايا في العجلة"
    
    total_prob = sum(float(g.get("probability", 0) or 0) for g in gifts)
    selected = None
    
    if total_prob > 0:
        r = random.uniform(0, total_prob)
        upto = 0
        for g in gifts:
            if upto + float(g.get("probability", 0) or 0) >= r:
                selected = g
                break
            upto += float(g.get("probability", 0) or 0)
    
    if not selected:
        selected = random.choice(gifts)
        
    selected = dict(selected)
    
    amount_won = float(selected.get("amount", 0) or 0)
    
    if amount_won > 0:
        db.execute("UPDATE users SET balance = balance + ?, total_wheel_winnings = total_wheel_winnings + ? WHERE id=?", 
                   (amount_won, amount_won, user_id))
        add_transaction(user_id, amount_won, "wheel_win", f"ربح عجلة الحظ: {selected['name']}")
        db.execute("INSERT INTO wheel_spins (user_id, gift_id, result, amount_won) VALUES (?, ?, 'win', ?)",
                   (user_id, selected["id"], amount_won))
        return selected, f"🎉 مبروك! لقد فزت بـ {selected['name']}!"
    else:
        db.execute("INSERT INTO wheel_spins (user_id, gift_id, result, amount_won) VALUES (?, ?, 'lose', 0)",
                   (user_id, selected["id"], 0))
        return selected, "حظ أوفر! لم تفز هذه المرة. حاول مرة أخرى!"

def check_and_award_spins(user_id, purchase_amount):
    thresholds = db.execute("SELECT * FROM spin_reward_thresholds WHERE is_active=1 ORDER BY threshold_amount ASC", fetch=True) or []
    if not thresholds: return 0
    
    user = db.execute("SELECT total_spent FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return 0
    
    total_spent = user["total_spent"] or 0
    prev_spent = total_spent - purchase_amount
    
    spins_awarded = 0
    for t in thresholds:
        threshold = t["threshold_amount"]
        if prev_spent < threshold <= total_spent:
            spins_awarded += t["spins_awarded"]
    
    if spins_awarded > 0:
        db.execute("UPDATE users SET wheel_spins = wheel_spins + ? WHERE id=?", (spins_awarded, user_id))
        send_user_notification(user_id, "🎡 دورة مجانية!", f"مبروك! لقد حصلت على {spins_awarded} دورة في عجلة الحظ لإنفاقك مبلغ {format_price(purchase_amount)}.")
    
    return spins_awarded

def get_user_wheel_spins(user_id):
    user = db.execute("SELECT wheel_spins, total_wheel_spins, total_wheel_winnings FROM users WHERE id=?", (user_id,), fetchone=True)
    if not user: return 0, 0, 0
    return user["wheel_spins"] or 0, user["total_wheel_spins"] or 0, user["total_wheel_winnings"] or 0

def get_spin_thresholds():
    return [dict(t) for t in (db.execute("SELECT * FROM spin_reward_thresholds WHERE is_active=1 ORDER BY threshold_amount ASC", fetch=True) or [])]

def add_spin_threshold(amount, spins):
    db.execute("INSERT INTO spin_reward_thresholds (threshold_amount, spins_awarded, is_active) VALUES (?, ?, 1)", (amount, spins))

def delete_spin_threshold(threshold_id):
    db.execute("DELETE FROM spin_reward_thresholds WHERE id=?", (threshold_id,))

def process_referral_reward(referred_user_id, topup_request_id, topup_amount):
    user = db.execute("SELECT referred_by FROM users WHERE id=?", (referred_user_id,), fetchone=True)
    if not user or not user["referred_by"]: return
    
    existing = db.execute("SELECT id FROM referral_rewards WHERE referred_id=?", (referred_user_id,), fetchone=True)
    if existing: return
    
    referrer_id = user["referred_by"]
    bonus = float(db.get_setting("referral_bonus", "5000"))
    
    if bonus > 0:
        db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (bonus, referrer_id))
        add_transaction(referrer_id, bonus, "referral_bonus", f"مكافأة إحالة مستخدم جديد قام بشحن محفظته")
        db.execute("INSERT INTO referral_rewards (referrer_id, referred_id, topup_request_id, reward_amount, status) VALUES (?, ?, ?, ?, 'awarded')",
                   (referrer_id, referred_user_id, topup_request_id, bonus))
        send_user_notification(referrer_id, "🎁 مكافأة إحالة", f"مبروك! لقد ربحت {format_price(bonus)} لأن صديقك قام بشحن محفظته.")

_push_cleanup_thread_started = False

def start_push_token_cleanup_scheduler():
    global _push_cleanup_thread_started
    if _push_cleanup_thread_started:
        return
    _push_cleanup_thread_started = True
    
    def _cleanup_loop():
        while True:
            try:
                time.sleep(86400)
                if hasattr(app, '_cleanup_old_push_tokens'):
                    app._cleanup_old_push_tokens()
                    debug_print("[PUSH] Scheduled cleanup completed", "INFO")
            except Exception as e:
                debug_print(f"[PUSH] Cleanup scheduler error: {e}", "WARN")
    
    threading.Thread(target=_cleanup_loop, daemon=True).start()
    debug_print("[PUSH] Token cleanup scheduler started", "INFO")

# ==============================================================================
# CSS و HTML
# ==============================================================================

SITE_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Cairo:wght@400;600;700;800;900&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}

:root{
    --bg:#050614; --bg2:#0a0e26; --bg3:#0f1530; --card:rgba(15,20,45,0.65); --card-h:rgba(25,35,70,0.85);
    --accent:#7c3aed; --accent-l:#a78bfa; --accent-2:#06b6d4; --accent-2-l:#67e8f9; --accent-3:#ec4899;
    --accent-g:rgba(124,58,237,0.35); --ok:#10b981; --err:#ef4444; --warn:#f59e0b; --info:#3b82f6;
    --t1:#f8fafc; --t2:#cbd5e1; --t3:#64748b; --brd:rgba(255,255,255,0.08); --glass:rgba(5,8,25,0.75); --gbrd:rgba(255,255,255,0.12);
    --r:20px; --rs:12px; --sh:0 10px 40px rgba(0,0,0,0.5); --tr:all 0.4s cubic-bezier(0.4,0,0.2,1);
    --grad1:linear-gradient(135deg,#7c3aed 0%,#06b6d4 100%); --grad2:linear-gradient(135deg,#ec4899 0%,#7c3aed 100%);
    --grad3:linear-gradient(135deg,#10b981 0%,#06b6d4 100%); --grad4:linear-gradient(135deg,#f59e0b 0%,#ec4899 100%);
    --wa:#25d366; --vip-grad:linear-gradient(135deg,#f59e0b,#ec4899,#7c3aed);
}

body.light-mode{
    --bg:#f8fafc; --bg2:#ffffff; --bg3:#f1f5f9; --card:rgba(255,255,255,0.85); --card-h:rgba(248,250,252,0.95);
    --t1:#0f172a; --t2:#334155; --t3:#64748b; --glass:rgba(255,255,255,0.8); --gbrd:rgba(0,0,0,0.1); --brd:rgba(0,0,0,0.08); --accent-g:rgba(124,58,237,0.15)
}

html{scroll-behavior:smooth;max-width:100%;overflow-x:hidden}
body{font-family:'Tajawal','Cairo',sans-serif;background:var(--bg);color:var(--t1);direction:rtl;min-height:100vh;overflow-x:hidden;line-height:1.5;font-size:14px;padding-bottom:80px;transition:background 0.4s ease,color 0.4s ease;max-width:100%;will-change:scroll-position}
body.has-bg{background-attachment:fixed !important;background-position:center center !important;background-repeat:no-repeat !important;background-size:cover !important;position:relative}
body.has-bg::before{content:'';position:fixed;inset:0;background:rgba(5,6,20,0.88) !important;z-index:-2 !important}

body::before{content:'';position:fixed;inset:0;background:radial-gradient(circle at 15% 25%,rgba(124,58,237,0.15) 0%,transparent 45%),radial-gradient(circle at 85% 15%,rgba(6,182,212,0.12) 0%,transparent 45%);z-index:-2;will-change:transform;opacity:0.8}
body::after{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(124,58,237,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(124,58,237,0.03) 1px,transparent 1px);background-size:50px 50px;z-index:-1;mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);-webkit-mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);pointer-events:none}

@keyframes bgF{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(40px,-40px) scale(1.05)}66%{transform:translate(-30px,30px) scale(0.95)}}
@keyframes fiu{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes fi{from{opacity:0}to{opacity:1}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
@keyframes glow{0%,100%{box-shadow:0 0 30px var(--accent-g)}50%{box-shadow:0 0 60px var(--accent-g),0 0 90px var(--accent-g)}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes scaleIn{from{transform:scale(0.85);opacity:0}to{transform:scale(1);opacity:1}}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes float{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-15px) rotate(3deg)}}
@keyframes gradientShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes barFlow{0%{transform:translateX(-100%);opacity:0}50%{opacity:1}100%{transform:translateX(100%);opacity:0}}
@keyframes imgFadeIn{from{opacity:0;filter:blur(8px);transform:scale(1.05)}to{opacity:1;filter:blur(0);transform:scale(1)}}
@keyframes marquee{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}
@keyframes chatBubbleIn{from{transform:scale(0.8);opacity:0}to{transform:scale(1);opacity:1}}
@keyframes textPop{0%{transform:scale(0.8);opacity:0}50%{transform:scale(1.1)}100%{transform:scale(1);opacity:1}}
@keyframes slideFade{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}
@keyframes iconBounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes iconPulse{0%,100%{transform:scale(1);filter:brightness(1)}50%{transform:scale(1.1);filter:brightness(1.3)}}
@keyframes iconSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
@keyframes ripple{to{transform:scale(4);opacity:0}}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
@keyframes confettiFall{0%{transform:translateY(-100vh) rotate(0deg);opacity:1}100%{transform:translateY(100vh) rotate(720deg);opacity:0}}
@keyframes neonGlow{0%,100%{text-shadow:0 0 10px var(--accent),0 0 20px var(--accent),0 0 30px var(--accent)}50%{text-shadow:0 0 5px var(--accent),0 0 10px var(--accent),0 0 15px var(--accent)}}
@keyframes slideUp{from{transform:translateY(100%);opacity:0}to{transform:translateY(0);opacity:1}}
@keyframes slideDown{from{transform:translateY(-100%);opacity:0}to{transform:translateY(0);opacity:1}}
@keyframes zoomIn{from{transform:scale(0.3);opacity:0}to{transform:scale(1);opacity:1}}
@keyframes progressFill{from{width:0%}to{width:100%}}
@keyframes shine{0%{left:-100%}100%{left:100%}}
@keyframes textGradient{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes glowPulse{0%,100%{box-shadow:0 0 5px var(--accent-g)}50%{box-shadow:0 0 20px var(--accent-g),0 0 30px var(--accent-g)}}
@keyframes notificationPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.7)}50%{box-shadow:0 0 0 10px rgba(239,68,68,0)}}
@keyframes listFadeIn{from{opacity:0;transform:translateY(15px) scale(0.98)}to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes loadingBarTop{0%{left:-30%;width:30%}50%{width:30%}100%{left:100%;width:30%}}
@keyframes heartbeat{0%,100%{transform:scale(1)}25%{transform:scale(1.1)}50%{transform:scale(1)}75%{transform:scale(1.05)}}
@keyframes vipGlow{0%,100%{box-shadow:0 0 20px rgba(245,158,11,0.4)}50%{box-shadow:0 0 40px rgba(245,158,11,0.6),0 0 60px rgba(236,72,153,0.4)}}
@keyframes circleRotate{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
@keyframes countUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes emojiDance{0%,100%{transform:translateY(0) rotate(0deg)}25%{transform:translateY(-8px) rotate(-15deg)}50%{transform:translateY(0) rotate(0deg)}75%{transform:translateY(-8px) rotate(15deg)}}
@keyframes popupSlideIn{from{transform:translateX(450px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes popupSlideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(450px);opacity:0}}
@keyframes bannedPulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.05);opacity:0.8}}
@keyframes wheelSpin{from{transform:rotate(0deg)}to{transform:rotate(1440deg)}}
@keyframes wheelGlow{0%,100%{box-shadow:0 0 30px var(--accent-g)}50%{box-shadow:0 0 60px var(--accent-g),0 0 90px var(--accent-g)}}
@keyframes maintLogoPulse{0%,100%{transform:scale(1) rotate(0deg);box-shadow:0 0 50px rgba(124,58,237,0.6),0 0 100px rgba(124,58,237,0.3)}25%{transform:scale(1.1) rotate(-5deg);box-shadow:0 0 70px rgba(6,182,212,0.8),0 0 140px rgba(6,182,212,0.4)}50%{transform:scale(0.95) rotate(5deg);box-shadow:0 0 90px rgba(236,72,153,0.7),0 0 180px rgba(236,72,153,0.4)}75%{transform:scale(1.05) rotate(-3deg);box-shadow:0 0 60px rgba(124,58,237,0.9),0 0 120px rgba(124,58,237,0.5)}}
@keyframes maintRingExpand{0%{transform:scale(1);opacity:1}100%{transform:scale(1.5);opacity:0}}

.loading-bar-top{position:fixed;top:0;left:0;height:3px;background:var(--grad1);z-index:9999;animation:loadingBarTop 1.5s ease-in-out infinite;box-shadow:0 0 10px var(--accent)}

.loader-screen{position:fixed;inset:0;background:radial-gradient(ellipse at center,#0a0e26 0%,#050614 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:99999;transition:opacity .5s;overflow:hidden}
.loader-screen.hidden{opacity:0;pointer-events:none}

.loader-rocket-container{position:relative;width:200px;height:200px;display:flex;align-items:center;justify-content:center;perspective:1000px;transform-style:preserve-3d;animation:float 3s ease-in-out infinite}
.loader-ring{position:absolute;border-radius:50%;border:3px solid transparent;transform-style:preserve-3d;pointer-events:none}
.loader-ring-1{width:200px;height:200px;border-top-color:#7c3aed;border-right-color:#06b6d4;border-bottom-color:rgba(124,58,237,0.15);border-left-color:rgba(6,182,212,0.15);animation:spin 2s linear infinite;box-shadow:0 0 30px rgba(124,58,237,0.4)}
.loader-ring-2{width:160px;height:160px;border-top-color:#ec4899;border-left-color:#a78bfa;border-bottom-color:rgba(236,72,153,0.15);border-right-color:rgba(167,139,250,0.15);animation:spin 1.5s linear infinite reverse;box-shadow:0 0 30px rgba(236,72,153,0.4)}
.loader-ring-3{width:120px;height:120px;border-top-color:#10b981;border-left-color:#f59e0b;border-bottom-color:rgba(16,185,129,0.15);border-right-color:rgba(245,158,11,0.15);animation:spin 1s linear infinite;box-shadow:0 0 30px rgba(16,185,129,0.4)}
.loader-rocket{font-size:3rem;display:inline-block;filter:drop-shadow(0 0 20px rgba(124,58,237,0.9));line-height:1;animation:bounce 2s ease-in-out infinite}
.loader-text-3d{margin-top:35px;font-size:2rem;font-weight:900;color:#fff;text-shadow:2px 2px 4px rgba(0,0,0,0.5);letter-spacing:1px;animation:neonGlow 2s ease-in-out infinite}
.loader-text{margin-top:14px;font-size:.9rem;font-weight:800;color:var(--t2);animation:pulse 1.5s ease-in-out infinite;letter-spacing:3px}
.loader-progress-bar{margin-top:20px;width:200px;height:4px;background:var(--bg2);border-radius:2px;overflow:hidden;position:relative}
.loader-progress-bar::after{content:'';position:absolute;inset:0;background:var(--grad1);animation:progressFill 3s ease-in-out infinite}

.container{max-width:1280px;margin:0 auto;padding:0 12px;width:100%}

.header{background:var(--glass);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border-bottom:1px solid var(--gbrd);position:sticky;top:0;z-index:1000;animation:fi .5s ease;overflow:visible}
.header::after{content:'';position:absolute;bottom:0;left:0;width:100%;height:2px;background:var(--grad1);background-size:200% 100%;animation:barFlow 3s linear infinite}

.hdr{max-width:1280px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;position:relative;z-index:2}
.header-left{display:flex;align-items:center;gap:10px;cursor:pointer;text-decoration:none;min-width:0}
.header-logo-circle{width:48px;height:48px;border-radius:50%;background:var(--grad1);display:flex;align-items:center;justify-content:center;overflow:hidden;box-shadow:0 4px 20px var(--accent-g);flex-shrink:0;position:relative;border:2px solid rgba(255,255,255,0.15);transition:transform 0.4s}
.header-left:hover .header-logo-circle{transform:scale(1.1) rotate(10deg)}
.header-logo-circle img{width:100%;height:100%;object-fit:cover;position:relative;z-index:1}
.header-logo-circle .logo-emoji{font-size:1.4rem;z-index:1;position:relative}
.header-store-name{font-size:1.3rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:-0.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;animation:textGradient 3s ease infinite}

.header-right{display:flex;align-items:center;gap:8px;flex-wrap:nowrap}
.header-add-btn{width:42px;height:42px;border-radius:50%;background:var(--grad1);border:none;color:#fff;font-size:1.5rem;font-weight:300;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:var(--tr);box-shadow:0 4px 15px var(--accent-g);flex-shrink:0;line-height:1;position:relative;z-index:10}
.header-add-btn:hover{transform:scale(1.1) rotate(180deg);box-shadow:0 6px 25px var(--accent-g)}
.header-add-btn:active{transform:scale(0.9)}

.header-currency-btn{padding:6px 10px;border-radius:30px;background:var(--card-h);border:1px solid var(--accent);color:var(--accent-l);font-weight:800;font-size:.72rem;cursor:pointer;text-decoration:none;transition:var(--tr);flex-shrink:0;display:inline-flex;align-items:center;gap:4px;box-shadow:0 2px 10px var(--accent-g)}
.header-currency-btn:hover{background:var(--accent);color:#fff;transform:scale(1.05)}

.header-balance-box{background:linear-gradient(135deg,rgba(16,185,129,0.2),rgba(6,182,212,0.14));border:1px solid rgba(16,185,129,0.4);color:var(--ok);padding:8px 16px;border-radius:30px;font-size:.85rem;font-weight:800;display:inline-flex;align-items:center;gap:5px;white-space:nowrap;flex-shrink:0;box-shadow:0 4px 15px rgba(16,185,129,0.1);transition:var(--tr);cursor:pointer;position:relative;z-index:10}
.header-balance-box:hover{transform:translateY(-2px);box-shadow:0 6px 25px rgba(16,185,129,0.3)}

.header-cart-btn,.header-notif-btn,.header-menu-btn{position:relative;background:var(--card-h);border:1px solid var(--brd);color:var(--t2);width:42px;height:42px;border-radius:50%;cursor:pointer;font-size:1.1rem;display:flex;align-items:center;justify-content:center;transition:var(--tr);flex-shrink:0;z-index:10}
.header-cart-btn:hover,.header-notif-btn:hover{background:var(--accent);color:#fff;transform:scale(1.05)}
.header-menu-btn:hover{background:var(--accent);border-color:var(--accent);color:#fff}
.header-cart-btn:active,.header-notif-btn:active,.header-menu-btn:active{transform:scale(0.9)}

.header-cart-badge,.header-notif-badge{position:absolute;top:-3px;left:-3px;background:var(--err);color:#fff;width:18px;height:18px;border-radius:50%;font-size:.6rem;font-weight:700;display:flex;align-items:center;justify-content:center;animation:notificationPulse 1s ease-in-out infinite;border:2px solid var(--bg)}
.hamburger{display:flex;flex-direction:column;justify-content:space-between;width:20px;height:14px;z-index:1;pointer-events:none}
.hamburger span{display:block;width:100%;height:2px;background:var(--t1);border-radius:2px;transition:var(--tr)}
.hamburger.active span:nth-child(1){transform:translateY(6px) rotate(45deg)}
.hamburger.active span:nth-child(2){opacity:0}
.hamburger.active span:nth-child(3){transform:translateY(-6px) rotate(-45deg)}

.header-search-row{max-width:1280px;margin:0 auto;padding:0 16px 10px}
.header-search-wrap{position:relative;flex:1}
.header-search-wrap input{width:100%;padding:12px 44px 12px 16px;background:var(--bg2);border:2px solid var(--brd);border-radius:30px;color:var(--t1);font-family:'Tajawal',sans-serif;font-size:.85rem;outline:none;transition:var(--tr)}
.header-search-wrap input:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-g)}
.header-search-wrap .search-icon{position:absolute;left:16px;top:50%;transform:translateY(-50%);width:18px;height:18px;color:var(--t3);opacity:0.6;pointer-events:none;display:flex;align-items:center;justify-content:center}

.header-login-btn{padding:8px 20px;font-size:.8rem;font-weight:800;background:var(--grad1);color:#fff;text-decoration:none;border-radius:30px;transition:var(--tr);box-shadow:0 4px 15px var(--accent-g);flex-shrink:0;animation:glowPulse 2s ease-in-out infinite;position:relative;z-index:10;display:inline-flex;align-items:center;gap:5px}
.header-login-btn:hover{transform:translateY(-2px);box-shadow:0 6px 25px var(--accent-g)}

@media(max-width:600px){
    .header-store-name{font-size:.85rem;max-width:70px}
    .header-logo-circle{width:34px;height:34px}
    .header-logo-circle .logo-emoji{font-size:1rem}
    .header-add-btn{width:32px;height:32px;font-size:1rem}
    .header-balance-box{padding:4px 10px;font-size:.68rem}
    .header-currency-btn{padding:4px 8px;font-size:.65rem}
    .header-cart-btn,.header-notif-btn,.header-menu-btn{width:32px;height:32px;font-size:.9rem}
    .header-cart-badge,.header-notif-badge{width:14px;height:14px;font-size:.5rem;top:-2px;left:-2px}
    .header-search-row{padding:0 10px 8px}
    .header-search-wrap input{padding:9px 36px 9px 12px;font-size:.75rem}
    .header-search-wrap .search-icon{left:10px;width:16px;height:16px}
    .header-login-btn{padding:5px 12px;font-size:.68rem}
}

.promo-bar{background:var(--grad1);background-size:200% 200%;animation:gradientShift 5s ease infinite;color:#fff;padding:8px 14px;text-align:center;font-weight:800;overflow:hidden;white-space:nowrap;box-shadow:0 4px 15px var(--accent-g);cursor:pointer;text-decoration:none;display:block}
.promo-bar:hover{opacity:0.9}
.promo-bar span{display:inline-block;animation:marquee 18s linear infinite;padding-right:100%}

.top-ads-container{max-width:1280px;margin:10px auto;padding:0 12px}
.top-ads-slideshow{position:relative;width:100%;height:220px;border-radius:16px;overflow:hidden;margin-bottom:8px;background:var(--bg2);box-shadow:0 4px 20px rgba(0,0,0,0.3)}
.top-ads-slideshow .slide{position:absolute;inset:0;opacity:0;transition:opacity 1s ease-in-out;display:flex;align-items:center;justify-content:center}
.top-ads-slideshow .slide.active{opacity:1}
.top-ads-slideshow .slide img{width:100%;height:100%;object-fit:cover}
.top-ads-slideshow .slide-indicators{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);display:flex;gap:6px;z-index:5}
.slide-indicator{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.4);cursor:pointer;transition:var(--tr)}
.slide-indicator.active{background:#fff;width:24px;border-radius:4px}
.top-ads-text-bar{background:var(--grad1);background-size:200% 200%;animation:gradientShift 5s ease infinite;color:#fff;padding:8px 14px;border-radius:var(--rs);text-align:center;font-weight:800;overflow:hidden;white-space:nowrap;box-shadow:0 4px 15px var(--accent-g);margin-bottom:8px;display:flex;align-items:center;justify-content:center;gap:5px}
.top-ads-text-bar span{display:inline-block;animation:marquee 18s linear infinite;padding-right:100%}
@media(max-width:600px){.top-ads-slideshow{height:150px}}

.card{background:var(--card);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--gbrd);border-radius:var(--r);padding:16px;transition:var(--tr);position:relative;overflow:hidden;animation:fiu .4s ease;max-width:100%}
.card:hover{border-color:rgba(124,58,237,0.4);transform:translateY(-3px);box-shadow:var(--sh)}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:10px 20px;border-radius:var(--rs);font-family:'Tajawal',sans-serif;font-size:.88rem;font-weight:700;border:none;cursor:pointer;transition:var(--tr);text-decoration:none;position:relative;overflow:hidden;-webkit-tap-highlight-color:transparent;user-select:none;white-space:nowrap;outline:none}
.btn:active{transform:scale(0.96)}
.btn:focus{outline:none}
.bp{background:var(--grad1);color:#fff;box-shadow:0 6px 20px var(--accent-g)}
.bp:hover{transform:translateY(-2px);box-shadow:0 10px 30px var(--accent-g)}
.bs{background:var(--grad3);color:#fff}
.bd{background:linear-gradient(135deg,var(--err),#dc2626);color:#fff}
.bw{background:linear-gradient(135deg,var(--warn),#d97706);color:#000}
.bo{background:transparent;border:2px solid var(--brd);color:var(--t2)}
.bo:hover{border-color:var(--accent);color:var(--accent-l)}
.bsm{padding:6px 12px;font-size:.76rem}
.bbl{width:100%}
.btn:disabled{opacity:0.5;cursor:not-allowed;transform:none !important;box-shadow:none !important}
.btn-guest-locked{background:linear-gradient(135deg,var(--t3),var(--bg2));color:var(--t2);cursor:not-allowed;position:relative}

.fg{margin-bottom:14px}
.fl{display:block;margin-bottom:5px;font-size:.84rem;font-weight:700;color:var(--t2)}
.fi{width:100%;padding:10px 14px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);color:var(--t1);font-family:'Tajawal',sans-serif;font-size:.86rem;transition:var(--tr);outline:none}
.fi:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-g)}
textarea.fi{resize:vertical;min-height:80px}

.grid{display:grid;gap:12px;width:100%}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
.g5{grid-template-columns:repeat(5,1fr)}

.cat-circular-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:10px 0;width:100%;max-width:600px;margin:0 auto}
.cat-circular-item{display:flex;flex-direction:column;align-items:center;gap:10px;text-decoration:none;color:var(--t1);cursor:pointer;transition:var(--tr);animation:fiu .5s ease}
.cat-circular-item:hover{transform:translateY(-5px)}
.cat-circular-icon{width:80px;height:80px;border-radius:50%;background:var(--grad1);display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;box-shadow:0 8px 25px var(--accent-g);border:3px solid rgba(255,255,255,0.1);transition:var(--tr)}
.cat-circular-item:hover .cat-circular-icon{transform:scale(1.1);box-shadow:0 12px 35px var(--accent-g),0 0 40px var(--accent-g)}
.cat-circular-icon img{width:100%;height:100%;object-fit:cover;transition:transform 0.6s}
.cat-circular-item:hover .cat-circular-icon img{transform:scale(1.15)}
.cat-circular-icon .cat-emoji{font-size:2.2rem;display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:var(--grad1)}
.cat-circular-name{font-size:.78rem;font-weight:700;color:var(--t1);text-align:center;line-height:1.3;max-width:90px;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;transition:var(--tr)}
.cat-circular-item:hover .cat-circular-name{color:var(--accent-l)}
.cat-circular-count{font-size:.68rem;color:var(--t3);font-weight:600;background:rgba(124,58,237,0.1);padding:2px 8px;border-radius:10px;display:inline-flex;align-items:center;gap:4px}

@media(max-width:600px){
    .cat-circular-grid{grid-template-columns:repeat(3,1fr);gap:12px}
    .cat-circular-icon{width:70px;height:70px}
    .cat-circular-icon .cat-emoji{font-size:1.8rem}
    .cat-circular-name{font-size:.7rem;max-width:75px}
    .cat-circular-count{font-size:.6rem;padding:1px 6px}
}
@media(max-width:380px){
    .cat-circular-grid{grid-template-columns:repeat(3,1fr);gap:8px}
    .cat-circular-icon{width:60px;height:60px}
    .cat-circular-icon .cat-emoji{font-size:1.5rem}
    .cat-circular-name{font-size:.62rem;max-width:65px}
}

.cat-grid-2{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;width:100%}
.cat-card{background:var(--card);backdrop-filter:blur(20px);border:1px solid var(--gbrd);border-radius:var(--r);overflow:hidden;transition:var(--tr);cursor:pointer;text-decoration:none;color:inherit;display:block;position:relative;animation:fiu .5s ease;height:100%}
.cat-card:hover{border-color:rgba(124,58,237,0.5);transform:translateY(-5px) scale(1.02);box-shadow:0 15px 35px rgba(124,58,237,0.3)}
.cat-card-img{width:100%;height:120px;background:var(--grad1);display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
.cat-card-img img{width:100%;height:100%;object-fit:cover;transition:transform .6s;position:relative;z-index:1;pointer-events:none}
.cat-card:hover .cat-card-img img{transform:scale(1.15)}
.cat-card-overlay{position:absolute;inset:0;background:linear-gradient(180deg,transparent 40%,rgba(6,8,24,0.95) 100%);display:flex;align-items:flex-end;padding:10px;z-index:2}
.cat-card-overlay h3{color:#fff;font-size:.85rem;font-weight:800;text-shadow:0 2px 10px rgba(0,0,0,0.7)}
.cat-card-body{padding:10px}
.cat-card-desc{font-size:.7rem;color:var(--t3);margin-bottom:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2em}
.cat-card-count{display:inline-flex;align-items:center;gap:4px;color:var(--accent-l);font-weight:700;font-size:.68rem;background:rgba(124,58,237,0.12);padding:3px 10px;border-radius:20px}

.pc{background:var(--card);backdrop-filter:blur(20px);border:1px solid var(--gbrd);border-radius:var(--r);overflow:hidden;transition:var(--tr);cursor:pointer;position:relative;animation:fiu .4s ease;display:flex;flex-direction:column;height:100%;box-shadow:0 4px 16px rgba(0,0,0,0.2);max-width:100%}
.pc:hover{border-color:rgba(124,58,237,0.5);transform:translateY(-3px) scale(1.02);box-shadow:0 12px 35px rgba(124,58,237,0.2)}
.pc-img{width:100%;height:100px;background:var(--bg2);display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
.pc-img img{max-width:90%;max-height:90%;object-fit:contain;transition:transform .6s;pointer-events:none}
.pc:hover .pc-img img{transform:scale(1.12)}
.pc-body{padding:8px;flex:1;display:flex;flex-direction:column;position:relative;z-index:2}
.pc-name{font-size:.74rem;font-weight:700;color:var(--t1);margin-bottom:4px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.4em}
.pc-price-row{margin-top:auto;padding-top:4px;display:flex;align-items:center;justify-content:flex-start;gap:4px;flex-wrap:wrap}
.pc-price{font-size:.78rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;display:inline-block;animation:textGradient 3s ease infinite}
.pc-original-price{font-size:.68rem;color:var(--t3);text-decoration:line-through;text-decoration-color:var(--err)}

.pc-fav-card,.pc-quick-view,.pc-compare{position:absolute;width:26px;height:26px;background:rgba(5,6,20,0.75);backdrop-filter:blur(8px);border:1px solid var(--gbrd);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:.85rem;color:var(--accent-l);z-index:4;transition:var(--tr);line-height:1}
.pc-fav-card{top:6px;left:6px}
.pc-quick-view{bottom:6px;right:6px;font-size:.75rem}
.pc-compare{top:6px;right:40px;font-size:.7em}
.pc-fav-card:hover,.pc-quick-view:hover,.pc-compare:hover{transform:scale(1.2);background:var(--accent);color:#fff}
.pc-fav-card.active{background:var(--ok);color:#fff;border-color:var(--ok);animation:heartbeat 0.6s ease}
.pc-compare.active{background:var(--info);color:#fff}

.pc-discount-badge,.pc-new-badge,.pc-out-badge,.pc-featured-badge,.pc-offer-badge{position:absolute;top:6px;right:6px;color:#fff;padding:3px 10px;border-radius:20px;font-size:.58rem;font-weight:800;z-index:5;box-shadow:0 2px 10px rgba(0,0,0,0.3)}
.pc-discount-badge{background:linear-gradient(135deg,#ef4444,#dc2626);box-shadow:0 2px 10px rgba(239,68,68,0.4);animation:heartbeat 1.5s ease-in-out infinite}
.pc-new-badge{background:linear-gradient(135deg,#10b981,#06b6d4);box-shadow:0 2px 10px rgba(16,185,129,0.4)}
.pc-out-badge{background:linear-gradient(135deg,#ef4444,#dc2626);box-shadow:0 2px 10px rgba(239,68,68,0.4);animation:pulse 1.5s infinite}
.pc-featured-badge{background:linear-gradient(135deg,#f59e0b,#ec4899);box-shadow:0 2px 10px rgba(245,158,11,0.4);animation:glowPulse 2s ease-in-out infinite}
.pc-offer-badge{background:linear-gradient(135deg,#f59e0b,#ec4899);box-shadow:0 2px 10px rgba(245,158,11,0.4);animation:glowPulse 2s ease-in-out infinite}

@media(max-width:500px){
    .pc-img{height:80px}
    .pc-body{padding:6px}
    .pc-name{font-size:.66rem;line-height:1.2;min-height:2em}
    .pc-price{font-size:.7rem}
    .pc-fav-card{width:22px;height:22px;font-size:.72rem;top:4px;left:4px}
    .pc-quick-view{width:22px;height:22px;font-size:.65rem;bottom:4px;right:4px}
    .pc-compare{width:22px;height:22px;font-size:.6rem;top:4px;right:32px}
    .cat-card-img{height:90px}
    .cat-card-overlay h3{font-size:.75rem}
    .cat-card-desc{font-size:.62rem}
    .cat-card-count{font-size:.6rem}
}

@media(max-width:900px){.g3,.g4,.g5{grid-template-columns:repeat(4,1fr)}}
@media(max-width:700px){.g3,.g4,.g5{grid-template-columns:repeat(3,1fr)}}
@media(max-width:500px){.g2,.g3,.g4,.g5{grid-template-columns:repeat(2,1fr)}.grid{gap:8px}body{padding-bottom:80px}.cat-grid-2{grid-template-columns:repeat(2,1fr);gap:10px}}
@media(max-width:380px){.g2,.g3,.g4,.g5{grid-template-columns:repeat(2,1fr)}.grid{gap:6px}}

.lazy-img{opacity:0;transition:opacity .6s ease,filter .6s ease,transform .6s ease;filter:blur(8px);transform:scale(1.05)}
.lazy-img.loaded{opacity:1;filter:blur(0);transform:scale(1);animation:imgFadeIn .8s ease}
.img-skeleton{position:absolute;inset:0;background:linear-gradient(110deg,var(--bg2) 8%,var(--card-h) 18%,var(--bg2) 33%);background-size:200% 100%;animation:shimmer 1.5s linear infinite;z-index:0;overflow:hidden}

.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:18px;font-size:.68rem;font-weight:700}
.badge-ok{background:rgba(16,185,129,0.15);color:var(--ok)}
.badge-err{background:rgba(239,68,68,0.15);color:var(--err)}
.badge-warn{background:rgba(245,158,11,0.15);color:var(--warn)}
.badge-info{background:rgba(59,130,246,0.15);color:var(--info)}

.tag{display:inline-block;padding:3px 10px;border-radius:18px;font-size:.72rem;font-weight:600}
.tag-ok{background:rgba(16,185,129,0.15);color:var(--ok)}
.tag-err{background:rgba(239,68,68,0.15);color:var(--err)}
.tag-warn{background:rgba(245,158,11,0.15);color:var(--warn)}
.tag-info{background:rgba(124,58,237,0.15);color:var(--accent-l)}

.table-w{overflow-x:auto;border-radius:var(--r);border:1px solid var(--brd);background:var(--card);backdrop-filter:blur(15px);max-width:100%}
table{width:100%;border-collapse:collapse}
th{background:var(--bg2);color:var(--t2);font-weight:700;padding:10px 12px;text-align:right;font-size:.76rem;white-space:nowrap;border-bottom:2px solid var(--brd)}
td{padding:10px 12px;border-bottom:1px solid var(--brd);color:var(--t1);font-size:.76rem}
tr:hover td{background:rgba(124,58,237,0.04)}
tr:last-child td{border-bottom:none}

.empty{text-align:center;padding:40px 16px;color:var(--t3)}
.empty-icon{font-size:3rem;margin-bottom:12px;opacity:.5;animation:bounce 2s ease-in-out infinite;display:flex;justify-content:center}
.empty-text{font-size:1rem;font-weight:600}

.footer{text-align:center;padding:18px 12px;color:var(--t3);font-size:.76rem;border-top:1px solid var(--brd);margin-top:26px;background:var(--glass);backdrop-filter:blur(20px)}
.footer-links{display:flex;justify-content:center;gap:15px;margin-bottom:10px;flex-wrap:wrap}
.footer-link{color:var(--t2);text-decoration:none;font-size:.78rem;transition:var(--tr);display:inline-flex;align-items:center;gap:4px}
.footer-link:hover{color:var(--accent-l)}

.wallet-card{background:var(--grad1);background-size:200% 200%;animation:gradientShift 5s ease infinite;border-radius:var(--r);padding:24px;color:#fff;position:relative;overflow:hidden;box-shadow:0 10px 40px var(--accent-g)}
.wallet-balance{font-size:2.2rem;font-weight:900;margin:9px 0;position:relative;z-index:1;text-shadow:0 4px 20px rgba(0,0,0,0.3)}

.wallet-info-display{background:var(--bg2);border:2px solid var(--accent);border-radius:var(--r);padding:16px;margin-bottom:14px;animation:fiu .4s ease}
.wallet-info-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--brd);gap:10px;flex-wrap:wrap}
.wallet-info-label{font-size:.82rem;color:var(--t3);font-weight:700;display:flex;align-items:center;gap:5px;flex-shrink:0}
.wallet-info-value{font-size:.85rem;font-weight:800;color:var(--accent-l);display:flex;align-items:center;gap:8px;flex:1;min-width:0;flex-wrap:wrap;word-break:break-all;overflow-wrap:break-word}
.wallet-info-value code{font-family:'Courier New',monospace;font-size:.8rem;color:var(--t1);background:var(--bg);padding:4px 10px;border-radius:6px;word-break:break-all;overflow-wrap:break-word;max-width:100%;display:inline-block;direction:ltr;text-align:left}
.wallet-info-copy-btn{background:var(--accent);color:#fff;border:none;padding:6px 12px;border-radius:8px;font-size:.72rem;cursor:pointer;transition:var(--tr);display:inline-flex;align-items:center;gap:4px;flex-shrink:0;white-space:nowrap}
.wallet-info-copy-btn:hover{background:var(--accent-l);transform:scale(1.05)}
.wallet-info-copy-btn:active{transform:scale(0.95)}
@media(max-width:600px){.wallet-info-row{flex-direction:column;align-items:stretch;gap:6px}.wallet-info-value{justify-content:space-between}}

.product-detail{display:grid;grid-template-columns:1fr 1fr;gap:24px;max-width:1100px;margin:0 auto;animation:fiu .5s ease}
@media(max-width:700px){.product-detail{grid-template-columns:1fr;gap:18px}}

.product-images-gallery{display:flex;flex-direction:column;gap:10px}
.product-image-main{width:100%;border-radius:var(--r);background:var(--bg2);overflow:hidden;min-height:300px;max-height:450px;display:flex;align-items:center;justify-content:center;position:relative;border:1px solid var(--brd)}
.product-image-main img{max-width:100%;max-height:450px;object-fit:contain}
.product-thumbnails{display:flex;gap:6px;flex-wrap:wrap}
.product-thumb{width:60px;height:60px;border-radius:var(--rs);overflow:hidden;cursor:pointer;border:2px solid var(--brd);transition:var(--tr);display:flex;align-items:center;justify-content:center;background:var(--bg2)}
.product-thumb:hover,.product-thumb.active{border-color:var(--accent)}
.product-thumb img{max-width:90%;max-height:90%;object-fit:contain}
@media(max-width:600px){.product-image-main{min-height:220px;max-height:320px}.product-image-main img{max-height:320px}.product-thumb{width:50px;height:50px}}

::-webkit-scrollbar{width:7px;height:7px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--card-h);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}

.toast-c{position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:3000;display:flex;flex-direction:column;gap:9px;width:90%;max-width:400px}
.toast{padding:11px 20px;border-radius:var(--rs);font-weight:600;animation:fiu .4s ease;box-shadow:0 10px 40px rgba(0,0,0,0.5);text-align:center;color:#fff;backdrop-filter:blur(20px)}
.toast-ok{background:linear-gradient(135deg,rgba(16,185,129,0.95),rgba(6,182,212,0.95))}
.toast-err{background:linear-gradient(135deg,rgba(239,68,68,0.95),rgba(220,38,38,0.95))}
.toast-info{background:var(--grad1)}

.section-title{font-size:1.25rem;font-weight:900;margin:18px 0 14px;display:flex;align-items:center;gap:8px;position:relative}
.section-title::before{content:'';width:4px;height:24px;background:var(--grad1);border-radius:3px;box-shadow:0 0 15px var(--accent-g)}

.select-styled{width:100%;padding:12px 16px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);color:var(--t1);font-family:'Tajawal',sans-serif;font-size:.9rem;font-weight:700;outline:none;cursor:pointer;transition:var(--tr);appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a78bfa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");background-repeat:no-repeat;background-position:left 14px center;background-size:16px;margin-bottom:16px}
.select-styled:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-g)}
.select-styled option{background:var(--bg2);color:var(--t1);padding:10px}

.select-styled-wide{width:100%;padding:14px 18px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);color:var(--t1);font-family:'Tajawal',sans-serif;font-size:.95rem;font-weight:700;outline:none;cursor:pointer;transition:var(--tr);appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a78bfa' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");background-repeat:no-repeat;background-position:left 16px center;background-size:18px;margin-bottom:16px;min-height:50px}
.select-styled-wide:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-g)}
.select-styled-wide:hover{border-color:var(--accent-l)}
.select-styled-wide option{background:var(--bg2);color:var(--t1);padding:12px;font-size:.9rem}

.options-box-enhanced{background:linear-gradient(135deg,rgba(124,58,237,0.08),rgba(6,182,212,0.05));border:2px solid rgba(124,58,237,0.4);border-radius:var(--r);padding:18px;margin-bottom:18px;animation:fiu 0.4s ease;box-shadow:0 4px 20px rgba(124,58,237,0.1)}
.options-title-enhanced{font-size:1rem;font-weight:800;color:var(--accent-l);margin-bottom:14px;display:flex;align-items:center;gap:10px;padding-bottom:10px;border-bottom:1px dashed rgba(124,58,237,0.3)}
.option-info-box{margin-top:10px;padding:12px;background:var(--bg2);border-radius:var(--rs);border:1px solid var(--brd);display:flex;justify-content:space-between;align-items:center;transition:var(--tr)}
.option-price-display{font-size:1.2rem;font-weight:900;color:var(--ok);background:rgba(16,185,129,0.1);padding:5px 15px;border-radius:20px}
.dropdown-error{color:var(--err);font-size:0.8rem;margin-top:10px;font-weight:700;text-align:center;background:rgba(239,68,68,0.1);padding:8px 12px;border-radius:var(--rs);border:1px solid rgba(239,68,68,0.3);animation:shake 0.5s ease}

.required-fields-box{background:linear-gradient(135deg,rgba(245,158,11,0.08),rgba(124,58,237,0.05));border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:16px;margin-bottom:16px;animation:fiu .4s ease}
.required-fields-title{font-size:.94rem;font-weight:800;color:var(--warn);margin-bottom:12px;display:flex;align-items:center;gap:8px}
.field-group{margin-bottom:12px}
.field-label{display:block;margin-bottom:5px;font-size:.84rem;font-weight:700;color:var(--t2)}
.field-label .req-star{color:var(--err);margin-right:3px}
.field-input{width:100%;padding:10px 13px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);color:var(--t1);font-family:'Tajawal',sans-serif;font-size:.86rem;transition:var(--tr);outline:none}
.field-input:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-g)}
.field-hint{font-size:.7rem;color:var(--t3);margin-top:3px}

.instructions-box{background:linear-gradient(135deg,rgba(59,130,246,0.08),rgba(124,58,237,0.05));border:1px solid rgba(59,130,246,0.3);border-radius:var(--r);padding:14px;margin-bottom:16px}
.instructions-title{font-size:.94rem;font-weight:800;color:var(--info);margin-bottom:9px}
.instructions-content{font-size:.82rem;color:var(--t2);line-height:1.8;white-space:pre-wrap;word-wrap:break-word;background:var(--bg);padding:10px;border-radius:var(--rs);border-right:3px solid var(--info)}

.purchase-summary-box{margin-top:16px;padding:16px;background:linear-gradient(135deg,rgba(124,58,237,0.12),rgba(6,182,212,0.08));border:2px solid var(--accent);border-radius:var(--r);display:flex;flex-direction:column;gap:12px;animation:fiu .4s ease}
.purchase-total-row{display:flex;justify-content:space-between;align-items:center;padding-bottom:12px;border-bottom:1px dashed var(--brd)}
.purchase-total-label{font-size:1rem;font-weight:700;color:var(--t2)}
.purchase-total-value{font-size:1.5rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite}
.purchase-btn{width:100%;padding:14px 20px;font-size:1rem;font-weight:800;background:var(--grad3);color:#fff;border:none;border-radius:var(--rs);cursor:pointer;transition:var(--tr);display:flex;align-items:center;justify-content:center;gap:8px}
.purchase-btn:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(16,185,129,0.4)}
.purchase-btn:disabled{background:var(--bg2);color:var(--t3);cursor:not-allowed;transform:none;box-shadow:none}

.guest-login-prompt{background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(236,72,153,0.08));border:2px dashed rgba(245,158,11,0.4);border-radius:var(--r);padding:20px;text-align:center;margin-top:16px;animation:fiu .4s ease}
.guest-login-prompt-icon{font-size:3rem;margin-bottom:12px;animation:emojiDance 2s ease-in-out infinite;display:flex;justify-content:center}
.guest-login-prompt-title{font-size:1.1rem;font-weight:800;color:var(--warn);margin-bottom:8px}
.guest-login-prompt-text{font-size:.85rem;color:var(--t2);margin-bottom:15px;line-height:1.6}
.guest-login-prompt-btn{display:inline-flex;align-items:center;gap:5px;padding:12px 30px;background:var(--grad1);color:#fff;text-decoration:none;border-radius:30px;font-weight:800;transition:var(--tr);box-shadow:0 6px 20px var(--accent-g);animation:glowPulse 2s ease-in-out infinite}
.guest-login-prompt-btn:hover{transform:translateY(-2px);box-shadow:0 10px 30px var(--accent-g)}

.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.8);backdrop-filter:blur(5px);display:none;align-items:center;justify-content:center;z-index:5000;padding:20px}
.modal-overlay.active{display:flex;animation:fi 0.3s ease}
.modal-box{background:var(--bg2);border:1px solid var(--gbrd);border-radius:var(--r);padding:24px;max-width:500px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.5);animation:scaleIn 0.4s ease;max-height:90vh;overflow-y:auto}
.modal-icon{font-size:2.4rem;margin-bottom:10px;display:flex;justify-content:center;color:var(--accent-l)}
.modal-title{font-size:1.15rem;font-weight:900;margin-bottom:8px}
.modal-msg{color:var(--t2);margin-bottom:16px;font-size:.86rem;line-height:1.7}
.modal-actions{display:flex;gap:9px;justify-content:center;flex-wrap:wrap}

.quick-view-modal{position:fixed;inset:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;z-index:6000;padding:20px}
.quick-view-modal.active{display:flex;animation:fi 0.3s ease}
.quick-view-box{background:var(--bg2);border:1px solid var(--gbrd);border-radius:var(--r);padding:24px;max-width:600px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,0.5);animation:scaleIn 0.4s ease;max-height:90vh;overflow-y:auto;position:relative}
.quick-view-close{position:absolute;top:15px;left:15px;font-size:1.5rem;cursor:pointer;color:var(--t3);background:none;border:none;transition:var(--tr);z-index:10;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.quick-view-close:hover{color:var(--err);background:rgba(239,68,68,0.1);transform:rotate(90deg)}
.quick-view-img{width:100%;height:200px;background:var(--bg);border-radius:var(--rs);overflow:hidden;display:flex;align-items:center;justify-content:center;margin-bottom:15px}
.quick-view-img img{max-width:100%;max-height:100%;object-fit:contain}
.quick-view-name{font-size:1.2rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;margin-bottom:10px}
.quick-view-price{font-size:1.5rem;font-weight:900;color:var(--ok);margin-bottom:15px}
.quick-view-desc{font-size:.85rem;color:var(--t2);line-height:1.7;margin-bottom:20px}

.qty-selector{display:flex;align-items:center;gap:8px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);padding:5px;transition:var(--tr)}
.qty-btn{width:36px;height:36px;border-radius:var(--rs);background:var(--card-h);border:1px solid var(--brd);color:var(--t1);font-size:1.2rem;font-weight:900;cursor:pointer;transition:var(--tr);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.qty-btn:hover{background:var(--accent);color:#fff;transform:scale(1.05)}
.qty-input{flex:1;text-align:center;background:transparent;border:none;color:var(--t1);font-size:1.05rem;font-weight:800;font-family:'Tajawal',sans-serif;outline:none;min-width:50px}

.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:var(--glass);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border-top:1px solid var(--gbrd);display:flex;justify-content:space-around;align-items:center;padding:8px 4px;z-index:1000;box-shadow:0 -4px 20px rgba(0,0,0,0.3)}
.bottom-nav::before{content:'';position:absolute;top:0;left:0;width:100%;height:2px;background:var(--grad1);background-size:200% 100%;animation:barFlow 3s linear infinite}
.bottom-nav-item{display:flex;flex-direction:column;align-items:center;gap:3px;text-decoration:none;color:var(--t3);font-size:.62rem;font-weight:700;padding:6px 12px;border-radius:12px;transition:var(--tr);cursor:pointer;position:relative;flex:1;max-width:80px}
.bottom-nav-item:hover{color:var(--accent-l);transform:translateY(-2px)}
.bottom-nav-item.active{color:var(--accent)}
.bottom-nav-item.active .bottom-nav-icon{background:var(--grad1);color:#fff;transform:scale(1.1)}
.bottom-nav-icon{width:36px;height:36px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;transition:var(--tr);background:rgba(255,255,255,0.05)}
.bottom-nav-item:hover .bottom-nav-icon{background:rgba(124,58,237,0.2)}
.bottom-nav-badge{position:absolute;top:2px;right:8px;background:var(--err);color:#fff;width:16px;height:16px;border-radius:50%;font-size:.5rem;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid var(--bg)}
@media(max-width:600px){.bottom-nav-item{font-size:.55rem;padding:4px 8px}.bottom-nav-icon{width:30px;height:30px;font-size:1rem}.bottom-nav-badge{width:14px;height:14px;font-size:.45rem;top:0;right:4px}}

.wa-support-fab{position:fixed;bottom:80px;left:14px;width:50px;height:50px;border-radius:50%;background:#25d366;color:#fff;display:flex !important;align-items:center;justify-content:center;font-size:1.5rem;cursor:pointer;box-shadow:0 8px 28px rgba(37,211,102,0.4);z-index:9997;border:none;animation:float 3s ease-in-out infinite;transition:background 0.4s ease,box-shadow 0.4s ease,opacity 0.4s ease,visibility 0.4s ease;outline:none;text-decoration:none}
.wa-support-fab:hover{transform:scale(1.1);box-shadow:0 12px 35px rgba(37,211,102,0.6)}
.wa-support-fab:active{transform:scale(0.9)}

.back-to-top{position:fixed;bottom:80px;right:14px;width:45px;height:45px;background:var(--card-h);border:1px solid var(--gbrd);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 15px rgba(0,0,0,0.3);z-index:9997;opacity:0;pointer-events:none;transition:var(--tr);color:var(--accent-l);font-size:1.2rem;outline:none}
.back-to-top.visible{opacity:1;pointer-events:auto}
.back-to-top:hover{background:var(--accent);color:#fff;transform:translateY(-3px)}

.product-title-display{font-size:1.5rem;font-weight:900;margin-bottom:6px;background:linear-gradient(135deg,var(--t1),var(--accent-l));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.4}

.related-products-section{margin-top:30px;padding-top:20px;border-top:1px solid var(--brd)}
.related-products-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:12px}
@media(max-width:700px){.related-products-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:500px){.related-products-grid{grid-template-columns:repeat(2,1fr)}}

.share-buttons{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.share-btn{padding:8px 14px;border-radius:var(--rs);font-size:.78rem;font-weight:700;cursor:pointer;transition:var(--tr);border:none;color:#fff;display:inline-flex;align-items:center;gap:5px;text-decoration:none}
.share-btn:hover{transform:translateY(-2px)}
.share-btn.wa{background:#25d366}
.share-btn.tg{background:#0088cc}
.share-btn.copy{background:var(--accent)}

.stock-indicator{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:.7rem;font-weight:700}
.stock-in{background:rgba(16,185,129,0.15);color:var(--ok)}
.stock-out{background:rgba(239,68,68,0.15);color:var(--err)}
.out-of-stock-alert{background:rgba(239,68,68,0.1);border:2px solid rgba(239,68,68,0.3);color:var(--err);padding:14px;text-align:center;border-radius:var(--r);font-weight:800;margin-bottom:15px;animation:shake 1s ease infinite}

.loyalty-points-box{background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(236,72,153,0.08));border:1px solid rgba(245,158,11,0.3);border-radius:var(--rs);padding:12px 16px;display:flex;align-items:center;gap:10px;margin-bottom:12px}
.loyalty-points-icon{font-size:1.6rem}
.loyalty-points-text{font-size:.85rem;color:var(--warn);font-weight:700}

.vip-badge-display{display:inline-flex;align-items:center;gap:5px;padding:5px 14px;border-radius:20px;background:var(--vip-grad);color:#fff;font-size:.78rem;font-weight:900;box-shadow:0 4px 15px rgba(245,158,11,0.3);animation:vipGlow 2s ease-in-out infinite;text-shadow:0 2px 4px rgba(0,0,0,0.2)}
.vip-card{background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(236,72,153,0.1),rgba(124,58,237,0.1));border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:18px;margin-bottom:16px;position:relative;overflow:hidden;animation:fiu .4s ease}
.vip-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--vip-grad);animation:gradientShift 3s ease infinite}
.vip-card-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.vip-card-icon{font-size:2.5rem;animation:iconBounce 2s ease-in-out infinite}
.vip-card-title{font-size:1.1rem;font-weight:900;color:var(--warn)}
.vip-card-level{font-size:.8rem;color:var(--t3);font-weight:600}
.vip-card-benefits{font-size:.82rem;color:var(--t2);line-height:1.7;margin-top:8px}

.achievements-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;margin-top:12px}
.achievement-card{background:var(--card);border:1px solid var(--brd);border-radius:var(--rs);padding:14px;text-align:center;transition:var(--tr);animation:fiu .4s ease}
.achievement-card:hover{transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,0,0,0.2);border-color:var(--accent)}
.achievement-icon{font-size:2rem;margin-bottom:8px;animation:iconBounce 2s ease-in-out infinite}
.achievement-name{font-size:.78rem;font-weight:800;color:var(--t1);margin-bottom:4px}
.achievement-desc{font-size:.68rem;color:var(--t3);line-height:1.4}

.contest-card{background:linear-gradient(135deg,rgba(245,158,11,0.12),rgba(124,58,237,0.08));border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:18px;margin-bottom:14px;transition:var(--tr);animation:fiu .4s ease}
.contest-card:hover{transform:translateY(-3px);box-shadow:0 12px 30px rgba(245,158,11,0.2)}
.contest-title{font-size:1.1rem;font-weight:900;color:var(--warn);margin-bottom:8px;display:flex;align-items:center;gap:8px}
.contest-prize{font-size:.9rem;color:var(--ok);font-weight:800;background:rgba(16,185,129,0.1);padding:6px 14px;border-radius:20px;display:inline-block;margin-bottom:10px}
.contest-desc{font-size:.82rem;color:var(--t2);line-height:1.6;margin-bottom:12px}
.contest-end-date{font-size:.72rem;color:var(--t3);margin-bottom:10px}

.shipping-methods{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
.shipping-method{display:flex;align-items:center;gap:10px;padding:12px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);cursor:pointer;transition:var(--tr)}
.shipping-method:hover{border-color:var(--accent)}
.shipping-method.selected{border-color:var(--accent);background:rgba(124,58,237,0.1)}
.shipping-method input{width:18px;height:18px;accent-color:var(--accent)}
.shipping-method-info{flex:1}
.shipping-method-name{font-weight:700;font-size:.86rem}
.shipping-method-desc{font-size:.72rem;color:var(--t3);margin-top:2px}
.shipping-method-price{font-weight:800;color:var(--accent-l)}

.checkout-steps{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}
.checkout-step{flex:1;min-width:80px;padding:8px;background:var(--bg2);border:2px solid var(--brd);border-radius:var(--rs);text-align:center;font-size:.74rem;font-weight:700;color:var(--t3);transition:var(--tr);display:flex;align-items:center;justify-content:center;gap:5px}
.checkout-step.active{background:var(--grad1);color:#fff;border-color:transparent}
.checkout-step.completed{background:rgba(16,185,129,0.15);color:var(--ok);border-color:rgba(16,185,129,0.3)}

.sell-info-box{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
@media(max-width:600px){.sell-info-box{grid-template-columns:repeat(2,1fr)}}
.sell-info-item{background:var(--bg2);padding:9px;border-radius:var(--rs);text-align:center;border:1px solid var(--brd)}
.sell-info-label{font-size:.7rem;color:var(--t3);margin-bottom:2px}
.sell-info-value{font-weight:800;color:var(--accent-l)}

.product-tabs{display:flex;gap:5px;margin-bottom:15px;border-bottom:2px solid var(--brd);flex-wrap:wrap}
.product-tab{padding:10px 16px;cursor:pointer;font-weight:700;color:var(--t3);transition:var(--tr);border-bottom:3px solid transparent;font-size:.85rem;display:flex;align-items:center;gap:5px}
.product-tab:hover{color:var(--accent-l)}
.product-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.product-tab-content{display:none;animation:fiu .3s ease}
.product-tab-content.active{display:block}

.breadcrumb{display:flex;gap:8px;align-items:center;font-size:.78rem;color:var(--t3);margin-bottom:12px;flex-wrap:wrap}
.breadcrumb a{color:var(--accent-l);text-decoration:none;transition:var(--tr);display:inline-flex;align-items:center;gap:4px}
.breadcrumb a:hover{text-decoration:underline}
.breadcrumb-separator{opacity:0.5}

.cart-item{display:flex;gap:10px;padding:12px;background:var(--card);border:1px solid var(--brd);border-radius:var(--rs);margin-bottom:10px;align-items:center;animation:fiu .3s ease}
.cart-item-img{width:60px;height:60px;border-radius:var(--rs);overflow:hidden;background:var(--bg2);flex-shrink:0;display:flex;align-items:center;justify-content:center}
.cart-item-img img{width:100%;height:100%;object-fit:contain}
.cart-item-info{flex:1;min-width:0}
.cart-item-name{font-size:.85rem;font-weight:700;color:var(--t1);margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cart-item-price{font-size:.8rem;font-weight:800;color:var(--accent-l)}
.cart-item-remove{background:none;border:none;color:var(--err);font-size:1.2rem;cursor:pointer;padding:5px;transition:var(--tr);flex-shrink:0}
.cart-item-remove:hover{transform:scale(1.2)}

.comparison-table{width:100%;border-collapse:collapse;overflow:hidden;border-radius:var(--r)}
.comparison-table th,.comparison-table td{padding:12px;text-align:center;border:1px solid var(--brd)}
.comparison-table th{background:var(--grad1);color:#fff;font-weight:800}
.comparison-table td{background:var(--card)}
.comparison-product-img{width:80px;height:80px;margin:0 auto;border-radius:var(--rs);overflow:hidden;background:var(--bg2)}
.comparison-product-img img{width:100%;height:100%;object-fit:contain}

.faq-item{background:var(--card);border:1px solid var(--brd);border-radius:var(--rs);margin-bottom:10px;overflow:hidden;transition:var(--tr)}
.faq-item:hover{border-color:var(--accent)}
.faq-question{padding:14px;font-weight:700;cursor:pointer;display:flex;justify-content:space-between;align-items:center;color:var(--t1);font-size:.88rem}
.faq-question:hover{color:var(--accent-l)}
.faq-answer{max-height:0;overflow:hidden;transition:max-height 0.3s ease;padding:0 14px}
.faq-item.open .faq-answer{max-height:300px;padding:0 14px 14px}
.faq-answer{font-size:.82rem;color:var(--t2);line-height:1.7}
.faq-toggle{transition:transform 0.3s}
.faq-item.open .faq-toggle{transform:rotate(45deg)}

.blog-card{background:var(--card);border:1px solid var(--brd);border-radius:var(--r);overflow:hidden;transition:var(--tr);height:100%;display:flex;flex-direction:column}
.blog-card:hover{transform:translateY(-5px);box-shadow:0 15px 35px rgba(0,0,0,0.3);border-color:var(--accent)}
.blog-card-img{width:100%;height:180px;background:var(--grad1);overflow:hidden}
.blog-card-img img{width:100%;height:100%;object-fit:cover;transition:transform .6s}
.blog-card:hover .blog-card-img img{transform:scale(1.1)}
.blog-card-body{padding:14px;flex:1;display:flex;flex-direction:column}
.blog-card-title{font-size:.95rem;font-weight:800;color:var(--t1);margin-bottom:8px;line-height:1.4}
.blog-card-excerpt{font-size:.8rem;color:var(--t3);line-height:1.6;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.blog-card-date{font-size:.7rem;color:var(--t3);margin-top:10px}

.newsletter-box{background:var(--grad1);background-size:200% 200%;animation:gradientShift 5s ease infinite;padding:30px;border-radius:var(--r);text-align:center;color:#fff;margin-top:20px}
.newsletter-title{font-size:1.3rem;font-weight:900;margin-bottom:10px}
.newsletter-text{font-size:.88rem;opacity:.9;margin-bottom:15px}
.newsletter-form{display:flex;gap:8px;max-width:400px;margin:0 auto}
.newsletter-input{flex:1;padding:10px 14px;border:none;border-radius:var(--rs);outline:none;font-family:'Tajawal',sans-serif;font-size:.85rem}

.social-links{display:flex;justify-content:center;gap:12px;margin-top:15px;flex-wrap:wrap}
.social-link{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.2rem;text-decoration:none;transition:var(--tr)}
.social-link:hover{transform:translateY(-3px) scale(1.1)}
.social-link.fb{background:#1877f2}
.social-link.ig{background:linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)}
.social-link.tw{background:#1da1f2}
.social-link.yt{background:#ff0000}
.social-link.tg{background:#0088cc}
.social-link.wa{background:#25d366}

.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.stat-box{background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--r);padding:18px;text-align:center;transition:var(--tr);position:relative;overflow:hidden}
.stat-box::before{content:'';position:absolute;top:0;left:0;width:100%;height:3px;background:var(--grad1)}
.stat-box:hover{transform:translateY(-5px);box-shadow:0 15px 30px rgba(0,0,0,0.3)}
.stat-icon{font-size:2rem;margin-bottom:8px;display:inline-flex}
.stat-value{font-size:1.6rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite}
.stat-label{font-size:.75rem;color:var(--t3);margin-top:4px}

.filters-bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:12px;background:var(--card);border-radius:var(--rs);border:1px solid var(--brd)}
.filter-item{display:flex;flex-direction:column;gap:4px}
.filter-label{font-size:.72rem;color:var(--t3);font-weight:600}
.filter-select{padding:6px 10px;background:var(--bg2);border:1px solid var(--brd);border-radius:6px;color:var(--t1);font-size:.78rem;outline:none;cursor:pointer}
.filter-select:focus{border-color:var(--accent)}

.reviews-section{margin-top:30px;padding-top:20px;border-top:1px solid var(--brd)}
.reviews-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:12px}
.review-card{background:var(--card);border:1px solid var(--brd);border-radius:var(--rs);padding:14px;animation:fiu .4s ease}
.review-header{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.review-avatar{width:36px;height:36px;border-radius:50%;background:var(--grad1);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:.9rem}
.review-username{font-weight:700;font-size:.85rem;color:var(--t1)}
.review-stars{color:var(--warn);font-size:.8rem;margin-top:2px}
.review-comment{font-size:.82rem;color:var(--t2);line-height:1.6}
.review-date{font-size:.7rem;color:var(--t3);margin-top:6px}
.rating-display{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.rating-stars{color:var(--warn);font-size:1.2rem}
.rating-text{font-size:.85rem;color:var(--t2);font-weight:600}

.gift-card{background:linear-gradient(135deg,rgba(236,72,153,0.12),rgba(124,58,237,0.08));border:2px solid rgba(236,72,153,0.3);border-radius:var(--r);padding:18px;transition:var(--tr);position:relative;overflow:hidden;animation:fiu .4s ease;display:flex;flex-direction:column;gap:10px;height:100%}
.gift-card:hover{border-color:rgba(236,72,153,0.6);transform:translateY(-5px) scale(1.02);box-shadow:0 15px 40px rgba(236,72,153,0.3)}
.gift-card-img{width:100%;height:140px;border-radius:var(--rs);background:linear-gradient(135deg,rgba(236,72,153,0.2),rgba(124,58,237,0.15));display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
.gift-card-img img{width:100%;height:100%;object-fit:cover;transition:transform .6s}
.gift-card:hover .gift-card-img img{transform:scale(1.1)}
.gift-card-img-placeholder{font-size:3.5rem;animation:emojiDance 2s ease-in-out infinite}
.gift-card-name{font-size:1rem;font-weight:800;color:var(--t1);background:linear-gradient(135deg,var(--accent-l),#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.gift-card-desc{font-size:.78rem;color:var(--t3);line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.4em}
.gift-card-price{font-size:1.2rem;font-weight:900;color:var(--ok);background:rgba(16,185,129,0.1);padding:8px 16px;border-radius:20px;display:inline-block;margin-top:5px}
.gift-card-buy-btn{width:100%;padding:12px;background:linear-gradient(135deg,#ec4899,#7c3aed);color:#fff;border:none;border-radius:var(--rs);font-weight:800;cursor:pointer;transition:var(--tr);margin-top:auto;display:flex;align-items:center;justify-content:center;gap:8px}
.gift-card-buy-btn:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(236,72,153,0.4)}
.gift-card-buy-btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}

.gift-code-display{background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(6,182,212,0.1));border:2px dashed var(--ok);border-radius:var(--r);padding:18px;margin-top:15px;text-align:center;animation:scaleIn .4s ease}
.gift-code-label{font-size:.78rem;color:var(--t3);margin-bottom:8px;font-weight:600}
.gift-code-value{font-size:1.3rem;font-weight:900;color:var(--ok);font-family:monospace;letter-spacing:2px;background:var(--bg);padding:10px 20px;border-radius:var(--rs);display:inline-block;word-break:break-all}

.method-box{background:var(--card);backdrop-filter:blur(20px);border:2px solid var(--brd);border-radius:var(--r);padding:10px;text-align:center;cursor:pointer;transition:var(--tr);display:flex;flex-direction:column;align-items:center;gap:8px}
.method-box:hover{border-color:var(--accent);transform:translateY(-3px)}
.method-box.selected{border-color:var(--ok);background:rgba(16,185,129,0.1)}
.method-box-img{width:100%;height:80px;border-radius:var(--rs);overflow:hidden;background:var(--bg2);display:flex;align-items:center;justify-content:center}
.method-box-img img{max-width:100%;max-height:100%;object-fit:contain}
.method-box-icon{font-size:2rem;color:var(--accent-l)}
.method-box-name{font-size:0.85rem;font-weight:800;color:var(--t1)}
.method-box-desc{font-size:0.72rem;color:var(--t3)}
.method-box-price{font-size:0.9rem;font-weight:900;color:var(--ok);background:rgba(16,185,129,0.1);padding:4px 10px;border-radius:20px;display:inline-block;margin-top:5px}

.referral-box{background:linear-gradient(135deg,rgba(245,158,11,0.12),rgba(124,58,237,0.08));border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:18px;margin-bottom:16px;position:relative;overflow:hidden;animation:fiu .4s ease}
.referral-box::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--vip-grad);animation:gradientShift 3s ease infinite}
.referral-title{font-size:1.1rem;font-weight:900;color:var(--warn);margin-bottom:8px;display:flex;align-items:center;gap:8px}
.referral-text{font-size:.85rem;color:var(--t2);line-height:1.6;margin-bottom:14px}
.referral-link-box{background:var(--bg2);border:1px solid var(--brd);border-radius:var(--rs);padding:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.referral-link-box code{font-family:'Courier New',monospace;font-size:.82rem;color:var(--accent-l);background:var(--bg);padding:8px 12px;border-radius:8px;flex:1;min-width:0;word-break:break-all;direction:ltr;text-align:left}

.maint-screen{position:fixed;inset:0;background:#050614;display:flex;justify-content:center;align-items:center;z-index:9999;overflow:hidden}
.maint-bg{position:absolute;inset:0;background:radial-gradient(circle at 50% 50%,rgba(124,58,237,0.2) 0%,transparent 60%);animation:pulse 4s infinite}
.maint-card{background:rgba(15,20,45,0.8);backdrop-filter:blur(20px);border:1px solid rgba(124,58,237,0.3);border-radius:24px;padding:40px;text-align:center;max-width:500px;width:90%;box-shadow:0 0 50px rgba(124,58,237,0.2);position:relative;z-index:2}
.maint-icon{font-size:4rem;animation:spin 3s linear infinite;margin-bottom:20px;display:inline-block}
.maint-title{font-size:1.8rem;font-weight:900;background:linear-gradient(135deg,#7c3aed,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:15px}
.maint-msg{color:#cbd5e1;margin-bottom:30px;line-height:1.6;font-size:1rem}
.maint-timer-grid{display:flex;gap:15px;justify-content:center;margin-bottom:30px}
.maint-timer-box{background:rgba(5,8,25,0.8);border:1px solid rgba(255,255,255,0.1);padding:15px;border-radius:12px;min-width:70px}
.maint-timer-val{font-size:2rem;font-weight:900;color:#a78bfa;font-family:monospace}
.maint-timer-lbl{font-size:.8rem;color:#64748b;margin-top:5px}
.maint-btns{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.maint-btn{padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;color:#fff}
.maint-btn.wa{background:#25d366}
.maint-btn.tg{background:#0088cc}

.banned-screen{position:fixed;inset:0;background:linear-gradient(135deg,#0a0e26 0%,#1a0a1e 50%,#0a0e26 100%);display:flex;justify-content:center;align-items:center;z-index:99999;overflow:hidden;padding:20px}
.banned-bg-anim{position:absolute;inset:0;overflow:hidden;z-index:1}
.banned-orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:0.4;animation:float 8s ease-in-out infinite}
.banned-orb-1{width:400px;height:400px;background:#ef4444;top:-100px;right:-100px}
.banned-orb-2{width:300px;height:300px;background:#7c3aed;bottom:-50px;left:-50px;animation-delay:2s}
.banned-orb-3{width:200px;height:200px;background:#ec4899;top:40%;left:40%;animation-delay:4s}
.banned-card{background:rgba(15,20,45,0.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:2px solid rgba(239,68,68,0.3);border-radius:24px;padding:45px 35px;text-align:center;max-width:500px;width:100%;box-shadow:0 0 60px rgba(239,68,68,0.2);position:relative;z-index:2;animation:zoomIn 0.6s ease}
.banned-icon-container{position:relative;width:100px;height:100px;margin:0 auto 25px;display:flex;align-items:center;justify-content:center}
.banned-icon-circle{position:absolute;inset:0;border-radius:50%;background:linear-gradient(135deg,rgba(239,68,68,0.2),rgba(124,58,237,0.1));animation:bannedPulse 2s ease-in-out infinite}
.banned-icon{font-size:3.5rem;position:relative;z-index:1;animation:bannedPulse 2s ease-in-out infinite}
.banned-title{font-size:1.8rem;font-weight:900;background:linear-gradient(135deg,#ef4444,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:15px}
.banned-msg{color:#cbd5e1;margin-bottom:25px;line-height:1.7;font-size:.95rem}
.banned-reason{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:15px;margin-bottom:25px;text-align:right}
.banned-reason-label{font-size:.78rem;color:#ef4444;font-weight:800;margin-bottom:5px;display:flex;align-items:center;gap:5px}
.banned-reason-text{font-size:.88rem;color:#cbd5e1;line-height:1.6}
.banned-info{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:25px}
.banned-info-item{background:rgba(5,8,25,0.5);border:1px solid rgba(255,255,255,0.08);padding:12px;border-radius:10px;text-align:center}
.banned-info-label{font-size:.68rem;color:#64748b;margin-bottom:4px}
.banned-info-value{font-size:.82rem;color:#cbd5e1;font-weight:700}
.banned-btns{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.banned-btn{display:inline-flex;align-items:center;gap:8px;padding:12px 25px;border-radius:12px;text-decoration:none;font-weight:800;color:#fff;transition:all 0.3s ease;box-shadow:0 4px 15px rgba(0,0,0,0.3)}
.banned-btn:hover{transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,0,0,0.4)}
.banned-btn.wa{background:#25d366}
.banned-btn.tg{background:#0088cc}
@media(max-width:500px){.banned-card{padding:30px 20px}.banned-title{font-size:1.4rem}.banned-msg{font-size:.85rem}.banned-info{grid-template-columns:1fr}.banned-btn{padding:10px 20px;font-size:.85rem}}

.popup-notification-container{position:fixed;top:20px;right:20px;z-index:8000;display:flex;flex-direction:column;gap:12px;max-width:380px;width:90vw;pointer-events:none}
.popup-notification{background:linear-gradient(135deg,var(--bg2),rgba(15,20,45,0.95));border:1px solid var(--accent);border-radius:var(--r);padding:18px;box-shadow:0 15px 50px rgba(0,0,0,0.6),0 0 30px var(--accent-g);display:flex;align-items:flex-start;gap:14px;animation:popupSlideIn 0.5s cubic-bezier(0.4,0,0.2,1);overflow:hidden;pointer-events:auto;position:relative}
.popup-notification.removing{animation:popupSlideOut 0.4s cubic-bezier(0.4,0,0.2,1) forwards}
.popup-notification::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;width:0%;background:var(--grad1);animation:progressFill var(--notif-duration,5s) linear forwards}
.popup-notif-icon{font-size:2rem;flex-shrink:0;animation:emojiDance 1s ease-in-out infinite;display:flex;align-items:center;justify-content:center}
.popup-notif-content{flex:1;min-width:0}
.popup-notif-title{font-size:0.95rem;font-weight:800;color:var(--t1);margin-bottom:5px;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite}
.popup-notif-msg{font-size:0.8rem;color:var(--t2);line-height:1.6}
.popup-notif-close{background:none;border:none;color:var(--t3);font-size:1.1rem;cursor:pointer;padding:0;flex-shrink:0;transition:var(--tr);width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.popup-notif-close:hover{color:var(--err);background:rgba(239,68,68,0.1);transform:rotate(90deg)}
@media(max-width:600px){.popup-notification-container{top:10px;right:10px;left:10px;max-width:none;width:auto}.popup-notification{padding:14px}}

.welcome-popup{position:fixed;inset:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;z-index:7000;padding:20px;animation:fi 0.4s ease}
.welcome-popup-card{background:linear-gradient(135deg,var(--bg2),#0a0e26);border:1px solid var(--accent);border-radius:24px;padding:35px;max-width:440px;width:100%;text-align:center;box-shadow:0 0 60px var(--accent-g);position:relative;overflow:hidden;animation:scaleIn 0.6s ease}
.welcome-popup-icon{font-size:3.5rem;margin-bottom:16px;animation:emojiDance 2s ease-in-out infinite;position:relative;z-index:1}
.welcome-popup-title{font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;margin-bottom:12px;position:relative;z-index:1}
.welcome-popup-msg{color:var(--t2);font-size:.92rem;line-height:1.8;margin-bottom:22px;position:relative;z-index:1}

.confetti{position:fixed;top:0;width:10px;height:10px;z-index:99999;pointer-events:none;animation:confettiFall 3s linear forwards}

.image-preview-modal{position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:8000;display:none;align-items:center;justify-content:center;padding:20px}
.image-preview-modal.active{display:flex;animation:fi 0.3s ease}
.image-preview-modal img{max-width:95%;max-height:95vh;object-fit:contain;border-radius:10px}
.image-preview-close{position:absolute;top:20px;right:20px;background:rgba(0,0,0,0.5);color:#fff;border:none;width:40px;height:40px;border-radius:50%;font-size:1.5rem;cursor:pointer}

.cookie-banner{position:fixed;bottom:70px;left:0;right:0;background:var(--bg2);border-top:2px solid var(--accent);padding:15px 20px;z-index:9000;display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap;animation:slideUp 0.5s ease}
.cookie-banner-text{font-size:.82rem;color:var(--t2);flex:1}
.cookie-banner-btn{padding:8px 20px;background:var(--grad1);color:#fff;border:none;border-radius:var(--rs);cursor:pointer;font-weight:700;font-family:'Tajawal',sans-serif}

.floating-emoji{position:fixed;font-size:1.5rem;pointer-events:none;opacity:0.15;z-index:-1;animation:float 4s ease-in-out infinite}

img{max-width:100%;height:auto}
.header-left,.header-right{flex-wrap:nowrap;min-width:0}
.grid{min-width:0}
.pc,.cat-card,.card{min-width:0;max-width:100%}

.ripple-container{position:relative;overflow:hidden}
.ripple{position:absolute;border-radius:50%;background:rgba(255,255,255,0.6);transform:scale(0);animation:ripple 0.6s linear;pointer-events:none}

.btn-shimmer{position:relative;overflow:hidden}
.btn-shimmer::after{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.3),transparent);animation:shine 2s infinite}

.product-badges{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.product-badge{padding:4px 12px;border-radius:20px;font-size:.7rem;font-weight:700;display:inline-flex;align-items:center;gap:4px}
.product-badge.discount{background:linear-gradient(135deg,rgba(239,68,68,0.2),rgba(220,38,38,0.15));color:var(--err);border:1px solid rgba(239,68,68,0.3)}
.product-badge.new{background:linear-gradient(135deg,rgba(16,185,129,0.2),rgba(6,182,212,0.15));color:var(--ok);border:1px solid rgba(16,185,129,0.3)}
.product-badge.hot{background:linear-gradient(135deg,rgba(245,158,11,0.2),rgba(236,72,153,0.15));color:var(--warn);border:1px solid rgba(245,158,11,0.3)}
.product-badge.featured{background:linear-gradient(135deg,rgba(245,158,11,0.2),rgba(236,72,153,0.15));color:var(--warn);border:1px solid rgba(245,158,11,0.3);animation:glowPulse 2s ease-in-out infinite}
.product-badge.offer{background:linear-gradient(135deg,rgba(245,158,11,0.3),rgba(236,72,153,0.2));color:var(--warn);border:1px solid rgba(245,158,11,0.5);animation:glowPulse 2s ease-in-out infinite}

.svg-icon svg{width:100%;height:100%;display:block}
.svg-icon{display:inline-flex;align-items:center;justify-content:center;line-height:0;flex-shrink:0}
.btn .svg-icon,.bottom-nav-icon .svg-icon,.header-cart-btn .svg-icon,.header-notif-btn .svg-icon,.header-menu-btn .svg-icon,.header-add-btn .svg-icon{width:60%;height:60%}
.bottom-nav-icon .svg-icon{width:50%;height:50%}
.empty-icon .svg-icon{width:48px;height:48px}
.menu-item-icon .svg-icon{width:60%;height:60%}
.method-box-icon .svg-icon{width:32px;height:32px}
.popup-notif-icon .svg-icon{width:40px;height:40px}
.modal-icon .svg-icon{width:48px;height:48px}

.menu-page-container{max-width:600px;margin:0 auto;padding:10px}
.menu-header{display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid var(--brd)}
.menu-back-btn{display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:var(--card);border:1px solid var(--brd);color:var(--t1);cursor:pointer;transition:var(--tr);text-decoration:none}
.menu-back-btn:hover{background:var(--accent);color:#fff;transform:translateX(3px)}
.menu-title{font-size:1.5rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;flex:1}

.menu-profile-card{background:linear-gradient(135deg,rgba(124,58,237,0.15),rgba(6,182,212,0.08));border:2px solid var(--accent);border-radius:var(--r);padding:18px;display:flex;align-items:center;gap:14px;margin-bottom:18px;position:relative;overflow:hidden}
.menu-profile-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad1);animation:gradientShift 3s ease infinite}
.menu-avatar{width:70px;height:70px;border-radius:50%;background:var(--grad1);overflow:hidden;display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0;box-shadow:0 4px 20px var(--accent-g);border:3px solid rgba(255,255,255,0.15)}
.menu-avatar img{width:100%;height:100%;object-fit:cover}
.menu-profile-info{flex:1;min-width:0}
.menu-username{font-size:1.2rem;font-weight:900;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.menu-userid{font-size:.8rem;color:var(--t3);margin-top:3px}
.menu-balance{background:linear-gradient(135deg,#10b981,#06b6d4);color:#fff;padding:10px 16px;border-radius:30px;font-weight:900;font-size:.85rem;box-shadow:0 4px 15px rgba(16,185,129,0.3);white-space:nowrap}

.menu-guest-card{background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(236,72,153,0.08));border:2px dashed rgba(245,158,11,0.4);border-radius:var(--r);padding:18px;display:flex;align-items:center;gap:14px;margin-bottom:18px}
.menu-avatar-guest{width:70px;height:70px;border-radius:50%;background:var(--card-h);display:flex;align-items:center;justify-content:center;color:var(--t3);flex-shrink:0;border:2px dashed var(--brd)}
.menu-guest-text{flex:1}

.menu-section{background:var(--card);backdrop-filter:blur(20px);border:1px solid var(--gbrd);border-radius:var(--r);overflow:hidden;margin-bottom:14px}
.menu-section-title{padding:12px 16px;font-size:.8rem;font-weight:800;color:var(--t3);background:var(--bg2);border-bottom:1px solid var(--brd);letter-spacing:0.5px}
.menu-item-row{display:flex;align-items:center;gap:12px;padding:14px 16px;text-decoration:none;color:var(--t1);transition:var(--tr);position:relative;border-bottom:1px solid var(--brd)}
.menu-item-row:last-child{border-bottom:none}
.menu-item-row:hover{background:rgba(124,58,237,0.08)}
.menu-item-row:active{background:rgba(124,58,237,0.15)}
.menu-item-icon{width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0;box-shadow:0 4px 12px var(--accent-g);transition:var(--tr)}
.menu-item-row:hover .menu-item-icon{transform:scale(1.1) rotate(5deg);box-shadow:0 6px 20px var(--accent-g)}
.menu-item-content{flex:1;min-width:0}
.menu-item-name{font-size:.95rem;font-weight:800;color:var(--t1);margin-bottom:2px}
.menu-item-desc{font-size:.75rem;color:var(--t3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.menu-badge{background:var(--err);color:#fff;width:22px;height:22px;border-radius:50%;font-size:.7rem;font-weight:800;display:flex;align-items:center;justify-content:center;animation:notificationPulse 1.5s ease-in-out infinite}

.vip-badge-menu{display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:20px;background:var(--vip-grad);color:#fff;font-size:.72rem;font-weight:900;margin-top:5px;box-shadow:0 4px 15px rgba(245,158,11,0.3);animation:vipGlow 2s ease-in-out infinite}

.menu-footer{text-align:center;padding:20px 10px;color:var(--t3);font-size:.75rem}

@media(max-width:600px){
    .menu-page-container{padding:8px}
    .menu-profile-card,.menu-guest-card{padding:14px;gap:10px}
    .menu-avatar,.menu-avatar-guest{width:55px;height:55px}
    .menu-username{font-size:1rem}
    .menu-balance{padding:7px 12px;font-size:.72rem}
    .menu-item-row{padding:12px 14px;gap:10px}
    .menu-item-icon{width:42px;height:42px;border-radius:12px}
    .menu-item-name{font-size:.88rem}
    .menu-item-desc{font-size:.7rem}
}

@media(max-width:600px){
    .stats-grid{grid-template-columns:repeat(2,1fr)}
    .filters-bar{flex-direction:column;align-items:stretch}
    .filter-item{width:100%}
    .reviews-grid{grid-template-columns:1fr}
    .product-title-display{font-size:1.1rem}
    .wallet-balance{font-size:1.6rem}
    .newsletter-form{flex-direction:column}
    .blog-card-img{height:140px}
    .cookie-banner{flex-direction:column;text-align:center}
    .achievements-grid{grid-template-columns:repeat(2,1fr)}
}

.wa-full-page{display:flex;flex-direction:column;height:calc(100vh - 80px);max-width:700px;margin:0 auto;background:linear-gradient(180deg,#e5ddd5 0%,#dcd3c8 100%);border-radius:var(--r);overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.3);position:relative;color:#000 !important}

.wa-full-header{background:linear-gradient(135deg,#075e54,#128c7e);color:#fff !important;padding:10px 14px;display:flex;align-items:center;gap:10px;box-shadow:0 2px 10px rgba(0,0,0,0.2);z-index:10}
.wa-back-btn{display:flex;align-items:center;justify-content:center;color:#fff !important;text-decoration:none;width:34px;height:34px;border-radius:50%;transition:var(--tr)}
.wa-back-btn:hover{background:rgba(255,255,255,0.15)}
.wa-header-avatar{width:42px;height:42px;border-radius:50%;background:#fff;overflow:hidden;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,0.2)}
.wa-header-avatar img{width:100%;height:100%;object-fit:cover}
.wa-header-info{flex:1;min-width:0}
.wa-header-name{font-size:1rem;font-weight:800;color:#fff !important}
.wa-header-status{font-size:.72rem;opacity:.9;display:flex;align-items:center;gap:5px;color:#fff !important}
.wa-status-dot{width:8px;height:8px;border-radius:50%;background:#4ecb71;animation:pulse 2s infinite}
.wa-header-actions{display:flex;gap:5px}
.wa-header-btn{display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:transparent;border:none;color:#fff !important;cursor:pointer;transition:var(--tr);text-decoration:none}
.wa-header-btn:hover{background:rgba(255,255,255,0.15)}

.wa-full-body{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:8px;background-image:linear-gradient(rgba(255,255,255,0.4) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.4) 1px,transparent 1px);background-size:30px 30px}

.wa-date-separator{text-align:center;font-size:.7rem;color:#54656f !important;background:rgba(255,255,255,0.7);padding:5px 12px;border-radius:10px;align-self:center;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1)}

.wa-welcome-msg{background:rgba(255,255,255,0.95);padding:18px;border-radius:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.1);align-self:center;max-width:85%;margin-bottom:10px;color:#000 !important}
.wa-welcome-icon{color:#075e54 !important;margin-bottom:8px;display:flex;justify-content:center}
.wa-welcome-text{font-size:.95rem;font-weight:800;color:#075e54 !important;margin-bottom:5px}
.wa-welcome-sub{font-size:.78rem;color:#54656f !important;line-height:1.5}

.wa-msg{max-width:80%;padding:8px 12px;border-radius:10px;font-size:.88rem;line-height:1.4;word-wrap:break-word;position:relative;box-shadow:0 1px 2px rgba(0,0,0,0.1);animation:chatBubbleIn 0.3s ease;color:#000 !important}
.wa-msg.received{background:#fff;align-self:flex-start;border-bottom-left-radius:3px;border-top-left-radius:3px}
.wa-msg.sent{background:#d1f4cc;align-self:flex-end;border-bottom-right-radius:3px;border-top-right-radius:3px}
.wa-msg-time{font-size:.6rem;color:#667781 !important;margin-top:3px;text-align:left;display:flex;align-items:center;gap:3px;justify-content:flex-end}
.wa-msg.received .wa-msg-time{justify-content:flex-start}
.wa-msg-status{display:inline-flex;color:#667781 !important}
.wa-msg img{max-width:200px;max-height:200px;border-radius:8px;display:block;cursor:pointer}
.wa-msg-guest-alert{background:#fef3c7 !important;border:1px solid #f59e0b !important;color:#92400e !important;font-weight:700;text-align:center;align-self:center !important;max-width:90% !important}

.wa-full-input-area{background:#f0f0f0;padding:8px 10px;display:flex;align-items:center;gap:6px;border-top:1px solid #ddd}
.wa-input-btn{display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:transparent;border:none;color:#54656f !important;cursor:pointer;transition:var(--tr);flex-shrink:0}
.wa-input-btn:hover{background:rgba(0,0,0,0.05)}
.wa-input-wrap{flex:1;display:flex;align-items:center;background:#fff;border-radius:30px;padding:4px 6px 4px 14px;border:1px solid #ddd}
.wa-input-wrap input{flex:1;border:none;outline:none;background:transparent;font-family:'Tajawal',sans-serif;font-size:.88rem;padding:6px 0;color:#000 !important}
.wa-input-wrap input::placeholder{color:#667781 !important}
.wa-input-btn-inner{display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:transparent;border:none;color:#54656f !important;cursor:pointer;transition:var(--tr);position:relative;overflow:hidden}
.wa-input-btn-inner:hover{background:rgba(0,0,0,0.05)}
.wa-send-btn{display:flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#075e54,#128c7e);color:#fff !important;border:none;cursor:pointer;transition:var(--tr);flex-shrink:0;box-shadow:0 2px 10px rgba(7,94,84,0.3)}
.wa-send-btn:hover{transform:scale(1.1);box-shadow:0 4px 15px rgba(7,94,84,0.5)}
.wa-send-btn:active{transform:scale(0.95)}

.wa-emoji-picker{position:absolute;bottom:60px;left:10px;right:10px;background:#fff;border-radius:12px;padding:10px;box-shadow:0 5px 25px rgba(0,0,0,0.2);z-index:100}
.wa-emoji-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:5px}
.wa-emoji-grid span{font-size:1.5rem;cursor:pointer;padding:5px;border-radius:8px;text-align:center;transition:var(--tr)}
.wa-emoji-grid span:hover{background:#f0f0f0;transform:scale(1.2)}

@media(max-width:600px){
    .wa-full-page{height:calc(100vh - 70px);border-radius:0}
    .wa-header-name{font-size:.9rem}
    .wa-header-status{font-size:.65rem}
    .wa-msg{max-width:85%;font-size:.82rem}
    .wa-input-wrap input{font-size:.82rem}
}

.offers-page-title{font-size:1.5rem;font-weight:900;background:linear-gradient(135deg,#f59e0b,#ec4899,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.offer-card{background:linear-gradient(135deg,rgba(245,158,11,0.12),rgba(236,72,153,0.08),rgba(124,58,237,0.08));border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:18px;margin-bottom:14px;transition:var(--tr);animation:fiu .4s ease;position:relative;overflow:hidden}
.offer-card:hover{transform:translateY(-3px);box-shadow:0 12px 30px rgba(245,158,11,0.2);border-color:rgba(245,158,11,0.5)}
.offer-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f59e0b,#ec4899,#7c3aed);animation:gradientShift 3s ease infinite}
.offer-badge-large{position:absolute;top:15px;left:15px;background:linear-gradient(135deg,#f59e0b,#ec4899);color:#fff;padding:6px 16px;border-radius:20px;font-size:.85rem;font-weight:900;box-shadow:0 4px 15px rgba(245,158,11,0.4);animation:glowPulse 2s ease-in-out infinite}
.offer-title{font-size:1.1rem;font-weight:900;color:var(--t1);margin-bottom:8px;padding-left:80px}
.offer-desc{font-size:.82rem;color:var(--t2);line-height:1.6;margin-bottom:12px}
.offer-prices{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.offer-original-price{font-size:1rem;color:var(--t3);text-decoration:line-through}
.offer-new-price{font-size:1.4rem;font-weight:900;color:var(--ok)}
.offer-discount-percent{font-size:.85rem;font-weight:800;color:#f59e0b;background:rgba(245,158,11,0.15);padding:4px 12px;border-radius:20px}

.bottom-offers-section{background:linear-gradient(135deg,rgba(124,58,237,0.08),rgba(6,182,212,0.05),rgba(236,72,153,0.05));border-top:2px solid rgba(124,58,237,0.2);padding:24px 12px;margin-top:30px;border-radius:var(--r) var(--r) 0 0;position:relative;overflow:hidden}
.bottom-offers-section::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f59e0b,#ec4899,#7c3aed,#06b6d4);animation:gradientShift 3s ease infinite}
.bottom-offers-title{font-size:1.3rem;font-weight:900;background:linear-gradient(135deg,#f59e0b,#ec4899,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;margin-bottom:16px;display:flex;align-items:center;gap:8px;text-align:center;justify-content:center}
.bottom-offers-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;max-width:1200px;margin:0 auto}
.bottom-offer-card{background:var(--card);border:2px solid rgba(245,158,11,0.3);border-radius:var(--r);padding:16px;transition:var(--tr);position:relative;overflow:hidden;animation:fiu .4s ease;cursor:pointer;text-decoration:none;color:inherit;display:block}
.bottom-offer-card:hover{transform:translateY(-5px) scale(1.02);box-shadow:0 15px 40px rgba(245,158,11,0.3);border-color:rgba(245,158,11,0.6)}
.bottom-offer-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f59e0b,#ec4899);animation:gradientShift 3s ease infinite}
.bottom-offer-img{width:100%;height:120px;border-radius:var(--rs);background:var(--bg2);overflow:hidden;display:flex;align-items:center;justify-content:center;margin-bottom:10px}
.bottom-offer-img img{max-width:90%;max-height:90%;object-fit:contain}
.bottom-offer-badge{position:absolute;top:8px;left:8px;background:linear-gradient(135deg,#f59e0b,#ec4899);color:#fff;padding:4px 12px;border-radius:20px;font-size:.7rem;font-weight:900;box-shadow:0 2px 10px rgba(245,158,11,0.4);animation:glowPulse 2s ease-in-out infinite}
.bottom-offer-name{font-size:.9rem;font-weight:800;color:var(--t1);margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bottom-offer-prices{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bottom-offer-new-price{font-size:1rem;font-weight:900;color:var(--ok)}
.bottom-offer-old-price{font-size:.78rem;color:var(--t3);text-decoration:line-through}
.bottom-offer-discount{font-size:.72rem;font-weight:800;color:#f59e0b;background:rgba(245,158,11,0.15);padding:2px 8px;border-radius:12px}

.wheel-page-title{font-size:1.8rem;font-weight:900;background:linear-gradient(135deg,#f59e0b,#ec4899,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.wheel-container{background:linear-gradient(135deg,rgba(124,58,237,0.15),rgba(6,182,212,0.08),rgba(236,72,153,0.05));border:2px solid var(--accent);border-radius:var(--r);padding:24px;text-align:center;position:relative;overflow:hidden;animation:fiu .5s ease}
.wheel-container::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#f59e0b,#ec4899,#7c3aed,#06b6d4);animation:gradientShift 3s ease infinite}

.wheel-stats-box{display:flex;justify-content:center;gap:16px;margin-bottom:20px;flex-wrap:wrap}
.wheel-stat-item{background:var(--bg2);border:1px solid var(--brd);border-radius:var(--rs);padding:10px 20px;text-align:center;min-width:100px}
.wheel-stat-value{font-size:1.8rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite}
.wheel-stat-label{font-size:.72rem;color:var(--t3);margin-top:3px;font-weight:600}

.wheel-visual-container{position:relative;width:300px;height:300px;margin:0 auto 20px}
.wheel-pointer{position:absolute;top:-15px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:15px solid transparent;border-right:15px solid transparent;border-top:30px solid var(--err);z-index:10;filter:drop-shadow(0 4px 8px rgba(0,0,0,0.3))}
.wheel-svg{width:100%;height:100%;transition:transform 5s cubic-bezier(0.17,0.67,0.12,0.99);filter:drop-shadow(0 10px 30px rgba(124,58,237,0.4))}
.wheel-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:50px;height:50px;background:var(--bg);border:3px solid var(--accent);border-radius:50%;display:flex;align-items:center;justify-content:center;z-index:5;box-shadow:0 4px 15px var(--accent-g)}

.wheel-spin-btn{padding:16px 40px;font-size:1.2rem;font-weight:900;background:linear-gradient(135deg,#f59e0b,#ec4899,#7c3aed);color:#fff;border:none;border-radius:30px;cursor:pointer;transition:var(--tr);box-shadow:0 6px 25px rgba(245,158,11,0.4);animation:glowPulse 2s ease-in-out infinite;display:inline-flex;align-items:center;gap:10px}
.wheel-spin-btn:hover:not(:disabled){transform:translateY(-3px) scale(1.05);box-shadow:0 10px 35px rgba(245,158,11,0.6)}
.wheel-spin-btn:active:not(:disabled){transform:scale(0.95)}
.wheel-spin-btn:disabled{opacity:0.5;cursor:not-allowed;animation:none}

.wheel-result-box{margin-top:20px;padding:20px;border-radius:var(--r);animation:scaleIn .5s ease;display:none}
.wheel-result-box.show{display:block}
.wheel-result-icon{font-size:3rem;margin-bottom:10px;animation:emojiDance 1s ease-in-out infinite}
.wheel-result-text{font-size:1.2rem;font-weight:900;margin-bottom:10px}
.wheel-result-amount{font-size:2rem;font-weight:900;color:var(--ok)}

.wheel-info-box{margin-top:20px;background:var(--bg2);border:1px solid var(--brd);border-radius:var(--rs);padding:16px;text-align:right}
.wheel-info-title{font-size:.9rem;font-weight:800;color:var(--accent-l);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.wheel-info-text{font-size:.82rem;color:var(--t2);line-height:1.8}
.wheel-thresholds-list{margin-top:10px}
.wheel-threshold-item{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--bg);border-radius:var(--rs);margin-bottom:6px;border:1px solid var(--brd)}
.wheel-threshold-amount{font-weight:800;color:var(--accent-l)}
.wheel-threshold-spins{font-size:.78rem;color:var(--ok);font-weight:700}

@media(max-width:500px){
    .wheel-visual-container{width:260px;height:260px}
    .wheel-spin-btn{padding:14px 30px;font-size:1.1rem}
    .wheel-stat-item{min-width:80px;padding:8px 14px}
    .wheel-stat-value{font-size:1.5rem}
}

.maint-logo-circle{width:120px;height:120px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#06b6d4);display:flex;align-items:center;justify-content:center;overflow:hidden;margin:0 auto 30px;position:relative;box-shadow:0 0 50px rgba(124,58,237,0.6),0 0 100px rgba(124,58,237,0.3);animation:maintLogoPulse 2.5s ease-in-out infinite}
.maint-logo-circle img{width:100%;height:100%;object-fit:cover;position:relative;z-index:1}
.maint-logo-circle .logo-emoji{font-size:3.5rem;z-index:1;position:relative;color:#fff}
"""

SVG_ICONS = {
    "home": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>',
    "category": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect></svg>',
    "cart": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>',
    "wallet": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path><path d="M18 12a2 2 0 0 0 0 4h4v-4z"></path></svg>',
    "user": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>',
    "heart": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>',
    "heart_filled": '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>',
    "bell": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>',
    "gift": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"></polyline><rect x="2" y="7" width="20" height="5"></rect><line x1="12" y1="22" x2="12" y2="7"></line><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path></svg>',
    "compare": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="22"></line><polyline points="17 7 22 12 17 17"></polyline><polyline points="7 7 2 12 7 17"></polyline></svg>',
    "trophy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="9" x2="6" y2="2"></line><line x1="18" y1="9" x2="18" y2="2"></line><path d="M6 9a6 6 0 0 0 12 0"></path><line x1="12" y1="15" x2="12" y2="22"></line><path d="M8 22h8"></path></svg>',
    "medal": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="15" r="6"></circle><path d="M8.21 13.89L7 23l5-3 5 3-1.21-9.12"></path></svg>',
    "support": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>',
    "faq": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    "blog": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>',
    "orders": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-4"></path><polyline points="9 11 12 14 15 11"></polyline><line x1="12" y1="2" x2="12" y2="14"></line></svg>',
    "menu": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>',
    "close": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
    "whatsapp": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/></svg>',
    "telegram": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>',
    "send": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>',
    "attach": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>',
    "lock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>',
    "logout": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>',
    "edit": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>',
    "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    "arrow_up": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>',
    "arrow_back": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>',
    "phone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>',
    "mail": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>',
    "eye": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
    "share": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>',
    "copy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
    "package": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"></line><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>',
    "star": '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>',
    "fire": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>',
    "tag": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>',
    "settings": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
    "shield": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
    "diamond": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 18 3 22 9 12 22 2 9 6 3"></polygon><path d="M11 3L8 9l4 13 4-13-3-6"></path><line x1="2" y1="9" x2="22" y2="9"></line></svg>',
    "rocket": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91 0z"></path><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path></svg>',
    "money": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>',
    "shopping_bag": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>',
    "truck": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>',
    "credit_card": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>',
    "image": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
    "info": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
    "warning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    "check_circle": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
    "x_circle": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
    "grid": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect></svg>',
    "headphones": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>',
    "ticket": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"></path><line x1="13" y1="5" x2="13" y2="7"></line><line x1="13" y1="11" x2="13" y2="13"></line><line x1="13" y1="17" x2="13" y2="19"></line></svg>',
    "logout_chat": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>',
    "smile": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>',
    "mic": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>',
    "more_vertical": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>',
    "download": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    "upload": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>',
    "filter": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 10 12.46 22 3"></polygon></svg>',
    "users": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
    "star_outline": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>',
    "trending_up": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>',
    "moon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>',
    "sun": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>',
    "chevron_left": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>',
    "chevron_right": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>',
    "chevron_down": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    "plus": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
    "minus": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
    "trash": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
    "refresh": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>',
    "external_link": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>',
    "wheel": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="2" x2="12" y2="12"></line><line x1="12" y1="12" x2="21" y2="12"></line><line x1="12" y1="12" x2="5" y2="19"></line><line x1="12" y1="12" x2="19" y2="19"></line></svg>',
    "megaphone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-5v12L3 14v-3z"></path><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"></path></svg>',
    "channel": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-5v12L3 14v-3z"></path><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"></path></svg>'
}

def icon(name, size="1em", extra_class=""):
    svg = SVG_ICONS.get(name, SVG_ICONS["package"])
    return f'<span class="svg-icon {extra_class}" style="width:{size};height:{size};display:inline-flex;align-items:center;justify-content:center;line-height:0">{svg}</span>'

# ==============================================================================
# قوالب HTML و JavaScript
# ==============================================================================

LOADER_HTML = """
<div class="loader-screen" id="loaderScreen">
    <div class="loader-rocket-container">
        <div class="loader-ring loader-ring-1"></div>
        <div class="loader-ring loader-ring-2"></div>
        <div class="loader-ring loader-ring-3"></div>
        <div class="loader-rocket">{{ icon('rocket', '3em') }}</div>
    </div>
    <div class="loader-text-3d">{{ store_name }}</div>
    <div class="loader-text">جاري التحميل...</div>
    <div class="loader-progress-bar"></div>
</div>
<script>
(function(){
    function hideLoader(){
        var ls=document.getElementById('loaderScreen');
        if(ls){
            ls.classList.add('hidden');
            setTimeout(function(){if(ls&&ls.parentNode)ls.parentNode.removeChild(ls);},500);
        }
    }
    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',function(){setTimeout(hideLoader,400);});
    } else {
        setTimeout(hideLoader,400);
    }
    setTimeout(hideLoader,3000);
    if(typeof window!=='undefined'){
        window.addEventListener('load',function(){setTimeout(hideLoader,150);});
    }
})();
</script>
"""

LAZY_LOAD_SCRIPT = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    function handleLoad(img) {
        img.classList.add('loaded');
        var skel = img.previousElementSibling;
        if (skel && skel.classList.contains('img-skeleton')) { skel.style.opacity = '0'; setTimeout(function() { if(skel.parentNode) skel.parentNode.removeChild(skel); }, 400); }
    }
    function handleError(img) {
        img.classList.add('loaded'); img.style.opacity = '0.3';
        var skel = img.previousElementSibling;
        if (skel && skel.classList.contains('img-skeleton')) { skel.style.opacity = '0'; setTimeout(function() { if(skel.parentNode) skel.parentNode.removeChild(skel); }, 400); }
    }
    function initLazyImages() {
        var lazyImages = document.querySelectorAll('img.lazy-img:not(.loaded):not([data-init])');
        if ('IntersectionObserver' in window) {
            var imageObserver = new IntersectionObserver(function(entries, observer) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var img = entry.target; if (img.hasAttribute('data-init')) return;
                        img.setAttribute('data-init', '1');
                        img.addEventListener('load', function() { handleLoad(img); });
                        img.addEventListener('error', function() { handleError(img); });
                        if (img.dataset.src) img.src = img.dataset.src;
                        observer.unobserve(img);
                    }
                });
            }, { rootMargin: '300px 0px', threshold: 0.01 });
            lazyImages.forEach(function(img) { imageObserver.observe(img); });
        } else {
            lazyImages.forEach(function(img) { if (img.dataset.src) img.src = img.dataset.src; handleLoad(img); });
        }
    }
    initLazyImages();
    if ('MutationObserver' in window) {
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes && mutation.addedNodes.length > 0) {
                    var hasNewImages = false;
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1) {
                            if (node.tagName === 'IMG' && node.classList.contains('lazy-img') && !node.hasAttribute('data-init')) hasNewImages = true;
                            else if (node.querySelectorAll) {
                                var imgs = node.querySelectorAll('img.lazy-img:not([data-init])');
                                if (imgs.length > 0) hasNewImages = true;
                            }
                        }
                    });
                    if (hasNewImages) initLazyImages();
                }
            });
        });
        observer.observe(document.body, {childList: true, subtree: true});
    }
});
</script>
"""

GLOBAL_JS_SCRIPT = """
<script>
function openImagePreview(url){
    var img=document.getElementById('imagePreviewImg');
    var modal=document.getElementById('imagePreviewModal');
    if(img) img.src=url;
    if(modal) {modal.classList.add('active'); modal.style.display = 'flex';}
}
function closeImagePreview(){
    var modal=document.getElementById('imagePreviewModal');
    if(modal) {modal.classList.remove('active'); modal.style.display = '';}
}
function showModal(iconHtml,title,msg,playSnd){
    var m=document.getElementById('genericModal');
    if(!m) return;
    var iconEl=document.getElementById('modalIcon');
    var titleEl=document.getElementById('modalTitle');
    var msgEl=document.getElementById('modalMessage');
    if(iconEl) iconEl.innerHTML=iconHtml;
    if(titleEl) titleEl.textContent=title;
    if(msgEl) msgEl.innerHTML=msg;
    m.classList.add('active');
    m.style.display = 'flex';
}
function closeModal(){
    var m=document.getElementById('genericModal');
    if(m) {m.classList.remove('active'); m.style.display = '';}
}
function copyToClipboard(text){
    var ta=document.createElement('textarea');
    ta.value=text;
    ta.style.position='fixed';
    ta.style.opacity='0';
    document.body.appendChild(ta);
    ta.select();
    try{document.execCommand('copy');}catch(e){}
    document.body.removeChild(ta);
}
function toggleFavCard(e, el, prodId){
    if(e){e.stopPropagation();e.preventDefault();}
    fetch('/api/favorite/toggle/'+prodId,{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.active){
                el.classList.add('active');
                el.innerHTML = '{{ icon("heart_filled", "0.85em")|safe }}';
            } else if (d.success === false && d.message) {
                showModal('{{ icon("warning","2em")|safe }}','تنبيه', d.message);
            } else {
                el.classList.remove('active');
                el.innerHTML = '{{ icon("heart", "0.85em")|safe }}';
            }
        })
        .catch(function(){ 
            showModal('{{ icon("warning","2em")|safe }}','خطأ','يرجى تسجيل الدخول أولاً لإضافة المنتج للمفضلة.'); 
        });
}
function toggleCompare(e, el, prodId){
    if(e){e.stopPropagation();e.preventDefault();}
    fetch('/api/compare/toggle/'+prodId,{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.active === true){
                el.classList.add('active');
            } else if(d.active === false){
                el.classList.remove('active');
            } else if(d.message){
                showModal('{{ icon("warning","2em")|safe }}','تنبيه', d.message);
            }
        })
        .catch(function(){ 
            showModal('{{ icon("warning","2em")|safe }}','خطأ','يرجى تسجيل الدخول أولاً لاستخدام المقارنة.'); 
        });
}
function quickView(e, prodId) {
    if(e){e.stopPropagation();e.preventDefault();}
    fetch('/api/quick-view/'+prodId)
        .then(function(r){return r.json();})
        .then(function(data){
            if(data.success){
                var img=document.getElementById('qvImg');
                var name=document.getElementById('qvName');
                var price=document.getElementById('qvPrice');
                var desc=document.getElementById('qvDesc');
                var buyBtn=document.getElementById('qvBuyBtn');
                if(img) img.src = data.image_url || '';
                if(name) name.textContent = data.name;
                if(price) price.textContent = data.price;
                if(desc) desc.textContent = data.description || 'لا يوجد وصف متاح حالياً.';
                if(buyBtn) buyBtn.onclick = function() { window.location.href = '/product/'+prodId; };
                var modal=document.getElementById('quickViewModal');
                if(modal) {modal.classList.add('active'); modal.style.display='flex';}
            } else {
                showModal('{{ icon("x_circle","2em")|safe }}', 'خطأ', data.message || 'تعذر جلب البيانات');
            }
        })
        .catch(function(){ 
            showModal('{{ icon("warning","2em")|safe }}','خطأ','حدث خطأ في الاتصال'); 
        });
}
function closeQuickView(){
    var modal=document.getElementById('quickViewModal');
    if(modal) {modal.classList.remove('active'); modal.style.display='';}
}
function handleSearch(e){
    if(e.key==='Enter'){
        var q=document.getElementById('globalSearch').value.trim();
        if(q){window.location.href='/search?q='+encodeURIComponent(q);}
    }
}
function liveSearch(){
    var q=document.getElementById('globalSearch').value.trim();
    var resBox=document.getElementById('liveSearchResults');
    if(!resBox) return;
    if(q.length<2){
        resBox.style.display='none';
        return;
    }
    fetch('/api/search?q='+encodeURIComponent(q))
        .then(function(r){return r.json();})
        .then(function(data){
            if(data.products && data.products.length>0){
                resBox.innerHTML = data.products.map(function(p){
                    return '<div style="padding:10px;cursor:pointer;border-bottom:1px solid var(--brd)" onclick="window.location.href=\'/product/'+p.id+'\'"><span>'+p.name+'</span> - <span style="color:var(--accent-l);font-weight:700">'+p.price+'</span></div>';
                }).join('');
                resBox.style.display='block';
            } else {
                resBox.innerHTML = '<div style="padding:10px;color:var(--t3)">لا توجد نتائج</div>';
                resBox.style.display='block';
            }
        })
        .catch(function(){});
}
function markNotificationRead(id){
    fetch('/api/notification/read/'+id,{method:'POST'})
        .then(function(){location.reload();})
        .catch(function(){});
}
function markAllNotificationsRead() {
    fetch('/api/notifications/read-all', {method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){ if(d.success) location.reload(); })
        .catch(function(){});
}

function toggleCurrency() {
    fetch('/api/currency/switch', {method:'POST', credentials: 'same-origin'})
        .then(r => r.json())
        .then(d => {
            if(d.success) {
                var msg = d.message || 'تم تحديث الأسعار';
                showPopupNotification('💱 تم تغيير العملة', msg, '{{ icon("money","2em")|safe }}');
                if(typeof showToast === 'function'){ showToast(msg); }
                setTimeout(function(){ location.reload(); }, 900);
            } else if(typeof showModal === 'function') {
                showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', d.message || 'تعذر تغيير العملة');
            }
        })
        .catch(() => { if(typeof showModal === 'function'){ showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'حدث خطأ في الاتصال بالخادم'); } });
}

function showPopupNotification(title, message, iconHtml) {
    var container = document.getElementById('popupNotificationContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'popupNotificationContainer';
        container.className = 'popup-notification-container';
        document.body.appendChild(container);
    }
    var notif = document.createElement('div');
    notif.className = 'popup-notification';
    notif.style.setProperty('--notif-duration', '{{ popup_notif_duration }}s');
    notif.innerHTML = `
        <div class="popup-notif-icon">${iconHtml || '{{ icon("bell","2em")|safe }}'}</div>
        <div class="popup-notif-content">
            <div class="popup-notif-title">${title}</div>
            <div class="popup-notif-msg">${message}</div>
        </div>
        <button class="popup-notif-close">{{ icon("close","1.1em")|safe }}</button>
    `;
    container.appendChild(notif);
    
    var closeBtn = notif.querySelector('.popup-notif-close');
    closeBtn.addEventListener('click', function() {
        notif.classList.add('removing');
        setTimeout(function() { if(notif.parentNode) notif.parentNode.removeChild(notif); }, 400);
    });
    
    var duration = parseInt('{{ popup_notif_duration }}') * 1000 || 5000;
    setTimeout(function() {
        if(notif.parentNode) {
            notif.classList.add('removing');
            setTimeout(function() { if(notif.parentNode) notif.parentNode.removeChild(notif); }, 400);
        }
    }, duration);
}

var POPUPS_ENABLED = ('{{ enable_popup_notifications }}' === '1');
var lastNotifId = 0;
function checkNewPopupNotifications() {
    if(!POPUPS_ENABLED) return;
    fetch('/api/notifications/check?last='+lastNotifId)
        .then(r => r.json())
        .then(data => {
            if(data.notifications && data.notifications.length > 0) {
                data.notifications.forEach(function(n) {
                    showPopupNotification(n.title, n.message, '{{ icon("bell","2em")|safe }}');
                    if(n.id > lastNotifId) lastNotifId = n.id;
                    fetch('/api/notification/read/'+n.id, {method:'POST'});
                });
            }
            if(data.max_id && data.max_id > lastNotifId) {
                lastNotifId = data.max_id;
            }
        })
        .catch(() => {});
}
function showSiteEntryNotification() {
    if(!POPUPS_ENABLED) return;
    try {
        if(sessionStorage.getItem('mo_entry_notif_shown')) return;
        var cfgEl = document.getElementById('site-config-data');
        if(!cfgEl) return;
        var cfg = JSON.parse(cfgEl.textContent || '{}');
        if(cfg.entry_title || cfg.entry_msg) {
            sessionStorage.setItem('mo_entry_notif_shown', '1');
            setTimeout(function(){
                showPopupNotification(cfg.entry_title || 'مرحباً بك', cfg.entry_msg || '', '{{ icon("megaphone","2em")|safe }}');
            }, 1200);
        }
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded', function() {
    var btnHeaderNotif = document.getElementById('btnHeaderNotif');
    var btnCloseNotifPanel = document.getElementById('btnCloseNotifPanel');
    var notificationsPanel = document.getElementById('notificationsPanel');

    function openNotifPanel() {
        if (notificationsPanel) {
            notificationsPanel.style.display = 'flex';
            notificationsPanel.style.animation = 'scaleIn 0.3s ease';
            fetch('/api/notifications/unread')
                .then(r => r.json())
                .then(data => {
                    if(data.notifications && data.notifications.length > 0) {
                        var body = document.getElementById('notificationsBody');
                        if(body) {
                            body.innerHTML = data.notifications.map(function(n) {
                                return '<div class="notif-item" data-id="'+n.id+'" style="padding:12px 14px;border-bottom:1px solid var(--brd);cursor:pointer;transition:var(--tr);background:rgba(124,58,237,0.05);border-right:3px solid var(--accent);" onclick="markNotificationRead('+n.id+')">'+
                                    '<div style="font-weight:700;font-size:.85rem;margin-bottom:4px;color:var(--t1);">'+n.title+'</div>'+
                                    '<div style="font-size:.76rem;color:var(--t2);line-height:1.5;">'+n.message+'</div>'+
                                    '<div style="font-size:.65rem;color:var(--t3);margin-top:5px;">'+(n.created_at||'').slice(0,16)+'</div>'+
                                '</div>';
                            }).join('');
                        }
                    }
                })
                .catch(function(){});
        }
    }

    function closeNotifPanel() {
        if (notificationsPanel) {
            notificationsPanel.style.display = 'none';
        }
    }

    if (btnHeaderNotif) {
        btnHeaderNotif.style.cursor = 'pointer';
        btnHeaderNotif.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (notificationsPanel.style.display === 'flex' || notificationsPanel.style.display === 'block') {
                closeNotifPanel();
            } else {
                openNotifPanel();
            }
            return false;
        };
    }

    if (btnCloseNotifPanel) {
        btnCloseNotifPanel.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeNotifPanel();
            return false;
        };
    }

    document.addEventListener('click', function(e) {
        if (notificationsPanel && notificationsPanel.style.display === 'flex') {
            if (!notificationsPanel.contains(e.target) && btnHeaderNotif && !btnHeaderNotif.contains(e.target)) {
                closeNotifPanel();
            }
        }
    });
    
    if (notificationsPanel) {
        notificationsPanel.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }

    var backToTop = document.getElementById('backToTop');
    if (backToTop) {
        backToTop.addEventListener('click', function(e) {
            e.preventDefault();
            window.scrollTo({top: 0, behavior: 'smooth'});
        });
        window.addEventListener('scroll', function() {
            if(window.pageYOffset > 300) { backToTop.classList.add('visible'); } 
            else { backToTop.classList.remove('visible'); }
        });
    }

    var genericModal = document.getElementById('genericModal');
    var quickViewModal = document.getElementById('quickViewModal');
    var imagePreviewModal = document.getElementById('imagePreviewModal');
    var btnCloseQuickView = document.getElementById('btnCloseQuickView');
    var btnCloseImagePreview = document.getElementById('btnCloseImagePreview');

    if (genericModal) {
        genericModal.addEventListener('click', function(e) { if (e.target === genericModal) closeModal(); });
    }
    if (quickViewModal) {
        quickViewModal.addEventListener('click', function(e) { if (e.target === quickViewModal) closeQuickView(); });
    }
    if (btnCloseQuickView) {
        btnCloseQuickView.addEventListener('click', function(e) { e.preventDefault(); closeQuickView(); });
    }
    if (imagePreviewModal) {
        imagePreviewModal.addEventListener('click', function(e) { if (e.target === imagePreviewModal) closeImagePreview(); });
    }
    if (btnCloseImagePreview) {
        btnCloseImagePreview.addEventListener('click', function(e) { e.preventDefault(); closeImagePreview(); });
    }

    document.addEventListener('click', function(e) {
        var liveSearchResults = document.getElementById('liveSearchResults');
        var globalSearch = document.getElementById('globalSearch');
        if (liveSearchResults && globalSearch && !liveSearchResults.contains(e.target) && e.target !== globalSearch) {
            liveSearchResults.style.display = 'none';
        }
    });

    document.querySelectorAll('.faq-question').forEach(function(q) {
        q.addEventListener('click', function() {
            q.parentElement.classList.toggle('open');
        });
    });

    document.querySelectorAll('.product-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            var target = tab.getAttribute('data-tab');
            document.querySelectorAll('.product-tab').forEach(function(t) { t.classList.remove('active'); });
            document.querySelectorAll('.product-tab-content').forEach(function(c) { c.classList.remove('active'); });
            tab.classList.add('active');
            var content = document.getElementById('tab-' + target);
            if(content) content.classList.add('active');
        });
    });

    if(POPUPS_ENABLED){
        fetch('/api/notifications/unread')
            .then(r => r.json())
            .then(data => { 
                if(data.notifications && data.notifications.length > 0) {
                    data.notifications.forEach(function(n) {
                        showPopupNotification(n.title, n.message, '{{ icon("bell","2em")|safe }}');
                        if(n.id > lastNotifId) lastNotifId = n.id;
                        fetch('/api/notification/read/'+n.id, {method:'POST'}).catch(function(){});
                    });
                } else {
                    if(data.max_id) lastNotifId = data.max_id;
                }
            })
            .catch(() => {});
        showSiteEntryNotification();
        setInterval(checkNewPopupNotifications, 45000);
    }
});
</script>
"""

WELCOME_POPUP_HTML = """
<div class="welcome-popup" id="welcomePopup" style="display:none;">
    <div class="welcome-popup-card">
        <div class="welcome-popup-icon">
            {% if welcome_popup_image %}<img src="/images/{{ welcome_popup_image }}" alt="welcome" style="width:90px;height:90px;border-radius:50%;object-fit:cover;box-shadow:0 0 30px var(--accent-g);border:3px solid var(--accent)">{% elif store_logo %}<img src="/images/{{ store_logo }}" alt="logo" style="width:80px;height:80px;border-radius:50%;object-fit:cover;box-shadow:0 0 25px var(--accent-g);border:3px solid var(--accent)">{% else %}{{ icon('rocket', '3.5em') }}{% endif %}
        </div>
        <div class="welcome-popup-title">{{ welcome_popup_title }}</div>
        <div class="welcome-popup-msg">{{ welcome_popup_message }}</div>
        <button class="btn bp bbl" id="btnCloseWelcomePopup">{{ icon('check', '1em') }} تصفح المتجر الآن</button>
    </div>
</div>
<script>
(function(){
    function closeWelcomePopup(){
        var wp=document.getElementById('welcomePopup');
        if(wp){wp.style.display='none';}
        try{sessionStorage.setItem('mo_welcome_shown','1');}catch(e){}
    }
    document.addEventListener('DOMContentLoaded', function(){
        var btn = document.getElementById('btnCloseWelcomePopup');
        if(btn) btn.addEventListener('click', closeWelcomePopup);
        try{
            var shown=sessionStorage.getItem('mo_welcome_shown');
            if(!shown){
                setTimeout(function(){
                    var wp=document.getElementById('welcomePopup');
                    if(wp)wp.style.display='flex';
                },800);
            }
        }catch(e){
            setTimeout(function(){
                var wp=document.getElementById('welcomePopup');
                if(wp)wp.style.display='flex';
            },800);
        }
        if(btn) {
            btn.addEventListener('click', function(){
                try{sessionStorage.setItem('mo_welcome_shown','1');}catch(e){}
            });
        }
    });
})();
</script>
"""

AD_SLIDESHOW_SCRIPT = """
<script>
function initAdSlideshow(){
    var slideshows = document.querySelectorAll('.top-ads-slideshow');
    slideshows.forEach(function(slideshow){
        if(slideshow.dataset.initialized) return;
        slideshow.dataset.initialized = '1';
        var slides = slideshow.querySelectorAll('.slide');
        if(slides.length <= 1) return;
        var currentIdx = 0;
        var indicators = slideshow.querySelectorAll('.slide-indicator');
        function showSlide(idx){
            slides.forEach(function(s,i){s.classList.toggle('active', i===idx);});
            indicators.forEach(function(d,i){d.classList.toggle('active', i===idx);});
            currentIdx = idx;
        }
        function nextSlide(){showSlide((currentIdx + 1) % slides.length);}
        var interval = setInterval(nextSlide, 4000);
        slideshow.addEventListener('mouseenter', function(){clearInterval(interval);});
        slideshow.addEventListener('mouseleave', function(){interval = setInterval(nextSlide, 4000);});
        if(typeof goToSlide === 'undefined'){
            window.goToSlide = function(idx){
                if(slideshows.length > 0){
                    var s = slideshows[0];
                    var ss = s.querySelectorAll('.slide');
                    if(idx >= 0 && idx < ss.length){
                        ss.forEach(function(sl,i){sl.classList.toggle('active', i===idx);});
                        var inds = s.querySelectorAll('.slide-indicator');
                        inds.forEach(function(d,i){d.classList.toggle('active', i===idx);});
                    }
                }
            };
        }
    });
}
document.addEventListener('DOMContentLoaded', initAdSlideshow);
setTimeout(initAdSlideshow, 500);
</script>
"""

MAINTENANCE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>صيانة - {{ store_name }}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Cairo:wght@400;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--accent:#7c3aed;--accent2:#06b6d4;--bg:#050614}
body{font-family:'Tajawal','Cairo',sans-serif;background:var(--bg);color:#fff;direction:rtl;min-height:100vh;overflow:hidden;display:flex;justify-content:center;align-items:center}
.bg-anim{position:fixed;inset:0;overflow:hidden;z-index:1}
.orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:0.5;animation:float 8s ease-in-out infinite}
.orb-1{width:400px;height:400px;background:#7c3aed;top:-100px;right:-100px}
.orb-2{width:300px;height:300px;background:#06b6d4;bottom:-50px;left:-50px;animation-delay:2s}
.orb-3{width:200px;height:200px;background:#ec4899;top:40%;left:40%;animation-delay:4s}
@keyframes float{0%,100%{transform:translate(0,0) scale(1);opacity:0.5}33%{transform:translate(30px,-50px) scale(1.1);opacity:0.7}66%{transform:translate(-20px,30px) scale(0.9);opacity:0.3}}
.maint-card{background:rgba(15,20,45,0.6);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(124,58,237,0.3);border-radius:24px;padding:50px;text-align:center;max-width:600px;width:90%;box-shadow:0 0 60px rgba(124,58,237,0.2);position:relative;z-index:2;animation:zoomIn 0.6s ease;max-height:90vh;overflow-y:auto}
@keyframes zoomIn{from{transform:scale(0.8);opacity:0}to{transform:scale(1);opacity:1}}
.maint-logo-circle{width:140px;height:140px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#06b6d4);display:flex;align-items:center;justify-content:center;overflow:hidden;margin:0 auto 30px;position:relative;box-shadow:0 0 50px rgba(124,58,237,0.6),0 0 100px rgba(124,58,237,0.3);animation:maintLogoPulse 2.5s ease-in-out infinite}
.maint-logo-circle img{width:100%;height:100%;object-fit:cover;position:relative;z-index:1}
.maint-logo-circle .logo-emoji{font-size:4rem;z-index:1;position:relative;color:#fff}
@keyframes maintLogoPulse{0%,100%{transform:scale(1) rotate(0deg);box-shadow:0 0 50px rgba(124,58,237,0.6),0 0 100px rgba(124,58,237,0.3)}25%{transform:scale(1.1) rotate(-5deg);box-shadow:0 0 70px rgba(6,182,212,0.8),0 0 140px rgba(6,182,212,0.4)}50%{transform:scale(0.95) rotate(5deg);box-shadow:0 0 90px rgba(236,72,153,0.7),0 0 180px rgba(236,72,153,0.4)}75%{transform:scale(1.05) rotate(-3deg);box-shadow:0 0 60px rgba(124,58,237,0.9),0 0 120px rgba(124,58,237,0.5)}}
.maint-logo-circle::after{content:'';position:absolute;inset:-10px;border-radius:50%;border:2px solid rgba(124,58,237,0.5);animation:maintRingExpand 2s ease-out infinite}
@keyframes maintRingExpand{0%{transform:scale(1);opacity:1}100%{transform:scale(1.5);opacity:0}}
.maint-images-gallery{display:flex;gap:12px;justify-content:center;margin-bottom:25px;flex-wrap:wrap}
.maint-images-gallery img{max-width:180px;max-height:180px;border-radius:14px;object-fit:cover;border:2px solid rgba(124,58,237,0.3);box-shadow:0 4px 20px rgba(0,0,0,0.4);animation:zoomIn 0.8s ease}
.maint-title{font-size:2rem;font-weight:900;background:linear-gradient(135deg,#7c3aed,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:15px}
.maint-msg{color:#cbd5e1;margin-bottom:30px;line-height:1.6;font-size:1.1rem}
.maint-timer-grid{display:flex;gap:15px;justify-content:center;margin-bottom:40px}
.maint-timer-box{background:rgba(5,8,25,0.8);border:1px solid rgba(255,255,255,0.1);padding:15px 25px;border-radius:12px;min-width:80px;box-shadow:0 4px 15px rgba(0,0,0,0.3)}
.maint-timer-val{font-size:2.2rem;font-weight:900;color:#a78bfa;font-family:monospace;text-shadow:0 0 15px rgba(167,139,250,0.5)}
.maint-timer-lbl{font-size:.85rem;color:#64748b;margin-top:5px;text-transform:uppercase}
.maint-btns{display:flex;gap:20px;justify-content:center;flex-wrap:wrap}
.maint-btn{display:inline-flex;align-items:center;gap:10px;padding:12px 25px;border-radius:12px;text-decoration:none;font-weight:700;color:#fff;transition:all 0.3s ease;box-shadow:0 4px 15px rgba(0,0,0,0.3)}
.maint-btn:hover{transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,0,0,0.4)}
.maint-btn svg{width:24px;height:24px;fill:currentColor}
.maint-btn.wa{background:#25D366}
.maint-btn.tg{background:#229ED9}
@media(max-width:500px){.maint-card{padding:30px 20px}.maint-title{font-size:1.5rem}.maint-timer-val{font-size:1.8rem}.maint-timer-box{padding:10px 15px;min-width:60px}.maint-btn{padding:10px 20px;font-size:.9rem}.maint-images-gallery img{max-width:130px;max-height:130px}}
</style>
</head>
<body>
<div class="bg-anim">
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>
<div class="orb orb-3"></div>
</div>
<div class="maint-card">
<div class="maint-logo-circle">
{% if store_logo %}<img src="/images/{{ store_logo }}" alt="logo">{% else %}<span class="logo-emoji">🛍️</span>{% endif %}
</div>
<h1 class="maint-title">تحت الصيانة</h1>
<p class="maint-msg">{{ message }}</p>
{% if maintenance_images and maintenance_images|length > 0 %}
<div class="maint-images-gallery">
{% for img in maintenance_images %}
<img src="/images/{{ img.image_path }}" alt="{{ img.title or 'صيانة' }}" onerror="this.style.display='none'">
{% endfor %}
</div>
{% endif %}
{% if remaining > 0 %}
<div class="maint-timer-grid">
<div class="maint-timer-box"><div class="maint-timer-val" id="hours">00</div><div class="maint-timer-lbl">ساعة</div></div>
<div class="maint-timer-box"><div class="maint-timer-val" id="minutes">00</div><div class="maint-timer-lbl">دقيقة</div></div>
<div class="maint-timer-box"><div class="maint-timer-val" id="seconds">00</div><div class="maint-timer-lbl">ثانية</div></div>
</div>
{% else %}
<div style="margin-bottom:40px;color:#a78bfa;font-weight:700;font-size:1.1rem">سيتم العودة قريباً</div>
{% endif %}
<div class="maint-btns">
<a href="{{ support_whatsapp }}" target="_blank" class="maint-btn wa">
<svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43-.14-.01-.31-.01-.48-.01-.17 0-.43.06-.66.31-.23.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14-1.18-.06-.11-.22-.17-.47-.29z"/></svg>
واتساب
</a>
<a href="{{ support_telegram }}" target="_blank" class="maint-btn tg">
<svg viewBox="0 0 24 24"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>
تلجرام
</a>
</div>
</div>
<script>
var remaining = {{ remaining }};
function updateTimer() {
if (remaining <= 0) { return; }
var h = Math.floor(remaining / 3600);
var m = Math.floor((remaining % 3600) / 60);
var s = remaining % 60;
var hEl = document.getElementById('hours');
var mEl = document.getElementById('minutes');
var sEl = document.getElementById('seconds');
if(hEl) hEl.textContent = String(h).padStart(2, '0');
if(mEl) mEl.textContent = String(m).padStart(2, '0');
if(sEl) sEl.textContent = String(s).padStart(2, '0');
remaining--;
if(remaining < 0) { location.reload(); }
}
updateTimer();
setInterval(updateTimer, 1000);
</script>
</body>
</html>"""

BANNED_PAGE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>الحساب محظور - {{ store_name }}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Cairo:wght@400;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--accent:#ef4444;--bg:#050614}
body{font-family:'Tajawal','Cairo',sans-serif;background:var(--bg);color:#fff;direction:rtl;min-height:100vh;overflow:hidden;display:flex;justify-content:center;align-items:center}
.banned-bg-anim{position:fixed;inset:0;overflow:hidden;z-index:1}
.banned-orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:0.4;animation:float 8s ease-in-out infinite}
.banned-orb-1{width:400px;height:400px;background:#ef4444;top:-100px;right:-100px}
.banned-orb-2{width:300px;height:300px;background:#7c3aed;bottom:-50px;left:-50px;animation-delay:2s}
.banned-orb-3{width:200px;height:200px;background:#ec4899;top:40%;left:40%;animation-delay:4s}
@keyframes float{0%,100%{transform:translate(0,0) scale(1);opacity:0.4}33%{transform:translate(30px,-50px) scale(1.1);opacity:0.6}66%{transform:translate(-20px,30px) scale(0.9);opacity:0.2}}
.banned-card{background:rgba(15,20,45,0.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:2px solid rgba(239,68,68,0.3);border-radius:24px;padding:45px 35px;text-align:center;max-width:500px;width:90%;box-shadow:0 0 60px rgba(239,68,68,0.2);position:relative;z-index:2;animation:zoomIn 0.6s ease}
@keyframes zoomIn{from{transform:scale(0.8);opacity:0}to{transform:scale(1);opacity:1}}
.banned-icon-container{position:relative;width:100px;height:100px;margin:0 auto 25px;display:flex;align-items:center;justify-content:center}
.banned-icon-circle{position:absolute;inset:0;border-radius:50%;background:linear-gradient(135deg,rgba(239,68,68,0.2),rgba(124,58,237,0.1));animation:bannedPulse 2s ease-in-out infinite}
.banned-icon{font-size:3.5rem;position:relative;z-index:1;animation:bannedPulse 2s ease-in-out infinite}
@keyframes bannedPulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.05);opacity:0.8}}
.banned-title{font-size:1.8rem;font-weight:900;background:linear-gradient(135deg,#ef4444,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:15px}
.banned-msg{color:#cbd5e1;margin-bottom:25px;line-height:1.7;font-size:.95rem}
.banned-reason{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:15px;margin-bottom:25px;text-align:right}
.banned-reason-label{font-size:.78rem;color:#ef4444;font-weight:800;margin-bottom:5px;display:flex;align-items:center;gap:5px}
.banned-reason-text{font-size:.88rem;color:#cbd5e1;line-height:1.6}
.banned-info{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:25px}
.banned-info-item{background:rgba(5,8,25,0.5);border:1px solid rgba(255,255,255,0.08);padding:12px;border-radius:10px;text-align:center}
.banned-info-label{font-size:.68rem;color:#64748b;margin-bottom:4px}
.banned-info-value{font-size:.82rem;color:#cbd5e1;font-weight:700}
.banned-btns{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.banned-btn{display:inline-flex;align-items:center;gap:8px;padding:12px 25px;border-radius:12px;text-decoration:none;font-weight:800;color:#fff;transition:all 0.3s ease;box-shadow:0 4px 15px rgba(0,0,0,0.3)}
.banned-btn:hover{transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,0,0,0.4)}
.banned-btn.wa{background:#25d366}
.banned-btn.tg{background:#0088cc}
@media(max-width:500px){.banned-card{padding:30px 20px}.banned-title{font-size:1.4rem}.banned-msg{font-size:.85rem}.banned-info{grid-template-columns:1fr}.banned-btn{padding:10px 20px;font-size:.85rem}}
</style>
</head>
<body>
<div class="banned-bg-anim">
<div class="banned-orb banned-orb-1"></div>
<div class="banned-orb banned-orb-2"></div>
<div class="banned-orb banned-orb-3"></div>
</div>
<div class="banned-card">
<div class="banned-icon-container">
<div class="banned-icon-circle"></div>
<div class="banned-icon">🚫</div>
</div>
<h1 class="banned-title">تم حظر حسابك</h1>
<p class="banned-msg">عذراً، تم تقييد وصولك إلى المتجر بسبب مخالفة شروط الاستخدام. إذا كنت تعتقد أن هذا خطأ، يرجى التواصل مع الدعم الفني.</p>
<div class="banned-reason">
<div class="banned-reason-label">📝 سبب الحظر:</div>
<div class="banned-reason-text">{{ ban_reason or 'لم يتم تحديد سبب واضح' }}</div>
</div>
<div class="banned-info">
<div class="banned-info-item">
<div class="banned-info-label">المستخدم</div>
<div class="banned-info-value">{{ username }}</div>
</div>
<div class="banned-info-item">
<div class="banned-info-label">تاريخ الحظر</div>
<div class="banned-info-value">{{ banned_at }}</div>
</div>
</div>
<div class="banned-btns">
<a href="{{ support_whatsapp }}" target="_blank" class="banned-btn wa">
<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43-.14-.01-.31-.01-.48-.01-.17 0-.43.06-.66.31-.23.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14-1.18-.06-.11-.22-.17-.47-.29z"/></svg>
واتساب الدعم
</a>
<a href="{{ support_telegram }}" target="_blank" class="banned-btn tg">
<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>
تلجرام الدعم
</a>
</div>
</div>
</body>
</html>"""

ERROR_404_TMPL = """{% extends "base" %}{% block content %}<div class="error-page" style="text-align:center;padding:50px 20px"><div style="margin-bottom:16px;display:flex;justify-content:center">{{ icon('search', '4em') }}</div><h1 style="font-size:1.5rem;font-weight:900;color:var(--t1);margin-bottom:10px">الصفحة غير موجودة</h1><p style="color:var(--t3);font-size:.9rem;margin-bottom:20px">عذراً، الصفحة التي تبحث عنها غير متوفرة أو تم نقلها.</p><a href="/" class="btn bp" style="text-decoration:none">{{ icon('home', '1em') }} العودة للرئيسية</a></div>{% endblock %}"""

BASE_TMPL = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><meta name="theme-color" content="#050614">{% if site_icon %}<link rel="icon" type="image/x-icon" href="/images/{{ site_icon }}">{% elif store_logo %}<link rel="icon" type="image/x-icon" href="/images/{{ store_logo }}">{% endif %}<title>{{ title }} - {{ store_name }}</title><style>{{ css|safe }}</style>{% if site_background %}<style>body.has-bg{background-image:url('/images/{{ site_background }}') !important;}</style>{% endif %}</head><body class="{% if site_background %}has-bg{% endif %}">""" + LOADER_HTML + """
<script type="application/json" id="site-config-data">
{
    "entry_title": {{ site_entry_notif_title|tojson|safe }},
    "entry_msg": {{ site_entry_notif_message|tojson|safe }}
}
</script>
<header class="header">
    <div class="hdr">
        <a href="/" class="header-left">
            <div class="header-logo-circle">
                {% if store_logo %}<img src="/images/{{ store_logo }}" alt="logo">{% else %}<span class="logo-emoji">{{ icon('shopping_bag', '1.4em') }}</span>{% endif %}
            </div>
            <span class="header-store-name">{{ store_name }}</span>
        </a>
        <div class="header-right">
            <button class="header-add-btn" onclick="window.location.href='/wallet/topup'" title="شحن المحفظة">{{ icon('plus', '1.5em') }}</button>
            {% if logged_in %}
            <span class="header-balance-box" onclick="window.location.href='/wallet'">{{ icon('wallet', '1em') }} {{ balance }}</span>
            <button class="header-cart-btn" onclick="window.location.href='/cart'" title="السلة">{{ icon('cart', '1.1em') }}{% if cart_count > 0 %}<span class="header-cart-badge">{{ cart_count }}</span>{% endif %}</button>
            <button class="header-notif-btn" id="btnHeaderNotif" title="الإشعارات">{{ icon('bell', '1.1em') }}{% if notifications_count > 0 %}<span class="header-notif-badge">{{ notifications_count }}</span>{% endif %}</button>
            {% else %}
            <a href="/login" class="header-login-btn">{{ icon('rocket', '1em') }} الدخول</a>
            {% endif %}
            <button class="header-currency-btn" onclick="toggleCurrency()" title="تبديل العملة">
                {% if session_currency == 'USD' %}{{ icon('money', '0.85em') }} SYP{% else %}{{ icon('money', '0.85em') }} USD{% endif %}
            </button>
            <a href="/menu" class="header-menu-btn" title="القائمة">
                {{ icon('menu', '1.2em') }}
            </a>
        </div>
    </div>
    <div class="header-search-row">
        <div class="header-search-wrap">
            <span class="search-icon">{{ icon('search', '1.1em') }}</span>
            <input type="text" id="globalSearch" placeholder="ابحث عن منتجات..." oninput="liveSearch()" onkeypress="handleSearch(event)">
        </div>
        <div id="liveSearchResults" style="position:absolute;top:50px;right:0;left:0;background:var(--bg2);border:1px solid var(--gbrd);border-radius:var(--rs);max-height:300px;overflow-y:auto;display:none;z-index:1000"></div>
    </div>
</header>
{% if promo_bar_text %}
<a href="{{ promo_bar_link or '#' }}" class="promo-bar"><span>{{ promo_bar_text }}</span></a>
{% endif %}
{% if top_ads_images or top_ads_text %}
<div class="top-ads-container">
    {% if top_ads_images and top_ads_images|length > 0 %}
    <div class="top-ads-slideshow" id="topAdsSlideshow">
        {% for ad in top_ads_images %}
        <div class="slide {% if loop.first %}active{% endif %}">
            {% if ad.link_url %}<a href="{{ ad.link_url }}" target="_blank">{% endif %}
            {% if ad.image_path %}<img src="/images/{{ ad.image_path }}" alt="{{ ad.title }}" style="width:100%;height:100%;object-fit:cover;">
            {% elif ad.image_url %}<img src="{{ ad.image_url }}" alt="{{ ad.title }}" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none'">{% else %}<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:var(--grad1);color:#fff;font-size:1.5rem;font-weight:800">{{ ad.title or 'إعلان' }}</div>{% endif %}
            {% if ad.link_url %}</a>{% endif %}
        </div>
        {% endfor %}
        {% if top_ads_images|length > 1 %}
        <div class="slide-indicators">
            {% for ad in top_ads_images %}<div class="slide-indicator {% if loop.first %}active{% endif %}" onclick="goToSlide({{ loop.index0 }})"></div>{% endfor %}
        </div>
        {% endif %}
    </div>
    {% endif %}
    {% if top_ads_text and top_ads_text|length > 0 %}
    <div class="top-ads-text-bar"><span>{{ icon('info', '1em') }} {% for ad in top_ads_text %}{{ ad.content }} • {% endfor %}</span></div>
    {% endif %}
</div>
{% endif %}

<div class="notifications-panel" id="notificationsPanel" style="position:fixed;top:70px;left:14px;width:340px;max-height:450px;background:var(--bg2);border:1px solid var(--gbrd);border-radius:var(--r);z-index:5000;display:none;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5);animation:scaleIn 0.3s ease;">
    <div style="padding:14px 16px;border-bottom:1px solid var(--brd);font-weight:800;display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,rgba(124,58,237,0.15),rgba(6,182,212,0.08));">
        <span style="display:flex;align-items:center;gap:8px;font-size:.95rem;">
            {{ icon('bell', '1.1em') }} الإشعارات
            {% if notifications_count > 0 %}
            <span style="background:var(--err);color:#fff;padding:2px 8px;border-radius:10px;font-size:.7rem;font-weight:700;">{{ notifications_count }}</span>
            {% endif %}
        </span>
        <button id="btnCloseNotifPanel" style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);color:var(--err);cursor:pointer;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;transition:all 0.3s;">
            {{ icon('close', '1em') }}
        </button>
    </div>
    <div style="flex:1;overflow-y:auto;padding:5px;max-height:380px;" id="notificationsBody">
        {% for n in user_notifications %}
        <div class="notif-item" data-id="{{ n.id }}" style="padding:12px 14px;border-bottom:1px solid var(--brd);cursor:pointer;transition:var(--tr);position:relative;{% if not n.is_read %}background:rgba(124,58,237,0.05);border-right:3px solid var(--accent);{% endif %}" onclick="markNotificationRead({{ n.id }})">
            <div style="font-weight:700;font-size:.85rem;margin-bottom:4px;color:var(--t1);">{{ n.title }}</div>
            <div style="font-size:.76rem;color:var(--t2);line-height:1.5;">{{ n.message }}</div>
            <div style="font-size:.65rem;color:var(--t3);margin-top:5px;display:flex;align-items:center;gap:4px;">{{ icon('clock', '0.8em') }} {{ n.created_at[:16] }}</div>
        </div>
        {% endfor %}
        {% if not user_notifications %}
        <div style="text-align:center;padding:40px 20px;color:var(--t3);">
            <div style="font-size:2.5rem;margin-bottom:10px;opacity:0.5;">{{ icon('bell', '2.5em') }}</div>
            <div style="font-size:.85rem;font-weight:600;">لا توجد إشعارات جديدة</div>
        </div>
        {% endif %}
    </div>
    {% if user_notifications %}
    <div style="padding:10px;border-top:1px solid var(--brd);text-align:center;display:flex;justify-content:space-between;align-items:center;gap:10px;">
        <button class="btn bsm bo" onclick="markAllNotificationsRead()">{{ icon('check', '0.9em') }} قراءة الكل</button>
        <a href="/notifications" style="color:var(--accent-l);text-decoration:none;font-size:.8rem;font-weight:700;display:inline-flex;align-items:center;gap:5px;">عرض الكل {{ icon('chevron_left', '1em') }}</a>
    </div>
    {% endif %}
</div>

<div class="popup-notification-container" id="popupNotificationContainer"></div>

<main class="container" style="padding-top:16px;padding-bottom:30px">{% block content %}{% endblock %}</main>

{% if active_offers and active_offers|length > 0 and show_bottom_offers %}
<div class="bottom-offers-section">
    <h2 class="bottom-offers-title">{{ icon('tag', '1.5em') }} العروض المتوفرة</h2>
    <div class="bottom-offers-grid">
        {% for offer in active_offers %}
        <a href="/product/{{ offer.product_id }}" class="bottom-offer-card">
            <div class="bottom-offer-badge">خصم {{ offer.discount_percentage }}%</div>
            <div class="bottom-offer-img">
                {% if offer.image_path %}<img src="/images/{{ offer.image_path }}" alt="{{ offer.product_name }}">
                {% elif offer.image_url %}<img src="{{ offer.image_url }}" alt="{{ offer.product_name }}" onerror="this.style.display='none'">
                {% else %}{{ icon('package', '2em') }}{% endif %}
            </div>
            <div class="bottom-offer-name">{{ offer.product_name }}</div>
            <div class="bottom-offer-prices">
                <span class="bottom-offer-new-price">{{ format_price(offer.offer_price) }}</span>
                <span class="bottom-offer-old-price">{{ format_price(offer.original_price) }}</span>
                <span class="bottom-offer-discount">وفّر {{ format_price(offer.original_price - offer.offer_price) }}</span>
            </div>
        </a>
        {% endfor %}
    </div>
</div>
{% endif %}

<nav class="bottom-nav">
    <a href="/" class="bottom-nav-item {% if active_page == 'home' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('home', '1.2em') }}</div>
        <span>الرئيسية</span>
    </a>
    <a href="/categories" class="bottom-nav-item {% if active_page == 'categories' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('category', '1.2em') }}</div>
        <span>الأقسام</span>
    </a>
    {% if logged_in %}
    <a href="/orders" class="bottom-nav-item {% if active_page == 'orders' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('orders', '1.2em') }}</div>
        <span>طلباتي</span>
    </a>
    <a href="/wallet" class="bottom-nav-item {% if active_page == 'wallet' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('wallet', '1.2em') }}</div>
        <span>المحفظة</span>
    </a>
    <a href="/profile" class="bottom-nav-item {% if active_page == 'profile' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('user', '1.2em') }}</div>
        <span>حسابي</span>
    </a>
    {% else %}
    <a href="/gifts" class="bottom-nav-item {% if active_page == 'gifts' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('gift', '1.2em') }}</div>
        <span>الهدايا</span>
    </a>
    <a href="/offers" class="bottom-nav-item {% if active_page == 'offers' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('tag', '1.2em') }}</div>
        <span>العروض</span>
    </a>
    <a href="/support/chat" class="bottom-nav-item {% if active_page == 'support' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('support', '1.2em') }}</div>
        <span>الدعم</span>
    </a>
    <a href="/menu" class="bottom-nav-item {% if active_page == 'menu' %}active{% endif %}">
        <div class="bottom-nav-icon">{{ icon('menu', '1.2em') }}</div>
        <span>القائمة</span>
    </a>
    {% endif %}
</nav>

<footer class="footer">
    <div class="footer-links">
        <a href="/" class="footer-link">{{ icon('home', '1em') }} الرئيسية</a>
        <a href="/categories" class="footer-link">{{ icon('category', '1em') }} الأقسام</a>
        <a href="/offers" class="footer-link">{{ icon('tag', '1em') }} العروض</a>
        <a href="/faq" class="footer-link">{{ icon('faq', '1em') }} الأسئلة الشائعة</a>
        <a href="/support/chat" class="footer-link">{{ icon('support', '1em') }} الدعم المباشر</a>
        <a href="/blog" class="footer-link">{{ icon('blog', '1em') }} المدونة</a>
        <a href="/menu" class="footer-link">{{ icon('menu', '1em') }} القائمة الكاملة</a>
    </div>
    <p>{{ footer_text }}</p>
    {% if social_links %}
    <div class="social-links">
        {% if social_links.facebook %}<a href="{{ social_links.facebook }}" target="_blank" class="social-link fb" style="background:#1877f2">{{ icon('share', '1.2em') }}</a>{% endif %}
        {% if social_links.instagram %}<a href="{{ social_links.instagram }}" target="_blank" class="social-link ig" style="background:linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)">{{ icon('image', '1.2em') }}</a>{% endif %}
        {% if social_links.telegram %}<a href="{{ social_links.telegram }}" target="_blank" class="social-link tg" style="background:#0088cc">{{ icon('telegram', '1.2em') }}</a>{% endif %}
        {% if social_links.whatsapp %}<a href="{{ social_links.whatsapp }}" target="_blank" class="social-link wa" style="background:#25d366">{{ icon('whatsapp', '1.2em') }}</a>{% endif %}
    </div>
    {% endif %}
</footer>

<div class="toast-c" id="toasts"></div>
<div class="modal-overlay" id="genericModal"><div class="modal-box"><div class="modal-icon" id="modalIcon">{{ icon('clock', '2.4em') }}</div><div class="modal-title" id="modalTitle">جاري المعالجة</div><div class="modal-msg" id="modalMessage">يرجى الانتظار...</div><div class="modal-actions" id="modalActions"><button class="btn bp" onclick="closeModal()">حسناً</button></div></div></div>

<div class="quick-view-modal" id="quickViewModal">
    <div class="quick-view-box">
        <button class="quick-view-close" id="btnCloseQuickView">{{ icon('close', '1.5em') }}</button>
        <div class="quick-view-img" id="qvImgContainer">
            <img id="qvImg" src="" alt="Product Image">
        </div>
        <div class="quick-view-name" id="qvName"></div>
        <div class="quick-view-price" id="qvPrice"></div>
        <div class="quick-view-desc" id="qvDesc"></div>
        <button class="btn bp bbl" id="qvBuyBtn">{{ icon('cart', '1em') }} عرض المنتج</button>
    </div>
</div>

<div class="image-preview-modal" id="imagePreviewModal"><button class="image-preview-close" id="btnCloseImagePreview">{{ icon('close', '1.5em') }}</button><img id="imagePreviewImg" src="" alt="preview"></div>

<a href="/support/chat" class="wa-support-fab" title="محادثة مباشرة" style="text-decoration:none">{{ icon('whatsapp', '1.5em') }}</a>
<button class="back-to-top" id="backToTop">{{ icon('arrow_up', '1.2em') }}</button>
""" + LAZY_LOAD_SCRIPT + GLOBAL_JS_SCRIPT + WELCOME_POPUP_HTML + AD_SLIDESHOW_SCRIPT + """
</body></html>"""

MENU_PAGE_TMPL = """{% extends "base" %}{% block content %}
<div class="menu-page-container">
    <div class="menu-header">
        <a href="/" class="menu-back-btn">{{ icon('arrow_back', '1.5em') }}</a>
        <h1 class="menu-title">القائمة الرئيسية</h1>
    </div>
    
    {% if logged_in %}
    <div class="menu-profile-card">
        <div class="menu-avatar">
            {% if user_avatar %}<img src="/images/{{ user_avatar }}" alt="avatar">
            {% else %}{{ icon('user', '3em') }}{% endif %}
        </div>
        <div class="menu-profile-info">
            <div class="menu-username">{{ session_username }}</div>
            <div class="menu-userid">#{{ session_user_id }}</div>
            {% if is_vip %}<div class="vip-badge-menu">{{ icon('diamond', '1em') }} VIP {{ vip_level_name }}</div>{% endif %}
        </div>
        <div class="menu-balance">{{ balance }}</div>
    </div>
    {% else %}
    <div class="menu-guest-card">
        <div class="menu-avatar-guest">{{ icon('user', '3em') }}</div>
        <div class="menu-guest-text">
            <div style="font-weight:800;font-size:1.1rem">زائر</div>
            <div style="font-size:.8rem;color:var(--t3)">سجل الدخول للوصول لكل المزايا</div>
        </div>
        <a href="/login" class="btn bp bsm">{{ icon('logout', '1em') }} دخول</a>
    </div>
    {% endif %}
    
    <div class="menu-section">
        <div class="menu-section-title">المتجر</div>
        <a href="/" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('home', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الرئيسية</div>
                <div class="menu-item-desc">صفحة المتجر الرئيسية</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/categories" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('category', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الأقسام</div>
                <div class="menu-item-desc">تصفح جميع أقسام المنتجات</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/offers" class="menu-item-row">
            <div class="menu-item-icon" style="background:linear-gradient(135deg,#f59e0b,#ec4899)">{{ icon('tag', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">العروض الخاصة</div>
                <div class="menu-item-desc">تخفيضات حصرية لفترة محدودة</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/gifts" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('gift', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">أكواد الهدايا</div>
                <div class="menu-item-desc">تصفح بطاقات الهدايا المتاحة</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/wheel" class="menu-item-row">
            <div class="menu-item-icon" style="background:linear-gradient(135deg,#f59e0b,#7c3aed)">{{ icon('wheel', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">عجلة الحظ</div>
                <div class="menu-item-desc">أدر العجلة واربح الجوائز</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
    </div>
    
    {% if logged_in %}
    <div class="menu-section">
        <div class="menu-section-title">حسابي</div>
        <a href="/profile" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('user', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الصفحة الشخصية</div>
                <div class="menu-item-desc">إعدادات الحساب والمعلومات</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/wallet" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('wallet', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">المحفظة</div>
                <div class="menu-item-desc">رصيدك ومعاملاتك المالية</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/orders" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('orders', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">طلباتي</div>
                <div class="menu-item-desc">سجل طلباتك السابقة</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/favorites" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('heart', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">المفضلة</div>
                <div class="menu-item-desc">المنتجات التي أضفتها للمفضلة</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/compare" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('compare', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">المقارنة</div>
                <div class="menu-item-desc">قارن بين المنتجات</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/notifications" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('bell', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الإشعارات</div>
                <div class="menu-item-desc">{% if notifications_count > 0 %}لديك {{ notifications_count }} إشعار جديد{% else %}لا توجد إشعارات جديدة{% endif %}</div>
            </div>
            {% if notifications_count > 0 %}<span class="menu-badge">{{ notifications_count }}</span>{% endif %}
        </a>
        <a href="/achievements" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('medal', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الإنجازات</div>
                <div class="menu-item-desc">إنجازاتك ومكافآتك</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/contests" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('trophy', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">المسابقات</div>
                <div class="menu-item-desc">شارك واربح الجوائز</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
    </div>
    {% endif %}
    
    <div class="menu-section">
        <div class="menu-section-title">الدعم والمساعدة</div>
        <a href="/support/chat" class="menu-item-row">
            <div class="menu-item-icon" style="background:linear-gradient(135deg,#25d366,#128c7e)">{{ icon('support', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الدعم المباشر</div>
                <div class="menu-item-desc">محادثة مباشرة مع فريق الدعم</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/support" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('ticket', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">تذاكر الدعم</div>
                <div class="menu-item-desc">أنشئ تذكرة وتابع حالتها</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/faq" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('faq', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">الأسئلة الشائعة</div>
                <div class="menu-item-desc">إجابات لأكثر الأسئلة شيوعاً</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
        <a href="/blog" class="menu-item-row">
            <div class="menu-item-icon">{{ icon('blog', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">المدونة</div>
                <div class="menu-item-desc">مقالات وأخبار المتجر</div>
            </div>
            {{ icon('chevron_left', '1.2em') }}
        </a>
    </div>
    
    <div class="menu-section">
        <div class="menu-section-title">تواصل معنا</div>
        <a href="{{ support_whatsapp }}" target="_blank" class="menu-item-row">
            <div class="menu-item-icon" style="background:linear-gradient(135deg,#25d366,#128c7e)">{{ icon('whatsapp', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">واتساب</div>
                <div class="menu-item-desc">تواصل مباشر عبر واتساب</div>
            </div>
            {{ icon('external_link', '1.2em') }}
        </a>
        <a href="{{ support_telegram }}" target="_blank" class="menu-item-row">
            <div class="menu-item-icon" style="background:linear-gradient(135deg,#0088cc,#229ED9)">{{ icon('telegram', '1.4em') }}</div>
            <div class="menu-item-content">
                <div class="menu-item-name">تلجرام</div>
                <div class="menu-item-desc">انضم لقناتنا على تلجرام</div>
            </div>
            {{ icon('external_link', '1.2em') }}
        </a>
    </div>
    
    <div class="menu-footer">
        <p>{{ footer_text }}</p>
    </div>
</div>
{% endblock %}"""

SUPPORT_CHAT_PAGE_TMPL = """{% extends "base" %}{% block content %}
<div class="wa-full-page">
    <div class="wa-full-header">
        <a href="/" class="wa-back-btn">{{ icon('arrow_back', '1.4em') }}</a>
        <div class="wa-header-avatar">
            {% if store_logo %}<img src="/images/{{ store_logo }}" alt="support">
            {% else %}<span style="font-weight:900;color:#075e54;font-size:1.3rem">M</span>{% endif %}
        </div>
        <div class="wa-header-info">
            <div class="wa-header-name">الدعم الفني</div>
            <div class="wa-header-status">
                <span class="wa-status-dot"></span>
                <span id="waStatusText">متصل الآن</span>
            </div>
        </div>
        <div class="wa-header-actions">
            <button class="wa-header-btn" onclick="startVoiceCall()" title="مكالمة">{{ icon('phone', '1.2em') }}</button>
            <a href="{{ support_whatsapp }}" target="_blank" class="wa-header-btn" title="واتساب">{{ icon('whatsapp', '1.2em') }}</a>
            <button class="wa-header-btn" id="waMenuBtn" title="المزيد">{{ icon('more_vertical', '1.2em') }}</button>
        </div>
    </div>
    
    <div class="wa-full-body" id="waFullBody">
        <div class="wa-date-separator">اليوم</div>
        <div class="wa-welcome-msg">
            <div class="wa-welcome-icon">{{ icon('headphones', '2em') }}</div>
            <div class="wa-welcome-text">مرحباً بك في الدعم الفني لـ {{ store_name }}!</div>
            <div class="wa-welcome-sub">نحن هنا لمساعدتك. أرسل رسالتك وسيتم الرد عليك في أقرب وقت ممكن.</div>
        </div>
        <div id="waMessagesContainer"></div>
    </div>
    
    <div class="wa-full-input-area">
        <button class="wa-input-btn" id="waEmojiBtn" title="إيموجي">{{ icon('smile', '1.4em') }}</button>
        <div class="wa-input-wrap">
            <input type="text" id="waMessageInput" placeholder="اكتب رسالة..." autocomplete="off">
            <button class="wa-input-btn-inner" id="waAttachBtn" title="إرفاق ملف">
                {{ icon('attach', '1.2em') }}
                <input type="file" id="waFileInput" accept="image/*" style="display:none">
            </button>
        </div>
        <button class="wa-send-btn" id="waSendBtn" title="إرسال">{{ icon('send', '1.4em') }}</button>
    </div>
    
    <div class="wa-emoji-picker" id="waEmojiPicker" style="display:none">
        <div class="wa-emoji-grid">
            <span onclick="insertEmoji('😊')">😊</span>
            <span onclick="insertEmoji('😂')">😂</span>
            <span onclick="insertEmoji('❤️')">❤️</span>
            <span onclick="insertEmoji('👍')">👍</span>
            <span onclick="insertEmoji('🙏')">🙏</span>
            <span onclick="insertEmoji('🔥')">🔥</span>
            <span onclick="insertEmoji('⭐')">⭐</span>
            <span onclick="insertEmoji('🎉')">🎉</span>
            <span onclick="insertEmoji('🎁')">🎁</span>
            <span onclick="insertEmoji('✨')">✨</span>
            <span onclick="insertEmoji('💪')">💪</span>
            <span onclick="insertEmoji('🤝')">🤝</span>
            <span onclick="insertEmoji('📦')">📦</span>
            <span onclick="insertEmoji('💰')">💰</span>
            <span onclick="insertEmoji('🛒')">🛒</span>
            <span onclick="insertEmoji('⚡')">⚡</span>
        </div>
    </div>
</div>
<script>
var waLoggedIn = {% if logged_in %}true{% else %}false{% endif %};

function escapeHtml(t){var d=document.createElement('div');d.textContent=t;return d.innerHTML;}

function addMessage(text, isSent, isImage, time){
    var c=document.getElementById('waMessagesContainer');
    if(!c) return;
    var div=document.createElement('div');
    div.className='wa-msg '+(isSent?'sent':'received');
    if(isImage){
        div.innerHTML='<img src="'+text+'" onclick="openImagePreview(this.src)">';
    } else {
        div.innerHTML=escapeHtml(text);
    }
    var timeDiv=document.createElement('div');
    timeDiv.className='wa-msg-time';
    var timeStr = time || new Date().toLocaleTimeString('ar-EG',{hour:'2-digit',minute:'2-digit'});
    timeDiv.innerHTML=timeStr+(isSent?'<span class="wa-msg-status">{{ icon("check", "0.9em")|safe }}</span>':'');
    div.appendChild(timeDiv);
    c.appendChild(div);
    var body=document.getElementById('waFullBody');
    if(body) body.scrollTop=body.scrollHeight;
}

function showGuestAlert(){
    var c=document.getElementById('waMessagesContainer');
    if(!c) return;
    var div=document.createElement('div');
    div.className='wa-msg wa-msg-guest-alert';
    div.innerHTML='{{ icon("lock", "1em")|safe }} أنت تستخدم الدعم كزائر. لتتمكن من إرسال الرسائل والصور، يرجى <a href="/login" style="color:#075e54;font-weight:800">تسجيل الدخول</a>';
    c.appendChild(div);
    var body=document.getElementById('waFullBody');
    if(body) body.scrollTop=body.scrollHeight;
}

function loadWaMessages(){
    fetch('/api/chat/messages')
        .then(function(r){return r.json();})
        .then(function(d){
            var c=document.getElementById('waMessagesContainer');
            if(!c) return;
            c.innerHTML='';
            if(d.redirect){
                showGuestAlert();
                return;
            }
            if(d.messages && d.messages.length>0){
                d.messages.forEach(function(m){
                    var time = m.created_at || '';
                    if(m.image_path){
                        addMessage('/images/'+m.image_path, !m.is_from_admin, true, time);
                    } else {
                        addMessage(m.message, !m.is_from_admin, false, time);
                    }
                });
            }
        })
        .catch(function(){
            if(!waLoggedIn) showGuestAlert();
        });
}

function sendWaMessage(){
    var input=document.getElementById('waMessageInput');
    if(!input) return;
    var msg=input.value.trim();
    if(!msg) return;
    
    if(!waLoggedIn){
        showGuestAlert();
        return;
    }
    
    input.value='';
    addMessage(msg, true);
    
    fetch('/api/chat/send',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message:msg})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        if(d.success){
            setTimeout(loadWaMessages, 1000);
        } else if(d.redirect){
            showGuestAlert();
        }
    })
    .catch(function(){});
}

function sendWaFile(){
    var f=document.getElementById('waFileInput');
    if(!f || !f.files[0]) return;
    
    if(!waLoggedIn){
        showGuestAlert();
        f.value='';
        return;
    }
    
    var file=f.files[0];
    var fd=new FormData();
    fd.append('image',file);
    
    var reader=new FileReader();
    reader.onload=function(e){addMessage(e.target.result, true, true);};
    reader.readAsDataURL(file);
    
    fetch('/api/chat/send-image',{method:'POST',body:fd})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.success){
                setTimeout(loadWaMessages, 1500);
            } else if(d.redirect){
                showGuestAlert();
            }
        });
    f.value='';
}

function insertEmoji(e){
    var input=document.getElementById('waMessageInput');
    if(input){
        input.value += e;
        input.focus();
    }
}

function startVoiceCall(){
    showModal('{{ icon("phone","2em")|safe }}', 'مكالمة صوتية', 'ميزة المكالمات الصوتية قيد التطوير. حالياً يمكنك التواصل معنا عبر واتساب.', false);
}

document.addEventListener('DOMContentLoaded', function(){
    var sendBtn=document.getElementById('waSendBtn');
    var input=document.getElementById('waMessageInput');
    var attachBtn=document.getElementById('waAttachBtn');
    var fileInput=document.getElementById('waFileInput');
    var emojiBtn=document.getElementById('waEmojiBtn');
    var emojiPicker=document.getElementById('waEmojiPicker');
    
    if(sendBtn) sendBtn.addEventListener('click', sendWaMessage);
    if(input){
        input.addEventListener('keypress', function(e){
            if(e.key==='Enter'){e.preventDefault();sendWaMessage();}
        });
    }
    if(attachBtn && fileInput){
        attachBtn.addEventListener('click', function(){fileInput.click();});
    }
    if(fileInput){
        fileInput.addEventListener('change', sendWaFile);
    }
    if(emojiBtn && emojiPicker){
        emojiBtn.addEventListener('click', function(e){
            e.stopPropagation();
            if(emojiPicker.style.display==='none' || !emojiPicker.style.display){
                emojiPicker.style.display='block';
            } else {
                emojiPicker.style.display='none';
            }
        });
        document.addEventListener('click', function(e){
            if(!emojiPicker.contains(e.target) && e.target!==emojiBtn){
                emojiPicker.style.display='none';
            }
        });
    }
    
    loadWaMessages();
    
    setInterval(function(){
        if(waLoggedIn) loadWaMessages();
    }, 15000);
});
</script>
{% endblock %}"""

HOME_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('category', '1.25em') }} الأقسام الرئيسية</h1>
<div style="max-width:1200px;margin:0 auto">
{% if categories %}
<div class="cat-circular-grid">
{% for cat in categories %}
<a href="/category/{{ cat.id }}" class="cat-circular-item">
<div class="cat-circular-icon">
{% if cat.image_path %}<img src="/images/{{ cat.image_path }}" alt="{{ cat.name }}">
{% elif cat.image_url %}<img src="{{ cat.image_url }}" alt="{{ cat.name }}" onerror="this.style.display='none'">
{% else %}<div class="cat-emoji">{{ icon('package', '2.2em') }}</div>{% endif %}
</div>
<div class="cat-circular-name">{{ cat.name }}</div>
<div class="cat-circular-count">{{ icon('package', '0.9em') }} {{ cat.product_count }}</div>
</a>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('category', '3em') }}</div><div class="empty-text">لا توجد أقسام بعد</div></div>
{% endif %}
</div>

{% if best_sellers and best_sellers|length > 0 %}
<h1 class="section-title" style="margin-top:30px">{{ icon('fire', '1.25em') }} الأكثر مبيعاً</h1>
<div style="max-width:1200px;margin:0 auto">
<div class="grid g5">
{% for prod in best_sellers %}
<div class="pc ripple-container" onclick="window.location.href='/product/{{ prod.id }}'">
<div class="pc-fav-card" onclick="toggleFavCard(event, this, {{ prod.id }});">{{ icon('heart', '0.85em') }}</div>
<div class="pc-quick-view" onclick="quickView(event, {{ prod.id }});">{{ icon('eye', '0.75em') }}</div>
<div class="pc-img">
{% if prod.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ prod.image_path }}" alt="{{ prod.name }}" class="lazy-img">
{% elif prod.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ prod.image_url }}" alt="{{ prod.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
{% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '2em') }}</div>{% endif %}
</div>
<div class="pc-body">
<div class="pc-name">{{ prod.name }}</div>
<div class="pc-price-row"><span class="pc-price">{{ format_price(prod.sell_price) }}</span></div>
</div>
</div>
{% endfor %}
</div>
</div>
{% endif %}

{% if new_arrivals and new_arrivals|length > 0 %}
<h1 class="section-title" style="margin-top:30px">{{ icon('star', '1.25em') }} وصل حديثاً</h1>
<div style="max-width:1200px;margin:0 auto">
<div class="grid g5">
{% for prod in new_arrivals %}
<div class="pc ripple-container" onclick="window.location.href='/product/{{ prod.id }}'">
<div class="pc-new-badge">جديد</div>
<div class="pc-fav-card" onclick="toggleFavCard(event, this, {{ prod.id }});">{{ icon('heart', '0.85em') }}</div>
<div class="pc-quick-view" onclick="quickView(event, {{ prod.id }});">{{ icon('eye', '0.75em') }}</div>
<div class="pc-img">
{% if prod.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ prod.image_path }}" alt="{{ prod.name }}" class="lazy-img">
{% elif prod.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ prod.image_url }}" alt="{{ prod.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
{% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '2em') }}</div>{% endif %}
</div>
<div class="pc-body">
<div class="pc-name">{{ prod.name }}</div>
<div class="pc-price-row"><span class="pc-price">{{ format_price(prod.sell_price) }}</span></div>
</div>
</div>
{% endfor %}
</div>
</div>
{% endif %}
{% endblock %}"""

PRODUCT_TMPL = """{% extends "base" %}{% block content %}
<div class="breadcrumb">
    <a href="/">{{ icon('home', '1em') }} الرئيسية</a>
    <span class="breadcrumb-separator">/</span>
    {% if product.cat_name %}<a href="/category/{{ product.category_id }}">{{ product.cat_name }}</a><span class="breadcrumb-separator">/</span>{% endif %}
    <span>{{ product.name }}</span>
</div>
<div class="product-detail">
    <div class="product-images-gallery">
        <div class="product-image-main" id="mainImage">
            {% if product.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ product.image_path }}" alt="{{ product.name }}" id="mainImg" class="lazy-img">
            {% elif product.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ product.image_url }}" alt="{{ product.name }}" id="mainImg" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
            {% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '3em') }}</div>{% endif %}
        </div>
        {% if all_images and all_images|length > 1 %}
        <div class="product-thumbnails">
            {% for img in all_images %}
            <div class="product-thumb {% if loop.first %}active{% endif %}" onclick="changeMainImage(this,'{{ img.url }}')"><div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ img.url }}" alt="" class="lazy-img"></div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    <div>
        <h1 class="product-title-display">{{ product.name }}</h1>

        <div class="product-badges">
            {% if active_offer %}
            <span class="product-badge offer">{{ icon('tag', '1em') }} عرض خاص: خصم {{ active_offer.discount_percentage }}%</span>
            {% elif product.is_featured == 1 %}<span class="product-badge featured">{{ icon('star', '1em') }} منتج مميز</span>{% endif %}
            {% if product.sales_count > 10 %}<span class="product-badge hot">{{ icon('fire', '1em') }} الأكثر مبيعاً</span>{% endif %}
            {% if product.views > 50 %}<span class="product-badge new">{{ icon('eye', '1em') }} شائع</span>{% endif %}
            {% if product.stock_quantity == 0 %}
            <span class="stock-indicator stock-out">{{ icon('x_circle', '1em') }} غير متوفر حالياً</span>
            {% else %}
            <span class="stock-indicator stock-in">{{ icon('check_circle', '1em') }} متوفر</span>
            {% endif %}
        </div>

        <div class="product-tabs">
            <div class="product-tab active" data-tab="description">{{ icon('info', '1em') }} الوصف</div>
            <div class="product-tab" data-tab="specs">{{ icon('grid', '1em') }} التفاصيل</div>
            <div class="product-tab" data-tab="reviews">{{ icon('star', '1em') }} التقييمات</div>
        </div>

        <div id="tab-description" class="product-tab-content active">
            {% if product.description %}<p style="color:var(--t2);margin-bottom:12px;line-height:1.8">{{ product.description }}</p>{% endif %}
            {% if instructions %}<div class="instructions-box"><div class="instructions-title">{{ icon('info', '1em') }} تعليمات الشراء</div><div class="instructions-content">{{ instructions }}</div></div>{% endif %}
        </div>

        <div id="tab-specs" class="product-tab-content">
            <div class="card" style="margin-bottom:16px;padding:12px;">
                <h3 style="font-weight:800; margin-bottom:10px; color:var(--accent-l);">{{ icon('grid', '1em') }} تفاصيل البيع</h3>
                <div class="sell-info-box">
                    <div class="sell-info-item"><div class="sell-info-label">الحد الأدنى</div><div class="sell-info-value">{{ product.min_quantity or 1 }}</div></div>
                    <div class="sell-info-item"><div class="sell-info-label">الحد الأقصى</div><div class="sell-info-value">{% if product.max_quantity > 0 %}{{ product.max_quantity }}{% else %}غير محدود{% endif %}</div></div>
                    <div class="sell-info-item"><div class="sell-info-label">نوع المنتج</div><div class="sell-info-value">{% if product.product_type == 'digital' %}رقمي{% else %}مادي{% endif %}</div></div>
                </div>
            </div>
        </div>

        <div id="tab-reviews" class="product-tab-content">
            <div class="rating-display">
                <span class="rating-stars">{{ icon('star', '1.2em') }}{{ icon('star', '1.2em') }}{{ icon('star', '1.2em') }}{{ icon('star', '1.2em') }}{{ icon('star', '1.2em') }}</span>
                <span class="rating-text">{{ rating.avg or '0.0' }} ({{ rating.count }} تقييم)</span>
            </div>
            {% if reviews %}
            <div class="reviews-grid">
                {% for r in reviews %}
                <div class="review-card">
                    <div class="review-header">
                        <div class="review-avatar">{{ r.username[0] }}</div>
                        <div>
                            <div class="review-username">{{ r.username }}</div>
                            <div class="review-stars">{% for i in range(5) %}{% if i < r.rating %}★{% else %}☆{% endif %}{% endfor %}</div>
                        </div>
                    </div>
                    <div class="review-comment">{{ r.comment }}</div>
                    <div class="review-date">{{ r.created_at[:10] }}</div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty"><div class="empty-icon">{{ icon('star', '3em') }}</div><div class="empty-text">لا توجد تقييمات بعد</div></div>
            {% endif %}
        </div>

        {% if product.stock_quantity == 0 %}
        <div class="out-of-stock-alert">{{ icon('warning', '1em') }} هذا المنتج غير متوفر حالياً، لا يمكن إتمام عملية الشراء.</div>
        {% else %}
        <form id="buyForm" novalidate onsubmit="return false;">

            {% if required_fields_list and required_fields_list|length > 0 %}
            <div class="required-fields-box">
                <div class="required-fields-title">{{ icon('edit', '1em') }} معلومات الشراء المطلوبة</div>
                {% for field in required_fields_list %}
                <div class="field-group">
                    <label class="field-label">{{ field.label }}{% if field.required %}<span class="req-star">*</span>{% endif %}</label>
                    {% if field.type == 'select' and field.options %}
                    <select class="select-styled" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} onchange="updateTotal()">
                        <option value="">اختر {{ field.label }}</option>
                        {% for opt in field.options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}
                    </select>
                    {% elif field.type == 'textarea' %}
                    <textarea class="field-input" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}" rows="3"></textarea>
                    {% elif field.type == 'number' %}
                    <input class="field-input" type="number" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}">
                    {% elif field.type == 'email' %}
                    <input class="field-input" type="email" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}">
                    {% elif field.type == 'tel' %}
                    <input class="field-input" type="tel" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}">
                    {% elif field.type == 'url' %}
                    <input class="field-input" type="url" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}">
                    {% else %}
                    <input class="field-input" name="custom_field_{{ field.name }}" id="custom_field_{{ field.name }}" {% if field.required %}data-required="1"{% endif %} placeholder="{{ field.placeholder or 'أدخل ' + field.label }}">
                    {% endif %}
                    {% if field.hint %}<div class="field-hint">{{ icon('info', '0.9em') }} {{ field.hint }}</div>{% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if qty_options_parsed and qty_options_parsed|length > 0 %}
            <div class="options-box-enhanced" id="optionsBox">
                <div class="options-title-enhanced">
                    <span>{{ icon('tag', '1.4em') }}</span>
                    <span>اختر الفئة / الخيار المناسب</span>
                    <span style="color:var(--err);font-weight:900">*</span>
                    <span style="font-size:.7rem;color:var(--t3);margin-right:auto">(إلزامي)</span>
                </div>
                
                <select class="select-styled-wide" id="optSelect" name="selected_option_index" 
                        onchange="updateOptInfo()" data-required="1">
                    <option value="">-- اختر خياراً من القائمة --</option>
                    {% for opt in qty_options_parsed %}
                    <option value="{{ loop.index0 }}" 
                            data-price="{{ opt.price or product.sell_price or 0 }}" 
                            data-qty="{{ opt.qty or '' }}" 
                            data-api-id="{{ opt.api_id or '' }}" 
                            data-label="{{ opt.label }}">
                        {{ opt.label }}{% if opt.price %} — {{ format_price(opt.price) }}{% endif %}{% if opt.qty %} — ×{{ opt.qty }}{% endif %}
                    </option>
                    {% endfor %}
                </select>
                
                <div class="option-info-box" id="optInfoBox" style="display:none;">
                    <div style="display:flex;flex-direction:column;gap:6px;width:100%">
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="font-size:.82rem;color:var(--t2);font-weight:700">{{ icon('money', '1em') }} سعر الخيار:</span>
                            <span class="option-price-display" id="optPriceDisplay">0</span>
                        </div>
                    </div>
                </div>
                
                <div id="optError" class="dropdown-error" style="display:none;">
                    {{ icon('warning', '1em') }} يجب اختيار خيار من القائمة المنسدلة قبل الشراء
                </div>
            </div>
            {% endif %}

            {% if product.max_quantity and product.max_quantity > 1 %}
            <div class="fg">
                <label class="fl">{{ icon('grid', '1em') }} الكمية</label>
                <div class="qty-selector">
                    <button type="button" class="qty-btn" onclick="changeQty(-1)">{{ icon('minus', '1.2em') }}</button>
                    <input type="number" class="qty-input" name="quantity" id="qtyInput" value="{{ product.min_quantity or 1 }}" min="{{ product.min_quantity or 1 }}" max="{{ product.max_quantity or 999999 }}" step="{{ product.step_quantity or 1 }}" oninput="onQtyInput()" onblur="validateQty()">
                    <button type="button" class="qty-btn" onclick="changeQty(1)">{{ icon('plus', '1.2em') }}</button>
                </div>
                <div style="font-size:.72rem;color:var(--t3);margin-top:4px;text-align:center">الحد الأدنى: {{ product.min_quantity or 1 }} | الأقصى: {{ product.max_quantity or 'غير محدود' }} | الخطوة: {{ product.step_quantity or 1 }}</div>
            </div>
            {% else %}
            <input type="hidden" name="quantity" value="1" id="qtyInput">
            {% endif %}

        </form>

        <div class="purchase-summary-box">
            <div class="purchase-total-row">
                <span class="purchase-total-label">{{ icon('money', '1em') }} السعر الإجمالي</span>
                <span class="purchase-total-value" id="totalPrice">{% if active_offer %}{{ format_price(active_offer.offer_price) }}{% else %}{{ format_price(product.sell_price or 0) }}{% endif %}</span>
            </div>
            {% if logged_in %}
            <button type="button" class="purchase-btn btn-shimmer" id="mainPurchaseBtn">{{ icon('cart', '1em') }} تأكيد الشراء</button>
            {% else %}
            <div class="guest-login-prompt">
                <div class="guest-login-prompt-icon">{{ icon('lock', '3em') }}</div>
                <div class="guest-login-prompt-title">يجب تسجيل الدخول للشراء</div>
                <div class="guest-login-prompt-text">يمكنك تصفح المنتج ومشاهدة التفاصيل، ولكن لإتمام عملية الشراء يجب الدخول عبر تيليجرام.</div>
                <a href="/login" class="guest-login-prompt-btn">{{ icon('rocket', '1em') }} الدخول للشراء</a>
            </div>
            {% endif %}
        </div>

        <div class="share-buttons">
            <a href="https://wa.me/?text={{ product.name }} - {{ format_price(product.sell_price) }}" target="_blank" class="share-btn wa">{{ icon('whatsapp', '1em') }} واتساب</a>
            <a href="https://t.me/share/url?url={{ WEB_URL }}/product/{{ product.id }}&text={{ product.name }}" target="_blank" class="share-btn tg">{{ icon('telegram', '1em') }} تلجرام</a>
            <button class="share-btn copy" onclick="copyToClipboard('{{ WEB_URL }}/product/{{ product.id }}');showModal('{{ icon('copy','2em')|safe }}','تم النسخ','تم نسخ رابط المنتج!')">{{ icon('copy', '1em') }} نسخ الرابط</button>
        </div>

<script>
        (function(){
            "use strict";
            
            var CURRENCY = {{ currency_symbol|tojson|safe }};
            var PRODUCT_ID = {{ product.id }};
            {% if active_offer %}
            var unitPrice = {{ active_offer.offer_price or 0 }};
            {% else %}
            var unitPrice = {{ product.sell_price or 0 }};
            {% endif %}
            var minQty = {{ product.min_quantity or 1 }};
            var maxQty = {% if product.max_quantity and product.max_quantity > 0 %}{{ product.max_quantity }}{% else %}999999{% endif %};
            var stepQty = {{ product.step_quantity or 1 }};
            var useOptions = {% if qty_options_parsed and qty_options_parsed|length > 0 %}true{% else %}false{% endif %};
            var isSubmitting = false;
            
            function formatPrice(p){
                var num = parseFloat(p || 0);
                if(isNaN(num)) num = 0;
                if(num >= 1000){
                    return num.toLocaleString('ar-EG',{minimumFractionDigits:0, maximumFractionDigits:0}) + ' ' + CURRENCY;
                }
                return num.toLocaleString('ar-EG',{minimumFractionDigits:0, maximumFractionDigits:2}) + ' ' + CURRENCY;
            }
            
            function getUnitPrice(){
                var price = unitPrice;
                if(useOptions){
                    var select = document.getElementById('optSelect');
                    if(select && select.selectedIndex > 0){
                        var selectedOpt = select.options[select.selectedIndex];
                        var optPrice = parseFloat(selectedOpt.getAttribute('data-price'));
                        if(!isNaN(optPrice) && optPrice > 0){
                            price = optPrice;
                        }
                    }
                }
                return price;
            }
            
            function updateTotal(){
                var qty = 1;
                var qtyInput = document.getElementById('qtyInput');
                if(qtyInput){
                    var rawVal = (qtyInput.value || '').toString().trim();
                    if(rawVal === ''){ qty = minQty; } else {
                        qty = parseInt(rawVal);
                        if(isNaN(qty)) qty = minQty;
                        if(qty < minQty) qty = minQty;
                        if(maxQty > 0 && qty > maxQty) qty = maxQty;
                    }
                }
                var price = getUnitPrice();
                var total = price * qty;
                var totalEl = document.getElementById('totalPrice');
                if(totalEl){ totalEl.textContent = formatPrice(total); }
            }
            
            function updateOptInfo(){
                var select = document.getElementById('optSelect');
                var infoBox = document.getElementById('optInfoBox');
                var priceDisplay = document.getElementById('optPriceDisplay');
                var errBox = document.getElementById('optError');
                if(!select) return;
                if(errBox) errBox.style.display = 'none';
                if(select.selectedIndex > 0){
                    var selectedOpt = select.options[select.selectedIndex];
                    var optPrice = parseFloat(selectedOpt.getAttribute('data-price'));
                    if(infoBox && priceDisplay){
                        if(!isNaN(optPrice) && optPrice > 0){
                            priceDisplay.textContent = formatPrice(optPrice);
                            infoBox.style.display = 'flex';
                        } else {
                            infoBox.style.display = 'none';
                        }
                    }
                } else {
                    if(infoBox) infoBox.style.display = 'none';
                }
                updateTotal();
            }
            
            function changeQty(delta){
                var input = document.getElementById('qtyInput');
                if(!input) return;
                var current = parseInt(input.value) || minQty;
                var newVal = current + (delta * stepQty);
                if(newVal < minQty) newVal = minQty;
                if(maxQty > 0 && newVal > maxQty) newVal = maxQty;
                input.value = newVal;
                updateTotal();
            }
            
            function onQtyInput(){ updateTotal(); }
            
            function validateQty(){
                var input = document.getElementById('qtyInput');
                if(!input) return;
                var rawVal = (input.value || '').toString().trim();
                if(rawVal === ''){ input.value = minQty; } else {
                    var qty = parseInt(rawVal);
                    if(isNaN(qty) || qty < minQty){ input.value = minQty; }
                    else if(maxQty > 0 && qty > maxQty){ input.value = maxQty; }
                    else if(stepQty > 1 && (qty - minQty) % stepQty !== 0){
                        var remainder = (qty - minQty) % stepQty;
                        if(remainder < stepQty / 2){ qty = qty - remainder; } else { qty = qty + (stepQty - remainder); }
                        if(maxQty > 0 && qty > maxQty) qty = maxQty;
                        if(qty < minQty) qty = minQty;
                        input.value = qty;
                    }
                }
                updateTotal();
            }
            
            function changeMainImage(thumb, url){
                document.querySelectorAll('.product-thumb').forEach(function(t){ t.classList.remove('active'); });
                thumb.classList.add('active');
                var mainImg = document.getElementById('mainImg');
                if(mainImg){ mainImg.classList.remove('loaded'); mainImg.src = url; mainImg.onload = function(){ mainImg.classList.add('loaded'); }; }
            }
            
            async function submitBuyForm(prodId){
                if(isSubmitting) return false;
                
                var form = document.getElementById('buyForm');
                if(!form){
                    if(typeof showModal === 'function'){ showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'لم يتم العثور على نموذج الشراء.'); } else { alert('لم يتم العثور على نموذج الشراء.'); }
                    return false;
                }
                
                var btn = document.getElementById('mainPurchaseBtn');
                if(btn && btn.disabled) return false;
                
                var isValid = true;
                var firstInvalid = null;
                
                var requiredInputs = form.querySelectorAll('[data-required="1"]');
                requiredInputs.forEach(function(input){
                    var val = (input.value || '').toString().trim();
                    if(!val){
                        isValid = false;
                        if(!firstInvalid) firstInvalid = input;
                        input.style.borderColor = 'var(--err)';
                        input.style.boxShadow = '0 0 0 4px rgba(239,68,68,0.2)';
                        setTimeout(function(){ input.style.borderColor = ''; input.style.boxShadow = ''; }, 3000);
                    }
                });
                
                if(useOptions){
                    var select = document.getElementById('optSelect');
                    if(select && (select.selectedIndex <= 0 || !select.value)){
                        isValid = false;
                        if(!firstInvalid) firstInvalid = select;
                        select.style.borderColor = 'var(--err)';
                        select.style.boxShadow = '0 0 0 4px rgba(239,68,68,0.2)';
                        var errBox = document.getElementById('optError');
                        if(errBox){ errBox.style.display = 'block'; errBox.scrollIntoView({behavior:'smooth', block:'center'}); }
                        setTimeout(function(){ select.style.borderColor = ''; select.style.boxShadow = ''; }, 3000);
                        if(typeof showModal === 'function'){ showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', 'يرجى اختيار خيار من القائمة المنسدلة أولاً قبل تأكيد الشراء.'); } else { alert('يرجي اختيار خيار من القائمة المنسدلة أولاً قبل تأكيد الشراء.'); }
                        return false;
                    }
                }
                
                if(!isValid){
                    if(typeof showModal === 'function'){ showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', 'يرجى ملء جميع الحقول المطلوبة.'); } else { alert('يرجى ملء جميع الحقول المطلوبة.'); }
                    if(firstInvalid) firstInvalid.scrollIntoView({behavior:'smooth', block:'center'});
                    return false;
                }
                
                isSubmitting = true;
                if(btn){ btn.disabled = true; btn.style.opacity = '0.7'; btn.innerHTML = '{{ icon("clock","1em")|safe }} جاري المعالجة...'; }
                
                if(typeof showModal === 'function'){ showModal('{{ icon("clock","2.4em")|safe }}', 'جاري المعالجة', 'يرجى الانتظار بينما يتم تنفيذ طلبك تلقائياً...', false); }
                if(typeof showPopupNotification === 'function'){ showPopupNotification('⏳ جاري إرسال الطلب', 'يتم الآن معالجة طلبك، يرجى الانتظار...', '{{ icon("clock","2em")|safe }}'); }
                
                var formData = new FormData(form);
                formData.append('product_id', String(prodId));
                
                if(useOptions){
                    var sel = document.getElementById('optSelect');
                    if(sel && sel.selectedIndex > 0){
                        var selectedOpt = sel.options[sel.selectedIndex];
                        var apiId = selectedOpt.getAttribute('data-api-id');
                        var optLbl = selectedOpt.getAttribute('data-label');
                        var optPrice = selectedOpt.getAttribute('data-price');
                        if(apiId && apiId !== '' && apiId !== 'null'){ formData.append('variant_api_id', apiId); }
                        if(optLbl) formData.append('selected_option_label', optLbl);
                        if(optPrice) formData.append('selected_option_price', optPrice);
                    }
                }
                
                try {
                    var response = await fetch('/api/buy', {
                        method: 'POST',
                        body: formData,
                        credentials: 'same-origin',
                        headers: {'Accept': 'application/json'}
                    });
                    
                    if(response.status === 401){
                        if(typeof closeModal === 'function') closeModal();
                        if(typeof showModal === 'function'){ showModal('{{ icon("lock","2em")|safe }}', 'يجب تسجيل الدخول', 'انتهت جلستك. يرجى تسجيل الدخول مرة أخرى للمتابعة.'); }
                        if(typeof showPopupNotification === 'function'){ showPopupNotification('🔒 انتهت الجلسة', 'يرجى تسجيل الدخول مرة أخرى', '{{ icon("lock","2em")|safe }}'); }
                        setTimeout(function(){ window.location.href = '/login'; }, 2000);
                        return false;
                    }
                    
                    if(!response.ok){ throw new Error('HTTP ' + response.status); }
                    
                    var data = await response.json();
                    if(typeof closeModal === 'function') closeModal();
                    
                    if(data.success){
                        var msg = data.message || 'تم استلام طلبك بنجاح!';
                        if(data.delivered && String(data.delivered).trim() && String(data.delivered).trim() !== 'سيتم تسليم المنتج تلقائياً'){
                            msg += '<br><br><b>البيانات المسلمة:</b><br>';
                            msg += '<textarea id="deliveredData" style="width:100%;height:130px;background:var(--bg);color:var(--ok);';
                            msg += 'border:1px solid var(--brd);padding:10px;border-radius:10px;';
                            msg += 'font-family:monospace;direction:ltr;text-align:left;" readonly>';
                            msg += String(data.delivered).replace(/</g, '&lt;').replace(/>/g, '&gt;');
                            msg += '</textarea>';
                            msg += '<button class="btn bsm bp" style="margin-top:8px" onclick="copyToClipboard(document.getElementById(\'deliveredData\').value)">📋 نسخ</button>';
                        }
                        if(typeof showModal === 'function'){ showModal('{{ icon("check_circle","2.4em")|safe }}', 'تم استلام طلبك بنجاح!', msg); } else { alert(msg.replace(/<[^>]+>/g, '')); }
                        if(typeof showPopupNotification === 'function'){ showPopupNotification('تم الطلب بنجاح!', String(data.message || 'تم استلام طلبك').substring(0, 100), '{{ icon("check_circle","2em")|safe }}'); }
                        if(data.balance){ var balEl = document.querySelector('.header-balance-box'); if(balEl) balEl.innerHTML = '{{ icon("wallet","1em")|safe }} ' + data.balance; }
                    } else {
                        var iconHtml = data.type === 'balance' ? '{{ icon("wallet","2em")|safe }}' : (data.type === 'refund' ? '{{ icon("refresh","2em")|safe }}' : '{{ icon("x_circle","2em")|safe }}');
                        var titleStr = data.type === 'refund' ? 'تم الاسترداد' : (data.type === 'balance' ? 'رصيد غير كافٍ' : 'تم الرفض');
                        if(typeof showModal === 'function'){ showModal(iconHtml, titleStr, data.message || 'حدث خطأ غير متوقع'); } else { alert(data.message || 'حدث خطأ غير متوقع'); }
                        if(typeof showPopupNotification === 'function'){
                            var notifTitle = data.type === 'refund' ? 'تم الاسترداد' : (data.type === 'balance' ? 'رصيد غير كافٍ' : 'فشل الطلب');
                            showPopupNotification(notifTitle, String(data.message || 'فشل الطلب').substring(0, 100), iconHtml);
                        }
                        if(data.balance){ var balEl2 = document.querySelector('.header-balance-box'); if(balEl2) balEl2.innerHTML = '{{ icon("wallet","1em")|safe }} ' + data.balance; }
                    }
                } catch(err) {
                    if(typeof closeModal === 'function') closeModal();
                    if(typeof showModal === 'function'){ showModal('{{ icon("warning","2em")|safe }}', 'خطأ في الاتصال', 'حدث خطأ في الاتصال بالخادم. يرجى المحاولة مرة أخرى.<br><br>التفاصيل: ' + err.message); } else { alert('حدث خطأ في الاتصال بالخادم: ' + err.message); }
                    if(typeof showPopupNotification === 'function'){ showPopupNotification('خطأ بالاتصال', 'تعذر إرسال الطلب، يرجى المحاولة مرة أخرى', '{{ icon("warning","2em")|safe }}'); }
                } finally {
                    isSubmitting = false;
                    if(btn){ btn.disabled = false; btn.style.opacity = '1'; btn.innerHTML = '{{ icon("cart","1em")|safe }} تأكيد الشراء'; }
                }
                
                return false;
            }
            
            window.submitBuyForm = submitBuyForm;
            window.changeQty = changeQty;
            window.onQtyInput = onQtyInput;
            window.validateQty = validateQty;
            window.updateTotal = updateTotal;
            window.updateOptInfo = updateOptInfo;
            window.changeMainImage = changeMainImage;
            window.formatPrice = formatPrice;
            
            updateTotal();
            updateOptInfo();
            
            var purchaseBtn = document.getElementById('mainPurchaseBtn');
            if(purchaseBtn){
                purchaseBtn.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); submitBuyForm(PRODUCT_ID); });
            }
            
            document.addEventListener('DOMContentLoaded', function(){
                updateTotal(); updateOptInfo();
                var btn2 = document.getElementById('mainPurchaseBtn');
                if(btn2 && !btn2.hasAttribute('data-listener')){
                    btn2.setAttribute('data-listener', '1');
                    btn2.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); submitBuyForm(PRODUCT_ID); });
                }
            });
        })();
        </script>
        {% endif %}
    </div>
</div>

{% if related_products and related_products|length > 0 %}
<div class="related-products-section">
    <h1 class="section-title" style="font-size:1.1rem">{{ icon('share', '1.25em') }} منتجات ذات صلة</h1>
    <div class="related-products-grid">
        {% for prod in related_products %}
        <div class="pc ripple-container" onclick="window.location.href='/product/{{ prod.id }}'">
            <div class="pc-img">
                {% if prod.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ prod.image_path }}" alt="{{ prod.name }}" class="lazy-img">
                {% elif prod.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ prod.image_url }}" alt="{{ prod.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
                {% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '2em') }}</div>{% endif %}
            </div>
            <div class="pc-body">
                <div class="pc-name">{{ prod.name }}</div>
                <div class="pc-price-row"><span class="pc-price">{{ format_price(prod.sell_price) }}</span></div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}
{% endblock %}"""

CATEGORY_TMPL = """{% extends "base" %}{% block content %}
<div class="breadcrumb">
    <a href="/">{{ icon('home', '1em') }} الرئيسية</a>
    <span class="breadcrumb-separator">/</span>
    <span>{{ category.name }}</span>
</div>
<h1 class="section-title">{{ icon('category', '1.25em') }} {{ category.name }}</h1>
{% if category.description %}<p style="color:var(--t2);margin-bottom:16px;line-height:1.8">{{ category.description }}</p>{% endif %}
<div style="max-width:1200px;margin:0 auto">
{% if subcategories and subcategories|length > 0 %}
<h2 class="section-title" style="font-size:1rem">{{ icon('category', '1em') }} الأقسام الفرعية</h2>
<div class="cat-circular-grid" style="margin-bottom:20px">
{% for subcat in subcategories %}
<a href="/category/{{ subcat.id }}" class="cat-circular-item">
<div class="cat-circular-icon">
{% if subcat.image_path %}<img src="/images/{{ subcat.image_path }}" alt="{{ subcat.name }}">
{% elif subcat.image_url %}<img src="{{ subcat.image_url }}" alt="{{ subcat.name }}" onerror="this.style.display='none'">
{% else %}<div class="cat-emoji">{{ icon('package', '2.2em') }}</div>{% endif %}
</div>
<div class="cat-circular-name">{{ subcat.name }}</div>
<div class="cat-circular-count">{{ icon('package', '0.9em') }} {{ subcat.product_count }}</div>
</a>
{% endfor %}
</div>
{% endif %}
{% if products and products|length > 0 %}
<div class="section-title">{{ icon('package', '1.25em') }} المنتجات</div>
<div class="filters-bar">
    <div class="filter-item">
        <label class="filter-label">الترتيب</label>
        <select id="sortSelect" onchange="sortProducts()" class="filter-select">
            <option value="default">الترتيب الافتراضي</option>
            <option value="price_asc">السعر: الأقل أولاً</option>
            <option value="price_desc">السعر: الأعلى أولاً</option>
            <option value="name_asc">الاسم: أ-ي</option>
            <option value="name_desc">الاسم: ي-أ</option>
            <option value="best_selling">الأكثر مبيعاً</option>
        </select>
    </div>
</div>
<div class="grid g5" id="productsGrid">
{% for prod in products %}
<div class="pc ripple-container" onclick="window.location.href='/product/{{ prod.id }}'" data-name="{{ prod.name }}" data-price="{{ prod.sell_price }}" data-sales="{{ prod.sales_count }}" data-sort="{{ prod.sort_order or 0 }}">
{% if prod.stock_quantity == 0 %}<div class="pc-out-badge">غير متوفر</div>
{% elif prod.is_featured == 1 %}<div class="pc-featured-badge">مميز</div>
{% elif prod.sales_count > 10 %}<div class="pc-discount-badge">الأكثر مبيعاً</div>{% endif %}
<div class="pc-fav-card" onclick="toggleFavCard(event, this, {{ prod.id }});">{{ icon('heart', '0.85em') }}</div>
<div class="pc-compare" onclick="toggleCompare(event, this, {{ prod.id }});">{{ icon('compare', '0.7em') }}</div>
<div class="pc-quick-view" onclick="quickView(event, {{ prod.id }});">{{ icon('eye', '0.75em') }}</div>
<div class="pc-img">
{% if prod.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ prod.image_path }}" alt="{{ prod.name }}" class="lazy-img">
{% elif prod.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ prod.image_url }}" alt="{{ prod.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
{% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '2em') }}</div>{% endif %}
</div>
<div class="pc-body">
<div class="pc-name">{{ prod.name }}</div>
<div class="pc-price-row"><span class="pc-price">{{ format_price(prod.sell_price) }}</span></div>
</div>
</div>
{% endfor %}
</div>
{% elif not subcategories or subcategories|length == 0 %}
<div class="empty"><div class="empty-icon">{{ icon('package', '3em') }}</div><div class="empty-text">لا توجد منتجات في هذا القسم</div></div>
{% endif %}
</div>
<script>
var allProducts=Array.from(document.querySelectorAll('#productsGrid .pc'));
function sortProducts(){
    var sort=document.getElementById('sortSelect').value;
    var grid=document.getElementById('productsGrid');
    if(!grid) return;
    var items=allProducts.slice();
    if(sort==='default'){items.sort(function(a,b){return parseInt(a.getAttribute('data-sort')||0)-parseInt(b.getAttribute('data-sort')||0)})}
    else if(sort==='price_asc'){items.sort(function(a,b){return parseFloat(a.getAttribute('data-price')||0)-parseFloat(b.getAttribute('data-price')||0)})};
    if(sort==='price_desc'){items.sort(function(a,b){return parseFloat(b.getAttribute('data-price')||0)-parseFloat(a.getAttribute('data-price')||0)})};
    if(sort==='name_asc'){items.sort(function(a,b){return a.getAttribute('data-name').localeCompare(b.getAttribute('data-name'))})};
    if(sort==='name_desc'){items.sort(function(a,b){return b.getAttribute('data-name').localeCompare(a.getAttribute('data-name'))})};
    if(sort==='best_selling'){items.sort(function(a,b){return parseInt(b.getAttribute('data-sales')||0)-parseInt(a.getAttribute('data-sales')||0)})};
    items.forEach(function(item){grid.appendChild(item)});
}
</script>
{% endblock %}"""

CATEGORIES_LIST_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('category', '1.25em') }} جميع الأقسام</h1>
<div style="max-width:1200px;margin:0 auto">
{% if categories %}
<div class="cat-circular-grid">
{% for cat in categories %}
<a href="/category/{{ cat.id }}" class="cat-circular-item">
<div class="cat-circular-icon">
{% if cat.image_path %}<img src="/images/{{ cat.image_path }}" alt="{{ cat.name }}">
{% elif cat.image_url %}<img src="{{ cat.image_url }}" alt="{{ cat.name }}" onerror="this.style.display='none'">
{% else %}<div class="cat-emoji">{{ icon('package', '2.2em') }}</div>{% endif %}
</div>
<div class="cat-circular-name">{{ cat.name }}</div>
<div class="cat-circular-count">{{ icon('package', '0.9em') }} {{ cat.product_count }}</div>
</a>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('category', '3em') }}</div><div class="empty-text">لا توجد أقسام بعد</div></div>
{% endif %}
</div>
{% endblock %}"""

GIFTS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('gift', '1.25em') }} أكواد الهدايا</h1>
<div style="max-width:1200px;margin:0 auto">
{% if gifts %}
<div class="grid g4">
{% for g in gifts %}
<div class="gift-card">
<div class="gift-card-img">
{% if g.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ g.image_path }}" alt="{{ g.name }}" class="lazy-img">
{% elif g.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ g.image_url }}" alt="{{ g.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
{% else %}<div class="gift-card-img-placeholder">{{ icon('gift', '3.5em') }}</div>{% endif %}
</div>
<div class="gift-card-name">{{ g.name }}</div>
{% if g.description %}<div class="gift-card-desc">{{ g.description }}</div>{% endif %}
<div class="gift-card-price">{{ format_price(g.price) }}</div>
{% if logged_in %}
<button class="gift-card-buy-btn btn-shimmer" onclick="buyGift({{ g.id }})">{{ icon('cart', '1em') }} شراء الكود</button>
{% else %}
<button class="gift-card-buy-btn btn-guest-locked" onclick="showModal('{{ icon("lock","2em")|safe }}', 'يجب تسجيل الدخول', 'يرجى الدخول عبر تيليجرام لشراء الهدايا.')">{{ icon('lock', '1em') }} الدخول للشراء</button>
{% endif %}
</div>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('gift', '3em') }}</div><div class="empty-text">لا توجد أكواد هدايا متاحة حالياً</div></div>
{% endif %}
</div>
<script>
async function buyGift(id){
    showModal('{{ icon("clock","2.4em")|safe }}','جاري المعالجة','يرجى الانتظار...', false);
    try {
        const res = await fetch('/api/gift/buy/' + id, {method:'POST'});
        const data = await res.json();
        if(data.success){
            var msg = data.message + '<div class="gift-code-display"><div class="gift-code-label">كود الهدية الخاص بك:</div><div class="gift-code-value">' + data.code + '</div><button class="btn bp" style="margin-top:10px" onclick="copyToClipboard(this.previousElementSibling.textContent)">{{ icon("copy","1em") }} نسخ الكود</button></div>';
            showModal('{{ icon("gift","2.4em")|safe }}', 'تم شراء الكود بنجاح!', msg);
            if(data.balance){var balEl=document.querySelector('.header-balance-box');if(balEl)balEl.innerText='{{ icon("wallet","1em") }} '+data.balance;}
        } else {
            var iconHtml = data.type === 'balance' ? '{{ icon("wallet","2em")|safe }}' : '{{ icon("x_circle","2em")|safe }}';
            showModal(iconHtml, 'فشل الشراء', data.message);
            if(data.balance){var balEl=document.querySelector('.header-balance-box');if(balEl)balEl.innerText='{{ icon("wallet","1em") }} '+data.balance;}
        }
    } catch(err){
        showModal('{{ icon("warning","2em")|safe }}','خطأ','حدث خطأ في الاتصال بالخادم.');
    }
}
</script>
{% endblock %}"""

CART_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('cart', '1.25em') }} سلة المشتريات</h1>
<div style="max-width:800px;margin:0 auto">
{% if items %}
<div class="card" style="padding:15px">
{% for item in items %}
<div class="cart-item">
    <div class="cart-item-img">
        {% if item.image_path %}<img src="/images/{{ item.image_path }}" alt="{{ item.name }}">
        {% elif item.image_url %}<img src="{{ item.image_url }}" alt="{{ item.name }}" onerror="this.style.display='none'">
        {% else %}<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;opacity:0.3">{{ icon('package', '1.5em') }}</div>{% endif %}
    </div>
    <div class="cart-item-info">
        <div class="cart-item-name">{{ item.name }}</div>
        <div class="cart-item-price">{{ format_price(item.sell_price) }} × {{ item.quantity }}</div>
        {% if item.selected_option %}<div style="font-size:.7rem;color:var(--t3)">الخيار: {{ item.selected_option }}</div>{% endif %}
    </div>
    <button class="cart-item-remove" onclick="removeCartItem({{ item.id }})">{{ icon('trash', '1.2em') }}</button>
</div>
{% endfor %}
</div>
<div class="purchase-summary-box">
    <div class="purchase-total-row">
        <span class="purchase-total-label">{{ icon('money', '1em') }} الإجمالي</span>
        <span class="purchase-total-value">{{ format_price(total) }}</span>
    </div>
    <button class="purchase-btn btn-shimmer" onclick="window.location.href='/checkout'">{{ icon('check', '1em') }} إتمام الشراء</button>
</div>
{% else %}
<div class="empty">
    <div class="empty-icon">{{ icon('cart', '3em') }}</div>
    <div class="empty-text">سلتك فارغة</div>
    <div style="margin-top:12px"><a href="/" class="btn bp">{{ icon('package', '1em') }} تصفح المنتجات</a></div>
</div>
{% endif %}
</div>
<script>
function removeCartItem(id){
    if(!confirm('هل أنت متأكد من حذف هذا المنتج من السلة؟')) return;
    fetch('/api/cart/remove/'+id, {method:'POST'})
    .then(r=>r.json())
    .then(d=>{ if(d.success) location.reload(); });
}
</script>
{% endblock %}"""

COMPARE_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('compare', '1.25em') }} مقارنة المنتجات</h1>
<div style="max-width:1000px;margin:0 auto;overflow-x:auto">
{% if items and items|length > 0 %}
<table class="comparison-table">
    <tr>
        <th>الخاصية</th>
        {% for p in items %}<th>{{ p.name }}<br><button class="btn bsm bd" style="margin-top:5px" onclick="removeCompare({{ p.id }})">{{ icon('trash', '1em') }} إزالة</button></th>{% endfor %}
    </tr>
    <tr>
        <td>الصورة</td>
        {% for p in items %}
        <td><div class="comparison-product-img">
            {% if p.image_path %}<img src="/images/{{ p.image_path }}" alt="{{ p.name }}">
            {% elif p.image_url %}<img src="{{ p.image_url }}" alt="{{ p.name }}" onerror="this.style.display='none'">
            {% else %}{{ icon('package', '2em') }}{% endif %}
        </div></td>
        {% endfor %}
    </tr>
    <tr>
        <td>السعر</td>
        {% for p in items %}<td style="font-weight:900;color:var(--accent-l)">{{ format_price(p.sell_price) }}</td>{% endfor %}
    </tr>
    <tr>
        <td>الوصف</td>
        {% for p in items %}<td style="font-size:.8rem;color:var(--t2)">{{ p.description or 'لا يوجد وصف' }}</td>{% endfor %}
    </tr>
    <tr>
        <td>التوفر</td>
        {% for p in items %}<td>{% if p.stock_quantity == 0 %}<span class="tag tag-err">غير متوفر</span>{% else %}<span class="tag tag-ok">متوفر</span>{% endif %}</td>{% endfor %}
    </tr>
</table>
{% else %}
<div class="empty">
    <div class="empty-icon">{{ icon('compare', '3em') }}</div>
    <div class="empty-text">لا توجد منتجات للمقارنة</div>
    <div style="margin-top:12px"><a href="/" class="btn bp">{{ icon('package', '1em') }} تصفح المنتجات</a></div>
</div>
{% endif %}
</div>
<script>
function removeCompare(id){
    fetch('/api/compare/toggle/'+id, {method:'POST'})
    .then(r=>r.json())
    .then(d=>{ if(d.success) location.reload(); });
}
</script>
{% endblock %}"""

FAQ_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('faq', '1.25em') }} الأسئلة الشائعة</h1>
<div style="max-width:800px;margin:0 auto">
{% if faqs %}
{% for f in faqs %}
<div class="faq-item">
    <div class="faq-question">
        <span>{{ f.question }}</span>
        <span class="faq-toggle">{{ icon('plus', '1em') }}</span>
    </div>
    <div class="faq-answer">{{ f.answer }}</div>
</div>
{% endfor %}
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('faq', '3em') }}</div><div class="empty-text">لا توجد أسئلة شائعة حالياً</div></div>
{% endif %}
</div>
{% endblock %}"""

BLOG_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('blog', '1.25em') }} المدونة</h1>
<div style="max-width:1000px;margin:0 auto">
{% if posts %}
<div class="grid g3">
{% for p in posts %}
<div class="blog-card" onclick="window.location.href='/blog/{{ p.slug }}'">
    <div class="blog-card-img">
        {% if p.image_path %}<img src="/images/{{ p.image_path }}" alt="{{ p.title }}">
        {% else %}<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;opacity:0.5">{{ icon('blog', '3em') }}</div>{% endif %}
    </div>
    <div class="blog-card-body">
        <div class="blog-card-title">{{ p.title }}</div>
        <div class="blog-card-excerpt">{{ p.excerpt }}</div>
        <div class="blog-card-date">{{ icon('clock', '1em') }} {{ p.created_at[:10] }}</div>
    </div>
</div>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('blog', '3em') }}</div><div class="empty-text">لا توجد مقالات حالياً</div></div>
{% endif %}
</div>
{% endblock %}"""

BLOG_POST_TMPL = """{% extends "base" %}{% block content %}
<div style="max-width:800px;margin:0 auto">
<a href="/blog" style="color:var(--accent-l);text-decoration:none;display:inline-flex;align-items:center;gap:5px;margin-bottom:12px;font-weight:700">{{ icon('arrow_back', '1em') }} العودة للمدونة</a>
<div class="card">
<h1 style="font-size:1.5rem;font-weight:900;margin-bottom:15px;color:var(--t1)">{{ post.title }}</h1>
{% if post.image_path %}<img src="/images/{{ post.image_path }}" alt="{{ post.title }}" style="width:100%;border-radius:var(--rs);margin-bottom:15px">{% endif %}
<div class="blog-post-content" style="line-height:1.8;color:var(--t2)">{{ post.content }}</div>
<div style="margin-top:15px;font-size:.8rem;color:var(--t3);display:flex;align-items:center;gap:10px">{{ icon('clock', '1em') }} نُشر في: {{ post.created_at[:10] }} | {{ icon('eye', '1em') }} المشاهدات: {{ post.views }}</div>
</div>
</div>
{% endblock %}"""

ACHIEVEMENTS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('medal', '1.25em') }} إنجازاتي</h1>
<div style="max-width:1000px;margin:0 auto">
{% if achievements and achievements|length > 0 %}
<div class="achievements-grid">
{% for a in achievements %}
<div class="achievement-card">
    <div class="achievement-icon">{{ icon('medal', '2em') }}</div>
    <div class="achievement-name">{{ a.achievement_name }}</div>
    <div class="achievement-desc">{{ a.description }}</div>
</div>
{% endfor %}
</div>
{% else %}
<div class="empty">
    <div class="empty-icon">{{ icon('medal', '3em') }}</div>
    <div class="empty-text">لا توجد إنجازات بعد</div>
    <div style="margin-top:12px;font-size:.8rem;color:var(--t3)">أكمل طلبات لفتح إنجازات جديدة!</div>
</div>
{% endif %}
</div>
{% endblock %}"""

CONTESTS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('trophy', '1.25em') }} المسابقات</h1>
<div style="max-width:800px;margin:0 auto">
{% if contests and contests|length > 0 %}
{% for c in contests %}
<div class="contest-card">
    <div class="contest-title">{{ icon('trophy', '1.1em') }} {{ c.title }}</div>
    {% if c.prize %}<div class="contest-prize">{{ icon('gift', '1em') }} الجائزة: {{ c.prize }}</div>{% endif %}
    {% if c.description %}<div class="contest-desc">{{ c.description }}</div>{% endif %}
    {% if c.end_date %}<div class="contest-end-date">{{ icon('clock', '1em') }} ينتهي في: {{ c.end_date[:10] }}</div>{% endif %}
    {% if logged_in %}
    <button class="btn bp" onclick="joinContest({{ c.id }})">{{ icon('check', '1em') }} انضم للمسابقة</button>
    {% else %}
    <button class="btn btn-guest-locked" onclick="showModal('{{ icon("lock","2em")|safe }}', 'يجب تسجيل الدخول', 'يرجى الدخول عبر تيليجرام للمشاركة في المسابقات.')">{{ icon('lock', '1em') }} الدخول للمشاركة</button>
    {% endif %}
</div>
{% endfor %}
{% else %}
<div class="empty">
    <div class="empty-icon">{{ icon('trophy', '3em') }}</div>
    <div class="empty-text">لا توجد مسابقات حالياً</div>
</div>
{% endif %}
</div>
<script>
async function joinContest(id){
    showModal('{{ icon("clock","2.4em")|safe }}','جاري المعالجة','يرجى الانتظار...', false);
    try {
        const res = await fetch('/api/contest/join/' + id, {method:'POST'});
        const data = await res.json();
        if(data.success){
            showModal('{{ icon("check_circle","2.4em")|safe }}', 'تم الانضمام!', data.message);
        } else {
            showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', data.message);
        }
    } catch(err){
        showModal('{{ icon("warning","2em")|safe }}','خطأ','حدث خطأ في الاتصال بالخادم.');
    }
}
</script>
{% endblock %}"""

SHIPPING_CHECKOUT_TMPL = """{% extends "base" %}{% block content %}
<a href="/cart" style="color:var(--accent-l);text-decoration:none;display:inline-flex;align-items:center;gap:5px;margin-bottom:12px;font-weight:700">{{ icon('arrow_back', '1em') }} العودة للسلة</a>
<div style="max-width:680px;margin:0 auto">
<div class="checkout-steps">
<div class="checkout-step completed">{{ icon('cart', '1em') }} 1. السلة</div>
<div class="checkout-step active">{{ icon('truck', '1em') }} 2. الشحن والدفع</div>
<div class="checkout-step">{{ icon('check', '1em') }} 3. التأكيد</div>
</div>
<div class="card" style="margin-bottom:14px">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('package', '1em') }} تفاصيل الطلب</h3>
{% for item in items %}
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)">
    <span style="color:var(--t3)">{{ item.name }} (×{{ item.quantity }})</span>
    <span style="font-weight:800;color:var(--accent-l)">{{ format_price(item.sell_price * item.quantity) }}</span>
</div>
{% endfor %}
<div style="display:flex;justify-content:space-between;padding:6px 0;margin-top:5px">
    <span style="color:var(--t3)">سعر المنتجات</span>
    <span style="font-weight:800;color:var(--accent-l)">{{ format_price(product_total) }}</span>
</div>
</div>
<form id="checkoutForm" onsubmit="submitCheckout(event)">
<div class="card" style="margin-bottom:14px">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('truck', '1em') }} اختر طريقة الشحن</h3>
{% if shipping_methods %}
<div class="grid g3" id="shippingMethodsGrid">
{% for sm in shipping_methods %}
<div class="method-box" data-sm-id="{{ sm.id }}" data-sm-price="{{ sm.price }}" data-sm-name="{{ sm.name }}" data-sm-wallet="{{ sm.wallet_number or '' }}" data-sm-link="{{ sm.wallet_link or '' }}" onclick="selectShipping(this)">
<input type="radio" name="shipping_method_id" value="{{ sm.id }}" style="display:none">
{% if sm.image_path %}<div class="method-box-img"><div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ sm.image_path }}" alt="{{ sm.name }}" class="lazy-img"></div>
{% else %}<div class="method-box-icon">{{ icon('truck', '2em') }}</div>{% endif %}
<div class="method-box-name">{{ sm.name }}</div>
{% if sm.estimated_days %}<div class="method-box-desc">{{ icon('clock', '0.9em') }} {{ sm.estimated_days }}</div>{% endif %}
<div class="method-box-price">{{ format_price(sm.price) }}</div>
</div>
{% endfor %}
</div>
{% else %}<p style="color:var(--t3);text-align:center;padding:14px">لا توجد طرق شحن متاحة حالياً</p>{% endif %}
</div>
<div class="card" style="margin-bottom:14px">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('credit_card', '1em') }} معلومات الدفع</h3>
<div class="fg"><label class="fl">{{ icon('money', '1em') }} المبلغ المحوّل</label><input class="fi" type="number" name="payment_amount" required placeholder="أدخل المبلغ الذي قمت بتحويله" min="0" step="0.01"></div>
<div class="fg"><label class="fl">{{ icon('tag', '1em') }} رقم العملية / الحوالة</label><input class="fi" type="text" name="transaction_number" required placeholder="أدخل رقم العملية"></div>
{% if payment_methods %}
<div style="margin-top:10px"><p style="font-size:.78rem;color:var(--t3);margin-bottom:8px;display:flex;align-items:center;gap:5px">{{ icon('info', '1em') }} طرق الدفع المتاحة:</p>
{% for pm in payment_methods %}
<div style="background:var(--bg2);padding:10px;border-radius:var(--rs);margin-bottom:8px;border:1px solid var(--brd)">
<div style="font-weight:700;font-size:.82rem">{{ pm.name }}</div>
{% if pm.account_number %}<div style="font-size:.72rem;color:var(--t3)">رقم الحساب: <code>{{ pm.account_number }}</code></div>{% endif %}
{% if pm.account_name %}<div style="font-size:.72rem;color:var(--t3)">الاسم: {{ pm.account_name }}</div>{% endif %}
{% if pm.description %}<div style="font-size:.72rem;color:var(--t3)">{{ pm.description }}</div>{% endif %}
</div>
{% endfor %}
</div>
{% endif %}
</div>
<div class="purchase-summary-box">
<div class="purchase-total-row">
<span class="purchase-total-label">{{ icon('money', '1em') }} الإجمالي المطلوب</span>
<span class="purchase-total-value" id="grandTotal">{{ format_price(product_total) }}</span>
</div>
<input type="hidden" name="shipping_price" id="shippingPriceInput" value="0">
<button type="submit" class="purchase-btn btn-shimmer">{{ icon('check', '1em') }} تأكيد الطلب</button>
</div>
</form>
</div>
<script>
var productTotal={{ product_total }};
function selectShipping(box){
    document.querySelectorAll('#shippingMethodsGrid .method-box').forEach(function(b){b.classList.remove('selected');});
    box.classList.add('selected');
    box.querySelector('input[type="radio"]').checked = true;
    var price=parseFloat(box.getAttribute('data-sm-price')||0);
    document.getElementById('shippingPriceInput').value=price;
    var total=productTotal+price;
    document.getElementById('grandTotal').textContent=formatPriceLocal(total);
}
function formatPriceLocal(p){
    var num=parseFloat(p||0);
    if(num>=1000){return num.toLocaleString('ar-EG',{minimumFractionDigits:0,maximumFractionDigits:0})+' '+'{{ currency_symbol }}';}
    return num.toLocaleString('ar-EG',{minimumFractionDigits:0,maximumFractionDigits:2})+' '+'{{ currency_symbol }}';
}
async function submitCheckout(e) {
    e.preventDefault();
    var form = document.getElementById('checkoutForm');
    var formData = new FormData(form);
    if (!formData.get('shipping_method_id')) {
        showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', 'يرجى اختيار طريقة الشحن.');
        return;
    }
    showModal('{{ icon("clock","2.4em")|safe }}', 'جاري الإرسال', 'يرجى الانتظار...', false);
    try {
        const response = await fetch('/checkout/confirm', { method: 'POST', body: formData, credentials: 'same-origin' });
        const data = await response.json();
        if (data.success) {
            closeModal();
            window.location.href = '/wallet/topup/processing';
        } else {
            showModal('{{ icon("x_circle","2em")|safe }}', 'فشل الإرسال', data.message || 'حدث خطأ غير متوقع');
        }
    } catch (err) {
        showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'حدث خطأ في الاتصال بالخادم.');
    }
}
</script>
{% endblock %}"""

ORDER_SUCCESS_TMPL = """{% extends "base" %}{% block content %}
<div style="max-width:580px;margin:0 auto">
<div style="text-align:center;padding:28px 14px">
<div style="margin-bottom:12px;display:flex;justify-content:center">{{ icon('check_circle', '3em') }}</div>
<div style="font-size:1.2rem;font-weight:900;color:var(--ok);margin-bottom:6px">تم استلام طلبك بنجاح!</div>
<div style="color:var(--t2);font-size:.88rem;margin-bottom:16px">شكراً لك! تم استلام طلبك وسيتم مراجعته وتأكيده قريباً.</div>
</div>
<div class="card" style="margin-top:14px">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('orders', '1em') }} تفاصيل الطلب</h3>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">رقم الطلب</span><span style="font-weight:700" class="badge badge-info">{{ order.order_id }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">الكمية</span><span style="font-weight:700">{{ order.quantity }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">الحالة</span>
{% if order.status == 'completed' %}<span class="tag tag-ok">{{ icon('check_circle', '1em') }} مكتمل</span>
{% elif order.status == 'pending' %}<span class="tag tag-warn">{{ icon('clock', '1em') }} قيد المراجعة</span>
{% elif order.status == 'failed' %}<span class="tag tag-err">{{ icon('x_circle', '1em') }} فشل</span>
{% else %}<span class="tag tag-info">{{ order.status }}</span>{% endif %}
</div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">السعر</span><span style="font-weight:800;color:var(--accent-l)">{{ format_price(order.total_price) }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0"><span style="color:var(--t3)">التاريخ</span><span style="font-size:.76rem">{{ order.created_at[:16] }}</span></div>
{% if order.delivered_data %}
<div style="margin-top:12px;padding:10px;background:var(--bg);border-radius:var(--rs);border:1px solid var(--brd)">
<div style="font-weight:700;font-size:.8rem;margin-bottom:6px;display:flex;align-items:center;gap:5px">{{ icon('download', '1em') }} البيانات المسلمة:</div>
<div style="font-family:monospace;font-size:.76rem;color:var(--ok);white-space:pre-wrap;word-wrap:break-word">{{ order.delivered_data }}</div>
</div>
{% endif %}
</div>
<div style="text-align:center;margin-top:16px">
<a href="/orders" class="btn bp" style="text-decoration:none">{{ icon('orders', '1em') }} عرض طلباتي</a>
<a href="/" class="btn bo" style="text-decoration:none;margin-right:8px">{{ icon('home', '1em') }} الرئيسية</a>
</div>
</div>
{% if order.status == 'processing' or order.status == 'pending' %}
<script>
setTimeout(function(){ location.reload(); }, 15000);
</script>
{% endif %}
{% endblock %}"""

ORDERS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('orders', '1.25em') }} طلباتي (مفصل)</h1>
<div style="max-width:900px;margin:0 auto">
<div style="display:flex;gap:9px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
<button class="btn bsm bp" onclick="filterOrders('all')">{{ icon('grid', '1em') }} الكل</button>
<button class="btn bsm bs" onclick="filterOrders('pending')">{{ icon('clock', '1em') }} المعلقة</button>
<button class="btn bsm bo" onclick="filterOrders('completed')">{{ icon('check_circle', '1em') }} المقبولة</button>
<button class="btn bsm bd" onclick="filterOrders('failed')">{{ icon('x_circle', '1em') }} المرفوضة</button>
</div>
{% if orders %}
<div class="table-w">
<table>
<thead><tr><th>رقم الطلب</th><th>المنتج</th><th>الكمية</th><th>السعر</th><th>الحالة</th><th>التاريخ</th><th>تفاصيل</th></tr></thead>
<tbody>
{% for o in orders %}
<tr data-status="{{ o.status }}">
<td style="font-size:.7rem;direction:ltr">{{ o.order_id[:20] }}</td>
<td style="font-weight:700">{{ o.product_name or 'منتج محذوف' }}</td>
<td>{{ o.quantity }}</td>
<td style="font-weight:800;color:var(--accent-l)">{{ format_price(o.total_price) }}</td>
<td>
{% if o.status == 'completed' %}<span class="tag tag-ok">{{ icon('check_circle', '1em') }} مكتمل</span>
{% elif o.status == 'pending' %}<span class="tag tag-warn">{{ icon('clock', '1em') }} معلق</span>
{% elif o.status == 'processing' %}<span class="tag tag-info">{{ icon('refresh', '1em') }} قيد المعالجة</span>
{% elif o.status == 'failed' %}<span class="tag tag-err">{{ icon('x_circle', '1em') }} مرفوض</span>
{% else %}<span class="tag tag-info">{{ o.status }}</span>{% endif %}
</td>
<td style="font-size:.7rem">{{ o.created_at[:16] }}</td>
<td><a href="/order/details/{{ o.id }}" class="btn bsm bo" style="text-decoration:none">{{ icon('eye', '1em') }} تفاصيل</a></td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('orders', '3em') }}</div><div class="empty-text">لا توجد طلبات بعد</div><div style="margin-top:12px"><a href="/" class="btn bp">{{ icon('package', '1em') }} تصفح المنتجات</a></div></div>
{% endif %}
</div>
<script>
function filterOrders(status){
var rows=document.querySelectorAll('tbody tr');
rows.forEach(function(row){
if(status==='all'||row.getAttribute('data-status')===status){row.style.display='';}
else{row.style.display='none';}
});
}
</script>
{% endblock %}"""

ORDER_DETAILS_TMPL = """{% extends "base" %}{% block content %}
<a href="/orders" style="color:var(--accent-l);text-decoration:none;display:inline-flex;align-items:center;gap:5px;margin-bottom:12px;font-weight:700">{{ icon('arrow_back', '1em') }} العودة للطلبات</a>
<div style="max-width:800px;margin:0 auto">
<div class="card">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('orders', '1em') }} تفاصيل الطلب #{{ order.id }}</h3>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">رقم الطلب</span><span style="font-weight:700" class="badge badge-info">{{ order.order_id }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">المنتج</span><span style="font-weight:700">{{ product_name }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">الكمية</span><span style="font-weight:700">{{ order.quantity }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">سعر الوحدة</span><span style="font-weight:700">{{ format_price(order.unit_price) }}</span></div>
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">الإجمالي</span><span style="font-weight:800;color:var(--accent-l)">{{ format_price(order.total_price) }}</span></div>
{% if order.player_id %}<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">معرّف اللاعب</span><span style="font-weight:700" dir="ltr">{{ order.player_id }}</span></div>{% endif %}
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd)"><span style="color:var(--t3)">الحالة</span>
{% if order.status == 'completed' %}<span class="tag tag-ok">{{ icon('check_circle', '1em') }} مكتمل</span>
{% elif order.status == 'pending' %}<span class="tag tag-warn">{{ icon('clock', '1em') }} قيد المراجعة</span>
{% elif order.status == 'failed' %}<span class="tag tag-err">{{ icon('x_circle', '1em') }} مرفوض</span>
{% else %}<span class="tag tag-info">{{ order.status }}</span>{% endif %}
</div>
<div style="display:flex;justify-content:space-between;padding:6px 0"><span style="color:var(--t3)">التاريخ</span><span style="font-size:.76rem">{{ order.created_at[:16] }}</span></div>

{% if order.delivered_data %}
<div style="margin-top:16px;padding:12px;background:var(--bg);border-radius:var(--rs);border:1px solid var(--brd)">
<div style="font-weight:700;font-size:.82rem;margin-bottom:8px;color:var(--ok);display:flex;align-items:center;gap:5px">{{ icon('download', '1em') }} البيانات المسلمة:</div>
<div style="font-family:monospace;font-size:.76rem;color:var(--ok);white-space:pre-wrap;word-wrap:break-word;background:var(--bg2);padding:10px;border-radius:6px;border:1px dashed var(--brd)">{{ order.delivered_data }}</div>
<button class="btn bsm bp" style="margin-top:8px" onclick="copyToClipboard(this.previousElementSibling.textContent)">{{ icon('copy', '1em') }} نسخ البيانات</button>
</div>
{% endif %}
</div>
</div>
{% if order.status == 'processing' or order.status == 'pending' %}
<script>
setTimeout(function(){ location.reload(); }, 15000);
</script>
{% endif %}
{% endblock %}"""

PROFILE_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('settings', '1.25em') }} إعداداتي ومعلوماتي</h1>
<div style="max-width:800px;margin:0 auto">
{% if error %}<div style="background:rgba(239,68,68,0.15);padding:12px;border-radius:var(--rs);margin-bottom:13px;text-align:center;font-size:.8rem;color:var(--err);border:1px solid rgba(239,68,68,0.3)">{{ icon('warning', '1em') }} {{ error }}</div>{% endif %}

{% if stats.is_vip %}
<div class="vip-card">
    <div class="vip-card-header">
        <div class="vip-card-icon">{{ icon('diamond', '2.5em') }}</div>
        <div>
            <div class="vip-card-title">عضو VIP {{ stats.vip_level_name }}</div>
            <div class="vip-card-level">أنت عميل مميز! استمتع بمزايا حصرية.</div>
        </div>
    </div>
    <div class="vip-card-benefits">{{ icon('star', '1em') }} المزايا: {{ vip_benefits }}</div>
</div>
{% endif %}

{% if stats.loyalty_points > 0 %}
<div class="loyalty-points-box">
    <div class="loyalty-points-icon">{{ icon('star', '1.6em') }}</div>
    <div class="loyalty-points-text">لديك {{ stats.loyalty_points }} نقطة ولاء</div>
</div>
{% endif %}

{% if stats.achievements_count > 0 %}
<div style="margin-bottom:14px">
    <a href="/achievements" class="btn bp bsm" style="text-decoration:none">{{ icon('medal', '1em') }} إنجازاتي ({{ stats.achievements_count }})</a>
</div>
{% endif %}

{% if referral_link %}
<div class="referral-box">
    <div class="referral-title">{{ icon('gift', '1.2em') }} رابط الإحالة الخاص بك</div>
    <div class="referral-text">شارك هذا الرابط مع أصدقائك. عندما يقوم صديق بالتسجيل وشحن محفظته، ستحصل على مكافأة!</div>
    <div class="referral-link-box">
        <code id="referralLink">{{ referral_link }}</code>
        <button class="btn bp bsm" onclick="copyToClipboard(document.getElementById('referralLink').textContent);showModal('{{ icon("copy","2em")|safe }}', 'تم النسخ', 'تم نسخ رابط الإحالة بنجاح!')">نسخ الرابط</button>
    </div>
</div>
{% endif %}

<div class="card">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:18px">
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('user', '1em') }} اسم المستخدم</div><div style="font-size:.92rem;font-weight:800;color:var(--t1)">{{ user.username }}</div></div>
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('telegram', '1em') }} تيليجرام ID</div><div style="font-size:.92rem;font-weight:800;color:var(--t1)" dir="ltr">{{ user.telegram_id or 'غير متوفر' }}</div></div>
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('phone', '1em') }} رقم الهاتف</div><div style="font-size:.92rem;font-weight:800;color:var(--t1)" dir="ltr">{{ user.phone or 'غير متوفر' }}</div></div>
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('wallet', '1em') }} الرصيد الحالي</div><div style="font-size:.92rem;font-weight:800;color:var(--ok)">{{ format_price(user.balance) }}</div></div>
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('clock', '1em') }} تاريخ الانضمام</div><div style="font-size:.92rem;font-weight:800;color:var(--t1)">{{ user.created_at[:16] if user.created_at else '-' }}</div></div>
<div style="background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:14px"><div style="font-size:.78rem;color:var(--t3);margin-bottom:6px;font-weight:600;display:flex;align-items:center;gap:5px">{{ icon('logout', '1em') }} آخر تسجيل دخول</div><div style="font-size:.92rem;font-weight:800;color:var(--t1)">{{ user.last_login[:16] if user.last_login else '-' }}</div></div>
</div>
</div>

<div style="margin:20px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--brd);font-size:1rem;font-weight:800;color:var(--accent-l);display:flex;align-items:center;gap:8px">{{ icon('grid', '1em') }} إحصائيات الحساب</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:18px">
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ stats.total_orders }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">إجمالي الطلبات</div></div>
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ stats.completed_orders }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">طلبات مكتملة</div></div>
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ stats.pending_orders }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">طلبات قيد المراجعة</div></div>
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ stats.failed_orders }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">طلبات مرفوضة</div></div>
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ format_price(stats.total_spent) }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">إجمالي الإنفاق</div></div>
{% if stats.contests_won > 0 %}
<div style="background:linear-gradient(135deg,var(--card),var(--card-h));border:1px solid var(--gbrd);border-radius:var(--rs);padding:12px;text-align:center"><div style="font-size:1.4rem;font-weight:900;background:var(--grad1);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:textGradient 3s ease infinite">{{ stats.contests_won }}</div><div style="font-size:.7rem;color:var(--t3);margin-top:3px">مسابقات فائزة</div></div>
{% endif %}
</div>

<div style="margin:20px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--brd);font-size:1rem;font-weight:800;color:var(--accent-l);display:flex;align-items:center;gap:8px">{{ icon('edit', '1em') }} تعديل البيانات الشخصية</div>
<div class="card">
<form method="POST" action="/profile">
<div class="fg"><label class="fl">{{ icon('phone', '1em') }} رقم الهاتف</label><input class="fi" type="tel" name="phone" value="{{ user.phone or '' }}" placeholder="09XXXXXXXX"></div>
<div class="fg"><label class="fl">{{ icon('lock', '1em') }} كلمة المرور الجديدة (اتركها فارغة إذا لا تريد تغييرها)</label><input class="fi" type="password" name="password" placeholder="********" minlength="6"></div>
<button type="submit" class="btn bp bbl">{{ icon('check', '1em') }} حفظ التغييرات</button>
</form>
</div>
</div>
{% endblock %}"""

FAVORITES_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('heart', '1.25em') }} المفضلة</h1>
<div style="max-width:1200px;margin:0 auto">
{% if products %}
<div class="grid g5">
{% for prod in products %}
<div class="pc" onclick="window.location.href='/product/{{ prod.id }}'">
<div class="pc-fav-card active" onclick="toggleFavCard(event, this, {{ prod.id }});">{{ icon('heart_filled', '0.85em') }}</div>
<div class="pc-img">
{% if prod.image_path %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ prod.image_path }}" alt="{{ prod.name }}" class="lazy-img">
{% elif prod.image_url %}<div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="{{ prod.image_url }}" alt="{{ prod.name }}" class="lazy-img" onerror="this.style.display='none';this.previousElementSibling.style.display='none'">
{% else %}<div style="opacity:.3;display:flex;align-items:center;justify-content:center;width:100%;height:100%">{{ icon('package', '2em') }}</div>{% endif %}
</div>
<div class="pc-body">
<div class="pc-name">{{ prod.name }}</div>
<div class="pc-price-row"><span class="pc-price">{{ format_price(prod.sell_price) }}</span></div>
</div>
</div>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('heart', '3em') }}</div><div class="empty-text">لا توجد منتجات في المفضلة</div><div style="margin-top:12px"><a href="/" class="btn bp">{{ icon('package', '1em') }} تصفح المنتجات</a></div></div>
{% endif %}
</div>
{% endblock %}"""

WALLET_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('wallet', '1.25em') }} محفظتي</h1>
<div style="max-width:680px;margin:0 auto">
<div class="wallet-card" style="margin-bottom:18px">
<div style="font-size:.82rem;opacity:.9;position:relative;z-index:1;display:flex;align-items:center;gap:5px">{{ icon('wallet', '1em') }} رصيد المحفظة</div>
<div class="wallet-balance">{{ format_price(user_balance) }}</div>
<div style="display:flex;gap:8px;margin-top:8px;position:relative;z-index:1">
<a href="/wallet/topup" class="btn bs bbl" style="text-decoration:none">{{ icon('download', '1em') }} شحن المحفظة</a>
</div>
</div>
<div class="card">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('grid', '1em') }} آخر العمليات</h3>
{% if transactions %}
<div class="table-w">
<table>
<thead><tr><th>النوع</th><th>الوصف</th><th>المبلغ</th><th>الرصيد بعد</th><th>التاريخ</th></tr></thead>
<tbody>
{% for t in transactions %}
<tr>
<td>
{% if t.transaction_type == 'topup' %}<span class="badge badge-ok">{{ icon('download', '1em') }} شحن</span>
{% elif t.transaction_type == 'purchase' %}<span class="badge badge-err">{{ icon('cart', '1em') }} شراء</span>
{% elif t.transaction_type == 'refund' %}<span class="badge badge-info">{{ icon('refresh', '1em') }} استرداد</span>
{% elif t.transaction_type == 'gift_purchase' %}<span class="badge badge-warn">{{ icon('gift', '1em') }} هدية</span>
{% else %}<span class="badge badge-warn">{{ t.transaction_type }}</span>{% endif %}
</td>
<td style="font-size:.74rem">{{ t.description or '-' }}</td>
<td style="font-weight:800;color:{% if t.amount > 0 %}var(--ok){% else %}var(--err){% endif %}">{{ '%+.2f' % t.amount }}</td>
<td style="font-size:.74rem;color:var(--t3)">{% if t.balance_after is not none %}{{ format_price(t.balance_after) }}{% else %}-{% endif %}</td>
<td style="font-size:.68rem">{{ t.created_at[:16] }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% else %}
<div class="empty" style="padding:20px"><div class="empty-text">لا توجد عمليات بعد</div></div>
{% endif %}
</div>
</div>
{% endblock %}"""

WALLET_TOPUP_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('download', '1.25em') }} شحن المحفظة</h1>
<div style="max-width:680px;margin:0 auto">

{% if pending_requests and pending_requests|length > 0 %}
<div class="card" style="margin-bottom:14px;border:2px solid rgba(245,158,11,0.4)">
<h3 style="font-weight:800;margin-bottom:12px;color:var(--warn);display:flex;align-items:center;gap:8px">{{ icon('clock', '1em') }} طلبات الشحن قيد المراجعة ({{ pending_requests|length }})</h3>
{% for r in pending_requests %}
<div style="background:var(--bg2);padding:14px;border-radius:var(--rs);margin-bottom:10px;border:1px solid var(--brd);position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;right:0;width:4px;height:100%;background:var(--warn);"></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;padding-bottom:8px;border-bottom:1px dashed var(--brd)">
        <span style="font-weight:800;font-size:.85rem;color:var(--accent-l);display:flex;align-items:center;gap:5px;">{{ icon('tag', '0.9em') }} {{ r.request_id }}</span>
        <span class="tag tag-warn">{{ icon('clock', '0.9em') }} قيد المراجعة</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:.78rem">
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="color:var(--t3);font-weight:600;">{{ icon('credit_card', '0.9em') }} الطريقة:</span>
            <span style="font-weight:700;color:var(--t1)">{{ r.method_name or 'غير محدد' }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="color:var(--t3);font-weight:600;">{{ icon('money', '0.9em') }} المبلغ:</span>
            <span style="font-weight:800;color:var(--ok)">{{ format_price(r.amount) }}</span>
        </div>
        <div style="grid-column:1/-1;display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
            <span style="color:var(--t3);font-weight:600;">{{ icon('tag', '0.9em') }} رقم العملية:</span>
            <code style="font-family:'Courier New',monospace;background:var(--bg);padding:4px 10px;border-radius:6px;color:var(--accent-l);font-size:.82rem;direction:ltr;">{{ r.transaction_number or '-' }}</code>
        </div>
        {% if r.currency_type == 'USD' %}
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="color:var(--t3);font-weight:600;">{{ icon('money', '0.9em') }} المبلغ الأصلي:</span>
            <span style="font-weight:700;color:var(--accent-l)">{{ r.original_amount }}$</span>
        </div>
        {% endif %}
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="color:var(--t3);font-weight:600;">{{ icon('clock', '0.9em') }} التاريخ:</span>
            <span style="font-size:.72rem;color:var(--t2)">{{ r.created_at[:16] if r.created_at else '-' }}</span>
        </div>
    </div>
</div>
{% endfor %}
</div>
{% endif %}

<div class="card" style="margin-bottom:14px">
<h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('credit_card', '1em') }} طرق الشحن (اضغط على طريقة لفتح نافذة الشحن)</h3>
{% if methods %}
<div class="grid g3" id="topupMethodsGrid">
{% for m in methods %}
<div class="method-box" data-method-id="{{ m.id }}" data-method-name="{{ m.name }}" data-acc-num="{{ m.account_number or '' }}" data-acc-name="{{ m.account_name or '' }}" data-instructions="{{ m.instructions or '' }}" data-wallet-link="{{ m.wallet_link or '' }}" data-currency-type="{{ m.currency_type or 'SYP' }}" data-exchange-rate="{{ exchange_rate }}" onclick="openTopupModal(event, this)" style="cursor:pointer;">
{% if m.image_path %}<div class="method-box-img"><div class="img-skeleton"></div><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="/images/{{ m.image_path }}" alt="{{ m.name }}" class="lazy-img"></div>
{% else %}<div class="method-box-icon">{{ icon('credit_card', '2em') }}</div>{% endif %}
<div class="method-box-name">{{ m.name }}</div>
{% if m.currency_type == 'USD' %}<div class="method-box-desc" style="color:var(--accent-l)">{{ icon('money', '0.8em') }} عملة: USD</div>{% endif %}
</div>
{% endfor %}
</div>
{% else %}
<div class="empty" style="padding:20px"><div class="empty-text">لا توجد طرق شحن متاحة</div></div>
{% endif %}
</div>
</div>

<style>
.topup-modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    width: 100%; height: 100%;
    background: rgba(0,0,0,0.85);
    z-index: 100000;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 15px;
    box-sizing: border-box;
    -webkit-overflow-scrolling: touch;
}
.topup-modal-overlay.active {
    display: flex;
}
.topup-modal-box {
    background: var(--bg2);
    border: 1px solid var(--gbrd);
    border-radius: var(--r);
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    position: relative;
}
.topup-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--brd);
    position: sticky;
    top: 0;
    background: var(--bg2);
    z-index: 10;
    border-radius: var(--r) var(--r) 0 0;
}
.topup-modal-title {
    font-weight: 800;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--t1);
}
.topup-modal-close-btn {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    color: var(--err);
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.3rem;
    flex-shrink: 0;
}
.topup-modal-close-btn:active {
    transform: scale(0.9);
}
.topup-modal-body {
    padding: 20px;
}
.topup-modal-info {
    margin-bottom: 15px;
    font-size: .82rem;
    color: var(--t2);
    background: var(--bg2);
    padding: 12px;
    border-radius: var(--rs);
    border: 1px solid var(--brd);
}
.wallet-info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid var(--brd);
    gap: 10px;
    flex-wrap: wrap;
}
.wallet-info-row:last-child {
    border-bottom: none;
}
.wallet-info-label {
    font-size: .82rem;
    color: var(--t3);
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
}
.wallet-info-value {
    font-size: .85rem;
    font-weight: 800;
    color: var(--accent-l);
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    flex-wrap: wrap;
    word-break: break-all;
}
.wallet-info-value code {
    font-family: 'Courier New', monospace;
    font-size: .8rem;
    color: var(--t1);
    background: var(--bg);
    padding: 4px 10px;
    border-radius: 6px;
    word-break: break-all;
    max-width: 100%;
    display: inline-block;
    direction: ltr;
    text-align: left;
}
.wallet-info-copy-btn {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: .72rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    white-space: nowrap;
}
.wallet-info-copy-btn:active {
    transform: scale(0.95);
}
.wallet-external-link {
    color: var(--accent-l);
    text-decoration: none;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 8px 16px;
    background: rgba(124,58,237,0.1);
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: var(--rs);
}
@media(max-width:600px){
    .topup-modal-overlay {
        padding: 0;
    }
    .topup-modal-box {
        max-width: 100%;
        max-height: 100vh;
        height: 100vh;
        border-radius: 0;
    }
    .topup-modal-header {
        padding: 14px 16px;
    }
    .topup-modal-body {
        padding: 16px;
    }
    .wallet-info-row {
        flex-direction: column;
        align-items: stretch;
        gap: 6px;
    }
}
</style>

<div id="topupModal" class="topup-modal-overlay">
    <div class="topup-modal-box">
        <div class="topup-modal-header">
            <div class="topup-modal-title" id="topupModalTitle">{{ icon('credit_card', '1em') }} شحن المحفظة</div>
            <button type="button" class="topup-modal-close-btn" onclick="closeTopupModal()" title="إغلاق">{{ icon('close', '1.2em') }}</button>
        </div>
        <div class="topup-modal-body">
            <div class="topup-modal-info" id="topupModalInfo"></div>
            <form id="topupForm" onsubmit="submitTopupForm(event)">
                <input type="hidden" name="method_id" id="topup_method_id">
                <input type="hidden" name="currency_type" id="topup_currency_type" value="SYP">
                <div class="fg">
                    <label class="fl">{{ icon('money', '1em') }} <span id="topup_amount_label">المبلغ المطلوب شحنه</span></label>
                    <input class="fi" type="number" name="amount" id="topup_amount" required placeholder="أدخل المبلغ" min="1" step="0.01" oninput="calculateTopupConversion()">
                </div>
                <div class="fg" id="topupConvertedBox" style="display:none;">
                    <label class="fl">{{ icon('refresh', '1em') }} المبلغ المحوّل (ل.س)</label>
                    <input class="fi" type="text" id="topup_converted_amount" readonly style="font-weight:800;color:var(--ok);">
                    <input type="hidden" name="converted_amount" id="topup_hidden_converted_amount">
                </div>
                <div class="fg">
                    <label class="fl">{{ icon('tag', '1em') }} رقم العملية / الحوالة</label>
                    <input class="fi" type="text" name="transaction_number" id="topup_transaction_number" required placeholder="أدخل رقم العملية">
                </div>
                <button type="submit" class="btn bp bbl" id="topupSubmitBtn">{{ icon('upload', '1em') }} إرسال طلب الشحن</button>
            </form>
        </div>
    </div>
</div>

<script>
function openTopupModal(e, el) {
    e.preventDefault();
    e.stopPropagation();
    
    var id = el.getAttribute('data-method-id') || '';
    var name = el.getAttribute('data-method-name') || '';
    var accNum = el.getAttribute('data-acc-num') || '';
    var accName = el.getAttribute('data-acc-name') || '';
    var instr = el.getAttribute('data-instructions') || '';
    var wLink = el.getAttribute('data-wallet-link') || '';
    var curType = el.getAttribute('data-currency-type') || 'SYP';
    var exRate = parseFloat(el.getAttribute('data-exchange-rate') || 1);
    
    document.getElementById('topup_method_id').value = id;
    document.getElementById('topup_currency_type').value = curType;
    document.getElementById('topupModalTitle').innerHTML = '{{ icon("credit_card", "1em")|safe }} ' + name;
    
    var info = '';
    if(accNum && accNum !== 'None') {
        info += '<div class="wallet-info-row">' +
            '<span class="wallet-info-label">رقم المحفظة:</span>' +
            '<span class="wallet-info-value">' +
                '<code>' + accNum + '</code>' +
                '<button type="button" class="wallet-info-copy-btn" onclick="copyWalletText(this)" data-num="' + accNum + '">نسخ</button>' +
            '</span>' +
        '</div>';
    }
    if(accName && accName !== 'None') {
        info += '<div class="wallet-info-row">' +
            '<span class="wallet-info-label">اسم الحساب:</span>' +
            '<span class="wallet-info-value">' + accName + '</span>' +
        '</div>';
    }
    if(wLink && wLink !== 'None') {
        info += '<div class="wallet-info-row">' +
            '<span class="wallet-info-label">رابط المحفظة:</span>' +
            '<span class="wallet-info-value"><a href="' + wLink + '" target="_blank" class="wallet-external-link">اضغط هنا للفتح</a></span>' +
        '</div>';
    }
    if(curType === 'USD') {
        info += '<div class="wallet-info-row">' +
            '<span class="wallet-info-label">العملة:</span>' +
            '<span class="wallet-info-value" style="color:var(--accent-l)">دولار أمريكي (USD)</span>' +
        '</div>';
        info += '<div class="wallet-info-row">' +
            '<span class="wallet-info-label">سعر الصرف:</span>' +
            '<span class="wallet-info-value">1$ = ' + exRate + ' ل.س</span>' +
        '</div>';
        document.getElementById('topup_amount_label').innerText = 'المبلغ بالدولار (USD)';
        document.getElementById('topupConvertedBox').style.display = 'block';
    } else {
        document.getElementById('topup_amount_label').innerText = 'المبلغ بالليرة السورية (SYP)';
        document.getElementById('topupConvertedBox').style.display = 'none';
    }
    if(instr && instr !== 'None') {
        info += '<div style="margin-top:10px;padding-top:8px;border-top:1px dashed var(--brd);">' +
            '<div style="color:var(--warn);font-weight:700;font-size:.8rem;margin-bottom:6px;">تعليمات التحويل:</div>' +
            '<div style="white-space:pre-wrap;margin-top:5px;font-size:.78rem;color:var(--t2);line-height:1.6;">' + instr + '</div>' +
        '</div>';
    }
    document.getElementById('topupModalInfo').innerHTML = info;
    
    document.getElementById('topup_amount').value = '';
    document.getElementById('topup_transaction_number').value = '';
    
    var modal = document.getElementById('topupModal');
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeTopupModal() {
    var modal = document.getElementById('topupModal');
    modal.classList.remove('active');
    document.body.style.overflow = '';
}

function copyWalletText(btn) {
    var num = btn.getAttribute('data-num');
    var ta = document.createElement('textarea');
    ta.value = num;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    if(typeof showModal === 'function') {
        showModal('{{ icon("check_circle","2em")|safe }}', 'تم النسخ', 'تم نسخ رقم المحفظة بنجاح!');
    }
}

function calculateTopupConversion() {
    var curType = document.getElementById('topup_currency_type').value;
    if(curType !== 'USD') return;
    
    var amount = parseFloat(document.getElementById('topup_amount').value) || 0;
    var exRate = 1;
    var grid = document.getElementById('topupMethodsGrid');
    if(grid) {
        var usdBox = grid.querySelector('[data-currency-type="USD"]');
        if(usdBox) {
            exRate = parseFloat(usdBox.getAttribute('data-exchange-rate')) || 1;
        }
    }
    var converted = amount * exRate;
    document.getElementById('topup_converted_amount').value = converted.toFixed(2) + ' ل.س';
    document.getElementById('topup_hidden_converted_amount').value = converted.toFixed(2);
}

async function submitTopupForm(e) {
    e.preventDefault();
    var btn = document.getElementById('topupSubmitBtn');
    var methodId = document.getElementById('topup_method_id').value;
    var amount = document.getElementById('topup_amount').value;
    var txnNum = document.getElementById('topup_transaction_number').value;
    var curType = document.getElementById('topup_currency_type').value;
    var convertedAmount = document.getElementById('topup_hidden_converted_amount').value;
    
    if(!amount || amount <= 0) {
        if(typeof showModal === 'function') showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'يرجى إدخال مبلغ صحيح');
        return;
    }
    if(!txnNum) {
        if(typeof showModal === 'function') showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'يرجي إدخال رقم العملية');
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = 'جاري الإرسال...';
    
    try {
        var formData = new FormData();
        formData.append('method_id', methodId);
        formData.append('amount', amount);
        formData.append('transaction_number', txnNum);
        formData.append('currency_type', curType);
        if(curType === 'USD' && convertedAmount) {
            formData.append('converted_amount', convertedAmount);
        }
        
        var response = await fetch('/wallet/topup/confirm', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });
        
        var data = await response.json();
        
        if(data.success) {
            if(typeof showPopupNotification === 'function'){ showPopupNotification('✅ تم إرسال طلب شحن المحفظة', data.message || 'تم إرسال طلبك بنجاح وهو الآن قيد المراجعة من الإدارة', '{{ icon("check_circle","2em")|safe }}'); }
            if(typeof showModal === 'function'){ showModal('{{ icon("check_circle","2.4em")|safe }}', '✅ تم إرسال طلب الشحن بنجاح', data.message || 'تم إرسال طلب شحن المحفظة بنجاح! سيتم مراجعته وتأكيده من قبل الإدارة قريباً.'); }
            setTimeout(function(){
                closeTopupModal();
                window.location.href = data.redirect || '/wallet/topup/processing';
            }, 2000);
        } else {
            if(typeof showModal === 'function') showModal('{{ icon("x_circle","2em")|safe }}', 'فشل الإرسال', data.message || 'حدث خطأ غير متوقع');
        }
    } catch(err) {
        if(typeof showModal === 'function') showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'حدث خطأ في الاتصال بالخادم.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '{{ icon("upload","1em")|safe }} إرسال طلب الشحن';
    }
}

document.getElementById('topupModal').addEventListener('click', function(e) {
    if(e.target === this) {
        closeTopupModal();
    }
});
</script>
{% endblock %}"""

TOPUP_PROCESSING_TMPL = """{% extends "base" %}{% block content %}
<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:70vh;text-align:center;padding:20px">
    <div class="loader-rocket-container" style="margin-bottom:40px">
        <div class="loader-ring loader-ring-1"></div>
        <div class="loader-ring loader-ring-2"></div>
        <div class="loader-ring loader-ring-3"></div>
        <div class="loader-rocket">{{ icon('rocket', '3em') }}</div>
    </div>
    <h2 style="font-size:1.8rem;font-weight:900;background:var(--grad1);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:15px">تم إرسال طلبك بنجاح!</h2>
    <p style="font-size:1.1rem;color:var(--t2);line-height:1.8;margin-bottom:25px">جاري معالجة الطلب، يرجى الانتظار حتى تقوم الإدارة بمراجعة طلبك وتأكيده.<br>سيصلك إشعار فور تأكيد الطلب.</p>
    <div style="width:100%;max-width:400px;height:6px;background:var(--bg2);border-radius:3px;overflow:hidden;margin-bottom:30px">
        <div style="height:100%;background:var(--grad1);animation:progressFill 3s ease-in-out infinite"></div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center">
        <a href="/wallet" class="btn bp" style="text-decoration:none">{{ icon('wallet', '1em') }} العودة للمحفظة</a>
        <a href="/" class="btn bo" style="text-decoration:none">{{ icon('home', '1em') }} الصفحة الرئيسية</a>
    </div>
</div>
{% endblock %}"""

NOTIFICATIONS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('bell', '1.25em') }} الإشعارات</h1>
<div style="max-width:680px;margin:0 auto">
{% if notifications %}
<div style="text-align:center;margin-bottom:15px;">
    <button class="btn bsm bp" onclick="markAllNotifsRead()">{{ icon('check', '0.9em') }} تعليم الكل كمقروء</button>
</div>
{% for n in notifications %}
<div class="card" style="margin-bottom:10px; {% if not n.is_read %}border-color:var(--accent);{% endif %}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
<h3 style="font-size:.9rem;font-weight:800">{{ n.title }}</h3>
<span style="font-size:.7rem;color:var(--t3)">{{ n.created_at[:16] }}</span>
</div>
<p style="font-size:.82rem;color:var(--t2)">{{ n.message }}</p>
{% if not n.is_read %}<button class="btn bsm bp" style="margin-top:8px" onclick="markNotifRead({{ n.id }})">{{ icon('check', '1em') }} تعليم كمقروء</button>{% endif %}
</div>
{% endfor %}
{% else %}
<div class="empty"><div class="empty-icon">{{ icon('bell', '3em') }}</div><div class="empty-text">لا توجد إشعارات</div></div>
{% endif %}
</div>
<script>
function markNotifRead(id){fetch('/api/notification/read/'+id,{method:'POST'}).then(function(){location.reload()});}
function markAllNotifsRead(){fetch('/api/notifications/read-all',{method:'POST'}).then(function(r){return r.json();}).then(function(d){if(d.success) location.reload();});}
</script>
{% endblock %}"""

OFFERS_TMPL = """{% extends "base" %}{% block content %}
<h1 class="offers-page-title">{{ icon('tag', '1.5em') }} العروض الخاصة</h1>
<div style="max-width:1000px;margin:0 auto">
{% if offers and offers|length > 0 %}
{% for o in offers %}
<div class="offer-card">
    <div class="offer-badge-large">خصم {{ o.discount_percentage }}%</div>
    <div class="offer-title">{{ o.offer_title or o.product_name }}</div>
    {% if o.offer_description %}<div class="offer-desc">{{ o.offer_description }}</div>{% endif %}
    <div class="offer-prices">
        <span class="offer-original-price">{{ format_price(o.original_price) }}</span>
        <span class="offer-new-price">{{ format_price(o.offer_price) }}</span>
        <span class="offer-discount-percent">وفّر {{ format_price(o.original_price - o.offer_price) }}</span>
    </div>
    <button class="btn bp bbl" onclick="window.location.href='/product/{{ o.product_id }}'">{{ icon('cart', '1em') }} اعرض المنتج واشترِ الآن</button>
</div>
{% endfor %}
{% else %}
<div class="empty">
    <div class="empty-icon">{{ icon('tag', '3em') }}</div>
    <div class="empty-text">لا توجد عروض خاصة حالياً</div>
</div>
{% endif %}
</div>
{% endblock %}"""

WHEEL_TMPL = """{% extends "base" %}{% block content %}
<h1 class="wheel-page-title">{{ icon('wheel', '1.5em') }} عجلة الحظ</h1>
<div style="max-width:600px;margin:0 auto">
<div class="wheel-container">
    <div class="wheel-stats-box">
        <div class="wheel-stat-item">
            <div class="wheel-stat-value" id="userSpins">{{ user_spins }}</div>
            <div class="wheel-stat-label">الدورات المتاحة</div>
        </div>
        <div class="wheel-stat-item">
            <div class="wheel-stat-value">{{ total_spins }}</div>
            <div class="wheel-stat-label">إجمالي الدورات</div>
        </div>
        <div class="wheel-stat-item">
            <div class="wheel-stat-value">{{ format_price(total_winnings) }}</div>
            <div class="wheel-stat-label">إجمالي الجوائز</div>
        </div>
    </div>

    <div class="wheel-visual-container">
        <div class="wheel-pointer"></div>
        <svg class="wheel-svg" id="wheelSvg" viewBox="0 0 200 200">
            {% for g in gifts %}
            <path d="M 100 100 L {{ g.x1 }} {{ g.y1 }} A 100 100 0 0 1 {{ g.x2 }} {{ g.y2 }} Z" fill="{{ g.color }}" stroke="#fff" stroke-width="2"></path>
            <text x="{{ g.tx }}" y="{{ g.ty }}" fill="#fff" font-size="10" font-weight="bold" text-anchor="middle" transform="rotate({{ g.angle }} {{ g.tx }} {{ g.ty }})">{{ g.icon }}</text>
            <text x="{{ g.tx2 }}" y="{{ g.ty2 }}" fill="#fff" font-size="6" font-weight="bold" text-anchor="middle" transform="rotate({{ g.angle }} {{ g.tx2 }} {{ g.ty2 }})">{{ g.name[:10] }}</text>
            {% endfor %}
            <circle cx="100" cy="100" r="80" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="2"></circle>
        </svg>
        <div class="wheel-center">{{ icon('gift', '1.5em') }}</div>
    </div>

    <button class="wheel-spin-btn" id="spinBtn" onclick="spinWheel()" {% if user_spins <= 0 %}disabled{% endif %}>
        {{ icon('wheel', '1.2em') }} أدر العجلة الآن!
    </button>

    <div class="wheel-result-box" id="wheelResultBox">
        <div class="wheel-result-icon" id="wheelResultIcon"></div>
        <div class="wheel-result-text" id="wheelResultText"></div>
        <div class="wheel-result-amount" id="wheelResultAmount"></div>
    </div>

    <div class="wheel-info-box">
        <div class="wheel-info-title">{{ icon('info', '1em') }} كيفية الحصول على دورات؟</div>
        <div class="wheel-info-text">يحصل المستخدم على دورات مجانية في عجلة الحظ عند صرف مبالغ معينة في المتجر.</div>
        <div class="wheel-thresholds-list">
            {% for t in thresholds %}
            <div class="wheel-threshold-item">
                <span class="wheel-threshold-amount">عند صرف {{ format_price(t.threshold_amount) }}</span>
                <span class="wheel-threshold-spins">+ {{ t.spins_awarded }} دورة</span>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
</div>

<script>
var isSpinning = false;
function spinWheel() {
    if (isSpinning) return;
    var spinsEl = document.getElementById('userSpins');
    var currentSpins = parseInt(spinsEl.textContent);
    if (currentSpins <= 0) {
        showModal('{{ icon("warning","2em")|safe }}', 'تنبيه', 'لا توجد دورات متاحة حالياً. قم بالشراء للحصول على دورات مجانية!');
        return;
    }
    
    isSpinning = true;
    var spinBtn = document.getElementById('spinBtn');
    spinBtn.disabled = true;
    spinBtn.innerHTML = '{{ icon("clock","1.2em")|safe }} جاري الدوران...';
    
    var wheelSvg = document.getElementById('wheelSvg');
    var randomRotation = 1440 + Math.floor(Math.random() * 360);
    wheelSvg.style.transform = 'rotate(' + randomRotation + 'deg)';
    
    setTimeout(function() {
        fetch('/api/wheel/spin', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                var resultBox = document.getElementById('wheelResultBox');
                var resultIcon = document.getElementById('wheelResultIcon');
                var resultText = document.getElementById('wheelResultText');
                var resultAmount = document.getElementById('wheelResultAmount');
                
                if (data.success) {
                    resultIcon.innerHTML = data.gift_icon || '{{ icon("gift","3em")|safe }}';
                    resultText.textContent = data.message;
                    if (data.amount_value > 0) {
                        resultAmount.textContent = 'الفائز بـ: ' + data.amount_str;
                        resultAmount.style.color = 'var(--ok)';
                    } else {
                        resultAmount.textContent = 'حظ أوفر';
                        resultAmount.style.color = 'var(--t3)';
                    }
                    resultBox.classList.add('show');
                    
                    spinsEl.textContent = data.remaining_spins;
                    if (data.balance) {
                        var balEl = document.querySelector('.header-balance-box');
                        if (balEl) balEl.innerText = '{{ icon("wallet","1em") }} ' + data.balance;
                    }
                } else {
                    showModal('{{ icon("x_circle","2em")|safe }}', 'خطأ', data.message);
                }
                
                isSpinning = false;
                spinBtn.disabled = false;
                spinBtn.innerHTML = '{{ icon("wheel","1.2em")|safe }} أدر مرة أخرى';
            })
            .catch(err => {
                showModal('{{ icon("warning","2em")|safe }}', 'خطأ', 'حدث خطأ في الاتصال.');
                isSpinning = false;
                spinBtn.disabled = false;
                spinBtn.innerHTML = '{{ icon("wheel","1.2em")|safe }} أدر العجلة الآن!';
            });
    }, 5000);
}
</script>
{% endblock %}"""

SUPPORT_TMPL = """{% extends "base" %}{% block content %}
<h1 class="section-title">{{ icon('support', '1.25em') }} الدعم الفني - التذاكر</h1>
<div style="max-width:800px;margin:0 auto">
    <div class="card">
        <h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('ticket', '1em') }} إنشاء تذكرة دعم جديدة</h3>
        <form method="POST" action="/support/create">
            <div class="fg"><label class="fl">{{ icon('edit', '1em') }} الموضوع</label><input class="fi" type="text" name="subject" required placeholder="موضوع المشكلة"></div>
            <div class="fg"><label class="fl">{{ icon('support', '1em') }} الرسالة</label><textarea class="fi" name="message" required rows="5" placeholder="اكتب تفاصيل المشكلة"></textarea></div>
            <button type="submit" class="btn bp bbl">{{ icon('send', '1em') }} إرسال التذكرة</button>
        </form>
    </div>
    {% if tickets %}
    <h3 style="margin-top:20px;font-weight:800;display:flex;align-items:center;gap:8px">{{ icon('ticket', '1em') }} تذاكري السابقة</h3>
    <div class="table-w">
        <table>
            <thead><tr><th>رقم التذكرة</th><th>الموضوع</th><th>الحالة</th><th>التاريخ</th><th>عرض</th></tr></thead>
            <tbody>
            {% for t in tickets %}
            <tr>
                <td style="font-size:.72rem;direction:ltr">{{ t.ticket_id }}</td>
                <td style="font-weight:700">{{ t.subject }}</td>
                <td>{% if t.status == 'open' %}<span class="tag tag-ok">مفتوحة</span>{% else %}<span class="tag tag-warn">مغلقة</span>{% endif %}</td>
                <td style="font-size:.72rem">{{ t.created_at[:16] }}</td>
                <td><a href="/support/ticket/{{ t.id }}" class="btn bsm bo" style="text-decoration:none">{{ icon('eye', '1em') }} عرض</a></td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="empty" style="margin-top:20px"><div class="empty-icon">{{ icon('ticket', '3em') }}</div><div class="empty-text">لا توجد تذاكر سابقة</div></div>
    {% endif %}
</div>
{% endblock %}"""

SUPPORT_TICKET_TMPL = """{% extends "base" %}{% block content %}
<a href="/support" style="color:var(--accent-l);text-decoration:none;display:inline-flex;align-items:center;gap:5px;margin-bottom:12px;font-weight:700">{{ icon('arrow_back', '1em') }} العودة للدعم</a>
<div style="max-width:800px;margin:0 auto">
    <div class="card">
        <h3 style="font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px">{{ icon('ticket', '1em') }} {{ ticket.subject }}</h3>
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--brd);font-size:.82rem;color:var(--t3)">
            <span>رقم التذكرة: <b style="color:var(--t1);direction:ltr">{{ ticket.ticket_id }}</b></span>
            <span>الحالة: {% if ticket.status == 'open' %}<span class="tag tag-ok">مفتوحة</span>{% else %}<span class="tag tag-warn">مغلقة</span>{% endif %}</span>
        </div>
        <div style="margin-top:15px;max-height:400px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;">
            {% for m in messages %}
            <div style="padding:10px 14px;border-radius:12px;max-width:80%;{% if m.is_from_admin %}background:var(--accent);color:#fff;align-self:flex-start;{% else %}background:var(--bg2);color:var(--t1);align-self:flex-end;{% endif %}">
                <div style="font-size:.82rem;margin-bottom:5px;font-weight:600;">{% if m.is_from_admin %}الدعم:{% else %}أنا:{% endif %}</div>
                <div style="font-size:.88rem;line-height:1.5;">{{ m.message }}</div>
                <div style="font-size:.65rem;text-align:left;margin-top:5px;opacity:0.7;">{{ m.created_at[:16] }}</div>
            </div>
            {% endfor %}
        </div>
        <form method="POST" action="/support/ticket/{{ ticket.id }}/reply" style="margin-top:20px">
            <div class="fg"><textarea class="fi" name="message" required rows="3" placeholder="اكتب ردك هنا..."></textarea></div>
            <button type="submit" class="btn bp bbl">{{ icon('send', '1em') }} إرسال الرد</button>
        </form>
    </div>
</div>
{% endblock %}"""

# ==============================================================================
# تطبيق Flask (Routes - واجهة العميل فقط)
# ==============================================================================

app = Flask(__name__)
WEB_SECRET_KEY = db.get_setting("web_secret_key")
if not WEB_SECRET_KEY:
    WEB_SECRET_KEY = secrets.token_hex(32)
    db.set_setting("web_secret_key", WEB_SECRET_KEY)
app.secret_key = WEB_SECRET_KEY
app.permanent_session_lifetime = timedelta(days=365 * 10) # 10 years long session

templates_map = {
    "base": BASE_TMPL, "home": HOME_TMPL, "category": CATEGORY_TMPL, "product": PRODUCT_TMPL,
    "shipping_checkout": SHIPPING_CHECKOUT_TMPL,
    "order_success": ORDER_SUCCESS_TMPL, "orders": ORDERS_TMPL, "order_details": ORDER_DETAILS_TMPL,
    "favorites": FAVORITES_TMPL, "wallet": WALLET_TMPL, "wallet_topup": WALLET_TOPUP_TMPL,
    "categories_list": CATEGORIES_LIST_TMPL, "support": SUPPORT_TMPL,
    "support_ticket": SUPPORT_TICKET_TMPL, "maintenance": MAINTENANCE_HTML,
    "notifications": NOTIFICATIONS_TMPL, "banned": BANNED_PAGE_HTML,
    "gifts": GIFTS_TMPL, "cart": CART_TMPL, "compare": COMPARE_TMPL,
    "faq": FAQ_TMPL, "blog": BLOG_TMPL, "blog_post": BLOG_POST_TMPL,
    "error_404": ERROR_404_TMPL, "profile": PROFILE_TMPL,
    "achievements": ACHIEVEMENTS_TMPL, "contests": CONTESTS_TMPL,
    "menu_page": MENU_PAGE_TMPL,                  
    "support_chat_page": SUPPORT_CHAT_PAGE_TMPL,
    "offers": OFFERS_TMPL, "wheel": WHEEL_TMPL,
    "topup_processing": TOPUP_PROCESSING_TMPL
}

def tojson_filter(value):
    return json.dumps(value, ensure_ascii=False)

jinja_env = Environment(loader=DictLoader(templates_map), autoescape=True)
jinja_env.globals.update({
    "format_price": format_price,
    "icon": lambda name, size="1em", extra_class="": Markup(icon(name, size, extra_class))
})
jinja_env.filters.update({"length": len, "tojson": tojson_filter})

def render(tmpl_name, **kwargs):
    kwargs.setdefault("css", SITE_CSS)
    kwargs.setdefault("store_name", db.get_setting("store_name", "MO STORE"))
    kwargs.setdefault("store_description", db.get_setting("store_description", ""))
    kwargs.setdefault("store_logo", db.get_setting("store_logo", ""))
    kwargs.setdefault("site_icon", db.get_setting("site_icon", ""))
    kwargs.setdefault("site_background", db.get_setting("site_background", ""))
    kwargs.setdefault("title", kwargs.get("title", "الصفحة"))
    kwargs.setdefault("active_page", "")
    kwargs.setdefault("logged_in", "user_id" in session)
    kwargs.setdefault("balance", "")
    kwargs.setdefault("notifications_count", 0)
    kwargs.setdefault("user_notifications", [])
    kwargs.setdefault("instructions", "")
    kwargs.setdefault("currency_symbol", db.get_setting("currency", CURRENCY))
    kwargs.setdefault("session_currency", session.get("currency", db.get_setting("currency", CURRENCY)))
    kwargs.setdefault("profit_percentage", float(db.get_setting("profit_percentage", "15")))
    kwargs.setdefault("welcome_popup_title", db.get_setting("welcome_popup_title", "أهلاً وسهلاً بك في MO STORE!"))
    kwargs.setdefault("welcome_popup_message", db.get_setting("welcome_popup_message", "نحن سعيدون بزيارتك! اكتشف مجموعتنا الواسعة."))
    kwargs.setdefault("welcome_popup_image", db.get_setting("welcome_popup_image", ""))
    kwargs.setdefault("support_whatsapp", db.get_setting("support_whatsapp", ""))
    kwargs.setdefault("support_telegram", db.get_setting("support_telegram", ""))
    kwargs.setdefault("session_username", session.get("username", ""))
    kwargs.setdefault("session_user_id", session.get("user_id", "-"))
    kwargs.setdefault("site_entry_notif_title", db.get_setting("site_entry_notif_title", "مرحباً بك في متجرنا الراقي!"))
    kwargs.setdefault("site_entry_notif_message", db.get_setting("site_entry_notif_message", "تصفح أحدث المنتجات بأفضل الأسعار."))
    kwargs.setdefault("WEB_URL", WEB_URL)
    kwargs.setdefault("cart_count", 0)
    kwargs.setdefault("footer_text", db.get_setting("footer_text", "© 2025 MO STORE - جميع الحقوق محفوظة"))
    kwargs.setdefault("promo_bar_text", db.get_setting("promo_bar_text", "") if db.get_setting("enable_promo_bar", "1") == "1" else "")
    kwargs.setdefault("promo_bar_link", db.get_setting("promo_bar_link", ""))
    kwargs.setdefault("social_links", {
        "facebook": db.get_setting("social_facebook", ""),
        "instagram": db.get_setting("social_instagram", ""),
        "telegram": db.get_setting("support_telegram", ""),
        "whatsapp": db.get_setting("support_whatsapp", ""),
    })
    kwargs.setdefault("stats", get_site_stats())
    kwargs.setdefault("vip_benefits", db.get_setting("vip_benefits", "خصم 5% على جميع المنتجات"))
    kwargs.setdefault("popup_notif_duration", db.get_setting("popup_notif_duration", "5"))
    kwargs.setdefault("enable_popup_notifications", db.get_setting("enable_popup_notifications", "1"))
    kwargs.setdefault("show_bottom_offers", db.get_setting("enable_offers_section", "1") == "1")
    kwargs.setdefault("active_offers", get_all_active_offers())
    kwargs.setdefault("exchange_rate", db.get_setting("price_exchange_rate", "15000"))

    top_ads_images, top_ads_text = get_top_ads()
    kwargs.setdefault("top_ads_images", top_ads_images)
    kwargs.setdefault("top_ads_text", top_ads_text)

    if "user_id" in session:
        user = db.execute("SELECT balance, avatar_path, is_vip, vip_level, is_banned, ban_reason FROM users WHERE id=?", (session["user_id"],), fetchone=True)
        if user:
            kwargs["balance"] = format_price(user["balance"])
            kwargs["user_avatar"] = user["avatar_path"] if user["avatar_path"] else ""
            is_vip, vip_level = check_vip_status(session["user_id"])
            kwargs["is_vip"] = is_vip
            kwargs["vip_level"] = vip_level
            kwargs["vip_level_name"] = get_vip_level_name(vip_level)
            kwargs["vip_badge"] = get_vip_badge(vip_level)
            
            ref_code_row = db.execute("SELECT referral_code FROM users WHERE id=?", (session["user_id"],), fetchone=True)
            if ref_code_row and ref_code_row["referral_code"]:
                bot_un = get_current_bot_username()
                kwargs["referral_link"] = f"https://t.me/{bot_un}?start=ref_{ref_code_row['referral_code']}"
                kwargs["referral_bot_username"] = bot_un
            else:
                kwargs["referral_link"] = ""
                kwargs["referral_bot_username"] = get_current_bot_username()
            
            notifs_and_cart = db.execute(
                """SELECT 
                    (SELECT COUNT(*) FROM notifications WHERE (user_id=? OR is_broadcast=1) AND is_read=0) as notif_count,
                    (SELECT COUNT(*) FROM cart_items WHERE user_id=?) as cart_count
                """,
                (session["user_id"], session["user_id"]),
                fetchone=True
            )
            if notifs_and_cart:
                kwargs["notifications_count"] = notifs_and_cart["notif_count"]
                kwargs["cart_count"] = notifs_and_cart["cart_count"]
            
            if notifs_and_cart and notifs_and_cart["notif_count"] > 0:
                notifs = db.execute(
                    "SELECT * FROM notifications WHERE (user_id=? OR is_broadcast=1) AND is_read=0 ORDER BY created_at DESC LIMIT 10",
                    (session["user_id"],), fetch=True
                ) or []
                kwargs["user_notifications"] = [dict(n) for n in notifs]
            else:
                kwargs["user_notifications"] = []
        else:
            kwargs["is_vip"] = False
            kwargs["vip_level"] = 0
            kwargs["vip_level_name"] = "عادي"
            kwargs["vip_badge"] = ""
            kwargs["user_avatar"] = ""
            kwargs["cart_count"] = 0
            kwargs["notifications_count"] = 0
            kwargs["user_notifications"] = []
            kwargs["referral_link"] = ""
    else:
        kwargs["is_vip"] = False
        kwargs["vip_level"] = 0
        kwargs["vip_level_name"] = "عادي"
        kwargs["vip_badge"] = ""
        kwargs["user_avatar"] = ""
        kwargs["cart_count"] = 0
        kwargs["notifications_count"] = 0
        kwargs["user_notifications"] = []
        kwargs["referral_link"] = ""

    try:
        template = jinja_env.get_template(tmpl_name)
        return template.render(**kwargs)
    except Exception as e:
        return f"<div style='color:red;padding:20px;direction:rtl;text-align:right'>خطأ في القالب: {str(e)}<br><pre>{traceback.format_exc()}</pre></div>"

_virtual_methods_initialized = False

@app.before_request
def before_request():
    global _virtual_methods_initialized
    if not _virtual_methods_initialized:
        ensure_virtual_topup_methods()
        _virtual_methods_initialized = True
    
    if "currency" not in session or session.get("currency") not in ("SYP", "USD"):
        _cur_setting = str(db.get_setting("currency", CURRENCY) or "").strip().upper()
        session["currency"] = "USD" if _cur_setting in ("USD", "$", "دولار") else "SYP"

    ref_code = request.args.get('ref', type=str)
    if ref_code and ref_code.startswith("ref_"):
        actual_code = ref_code[4:]
        referrer = db.execute("SELECT id FROM users WHERE referral_code=?", (actual_code,), fetchone=True)
        if referrer:
            session.permanent = True
            session["pending_referrer"] = referrer["id"]

    tg_id = request.args.get('tg_id', type=int)
    if tg_id:
        tg_username = request.args.get('tg_username', type=str)
        try:
            referrer_id = session.get("pending_referrer")
            user = get_or_create_user(tg_id, tg_username, referrer_id=referrer_id)
            if user:
                session.permanent = True
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                if referrer_id:
                    session.pop("pending_referrer", None)
                db.execute("UPDATE users SET last_activity=CURRENT_TIMESTAMP WHERE id=?", (user["id"],))
        except Exception:
            pass
            
    username_param = request.args.get('username', type=str)
    user_identifier_param = request.args.get('user_id', type=str)
    if username_param and user_identifier_param:
        user = db.execute("SELECT * FROM users WHERE telegram_id=?", (user_identifier_param,), fetchone=True)
        if not user:
            try:
                user_id_int = int(user_identifier_param)
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id_int,), fetchone=True)
            except ValueError:
                pass
                
        if user and user["username"] == username_param:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            db.execute("UPDATE users SET last_activity=CURRENT_TIMESTAMP, last_login=CURRENT_TIMESTAMP WHERE id=?", (user["id"],))

    path = request.path
    if (path.startswith('/images/') or 
        path == '/favicon.ico' or 
        path.startswith('/api/notifications/check') or
        path.startswith('/api/chat/messages') or
        path.startswith('/api/notifications/latest') or
        path.startswith('/api/notifications/unread') or
        path.startswith('/api/search')):
        return None

    if "user_id" in session:
        try:
            user = db.execute("SELECT is_banned, ban_reason, username, created_at FROM users WHERE id=?", (session["user_id"],), fetchone=True)
            if user and user["is_banned"] == 1:
                if session.get("role") not in ["admin", "supporter"]:
                    return render("banned", 
                        store_name=db.get_setting("store_name", "MO STORE"),
                        username=user["username"], 
                        ban_reason=user["ban_reason"], 
                        banned_at=str(user["created_at"][:16] if user["created_at"] else ''),
                        support_whatsapp=db.get_setting("support_whatsapp", ""), 
                        support_telegram=db.get_setting("support_telegram", ""))
        except Exception:
            pass

    if not path.startswith('/api/'):
        try:
            maint_mode = db.get_setting("maintenance_mode", "off")
            if maint_mode == "on" and session.get("role") not in ["admin", "supporter"]:
                active, info = is_maintenance_active()
                if active:
                    remaining = get_maintenance_remaining()
                    msg = info["message"] if info and info["message"] else db.get_setting("maintenance_message", "الموقع تحت الصيانة")
                    maint_images = get_maintenance_images()
                    return render("maintenance",
                        store_name=db.get_setting("store_name", "MO STORE"),
                        message=msg, remaining=remaining,
                        support_whatsapp=db.get_setting("support_whatsapp", ""),
                        support_telegram=db.get_setting("support_telegram", ""),
                        maintenance_images=maint_images)
        except Exception:
            pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False, 
                    "message": "يجب تسجيل الدخول أولاً لإتمام عملية الشراء", 
                    "redirect": True,
                    "type": "auth"
                }), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Not Found"}), 404
    return render("error_404", title="صفحة غير موجودة"), 404

@app.route("/login")
def login_page():
    bot_username = get_current_bot_username()
    return redirect(f"https://t.me/{bot_username}?start=1")

@app.route("/api/currency/switch", methods=["POST"])
def api_switch_currency():
    current = session.get("currency", "SYP")
    if current == "USD":
        session["currency"] = "SYP"
        new_cur = "SYP"
    else:
        session["currency"] = "USD"
        new_cur = "USD"
    session.modified = True
    rate = db.get_setting("price_exchange_rate", "15000")
    msg = "تم تحويل عرض الأسعار إلى الدولار الأمريكي ($)" if new_cur == "USD" else "تم تحويل عرض الأسعار إلى الليرة السورية (ل.س)"
    return jsonify({"success": True, "currency": new_cur, "rate": rate, "message": msg})

@app.route("/")
def index():
    root_cats = get_hierarchical_categories()
    cat_list = []
    all_counts = db.execute("SELECT category_id, COUNT(*) as c FROM products WHERE is_active=1 GROUP BY category_id", fetch=True) or []
    count_map = {p["category_id"]: p["c"] for p in all_counts}
    
    def count_with_subcats(cat_id):
        all_ids = get_all_subcategory_ids(cat_id)
        return sum(count_map.get(cid, 0) for cid in all_ids)
    
    for cat in root_cats:
        c = dict(cat)
        c["product_count"] = count_with_subcats(c["id"])
        c["emoji"] = "📦"
        cat_list.append(c)
    
    best_sellers = get_best_sellers(10)
    new_arrivals = get_new_arrivals(10)
    stats = get_site_stats()
    
    return render("home", title="الرئيسية", active_page="home", categories=cat_list, best_sellers=best_sellers, new_arrivals=new_arrivals, stats=stats)

@app.route("/menu")
def menu_page_route():
    return render("menu_page", title="القائمة", active_page="menu")

@app.route("/offers")
def offers_page():
    offers = get_all_active_offers()
    return render("offers", title="العروض الخاصة", active_page="offers", offers=offers)

@app.route("/wheel")
@login_required
def wheel_page():
    user_spins, total_spins, total_winnings = get_user_wheel_spins(session["user_id"])
    gifts = get_wheel_gifts()
    thresholds = get_spin_thresholds()
    
    num_gifts = len(gifts)
    angle_step = 360 / num_gifts if num_gifts > 0 else 360
    
    for i, g in enumerate(gifts):
        start_angle = i * angle_step - 90
        end_angle = (i + 1) * angle_step - 90
        g["x1"] = 100 + 100 * math.cos(math.radians(start_angle))
        g["y1"] = 100 + 100 * math.sin(math.radians(start_angle))
        g["x2"] = 100 + 100 * math.cos(math.radians(end_angle))
        g["y2"] = 100 + 100 * math.sin(math.radians(end_angle))
        mid_angle = (start_angle + end_angle) / 2
        g["tx"] = 100 + 60 * math.cos(math.radians(mid_angle))
        g["ty"] = 100 + 60 * math.sin(math.radians(mid_angle))
        g["tx2"] = 100 + 40 * math.cos(math.radians(mid_angle))
        g["ty2"] = 100 + 40 * math.sin(math.radians(mid_angle))
        g["angle"] = mid_angle + 90
        
    return render("wheel", title="عجلة الحظ", active_page="wheel", user_spins=user_spins, total_spins=total_spins, total_winnings=total_winnings, gifts=gifts, thresholds=thresholds)

@app.route("/support/chat")
def support_chat_page():
    return render("support_chat_page", title="الدعم المباشر", active_page="support")

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"products": []})
    prods = db.execute("SELECT id, name, sell_price FROM products WHERE is_active=1 AND (name LIKE ? OR description LIKE ?) ORDER BY id DESC LIMIT 10", (f"%{query}%", f"%{query}%"), fetch=True) or []
    results = []
    for p in prods:
        results.append({"id": p["id"], "name": p["name"], "price": format_price(p["sell_price"])})
    return jsonify({"products": results})

@app.route("/api/quick-view/<int:prod_id>")
def api_quick_view(prod_id):
    prod = db.execute("SELECT id, name, description, sell_price, image_url, image_path FROM products WHERE id=? AND is_active=1", (prod_id,), fetchone=True)
    if not prod:
        return jsonify({"success": False, "message": "المنتج غير موجود"})
    img_url = prod["image_url"] if prod["image_url"] else (f"/images/{prod['image_path']}" if prod["image_path"] else "")
    return jsonify({
        "success": True,
        "name": prod["name"],
        "description": prod["description"] or "",
        "price": format_price(prod["sell_price"]),
        "image_url": img_url
    })

@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()
    products = []
    if query:
        prods = db.execute("SELECT * FROM products WHERE is_active=1 AND (name LIKE ? OR description LIKE ?) ORDER BY id DESC LIMIT 50", (f"%{query}%", f"%{query}%"), fetch=True) or []
        products = [dict(p) for p in prods]
    cat_mock = {"name": f"نتائج البحث عن: {query}", "description": "", "image_url": "", "image_path": "", "emoji": "🔍"}
    return render("category", title=f"بحث: {query}", category=cat_mock, products=products, subcategories=[])

@app.route("/categories")
def categories_page():
    root_cats = get_hierarchical_categories()
    all_prods = db.execute("SELECT category_id, COUNT(*) as c FROM products WHERE is_active=1 GROUP BY category_id", fetch=True) or []
    count_map = {p["category_id"]: p["c"] for p in all_prods}
    cat_list = []
    for cat in root_cats:
        c = dict(cat)
        c["product_count"] = count_map.get(c["id"], 0)
        c["emoji"] = "📦"
        if "subcategories" not in c:
            c["subcategories"] = []
        for subcat in c["subcategories"]:
            subcat["product_count"] = count_map.get(subcat["id"], 0)
            subcat["emoji"] = "📦"
        cat_list.append(c)
    return render("categories_list", title="الأقسام", active_page="categories", categories=cat_list)

@app.route("/category/<int:cat_id>")
def category_page(cat_id):
    cat = db.execute("SELECT * FROM categories WHERE id=? AND is_active=1", (cat_id,), fetchone=True)
    if not cat:
        abort(404)
    cat_dict = dict(cat)
    cat_dict["emoji"] = "📦"
    
    subcats_raw = db.execute("SELECT * FROM categories WHERE parent_id=? AND is_active=1 ORDER BY sort_order ASC, id ASC", (cat_dict.get("api_category_id") or "0",), fetch=True) or []
    subcategories = []
    for subcat in subcats_raw:
        subcat_dict = dict(subcat)
        subcat_dict["product_count"] = get_products_count_for_category(subcat["id"])
        subcat_dict["emoji"] = "📦"
        sub_sub_cats = db.execute("SELECT * FROM categories WHERE parent_id=? AND is_active=1 ORDER BY sort_order ASC, id ASC", (subcat_dict.get("api_category_id") or "0",), fetch=True) or []
        for s in sub_sub_cats:
            s_dict = dict(s)
            s_dict["emoji"] = "📦"
            subcat_dict["subcategories"].append(s_dict)
        subcategories.append(subcat_dict)
    
    products = db.execute("SELECT * FROM products WHERE category_id=? AND is_active=1 ORDER BY sort_order ASC, id", (cat_id,), fetch=True) or []
    prod_list = [dict(p) for p in products]
    return render("category", title=cat["name"], active_page="categories", category=cat_dict, products=prod_list, subcategories=subcategories)

@app.route("/product/<int:prod_id>")
def product_page(prod_id):
    prod = db.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=? AND p.is_active=1", (prod_id,), fetchone=True)
    if not prod:
        abort(404)
    db.execute("UPDATE products SET views = views + 1 WHERE id=?", (prod_id,))
    prod_dict = dict(prod)
    qty_options_parsed = parse_qty_options(prod_dict.get("qty_options"))
    required_fields_list = parse_required_fields(prod_dict.get("required_fields"))
    all_images = get_product_images(prod_dict)
    instructions = prod_dict.get("instructions") or ""
    active_offer = get_active_product_offer(prod_id)
    
    if active_offer:
        discount_factor = 1 - (float(active_offer["discount_percentage"]) / 100)
        for opt in qty_options_parsed:
            if opt.get("price") and float(opt["price"]) > 0:
                opt["original_price"] = float(opt["price"])
                opt["price"] = round(float(opt["price"]) * discount_factor, 2)
    
    related_prods = get_related_products(prod_id, prod_dict.get("category_id"))
    reviews = get_product_reviews(prod_id)
    rating = get_product_rating(prod_id)
    
    if "user_id" in session:
        add_recently_viewed(session["user_id"], prod_id)
        recently_viewed_prods = get_recently_viewed(session["user_id"])
        check_and_award_achievements(session["user_id"])
    else:
        recently_viewed_prods = []
        
    return render("product", title=prod["name"], active_page="", product=prod_dict, all_images=all_images, qty_options_parsed=qty_options_parsed, required_fields_list=required_fields_list, instructions=instructions, related_products=related_prods, recently_viewed=recently_viewed_prods, reviews=reviews, rating=rating, active_offer=active_offer)

@app.route("/gifts")
def gifts_page():
    gifts = get_active_gifts()
    return render("gifts", title="أكواد الهدايا", active_page="gifts", gifts=gifts)

@app.route("/api/gift/buy/<int:gift_id>", methods=["POST"])
@login_required
def api_buy_gift(gift_id):
    gift, order_id_or_err = buy_gift_code(gift_id, session["user_id"])
    if not gift:
        err_type = "balance" if "رصيدك غير كافٍ" in order_id_or_err else "error"
        return jsonify({"success": False, "type": err_type, "message": order_id_or_err})
    user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
    check_and_award_achievements(session["user_id"])
    return jsonify({
        "success": True,
        "message": f"تم شراء كود الهدية ({gift['name']}) بنجاح!",
        "code": gift["code"],
        "balance": format_price(user["balance"]) if user else ""
    })

_user_buy_locks = {}
_user_buy_locks_master = threading.Lock()

def get_user_buy_lock(user_id):
    with _user_buy_locks_master:
        if user_id not in _user_buy_locks:
            _user_buy_locks[user_id] = threading.Lock()
        return _user_buy_locks[user_id]

@app.route("/api/buy", methods=["POST"])
@login_required
def api_buy_product():
    user_id = session["user_id"]
    lock = get_user_buy_lock(user_id)
    if not lock.acquire(blocking=False):
        return jsonify({"success": False, "message": "لديك طلب قيد المعالجة بالفعل. يرجى الانتظار."})
    
    try:
        actual_prod_id = request.form.get("product_id")
        if not actual_prod_id:
            return jsonify({"success": False, "message": "معرف المنتج مفقود"})
        try:
            actual_prod_id = int(actual_prod_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "معرف المنتج غير صالح"})

        recent_order = db.execute(
            "SELECT id FROM purchase_orders WHERE user_id=? AND status='processing' AND created_at > datetime('now', '-15 seconds')",
            (session["user_id"],), fetchone=True
        )
        if recent_order:
            return jsonify({"success": False, "message": "لديك طلب قيد المعالجة بالفعل. يرجى الانتظار."})
        
        prod_row = db.execute("SELECT * FROM products WHERE id=? AND is_active=1", (actual_prod_id,), fetchone=True)
        if not prod_row:
            return jsonify({"success": False, "message": "المنتج غير موجود أو غير متاح"})
        prod = row_to_dict(prod_row)
        
        if prod.get("stock_quantity", 1) == 0:
            return jsonify({"success": False, "message": "هذا المنتج غير متوفر حالياً (نفد المخزون)."})
        
        qty = request.form.get("quantity", "1")
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            qty = 1
        if qty < 1: qty = 1
        
        min_q = prod.get("min_quantity") or 1
        max_q = prod.get("max_quantity") or 0
        if qty < min_q: qty = min_q
        if max_q > 0 and qty > max_q: qty = max_q
        
        selected_option_idx_str = request.form.get("selected_option_index", "").strip()
        selected_option_label = request.form.get("selected_option_label", "").strip()
        variant_api_id = request.form.get("variant_api_id", "").strip()
        
        qty_opts = parse_qty_options(prod.get("qty_options"))
        if qty_opts and len(qty_opts) > 0 and not selected_option_idx_str:
            return jsonify({
                "success": False, 
                "message": "يجب اختيار خيار من القائمة المنسدلة قبل الشراء"
            })
        
        active_offer = get_active_product_offer(actual_prod_id)
        if active_offer:
            unit_price = float(active_offer["offer_price"])
        else:
            unit_price = float(prod.get("sell_price") or 0)

        if selected_option_idx_str:
            try:
                idx = int(selected_option_idx_str)
                if qty_opts and 0 <= idx < len(qty_opts):
                    opt = qty_opts[idx]
                    if opt.get("price") and float(opt["price"]) > 0:
                        unit_price = float(opt["price"])
                    if opt.get("api_id"):
                        variant_api_id = str(opt["api_id"])
                    if opt.get("label"):
                        selected_option_label = str(opt["label"])
            except (ValueError, TypeError):
                pass
        
        if unit_price <= 0:
            return jsonify({
                "success": False,
                "message": "سعر المنتج غير محدد بشكل صحيح. يرجى التواصل مع الدعم."
            })
        
        total = unit_price * qty
        
        user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],), fetchone=True)
        if not user:
            return jsonify({"success": False, "message": "المستخدم غير موجود"})
        
        user_balance = float(user["balance"] or 0)
        
        if user_balance < total:
            return jsonify({
                "success": False, 
                "type": "balance", 
                "message": f"رصيدك غير كافٍ لإتمام عملية الشراء.\n\nسعر الطلب: {format_price(total)}\nرصيدك الحالي: {format_price(user_balance)}\nالمبلغ الناقص: {format_price(total - user_balance)}\n\nيرجى شحن محفظتك للمتابعة."
            })
        
        custom_fields = {}
        phone_value = ""
        player_id = ""
        
        form_fields = {}
        for key in request.form:
            if key.startswith("custom_field_"):
                field_name = key.replace("custom_field_", "")
                field_val = (request.form.get(key) or "").strip()
                form_fields[field_name] = field_val
        
        for field_name in sorted(form_fields.keys()):
            val = form_fields[field_name]
            if val:
                player_id = val
                break
        
        for field_name, val in form_fields.items():
            fn_lower = field_name.lower()
            if val and (fn_lower in ["phone", "phone_number", "mobile", "tel", "telephone", "number"] or "هاتف" in field_name or "جوال" in field_name):
                phone_value = val
                break
        
        for field_name, val in form_fields.items():
            custom_fields[field_name] = val
        
        if selected_option_label:
            custom_fields["selected_option_label"] = selected_option_label
        if variant_api_id:
            custom_fields["variant_api_id"] = variant_api_id
        
        order_uuid = str(uuid.uuid4())
        order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
        
        db.execute("UPDATE users SET balance = balance - ?, total_orders = total_orders + 1, total_spent = total_spent + ? WHERE id = ?", 
                   (total, total, session["user_id"]))
        db.execute("""INSERT INTO purchase_orders 
                     (order_id, user_id, product_id, quantity, unit_price, total_price, status, player_id, order_uuid, customer_info) 
                     VALUES (?, ?, ?, ?, ?, ?, 'processing', ?, ?, ?)""",
                  (order_id, session["user_id"], actual_prod_id, qty, unit_price, total, 
                   player_id, order_uuid, json.dumps(custom_fields, ensure_ascii=False)))
        
        add_transaction(session["user_id"], -total, "purchase", 
                        f"شراء: {prod['name']} (الكمية: {qty})" + (f" - الخيار: {selected_option_label}" if selected_option_label else ""), 
                        order_id)
        add_loyalty_points(session["user_id"], total)
        send_user_notification(session["user_id"], "📦 طلب جديد", 
                              f"تم إنشاء طلب {order_id} للمنتج {prod['name']} بكمية {qty} ومبلغ {format_price(total)}")
        check_vip_status(session["user_id"])
        check_and_award_achievements(session["user_id"])
        check_and_award_spins(session["user_id"], total)
        
        api_result = None
        is_manual_product = prod.get("api_product_id", "") and (
            str(prod["api_product_id"]).startswith("manual_") or
            str(prod["api_product_id"]).startswith("gen_")
        )
        
        api_product_id_to_use = variant_api_id if variant_api_id else prod.get("api_product_id", "")
        
        if api_product_id_to_use and not is_manual_product:
            try:
                api_result, _ = api_client.create_order(
                    product_id=api_product_id_to_use,
                    qty=qty,
                    player_id=player_id,
                    order_uuid=order_uuid,
                    extra_params=custom_fields,
                    phone=phone_value
                )
            except Exception as e:
                debug_print(f"API order creation failed: {e}", "ERROR")
                traceback.print_exc()
                api_result = None
        
        api_success = False
        api_order_id = ""
        delivered = ""
        
        if api_result and isinstance(api_result, dict):
            err_code = api_result.get("error_code") or api_result.get("code")
            status_val = str(api_result.get("status", "")).lower()
            has_explicit_error = bool(api_result.get("error")) or (err_code is not None)
            
            if has_explicit_error and status_val not in ("ok", "accept", "accepted", "success"):
                error_msg = api_result.get("error_message") or api_result.get("message") or "خطأ غير معروف"
                if err_code:
                    try:
                        code_int = int(err_code)
                        if code_int in API_ERROR_CODES:
                            error_msg = API_ERROR_CODES[code_int]
                    except:
                        pass
                debug_print(f"API returned error: {error_msg}", "ERROR")
                api_success = False
                api_client._last_error = error_msg
            elif status_val in ("ok", "accept", "accepted", "success", "wait", "pending", ""):
                api_success = True
                data_obj = api_result.get("data", api_result)
                if isinstance(data_obj, dict):
                    api_order_id = str(data_obj.get("order_id") or data_obj.get("id") or "")
                else:
                    api_order_id = str(api_result.get("order_id") or api_result.get("id") or "")
                delivered = api_client._deep_search_delivered(api_result, api_order_id or order_uuid)
                if delivered and not isinstance(delivered, str):
                    delivered = json.dumps(delivered, ensure_ascii=False)

        if api_success:
            if delivered and str(delivered).strip() and str(delivered).strip() not in ("[]", "{}", ""):
                db.execute("UPDATE purchase_orders SET api_order_id=?, api_response=?, delivered_data=?, status='completed', completed_at=CURRENT_TIMESTAMP WHERE order_id=?", 
                           (api_order_id, str(api_result)[:2000], str(delivered)[:2000], order_id))
                db.execute("UPDATE products SET sales_count = sales_count + 1 WHERE id=?", (actual_prod_id,))
                send_user_notification(session["user_id"], "✅ تم تأكيد الطلب", f"تم تأكيد طلبك {order_id} بنجاح! المنتج: {prod['name']}")
                updated_user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
                return jsonify({
                    "success": True,
                    "message": f"تم استلام طلبك بنجاح! رقم الطلب: {order_id}",
                    "delivered": str(delivered)[:1000],
                    "balance": format_price(updated_user["balance"])
                })
            else:
                db.execute("UPDATE purchase_orders SET api_order_id=?, api_response=?, status='processing' WHERE order_id=?", 
                           (api_order_id, str(api_result)[:2000], order_id))
                updated_user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
                return jsonify({
                    "success": True,
                    "message": f"تم استلام طلبك بنجاح! رقم الطلب: {order_id}. طلبك قيد المعالجة وسيتم تسليمه فور تأكيده.",
                    "delivered": "",
                    "balance": format_price(updated_user["balance"])
                })
        elif is_manual_product:
            db.execute("UPDATE purchase_orders SET status='completed', delivered_data='سيتم تسليم المنتج تلقائياً', completed_at=CURRENT_TIMESTAMP WHERE order_id=?", (order_id,))
            db.execute("UPDATE products SET sales_count = sales_count + 1 WHERE id=?", (actual_prod_id,))
            send_user_notification(session["user_id"], "✅ تم تأكيد الطلب", f"تم تأكيد طلبك {order_id} بنجاح! المنتج: {prod['name']}")
            updated_user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
            return jsonify({
                "success": True,
                "message": f"تم استلام طلبك بنجاح! رقم الطلب: {order_id}",
                "delivered": "سيتم تسليم المنتج تلقائياً",
                "balance": format_price(updated_user["balance"])
            })
        else:
            db.execute("UPDATE users SET balance = balance + ?, total_orders = total_orders - 1, total_spent = total_spent - ? WHERE id = ?", 
                       (total, total, session["user_id"]))
            add_transaction(session["user_id"], total, "refund", f"استرداد: {prod['name']} - فشل الشراء التلقائي", order_id)
            db.execute("UPDATE purchase_orders SET status='failed', completed_at=CURRENT_TIMESTAMP WHERE order_id=?", (order_id,))
            send_user_notification(session["user_id"], "❌ فشل الطلب", f"فشل طلبك {order_id}. تم استرداد المبلغ كاملاً.")
            updated_user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
            
            error_msg = "تعذر إتمام عملية الشراء تلقائياً. تم استرداد المبلغ كاملاً لمحفظتك."
            if api_client._last_error:
                error_msg += f"\n\nالسبب: {api_client._last_error}"
            
            return jsonify({
                "success": False,
                "type": "refund",
                "message": error_msg,
                "balance": format_price(updated_user["balance"])
            })
    except Exception as e:
        debug_print(f"Error in /api/buy: {e}", "ERROR")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"حدث خطأ داخلي في الخادم أثناء معالجة الطلب: {str(e)}"})
    finally:
        lock.release()

@app.route("/api/wheel/spin", methods=["POST"])
@login_required
def api_spin_wheel():
    gift, message = spin_wheel(session["user_id"])
    if not gift:
        return jsonify({"success": False, "message": message})
    user = db.execute("SELECT balance, wheel_spins FROM users WHERE id=?", (session["user_id"],), fetchone=True)
    return jsonify({
        "success": True,
        "message": message,
        "gift_icon": gift.get("icon", "🎁"),
        "amount_str": format_price(gift.get("amount", 0)),
        "amount_value": float(gift.get("amount", 0) or 0),
        "remaining_spins": user["wheel_spins"] if user else 0,
        "balance": format_price(user["balance"]) if user else ""
    })

@app.route("/cart")
def cart_page():
    if "user_id" not in session:
        return render("cart", title="سلة المشتريات", active_page="cart", items=[], total=0)
    items = get_cart_items(session["user_id"])
    total = sum(item["sell_price"] * item["quantity"] for item in items)
    return render("cart", title="سلة المشتريات", active_page="cart", items=items, total=total)

@app.route("/api/cart/add/<int:prod_id>", methods=["POST"])
@login_required
def api_add_cart(prod_id):
    qty = request.form.get("quantity", 1)
    opt = request.form.get("selected_option_label", "")
    custom = request.form.get("custom_fields", "")
    if add_to_cart(session["user_id"], prod_id, int(qty), opt, custom):
        return jsonify({"success": True, "message": "تمت الإضافة للسلة", "cart_count": get_cart_count(session["user_id"])})
    return jsonify({"success": False, "message": "فشل الإضافة"})

@app.route("/api/cart/remove/<int:cart_id>", methods=["POST"])
@login_required
def api_remove_cart(cart_id):
    remove_from_cart(cart_id, session["user_id"])
    return jsonify({"success": True, "cart_count": get_cart_count(session["user_id"])})

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = get_cart_items(session["user_id"])
    if not items:
        return redirect(url_for("cart_page"))
    
    product_total = sum(item["sell_price"] * item["quantity"] for item in items)
    shipping_methods = db.execute("SELECT * FROM shipping_methods WHERE is_active=1 ORDER BY sort_order", fetch=True) or []
    shipping_list = []
    for sm in shipping_methods:
        sm_dict = dict(sm)
        if sm_dict.get("wallet_link") and not sm_dict.get("qr_code_base64"):
            sm_dict["qr_code_base64"] = generate_qr_base64(sm_dict["wallet_link"])
        elif not sm_dict.get("qr_code_base64") and sm_dict.get("description"):
            sm_dict["qr_code_base64"] = generate_qr_base64(sm_dict["description"])
        shipping_list.append(sm_dict)
    payment_methods = db.execute("SELECT * FROM payment_methods WHERE is_active=1 ORDER BY sort_order", fetch=True) or []
    return render("shipping_checkout", title="إتمام الطلب", active_page="cart", items=items, product_total=product_total, shipping_methods=shipping_list, payment_methods=[dict(p) for p in payment_methods])

@app.route("/checkout/confirm", methods=["POST"])
@login_required
def checkout_confirm():
    items = get_cart_items(session["user_id"])
    if not items:
        return jsonify({"success": False, "message": "السلة فارغة"})
        
    item = items[0]
    prod_id = item["product_id"]
    qty = item["quantity"]
    player_id = ""
    product_total = item["sell_price"] * qty
    custom_fields = json.loads(item["custom_fields"]) if item["custom_fields"] else {}
    if item["selected_option"]:
        custom_fields["selected_option_label"] = item["selected_option"]
        
    prod = db.execute("SELECT * FROM products WHERE id=?", (prod_id,), fetchone=True)
    if not prod:
        return jsonify({"success": False, "message": "المنتج غير موجود"})
        
    shipping_method_id = request.form.get("shipping_method_id")
    payment_amount = float(request.form.get("payment_amount", 0))
    transaction_number = request.form.get("transaction_number", "").strip()
    shipping_price = 0
    if shipping_method_id:
        sm = db.execute("SELECT * FROM shipping_methods WHERE id=?", (shipping_method_id,), fetchone=True)
        if sm:
            shipping_price = sm["price"]
            
    total_price = product_total + shipping_price
    order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
    
    db.execute("""INSERT INTO purchase_orders (order_id, user_id, product_id, quantity, unit_price, total_price, status, player_id, shipping_method_id, shipping_price, transaction_number, payment_amount, customer_info) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)""", (order_id, session["user_id"], prod_id, qty, prod["sell_price"], total_price, player_id, shipping_method_id, shipping_price, transaction_number, payment_amount, json.dumps(custom_fields, ensure_ascii=False)))
    
    clear_cart(session["user_id"])
    
    send_user_notification(session["user_id"], "📦 تم استلام طلبك", f"تم استلام طلبك {order_id} بنجاح! المنتج: {prod['name']}، الكمية: {qty}، المبلغ: {format_price(total_price)}. سيتم مراجعته وتأكيده قريباً.")
    
    order_data = {"order_id": order_id, "quantity": qty, "unit_price": prod["sell_price"], "total_price": total_price, "shipping_method_id": shipping_method_id, "shipping_price": shipping_price, "payment_amount": payment_amount, "transaction_number": transaction_number, "player_id": player_id, "customer_info": json.dumps(custom_fields, ensure_ascii=False), "created_at": datetime.now().isoformat()}
    admin_text = build_order_details_text(order_data, prod["name"], session.get("username", ""))
    
    for admin_id in ADMIN_IDS:
        _send_telegram_async(admin_id, admin_text)
            
    notify_support_users("🚚 طلب شحن جديد", admin_text)
    
    order_db_id = db.execute("SELECT id FROM purchase_orders WHERE order_id=?", (order_id,), fetchone=True)
    return jsonify({"success": True, "order_id": order_db_id["id"], "message": "تم استلام الطلب بنجاح!"})

@app.route("/order/<int:order_id>")
@login_required
def order_success_page(order_id):
    order = db.execute("SELECT po.*, p.name as product_name FROM purchase_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.id=? AND po.user_id=?", (order_id, session["user_id"]), fetchone=True)
    if not order:
        abort(404)
    return render("order_success", title="تم استلام الطلب", order=dict(order), product_name=order["product_name"])

@app.route("/orders")
def orders_page():
    if "user_id" not in session:
        return render("orders", title="طلباتي", active_page="orders", orders=[])
    orders = db.execute("SELECT po.*, p.name as product_name FROM purchase_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.user_id=? ORDER BY po.created_at DESC LIMIT 50", (session["user_id"],), fetch=True) or []
    return render("orders", title="طلباتي", active_page="orders", orders=[dict(o) for o in orders])

@app.route("/order/details/<int:order_id>")
@login_required
def order_details_page(order_id):
    order = db.execute("SELECT po.*, p.name as product_name FROM purchase_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.id=? AND po.user_id=?", (order_id, session["user_id"]), fetchone=True)
    if not order:
        abort(404)
    return render("order_details", title=f"طلب #{order_id}", order=dict(order), product_name=order["product_name"])

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile_page():
    user_id = session["user_id"]
    if request.method == "POST":
        phone = request.form.get("phone", "").strip() or None
        password = request.form.get("password", "").strip()
        if password:
            if len(password) < 6:
                return render("profile", title="إعداداتي", active_page="profile", user=get_user_full_info(user_id), stats=get_user_full_info(user_id)["stats"], error="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
            pw_hash, salt = _hash_password(password)
            db.execute("UPDATE users SET phone=?, password_hash=?, salt=? WHERE id=?", (phone, pw_hash, salt, user_id))
        else:
            db.execute("UPDATE users SET phone=? WHERE id=?", (phone, user_id))
        return redirect(url_for("profile_page"))
    user_info = get_user_full_info(user_id)
    return render("profile", title="إعداداتي", active_page="profile", user=user_info, stats=user_info["stats"])

@app.route("/wallet")
def wallet_page():
    if "user_id" not in session:
        return render("wallet", title="محفظتي", active_page="wallet", user_balance=0, transactions=[])
    user = db.execute("SELECT balance FROM users WHERE id=?", (session["user_id"],), fetchone=True)
    transactions = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (session["user_id"],), fetch=True) or []
    return render("wallet", title="محفظتي", active_page="wallet", user_balance=user["balance"] if user else 0, transactions=[dict(t) for t in transactions])

@app.route("/wallet/topup")
@login_required
def wallet_topup_page():
    methods = db.execute("SELECT * FROM wallet_topup_methods WHERE is_active=1 ORDER BY sort_order", fetch=True) or []
    
    pending = db.execute("""
        SELECT wtr.*, wtm.name as method_name 
        FROM wallet_topup_requests wtr 
        LEFT JOIN wallet_topup_methods wtm ON wtr.method_id = wtm.id 
        WHERE wtr.user_id=? AND wtr.status='pending' 
        ORDER BY wtr.created_at DESC
    """, (session["user_id"],), fetch=True) or []
    
    methods_list = []
    for m in methods:
        md = dict(m)
        md["qr_code_base64"] = None
        methods_list.append(md)
    return render("wallet_topup", title="شحن المحفظة", active_page="wallet", methods=methods_list, pending_requests=[dict(r) for r in pending])

@app.route("/wallet/topup/processing")
@login_required
def wallet_topup_processing():
    return render("topup_processing", title="جاري المعالجة", active_page="wallet")

@app.route("/wallet/topup/confirm", methods=["POST"])
@login_required
def wallet_topup_confirm():
    try:
        last_req = db.execute("SELECT created_at FROM wallet_topup_requests WHERE user_id=? ORDER BY id DESC LIMIT 1", (session["user_id"],), fetchone=True)
        if last_req and last_req["created_at"]:
            try:
                req_time = datetime.strptime(last_req["created_at"], "%Y-%m-%d %H:%M:%S")
                if req_time.tzinfo is None:
                    req_time = req_time.replace(tzinfo=None)
                now_time = datetime.now()
                diff = (now_time - req_time).total_seconds()
                if diff < 120:
                    return jsonify({"success": False, "message": f"يرجى الانتظار {int((120 - diff)//60)} دقيقة و {int((120 - diff)%60)} ثانية بين كل طلب شحن."})
            except Exception:
                pass

        method_id = request.form.get("method_id")
        amount = float(request.form.get("amount", 0))
        transaction_number = request.form.get("transaction_number", "").strip()
        currency_type = request.form.get("currency_type", "SYP")
        converted_amount_str = request.form.get("converted_amount", "")
        
        if amount <= 0:
            return jsonify({"success": False, "message": "يرجي إدخال مبلغ صحيح"})
        if not transaction_number:
            return jsonify({"success": False, "message": "يرجي إدخال رقم العملية"})
        
        existing_txn = db.execute("SELECT id FROM wallet_topup_requests WHERE transaction_number=? AND status IN ('pending', 'approved')", (transaction_number,), fetchone=True)
        if existing_txn:
            return jsonify({"success": False, "message": "رقم العملية مستخدم مسبقاً. لا يمكن استخدامه مرتين."})
            
        final_amount_syp = amount
        original_amount = amount
        
        if currency_type == "USD":
            if converted_amount_str:
                try:
                    final_amount_syp = float(converted_amount_str)
                except:
                    final_amount_syp = convert_usd_to_syp(amount)
            else:
                final_amount_syp = convert_usd_to_syp(amount)
            
        request_id = f"TUP-{uuid.uuid4().hex[:12].upper()}"
        db.execute("""INSERT INTO wallet_topup_requests 
                      (request_id, user_id, method_id, amount, transaction_number, status, currency_type, original_amount) 
                      VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""", 
                   (request_id, session["user_id"], method_id, final_amount_syp, transaction_number, currency_type, original_amount))
        
        send_user_notification(session["user_id"], "📥 طلب شحن محفظة", f"تم إرسال طلب شحن محفظة بـ {format_price(final_amount_syp)}. رقم الطلب: {request_id}. سيتم تأكيده بعد المراجعة.")
        
        try:
            topup_data = {"request_id": request_id, "user_id": session["user_id"], "method_id": method_id, "amount": final_amount_syp, "transaction_number": transaction_number, "currency_type": currency_type, "original_amount": original_amount, "created_at": datetime.now().isoformat()}
            admin_text = build_topup_details_text(topup_data, session.get("username", ""))
            
            for admin_id in ADMIN_IDS:
                _send_telegram_async(admin_id, admin_text)
                    
            notify_support_users("📥 طلب شحن محفظة جديد", admin_text)
        except Exception as notify_err:
            debug_print(f"Topup admin notify error: {notify_err}", "WARN")
        
        return jsonify({"success": True, "message": "تم إرسال طلب الشحن بنجاح! سيتم مراجعته وتأكيده من قبل الإدارة قريباً.", "request_id": request_id, "redirect": "/wallet/topup/processing"})
    except Exception as e:
        return jsonify({"success": False, "message": f"حدث خطأ أثناء إرسال الطلب: {str(e)}"})

@app.route("/favorites")
def favorites_page():
    if "user_id" not in session:
        return render("favorites", title="المفضلة", active_page="favorites", products=[])
    products = db.execute("SELECT p.*, c.name as cat_name FROM user_favorites f JOIN products p ON f.product_id=p.id LEFT JOIN categories c ON p.category_id=c.id WHERE f.user_id=? AND p.is_active=1 ORDER BY f.created_at DESC", (session["user_id"],), fetch=True) or []
    return render("favorites", title="المفضلة", active_page="favorites", products=[dict(p) for p in products])

@app.route("/compare")
def compare_page():
    if "user_id" not in session:
        return render("compare", title="المقارنة", active_page="compare", items=[])
    items = get_comparison_items(session["user_id"])
    return render("compare", title="المقارنة", active_page="compare", items=items)

@app.route("/faq")
def faq_page():
    faqs = get_faqs()
    return render("faq", title="الأسئلة الشائعة", active_page="faq", faqs=faqs)

@app.route("/blog")
def blog_page():
    posts = get_blog_posts()
    return render("blog", title="المدونة", active_page="blog", posts=posts)

@app.route("/blog/<slug>")
def blog_post_page(slug):
    post = get_blog_post(slug)
    if not post:
        abort(404)
    return render("blog_post", title=post["title"], post=post)

@app.route("/achievements")
@login_required
def achievements_page():
    check_and_award_achievements(session["user_id"])
    achievements = get_user_achievements(session["user_id"])
    return render("achievements", title="إنجازاتي", active_page="achievements", achievements=achievements)

@app.route("/contests")
def contests_page():
    contests = get_active_contests()
    return render("contests", title="المسابقات", active_page="contests", contests=contests)

@app.route("/api/contest/join/<int:contest_id>", methods=["POST"])
@login_required
def api_join_contest(contest_id):
    success, message = join_contest(contest_id, session["user_id"])
    return jsonify({"success": success, "message": message})

@app.route("/notifications")
@login_required
def notifications_page():
    notifs = db.execute("SELECT * FROM notifications WHERE user_id=? OR is_broadcast=1 ORDER BY created_at DESC LIMIT 30", (session["user_id"],), fetch=True) or []
    return render("notifications", title="الإشعارات", active_page="notifications", notifications=[dict(n) for n in notifs])

@app.route("/support", methods=["GET"])
@login_required
def support_page():
    tickets = db.execute("SELECT t.*, (SELECT COUNT(*) FROM support_messages WHERE ticket_id=t.id) as messages_count FROM support_tickets t WHERE t.user_id=? ORDER BY t.created_at DESC", (session["user_id"],), fetch=True) or []
    return render("support", title="الدعم الفني", active_page="support", tickets=[dict(t) for t in tickets])

@app.route("/support/create", methods=["POST"])
@login_required
def support_create():
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    if not subject or not message:
        return redirect(url_for("support_page"))
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    db.execute("INSERT INTO support_tickets (ticket_id, user_id, subject) VALUES (?, ?, ?)", (ticket_id, session["user_id"], subject))
    ticket = db.execute("SELECT id FROM support_tickets WHERE ticket_id=?", (ticket_id,), fetchone=True)
    if ticket:
        db.execute("INSERT INTO support_messages (ticket_id, user_id, message, is_from_admin) VALUES (?, ?, ?, 0)", (ticket["id"], session["user_id"], message))
    for admin_id in ADMIN_IDS:
        _send_telegram_async(admin_id, f"📞 <b>تذكرة دعم جديدة</b>\n\n🎫 {ticket_id}\n👤 {session.get('username','?')}\n📝 {subject}\n\n{message}")
    return redirect(url_for("support_page"))

@app.route("/support/ticket/<int:ticket_id>")
@login_required
def support_ticket(ticket_id):
    ticket = db.execute("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (ticket_id, session["user_id"]), fetchone=True)
    if not ticket:
        abort(404)
    messages = db.execute("SELECT * FROM support_messages WHERE ticket_id=? ORDER BY created_at", (ticket_id,), fetch=True) or []
    return render("support_ticket", title=f"تذكرة: {ticket['subject']}", ticket=dict(ticket), messages=[dict(m) for m in messages])

@app.route("/support/ticket/<int:ticket_id>/reply", methods=["POST"])
@login_required
def support_ticket_reply(ticket_id):
    ticket = db.execute("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (ticket_id, session["user_id"]), fetchone=True)
    if not ticket:
        abort(404)
    message = request.form.get("message", "").strip()
    if message:
        db.execute("INSERT INTO support_messages (ticket_id, user_id, message, is_from_admin) VALUES (?, ?, ?, 0)", (ticket_id, session["user_id"], message))
        db.execute("UPDATE support_tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (ticket_id,))
        for admin_id in ADMIN_IDS:
            _send_telegram_async(admin_id, f"💬 <b>رد جديد على تذكرة</b>\n\n🎫 {ticket['ticket_id']}\n👤 {session.get('username','?')}\n\n{message}")
    return redirect(url_for("support_ticket", ticket_id=ticket_id))

@app.route("/images/<path:filename>")
def serve_image(filename):
    if filename.startswith(IMAGES_DIR + "/"):
        filename = filename[len(IMAGES_DIR) + 1:]
    filepath = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(filepath):
        response = send_file(filepath)
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response
    abort(404)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route("/api/favorite/toggle/<int:prod_id>", methods=["POST"])
@login_required
def api_toggle_fav(prod_id):
    existing = db.execute("SELECT id FROM user_favorites WHERE user_id=? AND product_id=?", (session["user_id"], prod_id), fetchone=True)
    if existing:
        db.execute("DELETE FROM user_favorites WHERE id=?", (existing["id"],))
        return jsonify({"active": False})
    else:
        db.execute("INSERT INTO user_favorites (user_id, product_id) VALUES (?, ?)", (session["user_id"], prod_id))
        return jsonify({"active": True})

@app.route("/api/compare/toggle/<int:prod_id>", methods=["POST"])
@login_required
def api_toggle_compare(prod_id):
    result = toggle_comparison(session["user_id"], prod_id)
    if result is None:
        return jsonify({"success": False, "message": "يمكنك مقارنة 4 منتجات كحد أقصى"})
    return jsonify({"success": True, "active": result})

@app.route("/api/notification/read/<int:notif_id>", methods=["POST"])
@login_required
def api_read_notification(notif_id):
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND (user_id=? OR is_broadcast=1)", (notif_id, session["user_id"]))
    return jsonify({"success": True})

@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_read_all_notifications():
    db.execute("UPDATE notifications SET is_read=1 WHERE (user_id=? OR is_broadcast=1) AND is_read=0", (session["user_id"],))
    return jsonify({"success": True})

@app.route("/api/notifications/latest")
def api_latest_notifications():
    if "user_id" not in session:
        return jsonify({"max_id": 0})
    row = db.execute("SELECT MAX(id) as max_id FROM notifications WHERE user_id=? OR is_broadcast=1", (session["user_id"],), fetchone=True)
    return jsonify({"max_id": row["max_id"] if row and row["max_id"] else 0})

@app.route("/api/notifications/unread")
def api_unread_notifications():
    if "user_id" not in session:
        return jsonify({"notifications": [], "max_id": 0}), 200
    notifs = db.execute("SELECT * FROM notifications WHERE is_read=0 AND (user_id=? OR is_broadcast=1) ORDER BY created_at DESC LIMIT 5", (session["user_id"],), fetch=True) or []
    max_row = db.execute("SELECT MAX(id) as max_id FROM notifications WHERE user_id=? OR is_broadcast=1", (session["user_id"],), fetchone=True)
    max_id = max_row["max_id"] if max_row and max_row["max_id"] else 0
    return jsonify({"notifications": [dict(n) for n in notifs], "max_id": max_id})

@app.route("/api/notifications/check")
def api_check_notifications():
    if "user_id" not in session:
        return jsonify({"notifications": [], "max_id": 0}), 200
    last_id = request.args.get("last", 0, type=int)
    notifs = db.execute("SELECT * FROM notifications WHERE id > ? AND (user_id=? OR is_broadcast=1) ORDER BY id DESC LIMIT 5", (last_id, session["user_id"]), fetch=True) or []
    max_row = db.execute("SELECT MAX(id) as max_id FROM notifications WHERE user_id=? OR is_broadcast=1", (session["user_id"],), fetchone=True)
    max_id = max_row["max_id"] if max_row and max_row["max_id"] else 0
    return jsonify({"notifications": [dict(n) for n in notifs], "max_id": max_id})

@app.route("/api/chat/messages")
def api_chat_messages():
    if "user_id" not in session:
        return jsonify({"redirect": True, "messages": []})
    db.execute("UPDATE chat_messages SET is_read=1 WHERE user_id=? AND is_from_admin=1", (session["user_id"],))
    messages = db.execute("SELECT * FROM chat_messages WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (session["user_id"],), fetch=True) or []
    msgs = [dict(m) for m in reversed(messages)]
    for m in msgs:
        m["created_at"] = m["created_at"][:16] if m["created_at"] else "الآن"
    return jsonify({"messages": msgs})

@app.route("/api/chat/send", methods=["POST"])
def api_chat_send():
    if "user_id" not in session:
        return jsonify({"redirect": True, "success": False})
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"success": False})
    db.execute("INSERT INTO chat_messages (user_id, message, is_from_admin, is_read) VALUES (?, ?, 0, 0)", (session["user_id"], message))
    for admin_id in ADMIN_IDS:
        _send_telegram_async(admin_id, f"💬 <b>رسالة دعم جديدة</b>\n\n👤 {session.get('username','?')}\n💬 {message}")
    return jsonify({"success": True, "reply": "شكراً لتواصلك! تم استلام رسالتك وسيتم الرد عليك قريباً."})

@app.route("/api/chat/send-image", methods=["POST"])
def api_chat_send_image():
    if "user_id" not in session:
        return jsonify({"redirect": True, "success": False})
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال الصورة"})
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "اسم الملف فارغ"})
    try:
        image_bytes = file.read()
        img_path = save_image_from_bytes(image_bytes, "chat")
        if not img_path:
            return jsonify({"success": False, "message": "فشل حفظ الصورة"})
        db.execute("INSERT INTO chat_messages (user_id, message, is_from_admin, is_read, image_path) VALUES (?, ?, 0, 0, ?)", (session["user_id"], "📷 صورة", img_path))
        
        def _send_photo_async(chat_id, photo_path, caption):
            def _send():
                try:
                    with open(photo_path, 'rb') as photo_file:
                        bot.send_photo(chat_id, photo_file, caption=caption)
                except Exception as e:
                    debug_print(f"Telegram photo send failed: {e}", "WARN")
            threading.Thread(target=_send, daemon=True).start()
            
        for admin_id in ADMIN_IDS:
            _send_photo_async(admin_id, os.path.join(IMAGES_DIR, img_path), f"💬 <b>صورة دعم جديدة</b>\n\n👤 {session.get('username','?')}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ==============================================================================
# بوت تيليجرام (لوحة تحكم شاملة وموسعة بالكامل)
# ==============================================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def save_telegram_photo(file_id, prefix="tg_img"):
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        return save_image_from_bytes(downloaded_file, prefix)
    except Exception as e:
        debug_print(f"Error saving telegram image: {e}", "ERROR")
        return None

_current_bot_info = {"username": None, "ts": 0, "lock": threading.Lock()}
BOT_INFO_CACHE_TTL = 3600

def get_current_bot_username():
    global _current_bot_info
    now = time.time()
    with _current_bot_info["lock"]:
        if _current_bot_info["username"] and (now - _current_bot_info["ts"]) < BOT_INFO_CACHE_TTL:
            return _current_bot_info["username"]
    
    try:
        me = bot.get_me()
        if me and me.username:
            with _current_bot_info["lock"]:
                _current_bot_info["username"] = me.username
                _current_bot_info["ts"] = now
            db.set_setting("bot_username", me.username)
            return me.username
    except Exception as e:
        debug_print(f"Failed to get bot username: {e}", "WARN")
    
    stored = db.get_setting("bot_username", BOT_USERNAME)
    with _current_bot_info["lock"]:
        _current_bot_info["username"] = stored
        _current_bot_info["ts"] = now
    return stored

def get_current_bot_referral_link(referral_code):
    bot_un = get_current_bot_username()
    return f"https://t.me/{bot_un}?start=ref_{referral_code}"

def get_admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📦 ➕ إضافة منتج", callback_data="admin_add_product"),
        InlineKeyboardButton("📦 📋 إدارة المنتجات", callback_data="admin_list_products")
    )
    markup.add(
        InlineKeyboardButton("📦 🔄 مزامنة منتج", callback_data="admin_sync_product"),
        InlineKeyboardButton("📦 🔍 بحث منتج", callback_data="admin_search_product")
    )
    markup.add(
        InlineKeyboardButton("🏷️ 🎁 إدارة العروض", callback_data="admin_offers"),
        InlineKeyboardButton("🏷️ ➕ عرض جديد", callback_data="admin_add_offer_btn")
    )
    markup.add(
        InlineKeyboardButton("🎡 🎁 إدارة عجلة الحظ", callback_data="admin_wheel"),
        InlineKeyboardButton("🎟️ 📋 أكواد الخصم", callback_data="admin_discounts")
    )
    markup.add(
        InlineKeyboardButton("🔄 💲 إعادة حساب الأسعار", callback_data="admin_recalc_prices"),
        InlineKeyboardButton("📂 ➕ إضافة قسم", callback_data="admin_add_category")
    )
    markup.add(
        InlineKeyboardButton("📂 📋 إدارة الأقسام", callback_data="admin_list_categories"),
        InlineKeyboardButton("🔀 🚚 نقل قسم فرعي", callback_data="admin_move_subcat")
    )
    markup.add(
        InlineKeyboardButton("💰 📈 نسبة الربح", callback_data="admin_profit"),
        InlineKeyboardButton("💱 🪙 عملة المتجر", callback_data="admin_currency")
    )
    markup.add(
        InlineKeyboardButton("💱 📊 سعر الصرف", callback_data="admin_exchange_rate"),
        InlineKeyboardButton("💰 📉 عمولة الشحن", callback_data="admin_topup_commission")
    )
    markup.add(
        InlineKeyboardButton("🚚 💵 حدود الشحن", callback_data="admin_min_shipping"),
        InlineKeyboardButton("🛒 💵 الحد الأدنى للطلب", callback_data="admin_min_order")
    )
    markup.add(
        InlineKeyboardButton("🚚 🎁 الشحن المجاني", callback_data="admin_free_shipping"),
        InlineKeyboardButton("📦 📉 تنبيه المخزون", callback_data="admin_stock_alert")
    )
    markup.add(
        InlineKeyboardButton("💳 📋 طرق الدفع", callback_data="admin_payments"),
        InlineKeyboardButton("🚚 📋 طرق الشحن", callback_data="admin_shipping")
    )
    markup.add(
        InlineKeyboardButton("🚚 ➕ طريقة شحن (ل.س)", callback_data="admin_add_shipping_btn"),
        InlineKeyboardButton("🚚 💵 طريقة شحن بالدولار", callback_data="admin_add_shipping_usd_btn")
    )
    markup.add(
        InlineKeyboardButton("💳 ➕ طريقة دفع جديدة", callback_data="admin_add_payment_btn"),
        InlineKeyboardButton("📥 📋 شحن المحفظة", callback_data="admin_topup_methods")
    )
    markup.add(
        InlineKeyboardButton("📥 ➕ طريقة شحن محفظة (ل.س)", callback_data="admin_add_topup_btn"),
        InlineKeyboardButton("📥 💵 طريقة شحن محفظة (دولار)", callback_data="admin_add_topup_usd_btn")
    )
    markup.add(
        InlineKeyboardButton("📱 🔔 إعدادات Push", callback_data="admin_push_settings")
    )
    markup.add(
        InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")
    )
    markup.add(
        InlineKeyboardButton("💰 📋 طلبات الشحن", callback_data="admin_topup_requests"),
        InlineKeyboardButton("🚚 ✅ موافقة طلبات الشحن", callback_data="admin_shipping_approvals")
    )
    markup.add(
        InlineKeyboardButton("📋 📦 جميع الطلبات", callback_data="admin_orders"),
        InlineKeyboardButton("📤 📋 تصدير الطلبات", callback_data="admin_export_orders")
    )
    markup.add(
        InlineKeyboardButton("📊 📈 إحصائيات المبيعات", callback_data="admin_sales_stats"),
        InlineKeyboardButton("💰 📋 المعاملات", callback_data="admin_transactions")
    )
    markup.add(
        InlineKeyboardButton("👥 📋 إدارة المستخدمين", callback_data="admin_users"),
        InlineKeyboardButton("🔒 📋 المستخدمون المحظورون", callback_data="admin_banned_users")
    )
    markup.add(
        InlineKeyboardButton("➕ 🛡️ إضافة داعم", callback_data="admin_add_supporter"),
        InlineKeyboardButton("👥 📋 قائمة الداعمين", callback_data="admin_list_supporters")
    )
    markup.add(
        InlineKeyboardButton("⭐ 📋 مستخدمو VIP", callback_data="admin_vip_users"),
        InlineKeyboardButton("🎁 💰 تعديل رصيد", callback_data="admin_edit_balance")
    )
    markup.add(
        InlineKeyboardButton("👤 🔍 بحث مستخدم", callback_data="admin_search_user"),
        InlineKeyboardButton("📊 📈 إحصائيات المستخدمين", callback_data="admin_user_stats")
    )
    markup.add(
        InlineKeyboardButton("📞 🎫 تذاكر الدعم", callback_data="admin_support"),
        InlineKeyboardButton("💬 💬 محادثات الدعم", callback_data="admin_chats")
    )
    markup.add(
        InlineKeyboardButton("📢 📝 إعلان نصي", callback_data="admin_ad_text"),
        InlineKeyboardButton("📢 🖼️ إعلان صورة", callback_data="admin_ad_image")
    )
    markup.add(
        InlineKeyboardButton("🗑️ 📋 حذف الإعلانات", callback_data="admin_list_ads"),
        InlineKeyboardButton("🎁 📋 أكواد الهدايا", callback_data="admin_gifts")
    )
    markup.add(
        InlineKeyboardButton("🎁 ➕ كود هدية", callback_data="admin_add_gift_btn"),
        InlineKeyboardButton("🎟️ ➕ كود خصم", callback_data="admin_add_discount")
    )
    markup.add(
        InlineKeyboardButton("📨 📢 رسالة جماعية", callback_data="admin_broadcast"),
        InlineKeyboardButton("📨 🖼️ رسالة صورة جماعية", callback_data="admin_broadcast_image")
    )
    markup.add(
        InlineKeyboardButton("🔔 📨 إرسال إشعار", callback_data="admin_send_notif"),
        InlineKeyboardButton("📢 📡 إدارة القناة", callback_data="admin_channel_mgmt")
    )
    markup.add(
        InlineKeyboardButton("📊 📈 تقرير المبيعات", callback_data="admin_report"),
        InlineKeyboardButton("🏆 ➕ مسابقة جديدة", callback_data="admin_add_contest")
    )
    markup.add(
        InlineKeyboardButton("📢 📡 قناة الإجبار", callback_data="admin_channel"),
        InlineKeyboardButton("🔒 📢 الإجبار للقناة", callback_data="admin_force_join")
    )
    markup.add(
        InlineKeyboardButton("🏷️ 🖼️ شعار وأيقونة", callback_data="admin_logo"),
        InlineKeyboardButton("🖼️ 🌌 خلفية الموقع", callback_data="admin_bg")
    )
    markup.add(
        InlineKeyboardButton("🖼️ ✨ النافذة الترحيبية", callback_data="admin_welcome_popup_img"),
        InlineKeyboardButton("📝 ✏️ رسالة الترحيب", callback_data="admin_welcome_msg")
    )
    markup.add(
        InlineKeyboardButton("🎨 🎨 ألوان الموقع", callback_data="admin_colors"),
        InlineKeyboardButton("📝 📄 اسم المتجر", callback_data="admin_store_name")
    )
    markup.add(
        InlineKeyboardButton("📝 📄 وصف المتجر", callback_data="admin_store_desc"),
        InlineKeyboardButton("📝 📄 نص الفوتر", callback_data="admin_footer")
    )
    markup.add(
        InlineKeyboardButton("📢 📝 شريط العروض", callback_data="admin_promo_bar"),
        InlineKeyboardButton("🔗 📞 روابط الدعم", callback_data="admin_support_links")
    )
    markup.add(
        InlineKeyboardButton("📱 🔗 روابط التواصل", callback_data="admin_social_links"),
        InlineKeyboardButton("🔍 📊 إعدادات SEO", callback_data="admin_seo")
    )
    markup.add(
        InlineKeyboardButton("🔧 ⚙️ وضع الصيانة", callback_data="admin_maintenance"),
        InlineKeyboardButton("🖼️ 📋 صور الصيانة", callback_data="admin_maint_images")
    )
    markup.add(
        InlineKeyboardButton("🔄 📡 مزامنة API", callback_data="admin_sync"),
        InlineKeyboardButton("💳 🔍 رصيد API", callback_data="admin_apibalance")
    )
    markup.add(
        InlineKeyboardButton("📊 📈 إحصائيات الموقع", callback_data="admin_stats"),
        InlineKeyboardButton("⚙️ 🔧 الإعدادات العامة", callback_data="admin_settings")
    )
    markup.add(
        InlineKeyboardButton("📝 ➕ مقال للمدونة", callback_data="admin_add_blog"),
        InlineKeyboardButton("❓ ➕ سؤال شائع", callback_data="admin_add_faq")
    )
    markup.add(
        InlineKeyboardButton("⭐ 📊 نقاط الولاء", callback_data="admin_loyalty"),
        InlineKeyboardButton("💎 📊 إعدادات VIP", callback_data="admin_vip_settings")
    )
    markup.add(
        InlineKeyboardButton("🎁 📊 نظام الإحالات", callback_data="admin_referral"),
        InlineKeyboardButton("🏆 📊 الإنجازات", callback_data="admin_achievements")
    )
    markup.add(
        InlineKeyboardButton("🗄️ 📋 سجلات الأخطاء", callback_data="admin_error_logs"),
        InlineKeyboardButton("📊 📋 سجلات المزامنة", callback_data="admin_sync_logs")
    )
    markup.add(
        InlineKeyboardButton("🔒 📋 سجل النشاط", callback_data="admin_activity_log"),
        InlineKeyboardButton("🌐 🔗 رابط المتجر", callback_data="admin_web_url")
    )
    return markup

def get_user_main_keyboard(web_app_url=None):
    markup = InlineKeyboardMarkup(row_width=1)
    url = web_app_url or db.get_setting("bot_web_url", WEB_URL)
    try:
        markup.add(InlineKeyboardButton("🚀 ابدأ التسوق", web_app=WebAppInfo(url=url)))
    except:
        markup.add(InlineKeyboardButton("🚀 ابدأ التسوق", url=url))
    markup.add(InlineKeyboardButton("🎁 رابط الإحالة", callback_data="user_referral"))
    markup.add(InlineKeyboardButton("💰 رصيدي", callback_data="user_balance"))
    return markup

def set_bot_state(user_id, state, data=None):
    db.execute("INSERT INTO bot_states (user_id, state, data, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=CURRENT_TIMESTAMP", (user_id, state, json.dumps(data) if data else None))

def get_bot_state(user_id):
    row = db.execute("SELECT state, data FROM bot_states WHERE user_id=?", (user_id,), fetchone=True)
    if not row:
        return None, None
    try:
        return row["state"], json.loads(row["data"]) if row["data"] else None
    except:
        return row["state"], None

def clear_bot_state(user_id):
    db.execute("DELETE FROM bot_states WHERE user_id=?", (user_id,))

@bot.message_handler(commands=["start"])
def cmd_start(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username)
    if not user:
        return bot.reply_to(message, "❌ حدث خطأ. حاول لاحقاً.")
    if user.get("is_banned"):
        return bot.reply_to(message, "❌ تم حظر حسابك. يرجى التواصل مع الدعم.")
    
    is_joined, group_link = check_force_join(message.from_user.id)
    if not is_joined:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔔 انضم للقناة", url=group_link))
        bot.send_message(message.chat.id, "❌ <b>عذراً</b>\n\nيجب الانضمام لقناتنا أولاً لاستخدام البوت.\n\nاضغط على الزر أدناه للانضمام ثم أرسل /start مرة أخرى.", reply_markup=markup)
        markup2 = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ تحقق من الانضمام", callback_data="user_check_join"))
        bot.send_message(message.chat.id, "بعد الانضمام، اضغط على الزر التالي للتحقق:", reply_markup=markup2)
        return

    if len(message.text.split()) > 1:
        payload = message.text.split()[1]
        if payload.startswith("ref_"):
            ref_code = payload[4:]
            referrer = db.execute("SELECT id FROM users WHERE referral_code=?", (ref_code,), fetchone=True)
            if referrer and referrer["id"] != user["id"]:
                if not user.get("referred_by"):
                    db.execute("UPDATE users SET referred_by=? WHERE id=?", (referrer["id"], user["id"]))
                    bot.send_message(referrer["id"], "🎉 <b>تم تسجيل إحالة جديدة باسمك!</b>\n\nسيحصل المستخدم الجديد على مكافأة عند شحن محفظته لأول مرة.")

    welcome = db.get_setting("welcome_message", "مرحباً بك في MO STORE! 🛒")
    web_url = f"{db.get_setting('bot_web_url', WEB_URL)}?tg_id={message.from_user.id}&tg_username={message.from_user.username}"
    
    msg = bot.send_message(message.chat.id, "🚀")
    time.sleep(1.5)
    bot.edit_message_text("🐆", msg.chat.id, msg.message_id)
    time.sleep(1.5)
    
    try:
        bot.set_message_reaction(message.chat.id, message.message_id, [ReactionType(type="emoji", emoji="👍")])
    except Exception as e:
        debug_print(f"Failed to set reaction: {e}", "WARN")
    
    if is_admin(message.from_user.id):
        text = f"👋 {welcome}\n\n🔧 <b>لوحة تحكم المدير</b>\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاختر من لوحة التحكم:"
        bot.edit_message_text(text, msg.chat.id, msg.message_id, reply_markup=get_admin_panel_keyboard())
    else:
        user_role = user.get("role")
        if user_role == "supporter":
            supporter_perms = (user.get("permissions") or "").split(",")
            text = f"👋 {welcome}\n\n🛡️ <b>لوحة تحكم الداعم</b>\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاختر من القائمة:"
            bot.edit_message_text(text, msg.chat.id, msg.message_id, reply_markup=get_supporter_panel_keyboard(supporter_perms))
        else:
            text = f"👋 {welcome}\n\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاضغط على الزر أدناه للدخول للمتجر 🛒✨"
            bot.edit_message_text(text, msg.chat.id, msg.message_id, reply_markup=get_user_main_keyboard(web_url))

@bot.callback_query_handler(func=lambda c: c.data == "user_check_join")
def user_check_join_cb(call):
    user = get_or_create_user(call.from_user.id, call.from_user.username)
    if user and user.get("is_banned"):
        return bot.answer_callback_query(call.id, "❌ تم حظر حسابك.")
        
    is_joined, group_link = check_force_join(call.from_user.id)
    if not is_joined:
        bot.answer_callback_query(call.id, "❌ لم تنضم بعد. يرجى الانضمام أولاً.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "✅ تم التحقق من انضمامك بنجاح!")
    welcome = db.get_setting("welcome_message", "مرحباً بك في MO STORE! 🛒")
    web_url = f"{db.get_setting('bot_web_url', WEB_URL)}?tg_id={call.from_user.id}&tg_username={call.from_user.username}"
    
    if is_admin(call.from_user.id):
        text = f"👋 {welcome}\n\n🔧 <b>لوحة تحكم المدير</b>\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاختر من لوحة التحكم:"
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())
    else:
        user_role = user.get("role")
        if user_role == "supporter":
            supporter_perms = (user.get("permissions") or "").split(",")
            text = f"👋 {welcome}\n\n🛡️ <b>لوحة تحكم الداعم</b>\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاختر من القائمة:"
            bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_supporter_panel_keyboard(supporter_perms))
        else:
            text = f"👋 {welcome}\n\n💰 رصيدك: <b>{format_price(user['balance'])}</b>\n\nاضغط على الزر أدناه للدخول للمتجر 🛒✨"
            bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_user_main_keyboard(web_url))

@bot.callback_query_handler(func=lambda c: c.data == "user_balance")
def user_balance_cb(call):
    user = db.execute("SELECT balance FROM users WHERE telegram_id=?", (call.from_user.id,), fetchone=True)
    balance_str = format_price(user['balance']) if user else "0"
    bot.answer_callback_query(call.id, f"💰 رصيدك الحالي: {balance_str}")

@bot.callback_query_handler(func=lambda c: c.data == "user_referral")
def user_referral_cb(call):
    user = db.execute("SELECT referral_code FROM users WHERE telegram_id=?", (call.from_user.id,), fetchone=True)
    if user and user["referral_code"]:
        bot_un = get_current_bot_username()
        ref_link = f"https://t.me/{bot_un}?start=ref_{user['referral_code']}"
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📋 نسخ الرابط", callback_data=f"copy_ref_{user['referral_code']}"),
            InlineKeyboardButton("↩️ رجوع", callback_data="user_back_to_main")
        )
        bot.edit_message_text(
            f"🎁 <b>رابط الإحالة الخاص بك</b>\n\nشارك هذا الرابط مع أصدقائك. عند قيام صديق بالتسجيل وشحن محفظته، ستحصل على مكافأة!\n\n<b>رابطك:</b>\n<code>{ref_link}</code>",
            call.from_user.id, 
            call.message.message_id,
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "❌ تعذر جلب رابط الإحالة.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_ref_"))
def copy_ref_cb(call):
    ref_code = call.data.split("_")[2]
    bot_un = get_current_bot_username()
    ref_link = f"https://t.me/{bot_un}?start=ref_{ref_code}"
    bot.answer_callback_query(call.id, "✅ تم تجهيز الرابط للنسخ. اضغط على الرابط في الرسالة لنسخه.", show_alert=False)

@bot.callback_query_handler(func=lambda c: c.data == "user_back_to_main")
def user_back_to_main_cb(call):
    web_url = f"{db.get_setting('bot_web_url', WEB_URL)}?tg_id={call.from_user.id}&tg_username={call.from_user.username}"
    user = db.execute("SELECT balance, role, permissions FROM users WHERE telegram_id=?", (call.from_user.id,), fetchone=True)
    
    if is_admin(call.from_user.id):
        text = "🔧 <b>لوحة تحكم المدير</b>\n\nاختر من القائمة:"
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())
    elif user and user["role"] == "supporter":
        supporter_perms = (user["permissions"] or "").split(",")
        text = "🛡️ <b>لوحة تحكم الداعم</b>\n\nاختر من القائمة:"
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_supporter_panel_keyboard(supporter_perms))
    else:
        welcome = db.get_setting("welcome_message", "مرحباً بك في MO STORE! 🛒")
        balance_str = format_price(user["balance"]) if user else "0"
        text = f"👋 {welcome}\n\n💰 رصيدك: <b>{balance_str}</b>\n\nاضغط على الزر أدناه للدخول للمتجر 🛒✨"
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=get_user_main_keyboard(web_url))

@bot.callback_query_handler(func=lambda c: c.data == "admin_back")
def admin_back_cb(call):
    if not is_admin(call.from_user.id): return
    bot.edit_message_text("🔧 <b>لوحة تحكم المدير</b>\n\nاختر من القائمة:", call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_cancel")
def admin_cancel_cb(call):
    if not is_admin(call.from_user.id): return
    clear_bot_state(call.from_user.id)
    bot.edit_message_text("❌ تم الإلغاء.", call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_supporter")
def admin_add_supporter_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_supporter"): return
    set_bot_state(call.from_user.id, "admin_add_supporter")
    bot.edit_message_text("🛡️ <b>إضافة داعم جديد</b>\n\nأرسل معرّف تيليجرام (ID) المستخدم:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_supporter") and get_bot_state(m.from_user.id)[0] == "admin_add_supporter")
def handle_add_supporter_step1(message: Message):
    try:
        tg_id = int(message.text.strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ معرّف غير صحيح.", reply_markup=get_admin_panel_keyboard())
    
    user = get_or_create_user(tg_id)
    if not user:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ المستخدم غير موجود في قاعدة البيانات.", reply_markup=get_admin_panel_keyboard())
    
    set_bot_state(message.from_user.id, "admin_select_supporter_perms", {"tg_id": tg_id, "perms": []})
    
    markup = get_supporter_perms_keyboard([])
    bot.reply_to(message, f"👤 المستخدم: {user['username']}\n\n🛡️ اختر الصلاحيات المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_perm_toggle_"))
def admin_perm_toggle_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_perm_toggle_"): return
    state, data = get_bot_state(call.from_user.id)
    if state != "admin_select_supporter_perms" or not data:
        return bot.answer_callback_query(call.id, "انتهت الجلسة، يرجى المحاولة مرة أخرى", show_alert=True)
        
    perm = call.data.split("_", 3)[3]
    if perm not in data["perms"]:
        data["perms"].append(perm)
        set_bot_state(call.from_user.id, "admin_select_supporter_perms", data)
        bot.answer_callback_query(call.id, f"✅ تمت إضافة: {perm}")
    else:
        data["perms"].remove(perm)
        set_bot_state(call.from_user.id, "admin_select_supporter_perms", data)
        bot.answer_callback_query(call.id, f"❌ تمت إزالة: {perm}")
    
    markup = get_supporter_perms_keyboard(data["perms"])
    bot.edit_message_reply_markup(call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_save_perms")
def admin_save_perms_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_save_perms"): return
    state, data = get_bot_state(call.from_user.id)
    if state != "admin_select_supporter_perms" or not data:
        return bot.answer_callback_query(call.id, "انتهت الجلسة، يرجى المحاولة مرة أخرى", show_alert=True)
        
    tg_id = data["tg_id"]
    perms = ",".join(data["perms"])
    
    user = db.execute("SELECT id FROM users WHERE telegram_id=?", (tg_id,), fetchone=True)
    if user:
        db.execute("UPDATE users SET role='supporter', permissions=? WHERE id=?", (perms, user["id"]))
        clear_bot_state(call.from_user.id)
        bot.edit_message_text(f"✅ تمت إضافة المستخدم كداعم بالصلاحيات التالية:\n<code>{perms}</code>", call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())
        try:
            bot.send_message(tg_id, "🎉 <b>تهانينا!</b>\n\nتم ترقيتك إلى داعم في المتجر.")
        except: pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_list_supporters")
def admin_list_supporters_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_list_supporters"): return
    users = db.execute("SELECT id, username FROM users WHERE role='supporter'", fetch=True) or []
    text = "🛡️ <b>قائمة الداعمين</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if not users:
        text += "لا يوجد داعمون."
    for u in users:
        text += f"• {u['username']}\n"
        markup.add(InlineKeyboardButton(f"🗑️ حذف صلاحيات: {u['username']}", callback_data=f"admin_del_supporter_{u['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_supporter_"))
def admin_del_supporter_cb(call):
    if not is_admin(call.from_user.id): return
    uid = int(call.data.split("_")[3])
    db.execute("UPDATE users SET role='user', permissions='[]' WHERE id=?", (uid,))
    bot.answer_callback_query(call.id, "✅ تمت إزالة صلاحيات الداعم")
    admin_list_supporters_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_push_settings")
def admin_push_settings_cb(call):
    if not is_admin(call.from_user.id): return
    expo_id = db.get_setting("expo_project_id", "")
    set_bot_state(call.from_user.id, "admin_set_expo_id")
    text = "📱 <b>إعدادات إشعارات Push (Expo)</b>\n\n"
    text += f"معرف المشروع الحالي: <code>{expo_id or 'غير محدد'}</code>\n\n"
    text += "أرسل معرف مشروع Expo الجديد:\n"
    text += "(يمكنك الحصول عليه من لوحة تحكم Expo - Project Settings)"
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, 
                          reply_markup=InlineKeyboardMarkup().add(
                              InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_expo_id")
def handle_set_expo_id(message: Message):
    expo_id = message.text.strip()
    db.set_setting("expo_project_id", expo_id)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تم تحديث معرف مشروع Expo:\n<code>{expo_id}</code>", 
                 reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_wheel")
def admin_wheel_cb(call):
    if not is_admin(call.from_user.id): return
    gifts = get_wheel_gifts()
    text = "🎡 <b>إدارة عجلة الحظ</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if gifts:
        for g in gifts:
            status = "✅" if g["is_active"] else "❌"
            text += f"{status} {g['icon']} {g['name']} - {format_price(g['amount'])}\n"
            markup.add(InlineKeyboardButton(f"🗑️ حذف: {g['name']}", callback_data=f"admin_del_wheel_{g['id']}"))
            markup.add(InlineKeyboardButton(f"🔄 تفعيل/تعطيل: {g['name']}", callback_data=f"admin_tog_wheel_{g['id']}"))
    else:
        text += "لا توجد هدايا حالياً.\n"
    markup.add(InlineKeyboardButton("➕ إضافة هدية جديدة", callback_data="admin_add_wheel_btn"))
    markup.add(InlineKeyboardButton("⚙️ إدارة عتبات المكافآت", callback_data="admin_wheel_thresholds"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_wheel_thresholds")
def admin_wheel_thresholds_cb(call):
    if not is_admin(call.from_user.id): return
    thresholds = get_spin_thresholds()
    text = "⚙️ <b>عتبات المكافآت</b>\n\nيحصل المستخدم على دورات عند تجاوز هذه المبالغ:\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    for t in thresholds:
        text += f"• {format_price(t['threshold_amount'])} = {t['spins_awarded']} دورة\n"
        markup.add(InlineKeyboardButton(f"🗑️ حذف: {format_price(t['threshold_amount'])}", callback_data=f"admin_del_thresh_{t['id']}"))
    markup.add(InlineKeyboardButton("➕ إضافة عتبة جديدة", callback_data="admin_add_thresh_btn"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_wheel"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_thresh_btn")
def admin_add_thresh_btn_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_add_thresh")
    bot.edit_message_text("➕ <b>إضافة عتبة جديدة</b>\n\nأرسل البيانات بالشكل:\n<code>المبلغ | عدد الدورات</code>\n\nمثال: <code>50000 | 1</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_wheel_thresholds")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_add_thresh")
def handle_add_thresh(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2: return bot.reply_to(message, "❌ صيغة خاطئة")
    try:
        amount = float(parts[0].strip())
        spins = int(parts[1].strip())
    except: return bot.reply_to(message, "❌ قيم غير صحيحة")
    add_spin_threshold(amount, spins)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة العتبة: {format_price(amount)} = {spins} دورة", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_thresh_"))
def admin_del_thresh_cb(call):
    if not is_admin(call.from_user.id): return
    tid = int(call.data.split("_")[3])
    delete_spin_threshold(tid)
    bot.answer_callback_query(call.id, "تم الحذف")
    admin_wheel_thresholds_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_wheel_btn")
def admin_add_wheel_btn_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_add_wheel")
    bot.edit_message_text("➕ <b>إضافة هدية جديدة</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | المبلغ | اللون | الأيقونة</code>\n\nمثال: <code>جائزة 1000 | 1000 | #10b981 | 🎁</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_wheel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_add_wheel")
def handle_add_wheel(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4: return bot.reply_to(message, "❌ صيغة خاطئة")
    name = parts[0].strip()
    try: amount = float(parts[1].strip())
    except: return bot.reply_to(message, "❌ المبلغ غير صحيح")
    color = parts[2].strip()
    icon = parts[3].strip()
    add_wheel_gift(name, amount, color, icon, message.from_user.id)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة الهدية: {name}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_wheel_"))
def admin_del_wheel_cb(call):
    if not is_admin(call.from_user.id): return
    gid = int(call.data.split("_")[3])
    delete_wheel_gift(gid)
    bot.answer_callback_query(call.id, "تم الحذف")
    admin_wheel_cb(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_tog_wheel_"))
def admin_tog_wheel_cb(call):
    if not is_admin(call.from_user.id): return
    gid = int(call.data.split("_")[3])
    new_status = toggle_wheel_gift_status(gid)
    bot.answer_callback_query(call.id, "تم التفعيل" if new_status == 1 else "تم التعطيل")
    admin_wheel_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def admin_broadcast_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_broadcast")
    bot.edit_message_text("📨 <b>إرسال رسالة جماعية نصية</b>\n\nأرسل الرسالة النصية التي تريد إرسالها لجميع المستخدمين:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast_image")
def admin_broadcast_img_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_broadcast_image")
    bot.edit_message_text("📨 <b>إرسال رسالة جماعية بالصورة</b>\n\nأرسل الصورة مع التعليق (Caption) الذي تريد إرسالها لجميع المستخدمين:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_broadcast")
def handle_broadcast_message(message: Message):
    msg_text = message.text or message.caption or ""
    if not msg_text:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ النص فارغ.", reply_markup=get_admin_panel_keyboard())
    
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "⏳ <b>جاري إرسال الرسالة الجماعية...</b>\nسيستغرق الأمر بعض الوقت حسب عدد المستخدمين.", reply_markup=get_admin_panel_keyboard())
    
    send_broadcast_telegram("📢 رسالة من الإدارة", msg_text, image_path=None)

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_broadcast_image")
def handle_broadcast_image(message: Message):
    msg_text = message.caption or "📢 رسالة من الإدارة"
    file_id = message.photo[-1].file_id
    
    bot.reply_to(message, "⏳ <b>جاري حفظ الصورة وإرسال الرسالة الجماعية...</b>\nسيستغرق الأمر بعض الوقت حسب عدد المستخدمين.", reply_markup=get_admin_panel_keyboard())
    
    img_path = save_telegram_photo(file_id, "broadcast")
    clear_bot_state(message.from_user.id)
    
    send_broadcast_telegram("📢 رسالة من الإدارة", msg_text, image_path=img_path)

@bot.callback_query_handler(func=lambda c: c.data == "admin_channel_mgmt")
def admin_channel_mgmt_cb(call):
    if not is_admin(call.from_user.id): return
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📢 نشر في القناة", callback_data="admin_ch_post"),
        InlineKeyboardButton("🗑️ حذف منشور من القناة", callback_data="admin_ch_del"),
        InlineKeyboardButton("📊 إحصائيات القناة", callback_data="admin_ch_stats"),
        InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")
    )
    bot.edit_message_text("📢 <b>إدارة القناة</b>\n\nاختر العملية المطلوبة:", call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ch_post")
def admin_ch_post_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_ch_post")
    bot.edit_message_text("📢 <b>نشر في القناة</b>\n\nأرسل النص أو الصورة (مع التعليق) التي تريد نشرها في القناة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_channel_mgmt")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_ch_post")
def handle_ch_post(message: Message):
    channel_id = db.get_setting("force_join_group_id", FORCE_JOIN_CHANNEL_ID)
    try:
        if message.content_type == 'text':
            bot.send_message(channel_id, message.text)
        elif message.content_type == 'photo':
            bot.send_photo(channel_id, message.photo[-1].file_id, caption=message.caption or "")
        elif message.content_type == 'video':
            bot.send_video(channel_id, message.video.file_id, caption=message.caption or "")
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم النشر في القناة بنجاح.", reply_markup=get_admin_panel_keyboard())
    except Exception as e:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, f"❌ فشل النشر: {str(e)}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_force_join")
def admin_force_join_cb(call):
    if not is_admin(call.from_user.id): return
    current = db.get_setting("force_join_enabled", "1")
    new = "0" if current == "1" else "1"
    db.set_setting("force_join_enabled", new)
    status = "مفعّل ✅" if new == "1" else "معطّل ❌"
    bot.answer_callback_query(call.id, f"تم تغيير الحالة إلى: {status}")
    bot.edit_message_text(f"🔒 <b>إجبار الانضمام للقناة</b>\n\nالحالة الحالية: <b>{status}</b>\n\nالقناة الحالية: {db.get_setting('force_join_group_link', FORCE_JOIN_CHANNEL_LINK)}", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_user_stats")
def admin_user_stats_cb(call):
    if not is_admin(call.from_user.id): return
    show_count = db.get_setting("show_user_count", "0")
    new = "1" if show_count == "0" else "0"
    db.set_setting("show_user_count", new)
    status = "إظهار ✅" if new == "1" else "إخفاء ❌"
    bot.answer_callback_query(call.id, f"تم تغيير الحالة إلى: {status}")
    bot.edit_message_text(f"👥 <b>إحصائيات المستخدمين</b>\n\nعرض عدد المستخدمين في الموقع: <b>{status}</b>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_topup_requests")
def admin_topup_requests_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_topup_requests"): return
    requests = db.execute("SELECT * FROM wallet_topup_requests WHERE status='pending' ORDER BY created_at DESC LIMIT 10", fetch=True) or []
    if not requests:
        return bot.edit_message_text("💰 لا توجد طلبات شحن معلقة حالياً.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))
    markup = InlineKeyboardMarkup(row_width=2)
    text = "💰 <b>طلبات الشحن المعلقة</b>\n\n"
    for r in requests:
        user = db.execute("SELECT username FROM users WHERE id=?", (r["user_id"],), fetchone=True)
        uname = user["username"] if user else "غير معروف"
        text += f"• {uname}: {format_price(r['amount'])} | {r['transaction_number']}\n"
        markup.add(
            InlineKeyboardButton(f"✅ موافقة {r['request_id'][:8]}", callback_data=f"admin_approve_top_{r['id']}"),
            InlineKeyboardButton(f"❌ رفض {r['request_id'][:8]}", callback_data=f"admin_reject_top_{r['id']}")
        )
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_approve_top_"))
def admin_approve_top_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_approve_top_"): return
    rid = int(call.data.split("_")[3])
    req = db.execute("SELECT * FROM wallet_topup_requests WHERE id=?", (rid,), fetchone=True)
    if not req or req["status"] != "pending":
        return bot.answer_callback_query(call.id, "❌ الطلب غير موجود أو تمت معالجته", show_alert=True)
    
    db.execute("UPDATE wallet_topup_requests SET status='approved', confirmed_by=?, confirmed_at=CURRENT_TIMESTAMP WHERE id=?", (call.from_user.id, rid))
    db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (req["amount"], req["user_id"]))
    add_transaction(req["user_id"], req["amount"], "topup", f"شحن محفظة - طلب {req['request_id']}", req["request_id"])
    send_user_notification(req["user_id"], "✅ تم شحن محفظتك", f"تم تأكيد طلب الشحن {req['request_id']} ومبلغ {format_price(req['amount'])} قد أضيف لرصيدك.")
    
    process_referral_reward(req["user_id"], rid, req["amount"])
    
    bot.answer_callback_query(call.id, "✅ تمت الموافقة والشحن بنجاح")
    admin_topup_requests_cb(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_reject_top_"))
def admin_reject_top_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_reject_top_"): return
    rid = int(call.data.split("_")[3])
    req = db.execute("SELECT * FROM wallet_topup_requests WHERE id=?", (rid,), fetchone=True)
    if not req or req["status"] != "pending":
        return bot.answer_callback_query(call.id, "❌ الطلب غير موجود أو تمت معالجته", show_alert=True)
    
    db.execute("UPDATE wallet_topup_requests SET status='rejected', confirmed_by=?, confirmed_at=CURRENT_TIMESTAMP WHERE id=?", (call.from_user.id, rid))
    send_user_notification(req["user_id"], "❌ رفض طلب الشحن", f"تم رفض طلب الشحن {req['request_id']}. يرجى مراجعة الدعم إذا كان هناك خطأ.")
    
    bot.answer_callback_query(call.id, "❌ تم الرفض")
    admin_topup_requests_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_shipping_approvals")
def admin_shipping_approvals_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_shipping_approvals"): return
    orders = db.execute("SELECT * FROM purchase_orders WHERE status='pending' AND shipping_method_id IS NOT NULL ORDER BY created_at DESC LIMIT 10", fetch=True) or []
    if not orders:
        return bot.edit_message_text("🚚 لا توجد طلبات شحن معلقة حالياً.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))
    markup = InlineKeyboardMarkup(row_width=1)
    text = "🚚 <b>طلبات الشحن المعلقة</b>\n\n"
    for o in orders:
        user = db.execute("SELECT username FROM users WHERE id=?", (o["user_id"],), fetchone=True)
        uname = user["username"] if user else "غير معروف"
        text += f"• {uname}: {o['order_id']} | {format_price(o['total_price'])}\n"
        markup.add(InlineKeyboardButton(f"✅ موافقة وإتمام {o['order_id'][:10]}", callback_data=f"admin_ship_approve_{o['id']}"))
        markup.add(InlineKeyboardButton(f"❌ رفض {o['order_id'][:10]}", callback_data=f"admin_ship_reject_{o['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_ship_approve_"))
def admin_ship_approve_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_ship_approve_"): return
    oid = int(call.data.split("_")[3])
    order = db.execute("SELECT * FROM purchase_orders WHERE id=?", (oid,), fetchone=True)
    if not order:
        return bot.answer_callback_query(call.id, "❌ الطلب غير موجود", show_alert=True)
    
    db.execute("UPDATE purchase_orders SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
    send_user_notification(order["user_id"], "✅ تم تأكيد طلبك", f"تم تأكيد طلبك {order['order_id']} وسيتم شحنه قريباً.")
    bot.answer_callback_query(call.id, "✅ تم تأكيد الطلب")
    admin_shipping_approvals_cb(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_ship_reject_"))
def admin_ship_reject_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_ship_reject_"): return
    oid = int(call.data.split("_")[3])
    order = db.execute("SELECT * FROM purchase_orders WHERE id=?", (oid,), fetchone=True)
    if not order:
        return bot.answer_callback_query(call.id, "❌ الطلب غير موجود", show_alert=True)
    
    db.execute("UPDATE purchase_orders SET status='failed', completed_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
    db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (order["total_price"], order["user_id"]))
    add_transaction(order["user_id"], order["total_price"], "refund", f"استرداد طلب {order['order_id']}", order["order_id"])
    send_user_notification(order["user_id"], "❌ رفض طلبك", f"تم رفض طلبك {order['order_id']} وتم استرداد المبلغ لمحفظتك.")
    bot.answer_callback_query(call.id, "❌ تم الرفض واسترداد المبلغ")
    admin_shipping_approvals_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_settings")
def admin_settings_cb(call):
    if not is_admin(call.from_user.id): return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 إظهار عدد المستخدمين", callback_data="admin_user_stats"),
        InlineKeyboardButton("🎁 العروض في الأسفل", callback_data="admin_toggle_bottom_offers")
    )
    markup.add(
        InlineKeyboardButton("🔔 الإشعارات المنبثقة", callback_data="admin_toggle_popups"),
        InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")
    )
    bot.edit_message_text("⚙️ <b>الإعدادات العامة</b>\n\nاختر الإعداد لتعديله:", call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_toggle_bottom_offers")
def admin_toggle_bottom_offers_cb(call):
    if not is_admin(call.from_user.id): return
    current = db.get_setting("enable_offers_section", "1")
    new = "0" if current == "1" else "1"
    db.set_setting("enable_offers_section", new)
    status = "مفعّل ✅" if new == "1" else "معطّل ❌"
    bot.answer_callback_query(call.id, f"تم التغيير إلى: {status}")
    bot.edit_message_text(f"🎁 <b>العروض في الأسفل</b>\n\nالحالة: <b>{status}</b>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_settings")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_toggle_popups")
def admin_toggle_popups_cb(call):
    if not is_admin(call.from_user.id): return
    current = db.get_setting("enable_popup_notifications", "1")
    new = "0" if current == "1" else "1"
    db.set_setting("enable_popup_notifications", new)
    status = "مفعّل ✅" if new == "1" else "معطّل ❌"
    bot.answer_callback_query(call.id, f"تم التغيير إلى: {status}")
    bot.edit_message_text(f"🔔 <b>الإشعارات المنبثقة</b>\n\nالحالة: <b>{status}</b>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_settings")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def admin_stats_cb(call):
    if not is_admin(call.from_user.id): return
    stats = get_site_stats()
    text = f"📊 <b>إحصائيات الموقع</b>\n\n"
    text += f"📦 المنتجات: <b>{stats['products']}</b>\n"
    text += f"📂 الأقسام: <b>{stats['categories']}</b>\n"
    text += f"📋 الطلبات: <b>{stats['orders']}</b>\n"
    text += f"✅ طلبات مكتملة: <b>{stats['completed']}</b>\n"
    text += f"💰 الإيرادات: <b>{format_price(stats['total_revenue'])}</b>\n"
    text += f"📥 شحنات المحفظة: <b>{format_price(stats['total_topup'])}</b>\n"
    text += f"🎁 الهدايا المتاحة: <b>{stats['gifts']}</b>\n"
    text += f"⭐ مستخدمو VIP: <b>{stats['vip_users']}</b>\n"
    text += f"🚫 المحظورون: <b>{stats['banned_users']}</b>\n"
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_sync")
def admin_sync_cb(call):
    if not is_admin(call.from_user.id): return
    bot.edit_message_text("🔄 <b>بدء المزامنة...</b>\n\nقد يستغرق الأمر عدة دقائق. سيتم إعلامك عند الانتهاء.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))
    
    def run_sync_async():
        try:
            engine = SyncEngine()
            summary = engine.run()
            bot.send_message(call.from_user.id, f"✅ <b>اكتملت المزامنة</b>\n\n{summary}")
        except Exception as e:
            bot.send_message(call.from_user.id, f"❌ <b>خطأ في المزامنة:</b>\n{str(e)}")
    
    threading.Thread(target=run_sync_async, daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data == "admin_maintenance")
def admin_maintenance_cb(call):
    if not is_admin(call.from_user.id): return
    is_active, _ = is_maintenance_active()
    markup = InlineKeyboardMarkup(row_width=1)
    if is_active:
        markup.add(InlineKeyboardButton("✅ إيقاف الصيانة", callback_data="admin_stop_maint"))
        text = "🔧 <b>وضع الصيانة مفعّل</b>\n\nالموقع حالياً تحت الصيانة."
    else:
        markup.add(InlineKeyboardButton("🚀 تفعيل لمدة ساعة", callback_data="admin_start_maint_60"))
        markup.add(InlineKeyboardButton("🚀 تفعيل لمدة 3 ساعات", callback_data="admin_start_maint_180"))
        markup.add(InlineKeyboardButton("🚀 تفعيل دائم", callback_data="admin_start_maint_0"))
        text = "🔧 <b>وضع الصيانة معطّل</b>\n\nاختر مدة الصيانة:"
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_start_maint_"))
def admin_start_maint_cb(call):
    if not is_admin(call.from_user.id): return
    duration = int(call.data.split("_")[3])
    msg = db.get_setting("maintenance_message", "الموقع تحت الصيانة، سنعود قريباً!")
    start_maintenance(duration, msg)
    bot.answer_callback_query(call.id, "✅ تم تفعيل الصيانة")
    admin_back_cb(call)
    send_broadcast_telegram("🔧 وضع الصيانة", f"الموقع الآن تحت الصيانة. {msg}")

@bot.callback_query_handler(func=lambda c: c.data == "admin_stop_maint")
def admin_stop_maint_cb(call):
    if not is_admin(call.from_user.id): return
    stop_maintenance()
    bot.answer_callback_query(call.id, "✅ تم إيقاف الصيانة")
    admin_back_cb(call)
    send_broadcast_telegram("✅ انتهاء الصيانة", "تم إيقاف وضع الصيانة، الموقع متاح الآن للجميع!")

@bot.callback_query_handler(func=lambda c: c.data == "admin_web_url")
def admin_web_url_cb(call):
    if not is_admin(call.from_user.id): return
    url = db.get_setting("bot_web_url", WEB_URL)
    bot.edit_message_text(f"🌐 <b>رابط المتجر</b>\n\nالرابط الحالي:\n<code>{url}</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_apibalance")
def admin_apibalance_cb(call):
    if not is_admin(call.from_user.id): return
    bot.edit_message_text("💳 <b>جاري فحص رصيد API...</b>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back")))
    try:
        profile = api_client.get_profile()
        if profile and isinstance(profile, dict):
            balance = profile.get("balance", "غير متوفر")
            bot.send_message(call.from_user.id, f"💳 <b>رصيد API</b>\n\nالرصيد الحالي: <b>{balance}</b>")
        else:
            bot.send_message(call.from_user.id, "❌ تعذر جلب الرصيد.")
    except Exception as e:
        bot.send_message(call.from_user.id, f"❌ خطأ: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == "admin_users")
def admin_users_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_users"): return
    users = db.execute("SELECT id, username, balance, is_banned FROM users ORDER BY id DESC LIMIT 20", fetch=True) or []
    text = "👥 <b>أحدث 20 مستخدم</b>\n\nاختر مستخدماً لإدارة حسابه:"
    markup = InlineKeyboardMarkup(row_width=1)
    for u in users:
        status = "🚫" if u["is_banned"] else "✅"
        markup.add(InlineKeyboardButton(f"{status} {u['username']} - {format_price(u['balance'])}", callback_data=f"admin_manage_user_{u['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_manage_user_"))
def admin_manage_user_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_manage_user_"): return
    uid = int(call.data.split("_")[3])
    user = db.execute("SELECT id, username, balance, is_banned, ban_reason, phone, telegram_id, created_at FROM users WHERE id=?", (uid,), fetchone=True)
    if not user:
        return bot.answer_callback_query(call.id, "❌ المستخدم غير موجود", show_alert=True)
    
    text = f"👤 <b>إدارة المستخدم</b>\n\n"
    text += f"🆔 ID: <code>{user['telegram_id']}</code>\n"
    text += f"👤 الاسم: {user['username']}\n"
    text += f"📱 الهاتف: {user['phone'] or 'غير متوفر'}\n"
    text += f"💰 الرصيد: {format_price(user['balance'])}\n"
    text += f"📅 الانضمام: {user['created_at'][:10]}\n"
    if user['is_banned']:
        text += f"🚫 محظور: {user['ban_reason'] or 'لا يوجد سبب'}\n"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💰 تعديل الرصيد", callback_data=f"admin_quick_edit_bal_{user['id']}"))
    if user['is_banned']:
        markup.add(InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_{user['id']}"))
    else:
        markup.add(InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_{user['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_users"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_edit_balance")
def admin_edit_balance_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_edit_balance"): return
    set_bot_state(call.from_user.id, "admin_edit_balance")
    bot.edit_message_text("💰 <b>تعديل رصيد مستخدم</b>\n\nأرسل معرّف تيليجرام (ID) المستخدم:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_edit_balance") and get_bot_state(m.from_user.id)[0] == "admin_edit_balance")
def handle_edit_balance_step1(message: Message):
    try:
        tg_id = int(message.text.strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ معرّف غير صحيح.", reply_markup=get_admin_panel_keyboard())
    
    user = db.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,), fetchone=True)
    if not user:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ المستخدم غير موجود.", reply_markup=get_admin_panel_keyboard())
    
    set_bot_state(message.from_user.id, "admin_edit_balance_amount", {"user_id": user["id"]})
    bot.reply_to(message, f"👤 المستخدم: {user['username']}\n💰 الرصيد الحالي: {format_price(user['balance'])}\n\nأرسل المبلغ الجديد (أو المبلغ مع + أو - للإضافة/الخصم، مثال: <code>+5000</code>):")

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_edit_balance_amount") and get_bot_state(m.from_user.id)[0] == "admin_edit_balance_amount")
def handle_edit_balance_step2(message: Message):
    state, data = get_bot_state(message.from_user.id)
    if not data or "user_id" not in data:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ خطأ، أعد المحاولة.", reply_markup=get_admin_panel_keyboard())
    
    amount_str = message.text.strip()
    try:
        if amount_str.startswith("+"):
            amount = float(amount_str[1:])
            action = "add"
        elif amount_str.startswith("-"):
            amount = float(amount_str[1:])
            action = "sub"
        else:
            amount = float(amount_str)
            action = "set"
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ مبلغ غير صحيح.", reply_markup=get_admin_panel_keyboard())
    
    user_id = data["user_id"]
    user = db.execute("SELECT balance, username FROM users WHERE id=?", (user_id,), fetchone=True)
    
    if action == "add":
        new_balance = user["balance"] + amount
        add_transaction(user_id, amount, "admin_adjustment", f"إضافة رصيد بواسطة الإدارة")
    elif action == "sub":
        new_balance = user["balance"] - amount
        add_transaction(user_id, -amount, "admin_adjustment", f"خصم رصيد بواسطة الإدارة")
    else:
        new_balance = amount
        add_transaction(user_id, new_balance - user["balance"], "admin_adjustment", f"تعديل الرصيد بواسطة الإدارة")
    
    db.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))
    clear_bot_state(message.from_user.id)
    
    bot.reply_to(message, f"✅ تم تعديل رصيد {user['username']}.\n💰 الرصيد الجديد: {format_price(new_balance)}", reply_markup=get_admin_panel_keyboard())
    send_user_notification(user_id, "💰 تحديث الرصيد", f"تم تحديث رصيدك بواسطة الإدارة.\nرصيدك الحالي: {format_price(new_balance)}")

@bot.callback_query_handler(func=lambda c: c.data == "admin_search_user")
def admin_search_user_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_search_user"): return
    set_bot_state(call.from_user.id, "admin_search_user")
    bot.edit_message_text("👤 <b>بحث عن مستخدم</b>\n\nأرسل معرّف تيليجرام (ID) أو اسم المستخدم:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_search_user") and get_bot_state(m.from_user.id)[0] == "admin_search_user")
def handle_search_user(message: Message):
    query = message.text.strip()
    user = None
    if query.isdigit():
        user = db.execute("SELECT * FROM users WHERE telegram_id=? OR id=?", (int(query), int(query)), fetchone=True)
    else:
        user = db.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query}%",), fetchone=True)
    
    clear_bot_state(message.from_user.id)
    if not user:
        return bot.reply_to(message, "❌ المستخدم غير موجود.", reply_markup=get_admin_panel_keyboard())
    
    text = f"👤 <b>معلومات المستخدم</b>\n\n"
    text += f"🆔 ID: <code>{user['telegram_id']}</code>\n"
    text += f"👤 الاسم: {user['username']}\n"
    text += f"💰 الرصيد: {format_price(user['balance'])}\n"
    text += f"📦 الطلبات: {user['total_orders']}\n"
    text += f"💸 الإنفاق: {format_price(user['total_spent'])}\n"
    text += f"⭐ VIP: {'نعم' if user['is_vip'] else 'لا'}\n"
    text += f"🚫 محظور: {'نعم' if user['is_banned'] else 'لا'}\n"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💰 تعديل الرصيد", callback_data=f"admin_quick_edit_bal_{user['id']}"))
    if user['is_banned']:
        markup.add(InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_{user['id']}"))
    else:
        markup.add(InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_{user['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    
    bot.reply_to(message, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_quick_edit_bal_"))
def admin_quick_edit_bal_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_quick_edit_bal_"): return
    uid = int(call.data.split("_")[4])
    set_bot_state(call.from_user.id, "admin_edit_balance_amount", {"user_id": uid})
    user = db.execute("SELECT username, balance FROM users WHERE id=?", (uid,), fetchone=True)
    if user:
        bot.edit_message_text(f"👤 المستخدم: {user['username']}\n💰 الرصيد الحالي: {format_price(user['balance'])}\n\nأرسل المبلغ الجديد (أو المبلغ مع + أو - للإضافة/الخصم):", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))
    else:
        bot.answer_callback_query(call.id, "❌ المستخدم غير موجود", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_ban_"))
def admin_ban_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_ban_"): return
    uid = int(call.data.split("_")[2])
    db.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
    bot.answer_callback_query(call.id, "🚫 تم الحظر")
    admin_back_cb(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_unban_"))
def admin_unban_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_unban_"): return
    uid = int(call.data.split("_")[2])
    db.execute("UPDATE users SET is_banned=0 WHERE id=?", (uid,))
    bot.answer_callback_query(call.id, "✅ تم فك الحظر")
    admin_back_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_store_name")
def admin_store_name_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_store_name")
    bot.edit_message_text("📝 <b>اسم المتجر</b>\n\nأرسل الاسم الجديد:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_store_name")
def handle_set_store_name(message: Message):
    db.set_setting("store_name", message.text.strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث اسم المتجر.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_store_desc")
def admin_store_desc_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_store_desc")
    bot.edit_message_text("📝 <b>وصف المتجر</b>\n\nأرسل الوصف الجديد:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_store_desc")
def handle_set_store_desc(message: Message):
    db.set_setting("store_description", message.text.strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث الوصف.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_welcome_msg")
def admin_welcome_msg_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_welcome_msg")
    bot.edit_message_text("📝 <b>رسالة الترحيب</b>\n\nأرسل الرسالة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_welcome_msg")
def handle_set_welcome_msg(message: Message):
    db.set_setting("welcome_message", message.text.strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث رسالة الترحيب.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_footer")
def admin_footer_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_footer")
    bot.edit_message_text("📝 <b>نص الفوتر</b>\n\nأرسل النص الجديد:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_footer")
def handle_set_footer(message: Message):
    db.set_setting("footer_text", message.text.strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث الفوتر.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_profit")
def admin_profit_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_profit")
    bot.edit_message_text("💰 <b>نسبة الربح</b>\n\nالنسبة الحالية: " + db.get_setting("profit_percentage", "15") + "%\n\nأرسل النسبة الجديدة (مثال: 20):", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_profit")
def handle_set_profit(message: Message):
    try:
        profit = float(message.text.strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())
    
    db.set_setting("profit_percentage", str(profit))
    recalculate_all_prices()
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تم تحديث نسبة الربح إلى {profit}% وتم إعادة حساب الأسعار.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_promo_bar")
def admin_promo_bar_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_promo")
    bot.edit_message_text("📢 <b>شريط العروض</b>\n\nالنص الحالي: " + db.get_setting("promo_bar_text", "") + "\n\nأرسل النص الجديد:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_promo")
def handle_set_promo(message: Message):
    db.set_setting("promo_bar_text", message.text.strip())
    db.set_setting("enable_promo_bar", "1")
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث شريط العروض.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_support_links")
def admin_support_links_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_support_links")
    bot.edit_message_text("🔗 <b>روابط الدعم</b>\n\nأرسل الروابط بالشكل:\n<code>واتساب | تلجرام</code>\n\nمثال:\n<code>https://wa.me/963999999999 | https://t.me/yourtelegram</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_support_links")
def handle_set_support_links(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    db.set_setting("support_whatsapp", parts[0].strip())
    db.set_setting("support_telegram", parts[1].strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث روابط الدعم.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_channel")
def admin_channel_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_channel")
    bot.edit_message_text("📢 <b>قناة الإجبار</b>\n\nأرسل البيانات بالشكل:\n<code>معرف القناة (-100...) | رابط القناة</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_channel")
def handle_set_channel(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    db.set_setting("force_join_group_id", parts[0].strip())
    db.set_setting("force_join_group_link", parts[1].strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث قناة الإجبار.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_gift_btn")
def admin_add_gift_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_gift_btn"): return
    set_bot_state(call.from_user.id, "admin_add_gift")
    bot.edit_message_text("🎁 <b>إضافة كود هدية</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | الوصف | السعر | الكود</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_gift") and get_bot_state(m.from_user.id)[0] == "admin_add_gift")
def handle_add_gift(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    name, desc, price, code = [p.strip() for p in parts[:4]]
    try: price = float(price)
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ السعر غير صحيح.", reply_markup=get_admin_panel_keyboard())
    add_gift_code(name, desc, price, code, created_by=message.from_user.id)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة الهدية: {name}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_offer_btn")
def admin_add_offer_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_offer_btn"): return
    set_bot_state(call.from_user.id, "admin_add_offer")
    bot.edit_message_text("🏷️ <b>إضافة عرض جديد</b>\n\nأرسل البيانات بالشكل:\n<code>معرف المنتج | العنوان | الوصف | نسبة الخصم</code>\n\nمثال: <code>1 | عرض خاص | خصم لفترة محدودة | 20</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_offer") and get_bot_state(m.from_user.id)[0] == "admin_add_offer")
def handle_add_offer(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    try:
        prod_id = int(parts[0].strip())
        title = parts[1].strip()
        desc = parts[2].strip()
        discount = float(parts[3].strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ بيانات غير صحيحة.", reply_markup=get_admin_panel_keyboard())
    
    success, msg = create_product_offer(prod_id, title, desc, discount, created_by=message.from_user.id)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ " + msg if success else "❌ " + msg, reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_product")
def admin_add_product_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_product"): return
    set_bot_state(call.from_user.id, "admin_add_product")
    bot.edit_message_text("📦 <b>إضافة منتج جديد</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | السعر | القسم | الوصف</code>\n\nملاحظة: القسم يجب أن يكون معرف القسم (ID).", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_product") and get_bot_state(m.from_user.id)[0] == "admin_add_product")
def handle_add_product(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    name = parts[0].strip()
    try: price = float(parts[1].strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ السعر غير صحيح.", reply_markup=get_admin_panel_keyboard())
    try: cat_id = int(parts[2].strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ معرف القسم غير صحيح.", reply_markup=get_admin_panel_keyboard())
    desc = parts[3].strip()
    
    api_id = f"manual_{uuid.uuid4().hex[:8]}"
    db.execute("INSERT INTO products (api_product_id, name, description, category_id, original_price, sell_price, is_active, product_type) VALUES (?, ?, ?, ?, ?, ?, 1, 'digital')", (api_id, name, desc, cat_id, price, price))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة المنتج: {name}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_category")
def admin_add_category_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_category"): return
    set_bot_state(call.from_user.id, "admin_add_category")
    bot.edit_message_text("📂 <b>إضافة قسم جديد</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | الوصف</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_category") and get_bot_state(m.from_user.id)[0] == "admin_add_category")
def handle_add_category(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    name = parts[0].strip()
    desc = parts[1].strip()
    api_id = f"manual_cat_{uuid.uuid4().hex[:8]}"
    db.execute("INSERT INTO categories (name, description, api_category_id, is_active) VALUES (?, ?, ?, 1)", (name, desc, api_id))
    invalidate_categories_cache()
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة القسم: {name}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_discount")
def admin_add_discount_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_discount"): return
    set_bot_state(call.from_user.id, "admin_add_discount")
    bot.edit_message_text("🎟️ <b>إضافة كود خصم</b>\n\nأرسل البيانات بالشكل:\n<code>الكود | نوع الخصم | القيمة | الحد الأدنى للطلب</code>\n\nنوع الخصم: percentage أو fixed", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_discount") and get_bot_state(m.from_user.id)[0] == "admin_add_discount")
def handle_add_discount(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    code = parts[0].strip().upper()
    dtype = parts[1].strip()
    try:
        value = float(parts[2].strip())
        min_order = float(parts[3].strip())
    except:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ قيم غير صحيحة.", reply_markup=get_admin_panel_keyboard())
    
    db.execute("INSERT INTO discount_codes (code, discount_type, discount_value, min_order, is_active) VALUES (?, ?, ?, ?, 1)", (code, dtype, value, min_order))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة كود الخصم: {code}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_blog")
def admin_add_blog_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_blog"): return
    set_bot_state(call.from_user.id, "admin_add_blog")
    bot.edit_message_text("📝 <b>إضافة مقال للمدونة</b>\n\nأرسل البيانات بالشكل:\n<code>العنوان | الرابط (slug) | المحتوى</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_blog") and get_bot_state(m.from_user.id)[0] == "admin_add_blog")
def handle_add_blog(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    title = parts[0].strip()
    slug = parts[1].strip()
    content = parts[2].strip()
    
    db.execute("INSERT INTO blog_posts (title, slug, content, is_published) VALUES (?, ?, ?, 1)", (title, slug, content))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة المقال: {title}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_faq")
def admin_add_faq_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_faq"): return
    set_bot_state(call.from_user.id, "admin_add_faq")
    bot.edit_message_text("❓ <b>إضافة سؤال شائع</b>\n\nأرسل البيانات بالشكل:\n<code>السؤال | الجواب</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_faq") and get_bot_state(m.from_user.id)[0] == "admin_add_faq")
def handle_add_faq(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    question = parts[0].strip()
    answer = parts[1].strip()
    
    db.execute("INSERT INTO faqs (question, answer, is_active) VALUES (?, ?, 1)", (question, answer))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تمت إضافة السؤال الشائع.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_contest")
def admin_add_contest_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_contest"): return
    set_bot_state(call.from_user.id, "admin_add_contest")
    bot.edit_message_text("🏆 <b>إضافة مسابقة جديدة</b>\n\nأرسل البيانات بالشكل:\n<code>العنوان | الوصف | الجائزة | تاريخ الانتهاء (YYYY-MM-DD)</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_contest") and get_bot_state(m.from_user.id)[0] == "admin_add_contest")
def handle_add_contest(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    title = parts[0].strip()
    desc = parts[1].strip()
    prize = parts[2].strip()
    end_date = parts[3].strip()
    
    db.execute("INSERT INTO contests (title, description, prize, end_date, is_active) VALUES (?, ?, ?, ?, 1)", (title, desc, prize, end_date))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, f"✅ تمت إضافة المسابقة: {title}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_logo")
def admin_logo_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_logo")
    bot.edit_message_text("🖼️ <b>شعار المتجر</b>\n\nأرسل الصورة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_logo")
def handle_set_logo(message: Message):
    file_id = message.photo[-1].file_id
    img_path = save_telegram_photo(file_id, "logo")
    if img_path:
        db.set_setting("store_logo", img_path)
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث الشعار.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_bg")
def admin_bg_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_bg")
    bot.edit_message_text("🌌 <b>خلفية الموقع</b>\n\nأرسل الصورة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_bg")
def handle_set_bg(message: Message):
    file_id = message.photo[-1].file_id
    img_path = save_telegram_photo(file_id, "bg")
    if img_path:
        db.set_setting("site_background", img_path)
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث الخلفية.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_welcome_popup_img")
def admin_welcome_popup_img_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_welcome_img")
    bot.edit_message_text("🖼️ <b>صورة النافذة الترحيبية</b>\n\nأرسل الصورة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_welcome_img")
def handle_set_welcome_img(message: Message):
    file_id = message.photo[-1].file_id
    img_path = save_telegram_photo(file_id, "welcome")
    if img_path:
        db.set_setting("welcome_popup_image", img_path)
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث صورة الترحيب.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_ad_image")
def admin_ad_image_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_add_ad_image")
    bot.edit_message_text("📢 <b>إضافة إعلان صورة</b>\n\nأرسل الصورة مع التعليق (Caption) كرابط للإعلان:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_add_ad_image")
def handle_add_ad_image(message: Message):
    link = message.caption or ""
    file_id = message.photo[-1].file_id
    img_path = save_telegram_photo(file_id, "ad")
    if img_path:
        db.execute("INSERT INTO ads (ad_type, title, image_path, link_url, position, is_active) VALUES ('image', ?, ?, ?, 'top', 1)", (link, img_path, link))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تمت إضافة إعلان الصورة.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_ad_text")
def admin_ad_text_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_add_ad_text")
    bot.edit_message_text("📢 <b>إضافة إعلان نصي</b>\n\nأرسل النص:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_add_ad_text")
def handle_add_ad_text(message: Message):
    text = message.text.strip()
    db.execute("INSERT INTO ads (ad_type, content, position, is_active) VALUES ('text', ?, 'top', 1)", (text,))
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تمت إضافة الإعلان النصي.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_maint_images")
def admin_maint_images_cb(call):
    if not is_admin(call.from_user.id): return
    images = get_maintenance_images()
    text = "🖼️ <b>صور الصيانة</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if images:
        for img in images:
            text += f"• {img['title'] or 'صورة'} (ID: {img['id']})\n"
            markup.add(InlineKeyboardButton(f"🗑️ حذف {img['id']}", callback_data=f"admin_del_maint_{img['id']}"))
    else:
        text += "لا توجد صور حالياً.\n"
    markup.add(InlineKeyboardButton("➕ إضافة صورة", callback_data="admin_add_maint_img"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_maint_img")
def admin_add_maint_img_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_add_maint_img")
    bot.edit_message_text("➕ <b>إضافة صورة صيانة</b>\n\nأرسل الصورة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_maint_images")))

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_add_maint_img")
def handle_add_maint_img(message: Message):
    file_id = message.photo[-1].file_id
    title = message.caption or ""
    img_path = save_telegram_photo(file_id, "maint")
    if img_path:
        add_maintenance_image(img_path, title)
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تمت إضافة صورة الصيانة.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة.")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_maint_"))
def admin_del_maint_cb(call):
    if not is_admin(call.from_user.id): return
    mid = int(call.data.split("_")[3])
    delete_maintenance_image(mid)
    bot.answer_callback_query(call.id, "تم الحذف")
    admin_maint_images_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_send_notif")
def admin_send_notif_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_send_notif")
    bot.edit_message_text("🔔 <b>إرسال إشعار للمستخدمين</b>\n\nأرسل نص الإشعار بالشكل:\n<code>العنوان | الرسالة</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_send_notif")
def handle_send_notif(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    title = parts[0].strip()
    msg = parts[1].strip()
    send_broadcast_telegram(title, msg)
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم إرسال الإشعار بنجاح.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_list_products")
def admin_list_products_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_list_products"): return
    products = db.execute("SELECT id, name, sell_price, is_active FROM products ORDER BY id DESC LIMIT 20", fetch=True) or []
    text = "📦 <b>أحدث 20 منتج</b>\n\n"
    for p in products:
        status = "✅" if p["is_active"] else "❌"
        text += f"{status} ID: {p['id']} - {p['name']} ({format_price(p['sell_price'])})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_sync_product")
def admin_sync_product_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_sync_product"): return
    set_bot_state(call.from_user.id, "admin_sync_product")
    bot.edit_message_text("📦 <b>مزامنة منتج</b>\n\nأرسل معرف المنتج (API ID) للمزامنة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_sync_product") and get_bot_state(m.from_user.id)[0] == "admin_sync_product")
def handle_sync_product(message: Message):
    api_id = message.text.strip()
    try:
        data = api_client.get_products(products_id=api_id)
        if data:
            bot.reply_to(message, "✅ تم جلب البيانات بنجاح. يرجى تشغيل المزامنة الكاملة لتطبيق التغييرات.", reply_markup=get_admin_panel_keyboard())
        else:
            bot.reply_to(message, "❌ تعذر جلب البيانات لهذا المعرف.", reply_markup=get_admin_panel_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=get_admin_panel_keyboard())
    clear_bot_state(message.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_search_product")
def admin_search_product_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_search_product"): return
    set_bot_state(call.from_user.id, "admin_search_product")
    bot.edit_message_text("🔍 <b>بحث عن منتج</b>\n\nأرسل اسم المنتج أو معرفه:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_search_product") and get_bot_state(m.from_user.id)[0] == "admin_search_product")
def handle_search_product(message: Message):
    query = message.text.strip()
    products = db.execute("SELECT id, name, sell_price FROM products WHERE name LIKE ? OR api_product_id LIKE ?", (f"%{query}%", f"%{query}%"), fetch=True) or []
    clear_bot_state(message.from_user.id)
    if not products:
        return bot.reply_to(message, "❌ لا توجد نتائج.", reply_markup=get_admin_panel_keyboard())
    text = "🔍 <b>نتائج البحث</b>\n\n"
    for p in products:
        text += f"ID: {p['id']} - {p['name']} ({format_price(p['sell_price'])})\n"
    bot.reply_to(message, text, reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_recalc_prices")
def admin_recalc_prices_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_recalc_prices"): return
    count = recalculate_all_prices()
    bot.answer_callback_query(call.id, f"✅ تم تحديث أسعار {count} منتج")
    admin_back_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_list_categories")
def admin_list_categories_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_list_categories"): return
    cats = db.execute("SELECT id, name FROM categories ORDER BY id DESC LIMIT 20", fetch=True) or []
    text = "📂 <b>الأقسام</b>\n\n"
    for c in cats:
        text += f"ID: {c['id']} - {c['name']}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_move_subcat")
def admin_move_subcat_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_move_subcat"): return
    set_bot_state(call.from_user.id, "admin_move_subcat")
    bot.edit_message_text("🔀 <b>نقل قسم فرعي</b>\n\nأرسل البيانات بالشكل:\n<code>معرف القسم الفرعي | معرف القسم الأب الجديد</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_move_subcat") and get_bot_state(m.from_user.id)[0] == "admin_move_subcat")
def handle_move_subcat(message: Message):
    parts = message.text.split("|")
    if len(parts) < 2:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    try:
        sub_id = int(parts[0].strip())
        parent_id = int(parts[1].strip())
        db.execute("UPDATE categories SET parent_id=? WHERE id=?", (str(parent_id), sub_id))
        invalidate_categories_cache()
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم نقل القسم.", reply_markup=get_admin_panel_keyboard())
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ خطأ.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_currency")
def admin_currency_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_currency")
    bot.edit_message_text("💱 <b>عملة المتجر</b>\n\nالعملة الحالية: " + db.get_setting("currency", "ل.س") + "\n\nأرسل العملة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_currency")
def handle_set_currency(message: Message):
    db.set_setting("currency", message.text.strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث العملة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_exchange_rate")
def admin_exchange_rate_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_exchange_rate")
    bot.edit_message_text("📊 <b>سعر الصرف</b>\n\nالسعر الحالي: " + db.get_setting("price_exchange_rate", "1") + "\n\nأرسل السعر الجديد:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_exchange_rate")
def handle_set_exchange_rate(message: Message):
    try:
        rate = float(message.text.strip())
        db.set_setting("price_exchange_rate", str(rate))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث سعر الصرف.", reply_markup=get_admin_panel_keyboard())
        send_broadcast_telegram("💱 تحديث سعر الصرف", f"تم تحديث سعر الصرف الجديد إلى {rate} ل.س للدولار الواحد. سيتم تحديث الأسعار تلقائياً عند التحويل.")
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data in ["admin_topup_commission", "admin_min_shipping", "admin_min_order", "admin_free_shipping", "admin_stock_alert"])
def admin_numeric_settings_cb(call):
    if not is_admin(call.from_user.id): return
    settings_map = {
        "admin_topup_commission": ("topup_commission", "عمولة الشحن"),
        "admin_min_shipping": ("min_shipping_charge", "الحد الأدنى لرسوم الشحن"),
        "admin_min_order": ("min_order_amount", "الحد الأدنى للطلب"),
        "admin_free_shipping": ("free_shipping_threshold", "حد الشحن المجاني"),
        "admin_stock_alert": ("stock_alert_threshold", "حد تنبيه المخزون")
    }
    key, name = settings_map[call.data]
    set_bot_state(call.from_user.id, "admin_set_numeric", {"key": key, "name": name})
    bot.edit_message_text(f"⚙️ <b>{name}</b>\n\nالقيمة الحالية: {db.get_setting(key, '0')}\n\nأرسل القيمة الجديدة:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_numeric")
def handle_set_numeric(message: Message):
    state, data = get_bot_state(message.from_user.id)
    try:
        val = float(message.text.strip())
        db.set_setting(data["key"], str(val))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, f"✅ تم تحديث {data['name']}.", reply_markup=get_admin_panel_keyboard())
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_payments")
def admin_payments_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_payments"): return
    methods = db.execute("SELECT id, name, is_active FROM payment_methods", fetch=True) or []
    text = "💳 <b>طرق الدفع</b>\n\n"
    for m in methods:
        status = "✅" if m["is_active"] else "❌"
        text += f"{status} {m['name']}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_shipping")
def admin_shipping_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_shipping"): return
    methods = db.execute("SELECT id, name, price, price_usd, currency_type, is_active FROM shipping_methods", fetch=True) or []
    text = "🚚 <b>طرق الشحن</b>\n\n"
    for m in methods:
        status = "✅" if m["is_active"] else "❌"
        if m["currency_type"] == "USD" and m["price_usd"] > 0:
            text += f"{status} {m['name']} - {m['price_usd']}$ (~{format_price(convert_usd_to_syp(m['price_usd']))})\n"
        else:
            text += f"{status} {m['name']} - {format_price(m['price'])}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_shipping_btn")
def admin_add_shipping_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_shipping_btn"): return
    set_bot_state(call.from_user.id, "admin_add_shipping")
    bot.edit_message_text("🚚 <b>إضافة طريقة شحن (ليرة سورية) - الخطوة 1</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | السعر (ل.س) | الأيام المتوقعة | رقم المحفظة</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_shipping") and get_bot_state(m.from_user.id)[0] == "admin_add_shipping")
def handle_add_shipping(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        return bot.reply_to(message, "❌ صيغة خاطئة.")
    name, price, days, wallet = [p.strip() for p in parts[:4]]
    try: price = float(price)
    except: return bot.reply_to(message, "❌ السعر غير صحيح.")
    
    cur = db.execute("INSERT INTO shipping_methods (name, price, estimated_days, wallet_number, is_active, currency_type) VALUES (?, ?, ?, ?, 0, 'SYP')", (name, price, days, wallet))
    sm_id = cur.lastrowid
    set_bot_state(message.from_user.id, "admin_set_method_img", {"type": "shipping", "id": sm_id})
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⏭️ تخطي (بدون صورة)", callback_data="admin_skip_method_img"))
    bot.reply_to(message, f"✅ تم حفظ بيانات {name}. \n🖼️ <b>الخطوة 2:</b> أرسل صورة لطريقة الشحن الآن، أو اضغط تخطي.", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_shipping_usd_btn")
def admin_add_shipping_usd_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_shipping_usd_btn"): return
    set_bot_state(call.from_user.id, "admin_add_shipping_usd")
    bot.edit_message_text("💵 <b>إضافة طريقة شحن بالدولار - الخطوة 1</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | السعر ($) | الأيام المتوقعة | رقم المحفظة</code>\n\nسيتم تحويل السعر تلقائياً لليرة السورية حسب سعر الصرف.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_shipping_usd") and get_bot_state(m.from_user.id)[0] == "admin_add_shipping_usd")
def handle_add_shipping_usd(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        return bot.reply_to(message, "❌ صيغة خاطئة.")
    name, price_usd, days, wallet = [p.strip() for p in parts[:4]]
    try: price_usd = float(price_usd)
    except: return bot.reply_to(message, "❌ السعر غير صحيح.")
    price_syp = convert_usd_to_syp(price_usd)
    cur = db.execute("INSERT INTO shipping_methods (name, price, price_usd, estimated_days, wallet_number, is_active, currency_type) VALUES (?, ?, ?, ?, ?, 0, 'USD')", (name, price_syp, price_usd, days, wallet))
    sm_id = cur.lastrowid
    set_bot_state(message.from_user.id, "admin_set_method_img", {"type": "shipping", "id": sm_id})
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⏭️ تخطي (بدون صورة)", callback_data="admin_skip_method_img"))
    bot.reply_to(message, f"✅ تم حفظ بيانات {name}.\nالسعر: {price_usd}$ (~{format_price(price_syp)})\n\n🖼️ <b>الخطوة 2:</b> أرسل صورة لطريقة الشحن الآن، أو اضغط تخطي.", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_payment_btn")
def admin_add_payment_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_payment_btn"): return
    set_bot_state(call.from_user.id, "admin_add_payment")
    bot.edit_message_text("💳 <b>إضافة طريقة دفع - الخطوة 1</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | رقم الحساب | اسم الحساب</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_payment") and get_bot_state(m.from_user.id)[0] == "admin_add_payment")
def handle_add_payment(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        return bot.reply_to(message, "❌ صيغة خاطئة.")
    name, acc_num, acc_name = [p.strip() for p in parts[:3]]
    cur = db.execute("INSERT INTO payment_methods (name, account_number, account_name, is_active) VALUES (?, ?, ?, 0)", (name, acc_num, acc_name))
    pm_id = cur.lastrowid
    set_bot_state(message.from_user.id, "admin_set_method_img", {"type": "payment", "id": pm_id})
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⏭️ تخطي (بدون صورة)", callback_data="admin_skip_method_img"))
    bot.reply_to(message, f"✅ تم حفظ بيانات {name}. \n🖼️ <b>الخطوة 2:</b> أرسل صورة لطريقة الدفع الآن، أو اضغط تخطي.", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_topup_btn")
def admin_add_topup_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_topup_btn"): return
    set_bot_state(call.from_user.id, "admin_add_topup")
    bot.edit_message_text("📥 <b>إضافة طريقة شحن محفظة (ل.س) - الخطوة 1</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | رقم الحساب | التعليمات</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_topup") and get_bot_state(m.from_user.id)[0] == "admin_add_topup")
def handle_add_topup(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        return bot.reply_to(message, "❌ صيغة خاطئة.")
    name, acc, instr = [p.strip() for p in parts[:3]]
    cur = db.execute("INSERT INTO wallet_topup_methods (name, account_number, instructions, is_active, currency_type) VALUES (?, ?, ?, 0, 'SYP')", (name, acc, instr))
    tm_id = cur.lastrowid
    set_bot_state(message.from_user.id, "admin_set_method_img", {"type": "topup", "id": tm_id})
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⏭️ تخطي (بدون صورة)", callback_data="admin_skip_method_img"))
    bot.reply_to(message, f"✅ تم حفظ بيانات {name}. \n🖼️ <b>الخطوة 2:</b> أرسل صورة لطريقة الشحن الآن، أو اضغط تخطي.", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_topup_usd_btn")
def admin_add_topup_usd_btn_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_add_topup_usd_btn"): return
    set_bot_state(call.from_user.id, "admin_add_topup_usd")
    bot.edit_message_text("💵 <b>إضافة طريقة شحن محفظة (دولار) - الخطوة 1</b>\n\nأرسل البيانات بالشكل:\n<code>الاسم | رقم الحساب | التعليمات</code>\n\nسيتم تحويل المبلغ تلقائياً لليرة السورية عند شحن المستخدم.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_add_topup_usd") and get_bot_state(m.from_user.id)[0] == "admin_add_topup_usd")
def handle_add_topup_usd(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        return bot.reply_to(message, "❌ صيغة خاطئة.")
    name, acc, instr = [p.strip() for p in parts[:3]]
    cur = db.execute("INSERT INTO wallet_topup_methods (name, account_number, instructions, is_active, currency_type) VALUES (?, ?, ?, 0, 'USD')", (name, acc, instr))
    tm_id = cur.lastrowid
    set_bot_state(message.from_user.id, "admin_set_method_img", {"type": "topup", "id": tm_id})
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⏭️ تخطي (بدون صورة)", callback_data="admin_skip_method_img"))
    bot.reply_to(message, f"✅ تم حفظ بيانات {name}. \n🖼️ <b>الخطوة 2:</b> أرسل صورة لطريقة الشحن الآن، أو اضغط تخطي.", reply_markup=markup)

@bot.message_handler(content_types=['photo'], func=lambda m: is_admin_or_supporter(m.from_user.id, "admin_set_method_img") and get_bot_state(m.from_user.id)[0] == "admin_set_method_img")
def handle_set_method_img(message: Message):
    state, data = get_bot_state(message.from_user.id)
    if not data:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ خطأ، أعد المحاولة.", reply_markup=get_admin_panel_keyboard())
    
    file_id = message.photo[-1].file_id
    img_path = save_telegram_photo(file_id, "method")
    if img_path:
        if data["type"] == "shipping":
            db.execute("UPDATE shipping_methods SET image_path=?, is_active=1 WHERE id=?", (img_path, data["id"]))
        elif data["type"] == "payment":
            db.execute("UPDATE payment_methods SET image_path=?, is_active=1 WHERE id=?", (img_path, data["id"]))
        elif data["type"] == "topup":
            db.execute("UPDATE wallet_topup_methods SET image_path=?, is_active=1 WHERE id=?", (img_path, data["id"]))
        
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم حفظ الصورة وتفعيل الطريقة بنجاح.", reply_markup=get_admin_panel_keyboard())
    else:
        bot.reply_to(message, "❌ فشل حفظ الصورة. أعد المحاولة أو اضغط تخطي.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_skip_method_img")
def admin_skip_method_img_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_skip_method_img"): return
    state, data = get_bot_state(call.from_user.id)
    if state == "admin_set_method_img" and data:
        if data["type"] == "shipping":
            db.execute("UPDATE shipping_methods SET is_active=1 WHERE id=?", (data["id"],))
        elif data["type"] == "payment":
            db.execute("UPDATE payment_methods SET is_active=1 WHERE id=?", (data["id"],))
        elif data["type"] == "topup":
            db.execute("UPDATE wallet_topup_methods SET is_active=1 WHERE id=?", (data["id"],))
        
        clear_bot_state(call.from_user.id)
        bot.edit_message_text("✅ تم تفعيل الطريقة بدون صورة.", call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())
    else:
        clear_bot_state(call.from_user.id)
        bot.edit_message_text("❌ حدث خطأ.", call.from_user.id, call.message.message_id, reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_topup_methods")
def admin_topup_methods_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_topup_methods"): return
    methods = db.execute("SELECT id, name, account_number, currency_type FROM wallet_topup_methods", fetch=True) or []
    text = "📥 <b>طرق شحن المحفظة</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if not methods:
        text += "لا توجد طرق شحن مضافة حالياً.\n"
    else:
        for m in methods:
            cur = "USD" if m['currency_type'] == 'USD' else "ل.س"
            text += f"• {m['name']} ({cur}) - <code>{m['account_number']}</code>\n"
            markup.add(InlineKeyboardButton(f"🗑️ حذف: {m['name']}", callback_data=f"admin_del_topup_{m['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_topup_"))
def admin_del_topup_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_del_topup_"): return
    try:
        topup_id = int(call.data.split("_")[3])
        method = db.execute("SELECT image_path FROM wallet_topup_methods WHERE id=?", (topup_id,), fetchone=True)
        if method and method["image_path"]:
            try:
                filepath = os.path.join(IMAGES_DIR, method["image_path"])
                if os.path.exists(filepath): os.remove(filepath)
            except: pass
        
        db.execute("DELETE FROM wallet_topup_methods WHERE id=?", (topup_id,))
        bot.answer_callback_query(call.id, "✅ تم حذف طريقة الشحن بنجاح")
        admin_topup_methods_cb(call)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ حدث خطأ: {str(e)}", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "admin_orders")
def admin_orders_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_orders"): return
    orders = db.execute("SELECT order_id, status, total_price FROM purchase_orders ORDER BY id DESC LIMIT 10", fetch=True) or []
    text = "📋 <b>أحدث 10 طلبات</b>\n\n"
    for o in orders:
        text += f"• {o['order_id']} - {o['status']} - {format_price(o['total_price'])}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_export_orders")
def admin_export_orders_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_export_orders"): return
    bot.answer_callback_query(call.id, "⏳ جاري التصدير...")
    csv_data = export_orders_to_csv()
    with open("orders_export.csv", "w", encoding="utf-8") as f:
        f.write(csv_data)
    with open("orders_export.csv", "rb") as f:
        bot.send_document(call.from_user.id, f)
    os.remove("orders_export.csv")

@bot.callback_query_handler(func=lambda c: c.data == "admin_sales_stats")
def admin_sales_stats_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_sales_stats"): return
    stats = get_site_stats()
    text = f"📊 <b>إحصائيات المبيعات</b>\n\n"
    text += f"💰 إجمالي الإيرادات: <b>{format_price(stats['total_revenue'])}</b>\n"
    text += f"✅ طلبات مكتملة: <b>{stats['completed']}</b>\n"
    text += f"📋 إجمالي الطلبات: <b>{stats['orders']}</b>\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_transactions")
def admin_transactions_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_transactions"): return
    trans = db.execute("SELECT t.amount, t.transaction_type, t.description, u.username FROM transactions t LEFT JOIN users u ON t.user_id=u.id ORDER BY t.id DESC LIMIT 10", fetch=True) or []
    text = "💰 <b>أحدث 10 معاملات</b>\n\n"
    for t in trans:
        text += f"• {t['username'] or '?'}: {t['amount']} ({t['transaction_type']})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["admin_view_all_users"])
def admin_users_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_view_all_users"): return
    users = db.execute("SELECT id, username, balance, is_banned FROM users ORDER BY id DESC LIMIT 20", fetch=True) or []
    text = "👥 <b>أحدث 20 مستخدم</b>\n\n"
    for u in users:
        status = "🚫" if u["is_banned"] else "✅"
        text += f"{status} {u['username']} - {format_price(u['balance'])}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_banned_users")
def admin_banned_users_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_banned_users"): return
    users = db.execute("SELECT id, username, ban_reason FROM users WHERE is_banned=1", fetch=True) or []
    text = "🚫 <b>المستخدمون المحظورون</b>\n\n"
    if not users:
        text += "لا يوجد محظورون."
    for u in users:
        text += f"• {u['username']} ({u['ban_reason'] or 'لا سبب'})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_vip_users")
def admin_vip_users_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_vip_users"): return
    users = db.execute("SELECT id, username, vip_level FROM users WHERE is_vip=1", fetch=True) or []
    text = "⭐ <b>مستخدمو VIP</b>\n\n"
    if not users:
        text += "لا يوجد مستخدمو VIP."
    for u in users:
        text += f"• {u['username']} (المستوى {u['vip_level']})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_support")
def admin_support_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_support"): return
    tickets = db.execute("SELECT ticket_id, subject, status FROM support_tickets ORDER BY id DESC LIMIT 10", fetch=True) or []
    text = "🎫 <b>أحدث 10 تذاكر</b>\n\n"
    for t in tickets:
        text += f"• {t['ticket_id']} - {t['subject']} ({t['status']})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_chats")
def admin_chats_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_chats"): return
    chats = db.execute("SELECT DISTINCT user_id FROM chat_messages WHERE is_from_admin=0 AND is_read=0", fetch=True) or []
    text = "💬 <b>محادثات الدعم غير المقروءة</b>\n\n"
    for c in chats:
        user = db.execute("SELECT username FROM users WHERE id=?", (c["user_id"],), fetchone=True)
        text += f"• {user['username'] if user else c['user_id']}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ch_del")
def admin_ch_del_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_ch_del")
    bot.edit_message_text("🗑️ <b>حذف منشور من القناة</b>\n\nأرسل معرف الرسالة (Message ID) التي تريد حذفها:", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_channel_mgmt")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_ch_del")
def handle_ch_del(message: Message):
    try:
        msg_id = int(message.text.strip())
        channel_id = db.get_setting("force_join_group_id", FORCE_JOIN_CHANNEL_ID)
        bot.delete_message(channel_id, msg_id)
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم حذف المنشور.", reply_markup=get_admin_panel_keyboard())
    except Exception as e:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, f"❌ فشل الحذف: {str(e)}", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_ch_stats")
def admin_ch_stats_cb(call):
    if not is_admin(call.from_user.id): return
    channel_id = db.get_setting("force_join_group_id", FORCE_JOIN_CHANNEL_ID)
    try:
        chat = bot.get_chat(channel_id)
        text = f"📊 <b>إحصائيات القناة</b>\n\n"
        text += f"📛 الاسم: {chat.title}\n"
        text += f"👥 الأعضاء: {chat.get_member_count()}\n"
        text += f"🔗 الرابط: {db.get_setting('force_join_group_link', FORCE_JOIN_CHANNEL_LINK)}"
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_channel_mgmt")))
    except Exception as e:
        bot.edit_message_text(f"❌ خطأ: {str(e)}", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_channel_mgmt")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_offers")
def admin_offers_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_offers"): return
    offers = db.execute("SELECT po.id, p.name FROM product_offers po JOIN products p ON po.product_id=p.id WHERE po.is_active=1", fetch=True) or []
    text = "🏷️ <b>العروض النشطة</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if not offers:
        text += "لا توجد عروض حالياً."
    for o in offers:
        text += f"• {o['name']}\n"
        markup.add(InlineKeyboardButton(f"🗑️ إيقاف عرض #{o['id']}", callback_data=f"admin_stop_offer_{o['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_stop_offer_"))
def admin_stop_offer_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_stop_offer_"): return
    oid = int(call.data.split("_")[3])
    deactivate_offer(oid)
    bot.answer_callback_query(call.id, "✅ تم إيقاف العرض")
    admin_offers_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_discounts")
def admin_discounts_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_discounts"): return
    codes = db.execute("SELECT code, discount_value FROM discount_codes WHERE is_active=1", fetch=True) or []
    text = "🎟️ <b>أكواد الخصم النشطة</b>\n\n"
    for d in codes:
        text += f"• {d['code']} - {d['discount_value']}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_list_ads")
def admin_list_ads_cb(call):
    if not is_admin(call.from_user.id): return
    ads = db.execute("SELECT id, title, content FROM ads WHERE is_active=1", fetch=True) or []
    text = "📢 <b>الإعلانات النشطة</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    if not ads:
        text += "لا توجد إعلانات."
    for a in ads:
        text += f"• {a['title'] or a['content']}\n"
        markup.add(InlineKeyboardButton(f"🗑️ حذف إعلان #{a['id']}", callback_data=f"admin_del_ad_{a['id']}"))
    markup.add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_del_ad_"))
def admin_del_ad_cb(call):
    if not is_admin(call.from_user.id): return
    aid = int(call.data.split("_")[3])
    db.execute("UPDATE ads SET is_active=0 WHERE id=?", (aid,))
    bot.answer_callback_query(call.id, "تم الحذف")
    admin_list_ads_cb(call)

@bot.callback_query_handler(func=lambda c: c.data == "admin_gifts")
def admin_gifts_cb(call):
    if not is_admin_or_supporter(call.from_user.id, "admin_gifts"): return
    gifts = db.execute("SELECT id, name, price FROM gift_codes WHERE is_active=1 AND is_sold=0", fetch=True) or []
    text = "🎁 <b>أكواد الهدايا المتاحة</b>\n\n"
    for g in gifts:
        text += f"• {g['name']} - {format_price(g['price'])}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_report")
def admin_report_cb(call):
    if not is_admin(call.from_user.id): return
    stats = get_site_stats()
    text = f"📊 <b>تقرير المبيعات</b>\n\n"
    text += f"💰 الإيرادات: {format_price(stats['total_revenue'])}\n"
    text += f"✅ الطلبات المكتملة: {stats['completed']}\n"
    text += f"📥 شحنات المحفظة: {format_price(stats['total_topup'])}\n"
    text += f"⭐ مستخدمو VIP: {stats['vip_users']}\n"
    text += f"🚫 المحظورون: {stats['banned_users']}\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_colors")
def admin_colors_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_colors")
    bot.edit_message_text("🎨 <b>ألوان الموقع</b>\n\nأرسل الألوان بالشكل:\n<code>اللون الأساسي | اللون الثانوي | لون التمييز</code>\n\nمثال: <code>#7c3aed | #06b6d4 | #ec4899</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_colors")
def handle_set_colors(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    db.set_setting("primary_color", parts[0].strip())
    db.set_setting("secondary_color", parts[1].strip())
    db.set_setting("accent_color", parts[2].strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث الألوان.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_social_links")
def admin_social_links_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_social_links")
    bot.edit_message_text("📱 <b>روابط التواصل</b>\n\nأرسل البيانات بالشكل:\n<code>فيسبوك | انستغرام | تويتر | يوتيوب</code>\n\nضع - إذا لم يوجد.", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_social_links")
def handle_set_social_links(message: Message):
    parts = message.text.split("|")
    if len(parts) < 4:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    db.set_setting("social_facebook", parts[0].strip())
    db.set_setting("social_instagram", parts[1].strip())
    db.set_setting("social_twitter", parts[2].strip())
    db.set_setting("social_youtube", parts[3].strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث روابط التواصل.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_seo")
def admin_seo_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_seo")
    bot.edit_message_text("🔍 <b>إعدادات SEO</b>\n\nأرسل البيانات بالشكل:\n<code>العنوان | الوصف | الكلمات المفتاحية</code>", call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_seo")
def handle_set_seo(message: Message):
    parts = message.text.split("|")
    if len(parts) < 3:
        clear_bot_state(message.from_user.id)
        return bot.reply_to(message, "❌ صيغة خاطئة.", reply_markup=get_admin_panel_keyboard())
    db.set_setting("seo_title", parts[0].strip())
    db.set_setting("seo_description", parts[1].strip())
    db.set_setting("seo_keywords", parts[2].strip())
    clear_bot_state(message.from_user.id)
    bot.reply_to(message, "✅ تم تحديث إعدادات SEO.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_error_logs")
def admin_error_logs_cb(call):
    if not is_admin(call.from_user.id): return
    logs = db.execute("SELECT endpoint, error_message, created_at FROM api_error_logs ORDER BY id DESC LIMIT 10", fetch=True) or []
    text = "🗄️ <b>أحدث 10 سجلات أخطاء</b>\n\n"
    if not logs:
        text += "لا توجد أخطاء مسجلة."
    for l in logs:
        text += f"• {l['endpoint']}: {l['error_message'][:50]}...\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_sync_logs")
def admin_sync_logs_cb(call):
    if not is_admin(call.from_user.id): return
    logs = db.execute("SELECT sync_type, status, started_at FROM sync_logs ORDER BY id DESC LIMIT 10", fetch=True) or []
    text = "📊 <b>سجلات المزامنة</b>\n\n"
    if not logs:
        text += "لا توجد سجلات مزامنة."
    for l in logs:
        text += f"• {l['sync_type']} - {l['status']} ({l['started_at'][:16]})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_activity_log")
def admin_activity_log_cb(call):
    if not is_admin(call.from_user.id): return
    logs = db.execute("SELECT action, description, created_at FROM activity_logs ORDER BY id DESC LIMIT 10", fetch=True) or []
    text = "🔒 <b>سجل النشاط</b>\n\n"
    if not logs:
        text += "لا يوجد نشاط مسجل."
    for l in logs:
        text += f"• {l['action']} - {l['description']} ({l['created_at'][:16]})\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_loyalty")
def admin_loyalty_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_loyalty")
    text = "⭐ <b>نقاط الولاء</b>\n\n"
    text += "القيمة الحالية: " + db.get_setting("loyalty_points_per_currency", "1") + " نقطة لكل وحدة عملة\n\n"
    text += "أرسل القيمة الجديدة (مثال: 2):"
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_loyalty")
def handle_set_loyalty(message: Message):
    try:
        val = float(message.text.strip())
        db.set_setting("loyalty_points_per_currency", str(val))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث قيمة نقاط الولاء.", reply_markup=get_admin_panel_keyboard())
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_vip_settings")
def admin_vip_settings_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_vip")
    text = "💎 <b>إعدادات VIP</b>\n\n"
    text += "الحد الحالي للإنفاق ليصبح VIP: " + format_price(float(db.get_setting("vip_threshold", "100000"))) + "\n\n"
    text += "أرسل الحد الجديد:"
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_vip")
def handle_set_vip(message: Message):
    try:
        val = float(message.text.strip())
        db.set_setting("vip_threshold", str(val))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث حد VIP.", reply_markup=get_admin_panel_keyboard())
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_referral")
def admin_referral_cb(call):
    if not is_admin(call.from_user.id): return
    set_bot_state(call.from_user.id, "admin_set_referral")
    text = "🎁 <b>نظام الإحالات</b>\n\n"
    text += "المكافأة الحالية للإحالة: " + format_price(float(db.get_setting("referral_bonus", "5000"))) + "\n\n"
    text += "أرسل المكافأة الجديدة:"
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ إلغاء", callback_data="admin_cancel")))

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_bot_state(m.from_user.id)[0] == "admin_set_referral")
def handle_set_referral(message: Message):
    try:
        val = float(message.text.strip())
        db.set_setting("referral_bonus", str(val))
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "✅ تم تحديث مكافأة الإحالة.", reply_markup=get_admin_panel_keyboard())
    except:
        clear_bot_state(message.from_user.id)
        bot.reply_to(message, "❌ قيمة غير صحيحة.", reply_markup=get_admin_panel_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "admin_achievements")
def admin_achievements_cb(call):
    if not is_admin(call.from_user.id): return
    achs = db.execute("SELECT achievement_name, COUNT(*) as count FROM user_achievements GROUP BY achievement_name", fetch=True) or []
    text = "🏆 <b>الإنجازات الممنوحة</b>\n\n"
    if not achs:
        text += "لم يتم منح أي إنجازات بعد."
    for a in achs:
        text += f"• {a['achievement_name']} ({a['count']} مرة)\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("↩️ رجوع", callback_data="admin_back"))
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=markup)

# ==============================================================================
# مسارات المصادقة الخاصة بتطبيق الهاتف وإشعارات Push (مدموجة بالكامل)
# ==============================================================================
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def _get_expo_project_id():
    try:
        return db.get_setting("expo_project_id", "")
    except Exception:
        return ""

def _send_expo_push_notification(push_token, title, message, data=None):
    if not push_token:
        return False
    
    if not push_token.startswith("ExponentPushToken["):
        if push_token.startswith("ExponentPushToken"):
            pass
        else:
            push_token = f"ExponentPushToken[{push_token}]"
    
    payload = {
        "to": push_token,
        "title": title,
        "body": message,
        "sound": "default",
        "priority": "high",
        "channelId": "default",
    }
    
    if data:
        payload["data"] = data
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    project_id = _get_expo_project_id()
    if project_id:
        headers["Authorization"] = f"Bearer {project_id}"
    
    try:
        response = requests.post(EXPO_PUSH_URL, json=payload, headers=headers, timeout=10)
        result = response.json()
        
        if response.status_code == 200:
            if "data" in result:
                ticket = result["data"]
                if isinstance(ticket, dict):
                    if ticket.get("status") == "ok":
                        try:
                            db.execute(
                                "UPDATE push_tokens SET last_used=CURRENT_TIMESTAMP WHERE token=?",
                                (push_token,)
                            )
                        except Exception:
                            pass
                        return True
                    elif ticket.get("status") == "error":
                        err_detail = ticket.get("details", {})
                        err_message = ticket.get("message", "")
                        
                        if "DeviceNotRegistered" in str(err_detail) or "invalid" in str(err_message).lower():
                            try:
                                db.execute(
                                    "UPDATE push_tokens SET is_active=0 WHERE token=?",
                                    (push_token,)
                                )
                            except Exception:
                                pass
                        return False
        else:
            return False
    except Exception:
        return False
    
    return False

def _send_push_to_user(user_id, title, message, data=None):
    try:
        tokens = db.execute(
            "SELECT token FROM push_tokens WHERE user_id=? AND is_active=1",
            (user_id,),
            fetch=True
        ) or []
        
        if not tokens:
            return False
        
        sent_count = 0
        for t in tokens:
            token = t["token"] if isinstance(t, dict) else t[0]
            if _send_expo_push_notification(token, title, message, data):
                sent_count += 1
        
        return sent_count > 0
    except Exception:
        return False

def _send_push_to_all_users(title, message, data=None):
    try:
        tokens = db.execute(
            "SELECT DISTINCT token FROM push_tokens WHERE is_active=1 LIMIT 500",
            (),
            fetch=True
        ) or []
        
        sent_count = 0
        for t in tokens:
            token = t["token"] if isinstance(t, dict) else t[0]
            if _send_expo_push_notification(token, title, message, data):
                sent_count += 1
        
        return sent_count
    except Exception:
        return 0

def _cleanup_old_push_tokens():
    try:
        db.execute(
            "DELETE FROM push_tokens WHERE is_active=0 AND created_at < datetime('now', '-30 days')"
        )
        db.execute(
            "UPDATE push_tokens SET is_active=0 WHERE last_used IS NOT NULL AND last_used < datetime('now', '-90 days') AND is_active=1"
        )
        db.execute(
            "UPDATE push_tokens SET is_active=0 WHERE last_used IS NULL AND created_at < datetime('now', '-60 days') AND is_active=1"
        )
    except Exception:
        pass

def _get_user_by_token(token):
    if not token:
        return None
    try:
        row = db.execute(
            """SELECT u.* FROM user_sessions s 
               JOIN users u ON s.user_id = u.id 
               WHERE s.token = ? AND s.used = 0""",
            (token,), fetchone=True
        )
        return row_to_dict(row) if row else None
    except Exception:
        return None

def _create_session(user_id):
    token = secrets.token_hex(32)
    ip = request.environ.get('REMOTE_ADDR', '') or ''
    ua = request.environ.get('HTTP_USER_AGENT', '') or ''
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        db.execute(
            """INSERT INTO user_sessions 
               (user_id, token, ip_address, user_agent, expires_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, token, ip[:100], ua[:200], expires_at)
        )
    except Exception:
        pass
    return token

def _get_authenticated_user():
    token = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    if not token:
        token = request.args.get('token', '')

    if token:
        user = _get_user_by_token(token)
        if user:
            return user, token

    if "user_id" in session:
        user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],), fetchone=True)
        if user:
            return row_to_dict(user), None

    return None, None

@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()

    if not username or not password:
        return jsonify({"success": False, "message": "اسم المستخدم وكلمة المرور مطلوبة"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}), 400

    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,), fetchone=True)
    if existing:
        return jsonify({"success": False, "message": "اسم المستخدم موجود مسبقاً"}), 409

    pw_hash, salt = _hash_password(password)
    referral_code = f"REF_APP_{uuid.uuid4().hex[:6].upper()}"

    try:
        cur = db.execute(
            """INSERT INTO users 
               (username, password_hash, salt, phone, email, balance, min_balance, role, is_active, referral_code, created_at, last_activity) 
               VALUES (?, ?, ?, ?, ?, 0, 0, 'user', 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (username, pw_hash, salt, phone, email, referral_code)
        )
        user_id = cur.lastrowid if cur and hasattr(cur, 'lastrowid') else None
        if not user_id:
            u = db.execute("SELECT id FROM users WHERE username=?", (username,), fetchone=True)
            user_id = u["id"] if u else None

        if not user_id:
            return jsonify({"success": False, "message": "فشل إنشاء الحساب"}), 500

        token = _create_session(user_id)
        _cleanup_old_push_tokens()
        
        return jsonify({
            "success": True, 
            "message": "تم إنشاء الحساب بنجاح",
            "user_id": user_id,
            "token": token,
            "username": username
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ داخلي: {str(e)}"}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"success": False, "message": "اسم المستخدم وكلمة المرور مطلوبة"}), 400

    user = db.execute("SELECT * FROM users WHERE username = ?", (username,), fetchone=True)
    if not user:
        return jsonify({"success": False, "message": "بيانات الدخول غير صحيحة"}), 401

    user = row_to_dict(user)
    if user.get("is_banned") == 1:
        return jsonify({"success": False, "message": "هذا الحساب محظور"}), 403

    if not user["password_hash"] or not user["salt"]:
        return jsonify({"success": False, "message": "يرجى ربط حسابك بتيليجرام أو إعادة تعيين كلمة المرور"}), 403

    if not _verify_password(password, user["password_hash"], user["salt"]):
        return jsonify({"success": False, "message": "بيانات الدخول غير صحيحة"}), 401

    token = _create_session(user["id"])
    db.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP, last_activity=CURRENT_TIMESTAMP WHERE id=?", (user["id"],))

    _cleanup_old_push_tokens()

    return jsonify({
        "success": True,
        "message": "تم تسجيل الدخول بنجاح",
        "user_id": user["id"],
        "token": token,
        "username": user["username"]
    }), 200

@app.route('/api/auth/handoff', methods=['GET'])
def api_auth_handoff():
    token = request.args.get('token')
    if not token:
        return redirect('/login')
        
    user = _get_user_by_token(token)
    if not user:
        return redirect('/login')
        
    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    
    return redirect('/')

@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    user, token = _get_authenticated_user()
    
    data = request.get_json(silent=True) or {}
    push_token = data.get('push_token', '')
    
    if push_token and user:
        try:
            db.execute(
                "UPDATE push_tokens SET is_active=0 WHERE token=? AND user_id=?",
                (push_token, user["id"])
            )
        except Exception:
            pass
    
    if token:
        db.execute("UPDATE user_sessions SET used = 1 WHERE token = ?", (token,))
    
    session.clear()
    return jsonify({"success": True, "message": "تم تسجيل الخروج بنجاح"}), 200

@app.route('/api/push/register', methods=['POST'])
def api_register_push_token():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح - يجب تسجيل الدخول أولاً"}), 401

    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    push_token = (data.get('push_token') or data.get('token') or '').strip()
    device_type = (data.get('device_type') or 'android').strip()
    device_id = (data.get('device_id') or '').strip()

    if not push_token:
        return jsonify({"success": False, "message": "رمز الإشعارات مطلوب"}), 400

    try:
        existing = db.execute(
            "SELECT id, user_id FROM push_tokens WHERE token=? AND is_active=1",
            (push_token,),
            fetchone=True
        )
        
        if existing:
            if existing["user_id"] == user["id"]:
                db.execute(
                    "UPDATE push_tokens SET last_used=CURRENT_TIMESTAMP, is_active=1 WHERE token=?",
                    (push_token,)
                )
                return jsonify({"success": True, "message": "تم تحديث رمز الإشعارات بنجاح"}), 200
            else:
                db.execute(
                    "UPDATE push_tokens SET is_active=0 WHERE token=?",
                    (push_token,)
                )
        
        db.execute(
            """INSERT INTO push_tokens 
               (user_id, token, device_type, device_id, is_active, created_at, last_used) 
               VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (user["id"], push_token, device_type[:20], device_id[:200])
        )
        
        return jsonify({"success": True, "message": "تم تسجيل رمز الإشعارات بنجاح"}), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ في التسجيل: {str(e)}"}), 500

@app.route('/api/push/unregister', methods=['POST'])
def api_unregister_push_token():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    push_token = (data.get('push_token') or data.get('token') or '').strip()

    if not push_token:
        return jsonify({"success": False, "message": "رمز الإشعارات مطلوب"}), 400

    try:
        db.execute(
            "UPDATE push_tokens SET is_active=0 WHERE token=? AND user_id=?",
            (push_token, user["id"])
        )
        return jsonify({"success": True, "message": "تم إلغاء تسجيل رمز الإشعارات بنجاح"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ: {str(e)}"}), 500

@app.route('/api/push/test', methods=['POST'])
def api_test_push_notification():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    sent = _send_push_to_user(
        user["id"],
        "🔔 اختبار الإشعارات",
        "تم إرسال هذا الإشعار بنجاح! نظام الإشعارات يعمل بشكل صحيح.",
        {"type": "test", "user_id": str(user["id"])}
    )
    
    if sent:
        return jsonify({"success": True, "message": "تم إرسال إشعار الاختبار بنجاح"}), 200
    else:
        return jsonify({"success": False, "message": "لم يتم إرسال الإشعار."}), 400

@app.route('/api/push/status', methods=['GET'])
def api_push_status():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    try:
        tokens = db.execute(
            "SELECT token, device_type, is_active, created_at, last_used FROM push_tokens WHERE user_id=? ORDER BY created_at DESC",
            (user["id"],),
            fetch=True
        ) or []
        
        return jsonify({
            "success": True,
            "registered": len(tokens) > 0,
            "active_count": sum(1 for t in tokens if t["is_active"] == 1),
            "total_count": len(tokens),
            "tokens": [dict(t) for t in tokens]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/auth/link-telegram', methods=['POST'])
def api_auth_link_telegram():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
        
    if user.get("telegram_id"):
        return jsonify({"success": False, "message": "الحساب مرتبط بتيليجرام بالفعل"}), 400
        
    link_code = secrets.token_hex(6).upper()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    
    try:
        db.execute("DELETE FROM telegram_link_codes WHERE user_id = ?", (user["id"],))
        db.execute(
            "INSERT INTO telegram_link_codes (user_id, code, expires_at) VALUES (?, ?, ?)",
            (user["id"], link_code, expires_at)
        )
        return jsonify({
            "success": True,
            "code": link_code,
            "message": "تم إنشاء رمز الربط. افتح البوت وأرسل الرمز."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ: {str(e)}"}), 500

@app.route('/api/auth/check-telegram-link', methods=['GET'])
def api_auth_check_telegram_link():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
        
    return jsonify({
        "success": True,
        "linked": bool(user.get("telegram_id")),
        "telegram_id": user.get("telegram_id")
    }), 200

@app.route('/api/auth/change-password', methods=['POST'])
def api_auth_change_password():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({"success": False, "message": "كلمة المرور القديمة والجديدة مطلوبة"}), 400

    if not user["password_hash"] or not _verify_password(old_password, user["password_hash"], user["salt"]):
        return jsonify({"success": False, "message": "كلمة المرور القديمة غير صحيحة"}), 403

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "كلمة المرور الجديدة قصيرة جداً"}), 400

    pw_hash, salt = _hash_password(new_password)
    db.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (pw_hash, salt, user["id"]))
    return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"}), 200

@app.route('/api/auth/profile', methods=['GET'])
def api_auth_profile():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "phone": user.get("phone", ""),
            "email": user.get("email", ""),
            "balance": user.get("balance", 0),
            "telegram_id": user.get("telegram_id"),
            "is_vip": bool(user.get("is_vip", 0)),
            "created_at": str(user.get("created_at", ""))
        }
    }), 200

@app.route('/api/auth/update-profile', methods=['POST'])
def api_auth_update_profile():
    user, token = _get_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    data = request.get_json(silent=True) or {}
    phone = data.get('phone', user.get("phone", ""))
    email = data.get('email', user.get("email", ""))

    db.execute("UPDATE users SET phone=?, email=? WHERE id=?", (phone, email, user["id"]))
    return jsonify({"success": True, "message": "تم تحديث الملف الشخصي بنجاح"}), 200

# ربط دوال Push بالكائن app للاستخدام في الدوال المساعدة
app._send_push_to_user = _send_push_to_user
app._send_push_to_all_users = _send_push_to_all_users
app._cleanup_old_push_tokens = _cleanup_old_push_tokens
app._send_expo_push_notification = _send_expo_push_notification

# بدء جدولة تنظيف رموز Push
start_push_token_cleanup_scheduler()

# ==============================================================================
# تشغيل التطبيق
# ==============================================================================

if __name__ == "__main__":
    debug_print("=" * 70)
    debug_print("🚀 بدء تشغيل MO STORE v200 PRO")
    debug_print(f"🌐 رابط المتجر: {WEB_URL}")
    debug_print(f"🤖 بوت تيليجرام: @{BOT_USERNAME}")
    debug_print(f"🗄️ قاعدة البيانات: {DB_PATH}")
    debug_print("=" * 70)
    
    # 1. التأكد من إعداد قاعدة البيانات
    try:
        debug_print("🗄️ جاري فحص قاعدة البيانات...")
        db._init_db()
        debug_print("✅ تم فحص قاعدة البيانات بنجاح.", "SUCCESS")
    except Exception as e:
        debug_print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}", "ERROR")
        traceback.print_exc()

    # 2. تنظيف أي ويبهوك معلق
    try:
        debug_print("🤖 التحقق من Webhook...")
        bot.remove_webhook()
        debug_print("✅ تم تنظيف الويبهوك.", "SUCCESS")
    except Exception as e:
        debug_print(f"تعذر إزالة الويبهوك (تأكد من ضبط BOT_TOKEN في متغيرات البيئة): {e}", "WARN")

    # 3. بدء خادم الويب (Flask) في خيط منفصل
    def run_flask():
        try:
            debug_print("🌐 بدء تشغيل خادم الويب Flask...")
            app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True, use_reloader=False)
        except Exception as e:
            debug_print(f"❌ خطأ في خادم الويب Flask: {e}", "ERROR")
            traceback.print_exc()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # إيقاف قصير للتأكد من بدء Flask
    time.sleep(3)
    
    # 4. تشغيل بوت تيليجرام مع حماية ضد الانهيار (لمنع الخروج بكود 0)
    debug_print("🤖 بدء تشغيل بوت تيليجرام (Polling)...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            debug_print(f"❌ خطأ في تشغيل البوت: {e}", "ERROR")
            traceback.print_exc()
            debug_print("🔄 إعادة محاولة الاتصال بعد 5 ثواني...", "WARN")
            time.sleep(5)
