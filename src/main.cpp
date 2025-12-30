#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>
#include "config.h"

// Edge Impulse Wake Word
#include <test-new_inferencing.h>

// ============== Wake Word Configuration ==============
// Optimized settings matching Edge Impulse browser portal (continuous inference mode)
#define WAKE_WORD_CONFIDENCE 0.60f  // 60% threshold (EI_CLASSIFIER_THRESHOLD default)
#define CONSECUTIVE_DETECTIONS 1    // Single detection (like Edge Impulse portal)
#define NOISE_GATE_THRESHOLD 100    // Minimum audio level to process (reduced false positives)
#define WAKE_WORD_GAIN 8            // 8x gain to match Edge Impulse portal example
#define CONFIDENCE_GAP 0.10f        // Nova score must be 10% higher than Noise/Unknown
#define DEBUG_WAKE_WORD false       // Disable debug output for production use

// ============== Button Configuration ==============
#define BUTTON_PIN 4
#define LONG_PRESS_TIME 3000  // 3 seconds for power off
bool isMuted = false;
unsigned long buttonPressStart = 0;
bool buttonWasPressed = false;

// ============== Global State ==============
bool isRecording = false;
bool isPlaying = false;
int consecutiveWakeDetections = 0;
static bool micReady = false;


// ============== Emotion Control ==============
enum Emotion {
    EMOTION_NORMAL,
    EMOTION_HAPPY,
    EMOTION_SAD,
    EMOTION_EXCITED,
    EMOTION_SCARED,
    EMOTION_SHOCK,
    EMOTION_ANGRY,
    EMOTION_ROMANTIC,
    EMOTION_COLD,
    EMOTION_HOT,
    EMOTION_SERIOUS,
    EMOTION_CONFUSED,
    EMOTION_CURIOUS,
    EMOTION_SLEEPY
};
Emotion currentEmotion = EMOTION_NORMAL;

// Audio buffers for wake word (continuous inference with double buffering)
typedef struct {
    int16_t *buffers[2];
    uint8_t buf_select;
    uint8_t buf_ready;
    uint32_t buf_count;
    uint32_t n_samples;
} inference_t;

static inference_t inference;
static int16_t sampleBuffer[2048];  // Temporary buffer for I2S reads
static int print_results = -(EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);  // Print after full window

// ============== NeoPixel Setup ==============
Adafruit_NeoPixel pixels(NUM_LEDS, RGB_LED_PIN, NEO_GRB + NEO_KHZ800);

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

// ============== Audio Preprocessing Variables ==============
static float dcOffsetFilter = 0.0f;
static const float DC_FILTER_ALPHA = 0.95f; // High-pass filter coefficient

// Simple low-pass filter for noise reduction
static int16_t lastSample = 0;
static const float LOWPASS_ALPHA = 0.85f; // INCREASED: Less aggressive filtering (0.0-1.0)

// DC offset removal (high-pass filter)
int16_t removeDCOffset(int16_t sample) {
    dcOffsetFilter = DC_FILTER_ALPHA * dcOffsetFilter + (1.0f - DC_FILTER_ALPHA) * sample;
    return sample - (int16_t)dcOffsetFilter;
}

// Low-pass filter to remove high-frequency noise (gentle)
int16_t lowPassFilter(int16_t sample) {
    lastSample = (int16_t)(LOWPASS_ALPHA * sample + (1.0f - LOWPASS_ALPHA) * lastSample);
    return lastSample;
}

// Gentle noise reduction - applies minimal filtering
int16_t reduceNoise(int16_t sample) {
    // Step 1: Remove DC offset only
    sample = removeDCOffset(sample);

    // Step 2: Very gentle low-pass filter (optional, can be disabled)
    // sample = lowPassFilter(sample);  // Commented out - too aggressive

    // Step 3: Gentle noise gate - only suppress dead silence
    if (abs(sample) < 10) {  // REDUCED: Lower threshold for noise floor
        sample = 0;
    }

    return sample;
}

