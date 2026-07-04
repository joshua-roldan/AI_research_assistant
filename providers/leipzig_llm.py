from openai import OpenAI

client = OpenAI(
    base_url="https://llm.scads.ai/v1",
    api_key="sk-1lGvx0ZMKp43aDcwjkjqLQ"
)

def chat(messages):
    return client.chat.completions.create(
        model="AI-research-assistant",
        messages=messages,
        temperature=0.2
    )