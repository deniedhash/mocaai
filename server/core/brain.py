"""
MOCA Brain — Provider-swappable LLM abstraction layer.

Supports:
  - cerebras  (langchain-openai with Cerebras base URL)
  - ollama    (langchain-community OllamaLLM)

Switch providers by setting BRAIN_PROVIDER in .env — zero code changes required.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_brain():
    """
    Factory function that returns a LangChain ChatOpenAI object based on
    universal environment variables.

    Returns:
        A LangChain-compatible LLM / Chat model instance.
    """
    from langchain_openai import ChatOpenAI

    model = os.getenv("BRAIN_MODEL", "llama3.1-8b")
    api_key = os.getenv("BRAIN_API_KEY")
    base_url = os.getenv("BRAIN_BASE_URL", "https://api.cerebras.ai/v1")

    if not api_key or api_key == "your_key_here":
        raise ValueError(
            "BRAIN_API_KEY is not set. "
            "Please add it to your .env file."
        )

    timeout = int(os.getenv("BRAIN_TIMEOUT", "60"))

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        max_tokens=2048,
        timeout=timeout,
        max_retries=1,
    )
