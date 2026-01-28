import os
import yaml
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RotatingKeyManager:
    def __init__(self, keys: List[str], metadata_template: List[str] = None):
        self.keys = keys
        self.metadata_template = metadata_template or []
        self.current_index = 0
        self._lock = False

    def get_current_key(self) -> str:
        if not self.keys:
            raise ValueError("No keys available")
        return self.keys[self.current_index]

    def get_current_metadata(self) -> List[str]:
        key = self.get_current_key()
        metadata = []
        for item in self.metadata_template:
            if "{key}" in item:
                metadata.append(item.format(key=key))
            else:
                metadata.append(item)
        return metadata

    def rotate(self) -> bool:
        if self._lock or len(self.keys) <= 1:
            return False
        self._lock = True
        self.current_index = (self.current_index + 1) % len(self.keys)
        self._lock = False
        logger.info(f"Rotated key, now using index {self.current_index}")
        return True

    def rotate_all(self):
        self.current_index = 0

    async def call_with_rotation(self, func, *args, max_retries: int = None, **kwargs):
        max_retries = max_retries or len(self.keys)
        last_error = None

        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "key" in error_str or "auth" in error_str or "unauthorized" in error_str:
                    logger.warning(f"Key authentication failed, rotating: {e}")
                    self.rotate()
                else:
                    logger.error(f"API call failed: {e}")
                    raise

        raise last_error


class Config:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.data = self._load_config()

        self.tcp = self._parse_tcp_config()
        self.riva_asr = self._parse_riva_asr_config()
        self.riva_tts = self._parse_riva_tts_config()
        self.openai_api = self._parse_openai_api_config()
        self.wakeword = self._parse_wakeword_config()
        self.audio_files = self._parse_audio_files_config()
        self.session = self._parse_session_config()
        self.actions = self._parse_actions_config()

    def _load_config(self) -> Dict[str, Any]:
        config_paths = [
            self.config_path,
            os.environ.get("TS3_AGENT_CONFIG", ""),
            "config.yaml",
        ]

        for path in config_paths:
            if path and os.path.exists(path):
                logger.info(f"Loading config from {path}")
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}

        logger.warning(f"No config file found, using defaults")
        return {}

    def _get(self, *keys, default=None) -> Any:
        result = self.data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            else:
                return default
            if result is None:
                return default
        return result

    def _parse_tcp_config(self) -> Dict[str, Any]:
        return {
            "host": self._get("tcp", "host", default="localhost"),
            "port": self._get("tcp", "port", default=9001),
        }

    def _parse_riva_asr_config(self) -> Dict[str, Any]:
        keys = self._get("riva_asr", "keys", default=[])
        metadata = self._get("riva_asr", "metadata", default=[])

        if isinstance(keys, str):
            keys = [keys]

        return {
            "server": self._get("riva_asr", "server", default="grpc.nvcf.nvidia.com:443"),
            "use_ssl": self._get("riva_asr", "use_ssl", default=True),
            "language_code": self._get("riva_asr", "language_code", default="zh-CN"),
            "keys": keys,
            "metadata": metadata,
            "key_manager": RotatingKeyManager(keys, metadata),
        }

    def _parse_riva_tts_config(self) -> Dict[str, Any]:
        keys = self._get("riva_tts", "keys", default=[])
        metadata = self._get("riva_tts", "metadata", default=[])

        if isinstance(keys, str):
            keys = [keys]

        return {
            "server": self._get("riva_tts", "server", default="grpc.nvcf.nvidia.com:443"),
            "use_ssl": self._get("riva_tts", "use_ssl", default=True),
            "language_code": self._get("riva_tts", "language_code", default="zh-CN"),
            "voice_name": self._get("riva_tts", "voice_name", default=""),
            "zero_shot_audio_prompt_file": self._get("riva_tts", "zero_shot_audio_prompt_file", default=""),
            "keys": keys,
            "metadata": metadata,
            "key_manager": RotatingKeyManager(keys, metadata),
        }

    def _parse_openai_api_config(self) -> Dict[str, Any]:
        keys = self._get("openai_api", "keys", default=[])

        if isinstance(keys, str):
            keys = [keys]

        return {
            "base_url": self._get("openai_api", "base_url", default="https://api.openai.com/v1"),
            "model": self._get("openai_api", "model", default="gpt-3.5-turbo"),
            "keys": keys,
            "timeout": self._get("openai_api", "timeout", default=60),
            "max_tokens": self._get("openai_api", "max_tokens", default=4096),
            "key_manager": RotatingKeyManager(keys),
        }

    def _parse_wakeword_config(self) -> Dict[str, Any]:
        return {
            "path": self._get("wakeword", "path", default="resources/wakeword/hey_jarvis.ppn"),
            "sensitivity": self._get("wakeword", "sensitivity", default=0.7),
        }

    def _parse_audio_files_config(self) -> Dict[str, str]:
        return {
            "wakeup_alert": self._get("audio_files", "wakeup_alert", default="resources/audio/wakeup_alert.flac"),
            "processing": self._get("audio_files", "processing", default="resources/audio/processing.flac"),
            "error": self._get("audio_files", "error", default="resources/audio/error.flac"),
        }

    def _parse_session_config(self) -> Dict[str, Any]:
        return {
            "max_users": self._get("session", "max_users", default=10),
            "idle_timeout": self._get("session", "idle_timeout", default=300),
            "post_wakeup_window": self._get("session", "post_wakeup_window", default=3.0),
            "command_end_gap": self._get("session", "command_end_gap", default=1.0),
        }

    def _parse_actions_config(self) -> Dict[str, Any]:
        return {
            "max_nesting_depth": self._get("actions", "max_nesting_depth", default=3),
            "nested_timeout": self._get("actions", "nested_timeout", default=30),
            "custom_actions_dir": self._get("actions", "custom_actions_dir", default="custom_actions"),
        }

    def reload(self):
        self.data = self._load_config()
        self.__init__(self.config_path)


import asyncio
