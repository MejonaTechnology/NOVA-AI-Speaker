"""Quick test for Edge TTS fallback"""
import edge_tts
import asyncio
import os

async def test_edge_tts():
    text = "Hello! I'm testing Edge TTS. This should sound like an Indian English voice."

    communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
    await communicate.save("test_edge_output.wav")

    print("[OK] Edge TTS test successful!")
    print("Generated: test_edge_output.wav")

    # Check file size
    size = os.path.getsize("test_edge_output.wav")
    print(f"File size: {size} bytes")

if __name__ == "__main__":
    asyncio.run(test_edge_tts())
