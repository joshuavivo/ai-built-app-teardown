# Changelog

Notable changes. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This file starts on 2026-11-21; earlier changes are in the git history and the merged pull requests.

## [Unreleased]

Fixes to the audited ("after") app, found by an independent review.

### Fixed
- **F9: the error detail is now really kept.** REPORT.md says the detail of a server error is kept
  on the server under the reference the person sees. `after.py` stored only a one-line `repr`. It
  now stores and logs the full traceback under that reference.
- **F2: sessions expire and logout ends them.** The session token never expired and there was no
  logout, so a copied cookie stayed valid indefinitely. Tokens now stop working after 12 hours, and
  `POST /api/logout` removes the token on the server and clears the cookie.
- **Bad client input gets a 400, not a server error.** A password or email with a lone
  surrogate, a non-numeric Content-Length, JSON nested 200,000 deep, a list as the checkout
  service, or broken text in the dog's name each crashed `after.py` into a 500, most
  before login. Each now gets a 400. Found by an outside review.
- **F7: a lockout lasts the 15 minutes it promises.** The lock was a rolling window, so
  with five misses spread over 14 minutes a guess got through 61 seconds after the lock,
  which didn't match "stops accepting attempts for 15 minutes". The lock now runs for 15
  minutes from the fifth miss, and the 429 says how many minutes are left. The overall
  rate is about the same either way (5 guesses per 15 minutes); the fix makes the behaviour
  match the wording.
- **The stored error list is bounded** to the newest 1,000 (the log keeps every one), so a
  flood of errors can't fill memory.
- **Bad JSON shape gets a 400.** A body that is valid JSON but not an object (`[1]`) crashed login
  and checkout into a 500. Both now answer 400.

### Changed
- README badges at the top: live test status for `main` and the license.
- README Limits names the remaining gaps (CSV formula injection in the export; a failed-login
  counter and session store that grow without limit); REPORT.md notes that F8's word list contains the real password.
- README opens with what the holes would cost a business.
- F9's "who could do it" now says any visitor, not any customer: `before.py` returns the
  trace from the login route, before anyone has logged in. The README's F2 snippet shows
  the current session code (it still showed the pre-expiry line), and Limits adds that
  logout ends only the current session and that there's no request-size limit.
