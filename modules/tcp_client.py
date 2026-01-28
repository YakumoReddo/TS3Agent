import socket
import struct
import asyncio
import logging
from typing import Callable, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class PacketType(Enum):
    AUDIO_OUTPUT = 0
    VOICE_INPUT = 1
    AUDIO_FROM_CLIENT = 2
    COMMAND = 3


class CodecType(Enum):
    OPUS_VOICE = 4
    OPUS_MUSIC = 5


class CommandType(Enum):
    STOP = 0
    CLEAR_QUEUE = 1
    PAUSE = 2
    RESUME = 3


PACKET_AUDIO_OUTPUT = 0
PACKET_VOICE_INPUT = 1
PACKET_AUDIO_FROM_CLIENT = 2
PACKET_COMMAND = 3

CODEC_OPUS_VOICE = 4
CODEC_OPUS_MUSIC = 5

CMD_STOP = 0
CMD_CLEAR_QUEUE = 1
CMD_PAUSE = 2
CMD_RESUME = 3

SAMPLE_RATE = 48000
CHANNELS = 2


def recv_exact(sock: socket.socket, count: int, timeout: float = 10.0) -> Optional[bytes]:
    data = b''
    sock.settimeout(timeout)
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


class TCPClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self._receive_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, Callable] = {}

    def set_callback(self, event: str, callback: Callable):
        self._callbacks[event] = callback

    def _emit(self, event: str, *args, **kwargs):
        callback = self._callbacks.get(event)
        if callback:
            callback(*args, **kwargs)

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False

    async def start_receiving(self):
        if not self.socket:
            raise RuntimeError("Not connected")
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        while self.connected and self.socket:
            try:
                header = recv_exact(self.socket, 4, timeout=1.0)
                if not header:
                    logger.info("Connection closed by server")
                    break

                length = struct.unpack('<I', header)[0]
                data = recv_exact(self.socket, length, timeout=5.0)
                if not data or len(data) < length:
                    logger.info("Connection closed while reading data")
                    break

                await self._handle_packet(data)

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error receiving packet: {e}")
                break

        self.connected = False
        self._emit('disconnected')

    async def _handle_packet(self, data: bytes):
        packet_type = data[0]

        if packet_type == PACKET_AUDIO_OUTPUT:
            codec = data[1]
            audio_data = data[2:]
            self._emit('audio_output', audio_data, codec)

        elif packet_type == PACKET_VOICE_INPUT:
            sender_id = struct.unpack('<H', data[1:3])[0]
            codec = data[3]
            audio_data = data[4:]
            self._emit('voice_input', sender_id, audio_data, codec)

    def send_packet(self, packet_type: int, data: bytes):
        if not self.connected or not self.socket:
            raise RuntimeError("Not connected")

        length = len(data)
        packet = struct.pack('<I', length) + bytes([packet_type]) + data
        self.socket.sendall(packet)

    def send_audio(self, audio_data: bytes, codec: int = CODEC_OPUS_MUSIC):
        packet_data = bytes([codec]) + audio_data
        self.send_packet(PACKET_AUDIO_FROM_CLIENT, packet_data)

    def send_command(self, command_type: int):
        packet_data = bytes([command_type])
        self.send_packet(PACKET_COMMAND, packet_data)

    def stop_playback(self):
        self.send_command(CMD_STOP)

    def clear_queue(self):
        self.send_command(CMD_CLEAR_QUEUE)

    def pause(self):
        self.send_command(CMD_PAUSE)

    def resume(self):
        self.send_command(CMD_RESUME)

    async def disconnect(self):
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"Error closing socket: {e}")
            self.socket = None

        logger.info("Disconnected")

    def is_connected(self) -> bool:
        return self.connected and self.socket is not None
