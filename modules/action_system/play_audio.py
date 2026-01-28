from .base import Action, ActionResult
from typing import Any, Dict
import logging
import os

logger = logging.getLogger(__name__)


class PlayAudioAction(Action):
    name = "play_audio"
    description = "播放指定的音频文件"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "音频文件路径"},
            "block": {"type": "boolean", "description": "是否阻塞等待播放完成", "default": True}
        },
        "required": ["file_path"]
    }

    def __init__(self, tcp_client):
        self.tcp_client = tcp_client

    async def execute(self, file_path: str, block: bool = True, **kwargs) -> ActionResult:
        try:
            if not os.path.exists(file_path):
                return ActionResult(False, f"音频文件不存在: {file_path}")

            audio_data = self._load_audio(file_path)
            if audio_data:
                self.tcp_client.send_audio(audio_data)
                if block:
                    import asyncio
                    await asyncio.sleep(0.5)
                return ActionResult(True, f"已播放音频: {file_path}")
            return ActionResult(False, "加载音频文件失败")
        except Exception as e:
            logger.error(f"PlayAudio action failed: {e}")
            return ActionResult(False, f"播放失败: {str(e)}")

    def _load_audio(self, file_path: str) -> bytes:
        try:
            import numpy as np
            import soundfile as sf

            audio, sr = sf.read(file_path, dtype='float32')

            if len(audio.shape) == 1:
                audio = np.column_stack([audio, audio])

            if sr != 48000:
                import librosa
                left = librosa.resample(audio[:, 0], orig_sr=sr, target_sr=48000)
                right = librosa.resample(audio[:, 1], orig_sr=sr, target_sr=48000)
                audio = np.column_stack([left, right])

            audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            interleaved = audio_int16.flatten('C')
            return interleaved.tobytes()
        except ImportError:
            with open(file_path, 'rb') as f:
                return f.read()
