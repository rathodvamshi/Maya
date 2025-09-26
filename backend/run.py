# backend/run.py
import uvicorn
import os

if __name__ == "__main__":
    # Set the Python path dynamically to ensure 'app' can be found
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if os.environ.get("PYTHONPATH") is None:
        os.environ["PYTHONPATH"] = backend_dir
    elif backend_dir not in os.environ["PYTHONPATH"]:
        os.environ["PYTHONPATH"] = f"{backend_dir}{os.pathsep}{os.environ['PYTHONPATH']}"

    # Run Uvicorn with reload enabled
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # The reload directories are now correctly pointing to the app source
        reload_dirs=[os.path.join(backend_dir, "app")]
    )
