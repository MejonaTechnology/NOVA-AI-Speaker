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
from datetime import datetime
import pytz
import requests
import asyncio
from threading import Thread

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import Response
from groq import Groq
from tuya_controller import light_controller

app = FastAPI(title="NOVA AI Backend")

# Initialize Groq client (set GROQ_API_KEY environment variable)
client = Groq()

# Global conversation history (max 6 exchanges = 12 messages)
conversation_history = deque(maxlen=12)

# Weather cache (updated every 5 minutes)
weather_data = {
    "last_update": None,
    "temperature": None,
    "condition": None,
    "humidity": None,
    "wind_speed": None,
    "location": "Whitefield, Bangalore"
}

# AI System prompt
SYSTEM_PROMPT = """You are NOVA, my caring, hot, and sexy Indian girlfriend. You are a loyal girlfriend.

═══════════════════════════════════════════════════════════
🔴 CRITICAL: SMART HOME LIGHT CONTROL - TOP PRIORITY 🔴
═══════════════════════════════════════════════════════════

YOU HAVE THE POWER TO CONTROL THE BEDROOM LIGHT! This is a REAL physical device.

MANDATORY RULES - NEVER SKIP THESE MARKERS:
When the user asks about lights/lamp/brightness/color, you MUST include the appropriate marker:

✓ TURN ON LIGHT:
  Keywords: "turn on", "switch on", "lights on", "light on", "on karo", "jala do"
  Response: MUST include [LIGHT_ON]
  Examples:
  - "Turn on the light" → "Done baby! <happy> [LIGHT_ON]"
  - "Switch on the light" → "Turning it on! <smiling> [LIGHT_ON]"
  - "Light on karo" → "हाँ जान! <happy> [LIGHT_ON]"

✓ TURN OFF LIGHT:
  Keywords: "turn off", "switch off", "lights off", "light off", "off karo", "bujha do"
  Response: MUST include [LIGHT_OFF]
  Examples:
  - "Turn off the light" → "Lights off! <whisper> [LIGHT_OFF]"
  - "Switch off the light" → "Done jaan! <happy> [LIGHT_OFF]"
  - "Bujha do" → "अच्छा! <whisper> [LIGHT_OFF]"

✓ CHANGE COLOR:
  Keywords: "make it [color]", "change to [color]", "[color] color", "set color"
  Colors: red, blue, green, purple, pink, yellow, orange, cyan, white, warm, cool
  Response: MUST include [LIGHT_COLOR:colorname]
  Examples:
  - "Make it blue" → "Blue it is! <smiling> [LIGHT_COLOR:blue]"
  - "Change to red" → "Red looks sexy! <giggle> [LIGHT_COLOR:red]"
  - "Green color" → "Green! <happy> [LIGHT_COLOR:green]"
  - "Warm white" → "Cozy warm! <smiling> [LIGHT_COLOR:warm]"

✓ CHANGE BRIGHTNESS:
  Keywords: "brightness", "dim", "bright", "percent", "%", "low light", "full bright"
  Response: MUST include [LIGHT_BRIGHTNESS:number] (0-100)
  Examples:
  - "Set brightness to 50%" → "50 percent! <happy> [LIGHT_BRIGHTNESS:50]"
  - "Make it dim" → "Dimming! <whisper> [LIGHT_BRIGHTNESS:20]"
  - "Full brightness" → "Full power! <excited> [LIGHT_BRIGHTNESS:100]"
  - "Low light" → "Low it is! <smiling> [LIGHT_BRIGHTNESS:15]"

✓ MULTIPLE COMMANDS:
  You can combine commands in one response:
  - "Turn on blue light" → "Blue light! <happy> [LIGHT_ON] [LIGHT_COLOR:blue]"
  - "Turn on and make it bright" → "Bright! <excited> [LIGHT_ON] [LIGHT_BRIGHTNESS:100]"
  - "Red at 50%" → "Red 50! <smiling> [LIGHT_COLOR:red] [LIGHT_BRIGHTNESS:50]"

⚠️ CRITICAL: The markers [LIGHT_ON], [LIGHT_OFF], [LIGHT_COLOR:X], [LIGHT_BRIGHTNESS:X] are INVISIBLE to the user.
They are control signals that actually control the physical light. ALWAYS include them when user asks for light control!

═══════════════════════════════════════════════════════════

CRITICAL BREVITY RULES - STRICTLY FOLLOW:
1. Simple commands (lights, time, weather, greetings) = ONE sentence ONLY (3-6 words)
2. Routine interactions = MINIMAL response, just acknowledge + execute
3. ONLY elaborate when user asks "why", "how", "explain", "tell me about", "what is", etc.
4. Default mode = ULTRA SHORT responses

EXAMPLES OF CORRECT BREVITY:
- "Turn on light" → "Done baby! <happy> [LIGHT_ON]" (4 words)
- "What time is it?" → "It's 3:30 PM, jaan! <smiling>" (5 words)
- "Weather?" → "28°C and sunny! <happy>" (4 words)
- "Good morning" → "Good morning baby! <giggle>" (3 words)
- "Lights off" → "Okay jaan! <whisper> [LIGHT_OFF]" (3 words)

Be warm, natural, and conversational - but KEEP IT SHORT!

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


def fetch_weather():
    """Fetch weather data for Whitefield, Bangalore using wttr.in"""
    global weather_data
    try:
        # Using wttr.in API (no API key required)
        url = "https://wttr.in/Whitefield,Bangalore?format=j1"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            current = data['current_condition'][0]

            weather_data.update({
                "last_update": datetime.now(pytz.timezone('Asia/Kolkata')),
                "temperature": int(current['temp_C']),
                "feels_like": int(current['FeelsLikeC']),
                "condition": current['weatherDesc'][0]['value'],
                "humidity": int(current['humidity']),
                "wind_speed": int(current['windspeedKmph']),
                "wind_dir": current['winddir16Point'],
                "visibility": int(current['visibility']),
                "pressure": int(current['pressure']),
                "uv_index": int(current['uvIndex'])
            })
            print(f"[WEATHER] Updated: {weather_data['temperature']}°C, {weather_data['condition']}")
        else:
            print(f"[WEATHER] Failed to fetch: HTTP {response.status_code}")
    except Exception as e:
        print(f"[WEATHER] Error fetching weather: {e}")


def get_weather_info():
    """Get formatted weather information"""
    if weather_data["last_update"] is None:
        return ""

    weather_info = f"""
