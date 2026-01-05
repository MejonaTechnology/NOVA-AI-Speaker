"""
Firestick Controller for NOVA AI
Controls Amazon Firestick via ADB (Android Debug Bridge)
"""

import subprocess
import time
import re
import os

# ADB Configuration
ADB_PATH = r"C:\Users\Mr Raj\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"


class FirestickController:
    def __init__(self, firestick_ip, adb_port=5555):
        """
        Initialize Firestick controller

        Args:
            firestick_ip: IP address of Firestick (e.g., "192.168.1.100")
            adb_port: ADB port (default: 5555)
        """
        self.firestick_ip = firestick_ip
        self.adb_port = adb_port
        self.device = f"{firestick_ip}:{adb_port}"
        self.connected = False

    def _run_adb_command(self, command, timeout=10):
        """Run an ADB command and return output"""
        try:
            # Replace 'adb' with full path to adb.exe
            if os.path.exists(ADB_PATH):
                command = command.replace("adb ", f'"{ADB_PATH}" ', 1)

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip(), result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"[FIRESTICK] Command timeout: {command}")
            return "", False
        except Exception as e:
            print(f"[FIRESTICK] Error running command: {e}")
            return "", False

    def connect(self):
        """Connect to Firestick via ADB"""
        # Disconnect first to ensure clean connection
        self._run_adb_command(f"adb disconnect {self.device}")
        time.sleep(0.5)

        # Connect to Firestick
        output, success = self._run_adb_command(f"adb connect {self.device}")

        if success and ("connected" in output.lower() or "already connected" in output.lower()):
            self.connected = True
            print(f"[FIRESTICK] Connected to {self.device}")
            return True
        else:
            self.connected = False
            print(f"[FIRESTICK] Failed to connect: {output}")
            return False

    def disconnect(self):
        """Disconnect from Firestick"""
        self._run_adb_command(f"adb disconnect {self.device}")
        self.connected = False
        print(f"[FIRESTICK] Disconnected from {self.device}")

    def _send_keyevent(self, keycode):
        """Send a keyevent to Firestick"""
        if not self.connected:
            if not self.connect():
                return False

        output, success = self._run_adb_command(f"adb -s {self.device} shell input keyevent {keycode}")
        if success:
            print(f"[FIRESTICK] Sent keyevent: {keycode}")
            return True
        else:
            print(f"[FIRESTICK] Failed to send keyevent {keycode}: {output}")
            return False

    def _send_text(self, text):
        """Send text input to Firestick"""
        if not self.connected:
            if not self.connect():
                return False

        # Replace spaces with %s for ADB
        text = text.replace(" ", "%s")
        output, success = self._run_adb_command(f"adb -s {self.device} shell input text {text}")
        if success:
            print(f"[FIRESTICK] Sent text: {text}")
            return True
        else:
            print(f"[FIRESTICK] Failed to send text: {output}")
            return False

    # ============== Navigation Controls ==============

    def home(self):
        """Go to home screen"""
        return self._send_keyevent("KEYCODE_HOME")

    def back(self):
        """Go back"""
        return self._send_keyevent("KEYCODE_BACK")

    def up(self):
        """Navigate up"""
        return self._send_keyevent("KEYCODE_DPAD_UP")

    def down(self):
        """Navigate down"""
        return self._send_keyevent("KEYCODE_DPAD_DOWN")

    def left(self):
        """Navigate left"""
        return self._send_keyevent("KEYCODE_DPAD_LEFT")

    def right(self):
        """Navigate right"""
        return self._send_keyevent("KEYCODE_DPAD_RIGHT")

    def select(self):
        """Select/Enter"""
        return self._send_keyevent("KEYCODE_DPAD_CENTER")

    def menu(self):
        """Open menu"""
        return self._send_keyevent("KEYCODE_MENU")

    # ============== Playback Controls ==============

    def play_pause(self):
        """Toggle play/pause"""
        return self._send_keyevent("KEYCODE_MEDIA_PLAY_PAUSE")

    def play(self):
        """Play"""
        return self._send_keyevent("KEYCODE_MEDIA_PLAY")

    def pause(self):
        """Pause"""
        return self._send_keyevent("KEYCODE_MEDIA_PAUSE")

    def stop(self):
        """Stop playback"""
        return self._send_keyevent("KEYCODE_MEDIA_STOP")

    def rewind(self):
        """Rewind"""
        return self._send_keyevent("KEYCODE_MEDIA_REWIND")

    def fast_forward(self):
        """Fast forward"""
        return self._send_keyevent("KEYCODE_MEDIA_FAST_FORWARD")

    def next(self):
        """Next track/episode"""
        return self._send_keyevent("KEYCODE_MEDIA_NEXT")

    def previous(self):
        """Previous track/episode"""
        return self._send_keyevent("KEYCODE_MEDIA_PREVIOUS")

    # ============== Volume Controls ==============

    def volume_up(self):
        """Volume up"""
        return self._send_keyevent("KEYCODE_VOLUME_UP")

    def volume_down(self):
        """Volume down"""
        return self._send_keyevent("KEYCODE_VOLUME_DOWN")

    def mute(self):
        """Mute/Unmute"""
        return self._send_keyevent("KEYCODE_VOLUME_MUTE")

    # ============== App Launching ==============

    def launch_app(self, package_name):
        """Launch an app by package name"""
        if not self.connected:
            if not self.connect():
                return False

        output, success = self._run_adb_command(
            f"adb -s {self.device} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        )
        if success:
            print(f"[FIRESTICK] Launched app: {package_name}")
            return True
        else:
            print(f"[FIRESTICK] Failed to launch app {package_name}: {output}")
            return False

    def launch_netflix(self):
        """Launch Netflix"""
        return self.launch_app("com.netflix.ninja")

    def launch_youtube(self):
        """Launch YouTube"""
        return self.launch_app("com.amazon.firetv.youtube")

    def launch_prime_video(self):
        """Launch Prime Video"""
        return self.launch_app("com.amazon.avod.thirdpartyclient")

    def launch_hotstar(self):
        """Launch Disney+ Hotstar"""
        return self.launch_app("in.startv.hotstar")

    def launch_spotify(self):
        """Launch Spotify"""
        return self.launch_app("com.spotify.tv.android")

    # ============== Search ==============

    def search(self, query):
        """Search for content"""
        # Open search (usually via home button then up)
        self.home()
        time.sleep(0.5)
        self.up()
        time.sleep(0.3)
        self.select()
        time.sleep(0.5)
        return self._send_text(query)

    # ============== Power Controls ==============

    def power_off(self):
        """Put Firestick to sleep"""
        return self._send_keyevent("KEYCODE_SLEEP")

    def wake_up(self):
        """Wake up Firestick"""
        return self._send_keyevent("KEYCODE_WAKEUP")


# ============== Global Controller Instance ==============

# Default Firestick IP (update this to your Firestick's IP)
FIRESTICK_IP = "192.168.31.165"  # Your Firestick IP address

firestick_controller = FirestickController(FIRESTICK_IP)


# ============== Helper Functions ==============

def execute_firestick_command(command):
    """
    Execute a Firestick command

    Args:
        command: Command string (e.g., "play", "pause", "netflix", "home")

    Returns:
        bool: True if successful, False otherwise
    """
    command = command.lower().strip()

    try:
        # Navigation
        if command == "home":
            return firestick_controller.home()
        elif command == "back":
            return firestick_controller.back()
        elif command in ["select", "ok", "enter"]:
            return firestick_controller.select()
        elif command == "up":
            return firestick_controller.up()
        elif command == "down":
            return firestick_controller.down()
        elif command == "left":
            return firestick_controller.left()
        elif command == "right":
            return firestick_controller.right()
        elif command == "menu":
            return firestick_controller.menu()

        # Playback
        elif command in ["play", "resume"]:
            return firestick_controller.play()
        elif command == "pause":
            return firestick_controller.pause()
        elif command in ["play_pause", "playpause"]:
            return firestick_controller.play_pause()
        elif command == "stop":
            return firestick_controller.stop()
        elif command in ["rewind", "backward"]:
            return firestick_controller.rewind()
        elif command in ["forward", "fastforward", "fast_forward"]:
            return firestick_controller.fast_forward()
        elif command == "next":
            return firestick_controller.next()
        elif command in ["previous", "prev"]:
            return firestick_controller.previous()

        # Volume
        elif command in ["volume_up", "volumeup", "louder"]:
            return firestick_controller.volume_up()
        elif command in ["volume_down", "volumedown", "quieter"]:
            return firestick_controller.volume_down()
        elif command == "mute":
            return firestick_controller.mute()

        # Apps
        elif command == "netflix":
            return firestick_controller.launch_netflix()
        elif command == "youtube":
            return firestick_controller.launch_youtube()
        elif command in ["prime", "prime_video", "primevideo"]:
            return firestick_controller.launch_prime_video()
        elif command == "hotstar":
            return firestick_controller.launch_hotstar()
        elif command == "spotify":
            return firestick_controller.launch_spotify()

        # Power
        elif command in ["sleep", "off", "power_off"]:
            return firestick_controller.power_off()
        elif command in ["wake", "wakeup", "wake_up", "on"]:
            return firestick_controller.wake_up()

        else:
            print(f"[FIRESTICK] Unknown command: {command}")
            return False

    except Exception as e:
        print(f"[FIRESTICK] Error executing command '{command}': {e}")
        return False


if __name__ == "__main__":
    # Test the controller
    print("Testing Firestick Controller...")

    # Connect
    if firestick_controller.connect():
        print("✅ Connected successfully")

        # Test home button
        print("\nTesting home button...")
        if firestick_controller.home():
            print("✅ Home button works")

        # Test play/pause
        print("\nTesting play/pause...")
        if firestick_controller.play_pause():
            print("✅ Play/pause works")

        # Disconnect
        firestick_controller.disconnect()
    else:
        print("❌ Failed to connect to Firestick")
        print(f"Make sure:")
        print(f"1. Firestick IP is correct: {FIRESTICK_IP}")
        print(f"2. ADB debugging is enabled on Firestick")
        print(f"3. Firestick is on the same network")
