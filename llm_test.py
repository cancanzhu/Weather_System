from openai import OpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL
c = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=60)
r = c.chat.completions.create(
    model="qwen3.6-plus",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=10,
)
print(r.choices[0].message.content)