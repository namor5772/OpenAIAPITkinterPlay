from openai import OpenAI
import base64

client = OpenAI()

result = client.images.generate(
    model="gpt-image-1",
    prompt="An agressive Echidna with its spikes up fighting with a Wombat on an open sunny field",
    size="1024x1024"
)

# Save image
image_base64 = result.data[0].b64_json
with open("fight.png", "wb") as f:
    f.write(base64.b64decode(image_base64))