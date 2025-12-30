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
    ↓ Groq Llama 3.3 70B (LLM)
    ↓ Groq Orpheus v1 (TTS) with gTTS fallback
    ↓ Returns PCM audio (16kHz, 16-bit)
    ↓
ESP32-S3 plays response through I2S speaker
```

## Development Commands

### ESP32 Firmware (PlatformIO)

```bash
# Build firmware
pio run

# Upload to ESP32-S3
pio run --target upload

# Monitor serial output
pio device monitor

# Clean build
pio run --target clean

# Build + Upload + Monitor (full workflow)
pio run --target upload && pio device monitor
```

**Important PlatformIO Notes:**
- Board: `esp32-s3-devkitc-1` with 16MB flash
- Framework: Arduino for ESP32
- Monitor baud: 115200
- Upload speed: 921600
- PSRAM enabled with cache fix (`-mfix-esp32-psram-cache-issue`)
- Partition: `huge_app.csv` for large firmware with Edge Impulse model

### Python Backend (FastAPI)

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export GROQ_API_KEY="your-groq-api-key"

# Run development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker build and run
docker build -t nova-ai-backend .
docker run -p 8000:8000 --env-file .env nova-ai-backend

# Docker Compose
docker-compose up -d
docker-compose logs -f
docker-compose down
```

### Go Backend (Alternative Implementation)

```bash
cd backend-go

# Install dependencies
go mod download

# Run development server
go run main.go

# Build binary
go build -o nova-ai-backend

# Docker build
docker build -t nova-ai-backend-go .
docker run -p 8001:8001 --env-file .env nova-ai-backend-go
```

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

**Audio Settings:**
- Sample Rate: 16kHz (both recording and playback)
- Bit Depth: 16-bit PCM
- Recording Duration: 3 seconds
- Wake Word Confidence: 0.75 (75%)
- Confidence Gap: 0.20 (20% higher than noise/unknown)
- Consecutive Detections: 1 (responsive triggering)

### Backend Environment Variables (`.env`)

Both Python and Go backends require:
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxx
TUYA_ACCESS_ID=your_tuya_access_id
TUYA_ACCESS_SECRET=your_tuya_access_secret
```

**Groq API Services Used:**
- **STT**: `whisper-large-v3-turbo` (16kHz audio)
- **LLM**: `llama-3.3-70b-versatile` (conversational AI)
- **TTS**: `canopylabs/orpheus-v1-english` (voice: diana - female, natural)
- **Fallback TTS**: Edge TTS (Microsoft Azure TTS, free alternative)

**Tuya Smart Home Integration:**
- Controls smart lights via Tuya Cloud API
- Automatic token refresh every 90 minutes
- Device ID configured in `backend/tuya_controller.py`

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
1. Train new model on Edge Impulse platform
2. Export for Arduino
3. Replace `lib/ei-wake-word/` with new library
4. Adjust `WAKE_WORD_CONFIDENCE` if needed

**Modifying AI Personality**:
Edit `SYSTEM_PROMPT` in `backend/main.py` (Python) or `backend-go/main.go` (Go)

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

## Git Workflow

Recent commits show the project uses:
- Descriptive commit messages with type prefixes: `fix(audio):`, `feat:`, etc.
- Domain naming migration (localhost → nova.mejona.com)
- Sample rate standardization (consolidated to 16kHz)

When committing:
- Test firmware builds with `pio run` before commit
- Verify backend with `uvicorn` or `go run`
- Include both firmware and backend changes if API contract changed
- Use conventional commit format: `fix(audio):`, `feat(tuya):`, `docs:`, etc.

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
