# Tuya Light Control - Curl Testing Examples

## Quick Test Commands

### 1. Turn Light ON
```bash
# Using Python test script (easiest)
python test_tuya_curl.py

# Or test specific command:
python -c "from tuya_controller import light_controller; light_controller.turn_on()"
```

### 2. Turn Light OFF
```bash
python -c "from tuya_controller import light_controller; light_controller.turn_off()"
```

### 3. Set Brightness to 50%
```bash
python -c "from tuya_controller import light_controller; light_controller.set_brightness(50)"
```

### 4. Set Color to BLUE
```bash
python -c "from tuya_controller import light_controller; light_controller.set_color('blue')"
```

### 5. Set Color to RED
```bash
python -c "from tuya_controller import light_controller; light_controller.set_color('red')"
```

### Available Colors
- red, orange, yellow, green, cyan, blue, purple, pink
- white, warm (warm white), cool (cool white)

## Direct Tuya API Curl Examples

### Get Access Token
```bash
# Note: You need to calculate the HMAC-SHA256 signature
# It's easier to use the Python script: python test_tuya_curl.py
```

### Full Test Script
Run the comprehensive test:
```bash
cd backend
python test_tuya_curl.py
```

This will:
1. Get access token
2. Turn light ON
3. Set brightness to 50%
4. Change color to BLUE
5. Change color to RED
6. Turn light OFF

## Backend Integration Test

Test if the NOVA AI backend processes light commands correctly:
```bash
cd backend
python test_backend_light.py
```

This tests the complete pipeline:
- AI response parsing
- Command extraction from [LIGHT_ON], [LIGHT_OFF], etc.
- Tuya API execution
- Text cleanup for TTS

## Troubleshooting

If light control doesn't work:

1. **Check credentials** in `backend/tuya_controller.py`:
   - ACCESS_ID: hqs4w54j7jaduwse8nec
   - ACCESS_SECRET: cecbd09a8b5846539319e042d9210583
   - DEVICE_ID: d7a2448c70762e9235aca7

2. **Verify device is online** in Tuya app

3. **Check network connectivity**:
   ```bash
   ping openapi.tuyain.com
   ```

4. **Test API directly**:
   ```bash
   python test_tuya_curl.py
   ```

5. **Check backend logs** when using voice commands with ESP32

## Status

✅ Tuya API Integration - **WORKING**
✅ Authentication - **WORKING**
✅ Turn ON/OFF - **WORKING**
✅ Brightness Control - **WORKING**
✅ Color Control - **WORKING**
✅ Backend Processing - **WORKING**

Last tested: 2025-12-29
All tests passed successfully!
