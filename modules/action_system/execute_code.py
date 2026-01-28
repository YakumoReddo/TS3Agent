from .base import Action, ActionResult
from typing import Any, Dict
import logging
import importlib.util
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecuteCodeAction(Action):
    name = "execute_code"
    description = "执行预定义的自定义动作代码"
    parameters = {
        "type": "object",
        "properties": {
            "action_name": {"type": "string", "description": "动作名称"},
            "params": {"type": "object", "description": "动作参数"}
        },
        "required": ["action_name"]
    }

    def __init__(self, custom_actions_dir: str = "custom_actions"):
        self.custom_actions_dir = Path(custom_actions_dir)
        self._action_cache: Dict[str, Any] = {}

    async def execute(self, action_name: str, params: Dict = None, **kwargs) -> ActionResult:
        try:
            if params is None:
                params = {}

            module = await self._load_action_module(action_name)
            if not module:
                return ActionResult(False, f"未找到动作: {action_name}")

            if hasattr(module, 'execute'):
                result = await self._call_with_timeout(module.execute, params)
                return ActionResult(True, str(result), result)
            else:
                return ActionResult(False, f"动作 {action_name} 没有 execute 函数")

        except asyncio.TimeoutError:
            return ActionResult(False, f"动作 {action_name} 执行超时")
        except Exception as e:
            logger.error(f"ExecuteCode action failed: {e}")
            return ActionResult(False, f"执行失败: {str(e)}")

    async def _load_action_module(self, action_name: str):
        if action_name in self._action_cache:
            return self._action_cache[action_name]

        action_path = self.custom_actions_dir / f"{action_name}.py"
        if not action_path.exists():
            logger.error(f"Action file not found: {action_path}")
            return None

        try:
            spec = importlib.util.spec_from_file_location(action_name, str(action_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._action_cache[action_name] = module
            return module
        except Exception as e:
            logger.error(f"Failed to load action module: {e}")
            return None

    async def _call_with_timeout(self, func, params, timeout: float = 30.0):
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(params)),
                timeout=timeout
            )
            return result
        except TypeError:
            result = await asyncio.wait_for(func(params), timeout=timeout)
            return result

    def reload_cache(self):
        self._action_cache.clear()
