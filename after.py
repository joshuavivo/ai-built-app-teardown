"""Pawprint Booking, AFTER the audit.

Same app, same routes, same data. Each change is tagged with the finding it closes (REPORT.md).
"""
import hashlib
import hmac
import json
import logging
import secrets
import sqlite3
import time
import traceback
import uuid

import seed
from web import Request, reply, serve

log = logging.getLogger("pawprint.after")

ITERATIONS = 600_000      # F8: PBKDF2-SHA256, OWASP's current figure
MAX_FAILURES = 5          # F7: failed logins per account ...
WINDOW_SECONDS = 15 * 60  # ... inside this window before it locks


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password, stored):
    _, iterations, salt, digest = stored.split("$")
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(test.hex(), digest)


def make_app():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(seed.SCHEMA)
    for email, pw, name, phone, admin in seed.USERS:
        db.execute("insert into users(email, pw, name, phone, is_admin) values (?,?,?,?,?)",
                   (email, hash_password(pw), name, phone, admin))
    for uid, service, dog, notes in seed.BOOKINGS:
        db.execute("insert into bookings(user_id, service, dog, notes, amount, paid) values (?,?,?,?,?,1)",
                   (uid, service, dog, notes, seed.SERVICES[service]))

    sessions = {}  # F2: random token -> user id, kept on the server
    failures = {}  # F7: email -> timestamps of recent failed logins
    errors = []    # F9: (ref, full traceback) for every server error; also written to the log

    def current_user(req):
        uid = sessions.get(req.cookies.get("session", ""))
        return db.execute("select * from users where id = ?", (uid,)).fetchone() if uid else None

    def route(req, sr):
        m, p = req.method, req.path

        if m == "GET" and p == "/config.js":  # F1: only the key that is meant to be public
            cfg = {"paymentsKey": seed.PUBLISHABLE_KEY, "apiBase": "/api"}
            return reply(sr, 200, f"window.CONFIG = {json.dumps(cfg)};", "application/javascript")

        if m == "POST" and p == "/api/login":
            try:
                body = req.json()
            except ValueError:
                return reply(sr, 400, {"error": "Bad request"})
            if not isinstance(body, dict):  # valid JSON but not an object, e.g. [1]
                return reply(sr, 400, {"error": "Bad request"})
            email = str(body.get("email", "")).lower()
            now = time.monotonic()
            recent = [t for t in failures.get(email, []) if now - t < WINDOW_SECONDS]
            failures[email] = recent
            if len(recent) >= MAX_FAILURES:  # F7: checked before the password is even looked at
                return reply(sr, 429, {"error": "Too many attempts. Try again in 15 minutes."})
            row = db.execute("select * from users where email = ?", (email,)).fetchone()
            if row and check_password(str(body.get("password", "")), row["pw"]):
                failures.pop(email, None)
                token = secrets.token_urlsafe(32)
                sessions[token] = row["id"]
                cookie = f"session={token}; Path=/; HttpOnly; Secure; SameSite=Lax"
                return reply(sr, 200, {"ok": True}, headers=[("Set-Cookie", cookie)])
            recent.append(now)
            return reply(sr, 401, {"error": "Wrong email or password"})

        user = current_user(req)
        if not user:
            return reply(sr, 401, {"error": "Log in first"})

        if p == "/admin/export":  # F6: the server checks who is asking
            if not user["is_admin"]:
                return reply(sr, 403, {"error": "Not allowed"})
            rows = db.execute("select name, email, phone from users").fetchall()
            csv = "name,email,phone\n" + "\n".join(",".join(r) for r in rows)
            return reply(sr, 200, csv, "text/csv")

        if m == "GET" and p == "/api/me":
            return reply(sr, 200, {"email": user["email"], "name": user["name"]})

        if m == "GET" and p.startswith("/api/bookings/"):  # F3: only your own; others look absent
            row = db.execute("select * from bookings where id = ? and user_id = ?",
                             (p.rsplit("/", 1)[1], user["id"])).fetchone()
            return reply(sr, 200, dict(row)) if row else reply(sr, 404, {"error": "Not found"})

        if m == "GET" and p == "/api/search":  # F4: the text is a value, never part of the SQL
            q = req.query.get("q", "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            rows = db.execute("select id, dog, service, notes from bookings "
                              "where user_id = ? and dog like ? escape '\\'",
                              (user["id"], f"%{q}%")).fetchall()
            return reply(sr, 200, [dict(r) for r in rows])

        if m == "POST" and p == "/api/checkout":  # F5: the price comes from the server's list
            try:
                body = req.json()
            except ValueError:
                return reply(sr, 400, {"error": "Bad request"})
            if not isinstance(body, dict):  # valid JSON but not an object, e.g. [1]
                return reply(sr, 400, {"error": "Bad request"})
            service = body.get("service")
            if service not in seed.SERVICES:
                return reply(sr, 400, {"error": "Unknown service"})
            amount = seed.SERVICES[service]
            db.execute("insert into bookings(user_id, service, dog, notes, amount, paid) values (?,?,?,?,?,1)",
                       (user["id"], service, str(body.get("dog", "")), str(body.get("notes", "")), amount))
            return reply(sr, 200, {"charged": amount})

        return reply(sr, 404, {"error": "Not found"})

    def app(environ, start_response):
        try:
            return route(Request(environ), start_response)
        except Exception as exc:  # F9: a reference number out, the detail stays in
            ref = uuid.uuid4().hex[:8]
            errors.append((ref, traceback.format_exc()))
            log.error("server error ref=%s: %r", ref, exc, exc_info=True)
            return reply(start_response, 500, {"error": "Something went wrong", "ref": ref})

    app.db = db  # test hooks, as in before.py
    app.errors = errors
    app.hash_password = hash_password
    app.close = db.close  # callers close the app when done so the connection isn't leaked
    return app


if __name__ == "__main__":
    serve(make_app(), port=8001)
