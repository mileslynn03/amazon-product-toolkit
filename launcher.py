"""Compatibility entry point for Amazon Product Toolkit's review subproject."""
import sys
from _review_project import load_review_module

_implementation = load_review_module("launcher")
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation
