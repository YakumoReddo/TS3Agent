# TS3 Agent相关说明
## 模型调用
本项目使用轮询key调用Riva ASR和Qwen的API端点。使用时，应当检测并读取配置文件，配置文件中指定了Riva ASR和OPENAI兼容API端点的相关信息以及key列表。
## Riva ASR调用示例
```
python python-clients/scripts/asr/transcribe_file_offline.py \
    --server grpc.nvcf.nvidia.com:443 --use-ssl \
    --metadata function-id "b702f636-f60c-4a3d-a6f4-f3568c13bd7d" \
    --metadata "authorization" "Bearer $NVIDIA_API_KEY" \
    --language-code en \
    --input-file <path_to_audio_file>
```

其中NVIDIA_API_KEY为Riva ASR的key。示例中的python-clients/scripts/asr/transcribe_file_offline.py文件与文件夹中transcribe_file_offline.py为同一文件。参照这个文件尝试将功能集成进agent

riva asr的语言和服务器等信息需要从配置文件读取
## LLM API调用示例
常规OPENAI兼容API调用方法即可。端点、key、模型等需要从配置文件中读取
## 唤醒词文件路径
从配置文件中读取
## 预设音频文件位置
从配置文件中读取
## 配置文件其他内容

除了上述配置信息外，配置文件还应该包括

- tcp服务器相关信息
- 用户进程池最大数量
- 释放空闲用户时间（该用户多长时间未收到音频(未发出声音)则将该线程释放)
- 唤醒后的指令边界时间设定
## 动作规范
你需要生成一系列动作规范，用于定义agent.md和操作。

至少包含speak动作，使用tts播放文字。至少包含play_audio动作，播放指定路径的音频。

如果可以的话，希望支持动作嵌套：即有一种动作是执行动作的，即这种动作会再次请求LLM返回动作列表，然后执行这个动作列表。注意设置一下最大嵌套动作层数和超时时间等。

这个动作系统会是关键。类似mcp。我们需要调用这些动作来完成agent的操作。

另外，有些动作可能会由我编写额外的python代码，这类动作一般是输入参数执行这段代码。

动作系统中的执行的python代码，实际上是我预先编写并且存放在指定目录的py文件，并且详细说明了作用及输入输出供llm调用。代码均为可靠代码。
## TTS音频生成
同样使用riva 的tts功能，具体参考riva/client/tts.py文件。其中示例音频zero_shot_audio_prompt_file需要在配置文件中设置。

