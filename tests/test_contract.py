#!/usr/bin/env python3
"""Three runnable tests, one per elegance gap in the naive client.

The theme: **the happy path is the mistake.** Each scenario is the kind of error
DeepAPI actually returns; the naive client's straightforward reaction is wrong,
and the fixed client honors the SKILL.md contract.

Run it two ways:
    python3 tests/test_contract.py     # prints the naive-vs-fixed matrix, then asserts
    python3 -m unittest discover -s tests
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_checks as cc


class Contract(unittest.TestCase):
    def test_fixed_honors_contract(self):
        for g in cc.GAPS:
            with self.subTest(gap=g["label"]):
                self.assertTrue(g["check"](cc.FIXED), f"fixed client should pass: {g['label']}")

    def test_naive_exhibits_the_bug(self):
        for g in cc.GAPS:
            with self.subTest(gap=g["label"]):
                self.assertFalse(g["check"](cc.NAIVE), f"naive client should fail: {g['label']}")


def matrix():
    ok, bad = "\033[32m✓\033[0m", "\033[31m✗\033[0m"
    print("\n  the happy path is the mistake\n")
    print(f"  {'gap':<38}{'naive':^8}{'fixed':^8}")
    print(f"  {'-' * 54}")
    for i, g in enumerate(cc.GAPS, 1):
        n = ok if g["check"](cc.NAIVE) else bad
        x = ok if g["check"](cc.FIXED) else bad
        print(f"  {str(i) + '  ' + g['label']:<38}{n:^17}{x:^17}")
        print(f"    \033[2m{g['recommendation']}\033[0m")
    print()


if __name__ == "__main__":
    matrix()
    unittest.main(argv=[sys.argv[0], "-v"], exit=False)
