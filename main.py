import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from modules.config import Config
from modules.tcp_client import TCPClient, CODEC_OPUS_MUSIC
from modules.speech_recognizer import SpeechRecognizer
from modules.tts_engine import TTSEngine
from modules.llm_handler import LLMHandler
from modules.action_executor import ActionExecutor
from modules.action_system.speak import SpeakAction
from modules.action_system.play_audio import PlayAudioAction
from modules.action_system.execute_code import ExecuteCodeAction
from modules.action_system.nested import NestedAction
from modules.user_session import UserSession, SessionState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/agent.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, config: Dict, action_executor: ActionExecutor, audio_files: Dict):
        self.sessions: Dict[int, UserSession] = {}
        self.config = config
        self.action_executor = action_executor
        self.audio_files = audio_files
        self.max_users = config.get("max_users", 10)
        self.idle_timeout = config.get("idle_timeout", 300)
        self.post_wakeup_window = config.get("post_wakeup_window", 3.0)
        self.command_end_gap = config.get("command_end_gap", 1.0)

        self._wakeword_config = {}
        self._on_play_audio_callback = None
        self._on_tts_callback = None

    def set_wakeword_config(self, wakeword_config: Dict):
        self._wakeword_config = wakeword_config

    def set_callbacks(self, on_play_audio, on_tts):
        self._on_play_audio_callback = on_play_audio
        self._on_tts_callback = on_tts

    def get_or_create(self, sender_id: int) -> UserSession:
        if sender_id in self.sessions:
            return self.sessions[sender_id]

        if len(self.sessions) >= self.max_users:
            oldest_id = min(self.sessions.keys(), key=lambda x: self.sessions[x]._last_audio_time)
            logger.info(f"Removing oldest session {oldest_id} to make room for {sender_id}")
            asyncio.create_task(self.sessions[oldest_id].cleanup())
            del self.sessions[oldest_id]

        session = UserSession(
            sender_id=sender_id,
            wakeword_path=self._wakeword_config.get("path", "resources/wakeword/hey_jarvis.ppn"),
            sensitivity=self._wakeword_config.get("sensitivity", 0.7),
            post_wakeup_window=self.post_wakeup_window,
            command_end_gap=self.command_end_gap,
            on_command_complete=self._create_session_callback(sender_id),
            on_play_audio=self._on_play_audio_callback,
        )

        asyncio.create_task(session.initialize())
        self.sessions[sender_id] = session
        logger.info(f"Created session for user {sender_id}")
        return session

    def _create_session_callback(self, sender_id: int):
        async def callback(event: str, data):
            session = self.sessions.get(sender_id)
            if not session:
                return

            if event == "start_listening":
                logger.info(f"User {sender_id}: Started listening after wakeword")
            elif event == "add_audio":
                if isinstance(data, bytes):
                    await self._process_audio_chunk(sender_id, data)
            elif event == "end_listening":
                await self._process_command(sender_id)

        return callback

    async def _process_audio_chunk(self, sender_id: int, audio_data: bytes):
        pass

    async def _process_command(self, sender_id: int):
        session = self.sessions.get(sender_id)
        if not session:
            return

        logger.info(f"User {sender_id}: Processing command")

        recording_path = self._get_recording_path(sender_id)

        if recording_path and os.path.exists(recording_path):
            try:
                recognizer = getattr(self, '_recognizer', None)
                llm_handler = getattr(self, '_llm_handler', None)

                if recognizer:
                    text = await recognizer.transcribe(recording_path)
                    logger.info(f"User {sender_id}: Transcribed text: {text}")

                    if text and llm_handler:
                        response = await llm_handler.chat_json(text)
                        logger.info(f"User {sender_id}: LLM response: {response}")

                        if response.get("actions"):
                            for action in response["actions"]:
                                await self.action_executor.execute_action(
                                    action.get("name"),
                                    action.get("arguments", {})
                                )

            except Exception as e:
                logger.error(f"User {sender_id}: Error processing command: {e}")
        else:
            logger.warning(f"User {sender_id}: No recording found")

        session.state = SessionState.IDLE

    def _get_recording_path(self, sender_id: int) -> Optional[str]:
        recordings_dir = Path("temp/recordings")
        if not recordings_dir.exists():
            return None

        user_recordings = list(recordings_dir.glob(f"command_*.wav"))
        if user_recordings:
            return str(sorted(user_recordings)[-1])
        return None

    def check_idle_timeouts(self):
        current_time = asyncio.get_event_loop().time()
        to_remove = []
        for sender_id, session in self.sessions.items():
            if session.check_idle_timeout(current_time, self.idle_timeout):
                to_remove.append(sender_id)

        for sender_id in to_remove:
            asyncio.create_task(self.sessions[sender_id].cleanup())
            del self.sessions[sender_id]


