import requests
import json

url = "http://localhost:8000/text"
payload = {"text": "Hello Nova"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        with open("response.wav", "wb") as f:
            f.write(response.content)
        print("Success! Audio saved to response.wav")
        print("Headers:", response.headers)
    else:
        print("Error:", response.text)
except Exception as e:
    print(f"Request failed: {e}")
