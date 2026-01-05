# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NOVA AI Voice Assistant** is a conversational AI girlfriend assistant running on ESP32-S3 hardware with wake word detection, voice interaction, and dual backend implementations (Python/FastAPI and Go).

### Hardware Architecture
- **MCU**: ESP32-S3 DevKit (16MB Flash, PSRAM enabled)
- **Microphone**: INMP441 I2S digital microphone (16kHz sampling)
- **Speaker**: MAX98357A I2S amplifier
- **Visual Feedback**: WS2812B RGB LED (NeoPixel)
- **Wake Word**: Edge Impulse ML model for on-device detection
- **Control**: GPIO 4 mute button with 3s press for power-off

### System Architecture

```
ESP32-S3 (Firmware)
    ↓ Wake Word Detection (Edge Impulse)
    ↓ Records 3s audio (16kHz, 16-bit PCM)
    ↓ HTTP POST /voice
    ↓
Backend (nova.mejona.com:80)
    ↓ Nginx Proxy → FastAPI (port 8000) or Go (port 8001)
    ↓ Groq Whisper (STT)
    ↓ Groq Llama 4 Maverick 17B (LLM) - latest conversational AI
    ↓ Groq Orpheus v1 (TTS) with edge-tts and gTTS fallback
    ↓ Returns PCM audio (16kHz, 16-bit, stereo)
    ↓
ESP32-S3 plays response through I2S speaker
```

## Quick Start

### First Time Setup
1. **Firmware Build**: `pio run` (builds for `esp32s3` environment)
2. **Backend Setup**: `cd backend && pip install -r requirements.txt`
3. **Environment Config**: Create `backend/.env` with `GROQ_API_KEY`, `TUYA_ACCESS_ID`, `TUYA_ACCESS_SECRET`
4. **Device Upload**: `pio run --target upload` and monitor with `pio device monitor`

### Key Files to Know
- **Main Firmware**: `src/main.cpp` (41KB, ~1500 lines - wake word detection loop and I2S audio)
- **Hardware Config**: `src/config.h` (pin definitions and settings)
- **Backend Server**: `backend/main.py` (31KB - FastAPI voice endpoint)
- **Tuya Integration**: `backend/tuya_controller.py` (smart light control)
- **Firestick Control**: `backend/firestick_controller.py` (ADB-based TV control)

## Development Commands

### ESP32 Firmware (PlatformIO)

```bash
# Standard workflow
pio run                           # Build firmware
pio run --target upload           # Upload to device
pio device monitor                # Monitor serial output (115200 baud)
pio run --target clean            # Clean build artifacts

# Combined operations
pio run --target upload && pio device monitor    # Upload + Monitor
pio run --target clean && pio run --target upload && pio device monitor  # Full rebuild
```

**Important PlatformIO Notes:**
- Board: `esp32-s3-devkitc-1` with 16MB flash
- Framework: Arduino for ESP32
- Monitor baud: 115200, Upload speed: 921600
- PSRAM enabled with cache fix (`-mfix-esp32-psram-cache-issue`)
- Partition: `huge_app.csv` for large firmware with Edge Impulse model
- Environment: `esp32s3` (standard upload) or `esp32s3-ota` (wireless OTA)

### Python Backend (FastAPI)

```bash
cd backend

# Development
pip install -r requirements.txt
export GROQ_API_KEY="your-groq-api-key"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker
docker-compose up -d                # Start with docker-compose
docker-compose logs -f              # View logs
docker-compose down                 # Stop services
docker build -t nova-ai-backend .   # Manual build (no cache)
```

### Go Backend (Alternative Implementation)

```bash
cd backend-go

go mod download
go run main.go
go build -o nova-ai-backend
docker build -t nova-ai-backend-go .
docker run -p 8001:8001 --env-file .env nova-ai-backend-go
```

## Testing & Validation

### Backend Testing

```bash
cd backend

# Test Tuya smart light integration
python test_tuya.py                 # Test API connectivity and commands
python test_tuya_curl.py            # CURL-based Tuya API testing

# Test AI marker generation (for light control)
python test_ai_prompt.py            # Verify [LIGHT_ON], [LIGHT_COLOR:*] markers

# Test Firestick TV control
python test_firestick.py            # ADB connection and control commands

# Test backend light control end-to-end
python test_backend_light.py        # Backend integration test
./test_backend_light.sh             # Shell wrapper for testing

# Manual endpoint testing (local server)
ffmpeg -f alsa -i hw:0 -t 3 -ar 16000 -ac 1 -f s16le test.pcm
curl -X POST http://localhost:8000/voice --data-binary @test.pcm --output response.pcm
ffplay -f s16le -ar 16000 -ac 1 response.pcm
```

