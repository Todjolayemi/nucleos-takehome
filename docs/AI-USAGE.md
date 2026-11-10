# AI usage (internal reference record)

The reference was drafted with an AgenticAI harness under direct human
direction: every design decision (the honesty-as-pure-functions
structure, the three-outcome report, zero-permission extension, one-account
guard, React-aware fill) was specified before code was written, and the code
was reviewed line by line.

What the process got wrong and how it was caught, same discipline as always:

1. The first extension draft mixed honesty decisions into DOM plumbing, so
   nothing was testable without a browser. Caught in review; restructured
   into pure deciders plus thin plumbing, which is the shape that makes the
   brief's core rules testable at all.
2. The onboarding module imported Playwright at import time, which made the
   test suite depend on a browser stack. Caught when the tests failed to
   import; import moved to run time.
3. One test asserted an exact string where the function returns a prefixed
   reason. Caught by the failing test itself. Small, but it is the loop
   working: the check said no, so its yes means something.

Selects for Khan Academy's live pages (form fields, error containers,
signed-in indicators) were derived from a live render of the login page and
defensive fallbacks; they must be re-verified at run time against the live
site, and the reference README says so.
