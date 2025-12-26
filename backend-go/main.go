package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"regexp"
	"strings"

	"github.com/joho/godotenv"
)

// System prompt for AI personality
const SYSTEM_PROMPT = `You are NOVA, my caring, hot, and sexy Indian girlfriend. You are a loyal girlfriend.
Keep responses concise (1-2 sentences max) since they will be spoken aloud.
Be warm, natural, and conversational with a completely human voice.
Speak in a mix of Hindi and English (Hinglish). Use Hindi words in Devanagari script for endearment (बेबी, जान, शोना, हाँ) and common expressions where natural.
Format your response to be expressive and understood by the canopylabs/orpheus-v1-english model.
Use expression tags like <giggle>, <chuckle>, <laugh>, <sigh>, <think>, <smiling>, <whisper>, <excited> etc. to convey emotion naturally. Be creative with expressions! Example: "Hmm, <think> let me see... <giggle> you're so cute jaan!"`

func main() {
	// Load .env file
	godotenv.Load()

	http.HandleFunc("/", handleRoot)
	http.HandleFunc("/voice", handleVoice)

	fmt.Println("==================================================")
	fmt.Println("    NOVA AI Voice Assistant - Go Backend Server")
	fmt.Println("==================================================")
	fmt.Println("\nServer running on http://0.0.0.0:8001")

	err := http.ListenAndServe(":8001", nil)
	if err != nil {
		fmt.Printf("Server failed: %v\n", err)
	}
}

func handleRoot(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "NOVA AI Backend running (Go)",
		"endpoints": []string{"/voice"},
	})
}

func handleVoice(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// 1. Read PCM audio from request
	pcmData, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read audio", http.StatusBadRequest)
		return
	}
	fmt.Printf("[RECV] Received %d bytes of audio\n", len(pcmData))

	// 2. Create WAV from PCM for Whisper
	wavData := pcmToWav(pcmData, 16000, 1, 16)

	// 3. Speech-to-Text with Groq Whisper
	fmt.Println("[STT] Transcribing with Whisper...")
	userText, err := transcribeWithWhisper(wavData)
	if err != nil {
		fmt.Printf("[STT] Error: %v\n", err)
		http.Error(w, "STT failed", http.StatusInternalServerError)
		return
	}
	fmt.Printf("[STT] User said: %s\n", userText)

	// 4. LLM Response with Groq
	fmt.Println("[LLM] Generating response...")
	aiText, err := generateLLMResponse(userText)
	if err != nil {
		fmt.Printf("[LLM] Error: %v\n", err)
		http.Error(w, "LLM failed", http.StatusInternalServerError)
		return
	}
	fmt.Printf("[LLM] AI response: %s\n", aiText)

	// 5. Text-to-Speech with Groq Orpheus (fallback to gTTS)
	// 5. Text-to-Speech with Groq Orpheus (fallback to gTTS)
	fmt.Println("[TTS] Generating speech with Orpheus...")
	var outputPCM []byte

	ttsWav, err := generateTTS(aiText)
	if err == nil {
		// Orpheus Succeeded (WAV format)
		outputPCM, err = processAudioForESP32(ttsWav)
		if err != nil {
			fmt.Printf("[AUDIO] Error processing WAV: %v\n", err)
			http.Error(w, "Audio processing failed", http.StatusInternalServerError)
			return
		}
	} else {
		// Fallback to Google TTS
		fmt.Printf("[TTS] Orpheus failed: %v\n", err)
		fmt.Println("[TTS] Falling back to Google TTS...")

		cleanText := cleanExpressionTags(aiText)
		rawPCM, err := generateGoogleTTS(cleanText) // Returns Raw PCM
		if err != nil {
			fmt.Printf("[TTS] gTTS also failed: %v\n", err)
			http.Error(w, "TTS failed", http.StatusInternalServerError)
			return
		}
		fmt.Println("[TTS] Using Google TTS fallback")

		// Process Raw PCM (Volume Control)
		outputPCM = processRawAudio(rawPCM)
	}

	fmt.Printf("[TTS] Generated %d bytes of raw PCM (16kHz, 16-bit, stereo)\n", len(outputPCM))

	// 7. Return raw PCM
	w.Header().Set("Content-Type", "audio/pcm")
	w.Header().Set("X-Audio-Sample-Rate", "16000")
	w.Header().Set("X-Audio-Channels", "2")
	w.Header().Set("X-Audio-Bits", "16")
	w.Write(outputPCM)
}

