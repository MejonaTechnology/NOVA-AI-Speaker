# WiFi Optimization Guide for NOVA AI Speaker

## Problem: Audio Lag During Playback

If you're experiencing choppy or laggy audio during NOVA's responses, it's usually caused by **slow or congested WiFi**.

## Quick Fixes (Ordered by Effectiveness)

### 1. Move ESP32 Closer to WiFi Router ⭐⭐⭐⭐⭐
**Most effective solution!**
- Place ESP32 within **5-10 meters** of your WiFi router
- Avoid walls, metal objects, or microwaves between ESP32 and router
- Check Serial Monitor for RSSI (signal strength):
  - **-50 dBm or better** = Excellent (no lag)
  - **-50 to -60 dBm** = Good (minimal lag)
  - **-60 to -70 dBm** = Fair (some lag possible)
  - **Below -70 dBm** = Weak (will cause lag!)

### 2. Use 2.4 GHz WiFi (Not 5 GHz) ⭐⭐⭐⭐
- ESP32 only supports **2.4 GHz WiFi**
- 2.4 GHz has **better range** through walls
- Make sure your router's 2.4 GHz band is enabled
- Use a strong password (WPA2) for better performance

### 3. Reduce WiFi Congestion ⭐⭐⭐⭐
**Change WiFi channel to avoid interference:**
- Download WiFi analyzer app on your phone:
  - Android: "WiFi Analyzer" (free)
  - iOS: "Network Analyzer" (free)
- Find the **least crowded channel** (1, 6, or 11 recommended)
- Change router's WiFi channel in router settings
- Avoid channels used by neighbors

### 4. Disconnect Other Devices ⭐⭐⭐
- Temporarily disconnect devices using WiFi (phones, laptops, smart TVs)
- Pause downloads/streaming on other devices
- This frees up bandwidth for NOVA

### 5. Restart Your Router ⭐⭐
- Unplug router for 30 seconds
- Plug back in and wait 2 minutes for full restart
- Reconnect ESP32 to WiFi