// Voice Activity Detection (VAD) - checks if audio has speech energy
bool isVoiceActivity(int16_t* buffer, size_t samples) {
    int32_t energy = 0;
    for (size_t i = 0; i < samples; i++) {
        energy += abs(buffer[i]);
    }
    int32_t avgEnergy = energy / samples;
    return avgEnergy > NOISE_GATE_THRESHOLD;
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
        .dma_buf_count = 24,   // Increased from 16 for more stable buffering
        .dma_buf_len = 1024,
        .use_apll = true,      // Enable APLL for more stable audio clock
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

    // Clear DMA buffers to avoid initial noise
    i2s_zero_dma_buffer(MIC_I2S_NUM);
    delay(100);

    micReady = true;
    Serial.println("[MIC] Enhanced microphone initialized (16kHz, APLL enabled)");
    Serial.println("[MIC] Minimal processing: DC offset removal + Gentle noise gate");
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
        .dma_buf_count = 24,   // Increased from 16 for smoother playback
        .dma_buf_len = 1024,
        .use_apll = true,      // Enable APLL for better audio quality
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
    Serial.println("[SPK] Enhanced speaker initialized (16kHz, APLL enabled)");
}

// ============== Display Functions Removed ==============
// Pure audio speaker - no screen needed


Emotion parseEmotionString(String emotion) {
    emotion.toLowerCase();
    if (emotion == "happy") return EMOTION_HAPPY;
    else if (emotion == "sad") return EMOTION_SAD;
    else if (emotion == "excited") return EMOTION_EXCITED;
    else if (emotion == "scared") return EMOTION_SCARED;
    else if (emotion == "shock") return EMOTION_SHOCK;
    else if (emotion == "angry") return EMOTION_ANGRY;
    else if (emotion == "romantic") return EMOTION_ROMANTIC;
    else if (emotion == "cold") return EMOTION_COLD;
    else if (emotion == "hot") return EMOTION_HOT;
    else if (emotion == "serious") return EMOTION_SERIOUS;
    else if (emotion == "confused") return EMOTION_CONFUSED;
    else if (emotion == "curious") return EMOTION_CURIOUS;
    else if (emotion == "sleepy") return EMOTION_SLEEPY;
    else return EMOTION_NORMAL;
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

    // Try primary WiFi
    Serial.printf("[WIFI] Trying primary: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    // If primary fails, try backup WiFi
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\n[WIFI] Primary failed, trying backup...");

        WiFi.disconnect();
        delay(100);

        Serial.printf("[WIFI] Trying backup: %s\n", WIFI_SSID_BACKUP);
        WiFi.begin(WIFI_SSID_BACKUP, WIFI_PASSWORD_BACKUP);

        attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            attempts++;
        }
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.printf("[WIFI] Connected to: %s\n", WiFi.SSID().c_str());
        Serial.print("[WIFI] IP Address: ");
        Serial.println(WiFi.localIP());

        // CRITICAL: Disable WiFi Power Save to prevent high latency/jitter
        WiFi.setSleep(false);
        Serial.println("[WIFI] Power Save Mode: DISABLED (High Performance)");

        // Set maximum WiFi TX power for better signal strength (reduces lag)
        WiFi.setTxPower(WIFI_POWER_19_5dBm); // Maximum power (19.5dBm)
        Serial.println("[WIFI] TX Power: MAXIMUM (19.5 dBm) - Reduces lag");

        // Print WiFi diagnostics for troubleshooting
        int rssi = WiFi.RSSI();
        Serial.printf("[WIFI] Signal Strength (RSSI): %d dBm\n", rssi);
        Serial.printf("[WIFI] Channel: %d\n", WiFi.channel());

        // Warn user about signal quality
        if (rssi > -50) {
            Serial.println("[WIFI] Signal Quality: EXCELLENT");
        } else if (rssi > -60) {
            Serial.println("[WIFI] Signal Quality: GOOD");
        } else if (rssi > -70) {
            Serial.println("[WIFI] Signal Quality: FAIR - May cause audio lag");
        } else {
            Serial.println("[WIFI] Signal Quality: WEAK - WILL cause audio lag!");
            Serial.println("[WIFI] >>> Move ESP32 closer to WiFi router <<<");
        }
    } else {
        Serial.println("\n[WIFI] Both networks failed!");
    }
}

