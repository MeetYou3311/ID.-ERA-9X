#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ID. ERA 9X软件升级分享 — 文案分享站
====================================
设计要点：
  - 访客免登录：直接打开网站，浏览 / 搜索 / 复制文案
  - 复制即清除：点击复制 -> 弹窗确认 -> 复制成功则文案从列表移除（防止重复领取）
  - 文案不足提示：剩余数量低于阈值时，前台显示告警横幅
  - 仅管理员可导入：独立的管理员登录入口，用于批量/单条导入文案、调节阈值、查看统计
技术栈：Flask + SQLite（零额外服务依赖，开箱即用）
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, g, request, session, redirect, url_for,
    render_template, flash, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "copybank.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-9x")
SITE_NAME = "ID. ERA 9X软件升级分享"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ------------------------- 数据库层 -------------------------
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def init_db(seed=True):
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS copy (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            category   TEXT NOT NULL DEFAULT '未分类',
            content    TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'taken'
            created_at TEXT NOT NULL,
            taken_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    if seed:
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('low_stock_threshold', '10')"
        )
    db.commit()
    db.close()


def get_setting(key, default=None):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    db.commit()


# ------------------------- 鉴权辅助 -------------------------
def admin_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ------------------------- CSRF 防护 -------------------------
@app.context_processor
def inject_csrf():
    if "csrf_token" not in session:
        import secrets
        session["csrf_token"] = secrets.token_hex(16)
    return {"csrf_token": session["csrf_token"], "site_name": SITE_NAME}


def validate_csrf():
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not token or not session.get("csrf_token") or token != session["csrf_token"]:
        abort(400, "CSRF 校验失败")


# ------------------------- 前台（访客免登录） -------------------------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    db = get_db()

    cats = [r["category"] for r in db.execute(
        "SELECT DISTINCT category FROM copy WHERE status='active' ORDER BY category"
    ).fetchall()]

    sql = "SELECT * FROM copy WHERE status='active'"
    params = []
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id DESC"
    items = db.execute(sql, params).fetchall()

    total_active = db.execute(
        "SELECT COUNT(*) AS c FROM copy WHERE status='active'"
    ).fetchone()["c"]
    threshold = int(get_setting("low_stock_threshold", 10) or 10)
    low_stock = total_active <= threshold

    return render_template(
        "browse.html",
        items=items,
        categories=cats,
        q=q,
        category=category,
        total_active=total_active,
        threshold=threshold,
        low_stock=low_stock,
    )


@app.route("/claim/<int:item_id>", methods=["POST"])
def claim(item_id):
    validate_csrf()
    db = get_db()
    row = db.execute(
        "SELECT id, content, status FROM copy WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return jsonify(ok=False, msg="文案不存在"), 404
    if row["status"] != "active":
        return jsonify(ok=False, msg="该文案已被领取"), 409
    now = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "UPDATE copy SET status='taken', taken_at=? WHERE id=?",
        (now, item_id),
    )
    db.commit()
    return jsonify(ok=True, content=row["content"])


