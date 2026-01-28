# 自定义动作编写规范

## 文件命名

动作文件名为 `<action_name>.py`，例如 `set_reminder.py`

## 文件模板

```python
"""
动作名称: set_reminder
描述: 设置定时提醒
输入参数:
  - time: string - 提醒时间（如 "5分钟后"）
  - message: string - 提醒内容
输出:
  - reminder_id: string - 提醒任务 ID
"""

async def execute(params: dict) -> dict:
    # 解析参数
    time_str = params.get("time", "")
    message = params.get("message", "")

    # 执行逻辑...
    # 这里编写你的 Python 代码
    reminder_id = await set_reminder(time_str, message)

    return {"success": True, "reminder_id": reminder_id}
```

## 函数签名

每个动作文件必须包含一个 `execute` 函数，接收一个字典参数，返回一个字典。

```python
def execute(params: dict) -> dict:
    """
    执行动作

    Args:
        params: 参数字典

    Returns:
        dict: 结果字典，应包含 'success' 字段
    """
    return {"success": True}
```

## 支持同步和异步

`execute` 函数可以是同步或异步的：

```python
# 同步版本
def execute(params: dict) -> dict:
    return {"result": "done"}

# 异步版本
async def execute(params: dict) -> dict:
    await asyncio.sleep(1)
    return {"result": "done"}
```

## 参数访问

通过 `params` 字典访问传入的参数：

```python
def execute(params: dict) -> dict:
    name = params.get("name", "")
    age = params.get("age", 0)

    if not name:
        return {"success": False, "error": "name is required"}

    return {"success": True, "greeting": f"Hello, {name}!"}
```

## 返回值

返回一个包含结果的字典，建议包含 `success` 字段：

```python
return {"success": True, "data": result}

# 或
return {"success": False, "error": "错误信息"}
```

## 注册动作

将编写好的 `.py` 文件放入 `custom_actions/` 目录即可自动注册。

## 示例：天气查询动作

```python
"""
动作名称: get_weather
描述: 查询天气信息
输入参数:
  - city: string - 城市名称
输出:
  - weather: string - 天气状况
  - temperature: float - 温度
"""

import httpx

def execute(params: dict) -> dict:
    city = params.get("city", "")

    if not city:
        return {"success": False, "error": "city is required"}

    try:
        # 调用天气 API
        # 示例代码
        return {
            "success": True,
            "weather": "晴朗",
            "temperature": 25.5
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## 注意事项

1. 动作文件应为可靠代码，避免抛出异常
2. 使用 `try-except` 捕获可能的错误
3. 返回有意义的错误信息
4. 动作执行应有合理超时（默认 30 秒）
5. 可以导入需要的模块
6. 避免写入全局状态
