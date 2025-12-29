"""
Test NOVA AI Backend - Light Control Integration
This tests if the backend properly processes light control commands from AI responses
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from tuya_controller import light_controller
from main import process_light_commands

print("=" * 60)
print("  Testing Light Control Command Processing")
print("=" * 60)

# Test scenarios with AI responses containing light commands
test_cases = [
    {
        "name": "Turn light ON",
        "ai_response": "Done baby! <happy> [LIGHT_ON]",
        "expected": "Light should turn ON"
    },
    {
        "name": "Turn light OFF",
        "ai_response": "Lights off! <whisper> [LIGHT_OFF]",
        "expected": "Light should turn OFF"
    },
    {
        "name": "Set brightness to 30%",
        "ai_response": "30 percent! <happy> [LIGHT_BRIGHTNESS:30]",
        "expected": "Brightness should be 30%"
    },
    {
        "name": "Set color to BLUE",
        "ai_response": "Blue it is! <smiling> [LIGHT_COLOR:blue]",
        "expected": "Color should change to BLUE"
    },
    {
        "name": "Set color to RED",
        "ai_response": "Red is so passionate! <giggle> [LIGHT_COLOR:red]",
        "expected": "Color should change to RED"
    },
    {
        "name": "Multiple commands - Turn ON + Set Blue + 50% brightness",
        "ai_response": "Making it blue at 50 percent! <happy> [LIGHT_ON] [LIGHT_COLOR:blue] [LIGHT_BRIGHTNESS:50]",
        "expected": "Light ON, BLUE color, 50% brightness"
    },
]

print("\nTesting process_light_commands() function...\n")

for i, test in enumerate(test_cases, 1):
    print(f"\n[TEST {i}] {test['name']}")
    print(f"AI Response: {test['ai_response']}")
    print(f"Expected: {test['expected']}")

    # Process the command
    cleaned_text = process_light_commands(test['ai_response'])

    print(f"Cleaned Text (for TTS): {cleaned_text}")
    print("-" * 60)

    # Wait 2 seconds before next test
    if i < len(test_cases):
        import time
        time.sleep(2)

print("\n" + "=" * 60)
print("  ALL TESTS COMPLETE")
print("=" * 60)
print("\nDid all the light commands work correctly?")
print("If yes, the backend integration is working!")
print("If no, there might be an issue with:")
print("  1. Tuya API credentials")
print("  2. Device ID")
print("  3. Network connectivity")
print("  4. Light device status")
