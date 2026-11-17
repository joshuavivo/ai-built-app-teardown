import sys
import unittest
from pathlib import Path
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
                self.assertTrue(check(before.make_app()), "attack should work on BEFORE")
                self.assertFalse(check(after.make_app()), "attack should fail on AFTER")


class TheFixedAppStillWorks(unittest.TestCase):
    """A fix that breaks the app for real customers is not a fix."""

    @classmethod
    def setUpClass(cls):
        cls.app = staticmethod(after.make_app())

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
        app.db.execute("drop table bookings")
        c2 = Client(app)
        c2.login("alex@example.com", "alex-pass-123")
        r = c2.get("/api/bookings/1")
        self.assertEqual(r.status, 500)
        self.assertNotIn("Traceback", r.text)
        self.assertIn("ref", r.json())


if __name__ == "__main__":
    unittest.main()
