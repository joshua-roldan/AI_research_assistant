#!/usr/bin/env python
# Find instructions how to install dependencies and how to run this script in README.md
import os
from openai import OpenAI

my_api_key = ""
path_to_key = os.path.join(os.path.expanduser("~"), ".scadsai-api-key")
if os.path.exists(path_to_key):
    with open(path_to_key) as keyfile:
        my_api_key = keyfile.readline().strip()
if len(my_api_key) < 1:
    print("Error: The key file '.scadsai-api-key' did not contain any key. Please make sure the file exists and contains only your API key.")
    exit(1)


client = OpenAI(base_url="https://llm.scads.ai/v1",api_key=my_api_key)
# Get models
print("""
Available models:
""")
for model in client.models.list().data:
    print(model.id)

model_name = "alias-ha"

# Use model
response = client.chat.completions.create(messages=[{"role":"user","content":"Tell me a joke!"}],model=model_name)

# Print the joke
print("""
Your joke:
""")
joke = response.choices[0].message.content
print(joke)


