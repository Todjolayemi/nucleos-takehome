# Nucleos take-home: Khan Academy onboarding + auto sign-in extension

Two pieces: a script that creates one Khan Academy learner account and
reports the outcome honestly, and a Manifest V3 Chrome extension that signs
that account in and reports Khan Academy's own error, word for word, when
the credentials are wrong.

## How to run the onboarding script

```bash
cd onboarding
pip install playwright
playwright install chromium
python create_account.py --email you@example.com --password 'A-Secret-123'
```

The browser opens visibly (no headless): sign-up involves a real flow and
the script refuses to race it. It walks the sign-up screens, registers an
adult learner (birthdate 1990 by default, checked by a pure function with a
boundary test), and then reports one of three outcomes:

- `account created: PROVEN` only when a signed-in indicator element is
  actually visible, and it names the selector that proved it
- `account NOT created` with the page's error text, verbatim
- `UNKNOWN` when neither appeared. UNKNOWN is a real answer here, not a
  failure of the script: reporting a guess would be the failure.

On success it writes the credentials to `extension/config.json` (gitignored)
so the extension uses the account the script created, which is what the
brief asks for. Credentials are never printed, logged, or committed.

The script refuses to run twice while `config.json` exists: one account,
full stop. `--retry` exists only for a failed first attempt and deletes the
stale config first. If a CAPTCHA or bot check appears, it aborts and says
so. It does not try to get past one.

## Extension setup

1. `cd extension`
2. `cp config.example.json config.json` (the example values are wrong on
   purpose, so your first run fails the way the brief wants)
3. Correct `config.json` only after the onboarding script has created the
   account (the script writes this file for you on success)
4. Chrome: `chrome://extensions`, Developer mode on, Load unpacked, select
   the `extension/` folder
5. Open https://www.khanacademy.org/login

First visit: toast shows Khan Academy's own error, quoted exactly, and the
console carries the same line. Fix the config, reload the page: success
toast naming the proof selector.

## Design decisions

| Decision | Why |
|---|---|
| Playwright, headful, slow-mo | the flow is real and involves bot checks; racing it headless is how you get banned and lie about outcomes |
| honesty logic as pure functions | `decide_run`, `format_report`, `pickErrorText`, `isSignInProven`, `outcomeReport` are plain functions over plain data, so the honesty rules themselves are unit-tested. DOM plumbing stays thin and separate. |
| proof = off /login AND an authenticated element | a URL change alone is not proof. A failed login can navigate too. |
| React-aware form fill | assigning `.value` directly does nothing in a React form. The script/extension set the value through the native setter and dispatch the `input` event. |
| one attempt per visit via an in-memory document flag | survives SPA route wobbles within a page, and resets on a new page load. The interpretation ("visit" = one page load in one tab) is explicit. |
| UNKNOWN as a first-class outcome | the brief's core rule is "never report an outcome you can't prove". A timeout with no error and no proof reports UNKNOWN, and the tests pin that behavior. |

## How I know what I know

Account created: a signed-in-only element is visible on a non-signup page
(the report names which selector). Sign-in succeeded: the URL has left
/login and an authenticated-only element (user avatar / profile link)
exists. Wrong credentials: Khan Academy's own error element, captured
verbatim. Anything else: UNKNOWN.

## Permissions

The extension requests **no permissions at all**. Content-script matching
is declared in the manifest and scoped to
`https://www.khanacademy.org/login*` only: it does not exist on any other
page, so there is nothing to justify beyond the match itself. Config is a
bundled file read through `chrome.runtime.getURL`, which needs no
permission. That is the whole permissions story.

## Tests

```bash
python -m unittest discover -s tests   # onboarding decisions (10)
node --test tests/content.test.mjs     # extension honesty rules (12)
```

The tested parts are the honesty rules: what counts as an error, what counts
as proof, the one-account rule, adult-age boundary, UNKNOWN-over-guessing.
DOM selectors are verified live instead; they are the part that can drift,
so they are isolated in the plumbing layer, not the decisions.

## Recording

Add the recording link here before submission. The recording should show, in
under four minutes, the headful onboarding run, the deliberately wrong config
and Khan Academy's exact error toast, then the corrected config and the
proof-based success toast. Do not show the real email or password.

## Known limitations and next steps

- Selectors for KA's form and proof elements can drift; they are collected
  in one place with fallbacks, and the README of any real submission should
  note the date they were verified.
- The signup walker is defensive, not omniscient: an unexpected screen it
  cannot classify leads to UNKNOWN, by design.
- With more time: a recording script for the 4-minute video, and a
  Playwright smoke test that loads the extension in a real Chromium and
  drives the wrong-then-right sequence end to end.

## AI usage

See docs/AI-USAGE.md for the exact account of what was drafted with what,
what was human-reviewed, and what the verification layers caught.
