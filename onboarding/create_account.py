#!/usr/bin/env python3
"""Khan Academy onboarding script (Nucleos take-home, requirement 1-2).

Creates ONE free learner account (email + password, registered as an adult),
then reports the outcome honestly:
  - "created: PROVEN" only when a signed-in indicator is actually present,
  - the verbatim page error when sign-up fails,
  - an explicit abort (never a guess) when a bot check blocks the flow.

Credentials live only in extension/config.json (gitignored). They are never
printed, committed, or logged. One account total: the script refuses to run
again while a config.json already exists, unless the previous attempt failed
(--retry).

Usage:
    python create_account.py --email you@example.com --password '...' [--retry]

Requires: pip install playwright && playwright install chromium
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

SIGNUP_URL = "https://www.khanacademy.org/signup"
CONFIG_OUT = Path(__file__).resolve().parent.parent / "extension" / "config.json"

# An adult learner by a wide margin: the brief requires an adult registration.
ADULT_BIRTHDATE = "1990-06-15"

# Signed-in proof: elements that only exist in an authenticated session.
# Multiple candidates because selectors drift; the report names which one fired.
SIGNED_IN_SELECTORS = [
    '[data-test-id="user-avatar"]',
    '[aria-label*="profile" i]',
    'a[href*="/profile"]',
]

BOT_CHECK_HINTS = ("captcha", "recaptcha", "are you a human", "puzzle")


def adult_age_ok(birthdate: str, today: date = None) -> bool:
    """True when the birthdate makes the registrant at least 18 years old."""
    try:
        b = date.fromisoformat(birthdate)
    except ValueError:
        return False
    today = today or date.today()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day)) >= 18


def decide_run(config_exists: bool, retry: bool) -> str:
    """One-account rule as a pure decision: 'proceed', or a refusal reason."""
    if config_exists and not retry:
        return ("refuse: config.json already exists, an account was created "
                "earlier; re-running would create a second account")
    if config_exists and retry:
        return "delete-stale-config: previous attempt failed, config discarded"
    return "proceed"


def format_report(created: bool, proven: bool, evidence: str, error: str) -> str:
    """Honest report formatting: PROVEN only with evidence, UNKNOWN over guessing."""
    if proven and evidence:
        return f"RESULT: account created: PROVEN\n  evidence: {evidence}"
    if error:
        return f"RESULT: account NOT created\n  page error (verbatim): {error}"
    return ("RESULT: UNKNOWN - neither a signed-in indicator nor an error "
            "appeared. Reporting UNKNOWN rather than guessing.")


def fill_react_input(page, selector: str, value: str):
    """Set a value in a React-controlled input and make React notice.

    Assigning .value directly does not fire the events React listens to, so
    the form would submit empty. This sets the value through the native
    setter, then dispatches the input event React's synthetic system rides on.
    """
    page.eval_on_selector(
        selector,
        """(el, value) => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, value);
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }""",
        value,
    )


def find_first(page, selectors, timeout_ms=8000):
    """Return the first selector that becomes visible, else None."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                return sel
        page.wait_for_timeout(250)
    return None


def page_error_text(page) -> str:
    """Best-effort verbatim capture of any visible form error."""
    for sel in ('[role="alert"]', ".error", '[class*="error" i]'):
        loc = page.locator(sel)
        for i in range(min(loc.count(), 5)):
            candidate = loc.nth(i)
            if not candidate.is_visible():
                continue
            t = candidate.inner_text().strip()
            if t:
                return t
    return "(no visible error text)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--birthdate", default=ADULT_BIRTHDATE)
    ap.add_argument("--retry", action="store_true",
                    help="allow a re-run when the previous attempt failed")
    a = ap.parse_args()

    if not adult_age_ok(a.birthdate):
        sys.exit("refusing: birthdate does not register an adult learner")

    # one-account rule: a config that already exists means an account was made
    if CONFIG_OUT.exists() and not a.retry:
        sys.exit(
            "refusing: extension/config.json already exists, an account was "
            "created earlier. Re-running would create a second account, which "
            "the brief forbids. Use --retry only if the previous run FAILED "
            "and you deleted the config from that failed run.")
    if CONFIG_OUT.exists() and a.retry:
        CONFIG_OUT.unlink()

    report = {"created": False, "proven": False, "evidence": "", "error": ""}
    from playwright.sync_api import sync_playwright  # imported at run time:
    # the pure decisions above stay importable without the browser stack
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=120)
        page = browser.new_page()
        page.goto(SIGNUP_URL)
        page.wait_for_load_state("domcontentloaded")

        # Sign-up walks through a few screens (learner type, birthday, form).
        # We answer what is on screen rather than assuming a fixed step count.
        steps_done = 0
        while steps_done < 8:
            html = page.content().lower()
            if any(h in html for h in BOT_CHECK_HINTS):
                report["error"] = ("bot check encountered: refusing to bypass "
                                   "(brief rule). Complete sign-up manually "
                                   "in the opened browser, then re-run with "
                                   "--retry only if nothing was created.")
                break

            # birthday screen
            if page.locator("input[type='date']").count():
                fill_react_input(page, "input[type='date']", a.birthdate)
                page.keyboard.press("Enter")
                page.wait_for_timeout(800)
                steps_done += 1
                continue

            # account form
            email_input = page.locator(
                "input[type='email'], input[name*='email' i]").first
            if email_input.count() and email_input.is_editable():
                for sel, val in (
                    ("input[name*='name' i], input[placeholder*='name' i]", "Tod Learner"),
                    ("input[type='email'], input[name*='email' i]", a.email),
                    ("input[type='password'], input[name*='password' i]", a.password),
                ):
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_editable():
                        fill_react_input(page, sel, val)
                page.get_by_role("button", name=re.compile("sign ?up", re.I)).first.click()
                page.wait_for_timeout(1500)
                steps_done += 1
                continue

            # proof: a signed-in indicator on a non-signup page
            proof = find_first(page, SIGNED_IN_SELECTORS, timeout_ms=6000)
            if proof and "/signup" not in page.url:
                report.update(created=True, proven=True,
                              evidence=f"signed-in indicator visible: {proof}")
                break

            # failure: still on a form with an error showing
            err = page_error_text(page)
            if err != "(no visible error text)" and "/signup" in page.url:
                report["error"] = err
                break

            page.wait_for_timeout(700)
            steps_done += 1

        browser.close()

    # Honest report. PROVEN only with the evidence selector on record.
    print(format_report(report["created"], report["proven"],
                        report["evidence"], report["error"]))
    if report["proven"]:
        CONFIG_OUT.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_OUT.write_text(json.dumps(
            {"username": a.email, "password": a.password}, indent=2) + "\n")
        print(f"  credentials written to {CONFIG_OUT} (gitignored; never committed)")
    elif report["error"]:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
