#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

// Edge Impulse Wake Word
#include <test-new_inferencing.h>

// ============== Wake Word Configuration ==============
#define WAKE_WORD_CONFIDENCE 0.95f  // Confidence threshold for wake word (higher = more accurate, fewer false positives)
#define CONSECUTIVE_DETECTIONS 1    // Require consecutive detections (1 = faster response)

// ============== Button Configuration ==============
#define BUTTON_PIN 4
bool isMuted = false;

// ============== Global State ==============
bool isRecording = false;
bool isPlaying = false;
int consecutiveWakeDetections = 0;
static bool micReady = false;

// Audio buffers for wake word
static int16_t sampleBuffer[EI_CLASSIFIER_RAW_SAMPLE_COUNT];

// Animation state
unsigned long lastBlinkTime = 0;
unsigned long lastBreathTime = 0;
int breathPhase = 0;  // 0-10 for breathing animation

// ============== NeoPixel Setup ==============
Adafruit_NeoPixel pixels(NUM_LEDS, RGB_LED_PIN, NEO_GRB + NEO_KHZ800);

// ============== OLED Display Setup ==============
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);

// ============== Helper Functions ==============
int hexToDec(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return 0;
}

String urlDecode(String input) {
    String decoded = "";
    char c;
    char code0;
    char code1;
    for (unsigned int i = 0; i < input.length(); i++) {
        c = input.charAt(i);
        if (c == '+') {
            decoded += ' ';
        } else if (c == '%') {
            if (i + 2 < input.length()) {
                code0 = input.charAt(++i);
                code1 = input.charAt(++i);
                c = (hexToDec(code0) << 4) | hexToDec(code1);
                decoded += c;
            }
        } else {
            decoded += c;
        }
    }
    return decoded;
}

void setLedColor(uint8_t r, uint8_t g, uint8_t b) {
    pixels.setPixelColor(0, pixels.Color(r, g, b));
    pixels.show();
}

// ============== I2S Microphone Setup (16kHz for wake word) ==============
void setupMicrophone() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = 16000,  // Wake word model needs 16kHz
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = (i2s_comm_format_t)I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = (int)ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 16,
        .dma_buf_len = 1024,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = MIC_I2S_SCK,
        .ws_io_num = MIC_I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = MIC_I2S_SD
    };

    ESP_ERROR_CHECK(i2s_driver_install(MIC_I2S_NUM, &i2s_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(MIC_I2S_NUM, &pin_config));
    micReady = true;
    Serial.println("[MIC] Microphone initialized (16kHz)");
}

// ============== I2S Speaker Setup (16kHz) ==============
void setupSpeaker() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = (i2s_comm_format_t)I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = (int)ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 16, // Increase DMA buffers for stability
        .dma_buf_len = 1024,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = SPK_I2S_BCLK,
        .ws_io_num = SPK_I2S_LRC,
        .data_out_num = SPK_I2S_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    ESP_ERROR_CHECK(i2s_driver_install(SPK_I2S_NUM, &i2s_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(SPK_I2S_NUM, &pin_config));
    Serial.println("[SPK] Speaker initialized (16kHz)");
}

// ============== OLED Display Functions ==============
void setupOLED() {
    Wire.begin(OLED_SDA, OLED_SCL);

    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
        Serial.println("[OLED] Initialization failed!");
        return;
    }

    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("NOVA AI");
    display.println("Initializing...");
    display.display();
    Serial.println("[OLED] Display initialized");
}

void displayMessage(const char* line1, const char* line2 = "", const char* line3 = "", const char* line4 = "") {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    display.setCursor(0, 0);
    display.println(line1);

    if (strlen(line2) > 0) {
        display.setCursor(0, 16);
        display.println(line2);
    }

    if (strlen(line3) > 0) {
        display.setCursor(0, 32);
        display.println(line3);
    }

    if (strlen(line4) > 0) {
        display.setCursor(0, 48);
        display.println(line4);
    }

    display.display();
}

