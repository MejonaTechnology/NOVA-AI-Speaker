"""
Test to verify the actual sample rate of Groq Orpheus TTS output
"""
import io
import os
from dotenv import load_dotenv
from groq import Groq
from pydub import AudioSegment
import wave

# Load environment variables first
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("Testing Groq Orpheus TTS sample rate...")

# Generate a short test audio
tts_response = client.audio.speech.create(
    model="canopylabs/orpheus-v1-english",
    voice="diana",
    input="Hello, this is a test",
    response_format="wav"
)

wav_bytes = tts_response.read()
print(f"\n[RAW] Received {len(wav_bytes)} bytes from Groq")

# Load WAV and check native sample rate
wav_buffer = io.BytesIO(wav_bytes)
with wave.open(wav_buffer, 'rb') as wav_file:
    native_params = wav_file.getparams()
    print(f"\n[NATIVE] Native Groq output:")
    print(f"  - Sample rate: {native_params.framerate} Hz")
    print(f"  - Channels: {native_params.nchannels}")
    print(f"  - Sample width: {native_params.sampwidth} bytes")
    print(f"  - Duration: {native_params.nframes / native_params.framerate:.2f} seconds")

# Now check what pydub does when we resample
print(f"\n[RESAMPLE] Converting to 16kHz...")
audio_segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
print(f"  - Original: {audio_segment.frame_rate} Hz, {audio_segment.channels} channels")

# Resample to 16kHz
audio_resampled = audio_segment.set_frame_rate(16000).set_channels(1)
print(f"  - Resampled: {audio_resampled.frame_rate} Hz, {audio_resampled.channels} channels")

# Export and check
resampled_wav = io.BytesIO()
audio_resampled.export(resampled_wav, format="wav")
resampled_wav.seek(0)

with wave.open(resampled_wav, 'rb') as wav_file:
    resampled_params = wav_file.getparams()
    print(f"  - Output: {resampled_params.framerate} Hz, {resampled_params.nchannels} channels")
    print(f"  - Output size: {len(resampled_wav.getvalue())} bytes")

print("\n✅ Test complete - check if native and output match ESP32 expectations (16kHz mono)")
