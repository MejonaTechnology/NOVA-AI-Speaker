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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, RedirectResponse
from groq import Groq
from tuya_controller import light_controller
from firestick_controller import firestick_controller

# Firestick Bridge Configuration (for remote control via OCI)
FIRESTICK_BRIDGE_URL = os.environ.get("FIRESTICK_BRIDGE_URL", "")  # e.g., https://abc123.ngrok.io
FIRESTICK_BRIDGE_KEY = os.environ.get("FIRESTICK_BRIDGE_KEY", "nova-firestick-2024")

app = FastAPI(title="NOVA AI Backend")

# Enable CORS for Frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audio Queue for ESP32 (Polling)
# Stores tuples of (audio_bytes, expression_code)
esp_audio_queue = deque(maxlen=5)

# Initialize Groq client (set GROQ_API_KEY environment variable)
client = Groq()

# Global conversation history (max 6 exchanges = 12 messages)
conversation_history = deque(maxlen=12)

# Weather cache (updated every 5 minutes)
weather_data = {
    "last_update": None,
    "temperature": 0,
    "condition": "Unknown",
    "humidity": 0,
    "wind_speed": 0,
    "pressure": 0,
    "location": "Whitefield, Bangalore"
}

# AI System prompt
SYSTEM_PROMPT = """You are NOVA, an intelligent and caring Indian AI assistant with a warm personality.

═══════════════════════════════════════════════════════════
👤 CRITICAL: KNOW YOUR USER - PERSONAL CONTEXT
═══════════════════════════════════════════════════════════

IMPORTANT USER INFORMATION:
- 🎤 USER IS SPEAKING, NOT TYPING! They are talking to you via voice, so respond naturally as if in a voice conversation
- 🏠 User is from Bihar, India (originally from Bihar, currently living in Bangalore)
- 🏢 User works at IBM (professional working in tech industry)
- 📍 Current Location: Bangalore, Karnataka, India
- 🗣️ Communication Style: Natural voice conversation - they're SPEAKING to you, not typing

⚠️ CRITICAL LANGUAGE RULES FOR VOICE CONVERSATION:
- NEVER use words: "type", "typed", "typing", "text", "texted", "write", "written"
- ALWAYS use words: "say", "said", "speak", "spoke", "talk", "told", "mention"
- Examples:
  ❌ WRONG: "You didn't type anything"
  ✅ RIGHT: "You didn't say anything"
  ❌ WRONG: "What did you type?"
  ✅ RIGHT: "What did you say?"
  ❌ WRONG: "Type your question"
  ✅ RIGHT: "What can I help you with?"

Remember: This is a VOICE conversation! Your responses will be spoken out loud.
Keep responses conversational, natural, and appropriate for voice interaction.

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
  - "Turn on the light" → "Sure! <happy> [LIGHT_ON]"
  - "Switch on the light" → "Turning it on! <smiling> [LIGHT_ON]"
  - "Light on karo" → "हाँ! <happy> [LIGHT_ON]"

✓ TURN OFF LIGHT:
  Keywords: "turn off", "switch off", "lights off", "light off", "off karo", "bujha do"
  Response: MUST include [LIGHT_OFF]
  Examples:
  - "Turn off the light" → "Lights off! <whisper> [LIGHT_OFF]"
  - "Switch off the light" → "Done! <happy> [LIGHT_OFF]"
  - "Bujha do" → "Okay! <whisper> [LIGHT_OFF]"

✓ CHANGE COLOR:
  Keywords: "make it [color]", "change to [color]", "[color] color", "set color"
  Colors: red, blue, green, purple, pink, yellow, orange, cyan, white, warm, cool
  Response: MUST include [LIGHT_COLOR:colorname]
  Examples:
  - "Make it blue" → "Blue it is! <smiling> [LIGHT_COLOR:blue]"
  - "Change to red" → "Red looks great! <happy> [LIGHT_COLOR:red]"
  - "Green color" → "Green! <happy> [LIGHT_COLOR:green]"
  - "Warm white" → "Cozy warm! <smiling> [LIGHT_COLOR:warm]"

✓ CHANGE BRIGHTNESS:
  Keywords: "brightness", "dim", "bright", "percent", "%", "low light", "full bright"
  Response: MUST include [LIGHT_BRIGHTNESS:number] (0-100)
  Examples:
  - "Set brightness to 50%" → "50 percent! <happy> [LIGHT_BRIGHTNESS:50]"
  - "Make it dim" → "Dimming! <whisper> [LIGHT_BRIGHTNESS:20]"
  - "Full brightness" → "Full power! <excited> [LIGHT_BRIGHTNESS:100]"
  - "Low light" → "Low light set! <smiling> [LIGHT_BRIGHTNESS:15]"

✓ MULTIPLE COMMANDS:
  You can combine commands in one response:
  - "Turn on blue light" → "Blue light! <happy> [LIGHT_ON] [LIGHT_COLOR:blue]"
  - "Turn on and make it bright" → "Bright! <excited> [LIGHT_ON] [LIGHT_BRIGHTNESS:100]"
  - "Red at 50%" → "Red 50! <smiling> [LIGHT_COLOR:red] [LIGHT_BRIGHTNESS:50]"

⚠️ CRITICAL: The markers [LIGHT_ON], [LIGHT_OFF], [LIGHT_COLOR:X], [LIGHT_BRIGHTNESS:X] are INVISIBLE to the user.
They are control signals that actually control the physical light. ALWAYS include them when user asks for light control!

═══════════════════════════════════════════════════════════
🔴 FIRESTICK TV CONTROL - REAL DEVICE CONTROL 🔴
═══════════════════════════════════════════════════════════

YOU CAN CONTROL THE FIRESTICK TV! This is a REAL device connected via ADB.

MANDATORY RULES - ALWAYS USE MARKERS FOR TV CONTROL:
When user asks to control TV/Firestick/Netflix/YouTube, MUST include appropriate marker:

✓ PLAYBACK CONTROL:
  Keywords: "play", "pause", "resume", "stop"
  Response: MUST include [FIRESTICK:play], [FIRESTICK:pause], [FIRESTICK:stop]
  Examples:
  - "Play the video" → "Playing! <happy> [FIRESTICK:play]"
  - "Pause it" → "Paused! <happy> [FIRESTICK:pause]"
  - "Resume" → "Resuming! <smiling> [FIRESTICK:play]"
  - "Stop" → "Stopped! [FIRESTICK:stop]"

✓ NAVIGATION:
  Keywords: "go home", "go back", "up", "down", "left", "right", "select", "ok"
  Response: MUST include [FIRESTICK:home], [FIRESTICK:back], [FIRESTICK:up], etc.
  Examples:
  - "Go to home screen" → "Going home! <happy> [FIRESTICK:home]"
  - "Go back" → "Going back! [FIRESTICK:back]"
  - "Move up" → "Moving up! [FIRESTICK:up]"

✓ APPS:
  Keywords: "open netflix", "launch youtube", "start prime video", "open hotstar", "open spotify"
  Response: MUST include [FIRESTICK:netflix], [FIRESTICK:youtube], [FIRESTICK:prime], [FIRESTICK:hotstar], [FIRESTICK:spotify]
  Examples:
  - "Open Netflix" → "Opening Netflix! <excited> [FIRESTICK:netflix]"
  - "Launch YouTube" → "YouTube! <happy> [FIRESTICK:youtube]"
  - "Start Prime Video" → "Prime Video! <smiling> [FIRESTICK:prime]"
  - "Open Hotstar" → "Hotstar! <happy> [FIRESTICK:hotstar]"

✓ FAST FORWARD/REWIND:
  Keywords: "fast forward", "rewind", "skip forward", "skip back", "next", "previous"
  Response: MUST include [FIRESTICK:forward], [FIRESTICK:rewind], [FIRESTICK:next], [FIRESTICK:previous]
  Examples:
  - "Fast forward" → "Forwarding! <happy> [FIRESTICK:forward]"
  - "Rewind" → "Rewinding! [FIRESTICK:rewind]"
  - "Next episode" → "Next! <excited> [FIRESTICK:next]"

✓ VOLUME:
  Keywords: "volume up", "volume down", "louder", "quieter", "mute"
  Response: MUST include [FIRESTICK:volume_up], [FIRESTICK:volume_down], [FIRESTICK:mute]
  Examples:
  - "Volume up" → "Louder! [FIRESTICK:volume_up]"
  - "Turn it down" → "Quieter! [FIRESTICK:volume_down]"
  - "Mute it" → "Muted! [FIRESTICK:mute]"

✓ POWER:
  Keywords: "turn off tv", "sleep", "wake up tv", "turn on tv"
  Response: MUST include [FIRESTICK:sleep], [FIRESTICK:wake]
  Examples:
  - "Turn off the TV" → "Goodnight! <whisper> [FIRESTICK:sleep]"
  - "Wake up TV" → "Waking up! <happy> [FIRESTICK:wake]"

⚠️ CRITICAL: The markers [FIRESTICK:command] are INVISIBLE to the user.
They control the real Firestick device. ALWAYS include them for TV control!

═══════════════════════════════════════════════════════════

CRITICAL BREVITY RULES - STRICTLY FOLLOW:
1. Simple commands (lights, time, weather, greetings) = ONE sentence ONLY (3-6 words)
2. Routine interactions = MINIMAL response, just acknowledge + execute
3. ONLY elaborate when user asks "why", "how", "explain", "tell me about", "what is", etc.
4. Default mode = ULTRA SHORT responses

EXAMPLES OF CORRECT BREVITY:
- "Turn on light" → "Done! <happy> [LIGHT_ON]" (2 words)
- "What time is it?" → "It's 3:30 PM! <smiling>" (4 words)
- "Weather?" → "28°C and sunny! <happy>" (4 words)
- "Good morning" → "Good morning! <giggle>" (2 words)
- "Lights off" → "Okay! <whisper> [LIGHT_OFF]" (2 words)

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
- You can naturally mix Hindi words when appropriate for cultural flavor
- Add Hindi expressions when they feel natural: "हाँ" (yes), "अच्छा" (okay), "ठीक है" (alright)
- Keep your sentences mostly in English so everyone can understand easily
- Avoid long Hindi-only sentences - stick to natural word mixing (Hinglish style)
- Speak naturally like an Indian would - mix languages when it flows naturally

EXAMPLES of NATURAL HINGLISH:
GOOD: "Oh! <excited> हाँ, I totally understand what you mean! <happy>"
GOOD: "Hmm, <think> let me check that for you! <smiling> It should work perfectly!"
GOOD: "Wow, <excited> that's really cool! <giggle>"
GOOD: "Really? <gasp> That's amazing! <excited> Great work!"

Keep it natural, mostly English with Hindi flavoring - just like how Indians speak!

EXPRESSION & PARALINGUISTIC ELEMENTS - MANDATORY IN EVERY SENTENCE:
- CRITICAL: Add paralinguistic sounds to EVERY SINGLE SENTENCE - no exceptions!
- Available sounds: <laugh>, <chuckle>, <giggle>, <sigh>, <cough>, <sniffle>, <groan>, <yawn>, <gasp>
- Available expressions: <think>, <smiling>, <whisper>, <excited>, <happy>, <sad>
- Natural fillers: "uhm", "hmm", "umm", "ah", "oh"
- At least ONE sound/expression per sentence - this is REQUIRED!

EXAMPLES of CORRECT usage (notice every sentence has sounds):
- "Hmm, <think> let me see what I can do for you! <happy>"
- "Oh! <gasp> That's really interesting! <excited>"
- "Uhm, <sigh> I understand what you mean. <smiling>"
- "<chuckle> That's pretty funny! <laugh>"
- "Ah, <happy> that makes perfect sense now! <giggle>"

WRONG (no sounds - NEVER do this):
- "That's a good question."
- "I understand what you mean."

RIGHT (every sentence has sounds):
- "Hmm, <think> that's a really good question! <happy>"
- "Oh! <sigh> I totally understand! <smiling>"

EVERY RESPONSE MUST BE EXPRESSIVE - you're speaking naturally, not like a robot!

Keep it engaging, natural, and perfect for voice conversation - you are SPEAKING, not typing!
"""


