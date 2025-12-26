# Conversation History and Smart TTS Chunking

## Overview

This document describes the conversation history and smart TTS chunking features implemented in the NOVA AI Voice Assistant backend.

## Features

### 1. Conversation History (6 Exchanges)

The backend now maintains conversation context by storing the last 6 exchanges (12 messages total) in memory.

**Implementation:**
```python
from collections import deque

# Global conversation history (max 6 exchanges = 12 messages)
conversation_history = deque(maxlen=12)
```

**How it works:**
- Each conversation exchange consists of 2 messages: user message + assistant response
- The deque automatically maintains only the last 12 messages (6 exchanges)
- When a new message is added and the limit is reached, the oldest message is automatically removed
- The conversation history is sent to the LLM for context-aware responses

**Example conversation flow:**
```
Exchange 1: User: "What's your name?" → AI: "I'm NOVA, your girlfriend!"
Exchange 2: User: "What did I just ask?" → AI: "You asked about my name, jaan!"
...
Exchange 6: User: "What was my first question?" → AI: "You asked what my name was!"
Exchange 7: User: "Tell me more" → AI: [Exchange 1 is now removed from history]
```

### 2. Smart Text Chunking for TTS

The Orpheus TTS API has a 200-character limit per request. To handle longer AI responses, we implement smart text chunking.

**Chunking Strategy:**
1. **Sentence boundary split (preferred):** Split at sentence endings (`.`, `!`, `?`)
2. **Word boundary split (fallback):** If a single sentence exceeds 200 chars, split at word boundaries
3. **Expression tag preservation:** Keep expression tags like `<giggle>`, `<excited>` within chunks

**Implementation:**
```python
def chunk_text_for_tts(text: str, max_length: int = 200):
    """
    Split text into chunks <= max_length, preserving sentence boundaries.
    Tries to split at sentence endings (., !, ?) first, then word boundaries.
    Preserves expression tags like <giggle>, <excited> within chunks.
    """
```

**Example:**
```
Input (339 chars):
"<excited> Oh my god, you won't believe what happened today! <giggle> I was walking to the market when I saw the cutest puppy ever. It was so adorable and fluffy. <smiling> The owner let me pet it for a while. It reminded me of the time we talked about getting a pet together. <whisper> Maybe we should get one soon, what do you think jaan?"

Output (2 chunks):
Chunk 1 (161 chars): "<excited> Oh my god, you won't believe what happened today! <giggle> I was walking to the market when I saw the cutest puppy ever. It was so adorable and fluffy."
Chunk 2 (177 chars): "<smiling> The owner let me pet it for a while. It reminded me of the time we talked about getting a pet together. <whisper> Maybe we should get one soon, what do you think jaan?"
```

### 3. Multi-Chunk TTS Generation

For each chunk, the system:
1. Sends the chunk to Orpheus TTS API
2. If Orpheus fails, falls back to gTTS (removing expression tags)
3. Processes the WAV audio to PCM format
4. Resamples to 16kHz if needed
5. Concatenates all chunk audio arrays into a single stream

**Implementation:**
```python
def generate_tts_audio(text: str):
    """
    Generate TTS audio, handling chunking for long text.
    Splits text into 200-char chunks, generates TTS for each,
    then concatenates all audio arrays into a single stream.
    Returns numpy array at 16kHz mono.
    """
```

**Audio Processing Pipeline:**
```
Text → Chunk 1 → Orpheus TTS → WAV → PCM → Resample 16kHz → Array 1
    → Chunk 2 → Orpheus TTS → WAV → PCM → Resample 16kHz → Array 2
    → Chunk 3 → Orpheus TTS → WAV → PCM → Resample 16kHz → Array 3
    → Concatenate(Array 1, Array 2, Array 3) → Final Audio → ESP32
```

## API Changes

### `/voice` Endpoint

**Enhanced flow:**
1. Receive PCM audio from ESP32
2. Convert to WAV and transcribe with Whisper STT
3. **Add user message to conversation history**
4. **Generate AI response with full conversation context**
5. **Add AI response to conversation history**
6. **Generate TTS audio with smart chunking**
7. Convert to PCM stereo and send back to ESP32

**Request:** Raw PCM audio (16kHz, 16-bit, mono)

**Response:** Raw PCM audio (16kHz, 16-bit, stereo)

**Headers:**
- `X-Audio-Sample-Rate`: "16000"
- `X-Audio-Channels`: "2"
- `X-Audio-Bits`: "16"
- `X-Transcription`: URL-encoded user speech transcription
- `X-AI-Response`: URL-encoded AI response text (first 200 chars)
- `Content-Length`: Size of PCM data in bytes

## Console Output

The backend now provides detailed logging for conversation history and TTS chunking:

```
[RECV] Received 128000 bytes of audio
[STT] Transcribing with Whisper...
[STT] User said: Tell me a long story about your day
[HISTORY] Added user message (Total: 5 messages)
[LLM] Generating response with conversation context...
[LLM] AI response (342 chars): <excited> Oh jaan, you won't believe what happened...
[HISTORY] Added assistant message (Total: 6 messages)
[TTS] Generating speech for 342 character response...
[TTS] Split into 2 chunks for Orpheus
[TTS] Processing chunk 1/2: <excited> Oh jaan, you won't believe what happ...
[TTS] Orpheus succeeded for chunk 1
[TTS] Processing chunk 2/2: <whisper> I missed you so much today, can't wai...
[TTS] Orpheus succeeded for chunk 2
[TTS] Chunk 2 resampled from 24000Hz to 16kHz
[TTS] Combined 2 chunks into 54720 samples
[TTS] Total audio duration: 3.42 seconds
[AUDIO] Final output: 219264 bytes of raw PCM (16kHz, 16-bit, stereo)
[AUDIO] Duration: 3.42 seconds
[SEND] Sending response to ESP32...
```

## Testing

### Unit Tests

Run the test suite to verify chunking algorithm:
```bash
cd backend
python test_chunking.py
```

**Test Cases:**
1. Short text (no chunking needed)
2. Long text with multiple sentences (sentence boundary split)
3. Very long single sentence (word boundary split)
4. Mixed Hindi and English with expression tags
5. Conversation history with deque (12 message limit)

### Integration Testing

Test conversation continuity:
```bash
# Start the backend server
python main.py

# Test conversation flow with ESP32 or API client
1. Say: "What's your name?"
2. Say: "What did I just ask you?"  # Should remember previous question
3. Say: "Tell me a long story"      # Should handle chunking
4. Say: "What was my first question?" # Should remember within 6 exchanges
```

## Performance Considerations

### Memory Usage
- Conversation history: ~12 messages × avg 100 chars = ~1.2 KB per session
- Multiple sessions: Linear growth with number of concurrent users
- **Recommendation:** For production, consider implementing per-user session storage

### Latency Impact
- Each TTS chunk adds ~200-500ms latency (Orpheus API call + processing)
- 2-chunk response: ~400-1000ms additional latency vs single chunk
- 3-chunk response: ~600-1500ms additional latency vs single chunk
- **Trade-off:** Longer responses provide better user experience despite added latency

### Audio Quality
- Each chunk is independently processed and resampled to 16kHz
- Concatenation is seamless (no gaps or clicks)
- Expression tags are preserved in each chunk for natural speech

## Future Enhancements

### Potential Improvements
1. **Per-user session management:** Store conversation history per user ID
2. **Persistent storage:** Save conversation history to database for long-term context
3. **Configurable history limit:** Allow users to adjust conversation memory depth
4. **Parallel TTS generation:** Generate multiple chunks in parallel for lower latency
5. **Streaming TTS:** Send audio chunks as they're generated (ESP32 needs streaming support)
6. **Smart chunk merging:** Combine short adjacent chunks to reduce API calls

### API Optimization
- Implement caching for common TTS responses
- Use connection pooling for Groq API calls
- Add retry logic with exponential backoff for failed TTS requests

## Troubleshooting

### Issue: AI doesn't remember previous conversation
**Cause:** Conversation history might be cleared on server restart
**Solution:** Conversation history is in-memory. For persistent memory, implement database storage.

### Issue: Long responses are truncated
**Cause:** Old implementation truncated to 200 chars
**Solution:** Updated! Now uses smart chunking to handle full response length.

### Issue: Audio has gaps between chunks
**Cause:** Incorrect array concatenation or resampling
**Solution:** Verify all chunks are resampled to same rate (16kHz) before concatenation.

### Issue: Expression tags don't work in gTTS fallback
**Cause:** gTTS doesn't support expression tags
**Solution:** Expression tags are automatically removed for gTTS fallback.

## Code References

**Main Implementation Files:**
- `backend/main.py` - Main backend implementation
- `backend/test_chunking.py` - Unit tests for chunking algorithm

**Key Functions:**
- `add_to_history(role, content)` - Add message to conversation history
- `get_conversation_messages()` - Get messages for LLM with conversation context
- `chunk_text_for_tts(text, max_length)` - Smart text chunking for TTS
- `generate_tts_audio(text)` - Multi-chunk TTS generation with concatenation

**Dependencies:**
- `collections.deque` - Efficient conversation history with automatic size limiting
- `numpy` - Audio array manipulation and concatenation
- `re` - Regular expressions for sentence boundary detection

## Version History

**v1.0.0 (2025-12-27):**
- Initial implementation of conversation history
- Smart text chunking for TTS
- Multi-chunk TTS generation
- Seamless audio concatenation
- Comprehensive test suite

---

For questions or issues, refer to the main project README or create an issue on GitHub.