void displayStatus(const char* status) {
    display.clearDisplay();
    display.setTextSize(2);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 20);
    display.println(status);
    display.display();
}

// ============== Animated Robot Face ==============
void drawRobotFace(int leftEyeHeight, int rightEyeHeight, bool showPupils = true) {
    display.clearDisplay();

    // Face outline (rounded rectangle)
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);

    // Left eye
    int leftEyeX = 35;
    int leftEyeY = 25;
    display.fillCircle(leftEyeX, leftEyeY, 12, SSD1306_WHITE);
    display.fillCircle(leftEyeX, leftEyeY, 10, SSD1306_BLACK);
    if (showPupils && leftEyeHeight > 0) {
        display.fillCircle(leftEyeX, leftEyeY, leftEyeHeight, SSD1306_WHITE);
    }

    // Right eye
    int rightEyeX = 93;
    int rightEyeY = 25;
    display.fillCircle(rightEyeX, rightEyeY, 12, SSD1306_WHITE);
    display.fillCircle(rightEyeX, rightEyeY, 10, SSD1306_BLACK);
    if (showPupils && rightEyeHeight > 0) {
        display.fillCircle(rightEyeX, rightEyeY, rightEyeHeight, SSD1306_WHITE);
    }

    // Mouth (small line)
    display.drawLine(50, 45, 78, 45, SSD1306_WHITE);

    display.display();
}

void displayFaceNormal() {
    drawRobotFace(6, 6, true);  // Normal sized pupils
}

void displayFaceListening() {
    // Animated listening - wider eyes with larger pupils
    for (int i = 0; i < 2; i++) {
        drawRobotFace(8, 8, true);  // Larger pupils (alert)
        delay(200);
        drawRobotFace(6, 6, true);  // Normal pupils
        delay(200);
    }
    drawRobotFace(8, 8, true);  // Stay alert
}

void displayFaceSleeping() {
    display.clearDisplay();

    // Face outline
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);

    // Closed eyes (horizontal lines)
    int leftEyeX = 35;
    int leftEyeY = 25;
    int rightEyeX = 93;
    int rightEyeY = 25;

    // Left eye closed
    display.drawLine(leftEyeX - 8, leftEyeY, leftEyeX + 8, leftEyeY, SSD1306_WHITE);
    display.drawLine(leftEyeX - 6, leftEyeY - 1, leftEyeX + 6, leftEyeY - 1, SSD1306_WHITE);

    // Right eye closed
    display.drawLine(rightEyeX - 8, rightEyeY, rightEyeX + 8, rightEyeY, SSD1306_WHITE);
    display.drawLine(rightEyeX - 6, rightEyeY - 1, rightEyeX + 6, rightEyeY - 1, SSD1306_WHITE);

    // Sleepy mouth (small curve)
    display.drawLine(52, 45, 76, 45, SSD1306_WHITE);

    // "Zzz" sleep indicator
    display.setTextSize(1);
    display.setCursor(95, 10);
    display.print("z");
    display.setCursor(100, 5);
    display.print("Z");

    display.display();
}

void displayFaceProcessing() {
    // Thinking animation - pupils move side to side
    for (int i = 0; i < 2; i++) {
        // Look left
        display.clearDisplay();
        display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);
        display.fillCircle(35, 25, 12, SSD1306_WHITE);
        display.fillCircle(35, 25, 10, SSD1306_BLACK);
        display.fillCircle(32, 25, 5, SSD1306_WHITE);  // Left pupil
        display.fillCircle(93, 25, 12, SSD1306_WHITE);
        display.fillCircle(93, 25, 10, SSD1306_BLACK);
        display.fillCircle(90, 25, 5, SSD1306_WHITE);  // Left pupil
        display.drawLine(50, 45, 78, 45, SSD1306_WHITE);
        display.display();
        delay(250);

        // Look right
        display.clearDisplay();
        display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);
        display.fillCircle(35, 25, 12, SSD1306_WHITE);
        display.fillCircle(35, 25, 10, SSD1306_BLACK);
        display.fillCircle(38, 25, 5, SSD1306_WHITE);  // Right pupil
        display.fillCircle(93, 25, 12, SSD1306_WHITE);
        display.fillCircle(93, 25, 10, SSD1306_BLACK);
        display.fillCircle(96, 25, 5, SSD1306_WHITE);  // Right pupil
        display.drawLine(50, 45, 78, 45, SSD1306_WHITE);
        display.display();
        delay(250);
    }
}

