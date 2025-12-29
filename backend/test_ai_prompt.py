"""
Test AI Light Control Response Generation
This tests if the AI correctly generates light control markers
"""

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Import the updated system prompt
from main import SYSTEM_PROMPT

client = Groq()

print("=" * 70)
print("  Testing AI Light Control Response Generation")
print("=" * 70)

# Test cases - what user might say
test_commands = [
    "Turn on the light",
    "Turn off the light",
    "Make it blue",
    "Set brightness to 50%",
    "Turn on blue light",
    "Make it dim",
    "Red color",
    "Light on karo",
    "Bujha do",
    "Full brightness",
    "Change to green",
    "Warm white light"
]

print("\nTesting if AI generates correct light control markers...\n")

for i, user_command in enumerate(test_commands, 1):
    print(f"\n[TEST {i}] User says: \"{user_command}\"")

    # Generate AI response
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_command}
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=100,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content.strip()
        print(f"AI responds: {ai_response}")

        # Check if correct marker is present
        has_light_on = "[LIGHT_ON]" in ai_response
        has_light_off = "[LIGHT_OFF]" in ai_response
        has_color = "[LIGHT_COLOR:" in ai_response
        has_brightness = "[LIGHT_BRIGHTNESS:" in ai_response

        markers_found = []
        if has_light_on:
            markers_found.append("LIGHT_ON")
        if has_light_off:
            markers_found.append("LIGHT_OFF")
        if has_color:
            # Extract color
            import re
            color_match = re.search(r'\[LIGHT_COLOR:(\w+)\]', ai_response)
            if color_match:
                markers_found.append(f"COLOR:{color_match.group(1)}")
        if has_brightness:
            # Extract brightness
            brightness_match = re.search(r'\[LIGHT_BRIGHTNESS:(\d+)\]', ai_response)
            if brightness_match:
                markers_found.append(f"BRIGHTNESS:{brightness_match.group(1)}")

        if markers_found:
            print(f"[SUCCESS] Markers detected: {', '.join(markers_found)}")
        else:
            print(f"[FAIL] NO MARKERS FOUND! AI failed to generate control markers!")

        print("-" * 70)

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        print("-" * 70)

print("\n" + "=" * 70)
print("  TEST COMPLETE")
print("=" * 70)
print("\nIf all tests show [SUCCESS] with correct markers, the AI is properly trained!")
print("If some show [FAIL], the AI needs more training or prompt refinement.")
