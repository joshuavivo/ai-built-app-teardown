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
- **Bad JSON shape gets a 400.** A body that is valid JSON but not an object (`[1]`) crashed login
  and checkout into a 500. Both now answer 400.

### Changed
- README Limits names the remaining gaps (CSV formula injection in the export; a failed-login
  counter and session store that grow without limit); REPORT.md notes that F8's word list contains the real password.
- README opens with what the holes would cost a business.
