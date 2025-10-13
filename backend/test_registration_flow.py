import requests
import time

API_BASE = "http://localhost:8000/api/auth"
TEST_EMAIL = "your@email.com"  # Change to a real test email
TEST_PASSWORD = "TestPassword123!"

# Step 1: Register (send OTP)
print("Step 1: Request OTP for registration...")
resp = requests.post(f"{API_BASE}/register", json={"email": TEST_EMAIL})
print("Status:", resp.status_code)
print("Response:", resp.text)
assert resp.status_code == 200, "Failed to send OTP"

input("Check your email for the OTP. Press Enter to continue...")
OTP = input("Enter the OTP you received: ")

# Step 2: Verify OTP and complete registration
print("Step 2: Verify OTP and complete registration...")
verify_payload = {
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD,
    "otp": OTP,
    "is_verified": True
}
resp2 = requests.post(f"{API_BASE}/verify-otp", json=verify_payload)
print("Status:", resp2.status_code)
print("Response:", resp2.text)
assert resp2.status_code == 200, "Failed to verify OTP and register user"

print("Registration flow test complete!")
