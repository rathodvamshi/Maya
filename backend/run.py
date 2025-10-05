# backend/run.py
import os
from pathlib import Path
import uvicorn

"""Local development entrypoint.

Purpose: run the FastAPI app with hot-reload while preventing needless reloads
triggered by changes inside the virtual environment (site-packages).
"""

def build_reload_excludes(backend_dir: Path) -> list[str]:
    """Return patterns to exclude common virtual environment folders.

    We include both direct paths and glob patterns so WatchFiles/uvicorn ignores
    nested matches. Safe no-ops if folders don't exist.
    """
    patterns: list[str] = []
    for name in ("venv", ".venv", "env", ".env"):
        venv_path = backend_dir / name
        if venv_path.exists():
            # Explicit path
            patterns.append(str(venv_path))
            # Direct children
            patterns.append(str(venv_path / "*"))
            # Any recursive reference
            patterns.append(f"**/{name}/*")
    # Common noisy artifacts
    patterns.extend([
        "**/*.pyc",
        "**/__pycache__/*",
        "**/*.log",
    ])
    return patterns


if __name__ == "__main__":
    backend_dir = Path(__file__).parent.resolve()

    # Ensure backend directory in PYTHONPATH for direct module imports
    current_pp = os.environ.get("PYTHONPATH", "")
    if not current_pp:
        os.environ["PYTHONPATH"] = str(backend_dir)
    elif str(backend_dir) not in current_pp.split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{backend_dir}{os.pathsep}{current_pp}"

    # Limit reload scanning strictly to source dirs we actually edit
    reload_dirs = [
        str(backend_dir / "app"),
        str(backend_dir / "config"),  # if you edit yaml/persona files often
    ]

    reload_excludes = build_reload_excludes(backend_dir)

    # Fallback for older uvicorn versions that might not honor reload_excludes:
    # We also set WATCHFILES_IGNORE which WatchFiles respects (semicolon separated on Windows).
    if "WATCHFILES_IGNORE" not in os.environ:
        os.environ["WATCHFILES_IGNORE"] = ";".join(reload_excludes)

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("UVICORN_HOST", "127.0.0.1"),
        port=int(os.environ.get("UVICORN_PORT", "8000")),
        reload=True,
        reload_dirs=reload_dirs,
        reload_excludes=reload_excludes,  # type: ignore[arg-type]
        # You can add log_level here via UVICORN_LOG_LEVEL env if desired
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )
