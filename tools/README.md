Project Cleaner & Auditor

This folder contains a self-contained automation to scan, clean, and audit the repository.

Features (dry-run by default):
- Map backend FastAPI endpoints and routers
- Cross-reference frontend API calls (axios/fetch)
- Count and optionally strip comments (Python, JS/TS, HTML/CSS)
- Detect duplicate functions/classes heuristically
- Identify dead code candidates (unused functions/imports)
- Identify temp/log/cache files and safe-delete in apply mode
- Generate debug_report.json and debug_report.md

Usage (Windows cmd):
- Dry run:
  python tools\\clean_and_audit.py --root . --report reports

- Apply selected actions (comment strip, cleanup) with backup:
  python tools\\clean_and_audit.py --root . --report reports --apply --backup

Flags:
- --strip-comments py,js,html,css
- --delete-caches yes
- --max-file-size-mb 2
- --ignore "venv,node_modules,build,__pycache__,.cache"

Notes:
- Always review the generated report before applying destructive actions.
- Endpoint verification is static (no server needed). Optional runtime probe to be added later.
