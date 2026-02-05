# AI Agent 测试文档

本文档说明如何测试AI Agent各个组件的功能，以便调试和验证系统各环节的可用性。

## 目录

1. [测试概述](#测试概述)
2. [环境准备](#环境准备)
3. [唤醒词检测测试](#唤醒词检测测试)
4. [语音识别(ASR)测试](#语音识别asr测试)
5. [大语言模型(LLM)测试](#大语言模型llm测试)
6. [语音合成(TTS)测试](#语音合成tts测试)
7. [动作系统测试](#动作系统测试)
8. [完整流水线测试](#完整流水线测试)
9. [常见问题排查](#常见问题排查)

---

## 测试概述

AI Agent 的处理流程如下：

```
音频输入 → 唤醒词检测 → 语音识别(ASR) → 大语言模型(LLM) → 动作执行 → TTS/音频输出
```

每个环节都提供了独立的测试脚本，可以单独测试各组件的功能。

### 测试文件列表

| 文件 | 用途 |
|------|------|
| `tests/test_wake_word.py` | 测试唤醒词检测 |
| `tests/test_asr.py` | 测试语音识别 |
| `tests/test_llm.py` | 测试大语言模型 |
| `tests/test_tts.py` | 测试语音合成 |
| `tests/test_actions.py` | 测试动作执行系统 |
| `tests/test_pipeline.py` | 测试完整处理流水线 |

---

## 环境准备

### 安装依赖

```bash
# 基础依赖
pip install pyyaml

# 唤醒词检测
pip install pvporcupine

# 语音识别和合成 (Riva)
pip install -e ./python-clients

# 大语言模型
pip install openai

# 音频处理 (可选)
pip install soundfile librosa
```

### 配置文件

复制示例配置并填入您的 API 密钥：

```bash
cp config_example.yaml config.yaml
# 编辑 config.yaml，填入各项 API 密钥
```

### 准备测试音频

建议准备以下测试音频文件：
- 包含唤醒词的音频 (16kHz, 16-bit, WAV)
- 包含指令语音的音频 (任意采样率, WAV)
- 不包含唤醒词的干扰音频

---

## 唤醒词检测测试

### 功能说明

测试 Porcupine 唤醒词检测引擎是否能正确识别音频中的唤醒词。

### 使用方法

```bash
# 使用配置文件
python tests/test_wake_word.py --config config.yaml --audio wake_test.wav

# 使用内置关键词
python tests/test_wake_word.py --access-key YOUR_KEY --keywords porcupine --audio wake_test.wav

# 使用自定义关键词文件
python tests/test_wake_word.py --access-key YOUR_KEY --keyword-paths /path/to/keyword.ppn --audio wake_test.wav

# 调整灵敏度
python tests/test_wake_word.py --config config.yaml --audio wake_test.wav --sensitivity 0.7

# 模拟实时处理
python tests/test_wake_word.py --config config.yaml --audio wake_test.wav --realtime
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--config, -c` | 配置文件路径 |
| `--audio, -a` | 测试音频文件路径 (必需) |
| `--access-key` | Porcupine 访问密钥 |
| `--keywords` | 内置关键词列表 (如 porcupine, alexa) |
| `--keyword-paths` | 自定义关键词文件路径 |
| `--sensitivity` | 检测灵敏度 (0.0-1.0) |
| `--realtime` | 按实时速度处理 |

### 预期结果

**成功情况：**
```
Wake Word Detection Test
============================================================
Keywords to detect: ['porcupine']
Sensitivity: 0.5
Porcupine initialized successfully
  - Frame length: 512 samples
  - Sample rate: 16000 Hz

Audio file info:
  - Channels: 1
  - Sample width: 2 bytes (16-bit)
  - Sample rate: 16000 Hz
  - Duration: 3.00 seconds

Processing audio...
  [DETECTED] 'porcupine' at 1.25 seconds (frame 39)

Test Results
============================================================
Audio duration: 3.00 seconds
Total detections: 1

Detection summary:
  - 'porcupine' at 1.25s

✓ Wake word detected
```

**未检测到情况：**
```
No wake word detected in the audio file.
Possible reasons:
  - The wake word is not present in the audio
  - Audio quality is too low
  - Sensitivity is too low (try increasing it)
  - Sample rate mismatch (audio should be 16kHz)
```

### 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 未检测到唤醒词 | 灵敏度太低 | 增加 `--sensitivity` 值 |
| 未检测到唤醒词 | 采样率不匹配 | 将音频转换为 16kHz |
| 访问密钥错误 | 密钥无效或过期 | 在 Picovoice Console 获取新密钥 |

---

## 语音识别(ASR)测试

### 功能说明

测试 Riva ASR 服务是否能正确将音频转录为文本。

### 使用方法

```bash
# 使用配置文件
python tests/test_asr.py --config config.yaml --audio speech.wav

# 使用直接参数
python tests/test_asr.py --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY \
    --language zh-CN --audio speech.wav

# 详细输出
python tests/test_asr.py --config config.yaml --audio speech.wav --verbose
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--config, -c` | 配置文件路径 |
| `--audio, -a` | 测试音频文件路径 (必需) |
| `--server` | Riva 服务器地址 |
| `--api-key` | API 密钥 |
| `--language` | 语言代码 (如 zh-CN, en-US) |
| `--function-id` | NVCF 功能 ID |
| `--no-ssl` | 禁用 SSL |
| `--verbose, -v` | 详细输出 |

### 预期结果

**成功情况：**
```
ASR (Speech Recognition) Test
============================================================

Configuration:
  - Server: grpc.nvcf.nvidia.com:443
  - Language: zh-CN
  - SSL: True
  - Audio file: speech.wav
  - File size: 45.2 KB

Connecting to Riva server...
  Connected successfully

Reading audio file...
  Read 46280 bytes

Sending to ASR service...
  Response received in 1.23 seconds

Results
============================================================

Result 1:
  [Best] 你好，请播放音乐

Final Transcript:
============================================================
你好，请播放音乐

✓ ASR test completed successfully
```

**失败情况：**
```
No transcription results returned.
Possible reasons:
  - Audio file is empty or too short
  - Audio quality is too low
  - Wrong language code
  - Audio format not supported
```

### 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 连接失败 | 网络问题或服务器地址错误 | 检查网络和服务器配置 |
| 无转录结果 | 音频太短或静音 | 确保音频包含清晰语音 |
| 认证失败 | API 密钥无效 | 检查密钥是否正确 |

---

## 大语言模型(LLM)测试

### 功能说明

测试 LLM API 是否能正确处理文本输入并返回符合格式要求的 JSON 响应。

### 使用方法

```bash
# 使用配置文件
python tests/test_llm.py --config config.yaml --text "播放音乐"

# 使用直接参数
python tests/test_llm.py --api-base https://api.openai.com/v1 \
    --api-key YOUR_KEY --model gpt-4 --text "Hello"

# 测试复杂指令
python tests/test_llm.py --config config.yaml --text "五分钟后提醒我开会"

# 详细输出
python tests/test_llm.py --config config.yaml --text "你好" --verbose
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--config, -c` | 配置文件路径 |
| `--text, -t` | 输入文本 (必需) |
| `--api-base` | API 基础 URL |
| `--api-key` | API 密钥 |
| `--model` | 模型名称 |
| `--prompt-file` | Agent 提示词文件 |
| `--max-tokens` | 最大令牌数 |
| `--temperature` | 采样温度 |
| `--user-id` | 模拟用户 ID |
| `--verbose, -v` | 详细输出 |

### 预期结果

**成功情况：**
```
LLM (Language Model) Test
============================================================

Configuration:
  - API Base: https://api.openai.com/v1
  - Model: gpt-4
  - Input Text: 播放音乐

Sending request to LLM...
  Response received in 2.15 seconds

Raw Response
============================================================
{
  "actions": [
    {
      "type": "speak",
      "params": {
        "text": "好的，正在为您播放音乐。"
      }
    },
    {
      "type": "play_audio",
      "params": {
        "file": "music"
      }
    }
  ]
}

Response Validation
============================================================
✓ Response is valid JSON
✓ 'actions' field present
  Number of actions: 2

  Action 1:
    Type: speak
    Params: {"text": "好的，正在为您播放音乐。"}
    ✓ Valid action type

  Action 2:
    Type: play_audio
    Params: {"file": "music"}
    ✓ Valid action type

Usage Statistics
============================================================
  Model: gpt-4
  Prompt tokens: 1250
  Completion tokens: 85
  Total tokens: 1335

✓ LLM test completed successfully
```

**JSON 格式错误：**
```
✗ Response is not valid JSON: Expecting value: line 1 column 1
```

### 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 响应非 JSON | 模型输出格式不正确 | 检查 Agent.md 提示词 |
| 缺少 actions | 提示词不完整 | 完善 Agent.md 中的格式说明 |
| API 错误 | 密钥或端点问题 | 验证 API 配置 |

---

## 语音合成(TTS)测试

### 功能说明

测试 TTS 服务是否能正确将文本合成为语音。支持两个平台：
- **Riva**: NVIDIA Riva TTS
- **Doubao**: 字节跳动豆包 TTS

### 使用方法

```bash
# 使用配置文件 (自动选择配置中的平台)
python tests/test_tts.py --config config.yaml --text "你好，世界"

# 指定使用 Riva TTS
python tests/test_tts.py --config config.yaml --platform riva --text "你好，世界"

# 指定使用 Doubao TTS
python tests/test_tts.py --config config.yaml --platform doubao --text "你好，世界"

# 保存输出音频
python tests/test_tts.py --config config.yaml --text "Hello, world" --output test_output.wav

# Riva 直接参数
python tests/test_tts.py --platform riva --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY \
    --language en-US --text "Hello" --output output.wav

# Doubao 直接参数
python tests/test_tts.py --platform doubao --doubao-appid YOUR_APPID --doubao-cluster YOUR_CLUSTER \
    --doubao-voice-type YOUR_VOICE_TYPE --api-key YOUR_TOKEN --text "你好" --output output.mp3
```

### 参数说明

#### 通用参数

| 参数 | 说明 |
|------|------|
| `--config, -c` | 配置文件路径 |
| `--text, -t` | 要合成的文本 (必需) |
| `--output, -o` | 输出文件路径 |
| `--platform` | TTS 平台: riva 或 doubao |
| `--api-key` | API 密钥 |
| `--verbose, -v` | 详细输出 |

#### Riva 专用参数

| 参数 | 说明 |
|------|------|
| `--server` | Riva 服务器地址 |
| `--language` | 语言代码 |
| `--voice` | 音色名称 |
| `--sample-rate` | 采样率 (Hz) |
| `--zero-shot-audio` | Zero-shot 音频提示文件 |

#### Doubao 专用参数

| 参数 | 说明 |
|------|------|
| `--doubao-appid` | Doubao 应用 ID |
| `--doubao-cluster` | Doubao 集群 |
| `--doubao-voice-type` | Doubao 音色类型 ID |

### 预期结果

#### Riva TTS 成功情况
```
Using TTS platform: riva

TTS (Text-to-Speech) Test
============================================================

Configuration:
  - Server: grpc.nvcf.nvidia.com:443
  - Language: zh-CN
  - Voice: Default
  - Sample Rate: 48000 Hz

Input Text: 你好，世界

Connecting to Riva server...
  Connected successfully

Synthesizing speech...
  Response received in 0.85 seconds

Results
============================================================
  Audio size: 96000 bytes (93.8 KB)
  Duration: 1.00 seconds
  Sample rate: 48000 Hz
  Synthesis speed: 1.2x real-time

Saving to: test_output.wav
  ✓ Saved successfully

✓ TTS test completed successfully
```

#### Doubao TTS 成功情况
```
Using TTS platform: doubao

Doubao TTS (Text-to-Speech) Test
============================================================

Configuration:
  - API URL: https://openspeech.bytedance.com/api/v1/tts
  - App ID: your_appid
  - Cluster: your_cluster
  - Voice Type: your_voice_type
  - Encoding: mp3

Input Text: 你好，世界

Sending request to Doubao TTS...
  Response received in 0.65 seconds

Results
============================================================
  Audio size: 15360 bytes (15.0 KB)
  Encoding: mp3

Saving to: test_output.mp3
  ✓ Saved successfully

✓ TTS test completed successfully
```

### 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| Riva 连接失败 | 网络或服务器问题 | 检查服务器地址和网络 |
| Riva 输出静音 | 文本或语言代码问题 | 确保文本和语言匹配 |
| Doubao 认证失败 | access_token 无效 | 检查 API 密钥 |
| Doubao 无音频 | appid/cluster/voice_type 错误 | 检查配置参数 |

---

## 动作系统测试

### 功能说明

测试动作执行系统是否能正确解析和执行 LLM 返回的 JSON 动作。

### 使用方法

```bash
# 测试单个 speak 动作
python tests/test_actions.py --action speak --params '{"text": "Hello, world"}'

# 测试 delay 动作
python tests/test_actions.py --action delay --params '{"seconds": 2}'

# 测试自定义脚本
python tests/test_actions.py --action execute_script --params '{"script": "system_info"}'

# 测试完整 JSON 响应
python tests/test_actions.py --json '{"actions": [{"type": "speak", "params": {"text": "Hi"}}]}'

# 测试定时动作
python tests/test_actions.py --schedule --delay 3 --text "Reminder!" --wait
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--action` | 单个动作类型 |
| `--params, -p` | 动作参数 (JSON 格式) |
| `--json, -j` | 完整 JSON 响应 |
| `--schedule` | 测试定时动作 |
| `--delay` | 定时延迟秒数 |
| `--text` | 定时动作文本 |
| `--wait` | 等待定时动作执行 |
| `--verbose, -v` | 详细输出 |

### 支持的动作类型

| 动作类型 | 说明 | 参数示例 |
|----------|------|----------|
| `speak` | TTS 语音 | `{"text": "Hello"}` |
| `play_audio` | 播放音频 | `{"file": "notification"}` |
| `delay` | 延迟 | `{"seconds": 5}` |
| `schedule` | 定时执行 | `{"delay_seconds": 300, "actions": [...]}` |
| `execute_script` | 执行脚本 | `{"script": "system_info", "args": {}}` |
| `nested_action` | 嵌套 LLM | `{"prompt": "...", "context": {}}` |

### 预期结果

**成功情况：**
```
Action System Test - Single Action
============================================================

Action: speak
Params: {"text": "Hello, world"}

Executing action...
    [TTS] Would speak: 'Hello, world'

Results
============================================================

Result 1:
  Success: True
  Message: Spoke: Hello, world...

✓ Action test completed successfully
```

---

## 完整流水线测试

### 功能说明

一次性测试从唤醒词检测到动作执行的完整处理流程。

### 使用方法

```bash
# 测试完整流水线
python tests/test_pipeline.py --config config.yaml --audio command.wav

# 使用模拟转录（跳过 ASR）
python tests/test_pipeline.py --config config.yaml --audio command.wav \
    --skip-asr --mock-transcript "播放音乐"

# 仅测试唤醒词检测
python tests/test_pipeline.py --config config.yaml --audio wake_test.wav \
    --skip-asr --skip-llm --skip-actions

# 详细输出
python tests/test_pipeline.py --config config.yaml --audio command.wav --verbose
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--config, -c` | 配置文件路径 (必需) |
| `--audio, -a` | 测试音频文件 (必需) |
| `--skip-wake-word` | 跳过唤醒词检测 |
| `--skip-asr` | 跳过语音识别 |
| `--skip-llm` | 跳过 LLM 处理 |
| `--skip-actions` | 跳过动作执行 |
| `--mock-transcript` | 使用模拟转录文本 |
| `--verbose, -v` | 详细输出 |

### 预期结果

**成功情况：**
```
Full Pipeline Test
======================================================================
Configuration: config.yaml
Audio file: command.wav

======================================================================
Stage 1: Wake Word Detection
======================================================================
  ✓ Wake word detected at 1.25s

======================================================================
Stage 2: ASR (Speech Recognition)
======================================================================
  ✓ Transcript: 播放音乐

======================================================================
Stage 3: LLM Processing
======================================================================
  ✓ Response received (156 chars)
  ✓ Valid JSON with 2 action(s)

======================================================================
Stage 4: Action Execution
======================================================================
  ✓ Executed 2 action(s)
    Success: 2, Failed: 0
    ✓ Action 1: Spoke: 好的，正在为您播放音乐...
    ✓ Action 2: Playing: music

======================================================================
Pipeline Summary
======================================================================
  wake_word: SUCCESS
  asr: SUCCESS
  llm: SUCCESS
  actions: SUCCESS

✓ Pipeline test completed successfully
```

---

## 常见问题排查

### 1. 导入错误

**问题：** `ImportError: No module named 'xxx'`

**解决：**
```bash
# 安装缺失的依赖
pip install pvporcupine  # 唤醒词
pip install openai       # LLM
pip install -e ./python-clients  # Riva
```

### 2. 配置文件未找到

**问题：** `Config file not found`

**解决：**
```bash
# 复制并编辑配置文件
cp config_example.yaml config.yaml
```

### 3. API 密钥错误

**问题：** `401 Unauthorized` 或 `Authentication failed`

**解决：**
- 检查 config.yaml 中的 API 密钥
- 确认密钥未过期
- 确认密钥有正确的权限

### 4. 音频格式问题

**问题：** 唤醒词检测失败或 ASR 无结果

**解决：**
- 唤醒词检测需要 16kHz, 16-bit, 单声道 WAV
- 使用 ffmpeg 转换：
  ```bash
  ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 output.wav
  ```

### 5. 网络连接问题

**问题：** `Connection refused` 或超时

**解决：**
- 检查网络连接
- 确认服务器地址正确
- 检查防火墙设置

---

## 测试最佳实践

1. **从简单到复杂**：先单独测试各组件，再测试完整流水线

2. **使用清晰的测试音频**：确保测试音频质量高、语音清晰

3. **保存测试结果**：使用 `--output` 参数保存 TTS 输出进行验证

4. **使用详细模式**：遇到问题时添加 `--verbose` 获取更多信息

5. **模拟测试**：使用 `--mock-transcript` 跳过依赖外部服务的环节

6. **检查日志**：查看 agent.log 文件获取详细错误信息
