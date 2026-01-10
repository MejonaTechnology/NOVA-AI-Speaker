#ifndef CONFIG_H
#define CONFIG_H

// ============== WiFi Configuration ==============
#define WIFI_SSID           "HOME"
#define WIFI_PASSWORD       "96089608"
#define WIFI_SSID_BACKUP    "Mr Raj"
#define WIFI_PASSWORD_BACKUP "pass-9608"

// ============== Backend Server ==============
#define BACKEND_HOST        "nova.mejona.com"
#define BACKEND_PORT        80
#define USE_HTTPS           false
#define VOICE_ENDPOINT      "/voice"

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
#define RECORD_SECONDS      30
#define I2S_BUFFER_SIZE     1024

// ============== Silence Detection ==============
#define SILENCE_THRESHOLD       200
#define SILENCE_DURATION_MS     1000
#define MIN_RECORD_DURATION_MS  1500

// Calculated values
#define RECORD_BUFFER_SIZE  (SAMPLE_RATE * RECORD_SECONDS * (BITS_PER_SAMPLE / 8))

// ============== RGB LED ==============
#define RGB_LED_PIN         48
#define NUM_LEDS            1

// ============== Button ==============
#define BUTTON_PIN          4

#endif // CONFIG_H
