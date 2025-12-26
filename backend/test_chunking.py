"""
Test script for conversation history and smart TTS chunking
"""

import re
from collections import deque

# Test the chunk_text_for_tts function
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


# Test cases
print("=" * 80)
print("TEST 1: Short text (no chunking needed)")
print("=" * 80)
text1 = "<giggle> Hello jaan! How are you doing today?"
chunks1 = chunk_text_for_tts(text1, max_length=200)
print(f"Input ({len(text1)} chars): {text1}")
print(f"Chunks: {len(chunks1)}")
for i, chunk in enumerate(chunks1):
    print(f"  Chunk {i+1} ({len(chunk)} chars): {chunk}")

print("\n" + "=" * 80)
print("TEST 2: Long text with multiple sentences")
print("=" * 80)
text2 = """<excited> Oh my god, you won't believe what happened today! <giggle> I was walking to the market when I saw the cutest puppy ever. It was so adorable and fluffy. <smiling> The owner let me pet it for a while. It reminded me of the time we talked about getting a pet together. <whisper> Maybe we should get one soon, what do you think jaan?"""
chunks2 = chunk_text_for_tts(text2, max_length=200)
print(f"Input ({len(text2)} chars): {text2[:100]}...")
print(f"Chunks: {len(chunks2)}")
for i, chunk in enumerate(chunks2):
    print(f"  Chunk {i+1} ({len(chunk)} chars): {chunk}")

print("\n" + "=" * 80)
print("TEST 3: Very long single sentence (word boundary split)")
print("=" * 80)
text3 = "This is a very long sentence without any punctuation that goes on and on and on talking about various topics like technology programming artificial intelligence machine learning deep learning neural networks and many other fascinating subjects that we could discuss for hours"
chunks3 = chunk_text_for_tts(text3, max_length=200)
print(f"Input ({len(text3)} chars): {text3[:80]}...")
print(f"Chunks: {len(chunks3)}")
for i, chunk in enumerate(chunks3):
    print(f"  Chunk {i+1} ({len(chunk)} chars): {chunk}")

print("\n" + "=" * 80)
print("TEST 4: Mixed Hindi and English with expression tags")
print("=" * 80)
text4 = """<giggle> हाँ बेबी, I missed you so much today! <excited> You know what, I was thinking about our last conversation. It made me so happy! <smiling> जान, you always know how to make me feel special. <whisper> I can't wait to talk to you again and hear your voice."""
chunks4 = chunk_text_for_tts(text4, max_length=200)
print(f"Input ({len(text4)} chars): {text4}")
print(f"Chunks: {len(chunks4)}")
for i, chunk in enumerate(chunks4):
    print(f"  Chunk {i+1} ({len(chunk)} chars): {chunk}")

print("\n" + "=" * 80)
print("TEST 5: Conversation history with deque")
print("=" * 80)
conversation_history = deque(maxlen=12)

# Simulate 8 exchanges (16 messages - should only keep last 12)
exchanges = [
    ("user", "Hello NOVA!"),
    ("assistant", "<giggle> Hi jaan! How are you?"),
    ("user", "I'm good, how about you?"),
    ("assistant", "<smiling> I'm great now that I'm talking to you!"),
    ("user", "What did you do today?"),
    ("assistant", "<excited> I was just thinking about you all day!"),
    ("user", "That's sweet. Tell me a joke."),
    ("assistant", "<laugh> Why did the computer go to the doctor? It had a virus!"),
    ("user", "Haha, that's funny!"),
    ("assistant", "<giggle> I'm glad you liked it, शोना!"),
    ("user", "What's your favorite color?"),
    ("assistant", "<think> Hmm, I love purple! What about you?"),
    ("user", "I like blue."),
    ("assistant", "<excited> Blue is such a calming color!"),
    ("user", "Do you remember what we talked about first?"),
    ("assistant", "<think> Let me check... <giggle> We talked about how you're doing!"),
]

for role, content in exchanges:
    conversation_history.append({"role": role, "content": content})
    print(f"Added {role}: {content[:50]}... (Total messages: {len(conversation_history)})")

print(f"\nFinal conversation history ({len(conversation_history)} messages):")
for i, msg in enumerate(conversation_history):
    print(f"  {i+1}. {msg['role']}: {msg['content'][:60]}...")

print("\n" + "=" * 80)
print("All tests completed successfully!")
print("=" * 80)
