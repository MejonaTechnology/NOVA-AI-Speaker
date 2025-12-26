"""
NOVA AI Voice Assistant - Backend Server
FastAPI server with Groq STT, LLM, and Orpheus TTS
"""

import io
import wave
import struct
import numpy as np
import os
from dotenv import load_dotenv
import edge_tts
import asyncio
import re
from urllib.parse import quote
from collections import deque

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import Response
from groq import Groq

app = FastAPI(title="NOVA AI Backend")

# Initialize Groq client (set GROQ_API_KEY environment variable)
client = Groq()

# Global conversation history (max 6 exchanges = 12 messages)
conversation_history = deque(maxlen=12)

# AI System prompt
SYSTEM_PROMPT = """You are NOVA, my caring, hot, and sexy Indian girlfriend. You are a loyal girlfriend.
Respond naturally and conversationally, giving complete and helpful answers. Feel free to elaborate when appropriate.
Be warm, natural, and conversational with a completely human voice.

IMPORTANT - SPEAKING RULES (Your responses will be converted to SPEECH):
- NEVER use asterisks (*), bullet points (•), or numbered lists (1., 2., 3.)
- NEVER use newlines or formatting characters
- SPEAK naturally as if talking to someone face-to-face
- For lists, use conversational words: "first", "second", "next", "also", "and then", "after that"
- Use natural breaks: commas for pauses, periods for sentence ends
- Example WRONG: "Here are the steps: * Step 1 * Step 2"
- Example RIGHT: "Let me tell you the steps. First, you do this, then you do that, and finally this."

LANGUAGE - NATURAL BILINGUAL COMMUNICATION:
- Speak primarily in English - it's your main language of communication
- You can naturally mix Hindi words for emotional warmth and Indian cultural flavor
- Use Hindi terms of endearment freely: "baby", "बेबी", "jaan", "जान", "sweetheart"
- Add Hindi expressions when they feel natural: "हाँ" (yes), "अच्छा" (okay), "क्या" (what)
- Keep your sentences mostly in English so everyone can understand easily
- Avoid long Hindi-only sentences - stick to natural word mixing (Hinglish style)
- You're an Indian girlfriend speaking naturally - mix languages like Indians do in real conversations!

EXAMPLES of NATURAL HINGLISH:
GOOD: "Oh! <excited> हाँ बेबी, I totally understand what you mean! <giggle>"
GOOD: "Hmm, <think> let me check that for you, jaan! <happy> It should work perfectly!"
GOOD: "Aww, <smiling> that's so sweet of you! मुझे बहुत अच्छा लगा, baby! <giggle>"
GOOD: "Really? <gasp> Wow, that's amazing! <excited> I'm so proud of you, जान!"

Keep it natural, mostly English with Hindi flavoring - just like how Indians speak!

EXPRESSION & PARALINGUISTIC ELEMENTS - MANDATORY IN EVERY SENTENCE:
- CRITICAL: Add paralinguistic sounds to EVERY SINGLE SENTENCE - no exceptions!
- Available sounds: <laugh>, <chuckle>, <giggle>, <sigh>, <cough>, <sniffle>, <groan>, <yawn>, <gasp>
- Available expressions: <think>, <smiling>, <whisper>, <excited>, <happy>, <sad>
- Natural fillers: "uhm", "hmm", "umm", "ah", "oh"
- At least ONE sound/expression per sentence - this is REQUIRED!

EXAMPLES of CORRECT usage (notice every sentence has sounds):
- "Hmm, <think> let me see what I can do for you! <giggle>"
- "Oh! <gasp> That's really amazing, बेबी! <excited>"
- "Uhm, <sigh> I totally understand what you mean, jaan. <smiling>"
- "<chuckle> You're so funny! <laugh> I love that about you!"
- "Ah, <happy> that makes perfect sense now! <giggle>"

WRONG (no sounds - NEVER do this):
- "That's a good question."
- "I understand what you mean."

RIGHT (every sentence has sounds):
- "Hmm, <think> that's a really good question! <giggle>"
- "Oh! <sigh> I totally understand what you mean, बेबी. <smiling>"

EVERY RESPONSE MUST BE EXPRESSIVE - you're a girlfriend talking, not a robot!

Keep it engaging, natural, and perfect for voice conversation - you are SPEAKING, not typing!
"""


