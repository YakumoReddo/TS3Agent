# AI Agent for TS3AudioBot

This is an external AI agent that connects to TS3AudioBot via TCP, processes voice commands from users using wake word detection, speech recognition, and LLM, and executes actions like TTS responses.

## Features

- **Multi-user Support**: Handles multiple users simultaneously with independent wake word detection
- **Wake Word Detection**: Uses Porcupine for efficient wake word detection per user
- **Speech Recognition**: Integrates with NVIDIA Riva ASR for accurate transcription
- **LLM Integration**: Sends transcripts to Qwen/OpenAI-compatible LLM for command processing
- **Text-to-Speech**: Uses Riva TTS to speak responses back to users
- **Action System**: Extensible action system supporting:
  - `speak` - TTS responses
  - `play_audio` - Play preset audio files
  - `delay` - Wait between actions
  - `schedule` - Schedule delayed actions (e.g., reminders)
  - `execute_script` - Run custom Python scripts
  - `nested_action` - Chain LLM calls for complex tasks
- **API Key Rotation**: Automatic rotation through multiple API keys on errors
- **Configurable Timing**: Adjustable wake word grace period, silence detection, etc.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TS3AudioBot                              │
│                    (TCP Server on 9001)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ TCP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    TCP Client                                ││
│  │         (Receives voice, sends audio/commands)               ││
│  └─────────────────────────┬───────────────────────────────────┘│
│                            │                                     │
│  ┌─────────────────────────▼───────────────────────────────────┐│
│  │              Per-User Processing Threads                     ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         ││
│  │  │   User 1    │  │   User 2    │  │   User N    │         ││
│  │  │ Porcupine   │  │ Porcupine   │  │ Porcupine   │         ││
│  │  │ Wake Word   │  │ Wake Word   │  │ Wake Word   │         ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘         ││
│  └─────────────────────────┬───────────────────────────────────┘│
│                            │ Wake word detected                  │
│  ┌─────────────────────────▼───────────────────────────────────┐│
│  │              Command Recording                               ││
│  │  (3s grace period, 1s silence = end, 30s max)               ││
│  └─────────────────────────┬───────────────────────────────────┘│
│                            │                                     │
│  ┌─────────────────────────▼───────────────────────────────────┐│
│  │              Riva ASR (Speech-to-Text)                       ││
│  └─────────────────────────┬───────────────────────────────────┘│
│                            │ Transcript                          │
│  ┌─────────────────────────▼───────────────────────────────────┐│
│  │              LLM (Qwen 235b / OpenAI)                        ││
│  │              + Agent.md prompt                               ││
│  └─────────────────────────┬───────────────────────────────────┘│
│                            │ JSON Actions                        │
│  ┌─────────────────────────▼───────────────────────────────────┐│
│  │              Action Executor                                 ││
│  │  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌───────────┐    ││
│  │  │  speak   │ │ play_audio │ │ schedule │ │  scripts  │    ││
│  │  └──────────┘ └────────────┘ └──────────┘ └───────────┘    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

1. **Python 3.8+**
2. **System dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libopus0
   
   # macOS
   brew install opus
   ```

3. **Python packages**:
   ```bash
   pip install opuslib pvporcupine pyyaml openai numpy soundfile
   
   # For Riva client (install from python-clients directory)
   pip install -e ./python-clients
   ```

### Configuration

1. Copy the example configuration:
   ```bash
   cp config_example.yaml config.yaml
   ```

2. Edit `config.yaml` with your settings:
   - **TCP Server**: Host and port of TS3AudioBot TCP server
   - **Wake Word**: Porcupine access key and keyword settings
   - **Riva ASR/TTS**: Server address, API keys, language settings
   - **LLM**: API endpoint, model name, API keys
   - **Timing**: Grace period, silence threshold, max duration

3. Get required API keys:
   - **Porcupine**: [Picovoice Console](https://console.picovoice.ai/)
   - **NVIDIA Riva**: [NVIDIA NGC](https://catalog.ngc.nvidia.com/)
   - **LLM**: Your OpenAI-compatible API provider

## Usage

### Basic Usage

```bash
python ai_agent.py --config config.yaml
```

### Configuration Options

See `config_example.yaml` for all available options. Key settings include:

```yaml
# Audio settings for each component
audio:
  tcp_input:
    sample_rate: 48000  # TS3AudioBot sends 48kHz audio
    channels: 1
  wake_word:
    sample_rate: 16000  # Porcupine requires 16kHz (auto-resampled)
    channels: 1
  asr:
    sample_rate: 48000  # ASR can use 48kHz
    channels: 1
  tts:
    sample_rate: 48000
    channels: 1

# TTS Platform Selection
tts:
  platform: "riva"  # Options: "riva", "doubao"

