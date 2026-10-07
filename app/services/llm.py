import os
import json
from openai import AsyncOpenAI
from typing import Dict, Any

# Load configuration from environment
# Defaults to localhost:3001/v1 for the FreeLLMAPI local proxy
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "http://localhost:3001/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "freellmapi-local-token")
# Fallback to a fast model name if needed, but local proxies often ignore the model param
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")

# Initialize the unified async client
llm_client = AsyncOpenAI(
    base_url=OPENAI_API_BASE,
    api_key=OPENAI_API_KEY,
)

async def generate_json_response(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
    """
    Helper function to query the unified LLM endpoint and return parsed JSON.
    """
    try:
        response = await llm_client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        # Fallback to simulated response if LLM gateway is unreachable during dev
        print(f"LLM Error: {e}")
        return {"error": str(e), "simulated": True}
