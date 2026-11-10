/**
 * Nucleos take-home: Khan Academy sign-in content script.
 *
 * Runs only on https://www.khanacademy.org/login* (manifest match).
 * Reads credentials from the bundled config.json (copy config.example.json
 * to config.json and correct the values after the onboarding script runs).
 *
 * Honesty rules, per the brief:
 *  - wrong credentials: show Khan Academy's OWN error, word for word
 *  - correct credentials: report success ONLY on a signed-in proof element
 *  - never report an outcome we cannot prove
 *  - one attempt per visit to the login page
 */

(function () {
  "use strict";

  // ---------- pure decisions (unit-tested in tests/content.test.mjs) ----------
  // The honesty rules live HERE, as plain functions over plain data, so the
  // parts the brief cares about most are testable without a browser.

  /** Which error text is the one Khan Academy chose to show? First
   *  non-empty, non-placeholder ("required" is a field hint, not an error). */
  function pickErrorText(errorTexts) {
    for (const t of errorTexts) {
      const text = (t || "").trim();
      if (text && text.toLowerCase() !== "required") return text;
    }
    return null;
  }

  /** A URL change alone is not proof of sign-in (a failed login can also
   *  navigate). Proof = off the login page AND an authenticated-only
   *  element matched. */
  function isSignInProven(location, matchedSelector) {
    if (!matchedSelector) return false;
    if (location.pathname.includes("/login")) return false;
    return true;
  }

  /** One attempt per visit. */
  function attemptDecision(alreadyAttempted, formPresent, configLoaded) {
    if (alreadyAttempted) return { action: "skip", reason: "already attempted this visit" };
    if (!configLoaded) return { action: "report", reason: "config not loaded" };
    if (!formPresent) return { action: "skip", reason: "login form not present" };
    return { action: "attempt" };
  }

  /** Map an observation to the honest report. UNKNOWN beats a guess. */
  function outcomeReport(observation) {
    if (!observation) {
      return { kind: "unknown",
               message: "No outcome could be proven within 15s: no error shown and no signed-in element found. Reporting UNKNOWN, not guessing." };
    }
    if (observation.err) {
      return { kind: "failed",
               message: `Khan Academy error (verbatim): "${observation.err}"` };
    }
    return { kind: "success",
             message: `Signed in: proven by ${observation.proof}` };
  }

  // ---------- DOM plumbing (verified live, not unit-tested) ----------

  function readLoginForm(doc) {
    const email = doc.querySelector(
      "input[type='email'], input[name*='email' i], input[name*='user' i]");
    const password = doc.querySelector("input[type='password']");
    return (email && password) ? { email, password } : null;
  }

  function readErrorCandidates(doc) {
    const els = doc.querySelectorAll(
      '[role="alert"], [class*="error" i], [data-test-id*="error" i]');
    const texts = [];
    for (const el of els) {
      const style = window.getComputedStyle(el);
      if (el.getClientRects().length && style.display !== "none" &&
          style.visibility !== "hidden") {
        texts.push(el.textContent || "");
      }
    }
    return texts;
  }

  const PROOF_SELECTORS = [
    '[data-test-id="user-avatar"]',
    'a[href*="/profile"]',
    '[aria-label*="profile" i]',
    '[data-test-id="user-dropdown"]',
  ];

  function matchProofSelector(doc) {
    for (const sel of PROOF_SELECTORS) {
      if (doc.querySelector(sel)) return sel;
    }
    return null;
  }

  // Content scripts run once per document. This survives SPA route changes,
  // while a reload starts a fresh visit with a fresh flag.
  let attemptedThisDocument = false;

  // ---------- page interaction (not unit-testable; verified live) ----------

  function setReactValue(el, value) {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function toast(doc, message, ok) {
    const t = doc.createElement("div");
    t.className = "nucleos-toast" + (ok ? " nucleos-ok" : " nucleos-err");
    t.textContent = message;
    doc.body.appendChild(t);
    setTimeout(() => t.remove(), 12000);
  }

  function log(kind, detail) {
    // Structured so the recording shows clean, greppable evidence.
    console.log(`[nucleos] ${kind}: ${detail}`);
  }

  async function loadConfig() {
    const url = chrome.runtime.getURL("config.json");
    const res = await fetch(url);
    if (!res.ok) throw new Error(`config.json missing (copy config.example.json): ${res.status}`);
    return res.json();
  }

  function waitFor(predicate, timeoutMs, onTick) {
    return new Promise((resolve) => {
      const started = Date.now();
      const timer = setInterval(() => {
        const value = predicate();
        if (value !== null && value !== undefined && value !== false) {
          clearInterval(timer);
          resolve(value);
        } else if (Date.now() - started > timeoutMs) {
          clearInterval(timer);
          resolve(null);
        } else if (onTick) {
          onTick();
        }
      }, 300);
    });
  }

  // ---------- main ----------

  async function main() {
    let config = null;
    try {
      config = await loadConfig();
    } catch (e) {
      toast(document, "Config not loaded: " + e.message, false);
      log("error", e.message);
      return;
    }

    const form = await waitFor(() => readLoginForm(document), 8000);
    const gate = attemptDecision(attemptedThisDocument, Boolean(form), Boolean(config));
    if (gate.action !== "attempt") {
      log(gate.action, gate.reason);
      return;
    }

    setReactValue(form.email, String(config.username || ""));
    setReactValue(form.password, String(config.password || ""));

    const submit = Array.from(document.querySelectorAll("button"))
      .find((b) => /log\s?in/i.test(b.textContent || ""));
    if (!submit) {
      log("error", "submit button not found");
      return;
    }

    attemptedThisDocument = true;
    submit.click();
    log("attempt", "submitted configured credentials");

    const observation = await waitFor(() => {
      const err = pickErrorText(readErrorCandidates(document));
      if (err) return { err };
      const sel = matchProofSelector(document);
      if (isSignInProven(window.location, sel)) return { proof: sel };
      return false;
    }, 15000);

    const report = outcomeReport(observation);
    toast(document, report.message, report.kind === "success");
    log(report.kind, report.message);
  }

  // Export the pure decisions for tests; inert in the browser.
  const api = { pickErrorText, isSignInProven, attemptDecision, outcomeReport };
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  // Only run as a content script (not under the test runner).
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.getURL) {
    main();
  }
})();
