from .base import Action, ActionResult
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

_speak_action = None
_play_audio_action = None
_execute_code_action = None


def initialize_actions(tts_engine=None, tcp_client=None, custom_actions_dir="custom_actions"):
    global _speak_action, _play_audio_action, _execute_code_action

    if tts_engine and tcp_client:
        from .speak import SpeakAction
        _speak_action = SpeakAction(tts_engine, tcp_client)

    if tcp_client:
        from .play_audio import PlayAudioAction
        _play_audio_action = PlayAudioAction(tcp_client)
        from .execute_code import ExecuteCodeAction
        _execute_code_action = ExecuteCodeAction(custom_actions_dir)


class ActionExecutor:
    def __init__(self):
        self._actions: Dict[str, Action] = {}
        self._nested_action = None

    def register(self, action: Action):
        self._actions[action.name] = action

    def register_nested(self, nested_action):
        self._nested_action = nested_action

    async def execute_action(self, name: str, arguments: Dict[str, Any] = None) -> ActionResult:
        if arguments is None:
            arguments = {}

        action = self._actions.get(name)
        if action:
            return await action.execute(**arguments)

        if name == "run_actions" and self._nested_action:
            return await self._nested_action.execute(actions=arguments.get("actions", []))

        return ActionResult(False, f"未知动作: {name}")

    def get_action_schema(self, name: str) -> Optional[Dict]:
        action = self._actions.get(name)
        if action:
            return {
                "name": action.name,
                "description": action.description,
                "parameters": action.parameters
            }
        return None

    def list_actions(self) -> Dict[str, Dict]:
        return {
            name: {
                "description": action.description,
                "parameters": action.parameters
            }
            for name, action in self._actions.items()
        }
