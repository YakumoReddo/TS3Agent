"""
动作名称: set_reminder
描述: 设置定时提醒任务
输入参数:
  - time: string - 提醒时间（如 "5分钟后"）
  - message: string - 提醒内容
输出:
  - reminder_id: string - 提醒任务 ID
  - scheduled_time: string - 计划执行时间
"""

import asyncio
import time

# 模拟提醒任务存储
_reminders = {}
_counter = 0


def execute(params: dict) -> dict:
    global _counter

    time_str = params.get("time", "")
    message = params.get("message", "")

    if not time_str:
        return {"success": False, "error": "time is required"}

    if not message:
        return {"success": False, "error": "message is required"}

    _counter += 1
    reminder_id = f"reminder_{_counter}"

    scheduled_time = calculate_scheduled_time(time_str)
    if scheduled_time is None:
        return {"success": False, "error": f"Invalid time format: {time_str}"}

    _reminders[reminder_id] = {
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": time.time()
    }

    return {
        "success": True,
        "reminder_id": reminder_id,
        "scheduled_time": scheduled_time,
        "message": message
    }


def calculate_scheduled_time(time_str: str) -> str:
    now = time.time()

    if "分钟后" in time_str:
        minutes = int(time_str.replace("分钟后", "").strip())
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + minutes * 60))

    if "小时后" in time_str:
        hours = int(time_str.replace("小时后", "").strip())
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + hours * 3600))

    if "秒后" in time_str:
        seconds = int(time_str.replace("秒后", "").strip())
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + seconds))

    return None
