import asyncio
from abc import ABC, abstractmethod
from babys_breath.config import (
    GROQ_API_KEY, GEMINI_API_KEY,
    GROQ_MODEL, GEMINI_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
)


class LLMProvider(ABC):
    @abstractmethod
    async def think(self, system: str, messages: list[dict], max_tokens: int = LLM_MAX_TOKENS) -> str:
        ...


class GroqProvider(LLMProvider):
    def __init__(self):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=GROQ_API_KEY)

    async def think(self, system: str, messages: list[dict], max_tokens: int = LLM_MAX_TOKENS) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=full_messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()


class GeminiProvider(LLMProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    async def think(self, system: str, messages: list[dict], max_tokens: int = LLM_MAX_TOKENS) -> str:
        # Gemini uses a different format — flatten into a single conversation
        parts = [f"System instructions: {system}\n\n"]
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}\n")
        prompt = "".join(parts)

        response = await asyncio.to_thread(
            self.model.generate_content,
            prompt,
            generation_config={
                "temperature": LLM_TEMPERATURE,
                "max_output_tokens": max_tokens,
            }
        )
        return response.text.strip()


class BabyBrain:
    """Multi-provider LLM engine with fallback chain."""

    def __init__(self):
        self.providers: list[LLMProvider] = []
        if GROQ_API_KEY:
            self.providers.append(GroqProvider())
        if GEMINI_API_KEY:
            self.providers.append(GeminiProvider())
        if not self.providers:
            raise RuntimeError("No LLM API keys configured. Set GROQ_API_KEY or GEMINI_API_KEY in .env")

    async def think(self, system: str, messages: list[dict], max_tokens: int = LLM_MAX_TOKENS) -> str:
        last_error = None
        for provider in self.providers:
            try:
                return await provider.think(system, messages, max_tokens)
            except Exception as e:
                last_error = e
                print(f"[BabyBrain] {provider.__class__.__name__} failed: {e}")
                continue
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
