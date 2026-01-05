
import requests

try:
    print("Sending request to public endpoint...")
    r = requests.post("http://nova.mejona.com/text", json={"text": "hello"}, stream=True, timeout=60)
    
    print(f"Status Code: {r.status_code}")
    print("--- HEADERS ---")
    for k, v in r.headers.items():
        print(f"{k}: {v}")
    print("----------------")
    
    # Read a bit of content to ensure stream works
    chunk = r.raw.read(1024)
    print(f"First 1024 bytes read: {len(chunk)}")

except Exception as e:
    print(f"Error: {e}")
