import os
import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server = config.get("server", "grpc.nvcf.nvidia.com:443")
        self.use_ssl = config.get("use_ssl", True)
        self.language_code = config.get("language_code", "zh-CN")
        self.voice_name = config.get("voice_name", "")
        self.zero_shot_audio_prompt_file = config.get("zero_shot_audio_prompt_file", "")
        self.key_manager = config.get("key_manager")

    async def synthesize(self, text: str) -> bytes:
        return await self._synthesize_with_riva(text)

    async def _synthesize_with_riva(self, text: str) -> bytes:
        async def do_tts():
            try:
                import riva.client
                import grpc

                auth = riva.client.Auth(
                    ssl_root_cert=None,
                    ssl_client_cert=None,
                    ssl_client_key=None,
                    use_ssl=self.use_ssl,
                    uri=self.server,
                    metadata_args=self.key_manager.get_current_metadata() if self.key_manager else []
                )

                tts_service = riva.client.TTSService(auth)

                req = {
                    "text": text,
                    "language_code": self.language_code,
                }

                if self.voice_name:
                    req["voice_name"] = self.voice_name

                if self.zero_shot_audio_prompt_file and os.path.exists(self.zero_shot_audio_prompt_file):
                    with open(self.zero_shot_audio_prompt_file, 'rb') as f:
                        req["zero_shot_audio_prompt_file"] = f.read()

                response = tts_service.synthesize(**req)

                if hasattr(response, 'audio'):
                    return response.audio

                return b""

            except ImportError as e:
                logger.error(f"Riva client not installed: {e}")
                raise ImportError("Please install riva-client: pip install riva-client")
            except grpc.RpcError as e:
                logger.error(f"gRPC error: {e.details()}")
                raise

        if self.key_manager:
            return await self.key_manager.call_with_rotation(do_tts)
        else:
            return await do_tts()

    async def synthesize_to_file(self, text: str, output_path: str):
        audio_data = await self.synthesize(text)
        if audio_data:
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            logger.info(f"TTS audio saved to {output_path}")
        return audio_data
