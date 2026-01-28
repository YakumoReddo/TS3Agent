import os
import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

RIVA_ASR_SAMPLE_RATE = 16000


class SpeechRecognizer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server = config.get("server", "grpc.nvcf.nvidia.com:443")
        self.use_ssl = config.get("use_ssl", True)
        self.language_code = config.get("language_code", "zh-CN")
        self.key_manager = config.get("key_manager")

    async def transcribe(self, audio_file: str) -> str:
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        return await self._transcribe_with_riva(str(audio_path))

    async def _transcribe_with_riva(self, audio_file: str) -> str:
        async def do_transcribe():
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

                asr_service = riva.client.ASRService(auth)

                config = riva.client.RecognitionConfig(
                    language_code=self.language_code,
                    max_alternatives=1,
                )

                with open(audio_file, 'rb') as f:
                    audio_data = f.read()

                response = asr_service.offline_recognize(audio_data, config)

                if response.results:
                    for result in response.results:
                        if result.alternatives:
                            return result.alternatives[0].transcript

                return ""

            except ImportError as e:
                logger.error(f"Riva client not installed: {e}")
                raise ImportError("Please install riva-client: pip install riva-client")
            except grpc.RpcError as e:
                logger.error(f"gRPC error: {e.details()}")
                raise

        if self.key_manager:
            return await self.key_manager.call_with_rotation(do_transcribe)
        else:
            return await do_transcribe()

    async def transcribe_streaming(self, audio_chunks):
        raise NotImplementedError("Streaming transcription not implemented yet")
