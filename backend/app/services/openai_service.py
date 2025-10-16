"""
OpenAI service for embeddings and optional text generation.

Implements 1024-d embeddings using model 'text-embedding-3-large' via HTTP API.
We use httpx (already a dependency) instead of the openai SDK to keep the
footprint minimal. Requires OPENAI_API_KEY in environment.
"""

from __future__ import annotations

import logging
from typing import List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def create_embedding(text: str, *, model: Optional[str] = None, dimensions: Optional[int] = None, timeout: float = 30.0) -> List[float]:
	"""Create an embedding using OpenAI's embeddings endpoint.

	- Default model: text-embedding-3-large
	- Default dimensions: settings.PINECONE_DIMENSIONS (expected 1024)
	Returns a Python list[float]. Raises on errors or dimension mismatch.
	"""
	api_key = getattr(settings, "OPENAI_API_KEY", None)
	if not api_key:
		raise ConnectionError("OPENAI_API_KEY is not configured.")

	mdl = model or "text-embedding-3-large"
	dims = dimensions or getattr(settings, "PINECONE_DIMENSIONS", 1024)

	url = "https://api.openai.com/v1/embeddings"
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}
	payload = {
		"model": mdl,
		"input": text,
		"dimensions": dims,
	}

	try:
		with httpx.Client(timeout=timeout) as client:
			resp = client.post(url, headers=headers, json=payload)
			resp.raise_for_status()
			data = resp.json()
			# Response shape: { data: [ { embedding: [...], index: 0, object: 'embedding'}], model: ..., object: 'list'}
			arr = None
			if isinstance(data, dict):
				items = data.get("data") or []
				if items and isinstance(items, list):
					first = items[0]
					arr = first.get("embedding") if isinstance(first, dict) else None
			if not arr or not isinstance(arr, list):
				raise ValueError("OpenAI embeddings response missing 'data[0].embedding'")
			if len(arr) != dims:
				raise ValueError(f"Embedding dimension mismatch: expected {dims}, got {len(arr)}")
			return arr
	except Exception as e:
		logger.error(f"OpenAI create_embedding failed: {e}")
		raise


def generate(prompt: str) -> str:
	"""Optional: simple stub for text generation if ever needed. Not used currently."""
	raise NotImplementedError("Text generation via OpenAI is not enabled in this project.")
