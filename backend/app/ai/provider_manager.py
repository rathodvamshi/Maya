"""
AI Provider Manager

Gemini-first minimal facade with tight timeouts.

This module provides a minimal async facade that can be used by
lightweight endpoints that only need a single-turn response without
the full prompt composition / memory plumbing of ai_service.

Integration example:

    from app.ai.provider_manager import AIProviderManager
    ai_manager = AIProviderManager()
    text = await ai_manager.generate(prompt, user_id)

Note: The existing app.services.ai_service still offers the rich,
context-aware path used by chat flows. This manager is additive and
safe to adopt incrementally where appropriate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.config import settings

# Reuse existing service modules
from app.services import gemini_service as _gemini

logger = logging.getLogger(__name__)


class AIProviderManager:
    def __init__(self, *, timeout: Optional[float] = None) -> None:
        # Single quick budget for both tries; caller can override per-call too
        self.TIMEOUT: float = float(timeout if timeout is not None else (getattr(settings, "AI_TIMEOUT", 8) or 8))

    async def _gen_gemini(self, prompt: str) -> str:
        # Run the sync provider in a worker thread
        return await asyncio.to_thread(_gemini.generate, prompt)

    async def _gen_cohere(self, prompt: str) -> str:
        raise RuntimeError("Cohere support removed")

    async def generate(self, prompt: str, user_id: str | None = None, timeout: Optional[float] = None) -> str:
        """Generate using Gemini.

        Timeout applies per attempt to keep snappy responses.
        """
        budget = float(timeout if timeout is not None else self.TIMEOUT)
        start = time.time()

        # Fast path: Gemini
        try:
            text = await asyncio.wait_for(self._gen_gemini(prompt), timeout=budget)
            latency = int((time.time() - start) * 1000)
            logger.info(f"[AI] Gemini responded in {latency}ms")
            return text
        except Exception as gemini_error:  # noqa: BLE001
            logger.error(f"[AI] Gemini failed: {gemini_error}")
            return "Sorry, I'm having trouble connecting to the AI service right now."
