#!/bin/bash
# Test NOVA AI Backend Light Control
# This script tests if the backend properly processes light control commands

echo "============================================================"
echo "  Testing NOVA AI Backend - Light Control Integration"
echo "============================================================"

BACKEND_URL="http://localhost:8000"

echo -e "\nChecking if backend is running..."
curl -s "$BACKEND_URL/" || {
    echo "[ERROR] Backend is not running!"
    echo "Start it with: cd backend && python main.py"
    exit 1
}

echo -e "\n\n[TEST 1] Testing 'Turn on the light' command"
echo "Creating test audio file with silence (simulating user saying 'turn on the light')..."
# Create 3 seconds of silence (16kHz, 16-bit, mono PCM)
dd if=/dev/zero of=test_audio.pcm bs=96000 count=1 2>/dev/null

echo "Sending to backend with simulated 'turn on the light' transcription..."
# We'll need to manually edit the backend to process this, or use Python

echo -e "\n\nNote: For proper testing, we need to use Python to simulate the AI response"
echo "with [LIGHT_ON], [LIGHT_OFF], etc. markers."
echo ""
echo "Let me create a Python test instead..."