### Firmware Debugging

**Serial Monitor Output Format**:
- `[WIFI]` - WiFi connection status
- `[MIC]` - Microphone initialization and audio levels
- `[SPK]` - Speaker initialization and playback
- `[WAKE]` - Wake word detection events and confidence scores
- `[REC]` - Audio recording duration and silence detection
- `[HTTP]` - Backend requests and responses
- `[PLAY]` - Audio streaming and playback progress

## Configuration

### ESP32 Configuration (`src/config.h`)

**WiFi Settings:**
```cpp
#define WIFI_SSID "your-network"
#define WIFI_PASSWORD "your-password"
```

**Backend Server:**
```cpp
#define BACKEND_HOST "nova.mejona.com"
#define BACKEND_PORT 80
#define USE_HTTPS false
#define VOICE_ENDPOINT "/voice"
```

**Hardware Pins:**
- **INMP441 Microphone**: SCK=42, WS=41, SD=2
- **MAX98357 Speaker**: BCLK=12, LRC=13, DIN=14
- **RGB LED**: GPIO 48
- **Mute Button**: GPIO 4

**Audio Settings**:
- Sample Rate: 16kHz (required for Groq APIs and Edge Impulse model)
- Bit Depth: 16-bit PCM
- Max Recording: 30 seconds (auto-stops on silence)
- **Wake Word Detection** (lines 14-20 in main.cpp):
  - Confidence: 0.92 (92% threshold - strict to prevent false triggers)
  - Confidence Gap: 0.30 (30% - Nova must exceed noise/unknown by 30%)
  - Consecutive Detections: 1 (responsive, single detection triggers)
  - Noise Gate: 200 (minimum audio level to process)
- **Silence Detection**:
  - Threshold: 200 (audio level for silence, accounts for background noise)
  - Duration: 1000ms (1 second of silence stops recording)
  - Minimum Recording: 1500ms (1.5 seconds minimum for transcription accuracy)

### Backend Environment Variables (`.env`)

