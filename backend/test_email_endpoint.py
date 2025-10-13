import requests

try:
    response = requests.get("http://localhost:8000/test-email?recipient=test@example.com")
    response.raise_for_status()
    print(response.json())
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
