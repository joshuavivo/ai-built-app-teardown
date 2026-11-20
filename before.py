"""Pawprint Booking, BEFORE the audit.

A booking app for a fictional dog groomer, written the way a fast first version often comes out
of an AI coding tool: it works, every screen loads, and the holes are in the parts nobody clicks.
Each flaw is deliberate and tagged with its finding number from REPORT.md. Do not deploy this.
"""
import hashlib
import json
import sqlite3
import traceback

import seed
from web import Request, reply, serve


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()  # F8: fast, unsalted


def make_app():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(seed.SCHEMA)
    for email, pw, name, phone, admin in seed.USERS:
        db.execute("insert into users(email, pw, name, phone, is_admin) values (?,?,?,?,?)",
                   (email, hash_password(pw), name, phone, admin))  # F8
    for uid, service, dog, notes in seed.BOOKINGS:
        db.execute("insert into bookings(user_id, service, dog, notes, amount, paid) values (?,?,?,?,?,1)",
                   (uid, service, dog, notes, seed.SERVICES[service]))

    def current_user(req):
        uid = req.cookies.get("uid")  # F2: the session cookie is just the user's id
        if not uid:
            return None
        return db.execute("select * from users where id = ?", (uid,)).fetchone()

    def route(req, sr):
        m, p = req.method, req.path

        if m == "GET" and p == "/config.js":  # F1: the server secret ships to every browser
            cfg = {"paymentsKey": seed.PAYMENTS_SECRET, "apiBase": "/api"}
            return reply(sr, 200, f"window.CONFIG = {json.dumps(cfg)};", "application/javascript")

        if m == "POST" and p == "/api/login":  # F7: no limit on attempts
            body = req.json()
            row = db.execute("select * from users where email = ?", (body.get("email"),)).fetchone()
            if row and row["pw"] == hash_password(str(body.get("password"))):
                return reply(sr, 200, {"ok": True}, headers=[("Set-Cookie", f"uid={row['id']}; Path=/")])
            return reply(sr, 401, {"error": "Wrong email or password"})

        if p == "/admin/export":  # F6: "nobody knows the URL" is the only lock
            rows = db.execute("select name, email, phone from users").fetchall()
            csv = "name,email,phone\n" + "\n".join(",".join(r) for r in rows)
            return reply(sr, 200, csv, "text/csv")

        user = current_user(req)
        if not user:
            return reply(sr, 401, {"error": "Log in first"})

        if m == "GET" and p == "/api/me":
            return reply(sr, 200, {"email": user["email"], "name": user["name"]})

        if m == "GET" and p.startswith("/api/bookings/"):  # F3: any logged-in user, any booking
            row = db.execute("select * from bookings where id = ?", (p.rsplit("/", 1)[1],)).fetchone()
            return reply(sr, 200, dict(row)) if row else reply(sr, 404, {"error": "Not found"})

        if m == "GET" and p == "/api/search":  # F4: user text pasted into SQL
            q = req.query.get("q", "")
            sql = (f"select id, dog, service, notes from bookings "
                   f"where user_id = {user['id']} and dog like '%{q}%'")
            return reply(sr, 200, [dict(r) for r in db.execute(sql).fetchall()])

        if m == "POST" and p == "/api/checkout":  # F5: the browser says what to charge
            body = req.json()
            amount = int(body["amount"])
            db.execute("insert into bookings(user_id, service, dog, notes, amount, paid) values (?,?,?,?,?,1)",
                       (user["id"], body["service"], body.get("dog", ""), body.get("notes", ""), amount))
            return reply(sr, 200, {"charged": amount})

        return reply(sr, 404, {"error": "Not found"})

    def app(environ, start_response):
        try:
            return route(Request(environ), start_response)
        except Exception:  # F9: the full stack trace goes back to whoever sent the request
            return reply(start_response, 500, {"error": traceback.format_exc()})

    app.db = db  # test hook: lets the offline-cracking check read stored hashes
    app.hash_password = hash_password  # test hook: how a new account's password would be stored
    app.close = db.close  # callers close the app when done so the connection isn't leaked
    return app


if __name__ == "__main__":
    serve(make_app())