Both Python and Go backends require:
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxx
TUYA_ACCESS_ID=your_tuya_access_id
TUYA_ACCESS_SECRET=your_tuya_access_secret
```

**Groq API Services Used:**
- **STT**: `whisper-large-v3-turbo` (16kHz audio transcription)
- **LLM**: `meta-llama/llama-4-maverick-17b-128e-instruct` (Llama 4 Maverick - latest conversational AI)
- **TTS**: `canopylabs/orpheus-v1-english` (voice: autumn - female, natural Indian accent)
- **Fallback TTS**: Google gTTS (free text-to-speech alternative)

**Tuya Smart Home Integration:**
- Controls smart lights via Tuya Cloud API
- Automatic token refresh every 90 minutes
- Device ID configured in `backend/tuya_controller.py`

**Firestick TV Control:**
- Controls Amazon Firestick via ADB (Android Debug Bridge)
- Requires ADB debugging enabled on Firestick
- Firestick IP configured in `backend/firestick_controller.py`
- Supports playback, navigation, app launching, volume, and power control

## Architecture Details

### ESP32 Firmware Flow (`src/main.cpp`)

1. **Initialization**:
   - Setup I2S microphone (16kHz, mono, 16-bit)
   - Setup I2S speaker (16kHz, stereo, 16-bit)
   - Initialize RGB LED (NeoPixel)
   - Connect to WiFi
   - Initialize Edge Impulse wake word model

2. **Wake Word Detection Loop**:
   - Continuously sample microphone at 16kHz
   - Feed samples to Edge Impulse classifier
   - Detect "Hey Nova" or custom wake word (confidence > 0.91)
   - Visual feedback: LED turns green on detection

3. **Voice Interaction**:
   - Play listening beep (880Hz + 1100Hz ping)
   - Record 3 seconds of audio with 3x gain boost
   - POST raw PCM to backend `/voice` endpoint
   - Stream response audio directly to I2S speaker
   - LED indicates status (green=listening, blue=processing, cyan=playing)

4. **Button Control**:
   - GPIO 4 button press toggles mute
   - Muted state disables wake word detection

### Backend Implementation (Python/Go)

**API Endpoint**: `POST /voice`
- **Input**: Raw PCM audio (16kHz, 16-bit, mono)
- **Output**: Raw PCM audio (16kHz, 16-bit, stereo for ESP32)

**Processing Pipeline**:
1. Convert PCM → WAV for Groq Whisper API
2. Transcribe audio using Whisper (language: English)
3. Generate response using Llama 3.3 70B with personality prompt
4. **Process light control commands** (extract markers like `[LIGHT_ON]`, `[LIGHT_COLOR:blue]`)
5. **Execute Tuya API commands** if light control markers detected
6. Synthesize speech using Orpheus TTS (with Edge TTS fallback)
7. Convert WAV → PCM (16kHz stereo) and return to ESP32

**AI Personality** (SYSTEM_PROMPT):
- NOVA: Indian girlfriend personality
- Hinglish responses (Hindi + English mix)
- Expression tags for emotional TTS: `<giggle>`, `<chuckle>`, `<think>`, `<sigh>`
- Concise responses (1-2 sentences for faster playback)

### Audio Processing Details

**ESP32 Audio Handling**:
- Recording buffer: 96KB (3 seconds × 16kHz × 2 bytes)
- Microphone gain: 3x amplification applied during recording
- Playback: Streamed directly from HTTP response to I2S
- PSRAM usage: Audio buffering for large responses

**Backend Audio Processing**:
- **Python**: Uses `wave` module and `pydub` for audio conversion
- **Go**: Manual PCM↔WAV conversion with binary encoding
- **Format**: 16kHz sample rate for compatibility with Groq APIs
- **Fallback**: gTTS generates MP3, converted to WAV via ffmpeg

### Edge Impulse Wake Word

**Library**: `lib/ei-wake-word/test-new_inferencing/`
- Pre-trained wake word detection model
- Runs on-device (no cloud required)
- Configured for ESP32-S3 with PSRAM
- Inference callback: `microphoneCallback()` feeds live audio

**Detection Logic**:
- Requires consecutive detections above threshold
- Confidence threshold: 0.75 (75%, configurable in `WAKE_WORD_CONFIDENCE`)
- Confidence gap: 0.20 (20%, Nova score must be 20% higher than noise/unknown)
- Consecutive detections: 1 (responsive triggering, configurable in `CONSECUTIVE_DETECTIONS`)
- Noise gate: 100 (minimum audio level to process, reduces false positives)

## Deployment Architecture

### Production Server (OCI - nova.mejona.com)

**Nginx Configuration** (`backend/nginx-nova.conf`):
```nginx
server {
    listen 80;
    server_name nova.mejona.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_buffering off;  # Critical for audio streaming
    }
}
```

**Docker Deployment**:
- Python backend runs in Docker container (port 8000)
- Go backend can run as alternative (port 8001)
- Nginx reverse proxy handles external traffic on port 80
- Health checks ensure service availability

## Code Structure

### ESP32 Firmware (`src/`)
```
src/
├── main.cpp              # Main firmware logic
│   ├── WiFi connection
│   ├── I2S audio setup (mic + speaker)
│   ├── Wake word detection loop
│   ├── Audio recording with gain
│   ├── HTTP communication with backend
│   └── Audio playback streaming
└── config.h              # Hardware pins and settings
```

### Python Backend (`backend/`)
```
backend/
├── main.py               # FastAPI server
│   ├── /voice endpoint (POST)
│   ├── PCM→WAV conversion
│   ├── Groq STT/LLM/TTS pipeline
│   └── Error handling with gTTS fallback
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container image
├── docker-compose.yml    # Orchestration config
└── nginx-nova.conf       # Nginx proxy config
```

### Go Backend (`backend-go/`)
```
backend-go/
├── main.go               # Go HTTP server
│   ├── /voice handler
│   ├── Audio format conversion
│   ├── Groq API integration
│   └── gTTS fallback via shell
├── go.mod               # Go module definition
└── Dockerfile           # Multi-stage build
```

### Edge Impulse Library (`lib/ei-wake-word/`)
Pre-built Edge Impulse SDK with wake word model (not typically modified)

### Tuya Smart Home (`backend/tuya_controller.py`)
```
backend/
├── tuya_controller.py    # Tuya API integration
│   ├── TuyaOpenAPI class (authentication, token management)
│   ├── SmartLightController (high-level commands)
│   └── Automatic token refresh (every 90 minutes)
├── test_tuya.py          # API testing script
└── test_ai_prompt.py     # AI marker generation testing
```

### Firestick TV Control (`backend/firestick_controller.py`)
```
backend/
├── firestick_controller.py    # Firestick ADB integration
│   ├── FirestickController class (ADB connection and commands)
│   ├── execute_firestick_command() helper function
│   └── Support for playback, navigation, apps, volume, power
├── test_firestick.py          # Firestick testing script
└── FIRESTICK_SETUP.md         # Complete setup guide
```

## Development Notes

### ESP32 Memory Considerations
- **PSRAM Required**: Wake word model + audio buffers need external PSRAM
- **Partition Scheme**: `huge_app.csv` allows large firmware (>2MB)
- **Heap Management**: Use `malloc`/`free` for audio buffers
- **Stack Size**: Edge Impulse requires sufficient stack for inference

### Audio Quality Tips
- **16kHz Sample Rate**: Critical for both wake word model and Groq APIs
- **Recording Gain**: 3x amplification compensates for quiet INMP441
- **I2S Buffer Sizes**: Larger DMA buffers (16×1024) improve stability
- **Speaker Playback**: Streaming directly from HTTP prevents memory issues
- **APLL Configuration**: APLL disabled for speaker (`use_apll = false`) - fixes 2x playback speed issue
- **Stereo Output**: Backend sends stereo PCM (left/right channels duplicated) for MAX98357A compatibility

### WiFi Performance Optimizations
Critical settings in `src/main.cpp` (lines 348-380):
- **Power Save**: Disabled (`WiFi.setSleep(false)`) for ultra-low latency
- **TX Power**: Maximum 19.5dBm (`WiFi.setTxPower(WIFI_POWER_19_5dBm)`) for stronger signal
- **Auto-Reconnect**: Enabled (`WiFi.setAutoReconnect(true)`) to reduce disconnections
- **Persistent Mode**: Disabled (`WiFi.persistent(false)`) for faster reconnection without flash writes
- **ESP-IDF Power Save**: None (`esp_wifi_set_ps(WIFI_PS_NONE)`) for consistent performance

### Debugging Commands

**ESP32 Serial Monitor**:
- `[WIFI]` - WiFi connection status
- `[MIC]` - Microphone initialization
- `[SPK]` - Speaker initialization
- `[WAKE]` - Wake word detection events
- `[REC]` - Audio recording status
- `[HTTP]` - Backend communication
- `[PLAY]` - Audio playback progress

**Backend Logs**:
- `[RECV]` - Received audio size
- `[STT]` - Transcription results
- `[LLM]` - AI response generation
- `[TTS]` - Speech synthesis status
- `[AUDIO]` - Audio processing details

### Common Development Tasks

**Changing Wake Word**:
1. Train new model on Edge Impulse platform with your audio samples
2. Export C++ library for Arduino ESP32
3. Replace `lib/ei-wake-word/test-new_inferencing/` directory
4. Update `WAKE_WORD_CONFIDENCE` threshold in `src/main.cpp` (line 16, currently 0.92)
5. Rebuild and test: `pio run --target upload && pio device monitor`

**Modifying AI Personality** (Hinglish girlfriend assistant):
- Edit `SYSTEM_PROMPT` in `backend/main.py` lines 50-120
- Add emotion tags like `<giggle>`, `<think>`, `<sigh>` for TTS expression
- Keep responses concise (1-2 sentences) for faster playback
- Test with: `python test_ai_prompt.py` to verify output format

**Adding Light Control Commands**:
1. AI must generate `[LIGHT_ON]`, `[LIGHT_OFF]`, `[LIGHT_COLOR:*]`, `[LIGHT_BRIGHTNESS:*]` markers
2. Backend main.py extracts markers and calls `light_controller.execute_command()`
3. Tuya API converts to actual device commands
4. Test: `python test_ai_prompt.py` then `python test_backend_light.py`

**Testing Tuya Light Control**:
```bash
cd backend