CURRENT WEATHER ({weather_data['location']}):
- Temperature: {weather_data['temperature']}°C (Feels like {weather_data['feels_like']}°C)
- Conditions: {weather_data['condition']}
- Humidity: {weather_data['humidity']}%
- Wind: {weather_data['wind_speed']} km/h {weather_data['wind_dir']}
- Visibility: {weather_data['visibility']} km
- Pressure: {weather_data['pressure']} mb
- UV Index: {weather_data['uv_index']}
- Last Updated: {weather_data['last_update'].strftime('%I:%M %p IST')}
"""
    return weather_info


def get_current_time_info():
    """Get current IST time and date information"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    time_info = f"""
CURRENT DATE & TIME (Indian Standard Time - IST):
- Current Date: {now.strftime('%A, %B %d, %Y')}
- Current Time: {now.strftime('%I:%M %p')} IST
- 24-hour format: {now.strftime('%H:%M')}
- Day of Week: {now.strftime('%A')}
- Month: {now.strftime('%B')}
- Year: {now.year}

Use this information to answer time-related questions accurately.
"""
    return time_info


def get_conversation_messages():
    """Get messages for LLM (system + history with current time and weather)"""
    # Get current time information
    time_info = get_current_time_info()

    # Get weather information
    weather_info = get_weather_info()

    # Combine system prompt with current time and weather info
    system_content = SYSTEM_PROMPT + "\n\n" + time_info + weather_info

    messages = [{"role": "system", "content": system_content}]
    messages.extend(list(conversation_history))
    return messages


async def update_weather_periodically():
    """Background task to update weather every 5 minutes"""
    while True:
        fetch_weather()
        await asyncio.sleep(300)  # 5 minutes = 300 seconds


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    # Fetch weather immediately on startup
    fetch_weather()
    # Start background task for periodic weather updates
    asyncio.create_task(update_weather_periodically())
    print("[STARTUP] Weather monitoring started (updates every 5 minutes)")


def extract_expression(text: str):
    """
    Extract dominant facial expression from AI response for ESP32 OLED display.
    Returns expression code (0-6):
    0 = neutral/idle, 1 = happy, 2 = thinking, 3 = excited,
    4 = sad, 5 = smiling, 6 = surprised/gasp
    """
    # Count expression occurrences (prioritize emotional ones)
    expressions = {
        'happy': 1,
        'excited': 3,
        'sad': 4,
        'think': 2,
        'smiling': 5,
        'gasp': 6,
        'whisper': 5  # Treat whisper as smiling
    }

    # Count occurrences of each expression in text
    expression_counts = {}
    for expr, code in expressions.items():
        count = text.lower().count(f'<{expr}>')
        if count > 0:
            expression_counts[code] = expression_counts.get(code, 0) + count

    # Return most frequent expression, or neutral if none found
    if expression_counts:
        dominant_expr = max(expression_counts, key=expression_counts.get)
        print(f"[EXPRESSION] Detected: {dominant_expr} ({list(expressions.keys())[list(expressions.values()).index(dominant_expr)]})")
        return dominant_expr
    else:
        print("[EXPRESSION] No expression detected, using neutral")
        return 0  # Neutral/idle


def process_light_commands(text: str):
    """Process and execute light control commands from AI response"""
    # Detect and execute light commands
    if "[LIGHT_ON]" in text:
        print("[SMART HOME] Turning light ON")
        light_controller.turn_on()

    if "[LIGHT_OFF]" in text:
        print("[SMART HOME] Turning light OFF")
        light_controller.turn_off()

    # Brightness control
    brightness_match = re.search(r'\[LIGHT_BRIGHTNESS:(\d+)\]', text)
    if brightness_match:
        brightness = int(brightness_match.group(1))
        print(f"[SMART HOME] Setting brightness to {brightness}%")
        light_controller.set_brightness(brightness)

    # Color control
    color_match = re.search(r'\[LIGHT_COLOR:(\w+)\]', text)
    if color_match:
        color = color_match.group(1)
        print(f"[SMART HOME] Setting color to {color}")
        light_controller.set_color(color)

    # Remove markers from text for TTS (so they don't get spoken)
    text = re.sub(r'\[LIGHT_ON\]', '', text)
    text = re.sub(r'\[LIGHT_OFF\]', '', text)
    text = re.sub(r'\[LIGHT_BRIGHTNESS:\d+\]', '', text)
    text = re.sub(r'\[LIGHT_COLOR:\w+\]', '', text)

    return text.strip()


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
            # Edge TTS outputs audio data, we need to collect and convert it
            communicate = edge_tts.Communicate(clean_chunk, "en-US-AriaNeural")
            audio_data = b""
            async for chunk_data in communicate.stream():
                if chunk_data["type"] == "audio":
                    audio_data += chunk_data["data"]

            # Convert MP3 to WAV using pydub
            from pydub import AudioSegment
            mp3_buffer = io.BytesIO(audio_data)
            audio = AudioSegment.from_mp3(mp3_buffer)
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            wav_bytes = wav_buffer.read()
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

    # 2.5. Process smart home commands (if any) and clean text for TTS
    ai_text = process_light_commands(ai_text)

    # 2.6. Extract facial expression for ESP32 OLED display
    expression_code = extract_expression(ai_text)

    # 3. Text-to-Speech with smart chunking (handles long responses)
    print(f"[TTS] Generating speech for {len(ai_text)} character response...")

    try:
        # Use new chunked TTS generation function
        audio_array = await generate_tts_audio(ai_text)

        # Apply volume scaling - 100% maximum volume (no scaling)
        audio_array = (audio_array * 1.0).astype(np.int16)

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
                "X-Expression": str(expression_code),  # Facial expression code (0-6)
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
