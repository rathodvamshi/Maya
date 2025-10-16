"""Quick smoke test to validate embedding dimension matches settings.

Usage (from backend/):
  python scripts/embedding_smoke.py
"""
from __future__ import annotations

import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.config import settings
from app.services.embedding_service import create_embedding


def main():
    required = getattr(settings, "PINECONE_DIMENSIONS", 1024)
    text = "Hello, this is a dimension check."
    vec = create_embedding(text)
    ok = bool(vec and len(vec) == required)
    print(f"Required: {required}, Got: {len(vec) if vec else 'None'}")
    print("PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
