import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMHandler:
    def __init__(self, config: Dict[str, Any], system_prompt: str = ""):
        self.config = config
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model = config.get("model", "gpt-3.5-turbo")
        self.timeout = config.get("timeout", 60)
        self.max_tokens = config.get("max_tokens", 4096)
        self.key_manager = config.get("key_manager")
        self.system_prompt = system_prompt

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        return await self._call_api(messages, temperature)

    async def chat_with_prompt(self, user_message: str, temperature: float = 0.7) -> str:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_message})
        return await self._call_api(messages, temperature)

    async def chat_json(self, user_message: str, temperature: float = 0.7) -> Dict[str, Any]:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        extended_prompt = user_message + "\n\n请以JSON格式响应，包含actions字段。"
        messages.append({"role": "user", "content": extended_prompt})

        response_text = await self._call_api(messages, temperature)
        return self._parse_json_response(response_text)

    async def _call_api(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        async def do_call():
            try:
                import httpx

                headers = {
                    "Content-Type": "application/json"
                }

                api_key = self.key_manager.get_current_key() if self.key_manager else ""
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": self.max_tokens,
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    data = response.json()

                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]

                    return ""

            except ImportError:
                logger.error("httpx not installed, falling back to requests")
                raise ImportError("Please install httpx: pip install httpx")
            except Exception as e:
                logger.error(f"API call failed: {e}")
                raise

        if self.key_manager:
            return await self.key_manager.call_with_rotation(do_call)
        else:
            return await do_call()

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    return json.loads(response_text[json_start:json_end])
                except json.JSONDecodeError:
                    pass
            return {"actions": [], "error": "Failed to parse JSON response"}