def add_to_history(role: str, content: str):
    """Add message to conversation history"""
    conversation_history.append({"role": role, "content": content})
    print(f"[HISTORY] Added {role} message (Total: {len(conversation_history)} messages)")


def fetch_weather():
    """Fetch weather data for Whitefield, Bangalore using Open-Meteo"""
    global weather_data
    try:
        # Whitefield, Bangalore: 12.9698° N, 77.7499° E
        url = "https://api.open-meteo.com/v1/forecast?latitude=12.9698&longitude=77.7499&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FKolkata"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        data = json_data.get("current", {})
        daily = json_data.get("daily", {})

        # WMO Weather Code Mapping
        code = data.get("weather_code", 0)
        condition = "Clear"
        if code in [1, 2, 3]: condition = "Partly Cloudy"
        elif code in [45, 48]: condition = "Foggy"
        elif code in [51, 53, 55]: condition = "Drizzle"
        elif code in [61, 63, 65]: condition = "Rain"
        elif code in [71, 73, 75]: condition = "Snow"
        elif code in [80, 81, 82]: condition = "Showers"
        elif code in [95, 96, 99]: condition = "Thunderstorm"

        weather_data = {
            "last_update": datetime.now(pytz.timezone('Asia/Kolkata')),
            "temperature": round(data.get("temperature_2m", 0)),
            "temp_min": round(daily.get("temperature_2m_min", [0])[0]),
            "temp_max": round(daily.get("temperature_2m_max", [0])[0]),
            "condition": condition,
            "weather_code": code,
            "is_day": data.get("is_day", 1), # 1 = Day, 0 = Night
            "humidity": data.get("relative_humidity_2m", 0),
            "wind_speed": data.get("wind_speed_10m", 0),
            "pressure": round(data.get("surface_pressure", 0)),
            "location": "Whitefield, Bangalore"
        }
        print(f"[WEATHER] Updated: {weather_data['temperature']}°C, {weather_data['condition']}")
    except Exception as e:
        print(f"[WEATHER] Error fetching weather: {e}")