# ------------------------- 管理员登录 -------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            session["admin_user"] = username
            flash("管理员登录成功", "success")
            return redirect(url_for("admin_dashboard"))
        flash("管理员账号或密码错误", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin_login"))


# ------------------------- 管理员后台 -------------------------
@app.route("/admin")
@admin_login_required
def admin_dashboard():
    db = get_db()
    stats = db.execute(
        "SELECT "
        "SUM(status='active') AS active, "
        "SUM(status='taken')  AS taken, "
        "COUNT(*)             AS total "
        "FROM copy"
    ).fetchone()
    active = db.execute(
        "SELECT * FROM copy WHERE status='active' ORDER BY id DESC"
    ).fetchall()
    taken = db.execute(
        "SELECT * FROM copy WHERE status='taken' ORDER BY taken_at DESC LIMIT 200"
    ).fetchall()
    cats = [r["category"] for r in db.execute(
        "SELECT DISTINCT category FROM copy ORDER BY category"
    ).fetchall()]
    threshold = int(get_setting("low_stock_threshold", 10) or 10)
    return render_template(
        "admin.html",
        stats=stats,
        active=active,
        taken=taken,
        categories=cats,
        threshold=threshold,
    )


def _parse_batch(raw):
    """把批量文本解析为 (title, content) 列表。
    支持格式：每行一条；可用 Tab 或 '||' 分隔 标题与内容；否则整行作内容、标题取前 20 字。"""
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            title, _, content = line.partition("\t")
        elif "||" in line:
            title, _, content = line.partition("||")
        else:
            title, content = "", line
        title, content = title.strip(), content.strip()
        if not content:
            continue
        if not title:
            title = content[:20]
        items.append((title, content))
    return items


@app.route("/admin/import", methods=["POST"])
@admin_login_required
def admin_import():
    validate_csrf()
    mode = request.form.get("mode", "single")
    category = (request.form.get("category") or "").strip() or "未分类"
    now = datetime.now().isoformat(timespec="seconds")
    db = get_db()
    inserted = 0

    if mode == "batch":
        raw = request.form.get("batch", "")
        f = request.files.get("file")
        if f and f.filename:
            raw = (f.read() or b"").decode("utf-8", errors="ignore")
        for title, content in _parse_batch(raw):
            db.execute(
                "INSERT INTO copy (title, category, content, status, created_at, taken_at) "
                "VALUES (?, ?, ?, 'active', ?, NULL)",
                (title, category, content, now),
            )
            inserted += 1
    else:
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("内容不能为空", "danger")
            return redirect(url_for("admin_dashboard"))
        if not title:
            title = content[:20]
        db.execute(
            "INSERT INTO copy (title, category, content, status, created_at, taken_at) "
            "VALUES (?, ?, ?, 'active', ?, NULL)",
            (title, category, content, now),
        )
        inserted += 1

    db.commit()
    flash(f"成功导入 {inserted} 条文案", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/setting", methods=["POST"])
@admin_login_required
def admin_setting():
    validate_csrf()
    try:
        threshold = int(request.form.get("threshold", 10))
    except ValueError:
        threshold = 10
    if threshold < 0:
        threshold = 0
    set_setting("low_stock_threshold", threshold)
    flash("不足阈值已更新", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<int:item_id>", methods=["POST"])
@admin_login_required
def admin_delete(item_id):
    validate_csrf()
    db = get_db()
    db.execute("DELETE FROM copy WHERE id = ?", (item_id,))
    db.commit()
    flash("文案已删除", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/restore/<int:item_id>", methods=["POST"])
@admin_login_required
def admin_restore(item_id):
    validate_csrf()
    db = get_db()
    db.execute(
        "UPDATE copy SET status='active', taken_at=NULL WHERE id = ?", (item_id,)
    )
    db.commit()
    flash("文案已恢复为可领取", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/change-password", methods=["POST"])
@admin_login_required
def admin_change_password():
    validate_csrf()
    global ADMIN_PASSWORD
    new_pwd = request.form.get("new_password", "")
    if len(new_pwd) < 6:
        flash("新密码至少 6 位", "danger")
        return redirect(url_for("admin_dashboard"))
    ADMIN_PASSWORD = new_pwd
    flash("管理员密码已更新（重启后生效；建议用环境变量 ADMIN_PASSWORD 固化）", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(400)
def bad_request(e):
    return jsonify(ok=False, msg=str(e.description)), 400


if __name__ == "__main__":
    init_db(seed=True)
    print("✅ 文案分享站已启动")
    print(f"   站点名称：{SITE_NAME}")
    print("   前台地址： http://127.0.0.1:5000")
    print("   管理入口： http://127.0.0.1:5000/admin/login")
    print(f"   管理员账号：{ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug)
