# Ensure the 'app' package is importable when running tests directly.
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
APP_DIR = os.path.join(BACKEND_DIR, 'app')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