# Test Tuya API directly
python test_tuya.py

# Test AI marker generation
python test_ai_prompt.py

# Manual API testing with curl (see backend/CURL_EXAMPLES.md)
```

**Light Control Commands** (voice commands):
- "Turn on the light" → `[LIGHT_ON]`
- "Turn off the light" → `[LIGHT_OFF]`
- "Make it blue" → `[LIGHT_COLOR:blue]`
- "Set brightness to 50%" → `[LIGHT_BRIGHTNESS:50]`
- "Turn on blue light" → `[LIGHT_ON] [LIGHT_COLOR:blue]`
- Supported colors: red, blue, green, purple, pink, yellow, orange, cyan, white, warm, cool

**Testing Firestick TV Control**:
```bash
cd backend

# Install ADB first (if not already installed)
# Windows: Download platform tools from developer.android.com
# Linux: sudo apt install adb

# Configure Firestick IP in firestick_controller.py
# Edit line ~264: FIRESTICK_IP = "192.168.1.100"

# Enable ADB debugging on Firestick:
# Settings → My Fire TV → Developer Options → ADB Debugging

# Test connection
python test_firestick.py

# Expected output:
# ✅ PASS: Connected to Firestick successfully
# ✅ PASS: Navigation, Playback, Apps, Volume tests
```

**Firestick Control Commands** (voice commands):
- "Open Netflix" → `[FIRESTICK:netflix]`
- "Launch YouTube" → `[FIRESTICK:youtube]`
- "Play" / "Resume" → `[FIRESTICK:play]`
- "Pause" → `[FIRESTICK:pause]`
- "Go home" → `[FIRESTICK:home]`
- "Go back" → `[FIRESTICK:back]`
- "Volume up" → `[FIRESTICK:volume_up]`
- "Mute" → `[FIRESTICK:mute]`
- "Turn off TV" → `[FIRESTICK:sleep]`
- See `backend/FIRESTICK_SETUP.md` for complete command list

**Testing Backend Locally**:
```bash
# Record 3s test audio
ffmpeg -f alsa -i hw:0 -t 3 -ar 16000 -ac 1 -f s16le test.pcm

