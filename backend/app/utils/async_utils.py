# backend/app/utils.py

# CRITICAL: This file will handle the monkey-patching.
import eventlet
eventlet.monkey_patch()

import asyncio

def run_async(func, *args, **kwargs):
    """
    A helper function to run an async function from a synchronous context like Celery.
    """
    return asyncio.run(func(*args, **kwargs))