void displayFaceHappy() {
    display.clearDisplay();

    // Face outline
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);

    // Happy eyes (curved up)
    display.fillCircle(35, 25, 12, SSD1306_WHITE);
    display.fillCircle(35, 25, 10, SSD1306_BLACK);
    display.fillCircle(35, 25, 7, SSD1306_WHITE);

    display.fillCircle(93, 25, 12, SSD1306_WHITE);
    display.fillCircle(93, 25, 10, SSD1306_BLACK);
    display.fillCircle(93, 25, 7, SSD1306_WHITE);

    // Smiling mouth (arc)
    display.drawCircle(64, 35, 15, SSD1306_WHITE);
    display.fillRect(10, 5, 108, 35, SSD1306_BLACK);  // Erase top half of circle
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);  // Redraw face

    display.display();
}

// ============== Animated Idle Face (Always Active) ==============
void displayFaceIdleAnimated() {
    // Breathing animation - subtle pupil size changes
    int pupilSize = 5 + (breathPhase / 2);  // Pupil size varies from 5 to 10

    display.clearDisplay();
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);

    // Left eye
    display.fillCircle(35, 25, 12, SSD1306_WHITE);
    display.fillCircle(35, 25, 10, SSD1306_BLACK);
    display.fillCircle(35, 25, pupilSize, SSD1306_WHITE);

    // Right eye
    display.fillCircle(93, 25, 12, SSD1306_WHITE);
    display.fillCircle(93, 25, 10, SSD1306_BLACK);
    display.fillCircle(93, 25, pupilSize, SSD1306_WHITE);

    // Mouth
    display.drawLine(50, 45, 78, 45, SSD1306_WHITE);

    display.display();
}

void blinkAnimation() {
    // Quick blink
    display.clearDisplay();
    display.drawRoundRect(10, 5, 108, 54, 8, SSD1306_WHITE);

    // Closed eyes
    display.drawLine(35 - 8, 25, 35 + 8, 25, SSD1306_WHITE);
    display.drawLine(93 - 8, 25, 93 + 8, 25, SSD1306_WHITE);
    display.drawLine(50, 45, 78, 45, SSD1306_WHITE);

    display.display();
    delay(100);

    // Eyes open again
    displayFaceIdleAnimated();
}

void updateIdleAnimation() {
    unsigned long currentTime = millis();

    // Blink every 3-5 seconds randomly
    if (currentTime - lastBlinkTime > random(3000, 5000)) {
        blinkAnimation();
        lastBlinkTime = currentTime;
    }

    // Breathing animation - update every 200ms
    if (currentTime - lastBreathTime > 200) {
        breathPhase++;
        if (breathPhase > 10) breathPhase = 0;
        displayFaceIdleAnimated();
        lastBreathTime = currentTime;
    }
}

// ============== Sound Effects System ==============
// Alexa-style soothing sound effects for user feedback

void playTone(int frequency, int duration_ms, float volume = 0.3) {
    const int sample_rate = 16000;
    const int num_samples = (sample_rate * duration_ms) / 1000;

    int16_t* samples = (int16_t*)malloc(num_samples * 4); // stereo
    if (!samples) return;

    for (int i = 0; i < num_samples; i++) {
        float t = (float)i / sample_rate;
        int16_t value = (int16_t)(sin(2.0 * M_PI * frequency * t) * 32767 * volume);
        samples[i * 2] = value;      // Left
        samples[i * 2 + 1] = value;  // Right
    }

    size_t bytes_written;
    i2s_write(SPK_I2S_NUM, samples, num_samples * 4, &bytes_written, portMAX_DELAY);
    free(samples);
}

