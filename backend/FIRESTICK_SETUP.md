# Firestick Control Setup Guide

## ✅ Status: FULLY IMPLEMENTED

NOVA AI can now control your Amazon Firestick via voice commands!

## Prerequisites

### 1. Install ADB (Android Debug Bridge)

**Windows:**
1. Download [Platform Tools](https://developer.android.com/studio/releases/platform-tools)
2. Extract to `C:\adb\` or any folder
3. Add folder to PATH environment variable
4. Test: Open CMD and run `adb version`

**Linux/Ubuntu:**
```bash
sudo apt update
sudo apt install adb
adb version
```

**Mac:**
```bash
brew install android-platform-tools
adb version
```

### 2. Enable ADB on Firestick

1. On your Firestick, navigate to:
   - **Settings** → **My Fire TV** → **Developer Options**

2. Enable:
   - **ADB Debugging**: Turn ON
   - **Apps from Unknown Sources**: Turn ON (optional, for app installation)

3. Note your Firestick's IP address:
   - **Settings** → **My Fire TV** → **About** → **Network**
   - Example: `192.168.1.100`

### 3. Configure Firestick IP in Backend

Edit `backend/firestick_controller.py` and update:
```python
# Line ~264
FIRESTICK_IP = "192.168.1.100"  # CHANGE THIS TO YOUR FIRESTICK IP
```

## Testing the Connection

### Test 1: Direct Connection Test
```bash
cd backend

# Test connection
adb connect 192.168.1.100:5555

# You should see: "connected to 192.168.1.100:5555"

# Test home button
adb shell input keyevent KEYCODE_HOME
```

### Test 2: Python Controller Test
```bash
cd backend

# Run the test script
python test_firestick.py

# Expected output:
# ✅ PASS: Connected to Firestick successfully
# ✅ PASS: Navigation controls
# ✅ PASS: Playback controls
# ✅ PASS: App launching
# ✅ PASS: Volume controls
```

### Test 3: Voice Command Test

1. Start the backend:
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Say to NOVA: **"Hey Nova, open Netflix"**
   - Expected: Netflix app launches on Firestick

3. Say: **"Hey Nova, pause"**
   - Expected: Video pauses

## Supported Voice Commands

### Playback Control
- **"Play"** / **"Resume"** → Play/resume video
- **"Pause"** → Pause video
- **"Stop"** → Stop playback
- **"Rewind"** → Rewind video
- **"Fast forward"** → Fast forward video
- **"Next"** → Next episode/track
- **"Previous"** → Previous episode/track

### Navigation
- **"Go home"** → Home screen
- **"Go back"** → Go back
- **"Move up"** / **"Move down"** / **"Move left"** / **"Move right"** → Navigate menu
- **"Select"** / **"OK"** / **"Enter"** → Select item

### App Launching
- **"Open Netflix"** → Launch Netflix
- **"Launch YouTube"** → Launch YouTube
- **"Start Prime Video"** → Launch Prime Video
- **"Open Hotstar"** → Launch Disney+ Hotstar
- **"Open Spotify"** → Launch Spotify

### Volume Control
- **"Volume up"** / **"Louder"** → Increase volume
- **"Volume down"** / **"Quieter"** → Decrease volume
- **"Mute"** → Mute/unmute

### Power Control
- **"Turn off TV"** / **"Sleep"** → Put Firestick to sleep
- **"Wake up TV"** / **"Turn on TV"** → Wake up Firestick

## How It Works

1. **Voice Input**: You say "Hey Nova, open Netflix"
2. **ESP32**: Records your voice and sends to backend
3. **Whisper STT**: Transcribes speech to text
4. **Llama AI**: Generates response with marker: `[FIRESTICK:netflix]`
5. **Backend**: Detects marker and sends ADB command to Firestick
6. **Firestick**: Netflix app launches!
7. **TTS**: NOVA responds "Opening Netflix!"

## Troubleshooting

### "Connection failed"
- **Check Firestick IP**: Ensure IP is correct in `firestick_controller.py`
- **Check network**: Firestick and computer must be on same WiFi
- **Enable ADB**: Verify ADB debugging is enabled on Firestick
- **Firewall**: Disable firewall temporarily to test
- **Restart Firestick**: Reboot and try again

### "Command not working"
- **Test ADB directly**: `adb -s 192.168.1.100:5555 shell input keyevent KEYCODE_HOME`
- **Check connection**: Run `adb devices` to see connected devices
- **Reconnect**: `adb disconnect` then `adb connect IP:5555`

### "App not launching"
- **Verify app installed**: Some apps may not be installed on your Firestick
- **Check package name**: Different regions may have different package names
- **Update controller**: Edit `launch_app()` methods in `firestick_controller.py`

### "Volume not working"
- Volume control depends on your TV/soundbar setup
- Some Firesticks don't support volume control via ADB
- Use physical remote or voice command on Firestick itself

## Adding More Apps

To add more apps, edit `firestick_controller.py`:

1. Find the app's package name:
```bash
adb shell pm list packages | grep appname
```

2. Add a method:
```python
def launch_myapp(self):
    """Launch My App"""
    return self.launch_app("com.myapp.package")
```

3. Add to `execute_firestick_command()`:
```python
elif command == "myapp":
    return firestick_controller.launch_myapp()
```

4. Update `backend/main.py` SYSTEM_PROMPT to include voice command examples

## Common App Package Names

- **Netflix**: `com.netflix.ninja`
- **YouTube**: `com.amazon.firetv.youtube`
- **Prime Video**: `com.amazon.avod.thirdpartyclient`
- **Disney+ Hotstar**: `in.startv.hotstar`
- **Spotify**: `com.spotify.tv.android`
- **Plex**: `com.plexapp.android`
- **VLC**: `org.videolan.vlc`

To find more, run:
```bash
adb shell pm list packages
```

## Performance Notes

- **ADB Latency**: ~200-500ms per command
- **Connection**: Persistent connection maintained
- **Auto-reconnect**: Automatically reconnects if connection drops
- **Timeout**: 10 seconds per command

## Security Notes

- **ADB Debugging**: Only enable when needed (can be security risk)
- **Network**: Keep Firestick on trusted network only
- **Firewall**: Use firewall rules to restrict ADB access
- **Disable when done**: Turn off ADB debugging after testing

## Production Deployment

For OCI server deployment:

1. Install ADB on server:
```bash
ssh ubuntu@nova.mejona.com
sudo apt update
sudo apt install adb
```

2. Update Firestick IP in `firestick_controller.py` (should be same network)

3. Test connection from server:
```bash
adb connect YOUR_FIRESTICK_IP:5555
```

4. Deploy backend with Docker (ADB will be accessible from container)

---

**Last Updated**: 2025-12-31
**Status**: ✅ Production Ready
**Integration**: Fully integrated with NOVA AI voice assistant
