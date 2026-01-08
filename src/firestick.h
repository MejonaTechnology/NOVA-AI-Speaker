/*
 * Fire TV Stick Controller for ESP32
 * Simplified ADB TCP client for sending key events and launching apps
 * 
 * Works because ESP32 is on the same network as Fire TV!
 */

#ifndef FIRESTICK_H
#define FIRESTICK_H

#include <WiFi.h>
#include "config.h"

// ADB Protocol Constants
#define ADB_VERSION         0x01000000
#define ADB_MAXDATA         256 * 1024

// ADB Command Types
#define A_SYNC              0x434e5953  // "SYNC"
#define A_CNXN              0x4e584e43  // "CNXN" - Connect
#define A_OPEN              0x4e45504f  // "OPEN" - Open stream
#define A_OKAY              0x59414b4f  // "OKAY"
#define A_CLSE              0x45534c43  // "CLSE" - Close
#define A_WRTE              0x45545257  // "WRTE" - Write

// Key codes for Fire TV
#define KEYCODE_HOME        3
#define KEYCODE_BACK        4
#define KEYCODE_DPAD_UP     19
#define KEYCODE_DPAD_DOWN   20
#define KEYCODE_DPAD_LEFT   21
#define KEYCODE_DPAD_RIGHT  22
#define KEYCODE_DPAD_CENTER 23   // Select/OK
#define KEYCODE_VOLUME_UP   24
#define KEYCODE_VOLUME_DOWN 25
#define KEYCODE_POWER       26
#define KEYCODE_MENU        82
#define KEYCODE_MEDIA_PLAY_PAUSE  85
#define KEYCODE_MEDIA_STOP        86
#define KEYCODE_MEDIA_NEXT        87
#define KEYCODE_MEDIA_PREVIOUS    88
#define KEYCODE_MEDIA_REWIND      89
#define KEYCODE_MEDIA_FAST_FORWARD 90
#define KEYCODE_MUTE        164
#define KEYCODE_MEDIA_PLAY  126
#define KEYCODE_MEDIA_PAUSE 127
#define KEYCODE_SLEEP       223
#define KEYCODE_WAKEUP      224

// App Package Names
#define PKG_NETFLIX         "com.netflix.ninja"
#define PKG_YOUTUBE         "com.amazon.firetv.youtube"
#define PKG_PRIME_VIDEO     "com.amazon.avod.thirdpartyclient"
#define PKG_HOTSTAR         "in.startv.hotstar"
#define PKG_SPOTIFY         "com.spotify.tv.android"

class FirestickController {
private:
    WiFiClient client;
    bool connected = false;
    uint32_t localId = 1;
    
    // Simple ADB message structure (simplified)
    struct AdbMessage {
        uint32_t command;
        uint32_t arg0;
        uint32_t arg1;
        uint32_t data_length;
        uint32_t data_check;
        uint32_t magic;
    };
    
    uint32_t calculateChecksum(const uint8_t* data, size_t length) {
        uint32_t sum = 0;
        for (size_t i = 0; i < length; i++) {
            sum += data[i];
        }
        return sum;
    }
    
    bool sendMessage(uint32_t command, uint32_t arg0, uint32_t arg1, const char* data = nullptr) {
        AdbMessage msg;
        size_t dataLen = data ? strlen(data) : 0;
        
        msg.command = command;
        msg.arg0 = arg0;
        msg.arg1 = arg1;
        msg.data_length = dataLen;
        msg.data_check = data ? calculateChecksum((const uint8_t*)data, dataLen) : 0;
        msg.magic = command ^ 0xFFFFFFFF;
        
        // Send header
        if (client.write((uint8_t*)&msg, sizeof(msg)) != sizeof(msg)) {
            return false;
        }
        
        // Send data if present
        if (data && dataLen > 0) {
            if (client.write((uint8_t*)data, dataLen) != dataLen) {
                return false;
            }
        }
        
        return true;
    }
    
