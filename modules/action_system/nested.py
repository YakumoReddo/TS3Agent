from .base import Action, ActionResult
from typing import Any, Dict, List
import logging
import asyncio

logger = logging.getLogger(__name__)


class NestedAction(Action):
    name = "run_actions"
    description = "嵌套执行多个动作"
    parameters = {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "arguments": {"type": "object"}
                    }
                }
            }
        },
        "required": ["actions"]
    }

    def __init__(self, action_executor, max_depth: int = 3, timeout: float = 30.0):
        self.action_executor = action_executor
        self.max_depth = max_depth
        self.timeout = timeout

    async def execute(self, actions: List[Dict] = None, current_depth: int = 0, **kwargs) -> ActionResult:
        if not actions:
            return ActionResult(True, "没有要执行的动作")

        if current_depth >= self.max_depth:
            return ActionResult(False, f"嵌套层数超过限制 ({self.max_depth})")

        results = []
        success_count = 0
        fail_count = 0

        for action_def in actions:
            action_name = action_def.get("name")
            arguments = action_def.get("arguments", {})

            try:
                result = await asyncio.wait_for(
                    self.action_executor.execute_action(action_name, arguments),
                    timeout=self.timeout
                )
                results.append(result)
                if result.success:
                    success_count += 1
                else:
                    fail_count += 1
            except asyncio.TimeoutError:
                results.append(ActionResult(False, f"动作 {action_name} 执行超时"))
                fail_count += 1
            except Exception as e:
                logger.error(f"Nested action error: {e}")
                results.append(ActionResult(False, str(e)))
                fail_count += 1

        return ActionResult(
            fail_count == 0,
            f"执行完成: {success_count} 成功, {fail_count} 失败",
            {"results": results, "success_count": success_count, "fail_count": fail_count}
        )