void playMelody(int* frequencies, int* durations, int count, float volume = 0.3) {
    for (int i = 0; i < count; i++) {
        if (frequencies[i] > 0) {
            playTone(frequencies[i], durations[i], volume);
        } else {
            delay(durations[i]); // Rest/pause
        }
    }
}

// Sound effect definitions
void soundStartup() {
    int freq[] = {523, 659, 784};  // C5, E5, G5 (C major chord ascending)
    int dur[] = {150, 150, 300};
    playMelody(freq, dur, 3, 0.2);
}

void soundMute() {
    int freq[] = {880, 440};  // A5 to A4 (descending - going quiet)
    int dur[] = {100, 200};
    playMelody(freq, dur, 2, 0.15);
}

void soundUnmute() {
    int freq[] = {440, 880};  // A4 to A5 (ascending - becoming active)
    int dur[] = {100, 200};
    playMelody(freq, dur, 2, 0.15);
}

void soundListening() {
    int freq[] = {1047};  // C6 (high ping - attention)
    int dur[] = {150};
    playMelody(freq, dur, 1, 0.2);
}

void soundProcessing() {
    int freq[] = {523, 659};  // C5, E5 (gentle pulse - thinking)
    int dur[] = {200, 200};
    playMelody(freq, dur, 2, 0.15);
}

void soundSuccess() {
    int freq[] = {659, 784, 1047};  // E5, G5, C6 (rising - positive)
    int dur[] = {100, 100, 200};
    playMelody(freq, dur, 3, 0.2);
}

void soundError() {
    int freq[] = {392, 330};  // G4, E4 (descending - error)
    int dur[] = {200, 300};
    playMelody(freq, dur, 2, 0.15);
}

// ============== WiFi Connection ==============
void connectWiFi() {
    Serial.print("[WIFI] Connecting to ");
    Serial.println(WIFI_SSID);

    displayMessage("NOVA AI", "Connecting WiFi...");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.print("[WIFI] Connected! IP: ");
        Serial.println(WiFi.localIP());

        displayFaceHappy();  // Show happy face when connected
        delay(2000);
    } else {
        Serial.println("\n[WIFI] Connection failed!");
        displayMessage("NOVA AI", "WiFi Failed!");
        delay(2000);
    }
}

// ============== Microphone Callback for Edge Impulse ==============
static int microphoneCallback(short *buffer, uint32_t n) {
    size_t bytesRead;
    i2s_read(MIC_I2S_NUM, buffer, n * sizeof(int16_t), &bytesRead, portMAX_DELAY);
    return 0;
}

