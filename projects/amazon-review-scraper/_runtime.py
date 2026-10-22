"""Explicit source and data locations for standalone and toolkit launches."""
from __future__ import annotations

import os
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.environ.get("AMAZON_REVIEW_PROJECT_ROOT", str(SOURCE_ROOT))).expanduser().resolve()
DATA_HOME = Path(os.environ.get("AMAZON_REVIEW_HOME", str(SOURCE_ROOT))).expanduser().resolve()
APP_ID = os.environ.get("AMAZON_REVIEW_APP_ID", "amazon-review-scraper-gui")
