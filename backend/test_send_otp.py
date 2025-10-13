import requests

# Change this to your test email address
email = "rahulkonda30@gmail.com"

url = "http://localhost:8000/api/auth/send-otp"
payload = {"email": email}

try:
    response = requests.post(url, json=payload)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