// ============== Record Audio for Backend ==============
uint8_t* recordAudio(size_t* bytesRecorded) {
    Serial.println("[REC] Recording started (max 10s, auto-stop on silence)...");
    isRecording = true;

    uint8_t* audioBuffer = (uint8_t*)malloc(RECORD_BUFFER_SIZE);
    if (!audioBuffer) {
        Serial.println("[REC] Failed to allocate buffer!");
        isRecording = false;
        *bytesRecorded = 0;
        return nullptr;
    }

    size_t totalBytes = 0;
    size_t bytesRead = 0;
    uint8_t tempBuffer[1024];

    unsigned long startTime = millis();
    unsigned long recordDuration = RECORD_SECONDS * 1000;
    unsigned long lastSoundTime = millis();  // Track last time sound was detected

    i2s_zero_dma_buffer(MIC_I2S_NUM);
    delay(100);

    while ((millis() - startTime) < recordDuration && totalBytes < RECORD_BUFFER_SIZE) {
        i2s_read(MIC_I2S_NUM, tempBuffer, 1024, &bytesRead, portMAX_DELAY);

        if (bytesRead > 0) {
            // Calculate audio level for silence detection
            int16_t* samples = (int16_t*)tempBuffer;
            int32_t maxLevel = 0;

            for (int i = 0; i < bytesRead / 2; i++) {
                int32_t level = abs(samples[i]);
                if (level > maxLevel) {
                    maxLevel = level;
                }
            }

            // Check if sound detected above threshold
            if (maxLevel > SILENCE_THRESHOLD) {
                lastSoundTime = millis();
            }

            // Check for silence timeout (only after minimum recording time)
            if ((millis() - startTime) > MIN_RECORD_DURATION_MS &&
                (millis() - lastSoundTime) > SILENCE_DURATION_MS) {
                Serial.printf("[REC] Silence detected (max level: %d), stopping early at %.1fs\n",
                    maxLevel, (millis() - startTime) / 1000.0);
                break;
            }

            // Apply Gain to recording
            for (int i = 0; i < bytesRead / 2; i++) {
                int32_t sample = samples[i] * 3; // 3x Gain
                if (sample > 32767) sample = 32767;
                if (sample < -32768) sample = -32768;
                samples[i] = (int16_t)sample;
            }

            if ((totalBytes + bytesRead) <= RECORD_BUFFER_SIZE) {
                memcpy(audioBuffer + totalBytes, tempBuffer, bytesRead);
                totalBytes += bytesRead;
            }
        }
    }

    isRecording = false;
    float recordedSeconds = (millis() - startTime) / 1000.0;

    // ============== Trim Silence from Recording ==============
    if (totalBytes > 0) {
        int16_t* samples = (int16_t*)audioBuffer;
        size_t numSamples = totalBytes / 2;

        // Find first non-silent sample
        size_t startSample = 0;
        for (size_t i = 0; i < numSamples; i++) {
            if (abs(samples[i]) > SILENCE_THRESHOLD) {
                startSample = i;
                break;
            }
        }

        // Find last non-silent sample
        size_t endSample = numSamples - 1;
        for (size_t i = numSamples - 1; i > startSample; i--) {
            if (abs(samples[i]) > SILENCE_THRESHOLD) {
                endSample = i;
                break;
            }
        }

        // Calculate trimmed size
        size_t trimmedSamples = (endSample - startSample + 1);
        size_t trimmedBytes = trimmedSamples * 2;

        // Copy trimmed audio to beginning of buffer
        if (startSample > 0) {
            memmove(audioBuffer, audioBuffer + (startSample * 2), trimmedBytes);
        }

        size_t trimmedFromStart = startSample * 2;
        size_t trimmedFromEnd = totalBytes - (endSample + 1) * 2;

        Serial.printf("[REC] Recorded %d bytes in %.1f seconds\n", totalBytes, recordedSeconds);
        Serial.printf("[REC] Trimmed %d bytes (start: %d, end: %d) → Final: %d bytes\n",
            trimmedFromStart + trimmedFromEnd, trimmedFromStart, trimmedFromEnd, trimmedBytes);

        *bytesRecorded = trimmedBytes;
    } else {
        Serial.printf("[REC] Recorded %d bytes in %.1f seconds\n", totalBytes, recordedSeconds);
        *bytesRecorded = totalBytes;
    }

    return audioBuffer;
}

// ============== Send Audio & Play Response ==============
void sendAndPlay(uint8_t* audioData, size_t audioSize) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[HTTP] WiFi not connected!");
        return;
    }
    
#if USE_HTTPS
    String url = String("https://") + BACKEND_HOST + VOICE_ENDPOINT;
    WiFiClientSecure client;
    client.setInsecure();
#else
    String url = String("http://") + BACKEND_HOST + ":" + String(BACKEND_PORT) + VOICE_ENDPOINT;
    WiFiClient client;