async def main():
    config = Config("config/config.yaml")

    logger.info("Starting TS3 AI Agent...")

    tcp_client = TCPClient(config.tcp["host"], config.tcp["port"])
    if not tcp_client.connect():
        logger.error("Failed to connect to TCP server")
        return

    await tcp_client.start_receiving()

    recognizer = SpeechRecognizer(config.riva_asr)
    tts_engine = TTSEngine(config.riva_tts)

    system_prompt = ""
    agent_md_path = Path("config/Agent.md")
    if agent_md_path.exists():
        with open(agent_md_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        logger.info(f"Loaded system prompt from {agent_md_path}")

    llm_handler = LLMHandler(config.openai_api, system_prompt)

    action_executor = ActionExecutor()
    action_executor.register(SpeakAction(tts_engine, tcp_client))
    action_executor.register(PlayAudioAction(tcp_client))
    action_executor.register(ExecuteCodeAction(config.actions["custom_actions_dir"]))
    action_executor.register_nested(NestedAction(action_executor,
                                                   config.actions["max_nesting_depth"],
                                                   config.actions["nested_timeout"]))

    async def play_audio_callback(file_key: str):
        file_path = config.audio_files.get(file_key)
        if file_path and os.path.exists(file_path):
            audio_data = load_audio_file(file_path)
            if audio_data:
                tcp_client.send_audio(audio_data)
                logger.info(f"Played audio file: {file_path}")

    def load_audio_file(file_path: str) -> bytes:
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
        except Exception as e:
            logger.error(f"Failed to load audio file: {e}")
            with open(file_path, 'rb') as f:
                return f.read()

    session_manager = SessionManager(config.session, action_executor, config.audio_files)
    session_manager.set_wakeword_config(config.wakeword)
    session_manager.set_callbacks(play_audio_callback, None)
    session_manager._recognizer = recognizer
    session_manager._llm_handler = llm_handler

    def on_voice_input(sender_id: int, audio_data: bytes, codec: int):
        session = session_manager.get_or_create(sender_id)
        asyncio.create_task(session.process_audio(audio_data))

    tcp_client.set_callback('voice_input', on_voice_input)
    tcp_client.set_callback('disconnected', lambda: logger.warning("TCP connection lost"))

    logger.info("TS3 AI Agent is running. Press Ctrl+C to stop.")

    idle_check_task = None
    try:
        idle_check_task = asyncio.create_task(check_idle_timeouts(session_manager))
        while tcp_client.is_connected():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if idle_check_task:
            idle_check_task.cancel()
            try:
                await idle_check_task
            except asyncio.CancelledError:
                pass

        for session in session_manager.sessions.values():
            await session.cleanup()

        await tcp_client.disconnect()
        logger.info("Shutdown complete")


async def check_idle_timeouts(session_manager: SessionManager):
    while True:
        await asyncio.sleep(60)
        session_manager.check_idle_timeouts()


if __name__ == "__main__":
    asyncio.run(main())
