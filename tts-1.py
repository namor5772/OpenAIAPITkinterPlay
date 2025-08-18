from pathlib import Path
from openai import OpenAI

client = OpenAI()

speech_file = Path("output.mp3")

# Generate audio from text
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="alloy",  # available: alloy, verse, shimmer, etc.
    input="Hello Lee-Ann, are you cleaning the dishes again. I should help"
) as response:
    response.stream_to_file(speech_file)

print(f"Saved audio to {speech_file}")