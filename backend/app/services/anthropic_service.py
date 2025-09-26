# backend/app/services/anthropic_service.py

import anthropic
from app.config import settings

# ======================================================
# Initialize Anthropic client safely
# ======================================================
try:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
except Exception as e:
    print(f"[ERROR] Anthropic client setup failed: {e}")
    client = None


# ======================================================
# Text Generation
# ======================================================
def generate(
    prompt: str,
    model: str = "claude-3-haiku-20240307",  # default = fastest model
    max_tokens: int = 1024
) -> str:
    """
    Generate a response from Anthropic Claude models.

    Args:
        prompt (str): User input.
        model (str): Claude model (default: claude-3-haiku-20240307).
        max_tokens (int): Max tokens to return.

    Returns:
        str: AI-generated response text.
    """
    if not client:
        raise ConnectionError("Anthropic service is not configured.")

    try:
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] Anthropic.generate failed: {e}")
        raise
