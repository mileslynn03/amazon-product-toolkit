"""Load the review subproject while preserving the toolkit's existing local data."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REVIEW_ROOT = ROOT / "projects" / "amazon-review-scraper"


def load_review_module(name):
    os.environ.setdefault("AMAZON_REVIEW_HOME", str(ROOT))
    os.environ.setdefault("AMAZON_REVIEW_PROJECT_ROOT", str(ROOT))
    os.environ.setdefault("AMAZON_REVIEW_APP_ID", "amazon-product-toolkit")
    location = str(REVIEW_ROOT)
    if location not in sys.path:
        sys.path.insert(0, location)
    spec = importlib.util.spec_from_file_location(name, REVIEW_ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
