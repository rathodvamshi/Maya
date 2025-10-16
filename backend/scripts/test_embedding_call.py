from __future__ import annotations
import os, sys
from pathlib import Path

# Ensure backend app import works
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.gemini_service import create_embedding


def main():
    vec = create_embedding("Hello world")
    print("Embedding length:", len(vec) if vec else None)
    assert vec and len(vec) == 1536, f"Expected 1536-d, got {len(vec) if vec else None}"
    print("PASS: Gemini embedding is 1536-d")


if __name__ == "__main__":
    main()
