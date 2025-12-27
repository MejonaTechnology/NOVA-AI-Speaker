#ifndef CONFIG_H
#define CONFIG_H

// ============== WiFi Configuration ==============
#define WIFI_SSID "HOME"
#define WIFI_PASSWORD "96089608"

// ============== Backend Server ==============
#define BACKEND_HOST "nova.mejona.com"  // OCI Domain
#define BACKEND_PORT 80  // HTTP (Nginx Proxy > Python 8000)
#define USE_HTTPS false
#define VOICE_ENDPOINT "/voice"

// ============== INMP441 Microphone (I2S Input) ==============
#define MIC_I2S_NUM         I2S_NUM_1
#define MIC_I2S_SCK         42
#define MIC_I2S_WS          41
#define MIC_I2S_SD          2

// ============== MAX98357 Speaker (I2S Output) ==============
#define SPK_I2S_NUM         I2S_NUM_0
#define SPK_I2S_BCLK        12
#define SPK_I2S_LRC         13
#define SPK_I2S_DIN         14

// ============== Audio Settings ==============
#define SAMPLE_RATE         16000
#define BITS_PER_SAMPLE     16
#define RECORD_SECONDS      30  // Maximum recording duration (30 seconds)
#define I2S_BUFFER_SIZE     1024

// ============== Silence Detection ==============
#define SILENCE_THRESHOLD       300    // Audio level threshold (lower = more sensitive)
#define SILENCE_DURATION_MS     3000   // 3 seconds of silence to stop recording
#define MIN_RECORD_DURATION_MS  1000   // Minimum 1 second recording

// Calculated values
#define RECORD_BUFFER_SIZE  (SAMPLE_RATE * RECORD_SECONDS * (BITS_PER_SAMPLE / 8))

// ============== RGB LED ==============
#define RGB_LED_PIN         48
#define NUM_LEDS            1

// ============== OLED Display (I2C) ==============
#define OLED_SDA            21
#define OLED_SCL            20
#define OLED_WIDTH          128
#define OLED_HEIGHT         64
#define OLED_RESET          -1  // No reset pin (use -1)
#define OLED_ADDRESS        0x3C  // Common I2C address (0x3C or 0x3D)

#endif // CONFIG_H
