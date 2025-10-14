import os
import sys
from openai import OpenAI

# Read API key from environment. Do NOT hardcode secrets in code.
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY is not set. Create backend/.env with OPENAI_API_KEY=... and load it in your shell.")
    sys.exit(1)

client = OpenAI(api_key=api_key)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello! Can you test if my key works?"}]
)

print(response.choices[0].message.content)