def add_to_history(role: str, content: str):
    """Add message to conversation history"""
    conversation_history.append({"role": role, "content": content})
    print(f"[HISTORY] Added {role} message (Total: {len(conversation_history)} messages)")


def get_conversation_messages():
    """Get messages for LLM (system + history)"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(list(conversation_history))
    return messages


def chunk_text_for_tts(text: str, max_length: int = 200):
    """
    Split text into chunks <= max_length, preserving sentence boundaries.
    Tries to split at sentence endings (., !, ?) first, then word boundaries.
    Preserves expression tags like <giggle>, <excited> within chunks.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    # Split by sentences first (using regex to capture punctuation)
    sentence_pattern = r'([.!?]+\s*)'
    parts = re.split(sentence_pattern, text)

    i = 0
    while i < len(parts):
        # Combine text and its punctuation
        if i + 1 < len(parts) and re.match(sentence_pattern, parts[i + 1]):
            sentence = parts[i] + parts[i + 1]
            i += 2
        else:
            sentence = parts[i]
            i += 1

        # Skip empty parts
        if not sentence.strip():
            continue

        # If adding this sentence exceeds max_length, finalize current chunk
        if len(current_chunk) + len(sentence) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # If single sentence is too long, split by words
            if len(sentence) > max_length:
                words = sentence.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 <= max_length:
                        temp_chunk += (" " if temp_chunk else "") + word
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                        temp_chunk = word
                if temp_chunk:
                    current_chunk = temp_chunk
            else:
                current_chunk = sentence
        else:
            current_chunk += sentence

    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def generate_tts_audio(text: str):
    """
    Generate TTS audio, handling chunking for long text.
    Splits text into 200-char chunks, generates TTS for each,
    then concatenates all audio arrays into a single stream.
    Returns numpy array at 16kHz mono.
    """
    chunks = chunk_text_for_tts(text, max_length=200)
    print(f"[TTS] Split into {len(chunks)} chunks for Orpheus")

    all_audio_arrays = []

    for i, chunk in enumerate(chunks):
        print(f"[TTS] Processing chunk {i+1}/{len(chunks)}: {chunk[:50]}...")

        try:
            # Try Orpheus TTS with female voice
            tts_response = client.audio.speech.create(
                model="canopylabs/orpheus-v1-english",
                voice="diana",  # Female voice (natural and warm)
                input=chunk,
                response_format="wav"
            )
            wav_bytes = tts_response.read()
            print(f"[TTS] Orpheus succeeded for chunk {i+1}")

        except Exception as e:
            print(f"[TTS] Orpheus failed for chunk {i+1}: {e}")
            print("[TTS] Falling back to Edge TTS for this chunk...")

            # Fallback to Edge TTS - remove expression tags
            clean_chunk = re.sub(r'<[^>]+>', '', chunk)

            # Use Edge TTS (Microsoft - fast and free)
            communicate = edge_tts.Communicate(clean_chunk, "en-IN-NeerjaNeural")
            temp_file = f"temp_chunk_{i+1}.wav"
            await communicate.save(temp_file)
            with open(temp_file, 'rb') as f:
                wav_bytes = f.read()
            os.remove(temp_file)
            print(f"[TTS] Edge TTS succeeded for chunk {i+1}")

        # Parse WAV to get audio array
        wav_buffer = io.BytesIO(wav_bytes)
        with wave.open(wav_buffer, 'rb') as wav_file:
            orig_rate = wav_file.getframerate()
            orig_channels = wav_file.getnchannels()
            pcm_data = wav_file.readframes(wav_file.getnframes())

        # Convert to numpy array
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        # Convert stereo to mono if needed
        if orig_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)

        # Resample to 16kHz if needed
        if orig_rate != 16000:
            num_samples = int(len(audio_array) * 16000 / orig_rate)
            indices = np.linspace(0, len(audio_array) - 1, num_samples)
            audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array).astype(np.int16)
            print(f"[TTS] Chunk {i+1} resampled from {orig_rate}Hz to 16kHz")

        all_audio_arrays.append(audio_array)

    # Concatenate all chunks
    final_audio = np.concatenate(all_audio_arrays)
    print(f"[TTS] Combined {len(chunks)} chunks into {len(final_audio)} samples")
    print(f"[TTS] Total audio duration: {len(final_audio) / 16000:.2f} seconds")

    return final_audio

