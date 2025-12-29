"""
Test Tuya Light Control with curl-equivalent Python script
This script tests the Tuya API directly to debug light control issues
"""

import time
import hashlib
import hmac
import json
import requests

# Tuya credentials
ENDPOINT = "https://openapi.tuyain.com"
ACCESS_ID = "hqs4w54j7jaduwse8nec"
ACCESS_SECRET = "cecbd09a8b5846539319e042d9210583"
DEVICE_ID = "d7a2448c70762e9235aca7"

def calculate_sign(access_id, access_secret, access_token, method, path, body=None):
    """Calculate signature for Tuya API request"""
    timestamp = str(int(time.time() * 1000))

    # Build string to sign
    str_to_sign = method + "\n"

    # Content hash (empty if no body)
    if body:
        content_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
    else:
        content_hash = hashlib.sha256(b"").hexdigest()
    str_to_sign += content_hash + "\n"

    # Headers to sign
    str_to_sign += "\n"

    # URL
    str_to_sign += path

    # Calculate signature
    if access_token:
        sign_str = access_id + access_token + timestamp + str_to_sign
    else:
        sign_str = access_id + timestamp + str_to_sign

    sign = hmac.new(
        access_secret.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()

    return sign, timestamp

def get_access_token():
    """Get access token from Tuya"""
    path = "/v1.0/token?grant_type=1"
    method = "GET"

    sign, timestamp = calculate_sign(ACCESS_ID, ACCESS_SECRET, None, method, path)

    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        'sign_method': 'HMAC-SHA256',
        't': timestamp,
    }

    url = ENDPOINT + path
    print(f"\n[AUTH] Getting Access Token...")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")

    response = requests.get(url, headers=headers, timeout=10)

    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            access_token = result['result']['access_token']
            print(f"\n[SUCCESS] Access token obtained: {access_token[:20]}...")
            return access_token
        else:
            print(f"\n[ERROR] Failed to get token: {result}")
            return None
    else:
        print(f"\n[ERROR] HTTP Error: {response.status_code}")
        return None

def send_command(access_token, commands, command_name):
    """Send command to Tuya device"""
    path = f"/v1.0/devices/{DEVICE_ID}/commands"
    method = "POST"
    body = json.dumps({"commands": commands})

    sign, timestamp = calculate_sign(ACCESS_ID, ACCESS_SECRET, access_token, method, path, body=body)

    headers = {
        'client_id': ACCESS_ID,
        'access_token': access_token,
        'sign': sign,
        'sign_method': 'HMAC-SHA256',
        't': timestamp,
        'Content-Type': 'application/json'
    }

    url = ENDPOINT + path
    print(f"\n[CMD] Sending Command: {command_name}")
    print(f"URL: {url}")
    print(f"Body: {body}")
    print(f"Headers: {json.dumps({k: v for k, v in headers.items() if k != 'access_token'}, indent=2)}")

    response = requests.post(url, headers=headers, data=body, timeout=10)

    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print(f"[SUCCESS] Command '{command_name}' sent successfully!")
            return True
        else:
            print(f"[ERROR] Command '{command_name}' failed: {result}")
            return False
    else:
        print(f"[ERROR] HTTP Error: {response.status_code}")
        return False

def main():
    print("=" * 60)
    print("  TUYA LIGHT CONTROL TEST - Direct API Testing")
    print("=" * 60)

    # Step 1: Get access token
    access_token = get_access_token()
    if not access_token:
        print("\n[ERROR] Failed to get access token. Exiting.")
        return

    # Step 2: Test commands
    print("\n" + "=" * 60)
    print("  TESTING LIGHT COMMANDS")
    print("=" * 60)

    # Test 1: Turn light ON
    print("\n\n[TEST 1] Turning light ON...")
    send_command(access_token, [{"code": "switch_led", "value": True}], "TURN ON")
    time.sleep(2)

    # Test 2: Set brightness to 50%
    print("\n\n[TEST 2] Setting brightness to 50%...")
    send_command(access_token, [{"code": "bright_value_v2", "value": 500}], "BRIGHTNESS 50%")
    time.sleep(2)

    # Test 3: Set color to BLUE
    print("\n\n[TEST 3] Setting color to BLUE...")
    send_command(access_token, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 240, "s": 1000, "v": 700}}
    ], "COLOR BLUE")
    time.sleep(2)

    # Test 4: Set color to RED
    print("\n\n[TEST 4] Setting color to RED...")
    send_command(access_token, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 0, "s": 1000, "v": 700}}
    ], "COLOR RED")
    time.sleep(2)

    # Test 5: Turn light OFF
    print("\n\n[TEST 5] Turning light OFF...")
    send_command(access_token, [{"code": "switch_led", "value": False}], "TURN OFF")

    print("\n" + "=" * 60)
    print("  TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