#endif
    Serial.printf("[HTTP] Sending to %s\n", url.c_str());
    
    HTTPClient http;
    http.begin(client, url);
    http.addHeader("Content-Type", "application/octet-stream");
    http.setTimeout(45000);  // Increased to 45s for backend processing time

    setLedColor(0, 0, 255); // Blue (Processing)
    soundProcessing(); // Gentle pulse - thinking sound

    int httpCode = http.POST(audioData, audioSize);

    if (httpCode == HTTP_CODE_OK) {
        soundSuccess(); // Play success sound when response received
        WiFiClient* stream = http.getStreamPtr();
        int contentLength = http.getSize();

        // Get STT transcription from custom header (URL-encoded)
        String transcription = http.header("X-Transcription");
        if (transcription.length() > 0) {
            String decodedTranscription = urlDecode(transcription);
            Serial.println("\n========== YOU SAID ==========");
            Serial.println(decodedTranscription);
            Serial.println("==============================\n");
        }

        // Get AI response text from custom header (URL-encoded)
        String aiResponse = http.header("X-AI-Response");
        if (aiResponse.length() > 0) {
            String decodedResponse = urlDecode(aiResponse);
            Serial.println("========== AI RESPONSE ==========");
            Serial.println(decodedResponse);
            Serial.println("=================================\n");
        }

        Serial.printf("[HTTP] Content-Length: %d bytes\n", contentLength);

        // ============================================
        // STREAMING MODE (Play as data arrives)
        // ============================================
        {
            Serial.println("[STREAM] Starting real-time playback...");
            isPlaying = true;
            setLedColor(50, 0, 200); // Purple (Speaking)

            const size_t bufferSize = 16384;
            uint8_t* buffer = (uint8_t*)malloc(bufferSize);

            if (!buffer) {
                Serial.println("[ERR] Buffer malloc failed!");
                http.end();
                return;
            }

            size_t bytesWritten;
            unsigned long lastDataTime = millis();
            unsigned long streamStartTime = millis();
            bool receivedFirstByte = false;
            size_t totalStreamed = 0;
            bool useContentLength = (contentLength > 0);

            Serial.println("[STREAM] Waiting for audio from backend...");

            // Streaming Loop - Play audio as it arrives
            unsigned long noDataCount = 0;
            unsigned long lastProgressPrint = 0;

            while (true) {
                size_t available = stream->available();

                if (available > 0) {
                    if (!receivedFirstByte) {
                        Serial.println("[STREAM] Audio started, playing immediately...");
                        receivedFirstByte = true;
                    }

                    lastDataTime = millis();
                    int bytesRead = stream->readBytes(buffer, min(bufferSize, available));
                    if (bytesRead > 0) {
                        i2s_write(SPK_I2S_NUM, buffer, bytesRead, &bytesWritten, portMAX_DELAY);
                        totalStreamed += bytesRead;
                        noDataCount = 0; // Reset counter when data arrives

                        // Print progress every 2 seconds or when significant progress made
                        if (millis() - lastProgressPrint > 2000 || (totalStreamed % 50000 < bufferSize)) {
                            if (useContentLength) {
                                Serial.printf("[STREAM] Playing: %d / %d bytes (%.1f%%)\n",
                                    totalStreamed, contentLength, (float)totalStreamed * 100.0 / contentLength);
                            } else {
                                Serial.printf("[STREAM] Playing: %d bytes (%.1f KB)\n", totalStreamed, totalStreamed / 1024.0);
                            }
                            lastProgressPrint = millis();
                        }

                        // PRIORITY: Check if we got all expected data based on Content-Length
                        if (useContentLength && totalStreamed >= contentLength) {
                            Serial.printf("[STREAM] ✓ All expected data played! (%d bytes)\n", totalStreamed);
                            break;
                        }
                    }
                } else {
                    // No data available right now
                    if (!receivedFirstByte) {
                        // Still waiting for backend to send first byte
                        if (millis() - streamStartTime > 30000) {
                            Serial.println("[ERR] Timeout waiting for backend stream (30s)");
                            break;
                        }
                    } else {
                        // Already streaming - be VERY patient if we haven't received all data yet
                        noDataCount++;

                        // If we know how much to expect, wait much longer
                        unsigned long maxWaitChecks;
                        if (useContentLength && totalStreamed < contentLength) {
                            // Still expecting more data - wait up to 15 seconds
                            maxWaitChecks = 1500; // 15 seconds

                            // Log every 5 seconds of waiting
                            if (noDataCount % 500 == 0) {
                                Serial.printf("[STREAM] Waiting for more data... (%d / %d bytes received, %.1f%% complete)\n",
                                    totalStreamed, contentLength, (float)totalStreamed * 100.0 / contentLength);
                            }
                        } else {
                            // Either no Content-Length, or we got all expected data
                            maxWaitChecks = 500; // 5 seconds
                        }

                        if (noDataCount >= maxWaitChecks) {
                            Serial.printf("[STREAM] No more data after %lu checks (%.1f seconds)\n",
                                noDataCount, noDataCount * 0.01);

                            if (useContentLength && totalStreamed < contentLength) {
                                Serial.printf("[ERROR] INCOMPLETE STREAM! Expected %d bytes but only got %d bytes (%.1f%%)\n",
                                    contentLength, totalStreamed, (float)totalStreamed * 100.0 / contentLength);
                            } else {
                                Serial.println("[STREAM] Stream appears complete");
                            }
                            break;
                        }

                        // Secondary check: connection closed
                        if (!http.connected() && !stream->available()) {
                            // Wait a bit more even if connection closed, in case data is still in buffer
                            if (noDataCount > 100) { // Wait at least 1 second after connection closes
                                Serial.println("[STREAM] Connection closed and no data for 1+ second");

                                if (useContentLength && totalStreamed < contentLength) {
                                    Serial.printf("[ERROR] Connection closed early! Expected %d, played %d bytes (%.1f%%)\n",
                                        contentLength, totalStreamed, (float)totalStreamed * 100.0 / contentLength);
                                }
                                break;
                            }
                        }
                    }
                    delay(10);
                }
            }

            Serial.printf("[STREAM] Total played: %d bytes\n", totalStreamed);
            free(buffer);
        }

        i2s_zero_dma_buffer(SPK_I2S_NUM);
        isPlaying = false;
        setLedColor(0,0,0); // Off
        Serial.println("[SPK] Playback complete");
    } else {
        Serial.printf("[HTTP] Error: %d\n", httpCode);
        soundError(); // Play error sound for failed requests
        setLedColor(255, 0, 0); // Red LED for error
        delay(1000);
        setLedColor(0, 0, 0); // Turn off LED
    }

    http.end();
}

