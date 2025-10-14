import cohere

API_KEY = "wH0m1tGPbPiJCCcISUo1QLJ0tAD2G4oV5By38R4Z"  # Replace this

try:
    co = cohere.Client(API_KEY)
    response = co.chat(
    model="command",  # legacy model still available on many accounts
    message="Hello Cohere! Testing connection."
)

    print("✅ Cohere chat response:", response.text.strip())

except Exception as e:
    print("❌ Cohere Chat API test failed:", str(e))