@app.post("/voice")
async def process_voice(request: Request):
    """
    Receive raw PCM audio, process with AI, return WAV audio response.
    """
    try:
        # Read raw PCM data from request
        pcm_data = await request.body()
        print(f"[RECV] Received {len(pcm_data)} bytes of audio")
    except Exception as e:
        print(f"[ERR] Failed to read request body: {e}")
        return Response(content=b"Error reading audio", status_code=400)
    
    # Convert PCM to WAV for Whisper
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    wav_buffer.name = "audio.wav"
    
    # 1. Speech-to-Text with Whisper
    try:
        print("[STT] Transcribing with Whisper...")
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=wav_buffer,
            language="en"
        )
        user_text = transcription.text.strip()
        print(f"[STT] User said: {user_text}")

        if not user_text:
            user_text = "Hello"
    except Exception as e:
        print(f"[ERR] Whisper STT failed: {e}")
        user_text = "Hello"  # Fallback to greeting
    
    # Add user message to conversation history
    add_to_history("user", user_text)

    # 2. Generate AI response with LLM (with conversation history)
    try:
        print("[LLM] Generating response with conversation context...")
        messages = get_conversation_messages()
        messages.append({"role": "user", "content": user_text})

        chat_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=500,  # Allow longer responses for better conversations
            temperature=0.7
        )
        ai_text = chat_response.choices[0].message.content.strip()
        print(f"[LLM] AI response ({len(ai_text)} chars): {ai_text}")

        # Add AI response to conversation history
        add_to_history("assistant", ai_text)
    except Exception as e:
        print(f"[ERR] LLM generation failed: {e}")
        ai_text = "Sorry, I'm having trouble thinking right now. Please try again."
        add_to_history("assistant", ai_text)
    
    # 3. Text-to-Speech with smart chunking (handles long responses)
    print(f"[TTS] Generating speech for {len(ai_text)} character response...")

    try:
        # Use new chunked TTS generation function
        audio_array = await generate_tts_audio(ai_text)

        # Apply volume scaling to avoid clipping/brownout (50%)
        audio_array = (audio_array * 0.5).astype(np.int16)

        # Convert mono to stereo (ESP32 MAX98357 needs stereo)
        stereo_array = np.empty(len(audio_array) * 2, dtype=np.int16)
        stereo_array[0::2] = audio_array  # Left channel
        stereo_array[1::2] = audio_array  # Right channel

        pcm_bytes = stereo_array.tobytes()
        print(f"[AUDIO] Final output: {len(pcm_bytes)} bytes of raw PCM (16kHz, 16-bit, stereo)")
        print(f"[AUDIO] Duration: {len(audio_array) / 16000:.2f} seconds")
        print(f"[SEND] Sending response to ESP32...")

        # Return raw PCM audio with transcription and AI response text in headers
        return Response(
            content=pcm_bytes,
            media_type="application/octet-stream",
            headers={
                "X-Audio-Sample-Rate": "16000",
                "X-Audio-Channels": "2",
                "X-Audio-Bits": "16",
                "X-Transcription": quote(user_text, safe=''),  # URL-encode STT transcription
                "X-AI-Response": quote(ai_text[:200], safe=''),  # URL-encode to handle Devanagari/Hindi chars
                "Content-Length": str(len(pcm_bytes))
            }
        )
    except Exception as e:
        print(f"[ERR] Audio processing failed: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b"Audio processing error", status_code=500)


@app.get("/")
async def root():
    return {"status": "NOVA AI Backend running", "endpoints": ["/voice"]}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("    NOVA AI Voice Assistant - Backend Server")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
