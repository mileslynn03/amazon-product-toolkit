"""Run the canonical review test suite from the toolkit's existing test command."""
import os
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "amazon-review-scraper"


class ReviewSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        before = Path.cwd()
        try:
            os.chdir(PROJECT)
            return super().run(result, debug)
        finally:
            os.chdir(before)


def load_tests(loader, tests, pattern):
    sys.path.insert(0, str(PROJECT))
    review_loader = unittest.TestLoader()
    review_loader.testNamePatterns = loader.testNamePatterns
    suite = review_loader.discover(str(PROJECT / "tests"))
    return ReviewSuite([suite])
