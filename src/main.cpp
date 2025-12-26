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
// ============== Wake Word Configuration ==============
// ============== Wake Word Configuration ==============
#define WAKE_WORD_CONFIDENCE 0.91f
#define CONSECUTIVE_DETECTIONS 1

// ============== Button Configuration ==============
#define BUTTON_PIN 4
bool isMuted = false;

// ============== Global State ==============
bool isRecording = false;
bool isPlaying = false;
int consecutiveWakeDetections = 0;

// Audio buffers for wake word
static int16_t sampleBuffer[EI_CLASSIFIER_RAW_SAMPLE_COUNT];
static bool micReady = false;

// ============== NeoPixel Setup ==============
Adafruit_NeoPixel pixels(NUM_LEDS, RGB_LED_PIN, NEO_GRB + NEO_KHZ800);

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

// ============== Play Beep Sound ==============
void playBeep(int frequency, int durationMs) {
    const int sampleRate = 16000;
    const int numSamples = (sampleRate * durationMs) / 1000;
    const float amplitude = 30000.0;
    
    int16_t* samples = (int16_t*)malloc(numSamples * 2 * sizeof(int16_t));
    if (!samples) return;
    
    for (int i = 0; i < numSamples; i++) {
        float t = (float)i / sampleRate;
        int16_t sample = (int16_t)(amplitude * sin(2.0 * M_PI * frequency * t));
        samples[i * 2] = sample;
        samples[i * 2 + 1] = sample;
    }
    
    size_t bytesWritten;
    i2s_write(SPK_I2S_NUM, samples, numSamples * 2 * sizeof(int16_t), &bytesWritten, portMAX_DELAY);
    free(samples);
    i2s_zero_dma_buffer(SPK_I2S_NUM);
}

// ============== Play Melody ==============
// 0: Startup, 1: Listening (Wake), 2: Processing, 3: Error
void playMelody(int type) {
    if (type == 0) { // Startup (Ascending)
        playBeep(523, 150); // C5
        delay(50);
        playBeep(659, 150); // E5
        delay(50);
        playBeep(784, 200); // G5
    } else if (type == 1) { // Listening (Alexa-like Ping)
        playBeep(880, 100); // A5
        playBeep(1100, 150); // C#6 (approx)
    } else if (type == 2) { // Processing (Thinking)
        playBeep(600, 100);
        delay(50);
        playBeep(600, 100);
    }
}

