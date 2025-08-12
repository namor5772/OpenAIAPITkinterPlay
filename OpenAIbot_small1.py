from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",  # or the exact GPT-5 variant name
    input="Find the latest ABS CPI data for Australia and summarise it.",
    tools=[{"type": "web_search"}],
    tool_choice="auto"
)

print(response.output_text)