    bool waitForOkay(int timeout_ms = 5000) {
        unsigned long start = millis();
        while (millis() - start < timeout_ms) {
            if (client.available() >= sizeof(AdbMessage)) {
                AdbMessage response;
                client.read((uint8_t*)&response, sizeof(response));
                
                // Skip data if any
                if (response.data_length > 0) {
                    uint8_t buf[256];
                    size_t toRead = min((size_t)response.data_length, sizeof(buf));
                    client.read(buf, toRead);
                }
                
                if (response.command == A_OKAY) {
                    return true;
                }
            }
            delay(10);
        }
        return false;
    }

public:
    bool connect() {
        if (!FIRESTICK_ENABLED) {
            Serial.println("[FIRESTICK] Disabled in config");
            return false;
        }
        
        Serial.printf("[FIRESTICK] Connecting to %s:%d...\n", FIRESTICK_IP, FIRESTICK_PORT);
        
        if (!client.connect(FIRESTICK_IP, FIRESTICK_PORT)) {
            Serial.println("[FIRESTICK] Connection failed!");
            return false;
        }
        
        // Send CNXN (connect) message
        // Format: "host::features=..." 
        const char* banner = "host::\0";
        if (!sendMessage(A_CNXN, ADB_VERSION, ADB_MAXDATA, banner)) {
            Serial.println("[FIRESTICK] Failed to send CNXN");
            client.stop();
            return false;
        }
        
        // Wait for response (AUTH or CNXN)
        // Note: Fire TV may require authentication which we skip for simplicity
        // ADB debugging must be enabled and trusted on Fire TV
        delay(100);
        
        if (client.available() > 0) {
            connected = true;
            Serial.println("[FIRESTICK] Connected!");
            return true;
        }
        
        // Even without response, try to proceed
        connected = true;
        Serial.println("[FIRESTICK] Connected (no handshake response)");
        return true;
    }
    
    void disconnect() {
        if (client.connected()) {
            client.stop();
        }
        connected = false;
    }
    
    bool sendShellCommand(const char* command) {
        if (!connected && !connect()) {
            return false;
        }
        
        Serial.printf("[FIRESTICK] Shell: %s\n", command);
        
        // Open shell stream
        String shellCmd = String("shell:") + command;
        localId++;
        
        if (!sendMessage(A_OPEN, localId, 0, shellCmd.c_str())) {
            Serial.println("[FIRESTICK] Failed to open shell");
            disconnect();
            return false;
        }
        
        // Wait for response
        delay(200);
        
        // Read any response (not critical for key events)
        while (client.available() > 0) {
            client.read();
        }
        
        return true;
    }
    
    bool sendKeyEvent(int keycode) {
        char cmd[64];
        snprintf(cmd, sizeof(cmd), "input keyevent %d", keycode);
        return sendShellCommand(cmd);
    }
    
    bool launchApp(const char* packageName) {
        char cmd[128];
        snprintf(cmd, sizeof(cmd), "monkey -p %s -c android.intent.category.LAUNCHER 1", packageName);
        return sendShellCommand(cmd);
    }
    