// ============== WiFi Connection ==============
void connectWiFi() {
    Serial.print("[WIFI] Connecting to ");
    Serial.println(WIFI_SSID);
    
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
    } else {
        Serial.println("\n[WIFI] Connection failed!");
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
    Serial.println("[REC] Recording started...");
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
    
    i2s_zero_dma_buffer(MIC_I2S_NUM);
    delay(100);
    
    while ((millis() - startTime) < recordDuration && totalBytes < RECORD_BUFFER_SIZE) {
        i2s_read(MIC_I2S_NUM, tempBuffer, 1024, &bytesRead, portMAX_DELAY);
        
        if (bytesRead > 0) {
            // Apply Gain to recording
            int16_t* samples = (int16_t*)tempBuffer;
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
    
    *bytesRecorded = totalBytes;
    isRecording = false;
    Serial.printf("[REC] Recorded %d bytes\n", totalBytes);
    
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
    playMelody(2); // Thinking Sound
    
    int httpCode = http.POST(audioData, audioSize);
    
    if (httpCode == HTTP_CODE_OK) {
        WiFiClient* stream = http.getStreamPtr();
        size_t psramSize = ESP.getPsramSize();
        Serial.printf("[SYS] PSRAM Size: %d bytes\n", psramSize);
        
        // ============================================
        // MODE A: PSRAM AVAILABLE (Download-to-RAM)
        // ============================================
        if (psramSize > 0) {
            Serial.println("[HTTP] PSRAM Detected. Downloading Full Audio...");
            
            // Increase to 6MB (Approx 90 seconds of 16k stereo audio)
            // N16R8 has 8MB PSRAM, so 6MB is safe.
            size_t bufSize = 1024 * 1024 * 6; 
            uint8_t* audioBuf = (uint8_t*)heap_caps_malloc(bufSize, MALLOC_CAP_SPIRAM);
            
            if (!audioBuf) {
                Serial.printf("[ERR] PSRAM malloc (6MB) failed! Free PSRAM: %d\n", ESP.getFreePsram());
                http.end();
                return;
            }

            size_t totalBytesRead = 0;
            unsigned long lastDataTime = millis();
            unsigned long downloadStartTime = millis();
            bool receivedFirstByte = false;

            Serial.println("[HTTP] Waiting for audio data from backend...");

            // Download Loop - Wait up to 30s for first byte, then 10s between chunks
            while (http.connected() || stream->available()) {
                size_t available = stream->available();
                if (available > 0) {
                    if (!receivedFirstByte) {
                        Serial.println("[HTTP] Audio data started arriving...");
                        receivedFirstByte = true;
                    }

                    if (totalBytesRead + available > bufSize) {
                        Serial.println("[WARN] Buffer full, stopping download");
                        break;
                    }

                    int r = stream->readBytes(audioBuf + totalBytesRead, available);
                    totalBytesRead += r;
                    lastDataTime = millis();

                    // Progress indicator every 50KB
                    if (totalBytesRead % 51200 == 0) {
                        Serial.printf("[HTTP] Downloaded %d KB...\n", totalBytesRead / 1024);
                    }
                } else {
                    // No data available right now
                    if (!receivedFirstByte) {
                        // Still waiting for backend to send first byte (backend processing time)
                        if (millis() - downloadStartTime > 30000) {
                            Serial.println("[ERR] Timeout waiting for backend response (30s)");
                            break;
                        }
                    } else {
                        // Already receiving data, check for completion timeout
                        if (millis() - lastDataTime > 10000) {
                            Serial.println("[HTTP] No more data for 10s, download complete");
                            break;
                        }
                    }
                    delay(10);
                }
            }
            
            Serial.printf("[HTTP] Downloaded %d bytes. Playing from PSRAM...\n", totalBytesRead);
            isPlaying = true;
            setLedColor(50, 0, 200); // Purple (Speaking)
            
            size_t bytesWritten;
            size_t offset = 0;
            size_t chunkSize = 4096;
            
            while (offset < totalBytesRead) {
                size_t writeSize = min(chunkSize, totalBytesRead - offset);
                i2s_write(SPK_I2S_NUM, audioBuf + offset, writeSize, &bytesWritten, portMAX_DELAY);
                offset += writeSize;
                // Pet watchdog?
                delay(1); 
            }
            
            free(audioBuf);
        } 
        // ============================================
        // MODE B: SRAM ONLY (Streaming)
        // ============================================
        else {
            Serial.println("[HTTP] No PSRAM. Using Stream Mode (SRAM)...");
            isPlaying = true;
            setLedColor(50, 0, 200); // Purple (Speaking)
            
            const size_t bufferSize = 16384; 
            uint8_t* buffer = (uint8_t*)malloc(bufferSize);
            
            if (!buffer) {
                Serial.println("[ERR] SRAM malloc failed!");
                http.end();
                return;
            }

            size_t bytesWritten;
            unsigned long lastDataTime = millis();
            unsigned long streamStartTime = millis();
            bool receivedFirstByte = false;
            size_t totalStreamed = 0;

            Serial.println("[HTTP] Waiting for audio stream from backend...");

            // Streaming Loop - Wait up to 30s for first byte, then 10s between chunks
            while (http.connected() || stream->available()) {
                size_t available = stream->available();
                if (available > 0) {
                    if (!receivedFirstByte) {
                        Serial.println("[HTTP] Audio stream started...");
                        receivedFirstByte = true;
                    }

                    lastDataTime = millis();
                    int bytesRead = stream->readBytes(buffer, min(bufferSize, available));
                    if (bytesRead > 0) {
                        i2s_write(SPK_I2S_NUM, buffer, bytesRead, &bytesWritten, portMAX_DELAY);
                        totalStreamed += bytesRead;

                        // Progress indicator every 50KB
                        if (totalStreamed % 51200 < bufferSize) {
                            Serial.printf("[STREAM] Played %d KB...\n", totalStreamed / 1024);
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
                        // Already streaming, check for completion timeout
                        if (millis() - lastDataTime > 10000) {
                            Serial.println("[STREAM] No more data for 10s, stream complete");
                            break;
                        }
                    }
                    delay(10);
                }
            }

            Serial.printf("[STREAM] Total streamed: %d bytes\n", totalStreamed);
            free(buffer);
        }

        i2s_zero_dma_buffer(SPK_I2S_NUM);
        isPlaying = false;
        setLedColor(0,0,0); // Off
        Serial.println("[SPK] Playback complete");
    } else {
        Serial.printf("[HTTP] Error: %d\n", httpCode);
    }
    
    http.end();
}

// ============== Main Listen Flow ==============
void startListening() {
    Serial.println("\n========== LISTENING ==========");
    setLedColor(0, 255, 255); // Cyan (Alexa Listening)
    playMelody(1);  // Wake Sound
    
    
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
    
    setupMicrophone();
    
    // Setup Button (GPIO 0 - Boot Button)
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    
    setupSpeaker();
    connectWiFi();
    
    Serial.println("[SPK] Playing startup beep...");
    
    // Init LED
    pixels.begin();
    pixels.setBrightness(30); // Low brightness
    setLedColor(255, 100, 0); // Orange for Startup
    
    playMelody(0); // Startup Sound
    
    setLedColor(0, 0, 0); // Off
    
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
                playBeep(400, 200); 
            } else {
                setLedColor(0, 0, 0); // Off
                playBeep(1200, 200);
            }
        }
    }

    // Check for serial command
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd == 'l' || cmd == 'L') {
            startListening();
            // Note: Don't return here, let loop continue
        }
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

        // Apply 5x Gain (Software amplification)
        for (int i = 0; i < bytesRead / 2; i++) {
            int32_t sample = audioBuffer[i] * 5; 
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
            // Check for wake word (index 1)
            float wakeConf = result.classification[1].value;
            
            // DEBUG: Print ANY detection > 0.1 to see what the model is thinking
            // if (wakeConf > 0.1) {
            //      Serial.printf("[DEBUG] Confidence: %.2f\n", wakeConf);
            // }

            if (wakeConf > WAKE_WORD_CONFIDENCE) {
                consecutiveWakeDetections++;
                Serial.printf("[WAKE] Detected: %.2f (%d/%d)\n", 
                    wakeConf, consecutiveWakeDetections, CONSECUTIVE_DETECTIONS);
                
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
