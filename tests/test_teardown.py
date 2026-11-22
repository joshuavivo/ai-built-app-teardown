import hashlib
import io
import json
import secrets
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import after
import before
import exploits
from web import Client


class EveryFindingIsRealAndClosed(unittest.TestCase):
    """The proof: each attack works on the before app and fails on the after app."""

    def test_each_attack(self):
        for check in exploits.FINDINGS:
            with self.subTest(finding=check.__name__):
                vulnerable = before.make_app()
                fixed = after.make_app()
                try:
                    self.assertTrue(check(vulnerable), "attack should work on BEFORE")
                    self.assertFalse(check(fixed), "attack should fail on AFTER")
                finally:
                    vulnerable.close()
                    fixed.close()


class TheFixedAppStillWorks(unittest.TestCase):
    """A fix that breaks the app for real customers is not a fix."""

    @classmethod
    def setUpClass(cls):
        # make_app() returns a callable (the WSGI app); staticmethod keeps it from
        # being bound as a method when accessed via self/cls.
        cls.app = staticmethod(after.make_app())

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def customer(self):
        c = Client(self.app)
        self.assertEqual(c.login("alex@example.com", "alex-pass-123").status, 200)
        return c

    def test_customer_sees_their_own_booking(self):
        r = self.customer().get("/api/bookings/1")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json()["dog"], "Biscuit")

    def test_someone_elses_booking_looks_absent_not_forbidden(self):
        self.assertEqual(self.customer().get("/api/bookings/2").status, 404)

    def test_search_finds_own_dog_and_treats_wildcards_as_text(self):
        c = self.customer()
        self.assertEqual([b["dog"] for b in c.get("/api/search?q=bisc").json()], ["Biscuit"])
        self.assertEqual(c.get("/api/search?q=" + quote("%")).json(), [])

    def test_checkout_charges_the_listed_price(self):
        r = self.customer().post("/api/checkout", {"service": "full-groom", "amount": 1})
        self.assertEqual(r.json()["charged"], 8500)

    def test_unknown_service_is_refused(self):
        self.assertEqual(self.customer().post("/api/checkout", {"service": "free"}).status, 400)

    def test_owner_can_export(self):
        c = Client(self.app)
        c.login("owner@pawprint.example", "groomer-owner-pass")
        r = c.get("/admin/export")
        self.assertEqual(r.status, 200)
        self.assertIn("555-0142", r.text)

    def test_session_cookie_is_random_and_flagged(self):
        c = Client(self.app)
        r = c.login("alex@example.com", "alex-pass-123")
        cookie = dict(r.headers)["Set-Cookie"]
        for flag in ("HttpOnly", "Secure", "SameSite=Lax"):
            self.assertIn(flag, cookie)
        self.assertGreater(len(c.cookies["session"]), 30)

    def test_lockout_says_when_to_retry_and_right_password_works_before_it(self):
        app = after.make_app()
        self.addCleanup(app.close)
        c = Client(app)
        for _ in range(4):
            self.assertEqual(c.login("sam@example.com", "nope").status, 401)
        self.assertEqual(c.login("sam@example.com", "sam-pass-456").status, 200)
        for _ in range(5):
            c.login("sam@example.com", "nope")
        r = c.login("sam@example.com", "sam-pass-456")
        self.assertEqual(r.status, 429)
        self.assertIn("15 minutes", r.text)

    def test_server_error_gives_a_reference_not_internals(self):
        app = after.make_app()  # break the database to force a real crash
        self.addCleanup(app.close)
        app.db.execute("drop table bookings")
        c2 = Client(app)
        c2.login("alex@example.com", "alex-pass-123")
        r = c2.get("/api/bookings/1")
        self.assertEqual(r.status, 500)
        self.assertNotIn("Traceback", r.text)
        self.assertIn("ref", r.json())

    def test_logout_ends_the_session_on_the_server(self):
        app = after.make_app()
        self.addCleanup(app.close)
        c = Client(app)
        c.login("alex@example.com", "alex-pass-123")
        stolen = dict(c.cookies)  # what an attacker who copied the cookie would hold
        r = c.post("/api/logout")
        self.assertEqual(r.status, 200)
        self.assertIn("Max-Age=0", dict(r.headers)["Set-Cookie"])
        thief = Client(app)
        thief.cookies.update(stolen)
        self.assertEqual(thief.get("/api/me").status, 401)  # the token is dead, not just forgotten by the browser

    def test_a_session_expires_after_twelve_hours(self):
        app = after.make_app()
        self.addCleanup(app.close)
        c = Client(app)
        start = after.time.monotonic()
        with mock.patch.object(after.time, "monotonic", return_value=start):
            c.login("alex@example.com", "alex-pass-123")
        with mock.patch.object(after.time, "monotonic", return_value=start + after.SESSION_SECONDS - 1):
            self.assertEqual(c.get("/api/me").status, 200)
        with mock.patch.object(after.time, "monotonic", return_value=start + after.SESSION_SECONDS + 1):
            self.assertEqual(c.get("/api/me").status, 401)

    def test_a_json_body_that_is_not_an_object_is_a_bad_request(self):
        # Valid JSON that isn't an object (a list, a number) used to reach body.get() and crash
        # into a 500. It is the client's mistake, so it gets a 400 on both routes that read JSON.
        app = after.make_app()
        self.addCleanup(app.close)
        c = Client(app)
        for raw in (b"[1]", b"42", b'"x"'):
            self.assertEqual(c.post("/api/login", raw=raw).status, 400)
        c.login("alex@example.com", "alex-pass-123")
        self.assertEqual(c.post("/api/checkout", raw=b"[1]").status, 400)
        self.assertEqual(app.errors, [])

    def test_bad_client_input_is_a_400_not_a_server_error(self):
        # Each of these used to crash after.py into a 500 (and a stored traceback), most of
        # them without logging in.
        app = after.make_app()
        self.addCleanup(app.close)

        def raw_call(body, content_length=None):
            seen = {}
            environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/login", "QUERY_STRING": "",
                       "CONTENT_LENGTH": content_length if content_length is not None else str(len(body)),
                       "wsgi.input": io.BytesIO(body), "HTTP_COOKIE": ""}
            app(environ, lambda status, headers: seen.setdefault("status", int(status.split()[0])))
            return seen["status"]

        surrogate = json.dumps({"email": "sam@example.com", "password": "\ud800"}).encode()
        bad_email = json.dumps({"email": "\ud800@example.com", "password": "x"}).encode()
        deep = b"[" * 200_000 + b"]" * 200_000
        self.assertEqual(raw_call(surrogate), 400)
        self.assertEqual(raw_call(bad_email), 400)
        self.assertEqual(raw_call(b"{}", content_length="abc"), 400)
        self.assertEqual(raw_call(deep), 400)
        c = Client(app)
        c.login("alex@example.com", "alex-pass-123")
        self.assertEqual(c.post("/api/checkout", {"service": ["bath"]}).status, 400)
        self.assertEqual(c.post("/api/checkout", raw=json.dumps({"service": "bath", "dog": "\ud800"}).encode()).status, 400)
        self.assertEqual(app.errors, [])

    def test_only_the_most_recent_errors_are_kept(self):
        app = after.make_app()
        self.addCleanup(app.close)
        app.db.execute("drop table bookings")
        c = Client(app)
        c.login("alex@example.com", "alex-pass-123")
        with mock.patch.object(after, "MAX_KEPT_ERRORS", 2), self.assertLogs("pawprint", level="ERROR"):
            refs = [c.get("/api/bookings/1").json()["ref"] for _ in range(3)]
        self.assertEqual([ref for ref, _ in app.errors], refs[1:])

    def test_the_detail_is_kept_on_the_server_under_the_reference(self):
        # REPORT.md F9: "The detail is kept on the server under that number." Check it is:
        # the full traceback is stored and logged under the ref the person was shown.
        app = after.make_app()
        self.addCleanup(app.close)
        app.db.execute("drop table bookings")
        c = Client(app)
        c.login("alex@example.com", "alex-pass-123")
        with self.assertLogs("pawprint", level="ERROR") as logged:
            r = c.get("/api/bookings/1")
        ref = r.json()["ref"]
        detail = dict(app.errors)[ref]
        self.assertIn("Traceback", detail)
        self.assertIn("no such table: bookings", detail)
        self.assertIn(ref, logged.output[0])


def pbkdf2(password, iterations, salt):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


class TheF8CheckRejectsWeakStorage(unittest.TestCase):
    """The F8 check has to catch weak storage of every kind, not only MD5. Each test swaps a
    weak scheme into an otherwise fixed app; the check must say the attack works."""

    def attack_works_when_stored_with(self, hasher):
        app = after.make_app()
        self.addCleanup(app.close)
        app.hash_password = hasher
        app.db.execute("update users set pw = ? where email = ?",
                       (hasher("sam-pass-456"), "sam@example.com"))
        return exploits.f8_offline_cracking(app)

    def test_plaintext_is_not_a_fix(self):
        self.assertTrue(self.attack_works_when_stored_with(lambda pw: pw))

    def test_too_few_iterations_is_not_a_fix(self):
        self.assertTrue(self.attack_works_when_stored_with(
            lambda pw: pbkdf2(pw, 1_000, secrets.token_bytes(16))))

    def test_a_shared_salt_is_not_a_fix(self):
        self.assertTrue(self.attack_works_when_stored_with(
            lambda pw: pbkdf2(pw, 600_000, b"same-for-all-pws")))


if __name__ == "__main__":
    unittest.main()
