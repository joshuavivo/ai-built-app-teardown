# Security policy

This repository is a **deliberately vulnerable** sample (`before.py`) next to its
fixed version (`after.py`), built to demonstrate an audit. The vulnerabilities in
`before.py` are intentional and documented in [REPORT.md](REPORT.md) — they are not
bugs to report. There is no deployment; the demo servers bind to `127.0.0.1` only.

## What to report

If you find a security issue in the **fixed** version (`after.py`) that REPORT.md
claims is closed — a finding `F1`–`F9` that is still exploitable after the fix, or
a new issue the teardown missed — I'd like to know:

- Open a **GitHub Security Advisory** on this repository (Security → Report a
  vulnerability), or
- email **security@shadowvivo.com**.

No bounty is offered, but I'll credit you unless you'd rather stay anonymous.

## Not in scope

- Anything in `before.py` — it is vulnerable on purpose.
- The documented limits in the README (no CSRF token where `SameSite=Lax` covers
  it, lockout-by-account only, login timing). Those are called out, not hidden.
- The seed secret `demo-payments-secret-not-real` — it is a fake for the demo.
