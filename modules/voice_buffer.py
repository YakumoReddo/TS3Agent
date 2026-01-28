import asyncio
import os
import wave
import time
import logging
import struct
from typing import Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1


class VoiceBuffer:
    def __init__(self, post_wakeup_window: float = 3.0, command_end_gap: float = 1.0,
                 on_recording_complete = None):
        self.post_wakeup_window = post_wakeup_window
        self.command_end_gap = command_end_gap
        self.on_recording_complete = on_recording_complete

        self._pcm_data: List[int] = []
        self._last_audio_time: Optional[float] = None
        self._is_recording = False
        self._silence_timer: Optional[asyncio.Task] = None
        self._window_timer: Optional[asyncio.Task] = None
        self._latest_recording_path: Optional[str] = None
        self._latest_recording_path: Optional[str] = None

    def reset(self):
        self._pcm_data = []
        self._last_audio_time = None
        self._is_recording = False
        if self._silence_timer:
            self._silence_timer.cancel()
            self._silence_timer = None
        if self._window_timer:
            self._window_timer.cancel()
            self._window_timer = None

    def start_recording(self):
        self.reset()
        self._is_recording = True
        self._last_audio_time = time.time()
        self._window_timer = asyncio.create_task(self._run_post_window_timer())
        logger.info("Started recording after wakeword")

    def add_audio(self, audio_data: bytes):
        if not self._is_recording:
            return

        samples = self._decode_pcm(audio_data)
        self._pcm_data.extend(samples)
        self._last_audio_time = time.time()

        if self._silence_timer:
            self._silence_timer.cancel()

        self._silence_timer = asyncio.create_task(self._run_silence_timer())

    async def _run_post_window_timer(self):
        await asyncio.sleep(self.post_wakeup_window)
        if self._is_recording and len(self._pcm_data) == 0:
            logger.info("Post-wakeup window expired with no audio, abandoning command")
            self.reset()

    async def _run_silence_timer(self):
        await asyncio.sleep(self.command_end_gap)
        if self._is_recording and len(self._pcm_data) > 0:
            logger.info("Silence detected, ending command")
            await self._save_recording()

    def _decode_pcm(self, audio_data: bytes) -> List[int]:
        num_samples = len(audio_data) // 2
        samples = struct.unpack('h' * num_samples, audio_data)
        return list(samples)

    async def _save_recording(self) -> Optional[str]:
        if not self._pcm_data:
            return None

        output_dir = Path("temp/recordings")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time() * 1000)
        output_path = output_dir / f"command_{timestamp}.wav"

        try:
            with wave.open(str(output_path), 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setframerate(SAMPLE_RATE)

                pcm_bytes = struct.pack('h' * len(self._pcm_data), *self._pcm_data)
                wav_file.writeframes(pcm_bytes)

            duration = len(self._pcm_data) / SAMPLE_RATE
            logger.info(f"Saved recording to {output_path}, duration: {duration:.2f}s")
            self._latest_recording_path = str(output_path)
            self._is_recording = False

            if self.on_recording_complete:
                self.on_recording_complete(str(output_path))

            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return None

    def end_and_save(self) -> Optional[str]:
        if self._silence_timer:
            self._silence_timer.cancel()
        if self._window_timer:
            self._window_timer.cancel()

        if self._pcm_data:
            output_dir = Path("temp/recordings")
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            output_path = output_dir / f"command_{timestamp}.wav"

            try:
                with wave.open(str(output_path), 'wb') as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(SAMPLE_WIDTH)
                    wav_file.setframerate(SAMPLE_RATE)

                    pcm_bytes = struct.pack('h' * len(self._pcm_data), *self._pcm_data)
                    wav_file.writeframes(pcm_bytes)

                duration = len(self._pcm_data) / SAMPLE_RATE
                logger.info(f"Saved recording to {output_path}, duration: {duration:.2f}s")
                self.reset()
                return str(output_path)
            except Exception as e:
                logger.error(f"Failed to save recording: {e}")
                self.reset()
                return None

        self.reset()
        return None

    def is_recording(self) -> bool:
        return self._is_recording

    def get_audio_level(self) -> float:
        if not self._pcm_data:
            return 0.0
        return sum(abs(x) for x in self._pcm_data) / len(self._pcm_data)
