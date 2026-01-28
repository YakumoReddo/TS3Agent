import asyncio
import pvporcupine
import logging
from typing import Optional, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    EXECUTING = "executing"


class UserSession:
    def __init__(
        self,
        sender_id: int,
        wakeword_path: str,
        sensitivity: float = 0.7,
        post_wakeup_window: float = 3.0,
        command_end_gap: float = 1.0,
        on_command_complete: Optional[Callable[[str], Awaitable[None]]] = None,
        on_play_audio: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.sender_id = sender_id
        self.state = SessionState.IDLE
        self.wakeword_path = wakeword_path
        self.sensitivity = sensitivity
        self.post_wakeup_window = post_wakeup_window
        self.command_end_gap = command_end_gap
        self.on_command_complete = on_command_complete
        self.on_play_audio = on_play_audio

        self._porcupine: Optional[pvporcupine.Porcupine] = None
        self._last_audio_time = 0.0
        self._lock = asyncio.Lock()

    async def initialize(self):
        try:
            self._porcupine = pvporcupine.create(
                keyword_paths=[self.wakeword_path],
                sensitivities=[self.sensitivity]
            )
            logger.info(f"User {self.sender_id}: Porcupine initialized with {self.wakeword_path}")
        except Exception as e:
            logger.error(f"User {self.sender_id}: Failed to initialize Porcupine: {e}")
            raise

    def is_idle(self) -> bool:
        return self.state == SessionState.IDLE

    async def process_audio(self, audio_data: bytes):
        async with self._lock:
            self._last_audio_time = asyncio.get_event_loop().time()

            if self.state == SessionState.IDLE:
                await self._check_wakeword(audio_data)
            elif self.state == SessionState.LISTENING:
                await self._handle_listening(audio_data)

    async def _check_wakeword(self, audio_data: bytes):
        if not self._porcupine:
            return

        try:
            samples = self._extract_samples(audio_data)
            result = self._porcupine.process(samples)
            if result >= 0:
                logger.info(f"User {self.sender_id}: Wakeword detected!")
                await self._on_wakeword_detected()
        except Exception as e:
            logger.error(f"User {self.sender_id}: Wakeword detection error: {e}")

    def _extract_samples(self, audio_data: bytes):
        import struct
        num_samples = len(audio_data) // 2
        samples = struct.unpack('h' * num_samples, audio_data)
        return list(samples)

    async def _on_wakeword_detected(self):
        self.state = SessionState.LISTENING

        if self.on_play_audio:
            await self.on_play_audio("wakeup_alert")

        if self.on_command_complete:
            await self.on_command_complete("start_listening")

    async def _handle_listening(self, audio_data: bytes):
        if self.on_command_complete:
            await self.on_command_complete("add_audio", audio_data)

    async def end_listening(self) -> str:
        self.state = SessionState.PROCESSING
        if self.on_command_complete:
            return await self.on_command_complete("end_listening")
        return ""

    async def complete_command(self, result_text: str):
        if self.on_command_complete:
            await self.on_command_complete("complete", result_text)
        self.state = SessionState.IDLE

    async def cancel_command(self):
        self.state = SessionState.IDLE
        if self.on_command_complete:
            await self.on_command_complete("cancel")

    def check_idle_timeout(self, current_time: float, idle_timeout: float) -> bool:
        if self.state == SessionState.IDLE:
            if current_time - self._last_audio_time > idle_timeout:
                logger.info(f"User {self.sender_id}: Idle timeout reached, releasing session")
                return True
        return False

    async def cleanup(self):
        if self._porcupine:
            try:
                self._porcupine.delete()
            except Exception as e:
                logger.error(f"User {self.sender_id}: Error cleaning up Porcupine: {e}")
            self._porcupine = None
        logger.info(f"User {self.sender_id}: Session cleaned up")
