/*
 * Fire TV Stick Controller for ESP32 - Bluetooth HID Version
 * 
 * ESP32 acts as a Bluetooth keyboard that Fire TV pairs with.
 * Much simpler than ADB - no authentication issues!
 * 
 * Usage:
 * 1. Upload this firmware
 * 2. On Fire TV: Settings → Controllers → Add Bluetooth Device
 * 3. Select "NOVA Remote" and pair
 * 4. Done! Say "Hey Nova, go home" etc.
 */

#ifndef FIRESTICK_BLE_H
#define FIRESTICK_BLE_H

#include <BleKeyboard.h>
#include "config.h"

// Create BLE Keyboard instance
// Name shown when pairing with Fire TV
BleKeyboard bleKeyboard("NOVA Remote", "Mejona", 100);

// Track connection state
bool bleInitialized = false;
bool wasConnected = false;

// Initialize Bluetooth keyboard
void initFirestickBLE() {
    if (!FIRESTICK_ENABLED) {
        Serial.println("[FIRESTICK-BLE] Disabled in config");
        return;
    }
    
    Serial.println("[FIRESTICK-BLE] Initializing Bluetooth keyboard...");
    bleKeyboard.begin();
    bleInitialized = true;
    Serial.println("[FIRESTICK-BLE] Ready! Pair with 'NOVA Remote' on Fire TV");
}

// Check and report connection status
void checkFirestickConnection() {
    if (!bleInitialized) return;
    
    bool isConnected = bleKeyboard.isConnected();
    
    if (isConnected && !wasConnected) {
        Serial.println("[FIRESTICK-BLE] ✅ Connected to Fire TV!");
    } else if (!isConnected && wasConnected) {
        Serial.println("[FIRESTICK-BLE] ❌ Disconnected from Fire TV");
    }
    
    wasConnected = isConnected;
}

// Send keypress
bool sendKey(uint8_t key) {
    if (!bleInitialized || !bleKeyboard.isConnected()) {
        Serial.println("[FIRESTICK-BLE] Not connected to Fire TV");
        return false;
    }
    
    bleKeyboard.write(key);
    delay(50);  // Small delay between key events
    return true;
}

// Send media key (media keys are const MediaKeyReport)
bool sendMediaKey(const MediaKeyReport key) {
    if (!bleInitialized || !bleKeyboard.isConnected()) {
        Serial.println("[FIRESTICK-BLE] Not connected to Fire TV");
        return false;
    }
    
    bleKeyboard.write(key);
    delay(50);
    return true;
}

// Fire TV specific actions
class FirestickBLEController {
public:
    // Navigation
    bool home() {
        Serial.println("[FIRESTICK-BLE] Sending: HOME");
        // Fire TV responds to ESC as back, for home we use WWW_HOME
        return sendMediaKey(KEY_MEDIA_WWW_HOME);
    }
    
    bool back() {
        Serial.println("[FIRESTICK-BLE] Sending: BACK");
        return sendKey(KEY_ESC);
    }
    
    bool up() {
        Serial.println("[FIRESTICK-BLE] Sending: UP");
        return sendKey(KEY_UP_ARROW);
    }
    
    bool down() {
        Serial.println("[FIRESTICK-BLE] Sending: DOWN");
        return sendKey(KEY_DOWN_ARROW);
    }
    
    bool left() {
        Serial.println("[FIRESTICK-BLE] Sending: LEFT");
        return sendKey(KEY_LEFT_ARROW);
    }
    
    bool right() {
        Serial.println("[FIRESTICK-BLE] Sending: RIGHT");
        return sendKey(KEY_RIGHT_ARROW);
    }
    
    bool select() {
        Serial.println("[FIRESTICK-BLE] Sending: SELECT");
        return sendKey(KEY_RETURN);
    }
    
    bool menu() {
        Serial.println("[FIRESTICK-BLE] Sending: MENU");
        return sendKey(0xED);  // Consumer menu key
    }
    
    // Playback controls (library only has play/pause toggle)
    bool play() {
        Serial.println("[FIRESTICK-BLE] Sending: PLAY (toggle)");
        return sendMediaKey(KEY_MEDIA_PLAY_PAUSE);
    }
    
    bool pause() {
        Serial.println("[FIRESTICK-BLE] Sending: PAUSE (toggle)");
        return sendMediaKey(KEY_MEDIA_PLAY_PAUSE);
    }
    
    bool playPause() {
        Serial.println("[FIRESTICK-BLE] Sending: PLAY/PAUSE");
        return sendMediaKey(KEY_MEDIA_PLAY_PAUSE);
    }
    
    bool stop() {
        Serial.println("[FIRESTICK-BLE] Sending: STOP");
        return sendMediaKey(KEY_MEDIA_STOP);
    }
    