// ============== Continuous Inference Helper Functions ==============

/**
 * @brief Get audio signal data for Edge Impulse classifier
 */
static int microphone_audio_signal_get_data(size_t offset, size_t length, float *out_ptr) {
    // Convert int16 to float from the inactive buffer
    for (size_t i = 0; i < length; i++) {
        out_ptr[i] = (float)inference.buffers[inference.buf_select ^ 1][offset + i];
    }
    return 0;
}

/**
 * @brief Initialize continuous inference buffers
 */
static bool microphone_inference_start(uint32_t n_samples) {
    inference.buffers[0] = (int16_t *)malloc(n_samples * sizeof(int16_t));
    if (inference.buffers[0] == NULL) {
        Serial.println("[WAKE] Failed to allocate buffer 0");
        return false;
    }

    inference.buffers[1] = (int16_t *)malloc(n_samples * sizeof(int16_t));
    if (inference.buffers[1] == NULL) {
        free(inference.buffers[0]);
        Serial.println("[WAKE] Failed to allocate buffer 1");
        return false;
    }

    inference.buf_select = 0;
    inference.buf_count = 0;
    inference.n_samples = n_samples;
    inference.buf_ready = 0;

    Serial.printf("[WAKE] Continuous inference initialized (slice size: %d samples)\n", n_samples);
    return true;
}

/**
 * @brief Stop continuous inference and free buffers
 */
static void microphone_inference_end(void) {
    if (inference.buffers[0]) free(inference.buffers[0]);
    if (inference.buffers[1]) free(inference.buffers[1]);
    inference.buffers[0] = NULL;
    inference.buffers[1] = NULL;
}

