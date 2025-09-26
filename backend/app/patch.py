# backend/app/patch.py

# This file has one purpose: to ensure eventlet monkey-patching happens
# before any other module in the application is imported.
# Eventlet monkey patching has been removed to avoid conflicts with asyncio and
# Windows-specific SSL/socket issues. Celery runs with the 'solo' pool and does
# not require eventlet. The web app uses standard asyncio (Uvicorn/FastAPI).