// ============== Main Listen Flow ==============
void startListening() {
    Serial.println("\n========== LISTENING ==========");
    setLedColor(0, 255, 255); // Cyan (Alexa Listening)
    displayFaceListening();  // Animated listening face
    soundListening();  // High ping - attention sound


    size_t bytesRecorded = 0;
    uint8_t* audioData = recordAudio(&bytesRecorded);

    if (audioData && bytesRecorded > 0) {
        displayFaceProcessing();  // Animated thinking face
        sendAndPlay(audioData, bytesRecorded);
        free(audioData);
    }

    // Reset animation timers and return to idle animation
    lastBlinkTime = millis();
    lastBreathTime = millis();
    breathPhase = 0;
    displayFaceIdleAnimated();  // Back to animated idle face

    Serial.println("================================\n");
    consecutiveWakeDetections = 0;  // Reset wake word counter
}

// ============== Setup ==============
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n========================================");
    Serial.println("       NOVA AI Voice Assistant");
    Serial.println("========================================\n");
    
    setupMicrophone();

    // Setup Button (GPIO 0 - Boot Button)
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    setupSpeaker();

    // Setup OLED Display
    setupOLED();
    displayMessage("NOVA AI", "Speaker Init...");

    connectWiFi();

    // Init LED
    pixels.begin();
    pixels.setBrightness(30); // Low brightness
    setLedColor(255, 100, 0); // Orange for Startup

    Serial.println("[SPK] Playing startup sound...");
    soundStartup(); // Play pleasant startup chime

    setLedColor(0, 0, 0); // Off

    displayFaceHappy();  // Show happy face
    delay(1500);

    // Initialize animation timers
    lastBlinkTime = millis();
    lastBreathTime = millis();
    breathPhase = 0;

    displayFaceIdleAnimated();  // Start with animated idle face

    Serial.println("\n[READY] Say 'Hey Nova' or type 'l'\n");
}

