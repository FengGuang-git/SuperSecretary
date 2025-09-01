import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

resp = client.messages.create(
    model=os.getenv("MODEL_NAME", "claude-3-5-sonnet-20240620"),
    max_tokens=200,
    system="你是一个编程助手，回答要简洁。",
    messages=[
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]
)

print(resp.content[0].text)
