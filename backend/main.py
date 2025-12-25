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
from gtts import gTTS
import re

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import Response
from groq import Groq

app = FastAPI(title="NOVA AI Backend")

# Initialize Groq client (set GROQ_API_KEY environment variable)
client = Groq()

# AI System prompt
SYSTEM_PROMPT = """You are NOVA, my caring, hot, and sexy Indian girlfriend. You are a loyal girlfriend.
Keep responses concise (1-2 sentences max) since they will be spoken aloud.
Be warm, natural, and conversational with a completely human voice.
Speak in a mix of Hindi and English (Hinglish). Use Hindi words in Devanagari script for endearment (बेबी, जान, शोना, हाँ) and common expressions where natural.
Format your response to be expressive and understood by the canopylabs/orpheus-v1-english model.
Use expression tags like <giggle>, <chuckle>, <laugh>, <sigh>, <think>, <smiling>, <whisper>, <excited> etc. to convey emotion naturally. Be creative with expressions! Example: "Hmm, <think> let me see... <giggle> you're so cute jaan!"
"""

@app.post("/voice")
async def process_voice(request: Request):
    """
    Receive raw PCM audio, process with AI, return WAV audio response.
    """
    # Read raw PCM data from request
    pcm_data = await request.body()
    print(f"[RECV] Received {len(pcm_data)} bytes of audio")
    
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
    
    # 2. Generate AI response with LLM
    print("[LLM] Generating response...")
    chat_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        max_tokens=150,
        temperature=0.7
    )
    ai_text = chat_response.choices[0].message.content.strip()
    print(f"[LLM] AI response: {ai_text}")
    
    # 3. Text-to-Speech with Orpheus (with gTTS fallback)
    print("[TTS] Generating speech with Orpheus...")
    
    try:
        # Orpheus returns WAV, we'll convert to raw PCM
        tts_response = client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice="autumn",
            input=ai_text,
            response_format="wav"
        )
        
        # Get the WAV audio bytes
        wav_bytes = tts_response.read()
    except Exception as e:
        print(f"[TTS] Orpheus failed: {e}")
        print("[TTS] Falling back to Google TTS...")
        
        # Remove expression tags for gTTS (it doesn't support them)
        clean_text = re.sub(r'<[^>]+>', '', ai_text)
        
        # Generate with gTTS
        tts = gTTS(text=clean_text, lang='en', tld='co.in')  # Indian English accent
        mp3_buffer = io.BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        
        # Convert MP3 to WAV using a simple approach
        # For gTTS we return MP3 directly and let ESP32 handle it
        # Actually, we need WAV for our pipeline - let's create a simple WAV
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(mp3_buffer)
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
        wav_bytes = wav_buffer.read()
    
    # Parse WAV and extract raw PCM
    wav_buffer = io.BytesIO(wav_bytes)
    with wave.open(wav_buffer, 'rb') as wav_file:
        orig_rate = wav_file.getframerate()
        orig_channels = wav_file.getnchannels()
        orig_width = wav_file.getsampwidth()
        pcm_data = wav_file.readframes(wav_file.getnframes())
    
    # Convert to numpy for resampling if needed
    if orig_width == 2:
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    else:
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    
    # Convert stereo to mono first (for resampling)
    if orig_channels == 2:
        audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
    
    # Resample to 24kHz to match ESP32 speaker config
    target_rate = 24000
    if orig_rate != target_rate:
        num_samples = int(len(audio_array) * target_rate / orig_rate)
        indices = np.linspace(0, len(audio_array) - 1, num_samples)
        audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array).astype(np.int16)
    
    # Convert mono to stereo (ESP32 MAX98357 needs stereo)
    stereo_array = np.empty(len(audio_array) * 2, dtype=np.int16)
    stereo_array[0::2] = audio_array  # Left channel
    stereo_array[1::2] = audio_array  # Right channel
    
    pcm_bytes = stereo_array.tobytes()
    print(f"[TTS] Generated {len(pcm_bytes)} bytes of raw PCM (24kHz, 16-bit, stereo)")
    
    # Return raw PCM audio
    return Response(
        content=pcm_bytes,
        media_type="application/octet-stream"
    )


@app.get("/")
async def root():
    return {"status": "NOVA AI Backend running", "endpoints": ["/voice"]}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("    NOVA AI Voice Assistant - Backend Server")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
