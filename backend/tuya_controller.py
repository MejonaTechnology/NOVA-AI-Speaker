"""
Tuya Smart Light Controller for NOVA AI
Handles authentication and command execution for Tuya devices
"""

import time
import hashlib
import hmac
import json
import requests
import os


class TuyaOpenAPI:
    def __init__(self, endpoint, access_id, access_secret):
        self.endpoint = endpoint
        self.access_id = access_id
        self.access_secret = access_secret
        self.access_token = None
        self.token_expiry = 0

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
        """Get access token from Tuya (cached for 2 hours)"""
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expiry:
            return True

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
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                self.access_token = result['result']['access_token']
                # Token expires in 2 hours, refresh 5 mins before
                self.token_expiry = time.time() + (2 * 60 * 60) - (5 * 60)
                print(f"[TUYA] Access token obtained")
                return True
            else:
                print(f"[TUYA] Failed to get token: {result}")
                return False
        else:
            print(f"[TUYA] HTTP Error: {response.status_code} - {response.text}")
            return False

    def send_commands(self, device_id, commands, retry=True):
        """Send commands to a device with automatic token refresh on failure"""
        # Force fresh token if current token is expired or doesn't exist
        if not self.access_token or time.time() >= self.token_expiry:
            # Invalidate old token to force fresh authentication
            self.access_token = None
            self.token_expiry = 0
            if not self.get_access_token():
                print("[TUYA] Failed to get access token")
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
        response = requests.post(url, headers=headers, data=body, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"[TUYA] Command sent successfully")
                return True
            else:
                # Check if token is invalid (error code 1010 or 1004)
                error_code = result.get('code')
                if retry and error_code in [1004, 1010]:
                    print(f"[TUYA] Token invalid (code {error_code}), refreshing and retrying...")
                    # Force token refresh
                    self.access_token = None
                    self.token_expiry = 0
                    if self.get_access_token():
                        # Retry the command once with new token
                        return self.send_commands(device_id, commands, retry=False)

                print(f"[TUYA] Command failed: {result}")
                return False
        else:
            print(f"[TUYA] HTTP Error: {response.status_code} - {response.text}")
            return False


class SmartLightController:
    """High-level controller for smart lights with natural language commands"""

    def __init__(self):
        # Tuya credentials
        self.api = TuyaOpenAPI(
            endpoint="https://openapi.tuyain.com",
            access_id=os.getenv("TUYA_ACCESS_ID", "hqs4w54j7jaduwse8nec"),
            access_secret=os.getenv("TUYA_ACCESS_SECRET", "cecbd09a8b5846539319e042d9210583")
        )
        self.device_id = "d7a2448c70762e9235aca7"  # Bedroom light

        # State tracking
        self.is_on = False  # Track on/off state
        self.current_mode = "white"  # "white" or "colour"
        self.current_color_name = "white"  # Track actual color name for UI
        self.current_brightness = 70  # 0-100 percent
        self.current_color_hsv = {"h": 240, "s": 1000, "v": 700}  # Default blue

        # Color mappings (HSV values - h and s only, v is set by brightness)
        self.colors = {
            "red": {"h": 0, "s": 1000},
            "orange": {"h": 30, "s": 1000},
            "yellow": {"h": 60, "s": 1000},
            "green": {"h": 120, "s": 1000},
            "cyan": {"h": 180, "s": 1000},
            "blue": {"h": 240, "s": 1000},
            "purple": {"h": 280, "s": 1000},
            "pink": {"h": 320, "s": 1000},
            "white": None  # Use white mode instead
        }

    def turn_on(self):
        """Turn light ON"""
        result = self.api.send_commands(self.device_id, [
            {"code": "switch_led", "value": True}
        ])
        if result:
            self.is_on = True
        return result

    def turn_off(self):
        """Turn light OFF"""
        result = self.api.send_commands(self.device_id, [
            {"code": "switch_led", "value": False}
        ])
        if result:
            self.is_on = False
        return result

    def set_brightness(self, percent):
        """Set brightness (0-100%) - works for both white and color modes"""
        # Store brightness
        self.current_brightness = max(0, min(100, percent))

        # Convert percent to Tuya range (10-1000)
        value = max(10, min(1000, int(self.current_brightness * 10)))

        if self.current_mode == "colour":
            # In color mode, brightness is controlled by 'v' in colour_data_v2
            self.current_color_hsv["v"] = value
            return self.api.send_commands(self.device_id, [
                {"code": "work_mode", "value": "colour"},
                {"code": "colour_data_v2", "value": self.current_color_hsv}
            ])
        else:
            # In white mode, use bright_value_v2
            return self.api.send_commands(self.device_id, [
                {"code": "bright_value_v2", "value": value}
            ])

    def set_color(self, color_name):
        """Set color by name (red, blue, green, etc.)"""
        color_name = color_name.lower()

        if color_name == "white" or color_name == "warm" or color_name == "cool":
            # Use white mode
            self.current_mode = "white"
            self.current_color_name = color_name  # Track actual selection
            temp_value = 1000  # Default to Cool White (1000)
            if color_name == "warm":
                temp_value = 0  # Warmest (0)
            elif color_name == "cool":
                temp_value = 1000  # Coolest (1000)

            # Use current brightness for white mode
            brightness_value = max(10, min(1000, int(self.current_brightness * 10)))

            return self.api.send_commands(self.device_id, [
                {"code": "work_mode", "value": "white"},
                {"code": "temp_value_v2", "value": temp_value},
                {"code": "bright_value_v2", "value": brightness_value}
            ])
        elif color_name in self.colors:
            # Use color mode
            self.current_mode = "colour"
            self.current_color_name = color_name  # Track actual selection

            # Get h and s from color map, use current brightness for v
            color_hs = self.colors[color_name]
            brightness_value = max(10, min(1000, int(self.current_brightness * 10)))

            # Update current color HSV
            self.current_color_hsv = {
                "h": color_hs["h"],
                "s": color_hs["s"],
                "v": brightness_value
            }

            return self.api.send_commands(self.device_id, [
                {"code": "work_mode", "value": "colour"},
                {"code": "colour_data_v2", "value": self.current_color_hsv}
            ])
        else:
            print(f"[TUYA] Unknown color: {color_name}")
            return False


# Global instance
light_controller = SmartLightController()
