"""Tests for the onboarding script's decisions (the parts that matter most:
the one-account rule, adult registration, and honest reporting).

Run: python -m unittest discover -s tests
"""

import importlib.util
import os
import sys
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "create_account", os.path.join(HERE, "..", "onboarding", "create_account.py"))
# import without executing argparse/main (module import is safe: main is guarded)
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)


class TestAdultAge(unittest.TestCase):
    def test_adult_birthdate_passes(self):
        self.assertTrue(ca.adult_age_ok("1990-06-15"))

    def test_minor_birthdate_refused(self):
        self.assertFalse(ca.adult_age_ok("2015-01-01"))

    def test_boundary_exactly_18(self):
        self.assertTrue(
            ca.adult_age_ok("2008-11-08", today=date(2026, 11, 8)))

    def test_garbage_birthdate_refused(self):
        self.assertFalse(ca.adult_age_ok("not-a-date"))


class TestOneAccountRule(unittest.TestCase):
    def test_existing_config_refuses(self):
        self.assertTrue(ca.decide_run(True, False).startswith("refuse"))

    def test_no_config_proceeds(self):
        self.assertEqual(ca.decide_run(False, False), "proceed")

    def test_retry_after_failure_discards_stale_config(self):
        self.assertTrue(
            ca.decide_run(True, True).startswith("delete-stale-config"))


class TestHonestReport(unittest.TestCase):
    def test_proven_only_with_evidence(self):
        out = ca.format_report(True, True, "signed-in indicator: X", "")
        self.assertIn("PROVEN", out)
        self.assertIn("X", out)

    def test_created_but_unproven_reports_unknown(self):
        # the critical honesty case: creation claimed, proof absent
        out = ca.format_report(True, False, "", "")
        self.assertIn("UNKNOWN", out)

    def test_failure_reports_verbatim_error(self):
        out = ca.format_report(False, False, "", "Email already in use")
        self.assertIn("NOT created", out)
        self.assertIn("Email already in use", out)


if __name__ == "__main__":
    unittest.main()
