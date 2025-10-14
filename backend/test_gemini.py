# test_gemini.py

import google.generativeai as genai
import time

genai.configure(api_key="AIzaSyBaU26_YC9z6kGuBbgxnV1k-HRqlGFLShY")

def call_gemini_with_retry(prompt, retries=3, delay=2):
    for attempt in range(retries):
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(delay)
    return None

prompt = "Hello, are you working?"
response_text = call_gemini_with_retry(prompt)
if response_text:
    print("Gemini response:", response_text)
else:
    print("Gemini service is temporarily unavailable. Please try again later.")