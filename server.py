"""Compatibility ASGI entry point; the review implementation lives in projects/."""
import sys
from _review_project import load_review_module

_implementation = load_review_module("server")
if __name__ == "__main__":
    _implementation.uvicorn.run(_implementation.app, host="127.0.0.1", port=8000)
else:
    sys.modules[__name__] = _implementation
