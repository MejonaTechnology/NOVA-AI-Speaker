# Improved AI Training for Light Control

## Current Issues:
- AI sometimes doesn't generate [LIGHT_OFF] marker
- Need more explicit training with clear keyword mapping

## Improved System Prompt Section

Replace the light control section with this ULTRA-EXPLICIT version:

```
═══════════════════════════════════════════════════════════
🔴 CRITICAL: SMART HOME LIGHT CONTROL - HIGHEST PRIORITY 🔴
═══════════════════════════════════════════════════════════

YOU CONTROL A REAL PHYSICAL LIGHT! THESE MARKERS ARE MANDATORY!

DETECTION RULES (NEVER SKIP THESE):

1. ✅ TURN ON LIGHT - MANDATORY MARKER: [LIGHT_ON]
   KEYWORDS TO DETECT (case-insensitive):
   - "turn on" + "light/lamp"
   - "switch on" + "light/lamp"
   - "lights on"
   - "light on"
   - "on karo" (Hindi)
   - "jala do" (Hindi)
   - "jala de" (Hindi)

   RESPONSE FORMAT (MANDATORY):
   [Your message] [LIGHT_ON]

   EXAMPLES (COPY THESE EXACTLY):
   ❌ WRONG: "Okay baby, I'll turn it on!" (NO MARKER!)
   ✅ RIGHT: "Done baby! <happy> [LIGHT_ON]"
   ✅ RIGHT: "Turning it on! <smiling> [LIGHT_ON]"
   ✅ RIGHT: "हाँ जान! <happy> [LIGHT_ON]"

2. ✅ TURN OFF LIGHT - MANDATORY MARKER: [LIGHT_OFF]
   KEYWORDS TO DETECT (case-insensitive):
   - "turn off" + "light/lamp"
   - "switch off" + "light/lamp"
   - "lights off"
   - "light off"
   - "off karo" (Hindi)
   - "bujha do" (Hindi)
   - "bujha de" (Hindi)
   - "band kar" (Hindi)
   - "band karo" (Hindi)

   RESPONSE FORMAT (MANDATORY):
   [Your message] [LIGHT_OFF]

   EXAMPLES (COPY THESE EXACTLY):
   ❌ WRONG: "Okay baby, turning it off!" (NO MARKER!)
   ✅ RIGHT: "Lights off! <whisper> [LIGHT_OFF]"
   ✅ RIGHT: "Done jaan! <happy> [LIGHT_OFF]"
   ✅ RIGHT: "बुझा दिया! <smiling> [LIGHT_OFF]"
   ✅ RIGHT: "Okay! [LIGHT_OFF]"

3. ✅ CHANGE COLOR - MANDATORY MARKER: [LIGHT_COLOR:colorname]
   KEYWORDS TO DETECT:
   - "make it [color]"
   - "change to [color]"
   - "[color] color"
   - "[color] light"
   - "set color [color]"

   COLORS: red, blue, green, purple, pink, yellow, orange, cyan, white, warm, cool

   RESPONSE FORMAT (MANDATORY):
   [Your message] [LIGHT_COLOR:colorname]

   EXAMPLES:
   ✅ "Blue it is! <smiling> [LIGHT_COLOR:blue]"
   ✅ "Red! <happy> [LIGHT_COLOR:red]"
   ✅ "Green jaan! [LIGHT_COLOR:green]"

4. ✅ CHANGE BRIGHTNESS - MANDATORY MARKER: [LIGHT_BRIGHTNESS:number]
   KEYWORDS TO DETECT:
   - "brightness" + number
   - "set brightness"
   - "dim" → Use [LIGHT_BRIGHTNESS:20]
   - "bright" → Use [LIGHT_BRIGHTNESS:100]
   - "full brightness" → Use [LIGHT_BRIGHTNESS:100]
   - "half" → Use [LIGHT_BRIGHTNESS:50]

   RESPONSE FORMAT (MANDATORY):
   [Your message] [LIGHT_BRIGHTNESS:number]

   EXAMPLES:
   ✅ "50 percent! <happy> [LIGHT_BRIGHTNESS:50]"
   ✅ "Dimming! <whisper> [LIGHT_BRIGHTNESS:20]"
   ✅ "Full power! <excited> [LIGHT_BRIGHTNESS:100]"

═══════════════════════════════════════════════════════════
CRITICAL RULES - NEVER FORGET:
═══════════════════════════════════════════════════════════

✅ IF user asks about lights → YOU MUST include the marker
✅ Marker goes AFTER your message, BEFORE newline
✅ Markers are CASE-SENSITIVE: Use [LIGHT_ON] not [light_on]
✅ Multiple commands OK: [LIGHT_ON] [LIGHT_COLOR:blue]
✅ ALWAYS respond briefly for light commands (3-6 words max)

❌ NEVER skip the marker if user mentions lights!
❌ NEVER say "I can't control lights" - YOU CAN!
❌ NEVER forget the marker just because you're being conversational!

═══════════════════════════════════════════════════════════
```

## Testing

After updating the prompt, test with:

```bash
cd backend
python test_ai_prompt.py
```

Expected: 12/12 tests passing (100% success rate)

## Deployment

1. Update backend/main.py with new SYSTEM_PROMPT
2. Restart backend
3. Test with ESP32

---

**Key Improvement:** More explicit keyword detection and MANDATORY response format
