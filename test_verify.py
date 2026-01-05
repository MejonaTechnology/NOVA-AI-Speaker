
import requests
try:
    print("Testing public /text endpoint...")
    r = requests.post("http://nova.mejona.com/text", json={"text": "hello"}, timeout=60)
    print(f"Status: {r.status_code}")
    print(f"Content-Length: {len(r.content)}")
    if r.status_code == 200:
        print("SUCCESS: Audio received")
    else:
        print(f"FAILURE: {r.text}")
except Exception as e:
    print(f"ERROR: {e}")
