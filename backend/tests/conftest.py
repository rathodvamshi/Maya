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

def pytest_configure(config):
    # Register asyncio marker to silence warnings if plugin init order changes
    config.addinivalue_line("markers", "asyncio: mark test as using asyncio")

# Fallback executor for async tests when pytest-asyncio isn't installed/loaded
def pytest_pyfunc_call(pyfuncitem):
    try:
        import inspect, asyncio
        func = pyfuncitem.obj
        is_async = inspect.iscoroutinefunction(func)
        has_asyncio_mark = any(m.name == "asyncio" for m in getattr(pyfuncitem, "iter_markers", lambda: [])())
        if is_async or has_asyncio_mark:
            asyncio.run(func(**pyfuncitem.funcargs))
            return True
    except Exception:
        # Let pytest handle normally if anything goes wrong
        return None
