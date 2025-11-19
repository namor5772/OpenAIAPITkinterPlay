# This script lists all available models from the OpenAI API.from openai import OpenAI
from openai import OpenAI

client = OpenAI()

# Fetch models
models = client.models.list()

# Display some useful information about each model
for m in sorted(models.data, key=lambda x: x.id):
    print(f"ID: {m.id}")
    if hasattr(m, "created"):
        print(f"  Created: {m.created}")
    if hasattr(m, "owned_by"):
        print(f"  Owned by: {m.owned_by}")
    if hasattr(m, "object"):
        print(f"  Type: {m.object}")
    # Capabilities (newer models often have this)
    if hasattr(m, "capabilities"):
        print(f"  Capabilities: {m.capabilities}") # type: ignore
    print()

for m in models.data: print(m.id)
print(f"\nFound {len(models.data)} models available to this API key:\n")


n = 0
for m in sorted(models.data, key=lambda x: x.id):
    if m.id.startswith("gpt-") and m.id != "gpt-image-1":
        n += 1
        print(f"- {m.id}")

if n>0:
    print(f"✅ Text-completion capable models {n} available to your account:\n")
