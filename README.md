# AI-built app teardown

A small booking app for a fictional dog groomer, built the way a fast first version often comes
out of an AI coding tool, then audited and fixed. Every screen works. The nine holes are in the
parts nobody clicks.

I built this to show how I audit an app that went live quickly: find the easy ways in, prove each
one with a test that runs the attack, fix it, and keep the test so it stays fixed.

**Start with [REPORT.md](REPORT.md).** It's the plain-English write-up a business owner would get.

## What's here

| File | What it is |
|---|---|
| `before.py` | The app as first written. Each flaw is tagged `F1`–`F9` |
| `after.py` | The same app, same routes, same data, with each fix tagged |
| `exploits.py` | One attack per finding. Returns `True` if the attack worked |
| `tests/` | Each attack must work on `before` and fail on `after`, and the fixed app must still work for customers |
| `seed.py` | The made-up customers and bookings |
| `web.py` | A few lines of request plumbing and an in-process test client |

## Run it

```bash
python3 -m unittest discover -s tests    # the proof
python3 before.py                        # http://127.0.0.1:8000, local only
python3 after.py                         # http://127.0.0.1:8001
```

## Limits

- The fixes are the standard ones, kept small enough to read. Some would be done differently in
  production: sessions and lockout counters would live in a database or cache rather than memory,
  and the lockout would also count by network address so one person can't lock out many accounts.
- Locking an account after 5 failures also lets a stranger lock out a real customer on purpose.
  A real app weighs that against a delay that grows with each failure, or a CAPTCHA.
- The login answers slightly faster for an email that doesn't exist, which can hint at who has an
  account. Not fixed here.
- There's no CSRF token. `SameSite=Lax` covers the cross-site form case for these routes, but a
  real app with state-changing GET requests or older browsers needs one.

Standard library only, Python 3.9 or later. The tests run in-process; the demo servers listen on 127.0.0.1 only.

Joshua Vivo · [shadowvivo.com](https://shadowvivo.com)
