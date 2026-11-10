// Tests for the honesty decisions in extension/content.js.
// Run: node --test tests/
// These are the parts the brief says matter most: what counts as an error,
// what counts as proof, when to attempt, and how outcomes are reported.

import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { pickErrorText, isSignInProven, attemptDecision, outcomeReport } =
  require("../extension/content.js");

test("pickErrorText returns the first real error verbatim", () => {
  assert.equal(
    pickErrorText(["", "Incorrect username or password.", "Something else"]),
    "Incorrect username or password.");
});

test("pickErrorText ignores field hints like 'required'", () => {
  assert.equal(pickErrorText(["required", "Password is incorrect"]), "Password is incorrect");
});

test("pickErrorText returns null when nothing real is showing", () => {
  assert.equal(pickErrorText(["", "  ", "required"]), null);
});

test("a matched selector alone is not proof while still on /login", () => {
  assert.equal(isSignInProven({ pathname: "/login" }, '[data-test-id="user-avatar"]'), false);
});

test("proof requires leaving /login AND an authenticated element", () => {
  assert.equal(isSignInProven({ pathname: "/" }, '[data-test-id="user-avatar"]'), true);
  assert.equal(isSignInProven({ pathname: "/" }, null), false);
});

test("one attempt per visit: already attempted means skip", () => {
  assert.deepEqual(
    attemptDecision(true, true, true),
    { action: "skip", reason: "already attempted this visit" });
});

test("missing config is reported, not skipped silently", () => {
  const d = attemptDecision(false, true, false);
  assert.equal(d.action, "report");
});

test("no form means do nothing on this page", () => {
  assert.deepEqual(
    attemptDecision(false, false, true),
    { action: "skip", reason: "login form not present" });
});

test("happy path attempts exactly once", () => {
  assert.deepEqual(attemptDecision(false, true, true), { action: "attempt" });
});

test("an error observation reports verbatim", () => {
  const r = outcomeReport({ err: "Invalid login credentials" });
  assert.equal(r.kind, "failed");
  assert.match(r.message, /"Invalid login credentials"/);
});

test("a proven observation reports the proof selector", () => {
  const r = outcomeReport({ proof: '[data-test-id="user-avatar"]' });
  assert.equal(r.kind, "success");
  assert.match(r.message, /user-avatar/);
});

test("no observation reports UNKNOWN instead of guessing", () => {
  const r = outcomeReport(null);
  assert.equal(r.kind, "unknown");
  assert.match(r.message, /UNKNOWN/);
});
