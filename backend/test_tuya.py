"""
Test script for Tuya Smart Light API
Authenticates and sends commands to control bedroom light
"""

import time
import hashlib
import hmac
import json
import requests

# Tuya Credentials
ACCESS_ID = "hqs4w54j7jaduwse8nec"
ACCESS_SECRET = "cecbd09a8b5846539319e042d9210583"
API_ENDPOINT = "https://openapi.tuyain.com"  # India Data Center

class TuyaOpenAPI:
    def __init__(self, endpoint, access_id, access_secret):
        self.endpoint = endpoint
        self.access_id = access_id
        self.access_secret = access_secret
        self.access_token = None

    def _calculate_sign(self, method, path, params=None, body=None):
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
        if self.access_token:
            sign_str = self.access_id + self.access_token + timestamp + str_to_sign
        else:
            sign_str = self.access_id + timestamp + str_to_sign

        sign = hmac.new(
            self.access_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return sign, timestamp

    def get_access_token(self):
        """Get access token from Tuya"""
        path = "/v1.0/token?grant_type=1"
        method = "GET"

        sign, timestamp = self._calculate_sign(method, path)

        headers = {
            'client_id': self.access_id,
            'sign': sign,
            'sign_method': 'HMAC-SHA256',
            't': timestamp,
        }

        url = self.endpoint + path
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                self.access_token = result['result']['access_token']
                print(f"[OK] Access token obtained: {self.access_token[:20]}...")
                return True
            else:
                print(f"[FAIL] Failed to get token: {result}")
                return False
        else:
            print(f"[ERROR] HTTP Error: {response.status_code} - {response.text}")
            return False

    def get_devices(self):
        """Get list of all devices"""
        if not self.access_token:
            print("[ERROR] No access token. Call get_access_token() first")
            return None

        path = "/v1.0/devices"
        method = "GET"

        sign, timestamp = self._calculate_sign(method, path)

        headers = {
            'client_id': self.access_id,
            'access_token': self.access_token,
            'sign': sign,
            'sign_method': 'HMAC-SHA256',
            't': timestamp,
        }

        url = self.endpoint + path
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                devices = result['result']
                print(f"[OK] Found {len(devices)} devices:")
                for device in devices:
                    print(f"   - {device['name']} (ID: {device['id']})")
                return devices
            else:
                print(f"[FAIL] Failed to get devices: {result}")
                return None
        else:
            print(f"[ERROR] HTTP Error: {response.status_code} - {response.text}")
            return None

    def send_commands(self, device_id, commands):
        """Send commands to a device"""
        if not self.access_token:
            print("[ERROR] No access token. Call get_access_token() first")
            return False

        path = f"/v1.0/devices/{device_id}/commands"
        method = "POST"
        body = json.dumps({"commands": commands})

        sign, timestamp = self._calculate_sign(method, path, body=body)

        headers = {
            'client_id': self.access_id,
            'access_token': self.access_token,
            'sign': sign,
            'sign_method': 'HMAC-SHA256',
            't': timestamp,
            'Content-Type': 'application/json'
        }

        url = self.endpoint + path
        response = requests.post(url, headers=headers, data=body)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"[OK] Command sent successfully: {result}")
                return True
            else:
                print(f"[FAIL] Command failed: {result}")
                return False
        else:
            print(f"[ERROR] HTTP Error: {response.status_code} - {response.text}")
            return False


def test_light_control():
    """Test various light control commands"""

    # Initialize API
    api = TuyaOpenAPI(API_ENDPOINT, ACCESS_ID, ACCESS_SECRET)

    # Step 1: Get access token
    print("\n" + "="*60)
    print("STEP 1: Getting Access Token")
    print("="*60)
    if not api.get_access_token():
        print("Failed to authenticate. Exiting.")
        return

    # Step 2: Use provided Device ID
    print("\n" + "="*60)
    print("STEP 2: Using Device ID")
    print("="*60)
    device_id = "d7a2448c70762e9235aca7"  # Havells Room Light
    device_name = "Room Light - Havells"
    print(f"[TARGET] Testing with device: {device_name} (ID: {device_id})")

    # Step 3: Test commands
    print("\n" + "="*60)
    print("STEP 3: Testing Light Commands")
    print("="*60)

    # Test 1: Turn ON
    print("\n[TEST 1] Turn light ON")
    api.send_commands(device_id, [
        {"code": "switch_led", "value": True}
    ])
    time.sleep(2)

    # Test 2: Set brightness to 50% (500/1000)
    print("\n[TEST 2] Set brightness to 50%")
    api.send_commands(device_id, [
        {"code": "bright_value_v2", "value": 500}
    ])
    time.sleep(2)

    # Test 3: Set to WHITE mode with warm temperature
    print("\n[TEST 3] Set to WHITE mode - Warm (temp=800)")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "white"},
        {"code": "temp_value_v2", "value": 800},
        {"code": "bright_value_v2", "value": 700}
    ])
    time.sleep(3)

    # Test 4: Set to WHITE mode with cool temperature
    print("\n[TEST 4] Set to WHITE mode - Cool (temp=200)")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "white"},
        {"code": "temp_value_v2", "value": 200},
        {"code": "bright_value_v2", "value": 700}
    ])
    time.sleep(3)

    # Test 5: Set to COLOR mode - Red
    print("\n[TEST 5] Set to COLOR mode - Red")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 0, "s": 1000, "v": 1000}}
    ])
    time.sleep(3)

    # Test 6: Set to COLOR mode - Blue
    print("\n[TEST 6] Set to COLOR mode - Blue")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 240, "s": 1000, "v": 1000}}
    ])
    time.sleep(3)

    # Test 7: Set to COLOR mode - Green
    print("\n[TEST 7] Set to COLOR mode - Green")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 120, "s": 1000, "v": 1000}}
    ])
    time.sleep(3)

    # Test 8: Set to COLOR mode - Purple
    print("\n[TEST 8] Set to COLOR mode - Purple")
    api.send_commands(device_id, [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {"h": 280, "s": 1000, "v": 1000}}
    ])
    time.sleep(3)

    # Test 9: Brightness to maximum
    print("\n[TEST 9] Set brightness to 100%")
    api.send_commands(device_id, [
        {"code": "bright_value_v2", "value": 1000}
    ])
    time.sleep(2)

    # Test 10: Brightness to minimum
    print("\n[TEST 10] Set brightness to 10% (minimum)")
    api.send_commands(device_id, [
        {"code": "bright_value_v2", "value": 100}
    ])
    time.sleep(2)

    # Test 11: Turn OFF
    print("\n[TEST 11] Turn light OFF")
    api.send_commands(device_id, [
        {"code": "switch_led", "value": False}
    ])

    print("\n" + "="*60)
    print("[COMPLETE] ALL TESTS COMPLETED!")
    print("="*60)


if __name__ == "__main__":
    test_light_control()