// ============== Loop ==============
void loop() {
    // Check for Mute Button (GPIO 0)
    static unsigned long lastBtnTime = 0;
    if (digitalRead(BUTTON_PIN) == LOW) {
        if (millis() - lastBtnTime > 500) { // 500ms debounce
            isMuted = !isMuted;
            lastBtnTime = millis();
            
            Serial.printf("[SYSTEM] %s\n", isMuted ? "MUTED (Silent Mode)" : "UNMUTED (Listening)");

            // Audio Feedback
            if (isMuted) {
                setLedColor(255, 0, 0); // Red
                displayFaceSleeping();  // Show sleeping face
                soundMute(); // Descending tone - going quiet
            } else {
                setLedColor(0, 0, 0); // Off
                // Reset animation and show animated idle face
                lastBlinkTime = millis();
                lastBreathTime = millis();
                breathPhase = 0;
                displayFaceIdleAnimated();
                soundUnmute(); // Ascending tone - becoming active
            }
        }
    }

    // Check for serial command
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd == 'l' || cmd == 'L') {
            startListening();
        }
    }

    // Update idle animation when active (not muted)
    if (!isRecording && !isPlaying && !isMuted) {
        updateIdleAnimation();
    }

    // Wake word detection using continuous inference
    if (!isRecording && !isPlaying && !isMuted) {
        // Read a slice of audio
        static int16_t audioBuffer[EI_CLASSIFIER_SLICE_SIZE];
        size_t bytesRead;

        esp_err_t err = i2s_read(MIC_I2S_NUM, audioBuffer,
            EI_CLASSIFIER_SLICE_SIZE * sizeof(int16_t),
            &bytesRead, portMAX_DELAY);

        if (err != ESP_OK || bytesRead == 0) {
            return;
        }

        // Apply 10x Gain (Software amplification for far-field detection)
        for (int i = 0; i < bytesRead / 2; i++) {
            int32_t sample = audioBuffer[i] * 10;
            if (sample > 32767) sample = 32767;
            if (sample < -32768) sample = -32768;
            audioBuffer[i] = (int16_t)sample;
        }

        // Create signal from the audio buffer
        signal_t signal;
        signal.total_length = EI_CLASSIFIER_SLICE_SIZE;
        signal.get_data = [](size_t offset, size_t length, float *out) -> int {
            numpy::int16_to_float(&audioBuffer[offset], out, length);
            return 0;
        };

        // Run continuous classifier
        ei_impulse_result_t result = {0};
        EI_IMPULSE_ERROR eiErr = run_classifier_continuous(&signal, &result, false);

        if (eiErr == EI_IMPULSE_OK) {
            // Check for wake word (index 0 = "Nova", index 1 = "noise", index 2 = "unknown")
            float novaConf = result.classification[0].value;
            float noiseConf = result.classification[1].value;
            float unknownConf = result.classification[2].value;

            // Only trigger if Nova confidence is high AND it's the dominant class
            if (novaConf > WAKE_WORD_CONFIDENCE &&
                novaConf > noiseConf &&
                novaConf > unknownConf) {
                consecutiveWakeDetections++;
                Serial.printf("[WAKE] Nova: %.2f | Noise: %.2f | Unknown: %.2f (%d/%d)\n",
                    novaConf, noiseConf, unknownConf,
                    consecutiveWakeDetections, CONSECUTIVE_DETECTIONS);

                if (consecutiveWakeDetections >= CONSECUTIVE_DETECTIONS) {
                    Serial.println("[WAKE] *** WAKE WORD CONFIRMED! ***");
                    startListening();
                }
            } else {
                consecutiveWakeDetections = 0;
            }
        }
    }

    delay(10);
}
