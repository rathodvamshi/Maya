#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Simple, dependency-free scanner. Avoids network calls and keeps safety-first.

BACKEND_DIR = Path('backend')
FRONTEND_DIR = Path('frontend')
DEFAULT_IGNORE = {
    'venv', '.venv', 'node_modules', 'build', 'dist', '__pycache__', '.cache', '.git', '.idea', '.vscode'
}
FILE_EXTS = {
    'py': {'.py'},
    'js': {'.js', '.jsx', '.ts', '.tsx'},
    'html': {'.html', '.htm'},
    'css': {'.css', '.scss', '.sass'},
}

ROUTE_DECORATOR_ANY_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\.(get|post|put|delete|patch|options|head)\(\s*\"([^\"]*)\"[^\)]*\)")
APIR_VAR_PREFIX_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*APIRouter\(\s*prefix\s*=\s*\"([^\"]*)\"")
FRONTEND_API_RE = re.compile(r"apiClient\.(get|post|put|patch|delete)\(\s*([`'\"])(/[^`'\"]*)\2")
FETCH_RE = re.compile(r"fetch\(\s*([`'\"])(/[^`'\"]*)\1")

COMMENT_PATTERNS = {
    'py': [
        (re.compile(r"#.*"), ''),
        (re.compile(r"'''[\s\S]*?'''", re.M), ''),
        (re.compile(r'"""[\s\S]*?"""', re.M), ''),
    ],
    'js': [
        (re.compile(r"//.*"), ''),
        (re.compile(r"/\*[\s\S]*?\*/", re.M), ''),
    ],
    'html': [
        (re.compile(r"<!--([\s\S]*?)-->", re.M), ''),
    ],
    'css': [
        (re.compile(r"/\*[\s\S]*?\*/", re.M), ''),
    ],
}

DUPLICATE_MIN_LEN = 6  # lines