# Wake word settings
wake_word:
  access_key: "YOUR_PORCUPINE_ACCESS_KEY"
  keywords:
    - "porcupine"  # Built-in keyword
  sensitivity: 0.5

# Command timing
command_timing:
  grace_period: 3.0      # Seconds to wait for user to start speaking
  silence_threshold: 1.0  # Seconds of silence to end recording
  max_duration: 30.0     # Maximum command duration

# Riva ASR
riva_asr:
  server: "grpc.nvcf.nvidia.com:443"
  language_code: "zh-CN"
  api_keys:
    - "YOUR_API_KEY"

# Riva TTS (when tts.platform = "riva")
riva_tts:
  server: "grpc.nvcf.nvidia.com:443"
  language_code: "zh-CN"
  api_keys:
    - "YOUR_API_KEY"

# Doubao TTS (when tts.platform = "doubao")
doubao_tts:
  appid: "YOUR_DOUBAO_APPID"
  cluster: "YOUR_DOUBAO_CLUSTER"
  voice_type: "YOUR_VOICE_TYPE"
  api_keys:
    - "YOUR_DOUBAO_ACCESS_TOKEN"
```

### TTS Platform Options

The agent supports two TTS platforms:

#### 1. NVIDIA Riva TTS (default)

```yaml
tts:
  platform: "riva"

riva_tts:
  server: "grpc.nvcf.nvidia.com:443"
  use_ssl: true
  language_code: "zh-CN"
  sample_rate_hz: 48000
  api_keys:
    - "YOUR_NVIDIA_API_KEY"
```

#### 2. ByteDance Doubao TTS

```yaml
tts:
  platform: "doubao"

doubao_tts:
  api_url: "https://openspeech.bytedance.com/api/v1/tts"
  appid: "YOUR_DOUBAO_APPID"
  cluster: "YOUR_DOUBAO_CLUSTER"
  voice_type: "YOUR_VOICE_TYPE_ID"
  encoding: "mp3"  # mp3, wav, pcm
  speed_ratio: 1.0
  volume_ratio: 1.0
  pitch_ratio: 1.0
  api_keys:
    - "YOUR_DOUBAO_ACCESS_TOKEN"
```

### Audio Sample Rate Notes

- **TCP Input (48kHz)**: Audio from TS3AudioBot is Opus-encoded at 48kHz
- **Wake Word (16kHz)**: Porcupine requires 16kHz mono audio. The agent automatically resamples from 48kHz to 16kHz
- **ASR (48kHz)**: Riva ASR works well with 48kHz audio
- **TTS (48kHz)**: TTS output is generated at the configured sample rate

At startup, the agent logs all audio settings and TTS platform for debugging:

```
INFO - Audio Configuration
INFO - TTS Platform: riva
```

## Action System

The agent uses a JSON-based action system. The LLM returns actions in this format:

```json
{
  "actions": [
    {
      "type": "speak",
      "params": {
        "text": "Hello! How can I help you?"
      }
    }
  ]
}
```

### Available Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `speak` | TTS response | `text`: Text to speak |
| `play_audio` | Play audio file | `file`: Preset audio name |
| `delay` | Wait | `seconds`: Duration |
| `schedule` | Delayed execution | `delay_seconds`, `actions` |
| `execute_script` | Run Python script | `script`, `args` |
| `nested_action` | Chain LLM call | `prompt`, `context` |

### Custom Scripts

Add custom Python scripts to `actions_scripts/` directory:

```python
# actions_scripts/my_action.py
def execute(param1: str = "", **kwargs) -> dict:
    # Your logic here
    return {"status": "success", "result": param1}
```

## Agent Prompt

The `Agent.md` file defines how the LLM should respond. Edit this file to customize:
- Available actions and their usage
- Response format guidelines
- Example interactions
- Behavior rules

## Troubleshooting

### Connection Issues
- Ensure TS3AudioBot is running with TCP server enabled
- Check firewall settings for the TCP port
- Verify host/port in config.yaml

### Wake Word Not Detected
- Check Porcupine access key is valid
- Verify keyword path or built-in keyword name
- Adjust sensitivity (higher = more sensitive)

### ASR/TTS Errors
- Verify API keys are correct
- Check network connectivity to Riva server
- Ensure audio format is correct (48kHz, mono/stereo)

### LLM Errors
- Check API key and endpoint
- Verify model name is correct
- Check response format from LLM

## Files

| File | Description |
|------|-------------|
| `ai_agent.py` | Main agent script |
| `actions.py` | Action system implementation |
| `config_example.yaml` | Configuration template |
| `Agent.md` | LLM system prompt |
| `actions_scripts/` | Custom action scripts |

## License

MIT License