    // Convenience methods
    bool home() { return sendKeyEvent(KEYCODE_HOME); }
    bool back() { return sendKeyEvent(KEYCODE_BACK); }
    bool up() { return sendKeyEvent(KEYCODE_DPAD_UP); }
    bool down() { return sendKeyEvent(KEYCODE_DPAD_DOWN); }
    bool left() { return sendKeyEvent(KEYCODE_DPAD_LEFT); }
    bool right() { return sendKeyEvent(KEYCODE_DPAD_RIGHT); }
    bool select() { return sendKeyEvent(KEYCODE_DPAD_CENTER); }
    bool play() { return sendKeyEvent(KEYCODE_MEDIA_PLAY); }
    bool pause() { return sendKeyEvent(KEYCODE_MEDIA_PAUSE); }
    bool playPause() { return sendKeyEvent(KEYCODE_MEDIA_PLAY_PAUSE); }
    bool stop() { return sendKeyEvent(KEYCODE_MEDIA_STOP); }
    bool next() { return sendKeyEvent(KEYCODE_MEDIA_NEXT); }
    bool previous() { return sendKeyEvent(KEYCODE_MEDIA_PREVIOUS); }
    bool rewind() { return sendKeyEvent(KEYCODE_MEDIA_REWIND); }
    bool fastForward() { return sendKeyEvent(KEYCODE_MEDIA_FAST_FORWARD); }
    bool volumeUp() { return sendKeyEvent(KEYCODE_VOLUME_UP); }
    bool volumeDown() { return sendKeyEvent(KEYCODE_VOLUME_DOWN); }
    bool mute() { return sendKeyEvent(KEYCODE_MUTE); }
    bool sleep() { return sendKeyEvent(KEYCODE_SLEEP); }
    bool wakeup() { return sendKeyEvent(KEYCODE_WAKEUP); }
    
    // App launchers
    bool openNetflix() { return launchApp(PKG_NETFLIX); }
    bool openYouTube() { return launchApp(PKG_YOUTUBE); }
    bool openPrimeVideo() { return launchApp(PKG_PRIME_VIDEO); }
    bool openHotstar() { return launchApp(PKG_HOTSTAR); }
    bool openSpotify() { return launchApp(PKG_SPOTIFY); }
};

// Global instance
FirestickController firestick;

// Execute command by name (called from main.cpp)
bool executeFirestickCommand(const char* command) {
    if (!FIRESTICK_ENABLED) {
        return false;
    }
    
    String cmd = String(command);
    cmd.toLowerCase();
    
    Serial.printf("[FIRESTICK] Executing: %s\n", command);
    
    // Navigation
    if (cmd == "home") return firestick.home();
    if (cmd == "back") return firestick.back();
    if (cmd == "up") return firestick.up();
    if (cmd == "down") return firestick.down();
    if (cmd == "left") return firestick.left();
    if (cmd == "right") return firestick.right();
    if (cmd == "select" || cmd == "ok" || cmd == "enter") return firestick.select();
    
    // Playback
    if (cmd == "play" || cmd == "resume") return firestick.play();
    if (cmd == "pause") return firestick.pause();
    if (cmd == "playpause" || cmd == "play_pause") return firestick.playPause();
    if (cmd == "stop") return firestick.stop();
    if (cmd == "next") return firestick.next();
    if (cmd == "previous" || cmd == "prev") return firestick.previous();
    if (cmd == "rewind" || cmd == "backward") return firestick.rewind();
    if (cmd == "forward" || cmd == "fastforward" || cmd == "fast_forward") return firestick.fastForward();
    
    // Volume
    if (cmd == "volume_up" || cmd == "volumeup" || cmd == "louder") return firestick.volumeUp();
    if (cmd == "volume_down" || cmd == "volumedown" || cmd == "quieter") return firestick.volumeDown();
    if (cmd == "mute") return firestick.mute();
    
    // Apps
    if (cmd == "netflix") return firestick.openNetflix();
    if (cmd == "youtube") return firestick.openYouTube();
    if (cmd == "prime" || cmd == "prime_video" || cmd == "primevideo") return firestick.openPrimeVideo();
    if (cmd == "hotstar") return firestick.openHotstar();
    if (cmd == "spotify") return firestick.openSpotify();
    
    // Power
    if (cmd == "sleep" || cmd == "off" || cmd == "power_off") return firestick.sleep();
    if (cmd == "wake" || cmd == "wakeup" || cmd == "wake_up" || cmd == "on") return firestick.wakeup();
    
    Serial.printf("[FIRESTICK] Unknown command: %s\n", command);
    return false;
}

#endif // FIRESTICK_H