// ============== Continuous Wake Word Detection Function ==============
bool detectWakeWord() {
    if (isMuted || isRecording || isPlaying) {
        return false;  // Skip detection when muted or busy
    }

    // Read one slice of audio (250ms = 4000 samples at 16kHz)
    size_t bytesRead;
    i2s_read(MIC_I2S_NUM, sampleBuffer, 2048 * sizeof(int16_t), &bytesRead, portMAX_DELAY);

    if (bytesRead <= 0) {
        if (DEBUG_WAKE_WORD) Serial.println("[WAKE] I2S read error");
        return false;
    }

    // Apply 8x gain to match Edge Impulse portal (like the official example)
    for (int i = 0; i < bytesRead / 2; i++) {
        sampleBuffer[i] = (int16_t)(sampleBuffer[i] * 8);
    }

    // Fill the double buffer (ping-pong buffering)
    for (int i = 0; i < bytesRead / 2; i++) {
        inference.buffers[inference.buf_select][inference.buf_count++] = sampleBuffer[i];

        if (inference.buf_count >= inference.n_samples) {
            // Buffer full, switch buffers
            inference.buf_select ^= 1;
            inference.buf_count = 0;
            inference.buf_ready = 1;
            break;
        }
    }

    // Only run inference when we have a full slice ready
    if (inference.buf_ready == 0) {
        return false;
    }

    inference.buf_ready = 0;

    // Run continuous classifier (accumulates slices internally)
    signal_t signal;
    signal.total_length = EI_CLASSIFIER_SLICE_SIZE;
    signal.get_data = &microphone_audio_signal_get_data;
    ei_impulse_result_t result = {0};

    EI_IMPULSE_ERROR res = run_classifier_continuous(&signal, &result, DEBUG_WAKE_WORD);

    if (res != EI_IMPULSE_OK) {
        Serial.printf("[WAKE] Inference error: %d\n", res);
        return false;
    }

    // Only check results after processing a full window (4 slices = 1 second)
    if (++print_results >= EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW) {
        // Find scores for "Nova", "noise", and "unknown"
        float novaScore = 0.0f;
        float noiseScore = 0.0f;
        float unknownScore = 0.0f;

        for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
            const char* label = result.classification[i].label;
            float score = result.classification[i].value;

            if (strcmp(label, "Nova") == 0) {
                novaScore = score;
            } else if (strcmp(label, "noise") == 0) {
                noiseScore = score;
            } else if (strcmp(label, "unknown") == 0) {
                unknownScore = score;
            }
        }

        // Check if Nova score meets all criteria
        float maxOtherScore = max(noiseScore, unknownScore);
        bool detected = (novaScore >= WAKE_WORD_CONFIDENCE) &&
                        (novaScore > maxOtherScore + CONFIDENCE_GAP);

        if (detected) {
            consecutiveWakeDetections++;
            Serial.printf("[WAKE] ✓ Nova: %.2f | Noise: %.2f | Unknown: %.2f | Consecutive: %d/%d\n",
                          novaScore, noiseScore, unknownScore,
                          consecutiveWakeDetections, CONSECUTIVE_DETECTIONS);

            if (consecutiveWakeDetections >= CONSECUTIVE_DETECTIONS) {
                Serial.println("\n[WAKE] ========== WAKE WORD DETECTED! ==========\n");
                consecutiveWakeDetections = 0;
                print_results = -(EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);  // Reset
                return true;
            }
        } else {
            if (DEBUG_WAKE_WORD || novaScore > 0.3) {
                Serial.printf("[WAKE] Nova: %.2f | Noise: %.2f | Unknown: %.2f\n",
                              novaScore, noiseScore, unknownScore);
            }
            consecutiveWakeDetections = 0;
        }

        print_results = 0;  // Reset for next window
    }

    return false;
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

        // Get facial expression code from backend (0-6)
        String expressionHeader = http.header("X-Expression");
        if (expressionHeader.length() > 0) {
            int expressionCode = expressionHeader.toInt();
            Serial.printf("[EXPRESSION] Backend sent expression code: %d\n", expressionCode);

            // Map expression code to emotion enum
            // 0=neutral, 1=happy, 2=thinking, 3=excited, 4=sad, 5=smiling, 6=surprised
            switch (expressionCode) {
                case 1: currentEmotion = EMOTION_HAPPY; break;
                case 2: currentEmotion = EMOTION_CURIOUS; break;  // thinking -> curious
                case 3: currentEmotion = EMOTION_EXCITED; break;
                case 4: currentEmotion = EMOTION_SAD; break;
                case 5: currentEmotion = EMOTION_HAPPY; break;  // smiling -> happy
                case 6: currentEmotion = EMOTION_SHOCK; break;  // surprised -> shock
                default: currentEmotion = EMOTION_NORMAL; break;
            }
        }

        // Get emotion from backend LLM (X-Emotion header) - fallback if no X-Expression
        String emotionHeader = http.header("X-Emotion");
        if (emotionHeader.length() > 0) {
            currentEmotion = parseEmotionString(emotionHeader);
            Serial.printf("[EMOTION] Backend sent emotion: %s\n", emotionHeader.c_str());
        } else {
            currentEmotion = EMOTION_NORMAL;  // Default if no emotion provided
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

            // Mouth animation for speaking
            int mouthPhase = 0;  // 0=closed, 1=half, 2=open, 3=half (cycles)
            unsigned long lastMouthUpdate = millis();

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
                        // Maximize transfer to I2S DMA in one go
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

                        // If we know how much to expect, wait MUCH longer
                        unsigned long maxWaitChecks;
                        if (useContentLength && totalStreamed < contentLength) {
                            // Still expecting more data - wait up to 30 seconds
                            maxWaitChecks = 30000; // 30 seconds (very patient!)

                            // Log every 5 seconds of waiting
                            if (noDataCount % 5000 == 0) {
                                Serial.printf("[STREAM] Waiting for more data... (%d / %d bytes received, %.1f%% complete)\n",
                                    totalStreamed, contentLength, (float)totalStreamed * 100.0 / contentLength);
                            }
                        } else {
                            // Either no Content-Length, or we got all expected data
                            maxWaitChecks = 10000; // 10 seconds (also very patient!)
                        }

                        if (noDataCount >= maxWaitChecks) {
                            Serial.printf("[STREAM] No more data after %lu checks (%.1f seconds)\n",
                                noDataCount, noDataCount / 1000.0);

                            if (useContentLength && totalStreamed < contentLength) {
                                Serial.printf("[ERROR] INCOMPLETE STREAM! Expected %d bytes but only got %d bytes (%.1f%%)\n",
                                    contentLength, totalStreamed, (float)totalStreamed * 100.0 / contentLength);
                            } else {
                                Serial.println("[STREAM] Stream appears complete");
                            }
                            break;
                        }

                        // Secondary check: connection closed - but keep waiting for Content-Length
                        if (!http.connected() && !stream->available()) {
                            // If we have Content-Length and haven't received it all, keep waiting
                            if (useContentLength && totalStreamed < contentLength) {
                                // Keep waiting - data might still arrive
                                if (noDataCount % 5000 == 0) {
                                    Serial.printf("[STREAM] Connection closed but still waiting for data (%d/%d bytes)\n",
                                        totalStreamed, contentLength);
                                }
                                // Don't break - keep waiting until maxWaitChecks
                            } else {
                                // No Content-Length or we got everything - wait 3 seconds then stop
                                if (noDataCount > 3000) {
                                    Serial.println("[STREAM] Connection closed and no data for 3+ seconds");
                                    break;
                                }
                            }
                        }
                    }
                    // Only small delay if NO data, to prevent spinning too fast
                    delay(1); 
                }
            }

            Serial.printf("[STREAM] Total played: %d bytes\n", totalStreamed);
            free(buffer);

            // IMPORTANT: Wait for I2S DMA to finish playing buffered audio
            // At 16kHz, 16-bit stereo (4 bytes/sample), DMA buffers can hold:
            // 24 buffers × 1024 bytes = 24KB ≈ 6 seconds of audio
            if (totalStreamed > 0) {
                // Calculate approximate playback time for buffered audio
                // 16kHz × 2 channels × 2 bytes = 64,000 bytes/second
                int dmaBufferBytes = 24 * 1024; // 24 DMA buffers
                int waitMs = (dmaBufferBytes * 1000) / 64000; // ~375ms
                Serial.printf("[SPK] Waiting %dms for DMA buffer to finish playing...\n", waitMs);
                delay(waitMs + 200); // Extra 200ms margin for safety
            }
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
    soundListening();  // High ping - attention sound

    size_t bytesRecorded = 0;
    uint8_t* audioData = recordAudio(&bytesRecorded);

    if (audioData && bytesRecorded > 0) {
        sendAndPlay(audioData, bytesRecorded);
        free(audioData);
    }

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

    // Check wake-up reason
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
        Serial.println("[POWER] Woke up from button press!");
    } else if (wakeup_reason == ESP_SLEEP_WAKEUP_UNDEFINED) {
        Serial.println("[POWER] Power-on reset or first boot");
    }

    setupMicrophone();

    // Setup Button (GPIO 4)
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    setupSpeaker();

    connectWiFi();

    // Init LED
    pixels.begin();
    pixels.setBrightness(30); // Low brightness
    setLedColor(255, 100, 0); // Orange for Startup

    Serial.println("[SPK] Playing startup sound...");
    soundStartup(); // Play pleasant startup chime

    setLedColor(0, 0, 0); // Off

    // Initialize continuous wake word detection
    Serial.printf("\n[WAKE] Initializing continuous inference...\n");
    Serial.printf("[WAKE] Slice size: %d samples (%.0f ms)\n",
                  EI_CLASSIFIER_SLICE_SIZE,
                  (float)EI_CLASSIFIER_SLICE_SIZE / 16.0f);
    Serial.printf("[WAKE] Window: %d slices = %d samples (%.0f ms)\n",
                  EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW,
                  EI_CLASSIFIER_RAW_SAMPLE_COUNT,
                  (float)EI_CLASSIFIER_RAW_SAMPLE_COUNT / 16.0f);

    if (microphone_inference_start(EI_CLASSIFIER_SLICE_SIZE) == false) {
        Serial.println("[WAKE] ERROR: Failed to start continuous inference!");
    } else {
        run_classifier_init();  // Initialize Edge Impulse classifier
        Serial.println("[WAKE] Continuous inference ready!");
    }

    Serial.println("\n[READY] NOVA AI Speaker Ready!");
    Serial.println("Controls:");
    Serial.println("  - Wake word: Say 'Nova' to activate");
    Serial.println("  - Press BUTTON (GPIO 4) to start listening");
    Serial.println("  - Type 'l' to start listening");
    Serial.println("  - Type 'r' for mic test (record 10s & playback)");
    Serial.println("  - Long press BUTTON (3s) to sleep\n");
}