### 6. Use Quality of Service (QoS) ⭐⭐
**If your router supports QoS:**
- Access router settings (usually http://192.168.1.1)
- Enable QoS and prioritize ESP32's IP address
- This gives NOVA priority over other devices

## Advanced Optimizations (Already Implemented in Code)

### ✅ WiFi Power Save Disabled
```cpp
WiFi.setSleep(false);
```
- Prevents WiFi chip from sleeping
- Reduces latency from ~100ms to ~5ms
- **Already enabled in your firmware!**

### ✅ Maximum TX Power
```cpp
WiFi.setTxPower(WIFI_POWER_19_5dBm);
```
- Boosts WiFi transmission power to maximum (19.5 dBm)
- Improves signal strength and reduces packet loss
- **Added in latest firmware update!**

### ✅ WiFi Diagnostics
- Serial Monitor now shows:
  - Signal strength (RSSI)
  - WiFi channel
  - Signal quality warnings
- **Check Serial Monitor on boot to diagnose issues!**

## How to Check WiFi Signal Quality

1. **Upload firmware** with new WiFi diagnostics
2. **Open Serial Monitor** (115200 baud)
3. **Reboot ESP32** (press reset button)
4. **Look for WiFi diagnostics:**
   ```
   [WIFI] Connected to: YourNetwork
   [WIFI] IP Address: 192.168.1.100
   [WIFI] Power Save Mode: DISABLED (High Performance)
   [WIFI] TX Power: MAXIMUM (19.5 dBm) - Reduces lag
   [WIFI] Signal Strength (RSSI): -55 dBm
   [WIFI] Channel: 6
   [WIFI] Signal Quality: GOOD
   ```

5. **Interpret RSSI:**
   - **-50 dBm or better**: Excellent - No action needed
   - **-50 to -60 dBm**: Good - Should work fine
   - **-60 to -70 dBm**: Fair - Move closer to router
   - **Below -70 dBm**: Weak - MUST move closer to router

## Why Audio Lags (Technical Explanation)

### The Problem:
1. ESP32 sends **96 KB of audio** to backend (~3 seconds recording)
2. Backend processes and returns **~200-500 KB of audio response**
3. ESP32 **streams audio** in real-time while downloading
4. **Slow WiFi** = Download pauses = Audio stutters/lags

### Audio Streaming Process:
```
Backend → WiFi → ESP32 Buffer → I2S Speaker
  ↓         ↓         ↓              ↓
500KB    Slow?   16KB DMA      Real-time
         (lag)   (smooth)      playback
```

If WiFi is slower than playback speed (16kHz × 2 bytes = 32 KB/s), the buffer empties and audio pauses.

## Bandwidth Requirements

**Minimum WiFi speed needed:**
- **Recording upload:** 96 KB ÷ 3s = 32 KB/s = **256 Kbps**
- **Audio playback:** ~400 KB ÷ 10s = 40 KB/s = **320 Kbps**
- **Total required:** ~**600 Kbps minimum**

Most WiFi routers support **54 Mbps** (54,000 Kbps), so bandwidth is rarely the issue - **signal quality** and **congestion** are the real problems.

## Troubleshooting Steps

### Step 1: Check Serial Monitor
Upload new firmware and check RSSI value. If below -70 dBm, move closer to router.

### Step 2: Test WiFi Speed
- On your phone/laptop, move to ESP32's location
- Run speed test: https://fast.com
- Should see **>5 Mbps** download speed
- If slower, router is the problem

### Step 3: Reduce Interference
- Move ESP32 away from:
  - Microwave ovens (big interference!)
  - Bluetooth devices
  - Baby monitors
  - Cordless phones (2.4 GHz)
  - Metal shelves/cabinets

### Step 4: Test Different WiFi Networks
- Use your phone as WiFi hotspot
- Connect ESP32 to phone's hotspot
- Test if audio lag improves
- If yes, router/network is the issue

### Step 5: Check Router Settings
- Access router admin panel
- **WiFi Mode:** Set to "802.11n only" (faster than b/g/n mixed)
- **Channel Width:** Set to "20 MHz" (more stable than 40 MHz)
- **Channel:** Set to 1, 6, or 11 (avoid auto)
- **Band:** Ensure 2.4 GHz is enabled and strong

## Backend Optimization (Future Enhancement)

If WiFi optimization doesn't help, consider backend optimizations:

### Option 1: Audio Compression
Compress audio before sending (MP3/Opus instead of raw PCM):
- Current: 400 KB PCM audio
- Compressed: ~50 KB MP3 (8x smaller!)
- Requires MP3 decoder on ESP32 (more CPU usage)

### Option 2: CDN/Caching
Deploy backend closer to your location:
- Current: OCI India (Bangalore)
- Add: CDN with edge locations
- Reduces network latency

### Option 3: Reduce Audio Quality
Lower audio quality for faster streaming:
- Current: 16 kHz, 16-bit stereo
- Option: 16 kHz, 16-bit mono (50% smaller)
- Option: 8 kHz, 16-bit mono (75% smaller)

## Expected Performance After Optimization

With good WiFi signal (-50 to -60 dBm):
- **Recording time:** ~3 seconds (user speaking)
- **Upload time:** ~1-2 seconds
- **Backend processing:** ~3-5 seconds (Whisper + LLM + TTS)
- **Download time:** ~2-3 seconds (streaming starts immediately)
- **Total response time:** ~8-12 seconds

Audio should play **smoothly without stuttering** once download starts.

## Summary

**Best Solutions (in order):**
1. ⭐⭐⭐⭐⭐ Move ESP32 closer to WiFi router
2. ⭐⭐⭐⭐ Change WiFi channel to avoid congestion
3. ⭐⭐⭐⭐ Use 2.4 GHz WiFi (not 5 GHz)
4. ⭐⭐⭐ Disconnect other WiFi devices temporarily
5. ⭐⭐ Restart WiFi router

**Already Optimized in Code:**
- ✅ WiFi power save disabled
- ✅ Maximum TX power enabled
- ✅ WiFi diagnostics added
- ✅ DMA buffer optimization

**Check Serial Monitor** to see WiFi signal quality and take action accordingly!

---

**Last Updated:** 2025-12-29
**Firmware Version:** v2.1 (WiFi Optimization)