    bool next() {
        Serial.println("[FIRESTICK-BLE] Sending: NEXT");
        return sendMediaKey(KEY_MEDIA_NEXT_TRACK);
    }
    
    bool previous() {
        Serial.println("[FIRESTICK-BLE] Sending: PREVIOUS");
        return sendMediaKey(KEY_MEDIA_PREVIOUS_TRACK);
    }
    
    bool fastForward() {
        Serial.println("[FIRESTICK-BLE] Sending: FAST FORWARD");
        // Fire TV uses right arrow held or specific key
        sendKey(KEY_RIGHT_ARROW);
        delay(500);
        return true;
    }
    
    bool rewind() {
        Serial.println("[FIRESTICK-BLE] Sending: REWIND");
        sendKey(KEY_LEFT_ARROW);
        delay(500);
        return true;
    }
    
    // Volume controls
    bool volumeUp() {
        Serial.println("[FIRESTICK-BLE] Sending: VOLUME UP");
        return sendMediaKey(KEY_MEDIA_VOLUME_UP);
    }
    
    bool volumeDown() {
        Serial.println("[FIRESTICK-BLE] Sending: VOLUME DOWN");
        return sendMediaKey(KEY_MEDIA_VOLUME_DOWN);
    }
    
    bool mute() {
        Serial.println("[FIRESTICK-BLE] Sending: MUTE");
        return sendMediaKey(KEY_MEDIA_MUTE);
    }
    
    // App launch - Navigate using voice search or shortcuts
    // Note: Direct app launch requires going through Fire TV's interface
    // For now, we'll go home and user can navigate
    bool openApp(const char* appName) {
        Serial.printf("[FIRESTICK-BLE] App launch requested: %s\n", appName);
        Serial.println("[FIRESTICK-BLE] Note: Going home - navigate to app from there");
        return home();
    }
};

// Global instance
FirestickBLEController firestickBLE;

// Execute command by name (called from main.cpp)
bool executeFirestickCommand(const char* command) {
    if (!FIRESTICK_ENABLED) {
        Serial.println("[FIRESTICK-BLE] Disabled");
        return false;
    }
    
    if (!bleInitialized) {
        initFirestickBLE();
        delay(100);
    }
    
    if (!bleKeyboard.isConnected()) {
        Serial.println("[FIRESTICK-BLE] Not paired with Fire TV!");
        Serial.println("[FIRESTICK-BLE] Go to Fire TV Settings → Controllers → Add Bluetooth Device");
        Serial.println("[FIRESTICK-BLE] Then select 'NOVA Remote'");
        return false;
    }
    
    String cmd = String(command);
    cmd.toLowerCase();
    
    Serial.printf("[FIRESTICK-BLE] Executing: %s\n", command);
    
    // Navigation
    if (cmd == "home") return firestickBLE.home();
    if (cmd == "back") return firestickBLE.back();
    if (cmd == "up") return firestickBLE.up();
    if (cmd == "down") return firestickBLE.down();
    if (cmd == "left") return firestickBLE.left();
    if (cmd == "right") return firestickBLE.right();
    if (cmd == "select" || cmd == "ok" || cmd == "enter") return firestickBLE.select();
    if (cmd == "menu") return firestickBLE.menu();
    
    // Playback
    if (cmd == "play" || cmd == "resume") return firestickBLE.play();
    if (cmd == "pause") return firestickBLE.pause();
    if (cmd == "playpause" || cmd == "play_pause") return firestickBLE.playPause();
    if (cmd == "stop") return firestickBLE.stop();
    if (cmd == "next") return firestickBLE.next();
    if (cmd == "previous" || cmd == "prev") return firestickBLE.previous();
    if (cmd == "rewind" || cmd == "backward") return firestickBLE.rewind();
    if (cmd == "forward" || cmd == "fastforward" || cmd == "fast_forward") return firestickBLE.fastForward();
    
    // Volume
    if (cmd == "volume_up" || cmd == "volumeup" || cmd == "louder") return firestickBLE.volumeUp();
    if (cmd == "volume_down" || cmd == "volumedown" || cmd == "quieter") return firestickBLE.volumeDown();
    if (cmd == "mute") return firestickBLE.mute();
    
    // Apps (go home for now - user navigates from there)
    if (cmd == "netflix" || cmd == "youtube" || cmd == "prime" || cmd == "hotstar" || cmd == "spotify") {
        Serial.printf("[FIRESTICK-BLE] App '%s' requested - going home\n", command);
        return firestickBLE.home();
    }
    
    Serial.printf("[FIRESTICK-BLE] Unknown command: %s\n", command);
    return false;
}

#endif // FIRESTICK_BLE_H