// ============== Loop ==============
void loop() {


    // Check for Mute Button (GPIO 4) with Long-Press Power Off
    bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

    // Detect button press start
    if (buttonPressed && !buttonWasPressed) {
        buttonPressStart = millis();
        buttonWasPressed = true;
    }

    // Check for long press (3 seconds) - Power Off
    if (buttonPressed && buttonWasPressed) {
        unsigned long pressDuration = millis() - buttonPressStart;

        // Long press detected - enter deep sleep
        if (pressDuration >= LONG_PRESS_TIME) {
            Serial.println("\n[POWER] Long press detected - Shutting down...");
            setLedColor(255, 0, 0); // Red
            delay(1500);
            setLedColor(0, 0, 0); // Off

            // Configure wake-up source: Button press to wake up
            // GPIO 4 is INPUT_PULLUP, so it's HIGH when not pressed
            // Wake when button is pressed (LOW)
            esp_sleep_enable_ext0_wakeup((gpio_num_t)BUTTON_PIN, 0); // 0 = wake on LOW (button pressed)

            Serial.println("[POWER] Wake-up enabled on button press");
            Serial.println("[POWER] Entering deep sleep...");
            delay(100);

            // Enter deep sleep (ultra-low power mode)
            esp_deep_sleep_start();
        }
    }

    // Detect button release - Toggle Mute (short press)
    static unsigned long lastBtnTime = 0;
    if (!buttonPressed && buttonWasPressed) {
        unsigned long pressDuration = millis() - buttonPressStart;

        // Short press (< 3 seconds) - Toggle Mute
        if (pressDuration < LONG_PRESS_TIME && millis() - lastBtnTime > 500) {
            isMuted = !isMuted;
            lastBtnTime = millis();

            Serial.printf("[SYSTEM] %s\n", isMuted ? "MUTED (Silent Mode)" : "UNMUTED (Listening)");

            // Audio Feedback
            if (isMuted) {
                setLedColor(0, 0, 0); // Off (save battery)
                soundMute(); // Descending tone - going quiet
            } else {
                setLedColor(0, 0, 0); // Off
                soundUnmute(); // Ascending tone - becoming active
            }
        }

        buttonWasPressed = false;
    }

    // Check for serial command
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd == 'l' || cmd == 'L') {
            startListening();
        }
        else if (cmd == 'r' || cmd == 'R') {
            // Microphone test - record and playback
            Serial.println("\n========== MIC TEST MODE ==========");
            Serial.println("[TEST] Recording 10 seconds...");
            setLedColor(255, 0, 0); // Red - recording

            const size_t recordDuration = 10; // 10 seconds
            const size_t bufferSize = 16000 * 2 * recordDuration; // 16kHz, 16-bit, 10s
            uint8_t* testBuffer = (uint8_t*)malloc(bufferSize);

            if (!testBuffer) {
                Serial.println("[ERROR] Failed to allocate test buffer!");
                setLedColor(0, 0, 0);
            } else {
                size_t totalBytes = 0;
                size_t bytesRead = 0;

                i2s_zero_dma_buffer(MIC_I2S_NUM);
                delay(100);

                unsigned long startTime = millis();
                while ((millis() - startTime) < (recordDuration * 1000) && totalBytes < bufferSize) {
                    i2s_read(MIC_I2S_NUM, testBuffer + totalBytes, 1024, &bytesRead, portMAX_DELAY);
                    totalBytes += bytesRead;

                    // Print progress every second
                    if ((millis() - startTime) % 1000 < 50) {
                        int16_t* samples = (int16_t*)(testBuffer + totalBytes - bytesRead);
                        int32_t maxLevel = 0;
                        for (size_t i = 0; i < bytesRead / 2; i++) {
                            if (abs(samples[i]) > maxLevel) maxLevel = abs(samples[i]);
                        }
                        Serial.printf("[TEST] %ds | Max Level: %d | Bytes: %d\n",
                            (millis() - startTime) / 1000, maxLevel, totalBytes);
                    }
                }

                Serial.printf("[TEST] Recorded %d bytes in %d seconds\n",
                    totalBytes, (millis() - startTime) / 1000);

                // Calculate and show audio statistics
                int16_t* samples = (int16_t*)testBuffer;
                size_t numSamples = totalBytes / 2;
                int32_t maxLevel = 0;
                int64_t totalEnergy = 0;

                for (size_t i = 0; i < numSamples; i++) {
                    int32_t level = abs(samples[i]);
                    totalEnergy += level;
                    if (level > maxLevel) maxLevel = level;
                }

                int32_t avgLevel = totalEnergy / numSamples;
                Serial.printf("[TEST] Audio Stats: Max=%d, Avg=%d\n", maxLevel, avgLevel);

                if (maxLevel < 100) {
                    Serial.println("[WARNING] Very low audio levels - mic might not be working!");
                } else if (maxLevel > 30000) {
                    Serial.println("[WARNING] Very high audio levels - might be clipping!");
                } else {
                    Serial.println("[TEST] Audio levels look good!");
                }

                // Playback
                Serial.println("[TEST] Playing back recording...");
                setLedColor(0, 255, 0); // Green - playing
                delay(500);

                // Convert mono to stereo for playback
                int16_t stereoSample[2];
                size_t bytesWritten;

                for (size_t i = 0; i < numSamples; i++) {
                    stereoSample[0] = samples[i]; // Left
                    stereoSample[1] = samples[i]; // Right
                    i2s_write(SPK_I2S_NUM, stereoSample, 4, &bytesWritten, portMAX_DELAY);
                }

                i2s_zero_dma_buffer(SPK_I2S_NUM);
                free(testBuffer);

                Serial.println("[TEST] Playback complete!");
                setLedColor(0, 0, 0); // Off
                Serial.println("===================================\n");
            }
        }
    }

    // ============== Continuous Wake Word Detection ==============
    // Continuous inference runs on every loop (no timing delay needed)
    // The double buffering and slice-based approach handles timing automatically
    if (detectWakeWord()) {
        // Wake word detected! Start recording and conversation
        setLedColor(0, 255, 255); // Cyan (listening)
        soundListening();  // High ping - attention sound
        delay(200);

        // Record user's message
        size_t bytesRecorded;
        uint8_t* audioData = recordAudio(&bytesRecorded);

        if (audioData && bytesRecorded > 0) {
            // Send to backend and play response
            sendAndPlay(audioData, bytesRecorded);
            free(audioData);
        }

        // Reset for next wake word detection
        consecutiveWakeDetections = 0;
        print_results = -(EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);
        setLedColor(0, 0, 0); // Off
    }
}