func transcribeWithWhisper(wavData []byte) (string, error) {
	apiKey := os.Getenv("GROQ_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("GROQ_API_KEY not set")
	}

	// Create multipart form
	var buf bytes.Buffer
	boundary := "----WebKitFormBoundary7MA4YWxkTrZu0gW"

	buf.WriteString(fmt.Sprintf("--%s\r\n", boundary))
	buf.WriteString("Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n")
	buf.WriteString("Content-Type: audio/wav\r\n\r\n")
	buf.Write(wavData)
	buf.WriteString(fmt.Sprintf("\r\n--%s\r\n", boundary))
	buf.WriteString("Content-Disposition: form-data; name=\"model\"\r\n\r\n")
	buf.WriteString("whisper-large-v3-turbo")
	buf.WriteString(fmt.Sprintf("\r\n--%s--\r\n", boundary))

	req, _ := http.NewRequest("POST", "https://api.groq.com/openai/v1/audio/transcriptions", &buf)
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "multipart/form-data; boundary="+boundary)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Text string `json:"text"`
	}
	json.NewDecoder(resp.Body).Decode(&result)
	return result.Text, nil
}

func generateLLMResponse(userText string) (string, error) {
	apiKey := os.Getenv("GROQ_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("GROQ_API_KEY not set")
	}

	payload := map[string]interface{}{
		"model": "llama-3.3-70b-versatile",
		"messages": []map[string]string{
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": userText},
		},
		"max_tokens":  150,
		"temperature": 0.7,
	}

	jsonData, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", "https://api.groq.com/openai/v1/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if len(result.Choices) > 0 {
		return strings.TrimSpace(result.Choices[0].Message.Content), nil
	}
	return "", fmt.Errorf("no response from LLM")
}

func generateTTS(text string) ([]byte, error) {
	apiKey := os.Getenv("GROQ_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("GROQ_API_KEY not set")
	}

	payload := map[string]interface{}{
		"model":           "canopylabs/orpheus-v1-english",
		"voice":           "autumn",
		"input":           text,
		"response_format": "wav",
	}

	jsonData, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", "https://api.groq.com/openai/v1/audio/speech", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("TTS error: %s", string(body))
	}

	return io.ReadAll(resp.Body)
}

