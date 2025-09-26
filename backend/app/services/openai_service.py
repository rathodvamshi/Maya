# backend/app/services/openai_service.py

from openai import OpenAI, RateLimitError
from app.config import settings

# A global variable to track the current API key index.
current_key_index = 0
# Parse the comma-separated string of keys from settings into a list.
api_keys = [key.strip() for key in settings.OPENAI_API_KEYS.split(',')]

def generate_ai_response(prompt: str) -> str:
    """
    Generates a response from OpenAI's GPT model.
    If the current API key is rate-limited, it automatically switches to the next one.
    """
    global current_key_index
    if not api_keys or not all(api_keys):
        return "Error: No OpenAI API keys are configured. Please check your .env file."

    start_index = current_key_index
    while True:
        try:
            # Select the current key and initialize the client.
            key_to_try = api_keys[current_key_index]
            client = OpenAI(api_key=key_to_try)

            # Make the API call.
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful and friendly personal assistant named Maya."},
                    {"role": "user", "content": prompt}
                ]
            )
            return completion.choices[0].message.content

        except RateLimitError:
            print(f"OpenAI API key at index {current_key_index} is rate-limited. Trying next key.")
            # Move to the next key.
            current_key_index = (current_key_index + 1) % len(api_keys)
            
            # If we've tried all keys and are back where we started, all are exhausted.
            if current_key_index == start_index:
                print("All available OpenAI API keys are rate-limited.")
                return "I'm currently experiencing a high volume of requests. Please try again in a little while."
        
        except Exception as e:
            print(f"An error occurred while generating OpenAI response: {e}")
            return "Sorry, I'm having trouble connecting to my brain right now. Please try again later."
