from openai import OpenAI

# Initialize client (make sure your API key is in the OPENAI_API_KEY env variable)
client = OpenAI()

# Get all models
models = client.models.list()

chat_models = []

n = 0
 # Skip anything not intended for standard completions/chat
for m in models.data:
    model_id = m.id
    if any(skip in model_id for skip in ["embedding", "audio", "search", "realtime", "preview","transcribe", "tts"]):
        continue
    if model_id.startswith("gpt-") and not("instruct" in model_id) and (model_id != "gpt-image-1"):
        chat_models.append(model_id)
        n += 1

print(f"\n=== {n} Chat Models (use /chat/completions) ===")
n = 0
for cm in sorted(chat_models): 
    n +=1
    print(f"{n}: {cm}")

