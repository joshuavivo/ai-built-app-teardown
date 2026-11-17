"""Fictional seed data shared by both versions. Every name, email and phone number is made up
(555-01xx numbers and example domains are reserved for fiction)."""

# The server-side payment secret. Fake, and deliberately not shaped like any real provider's key.
PAYMENTS_SECRET = "demo-payments-secret-not-real"
PUBLISHABLE_KEY = "demo-publishable-key"

SERVICES = {"bath": 4000, "full-groom": 8500}  # prices in cents

USERS = [  # email, password, name, phone, is_admin
    ("owner@pawprint.example", "groomer-owner-pass", "Riley Park", "555-0100", 1),
    ("alex@example.com", "alex-pass-123", "Alex Moreno", "555-0142", 0),
    ("sam@example.com", "sam-pass-456", "Sam Okafor", "555-0177", 0),
]

BOOKINGS = [  # user id, service, dog, notes
    (2, "bath", "Biscuit", "Side gate code 4412, dog is nervous"),
    (3, "full-groom", "Juniper", "Leave at back door, key under the mat"),
]

SCHEMA = """
create table users(id integer primary key, email text unique, pw text, name text,
                   phone text, is_admin int default 0);
create table bookings(id integer primary key, user_id int, service text, dog text,
                      notes text, amount int, paid int default 0);
"""
