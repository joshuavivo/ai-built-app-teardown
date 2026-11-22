# Teardown report: Pawprint Booking

**The app:** an online booking app for a dog groomer. Customers log in, book a bath or a groom,
pay, and leave notes for the groomer. The owner can download the customer list.

**The app is fictional.** I built it to look the way a fast first version often comes out of an AI coding
tool, and then audited it the way I audit a real one. No client, person or business is behind it.

**How it was tested:** every finding below has a check in `exploits.py` that runs the attack
against the app. Each check works on the before version and fails on the after version, and a
second set of tests confirms the fixed app still works for real customers.

## Summary

Every endpoint worked. A customer could book, pay and log in without noticing anything wrong.
All nine problems sit in the parts a normal customer never touches: what the server trusts, what
it sends back, and what it remembers.

| # | Finding | Who could do it | What they'd get | Severity |
|---|---|---|---|---|
| F1 | Payment secret sent to every browser | Any visitor | Control of the payment account | Critical |
| F2 | Login cookie is just a number | Any visitor | Log in as anyone, including the owner | Critical |
| F3 | Change the number in the URL, see another booking | Any customer | Other customers' gate codes and notes | High |
| F4 | Search box talks straight to the database | Any customer | Every booking in the system | High |
| F5 | Checkout charges whatever the browser says | Any customer | An $85 groom for 1 cent | High |
| F6 | Customer list download has no lock | Any visitor | Every customer's name, email and phone | High |
| F7 | Unlimited password guesses | Any visitor | Into any account with a weak password | Medium |
| F8 | Passwords stored with a fast hash and no salt | Anyone who gets a copy of the database | Most passwords, in minutes | Medium |
| F9 | Errors show the code's internals | Any visitor (no login needed) | A map of the code for the next attack | Low |

## Findings

### F1. Payment secret sent to every browser
**What's wrong.** The page loads a settings file (`/config.js`), and that file contains the
*secret* payment key, the one that can issue charges and refunds. Anyone who opens the browser's
developer tools can copy it.
**Proof.** `f1_secret_in_browser`: load `/config.js` as a stranger and the secret is in it.
**Fix.** The browser gets only the *publishable* key, which is designed to be public. The secret
stays on the server. (For a real app: also rotate the old key, because it has already been seen.)

### F2. The login cookie is just a number
**What's wrong.** After logging in, the app remembers you with a cookie that says `uid=2`.
Change it to `uid=1` and the app thinks you are the owner. No password needed.
**Proof.** `f2_forged_session`: with no login at all, set the cookie to 1 and ask the app who you are.
**Fix.** A long random token that only the server can map back to a person, marked so scripts
on the page can't read it (`HttpOnly`), it only travels over HTTPS (`Secure`), and it isn't sent by
other sites' forms (`SameSite`). The token stops working after 12 hours, and logging out ends it on the server, so a
copied cookie doesn't stay valid forever.

### F3. Change the number in the URL, see another booking
**What's wrong.** `/api/bookings/1` is Alex's booking. `/api/bookings/2` is Sam's, and Alex can
open it too, including "key under the mat". The app checked that you were logged in, not that the
booking was yours.
**Proof.** `f3_read_someone_elses_booking`.
**Fix.** The database lookup now asks for the booking *and* the owner together. Someone else's
booking answers "not found", the same as one that doesn't exist, so nobody can count them either.

### F4. The search box talks straight to the database
**What's wrong.** Whatever you type in search is pasted into the database query. Typing
`' or 1=1 --` turns "my bookings matching this dog" into "every booking".
**Proof.** `f4_sql_injection_in_search`.
**Fix.** The search text goes to the database as a value, never as part of the query. `%` and `_`
are now treated as plain characters, so searching for `%` doesn't match everything.

### F5. Checkout charges whatever the browser says
**What's wrong.** The checkout request includes the price, and the server charges it. Edit the
request and an $85 groom costs 1 cent.
**Proof.** `f5_pick_your_own_price`.
**Fix.** The browser says *which* service. The server looks up the price. Unknown services are refused.

### F6. The customer list download has no lock
**What's wrong.** `/admin/export` downloads every customer's name, email and phone. It isn't
linked anywhere, and that was the only protection. Anyone who guessed or found the address had it.
**Proof.** `f6_open_admin_export`: fetch it as a stranger, then as an ordinary customer.
**Fix.** The server checks that the person asking is logged in *and* is an admin.

### F7. Unlimited password guesses
**What's wrong.** The login form lets anyone try passwords forever. A script tries thousands a minute.
**Proof.** `f7_unlimited_password_guesses`: the right password is the 25th guess and it gets in.
**Fix.** After 5 wrong passwords in 15 minutes, that account stops accepting attempts for 15 minutes
from the fifth miss, and says how long is left. The check happens before the password is even looked at.

### F8. Passwords stored with a fast hash and no salt
**What's wrong.** Passwords are stored as MD5. If the database ever leaks, cracking tools test
billions of MD5 guesses a second, and two people with the same password have the same stored value.
**Proof.** `f8_offline_cracking`: a four-word list cracks Sam's password from the stored value.
The list contains Sam's real password, as real leaked-password lists contain most people's.
The check also counts the attack as working if passwords are stored as plain text, with fewer
than 600,000 PBKDF2 iterations, or identically for two accounts with the same password, so a
weaker fix can't pass.
**Fix.** PBKDF2-SHA256 with 600,000 rounds and a random salt per person. Each guess now costs
real time, and the same password stores differently for each person.

### F9. Errors show the code's internals
**What's wrong.** Send a broken request and the app replies with its full error trace: file
names, line numbers and the code itself.
**Proof.** `f9_stack_trace_leak`.
**Fix.** The person sees "Something went wrong" and a reference number. The detail is kept on the
server under that number.

## What this audit did not cover

This was a code-and-behaviour review of the app itself. It did not cover the hosting setup, the
domain and email settings, third-party packages, the AI tools and keys used to build the app,
backups, or anything about the people who run it. A real audit scopes those in writing before it starts.

Fixing these nine doesn't make the app unbreakable. It closes the nine ways in that I found and
proved, and the tests fail if a later change reopens one of them.