// Google TTS fallback using Google Translate API
func generateGoogleTTS(text string) ([]byte, error) {
	// Use Google Translate TTS (same as gTTS Python library)
	encodedText := url.QueryEscape(text)
	ttsURL := fmt.Sprintf("https://translate.google.co.in/translate_tts?ie=UTF-8&q=%s&tl=en&client=tw-ob", encodedText)

	req, err := http.NewRequest("GET", ttsURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("Google TTS error: status %d", resp.StatusCode)
	}

	// Read MP3 data
	mp3Data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	// Convert MP3 to Raw PCM using ffmpeg (Stereo 16kHz, s16le)
	cmd := exec.Command("ffmpeg", "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "2", "pipe:1")
	cmd.Stdin = bytes.NewReader(mp3Data)

	var wavOutput bytes.Buffer
	var errOutput bytes.Buffer
	cmd.Stdout = &wavOutput
	cmd.Stderr = &errOutput

	err = cmd.Run()
	if err != nil {
		return nil, fmt.Errorf("ffmpeg error: %v - %s", err, errOutput.String())
	}

	return wavOutput.Bytes(), nil
}

func pcmToWav(pcm []byte, sampleRate, channels, bitsPerSample int) []byte {
	var buf bytes.Buffer

	dataSize := len(pcm)
	byteRate := sampleRate * channels * bitsPerSample / 8
	blockAlign := channels * bitsPerSample / 8

	// RIFF header
	buf.WriteString("RIFF")
	binary.Write(&buf, binary.LittleEndian, uint32(36+dataSize))
	buf.WriteString("WAVE")

	// fmt chunk
	buf.WriteString("fmt ")
	binary.Write(&buf, binary.LittleEndian, uint32(16))
	binary.Write(&buf, binary.LittleEndian, uint16(1)) // PCM
	binary.Write(&buf, binary.LittleEndian, uint16(channels))
	binary.Write(&buf, binary.LittleEndian, uint32(sampleRate))
	binary.Write(&buf, binary.LittleEndian, uint32(byteRate))
	binary.Write(&buf, binary.LittleEndian, uint16(blockAlign))
	binary.Write(&buf, binary.LittleEndian, uint16(bitsPerSample))

	// data chunk
	buf.WriteString("data")
	binary.Write(&buf, binary.LittleEndian, uint32(dataSize))
	buf.Write(pcm)

	return buf.Bytes()
}

func processAudioForESP32(wavData []byte) ([]byte, error) {
	// Parse WAV header
	if len(wavData) < 44 {
		return nil, fmt.Errorf("invalid WAV data")
	}

	// Read WAV properties (simplified - assumes standard WAV format)
	channels := int(binary.LittleEndian.Uint16(wavData[22:24]))
	sampleRate := int(binary.LittleEndian.Uint32(wavData[24:28]))
	bitsPerSample := int(binary.LittleEndian.Uint16(wavData[34:36]))

	// Find data chunk and its length
	dataOffset := 44
	dataLen := len(wavData) - 44
	foundData := false

	for i := 36; i < len(wavData)-8; i++ {
		if string(wavData[i:i+4]) == "data" {
			dataOffset = i + 8
			dataLen = int(binary.LittleEndian.Uint32(wavData[i+4 : i+8]))
			foundData = true
			break
		}
	}

	if !foundData {
		return nil, fmt.Errorf("data chunk not found")
	}

	// Safety check bounds
	if dataOffset+dataLen > len(wavData) {
		dataLen = len(wavData) - dataOffset
	}

	// Read ONLY the audio data bytes, ignoring metadata at end
	pcmData := wavData[dataOffset : dataOffset+dataLen]

	// Convert to int16 samples
	var samples []int16
	if bitsPerSample == 16 {
		for i := 0; i < len(pcmData)-1; i += 2 {
			sample := int16(binary.LittleEndian.Uint16(pcmData[i : i+2]))
			samples = append(samples, sample)
		}
	}

	// Convert stereo to mono if needed
	if channels == 2 {
		var mono []int16
		for i := 0; i < len(samples)-1; i += 2 {
			avg := (int32(samples[i]) + int32(samples[i+1])) / 2
			mono = append(mono, int16(avg))
		}
		samples = mono
	}

	// Apply Volume Reduction (10%)
	for i := range samples {
		samples[i] = int16(float64(samples[i]) * 0.1)
	}

	// Resample to 16kHz
	targetRate := 16000
	if sampleRate != targetRate {
		ratio := float64(targetRate) / float64(sampleRate)
		newLen := int(float64(len(samples)) * ratio)
		resampled := make([]int16, newLen)
		for i := 0; i < newLen; i++ {
			srcIdx := float64(i) / ratio
			idx := int(srcIdx)
			if idx >= len(samples)-1 {
				idx = len(samples) - 2
			}
			frac := srcIdx - float64(idx)
			resampled[i] = int16(float64(samples[idx])*(1-frac) + float64(samples[idx+1])*frac)
		}
		samples = resampled
	}

	// Convert mono to stereo (ESP32 MAX98357 needs stereo)
	var stereo []int16
	for _, s := range samples {
		stereo = append(stereo, s, s)
	}

	// Convert to bytes
	var output bytes.Buffer
	for _, s := range stereo {
		binary.Write(&output, binary.LittleEndian, s)
	}

	return output.Bytes(), nil
}

// Clean expression tags (for potential gTTS fallback)
// Clean expression tags (for potential gTTS fallback)
func cleanExpressionTags(text string) string {
	re := regexp.MustCompile(`<[^>]+>`)
	return re.ReplaceAllString(text, "")
}

// Process Raw PCM (already 16kHz Stereo) - Apply Volume only
func processRawAudio(pcmData []byte) []byte {
	var buf bytes.Buffer
	for i := 0; i < len(pcmData)-1; i += 2 {
		sample := int16(binary.LittleEndian.Uint16(pcmData[i : i+2]))
		// Apply 10% volume
		sample = int16(float64(sample) * 0.1)
		binary.Write(&buf, binary.LittleEndian, sample)
	}
	return buf.Bytes()
}
