#!/usr/bin/env python3
"""
AI Agent for TS3AudioBot

This agent connects to the TS3AudioBot TCP server, processes voice commands from users,
and executes actions based on LLM responses.

Flow:
1. Connect to TCP server and receive audio from different users
2. Run per-user Porcupine wake word detection
3. After wake word detection, record command with timing rules
4. Send command audio to Riva ASR for transcription
5. Send transcript to LLM (Qwen) with Agent.md prompt
6. Execute actions from LLM response (speak, play_audio, etc.)
"""

import os
import sys
import json
import time
import wave
import socket
import struct
import logging
import threading
import tempfile
import argparse
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import yaml
import array

# Ensure riva client is importable
sys.path.insert(0, str(Path(__file__).parent / "python-clients"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# TCP Protocol Constants
PACKET_AUDIO_OUTPUT = 0
PACKET_VOICE_INPUT = 1
PACKET_AUDIO_FROM_CLIENT = 2
PACKET_COMMAND = 3

# Codec Types
CODEC_OPUS_VOICE = 4  # Mono, 48kHz
CODEC_OPUS_MUSIC = 5  # Stereo, 48kHz

# Audio Constants
SAMPLE_RATE = 48000
OPUS_FRAME_SIZE = 960  # 20ms at 48kHz


@dataclass
class UserState:
    """State for a single user's voice processing."""
    user_id: int
    # Porcupine wake word detector (created per-user)
    porcupine: Any = None
    # Audio buffer for wake word detection
    wake_buffer: List[int] = field(default_factory=list)
    # Command recording state
    is_recording_command: bool = False
    command_audio: List[bytes] = field(default_factory=list)
    command_start_time: float = 0.0
    last_audio_time: float = 0.0
    wake_time: float = 0.0
    # Opus decoder
    decoder: Any = None
    # Thread lock
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Activity tracking
    last_activity_time: float = field(default_factory=time.time)


class KeyRotator:
    """Rotates through a list of API keys."""
    
    def __init__(self, keys: List[str]):
        self.keys = keys if keys else []
        self._index = 0
        self._lock = threading.Lock()
    
    def get_key(self) -> Optional[str]:
        """Get the current API key."""
        if not self.keys:
            return None
        with self._lock:
            return self.keys[self._index]
    
    def rotate(self) -> Optional[str]:
        """Rotate to the next API key and return it."""
        if not self.keys:
            return None
        with self._lock:
            self._index = (self._index + 1) % len(self.keys)
            return self.keys[self._index]


class AIAgent:
    """
    Main AI Agent class that coordinates all components.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the AI Agent.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize API key rotators
        self.asr_keys = KeyRotator(self.config.get('riva_asr', {}).get('api_keys', []))
        self.tts_keys = KeyRotator(self.config.get('riva_tts', {}).get('api_keys', []))
        self.llm_keys = KeyRotator(self.config.get('llm', {}).get('api_keys', []))
        
        # User states - keyed by user_id
        self.users: Dict[int, UserState] = {}
        self.users_lock = threading.Lock()
        
        # TCP connection
        self.socket: Optional[socket.socket] = None
        self.send_lock = threading.Lock()
        self.running = False
        
        # Opus encoder for sending audio
        self.opus_encoder: Any = None
        
        # Action executor (initialized later)
        self.action_executor: Any = None
        
        # Load agent prompt
        self.agent_prompt = self._load_agent_prompt()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self) -> None:
        """Setup logging based on configuration."""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        logger.setLevel(level)
        
        log_file = log_config.get('file')
        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
    
    def _load_agent_prompt(self) -> str:
        """Load the agent prompt from file."""
        prompt_file = Path(self.config.get('agent', {}).get('prompt_file', 'Agent.md'))
        if prompt_file.exists():
            return prompt_file.read_text(encoding='utf-8')
        
        logger.warning(f"Agent prompt file not found: {prompt_file}")
        return ""
    
    def _create_porcupine(self) -> Any:
        """Create a new Porcupine wake word detector."""
        import pvporcupine
        
        wake_config = self.config.get('wake_word', {})
        access_key = wake_config.get('access_key', '')
        
        if not access_key:
            raise ValueError("Porcupine access key not configured")
        
        # Get keyword paths or built-in keywords
        keyword_paths = wake_config.get('keyword_paths')
        keywords = wake_config.get('keywords')
        sensitivity = wake_config.get('sensitivity', 0.5)
        
        if keyword_paths:
            sensitivities = [sensitivity] * len(keyword_paths)
            return pvporcupine.create(
                access_key=access_key,
                keyword_paths=keyword_paths,
                sensitivities=sensitivities
            )
        elif keywords:
            sensitivities = [sensitivity] * len(keywords)
            return pvporcupine.create(
                access_key=access_key,
                keywords=keywords,
                sensitivities=sensitivities
            )
        else:
            raise ValueError("No wake word keywords or keyword_paths configured")
    
    def _create_opus_decoder(self, channels: int = 1) -> Any:
        """Create an Opus decoder."""
        import opuslib
        return opuslib.Decoder(SAMPLE_RATE, channels)
    
    def _create_opus_encoder(self, channels: int = 2) -> Any:
        """Create an Opus encoder for sending audio."""
        import opuslib
        encoder = opuslib.Encoder(SAMPLE_RATE, channels, opuslib.APPLICATION_AUDIO)
        encoder.bitrate = 96000
        return encoder
    
    def _get_or_create_user(self, user_id: int) -> Optional[UserState]:
        """Get or create a user state."""
        with self.users_lock:
            if user_id in self.users:
                user = self.users[user_id]
                user.last_activity_time = time.time()
                return user
            
            # Check pool limit
            pool_config = self.config.get('user_pool', {})
            max_users = pool_config.get('max_users', 10)
            
            if len(self.users) >= max_users:
                # Try to free an idle user
                self._cleanup_idle_users()
                if len(self.users) >= max_users:
                    logger.warning(f"User pool full, cannot create state for user {user_id}")
                    return None
            
            # Create new user state
            logger.info(f"Creating state for user {user_id}")
            user = UserState(user_id=user_id)
            
            try:
                user.porcupine = self._create_porcupine()
                user.decoder = self._create_opus_decoder(channels=1)
            except Exception as e:
                logger.error(f"Failed to initialize user state: {e}")
                return None
            
            self.users[user_id] = user
            return user
    
    def _cleanup_idle_users(self) -> None:
        """Remove idle users from the pool."""
        idle_timeout = self.config.get('user_pool', {}).get('idle_timeout', 300)
        current_time = time.time()
        
        users_to_remove = []
        for user_id, user in self.users.items():
            if current_time - user.last_activity_time > idle_timeout:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            self._remove_user(user_id)
    
    def _remove_user(self, user_id: int) -> None:
        """Remove a user from the pool and clean up resources."""
        if user_id not in self.users:
            return
        
        user = self.users.pop(user_id)
        logger.info(f"Removing user {user_id} from pool")
        
        try:
            if user.porcupine:
                user.porcupine.delete()
        except Exception as e:
            logger.error(f"Error cleaning up porcupine for user {user_id}: {e}")
    
    def connect(self) -> bool:
        """Connect to the TCP server."""
        tcp_config = self.config.get('tcp_server', {})
        host = tcp_config.get('host', 'localhost')
        port = tcp_config.get('port', 9001)
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.socket.settimeout(1.0)  # Allow periodic timeout for clean shutdown
            logger.info(f"Connected to TCP server at {host}:{port}")
            
            # Initialize opus encoder for sending
            self.opus_encoder = self._create_opus_encoder(channels=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to TCP server: {e}")
            return False
    
    def _recv_exact(self, count: int) -> Optional[bytes]:
        """Receive exactly count bytes from socket."""
        data = b''
        while len(data) < count:
            try:
                chunk = self.socket.recv(count - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                if not self.running:
                    return None
                continue
        return data
    
    def _send_packet(self, packet_type: int, data: bytes) -> bool:
        """Send a packet to the TCP server."""
        if not self.socket:
            return False
        
        try:
            with self.send_lock:
                length = 1 + len(data)
                packet = struct.pack('<I', length) + bytes([packet_type]) + data
                self.socket.sendall(packet)
            return True
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False
    
    def send_audio(self, pcm_data: bytes, channels: int = 2) -> bool:
        """
        Send PCM audio to the TCP server.
        
        Args:
            pcm_data: Raw PCM audio (int16, interleaved if stereo)
            channels: Number of channels (1 or 2)
        """
        import numpy as np
        
        # Convert bytes to numpy array
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        
        # If mono and we need stereo, duplicate
        if channels == 1:
            samples = np.column_stack([samples, samples]).flatten()
            channels = 2
        
        # Encode and send in frames
        codec = CODEC_OPUS_MUSIC if channels == 2 else CODEC_OPUS_VOICE
        
        frame_samples = OPUS_FRAME_SIZE * channels
        for i in range(0, len(samples), frame_samples):
            frame = samples[i:i + frame_samples]
            if len(frame) < frame_samples:
                # Pad last frame
                frame = np.pad(frame, (0, frame_samples - len(frame)))
            
            try:
                opus_data = self.opus_encoder.encode(frame.tobytes(), OPUS_FRAME_SIZE)
                self._send_packet(PACKET_AUDIO_FROM_CLIENT, bytes([codec]) + opus_data)
                
                # Rate limit to approximately real-time
                time.sleep(0.018)  # ~20ms per frame
            except Exception as e:
                logger.error(f"Error encoding/sending audio: {e}")
                return False
        
        return True
    
    def send_audio_file(self, file_path: str) -> bool:
        """
        Send an audio file to the TCP server.
        
        Args:
            file_path: Path to the audio file (WAV, FLAC, MP3, etc.)
        """
        import numpy as np
        
        try:
            # Try soundfile first
            try:
                import soundfile as sf
                audio, sr = sf.read(file_path, dtype='float32')
            except ImportError:
                import librosa
                audio, sr = librosa.load(file_path, sr=SAMPLE_RATE, mono=False)
                if len(audio.shape) == 1:
                    audio = np.column_stack([audio, audio])
                elif audio.shape[0] == 2:
                    audio = audio.T
            
            # Ensure stereo
            if len(audio.shape) == 1:
                audio = np.column_stack([audio, audio])
            elif audio.shape[1] == 1:
                audio = np.column_stack([audio[:, 0], audio[:, 0]])
            
            # Resample if needed
            if sr != SAMPLE_RATE:
                try:
                    import librosa
                    left = librosa.resample(audio[:, 0], orig_sr=sr, target_sr=SAMPLE_RATE)
                    right = librosa.resample(audio[:, 1], orig_sr=sr, target_sr=SAMPLE_RATE)
                    audio = np.column_stack([left, right])
                except ImportError:
                    logger.warning(f"Cannot resample, librosa not available")
            
            # Convert to int16
            audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            
            # Send
            return self.send_audio(audio_int16.flatten().tobytes(), channels=2)
            
        except Exception as e:
            logger.error(f"Error sending audio file: {e}")
            return False
    
    def _process_voice_packet(self, user_id: int, codec: int, audio_data: bytes) -> None:
        """Process a voice input packet from a user."""
        user = self._get_or_create_user(user_id)
        if not user:
            return
        
        with user.lock:
            try:
                # Decode Opus to PCM
                pcm_data = user.decoder.decode(audio_data, OPUS_FRAME_SIZE)
                
                # Convert to int16 samples
                samples = array.array('h')
                samples.frombytes(pcm_data)
                
                # Process for wake word detection or command recording
                self._process_user_audio(user, list(samples))
                
            except Exception as e:
                logger.error(f"Error processing voice packet for user {user_id}: {e}")
    
    def _process_user_audio(self, user: UserState, samples: List[int]) -> None:
        """
        Process audio samples for a user.
        Handles wake word detection and command recording.
        """
        current_time = time.time()
        user.last_audio_time = current_time
        
        # Add samples to wake buffer
        user.wake_buffer.extend(samples)
        
        timing_config = self.config.get('command_timing', {})
        grace_period = timing_config.get('grace_period', 3.0)
        silence_threshold = timing_config.get('silence_threshold', 1.0)
        max_duration = timing_config.get('max_duration', 30.0)
        
        if user.is_recording_command:
            # Recording command - add audio
            # Convert samples back to bytes
            sample_array = array.array('h', samples)
            user.command_audio.append(sample_array.tobytes())
            
            # Check for end conditions
            elapsed = current_time - user.command_start_time
            
            # Check max duration
            if elapsed > max_duration:
                logger.info(f"User {user.user_id}: Command max duration reached")
                self._finish_command_recording(user)
                return
            
            # Note: Silence detection would require VAD
            # For simplicity, we rely on the timing after wake word
            # Real implementation should use VAD to detect silence
            
        else:
            # Check wake word
            frame_length = user.porcupine.frame_length
            
            while len(user.wake_buffer) >= frame_length:
                frame = user.wake_buffer[:frame_length]
                user.wake_buffer = user.wake_buffer[frame_length:]
                
                result = user.porcupine.process(frame)
                if result >= 0:
                    logger.info(f"User {user.user_id}: Wake word detected!")
                    self._on_wake_word_detected(user)
                    return
    
    def _on_wake_word_detected(self, user: UserState) -> None:
        """Handle wake word detection for a user."""
        user.wake_time = time.time()
        user.is_recording_command = True
        user.command_audio = []
        user.command_start_time = time.time()
        user.wake_buffer = []  # Clear wake buffer
        
        # Play wake confirmation sound
        self._play_wake_confirmation(user.user_id)
        
        # Start a thread to monitor command timeout
        threading.Thread(
            target=self._monitor_command_timeout,
            args=(user,),
            daemon=True
        ).start()
    
    def _monitor_command_timeout(self, user: UserState) -> None:
        """Monitor for command end (silence timeout)."""
        timing_config = self.config.get('command_timing', {})
        grace_period = timing_config.get('grace_period', 3.0)
        silence_threshold = timing_config.get('silence_threshold', 1.0)
        max_duration = timing_config.get('max_duration', 30.0)
        
        # Wait for grace period
        grace_end = user.wake_time + grace_period
        
        while user.is_recording_command and self.running:
            current_time = time.time()
            
            # Check max duration
            if current_time - user.command_start_time > max_duration:
                with user.lock:
                    if user.is_recording_command:
                        logger.info(f"User {user.user_id}: Max command duration reached")
                        self._finish_command_recording(user)
                return
            
            # After grace period, check for silence
            if current_time > grace_end:
                with user.lock:
                    silence_duration = current_time - user.last_audio_time
                    if silence_duration > silence_threshold and user.command_audio:
                        logger.info(f"User {user.user_id}: Silence detected, ending command")
                        self._finish_command_recording(user)
                        return
            
            time.sleep(0.1)
    
    def _finish_command_recording(self, user: UserState) -> None:
        """Finish recording a command and process it."""
        user.is_recording_command = False
        
        if not user.command_audio:
            logger.info(f"User {user.user_id}: No command audio recorded")
            return
        
        # Combine audio chunks
        audio_data = b''.join(user.command_audio)
        user.command_audio = []
        
        # Process command in a separate thread
        threading.Thread(
            target=self._process_command,
            args=(user.user_id, audio_data),
            daemon=True
        ).start()
    
    def _process_command(self, user_id: int, audio_data: bytes) -> None:
        """
        Process a recorded command.
        
        1. Transcribe with Riva ASR
        2. Send to LLM
        3. Execute actions
        """
        logger.info(f"User {user_id}: Processing command ({len(audio_data)} bytes)")
        
        try:
            # Save audio to temp file for ASR
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name
                with wave.open(f, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(SAMPLE_RATE)
                    wav.writeframes(audio_data)
            
            # Transcribe
            transcript = self._transcribe_audio(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            if not transcript:
                logger.warning(f"User {user_id}: No transcript from ASR")
                self._speak("Sorry, I couldn't understand that.")
                return
            
            logger.info(f"User {user_id}: Transcript: {transcript}")
            
            # Send to LLM
            llm_response = self._call_llm(user_id, transcript)
            
            if not llm_response:
                logger.error(f"User {user_id}: No response from LLM")
                self._speak("Sorry, I encountered an error processing your request.")
                return
            
            logger.info(f"User {user_id}: LLM response received")
            
            # Execute actions
            if self.action_executor:
                results = self.action_executor.execute_response(llm_response)
                for result in results:
                    if not result.success:
                        logger.error(f"Action failed: {result.error}")
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            self._speak("Sorry, an error occurred while processing your command.")
    
    def _transcribe_audio(self, audio_path: str) -> Optional[str]:
        """Transcribe audio using Riva ASR."""
        asr_config = self.config.get('riva_asr', {})
        
        try:
            import riva.client
            
            # Get API key
            api_key = self.asr_keys.get_key()
            if not api_key:
                logger.error("No ASR API key available")
                return None
            
            # Create metadata for authentication
            metadata = []
            function_id = asr_config.get('function_id')
            if function_id:
                metadata.append(['function-id', function_id])
            metadata.append(['authorization', f'Bearer {api_key}'])
            
            # Create auth
            auth = riva.client.Auth(
                ssl_root_cert=None,
                use_ssl=asr_config.get('use_ssl', True),
                uri=asr_config.get('server', 'grpc.nvcf.nvidia.com:443'),
                metadata_args=metadata,
            )
            
            asr_service = riva.client.ASRService(auth)
            
            # Configure recognition
            config = riva.client.RecognitionConfig(
                language_code=asr_config.get('language_code', 'zh-CN'),
                max_alternatives=1,
                enable_automatic_punctuation=True,
            )
            
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # Offline recognition
            response = asr_service.offline_recognize(audio_data, config)
            
            # Extract transcript
            if response.results:
                transcript = ""
                for result in response.results:
                    if result.alternatives:
                        transcript += result.alternatives[0].transcript
                return transcript.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"ASR error: {e}")
            # Try rotating to next key
            self.asr_keys.rotate()
            return None
    
    def _call_llm(self, user_id: int, transcript: str) -> Optional[str]:
        """Call the LLM with the transcript."""
        llm_config = self.config.get('llm', {})
        
        try:
            import openai
            
            api_key = self.llm_keys.get_key()
            if not api_key:
                logger.error("No LLM API key available")
                return None
            
            # Setup client
            client = openai.OpenAI(
                api_key=api_key,
                base_url=llm_config.get('api_base', 'https://api.openai.com/v1')
            )
            
            # Prepare system prompt
            system_prompt = self.agent_prompt
            
            # Add context
            preset_audio = self.action_executor.get_available_preset_audio() if self.action_executor else []
            custom_scripts = self.action_executor.get_available_scripts() if self.action_executor else []
            
            system_prompt = system_prompt.format(
                user_id=user_id,
                timestamp=datetime.now().isoformat(),
                preset_audio_files=', '.join(preset_audio) if preset_audio else 'None',
                custom_scripts=', '.join(custom_scripts) if custom_scripts else 'None'
            )
            
            # Call LLM
            response = client.chat.completions.create(
                model=llm_config.get('model', 'qwen-235b'),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                max_tokens=llm_config.get('max_tokens', 2048),
                temperature=llm_config.get('temperature', 0.7),
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM error: {e}")
            self.llm_keys.rotate()
            return None
    
    def _synthesize_speech(self, text: str) -> Optional[bytes]:
        """Synthesize speech using Riva TTS."""
        tts_config = self.config.get('riva_tts', {})
        
        try:
            import riva.client
            from riva.client.proto.riva_audio_pb2 import AudioEncoding
            
            api_key = self.tts_keys.get_key()
            if not api_key:
                logger.error("No TTS API key available")
                return None
            
            # Create metadata
            metadata = []
            function_id = tts_config.get('function_id')
            if function_id:
                metadata.append(['function-id', function_id])
            metadata.append(['authorization', f'Bearer {api_key}'])
            
            auth = riva.client.Auth(
                ssl_root_cert=None,
                use_ssl=tts_config.get('use_ssl', True),
                uri=tts_config.get('server', 'grpc.nvcf.nvidia.com:443'),
                metadata_args=metadata,
            )
            
            tts_service = riva.client.SpeechSynthesisService(auth)
            
            # Zero shot audio prompt
            zero_shot_file = tts_config.get('zero_shot_audio_prompt_file')
            zero_shot_path = Path(zero_shot_file) if zero_shot_file else None
            
            response = tts_service.synthesize(
                text=text,
                voice_name=tts_config.get('voice_name'),
                language_code=tts_config.get('language_code', 'zh-CN'),
                encoding=AudioEncoding.LINEAR_PCM,
                sample_rate_hz=tts_config.get('sample_rate_hz', SAMPLE_RATE),
                zero_shot_audio_prompt_file=zero_shot_path,
                zero_shot_quality=tts_config.get('zero_shot_quality', 20),
            )
            
            return response.audio
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            self.tts_keys.rotate()
            return None
    
    def _speak(self, text: str) -> None:
        """Synthesize and play speech."""
        audio_data = self._synthesize_speech(text)
        if audio_data:
            self.send_audio(audio_data, channels=1)
    
    def _play_wake_confirmation(self, user_id: int) -> None:
        """Play wake word confirmation sound."""
        preset_config = self.config.get('preset_audio', {})
        wake_file = preset_config.get('wake_confirmation')
        
        if wake_file and Path(wake_file).exists():
            self.send_audio_file(wake_file)
        else:
            # Fallback: speak a short confirmation
            self._speak("Yes?")
    
    def _initialize_action_executor(self) -> None:
        """Initialize the action executor."""
        from actions import ActionExecutor
        
        action_config = self.config.get('action_system', {})
        
        self.action_executor = ActionExecutor(
            tts_callback=self._speak,
            play_audio_callback=self.send_audio_file,
            llm_callback=self._nested_llm_call,
            custom_actions_dir=self.config.get('custom_actions_dir'),
            preset_audio_dir=self.config.get('preset_audio', {}).get('directory'),
            max_nesting_depth=action_config.get('max_nesting_depth', 3),
            action_timeout=action_config.get('action_timeout', 30.0),
            nested_action_timeout=action_config.get('nested_action_timeout', 60.0),
        )
    
    def _nested_llm_call(self, prompt: str, context: dict) -> str:
        """Make a nested LLM call for action chaining."""
        llm_config = self.config.get('llm', {})
        
        try:
            import openai
            
            api_key = self.llm_keys.get_key()
            if not api_key:
                return json.dumps({"actions": [], "error": "No API key"})
            
            client = openai.OpenAI(
                api_key=api_key,
                base_url=llm_config.get('api_base', 'https://api.openai.com/v1')
            )
            
            # Build context message
            context_str = json.dumps(context) if context else ""
            user_message = f"{prompt}\n\nContext: {context_str}" if context_str else prompt
            
            response = client.chat.completions.create(
                model=llm_config.get('model', 'qwen-235b'),
                messages=[
                    {"role": "system", "content": self.agent_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=llm_config.get('max_tokens', 2048),
                temperature=llm_config.get('temperature', 0.7),
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Nested LLM error: {e}")
            return json.dumps({"actions": [], "error": str(e)})
    
    def run(self) -> None:
        """Main run loop."""
        logger.info("AI Agent starting...")
        
        # Initialize action executor
        self._initialize_action_executor()
        
        # Connect to TCP server
        if not self.connect():
            logger.error("Failed to connect to TCP server")
            return
        
        self.running = True
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()
        
        logger.info("AI Agent running. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                # Read packet header
                header = self._recv_exact(4)
                if not header:
                    if self.running:
                        logger.warning("Connection lost")
                    break
                
                length = struct.unpack('<I', header)[0]
                
                # Read packet data
                data = self._recv_exact(length)
                if not data or len(data) < length:
                    if self.running:
                        logger.warning("Connection lost while reading data")
                    break
                
                packet_type = data[0]
                
                if packet_type == PACKET_VOICE_INPUT:
                    # Voice from a user: [PacketType:1][SenderId:2][Codec:1][AudioData:N]
                    sender_id = struct.unpack('<H', data[1:3])[0]
                    codec = data[3]
                    audio_data = data[4:]
                    
                    # Process in thread pool to avoid blocking
                    threading.Thread(
                        target=self._process_voice_packet,
                        args=(sender_id, codec, audio_data),
                        daemon=True
                    ).start()
                
                elif packet_type == PACKET_AUDIO_OUTPUT:
                    # Bot audio output - we can ignore this for agent purposes
                    pass
                
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.stop()
    
    def _cleanup_loop(self) -> None:
        """Periodically clean up idle users."""
        while self.running:
            time.sleep(30)  # Check every 30 seconds
            with self.users_lock:
                self._cleanup_idle_users()
    
    def stop(self) -> None:
        """Stop the agent."""
        logger.info("Stopping AI Agent...")
        self.running = False
        
        # Clean up users
        with self.users_lock:
            for user_id in list(self.users.keys()):
                self._remove_user(user_id)
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        
        # Stop action executor
        if self.action_executor:
            self.action_executor.stop()
        
        logger.info("AI Agent stopped")


def main():
    parser = argparse.ArgumentParser(
        description="AI Agent for TS3AudioBot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("AI Agent for TS3AudioBot")
    print("=" * 60)
    
    try:
        agent = AIAgent(args.config)
        agent.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create a config.yaml file based on config_example.yaml")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutdown requested")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