def iter_files(root: Path, include_exts: Set[str], ignore: Set[str]) -> Iterable[Path]:
    for p in root.rglob('*'):
        if any(part in ignore for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in include_exts:
            yield p


def find_backend_endpoints() -> Dict[str, Any]:
    results: Dict[str, Any] = { 'routers': [] }
    routers_dir = BACKEND_DIR / 'app' / 'routers'
    if not routers_dir.exists():
        return results
    for py in iter_files(routers_dir, FILE_EXTS['py'], DEFAULT_IGNORE):
        try:
            txt = py.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        # Build map of router var -> prefix
        var_prefix: Dict[str, str] = {}
        for vm in APIR_VAR_PREFIX_RE.finditer(txt):
            var_prefix[vm.group(1)] = vm.group(2)

        endpoints = []
        for m in ROUTE_DECORATOR_ANY_RE.finditer(txt):
            var = m.group(1)
            method = m.group(2).upper()
            path = m.group(3)
            prefix = var_prefix.get(var, '')
            full_path = (prefix + path) if prefix else path
            endpoints.append({'var': var, 'method': method, 'path': full_path})
        results['routers'].append({ 'file': str(py), 'prefix_map': var_prefix, 'endpoints': endpoints })
    return results


def analyze_python_dependencies(root: Path) -> Dict[str, Any]:
    req_path = root / 'backend' / 'requirements.txt'
    result: Dict[str, Any] = {
        'duplicates': [],
        'unversioned': [],
        'entries': [],
        'unused_suspects': [],
        'missing_suspects': [],
    }
    if not req_path.exists():
        return result
    # Parse requirements lines (ignore comments/empty)
    lines = [ln.strip() for ln in req_path.read_text(encoding='utf-8', errors='ignore').splitlines()]
    pkgs: List[str] = []
    seen: Dict[str, int] = {}
    for ln in lines:
        if not ln or ln.startswith('#'):
            continue
        result['entries'].append(ln)
        name = re.split(r"[<>=\[]", ln, maxsplit=1)[0].strip().lower()
        if not name:
            continue
        pkgs.append(name)
        seen[name] = seen.get(name, 0) + 1
        if not any(op in ln for op in ('==', '>=', '<=', '~=', '!=')) and name not in {'uvicorn','fastapi','pytest'}:
            result['unversioned'].append(ln)
    result['duplicates'] = [p for p, c in seen.items() if c > 1]

    # Heuristic import usage collection
    imported: Set[str] = set()
    for py in iter_files(root / 'backend', FILE_EXTS['py'], DEFAULT_IGNORE):
        try:
            txt = py.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for m in re.finditer(r"^\s*import\s+([a-zA-Z0-9_\.]+)", txt, re.M):
            imported.add(m.group(1).split('.')[0].lower())
        for m in re.finditer(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+", txt, re.M):
            imported.add(m.group(1).split('.')[0].lower())

    # Simple mapping from requirement to top-level import name (best effort)
    def top_level_name(req: str) -> str:
        # common cases
        mapping = {
            'pymongo': 'pymongo',
            'python-jose': 'jose',
            'pydantic-settings': 'pydantic_settings',
            'python-multipart': 'multipart',
            'pinecone-client': 'pinecone',
            'python-dotenv': 'dotenv',
            'google-generativeai': 'google',
            'neo4j': 'neo4j',
            'dateparser': 'dateparser',
            'python-dateutil': 'dateutil',
            'prometheus-client': 'prometheus_client',
        }
        return mapping.get(req, req.replace('-', '_'))

    req_names = [re.split(r"[<>=\[]", e, maxsplit=1)[0].strip().lower() for e in result['entries']]
    for name in req_names:
        tl = top_level_name(name)
        if tl not in imported:
            result['unused_suspects'].append(name)
    for mod in sorted(imported):
        # Skip app-local modules
        if mod in {'app','tests'}:
            continue
        # Inverse mapping may be imperfect; only flag obvious ones
        if mod not in {top_level_name(n) for n in req_names}:
            result['missing_suspects'].append(mod)
    return result


def analyze_frontend_dependencies(root: Path) -> Dict[str, Any]:
    pkg_path = root / 'frontend' / 'package.json'
    result: Dict[str, Any] = {
        'declared': {},
        'unused_suspects': [],
        'missing_suspects': [],
    }
    if not pkg_path.exists():
        return result
    try:
        pkg = json.loads(pkg_path.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        return result
    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
    result['declared'] = deps

    # Collect imports/require usage
    used: Set[str] = set()
    for f in iter_files(root / 'frontend', FILE_EXTS['js'], DEFAULT_IGNORE):
        try:
            txt = f.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for m in re.finditer(r'^\s*import\s+(?:[^\'\"]+\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]', txt, re.M):
            used.add(m.group(1).split('/')[0])
        for m in re.finditer(r'require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)', txt):
            used.add(m.group(1).split('/')[0])
    declared_names = set(deps.keys())
    # Exclude relative imports and alias '@'
    used_pkgs = {u for u in used if not u.startswith('.') and not u.startswith('@types/')}
    result['unused_suspects'] = sorted([d for d in declared_names if d not in used_pkgs])
    result['missing_suspects'] = sorted([u for u in used_pkgs if u not in declared_names and not u.startswith('@')])
    return result


def find_frontend_api_calls() -> List[Dict[str, str]]:
    calls: List[Dict[str, str]] = []
    if not FRONTEND_DIR.exists():
        return calls
    include = FILE_EXTS['js'] | FILE_EXTS['html']
    for f in iter_files(FRONTEND_DIR, include, DEFAULT_IGNORE):
        try:
            txt = f.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for m in FRONTEND_API_RE.finditer(txt):
            calls.append({'file': str(f), 'method': m.group(1).upper(), 'path': m.group(3)})
        for m in FETCH_RE.finditer(txt):
            calls.append({'file': str(f), 'method': 'GET', 'path': m.group(2)})
    return calls


def strip_comments_text(text: str, lang: str) -> Tuple[str, int]:
    patterns = COMMENT_PATTERNS.get(lang)
    if not patterns:
        return text, 0
    total_removed = 0
    for rx, repl in patterns:
        before = len(text)
        text = rx.sub(repl, text)
        total_removed += (before - len(text))
    return text, total_removed


def strip_comments_in_files(files: List[Path], lang: str, apply: bool) -> Dict[str, Any]:
    summary = { 'files': [], 'bytes_removed': 0 }
    for f in files:
        try:
            orig = f.read_text(encoding='utf-8', errors='ignore')
            new, removed = strip_comments_text(orig, lang)
            if removed > 0:
                summary['files'].append(str(f))
                summary['bytes_removed'] += removed
                if apply:
                    f.write_text(new, encoding='utf-8')
        except Exception:
            continue
    return summary


def detect_duplicate_blocks(files: List[Path]) -> Dict[str, List[str]]:
    # Hash normalized line blocks to find duplicates across files.
    from hashlib import sha1
    index: Dict[str, List[str]] = {}
    def norm(line: str) -> str:
        return re.sub(r"\s+", " ", line.strip())
    for f in files:
        try:
            lines = f.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            continue
        for i in range(0, max(0, len(lines) - DUPLICATE_MIN_LEN + 1)):
            block = '\n'.join(norm(l) for l in lines[i:i + DUPLICATE_MIN_LEN])
            if not block or len(block) < 20:
                continue
            h = sha1(block.encode('utf-8')).hexdigest()
            index.setdefault(h, []).append(f"{f}#L{i+1}")
    # Keep only duplicates appearing in 2+ locations
    return {h: locs for h, locs in index.items() if len(locs) > 1}


def canonicalize_path(p: str) -> str:
    # Drop query string
    p = p.split('?', 1)[0]
    # Ensure leading slash
    if not p.startswith('/'):
        p = '/' + p
    # Replace JS template placeholders and FastAPI params with generic '{}'
    p = re.sub(r"\$\{[^}]+\}", "{}", p)  # JS template literals
    p = re.sub(r"\{[^}]+\}", "{}", p)     # FastAPI path params
    p = re.sub(r":[A-Za-z_][A-Za-z0-9_-]*", "{}", p)  # Express-style
    # Normalize multiple slashes
    p = re.sub(r"/+", "/", p)
    # Remove trailing slash except root
    if len(p) > 1 and p.endswith('/'):
        p = p[:-1]
    return p


def collect_temp_and_caches(root: Path) -> Dict[str, List[str]]:
    remove_files: List[str] = []
    remove_dirs: List[str] = []
    for p in root.rglob('*'):
        if any(part in DEFAULT_IGNORE for part in p.parts):
            continue
        name = p.name.lower()
        if p.is_file() and (name.endswith('.log') or name.endswith('.tmp') or name.endswith('.bak')):
            remove_files.append(str(p))
        if p.is_dir() and (name in {'__pycache__', '.cache'}):
            remove_dirs.append(str(p))
    return {'files': remove_files, 'dirs': remove_dirs}


def backup_paths(paths: List[str], dest_zip: Path) -> None:
    import zipfile
    with zipfile.ZipFile(dest_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            pth = Path(p)
            if pth.is_file():
                z.write(pth, arcname=str(pth))
            elif pth.is_dir():
                for sub in pth.rglob('*'):
                    if sub.is_file():
                        z.write(sub, arcname=str(sub))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Project Cleaner & Auditor (dry-run by default)')
    ap.add_argument('--root', default='.', help='Project root path')
    ap.add_argument('--report', default='reports', help='Report output directory')
    ap.add_argument('--apply', action='store_true', help='Apply safe changes (comment strip, cache delete)')
    ap.add_argument('--backup', action='store_true', help='Create a zip backup before destructive actions')
    ap.add_argument('--strip-comments', default='', help='Comma list of languages to strip: py,js,html,css')
    ap.add_argument('--delete-caches', default='no', help='yes to delete caches/temp/logs')
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    report_dir = (root / args.report)
    report_dir.mkdir(parents=True, exist_ok=True)

    backend_endpoints = find_backend_endpoints()
    frontend_calls = find_frontend_api_calls()
    py_dep = analyze_python_dependencies(root)
    fe_dep = analyze_frontend_dependencies(root)

    # Comment stripping
    strip_langs = {s.strip() for s in args.strip_comments.split(',') if s.strip()}
    comment_summary: Dict[str, Any] = {}
    if strip_langs:
        for lang in strip_langs:
            include_exts = FILE_EXTS.get(lang)
            if not include_exts:
                continue
            files = list(iter_files(root, include_exts, DEFAULT_IGNORE))
            if args.apply and args.backup and files:
                backup_zip = report_dir / f"backup_comments_{lang}.zip"
                backup_paths([str(f) for f in files], backup_zip)
            comment_summary[lang] = strip_comments_in_files(files, lang, apply=args.apply)

    # Duplicate detection
    code_files = list(iter_files(root, FILE_EXTS['py'] | FILE_EXTS['js'], DEFAULT_IGNORE))
    duplicates = detect_duplicate_blocks(code_files)

    # Temp / caches
    temp_info = collect_temp_and_caches(root)
    if args.apply and args.delete_caches.lower() == 'yes':
        to_backup: List[str] = temp_info['files'] + temp_info['dirs']
        if args.backup and to_backup:
            backup_zip = report_dir / 'backup_temp_cache.zip'
            backup_paths(to_backup, backup_zip)
        for f in temp_info['files']:
            try:
                os.remove(f)
            except Exception:
                pass
        for d in temp_info['dirs']:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    # Cross-reference endpoints and frontend calls
    endpoint_set = {(ep['method'], canonicalize_path(ep['path']))
                    for r in backend_endpoints.get('routers', []) for ep in r.get('endpoints', [])}
    used_endpoints: Set[Tuple[str, str]] = set()
    unknown_calls: List[Dict[str, str]] = []
    for call in frontend_calls:
        # Normalize to /api/* by default since frontend baseURL includes /api
        method = call['method']
        path = call['path']
        norm_path = path if path.startswith('/api') else f"/api{path}"
        k = (method, canonicalize_path(norm_path))
        if k in endpoint_set:
            used_endpoints.add(k)
        else:
            unknown_calls.append({**call, 'normalized': canonicalize_path(norm_path)})

    unused_endpoints = [
        {'method': m, 'path': p}
        for (m, p) in sorted(endpoint_set)
        if (m, p) not in used_endpoints and not p.startswith('/health') and not p.startswith('/metrics')
    ]

    report: Dict[str, Any] = {
        'backend_endpoints': backend_endpoints,
        'frontend_calls': frontend_calls,
        'unknown_frontend_calls': unknown_calls,
        'unused_endpoints': unused_endpoints,
        'duplicates_count': len(duplicates),
        'duplicates': {h: locs for h, locs in list(duplicates.items())[:100]},  # limit in JSON
        'comment_strip': comment_summary,
        'temp_and_caches': temp_info,
        'python_dependencies': py_dep,
        'frontend_dependencies': fe_dep,
        'applied': bool(args.apply),
    }

    # Write reports
    (report_dir / 'debug_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    # Minimal markdown summary
    md_lines = [
        '# Debug Report',
        '',
        f"Applied: {args.apply}",
        f"Backend routers: {len(backend_endpoints.get('routers', []))}",
        f"Frontend calls: {len(frontend_calls)}",
        f"Unknown frontend calls: {len(unknown_calls)}",
        f"Unused endpoints: {len(unused_endpoints)}",
        f"Duplicate blocks: {len(duplicates)}",
    f"Python deps: {len(py_dep.get('entries', []))} (dups: {len(py_dep.get('duplicates', []))})",
    f"Frontend deps: {len(fe_dep.get('declared', {}))}",
        '',
        '## Unused endpoints (first 50)',
    ]
    for ep in unused_endpoints[:50]:
        md_lines.append(f"- {ep['method']} {ep['path']}")
    md_lines += ['', '## Unknown frontend calls (first 50)']
    for c in unknown_calls[:50]:
        md_lines.append(f"- {c['method']} {c['path']} -> normalized {c['normalized']} ({c['file']})")
    (report_dir / 'debug_report.md').write_text('\n'.join(md_lines), encoding='utf-8')

    print(f"Report written to {report_dir}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