# Test endpoint
curl -X POST http://localhost:8000/voice \
  --data-binary @test.pcm \
  --output response.pcm

# Play response
ffplay -f s16le -ar 16000 -ac 1 response.pcm
```

**Updating Firmware OTA**:
Currently uses USB upload. For OTA updates, add ESP32 OTA library and implement update endpoint.

## Recent Fixes & Known Improvements

### Critical Issues Resolved (Recent Commits)

**Audio Playback** (commit d00e2fa):
- ✅ Fixed 2x playback speed issue: APLL disabled for speaker (`use_apll = false`)
- ✅ Fixed silence detection causing premature recording stops
- ✅ Removed 3x microphone gain for better natural quality

**Wake Word Detection** (commit 95a85aa, 98ad2e6):
- ✅ Changed to single detection (1 consecutive detection) for responsiveness
- ✅ Increased confidence threshold to 0.92 to prevent false triggers
- ✅ Model is poorly trained → strict thresholds compensate for this

**Backend Services** (commit 0cf0222):
- ✅ Switched to Llama 4 Maverick 17B for latest conversational AI
- ✅ Implemented automatic Groq rate limit handling
- ✅ Added gTTS/edge-tts fallback for TTS

**Dependencies** (commit 97c55d0):
- ✅ Pinned numpy<2 to prevent breaking changes
- ✅ Added adbutils for Firestick control
- ✅ Installed platform-tools for ADB on Windows

### Current Implementation Status

**✅ Fully Working**:
- Wake word detection ("Hey Nova") with LED feedback
- Voice recording with automatic silence detection
- Groq STT/LLM/TTS pipeline
- Tuya smart light control with [LIGHT_*] markers
- Firestick TV control with [FIRESTICK:*] markers
- Conversation history (6 exchanges max)
- Audio streaming without buffering issues
- WiFi reconnection with optimized power settings

**⚠️ Known Limitations**:
- Wake word model is poorly trained (requires strict thresholds)
- OTA firmware updates not yet implemented (USB upload only)
- Go backend included but not actively maintained (Python is primary)
- Single device context (no multi-user support)

## Performance Characteristics

- **Wake Word Latency**: ~100ms inference time on ESP32-S3
- **Network Latency**: ~1-2s (depends on WiFi + internet)
- **Backend Processing**: ~3-5s (Whisper + LLM + TTS)
- **Total Response Time**: ~5-8s from wake word to audio playback
- **Memory Usage**: ~120KB PSRAM for audio buffers

## Troubleshooting

**"Microphone not working"**:
- Check I2S pin connections (SCK=42, WS=41, SD=2)
- Verify INMP441 VDD is 3.3V, GND connected, L/R to GND
- Monitor serial for `[MIC] Microphone initialized`

**"Speaker crackling/distortion"**:
- Ensure 16kHz sample rate matches on both recording/playback
- Check MAX98357 gain setting (onboard jumpers)
- Increase DMA buffer sizes if streaming issues occur

**"Wake word not detecting"**:
- Adjust `WAKE_WORD_CONFIDENCE` (lower = more sensitive)
- Train custom model with your voice samples
- Check microphone gain is adequate

**"Backend timeout errors"**:
- Increase HTTPClient timeout: `http.setTimeout(30000)`
- Check internet connectivity and DNS resolution
- Verify Groq API key is valid and has credits

**"Out of memory errors"**:
- Enable PSRAM in platformio.ini (already configured)
- Use streaming audio playback instead of buffering
- Free audio buffers after use

**"Audio playing at 2x speed (too fast)"**:
- APLL should be disabled for speaker in `setupSpeaker()` function
- Verify `use_apll = false` in speaker I2S configuration (line 200 in main.cpp)
- Backend should send stereo PCM (left/right channels duplicated)

**"Light control not working"**:
- Verify Tuya credentials in `.env` file
- Check backend logs for `[TUYA]` messages
- Test Tuya API directly with `python backend/test_tuya.py`
- Verify AI is generating markers with `python backend/test_ai_prompt.py`
- Check device ID matches in `backend/tuya_controller.py`

**"Firestick control not working"**:
- Verify ADB is installed: `adb version`
- Check Firestick IP is correct in `backend/firestick_controller.py`
- Enable ADB debugging on Firestick (Settings → My Fire TV → Developer Options)
- Test connection: `adb connect FIRESTICK_IP:5555`
- Check backend logs for `[FIRESTICK]` messages
- Test Firestick API with `python backend/test_firestick.py`
- Ensure Firestick and server are on same network
- Firewall may block ADB port 5555 (temporarily disable to test)
- Restart Firestick if connection fails persistently

## Git Workflow

### Commit Message Format

Project uses **conventional commits** with type prefixes:
- `fix(component):` - Bug fixes (e.g., `fix(audio): Fix silence detection`)
- `feat(component):` - New features (e.g., `feat(tuya): Add light control`)
- `docs:` - Documentation updates
- `refactor(component):` - Code improvements without behavior change
- `perf:` - Performance optimizations

Components include: `audio`, `wake-word`, `backend`, `wifi`, `tuya`, `firestick`, `ai`

### Before Committing

1. **Firmware Changes**: `pio run` (ensure build succeeds)
2. **Backend Changes**: Test with `uvicorn main:app --port 8000` locally
3. **API Contract Changes**: Update both firmware AND backend together
4. **Testing**: Run relevant test scripts from `backend/test_*.py` suite

### Recent Work Context

Last 5 commits focus on:
1. **Dependencies Fix** (97c55d0): numpy pinning, adb, firestick path
2. **Firestick Integration** (72ec3fc): Missing controller dependency
3. **/text Endpoint** (0360139): ESP32 serial command/volume control
4. **Wake Word Tuning** (95a85aa): Single detection for responsiveness
5. **Audio Improvements** (98ad2e6): Flaky model workarounds with strict thresholds

## Deployment to Production (OCI Server)

### Backend Deployment via SSH

**Server Details**:
- Host: `nova.mejona.com` (161.118.184.207)
- SSH Key: `D:\Mejona Workspace\Product\Home-Assistant\oci_key_new`
- User: `ubuntu`
- Backend Directory: `~/nova-ai-backend`

**Deploy Updated Backend**:
```bash
# SSH into server
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207

# Navigate to backend directory
cd ~/nova-ai-backend

# Pull latest code (if using git)
git pull

# Rebuild Docker image (no cache for fresh build)
sudo docker build --no-cache -t nova-backend .

# Stop and remove old container
sudo docker stop nova-ai-backend
sudo docker rm nova-ai-backend

# Start new container
sudo docker run -d --name nova-ai-backend -p 8000:8000 --env-file .env nova-backend

# Check logs
sudo docker logs -f nova-ai-backend

# Verify it's running
curl http://localhost:8000
```

**Check Backend Status**:
```bash
# List running containers
sudo docker ps -a | grep nova

# View logs
sudo docker logs nova-ai-backend

# Restart container if needed
sudo docker restart nova-ai-backend
```

### Important Deployment Notes
- Environment variables (`.env`) must be present on server with Groq + Tuya credentials
- Nginx proxy configuration in `/etc/nginx/sites-available/nova.mejona.com`
- Server runs Docker containers for easy updates and isolation
- Backend auto-initializes Tuya token and weather monitoring on startup
