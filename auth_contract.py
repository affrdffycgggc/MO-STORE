"""
auth_contract.py
نظام المصادقة لتطبيق الهاتف مع دعم إشعارات Push
يتم ربطه بعد إنشاء app و db
"""

import secrets
import uuid
import json
import requests
from datetime import datetime, timedelta
from flask import request, session, jsonify, redirect, url_for, render_template_string

# إعدادات Expo Push
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def register_auth_routes(app, db, _hash_password, _verify_password):
    
    # ==================================================================
    # دوال إشعارات Push (Expo Push)
    # ==================================================================
    
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

    # ==================================================================
    # دوال المصادقة
    # ==================================================================

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
            return row
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
                return user, None

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

    # ربط دوال Push بالكائن app للاستخدام في الملف الرئيسي
    app._send_push_to_user = _send_push_to_user
    app._send_push_to_all_users = _send_push_to_all_users
    app._cleanup_old_push_tokens = _cleanup_old_push_tokens
    app._send_expo_push_notification = _send_expo_push_notification