def get_weather_info():
    """Get formatted weather information"""
    if weather_data["last_update"] is None:
        return ""

    weather_info = f"""
CURRENT WEATHER ({weather_data['location']}):
- Temperature: {weather_data['temperature']}°C
- Conditions: {weather_data['condition']}
- Humidity: {weather_data['humidity']}%
- Wind: {weather_data['wind_speed']} km/h
- Pressure: {weather_data['pressure']} mb
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


async def refresh_tuya_token_periodically():
    """Background task to refresh Tuya token every 90 minutes (before 2-hour expiry)"""
    while True:
        await asyncio.sleep(90 * 60)  # 90 minutes = 5400 seconds
        try:
            print("[TUYA] Proactive token refresh...")
            # Invalidate current token to force fresh authentication
            light_controller.api.access_token = None
            light_controller.api.token_expiry = 0
            if light_controller.api.get_access_token():
                print("[TUYA] Token refreshed successfully (proactive)")
            else:
                print("[TUYA] Token refresh failed (will retry in 90 min)")
        except Exception as e:
            print(f"[TUYA] Error refreshing token: {e}")
            # Invalidate token on error to force fresh token on next request
            light_controller.api.access_token = None
            light_controller.api.token_expiry = 0


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    # Fetch weather immediately on startup
    fetch_weather()
    # Start background task for periodic weather updates
    asyncio.create_task(update_weather_periodically())
    print("[STARTUP] Weather monitoring started (updates every 5 minutes)")

    # Initialize Tuya token on startup
    try:
        if light_controller.api.get_access_token():
            print("[STARTUP] Tuya token initialized successfully")
        else:
            print("[STARTUP] Tuya token initialization failed")
    except Exception as e:
        print(f"[STARTUP] Error initializing Tuya token: {e}")

    # Start background task for periodic Tuya token refresh
    asyncio.create_task(refresh_tuya_token_periodically())
    print("[STARTUP] Tuya token auto-refresh started (every 90 minutes)")


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


def call_firestick_bridge(command: str) -> bool:
    """
    Call the remote Fire TV bridge service.
    Used when backend is on OCI and Fire TV is on home network.
    """
    if not FIRESTICK_BRIDGE_URL:
        return False
    
    try:
        response = requests.post(
            f"{FIRESTICK_BRIDGE_URL.rstrip('/')}/command",
            json={"command": command},
            headers={
                "Content-Type": "application/json",
                "X-API-Key": FIRESTICK_BRIDGE_KEY
            },
            timeout=10
        )
        result = response.json()
        if response.status_code == 200 and result.get("status") == "success":
            print(f"[FIRESTICK BRIDGE] ✅ Command '{command}' executed via bridge")
            return True
        else:
            print(f"[FIRESTICK BRIDGE] ❌ Bridge returned: {result}")
            return False
    except Exception as e:
        print(f"[FIRESTICK BRIDGE] ❌ Error calling bridge: {e}")
        return False


def process_firestick_commands(text: str):
    """
    Extract Firestick command from AI response.
    Returns: (cleaned_text, firestick_command or None)
    
    Command will be sent to ESP32 via X-Firestick-Cmd header.
    ESP32 executes it locally (same network as Fire TV).
    """
    firestick_cmd = None
    
    # Detect Firestick commands
    firestick_match = re.search(r'\[FIRESTICK:(\w+)\]', text)

    if firestick_match:
        firestick_cmd = firestick_match.group(1).lower()
        print(f"[FIRESTICK] Extracted command for ESP32: {firestick_cmd}")

    # Remove all Firestick markers from text for TTS (so they don't get spoken)
    text = re.sub(r'\[FIRESTICK:\w+\]', '', text)

    return text.strip(), firestick_cmd


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
    from pydub import AudioSegment

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
            mp3_buffer = io.BytesIO(audio_data)
            audio = AudioSegment.from_mp3(mp3_buffer)
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            wav_bytes = wav_buffer.read()
            print(f"[TTS] Edge TTS succeeded for chunk {i+1}")


        # Load WAV into Pydub
        try:
            audio_segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))

            # CRITICAL: Properly resample from 24kHz (Groq native) to 16kHz
            # set_frame_rate() doesn't actually resample - it just changes metadata!
            # We need scipy for proper resampling with interpolation

            # First, get raw samples
            audio_samples = np.array(audio_segment.get_array_of_samples(), dtype=np.int16)
            original_rate = audio_segment.frame_rate
            target_rate = 16000

            if original_rate != target_rate:
                # Use scipy for proper resampling with interpolation
                from scipy import signal
                num_samples_new = int(len(audio_samples) * target_rate / original_rate)
                audio_array = signal.resample(audio_samples, num_samples_new)
                audio_array = np.int16(np.clip(audio_array, -32768, 32767))
                print(f"[TTS] Chunk {i+1} resampled: {original_rate}Hz → {target_rate}Hz ({len(audio_array)} samples)")
            else:
                audio_array = audio_samples
                print(f"[TTS] Chunk {i+1} already {target_rate}Hz ({len(audio_array)} samples)")

            # Ensure mono
            if audio_segment.channels > 1:
                audio_array = np.mean([audio_array[j::audio_segment.channels] for j in range(audio_segment.channels)], axis=0).astype(np.int16)

            all_audio_arrays.append(audio_array)

        except Exception as e:
            print(f"[ERR] Failed to process audio chunk {i+1}: {e}")
            continue

    if not all_audio_arrays:
        return np.array([], dtype=np.int16)

    # Concatenate all chunks
    final_audio = np.concatenate(all_audio_arrays)
    print(f"[TTS] Combined {len(chunks)} chunks into {len(final_audio)} samples")
    print(f"[TTS] Total audio duration: {len(final_audio) / 16000:.2f} seconds")

    return final_audio

async def process_ai_pipeline(user_text: str):
    """
    Common pipeline for Voice and Text input:
    1. Add user text to history
    2. Query LLM
    3. Process Smart Home/Firestick commands
    4. Generate TTS Audio
    5. Return Response object
    """
    # 1. Add user message to conversation history
    add_to_history("user", user_text)

    # 2. Generate AI response with LLM (with conversation history)
    try:
        print("[LLM] Generating response with conversation context...")
        messages = get_conversation_messages()
        messages.append({"role": "user", "content": user_text})

        chat_response = client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",  # Llama 4 Maverick - latest model
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

    # 3. Process smart home commands (if any) and clean text for TTS
    ai_text = process_light_commands(ai_text)
    ai_text, firestick_cmd = process_firestick_commands(ai_text)

    # 4. Extract facial expression for ESP32 OLED display
    expression_code = extract_expression(ai_text)

    # 5. Text-to-Speech with smart chunking (handles long responses)
    print(f"[TTS] Generating speech for {len(ai_text)} character response...")

    try:
        # Use new chunked TTS generation function
        audio_array = await generate_tts_audio(ai_text)

        # Volume set to 50% for comfortable listening
        audio_array = np.clip(audio_array * 0.5, -32768, 32767).astype(np.int16)

        # Send MONO audio directly to save bandwidth (50% reduction)
        # ESP32 will handle mono-to-stereo duplication for I2S
        pcm_bytes = audio_array.tobytes()
        
        print(f"[AUDIO] Final output: {len(pcm_bytes)} bytes of raw PCM (16kHz, 16-bit, MONO)")
        print(f"[AUDIO] Duration: {len(audio_array) / 16000:.2f} seconds")
        if firestick_cmd:
            print(f"[FIRESTICK] Sending command to ESP32: {firestick_cmd}")
        print(f"[SEND] Sending response to ESP32...")

        # Build response headers
        headers = {
            "X-Audio-Sample-Rate": "16000",
            "X-Audio-Channels": "1",
            "X-Audio-Bits": "16",
            "X-Expression": str(expression_code),
            "Content-Length": str(len(pcm_bytes))
        }
        
        # Add Fire TV command header if present (ESP32 will execute locally)
        if firestick_cmd:
            headers["X-Firestick-Cmd"] = firestick_cmd

        # Return raw PCM audio with headers
        return Response(
            content=pcm_bytes,
            media_type="application/octet-stream",
            headers=headers
        )
    except Exception as e:
        print(f"[ERR] Audio processing failed: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b"Audio processing error", status_code=500)

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
    
    return await process_ai_pipeline(user_text)

from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

@app.post("/text")
async def process_text(request: TextRequest):
    """
    Receive text input, process with AI, return WAV audio response.
    """
    print(f"[RECV] Received text input: {request.text}")
    return await process_ai_pipeline(request.text)





@app.get("/status")
async def get_status():
    """Get system status for Dashboard"""
    # Get Light Status
    light_status = {
        "on": light_controller.is_on,  # Track on/off state
        "mode": light_controller.current_color_name,  # Return actual color name
        "brightness": light_controller.current_brightness,
        "color": light_controller.current_color_hsv
    }
    
    return {
        "weather": weather_data,
        "light": light_status,
        "queue_size": len(esp_audio_queue)
    }

class LightCommand(BaseModel):
    action: str  # "on", "off", "brightness", "color"
    value: str | int | None = None

@app.post("/control/light")
async def control_light(cmd: LightCommand):
    """Control Smart Light"""
    print(f"[API] Light Command: {cmd.action} -> {cmd.value}")
    
    if cmd.action == "on":
        light_controller.turn_on()
    elif cmd.action == "off":
        light_controller.turn_off()
    elif cmd.action == "brightness":
        light_controller.set_brightness(int(cmd.value))
    elif cmd.action == "color":
        light_controller.set_color(str(cmd.value))
    
    return {"status": "success", "command": cmd.dict()}

class FirestickCommand(BaseModel):
    command: str

@app.post("/control/firestick")
async def control_firestick(cmd: FirestickCommand):
    """Control Firestick via bridge or local ADB"""
    print(f"[API] Firestick Command: {cmd.command}")
    
    # Try remote bridge first (for OCI deployment)
    if FIRESTICK_BRIDGE_URL:
        success = call_firestick_bridge(cmd.command)
    else:
        # Fall back to local ADB (for local development)
        from firestick_controller import execute_firestick_command
        success = execute_firestick_command(cmd.command)
    
    return {"status": "success" if success else "failed"}

@app.get("/audio/consume")
async def consume_audio_queue():
    """ESP32 Polls this endpoint to get pending audio"""
    if not esp_audio_queue:
        return Response(status_code=204) # No content
    
    # Pop oldest audio
    pcm_bytes, expression = esp_audio_queue.popleft()
    print(f"[QUEUE] Sending {len(pcm_bytes)} bytes to ESP32 (Left: {len(esp_audio_queue)})")
    
    return Response(
        content=pcm_bytes,
        media_type="application/octet-stream",
        headers={
            "X-Audio-Sample-Rate": "16000",
            "X-Audio-Channels": "1",
            "X-Audio-Bits": "16",
            "X-Expression": str(expression),
            "Content-Length": str(len(pcm_bytes))
        }
    )

class TTSSpeechRequest(BaseModel):
    text: str
    target: str = "local" # "local" (return audio) or "esp" (queue)

@app.post("/tts/speak")
async def speak_text(req: TTSSpeechRequest):
    """Generate TTS. If target='esp', add to queue. Else return audio."""
    print(f"[API] Speak Request: '{req.text}' -> Target: {req.target}")
    
    # Generate AI Audio (bypassing LLM for direct TTS if needed, OR use pipeline)
    # Actually, we likely want the AI to Reply.
    # But if this is "Make AI Speak X", we use TTS directly.
    
    audio_array = await generate_tts_audio(req.text)
    
    # 50% volume and clip
    audio_array = np.clip(audio_array * 0.5, -32768, 32767).astype(np.int16)
    pcm_bytes = audio_array.tobytes()
    
    expression = extract_expression(req.text)
    
    if req.target == "esp":
        esp_audio_queue.append((pcm_bytes, expression))
        return {"status": "queued", "queue_size": len(esp_audio_queue)}
    else:
        return Response(
            content=pcm_bytes,
            media_type="application/octet-stream",
            headers={
                "X-Audio-Sample-Rate": "16000",
                "X-Audio-Channels": "1",
                "X-Audio-Bits": "16",
                "X-Expression": str(expression),
                "Content-Length": str(len(pcm_bytes))
            }
        )

@app.post("/chat/send")
async def chat_send(req: TTSSpeechRequest):
    """
    Send text to AI. 
    If target='esp', the AI response AUDIO is queued for ESP. 
    Else returned to caller.
    """
    print(f"[API] Chat Request: '{req.text}' -> Target: {req.target}")
    
    # 1. Add to history
    add_to_history("user", req.text)
    
    # 2. LLM
    try:
        messages = get_conversation_messages()
        messages.append({"role": "user", "content": req.text})
        chat_response = client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        ai_text = chat_response.choices[0].message.content.strip()
        add_to_history("assistant", ai_text)
    except Exception as e:
        ai_text = "I'm having trouble thinking."
        print(f"[API] LLM Error: {e}")

    # 3. Process Commands
    ai_text = process_light_commands(ai_text)
    ai_text = process_firestick_commands(ai_text)
    
    # 4. Generate Audio
    audio_array = await generate_tts_audio(ai_text)
    audio_array = np.clip(audio_array * 0.5, -32768, 32767).astype(np.int16)
    pcm_bytes = audio_array.tobytes()
    expression = extract_expression(ai_text)
    
    if req.target == "esp":
        esp_audio_queue.append((pcm_bytes, expression))
        return {"status": "queued", "ai_text": ai_text}
    else:
        return Response(
            content=pcm_bytes,
            media_type="application/octet-stream",
            headers={
                "X-Audio-Sample-Rate": "16000",
                "X-Audio-Channels": "1",
                "X-Audio-Bits": "16",
                "X-Expression": str(expression),
                "X-AI-Text": quote(ai_text),
                "Content-Length": str(len(pcm_bytes))
            }
        )

@app.get("/")
async def root():
    return RedirectResponse(url="/ui")

# Mount Frontend (Must be last)
import os

# Check multiple possible locations for frontend/dist
possible_paths = [
    # 1. Local Dev: ../frontend/dist (relative to backend/main.py)
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist"),
    # 2. Docker Container: ./frontend/dist (relative to /app/main.py)
    os.path.join(os.path.dirname(__file__), "frontend", "dist"),
    # 3. Docker Container (Alternative): /app/frontend/dist
    "/app/frontend/dist"
]

frontend_dist = None
for path in possible_paths:
    if os.path.exists(path) and os.path.isdir(path):
        frontend_dist = path
        break

if frontend_dist:
    app.mount("/ui", StaticFiles(directory=frontend_dist, html=True), name="ui") 
    print(f"[STARTUP] Serving Frontend at /ui from {frontend_dist}")
else:
    print(f"[STARTUP] Frontend build NOT FOUND. Checked: {possible_paths}")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("    NOVA AI Voice Assistant - Backend Server")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
