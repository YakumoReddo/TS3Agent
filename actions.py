#!/usr/bin/env python3
"""
Actions module for the AI Agent.
Defines the action system for executing LLM responses.
"""

import os
import json
import time
import logging
import threading
import importlib.util
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    message: str = ""
    data: Any = None
    error: Optional[str] = None


class ActionExecutor:
    """
    Executes actions returned by the LLM.
    Supports built-in actions and custom Python scripts.
    """
    
    def __init__(
        self,
        tts_callback: Callable[[str], None],
        play_audio_callback: Callable[[str], None],
        llm_callback: Callable[[str, dict], dict],
        custom_actions_dir: Optional[str] = None,
        preset_audio_dir: Optional[str] = None,
        max_nesting_depth: int = 3,
        action_timeout: float = 30.0,
        nested_action_timeout: float = 60.0,
    ):
        """
        Initialize the ActionExecutor.
        
        Args:
            tts_callback: Function to call for TTS (text -> audio playback)
            play_audio_callback: Function to call for playing audio files (path -> playback)
            llm_callback: Function to call for nested LLM requests (prompt, context) -> response
            custom_actions_dir: Directory containing custom action scripts
            preset_audio_dir: Directory containing preset audio files
            max_nesting_depth: Maximum depth for nested actions
            action_timeout: Timeout for each action in seconds
            nested_action_timeout: Total timeout for nested action chains
        """
        self.tts_callback = tts_callback
        self.play_audio_callback = play_audio_callback
        self.llm_callback = llm_callback
        self.custom_actions_dir = Path(custom_actions_dir) if custom_actions_dir else None
        self.preset_audio_dir = Path(preset_audio_dir) if preset_audio_dir else None
        self.max_nesting_depth = max_nesting_depth
        self.action_timeout = action_timeout
        self.nested_action_timeout = nested_action_timeout
        
        # Scheduled actions storage
        self._scheduled_actions: List[dict] = []
        self._scheduler_lock = threading.Lock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_running = False
        
        # Thread pool for action execution
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Load custom action scripts
        self._custom_scripts: Dict[str, Any] = {}
        self._load_custom_scripts()
        
        # Start scheduler
        self._start_scheduler()
    
    def _load_custom_scripts(self) -> None:
        """Load custom action scripts from the custom_actions_dir."""
        if not self.custom_actions_dir or not self.custom_actions_dir.exists():
            return
        
        for script_path in self.custom_actions_dir.glob("*.py"):
            script_name = script_path.stem
            try:
                spec = importlib.util.spec_from_file_location(script_name, script_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._custom_scripts[script_name] = module
                    logger.info(f"Loaded custom script: {script_name}")
            except Exception as e:
                logger.error(f"Failed to load custom script {script_name}: {e}")
    
    def get_available_scripts(self) -> List[str]:
        """Get list of available custom scripts."""
        return list(self._custom_scripts.keys())
    
    def get_available_preset_audio(self) -> List[str]:
        """Get list of available preset audio files."""
        if not self.preset_audio_dir or not self.preset_audio_dir.exists():
            return []
        
        audio_extensions = {'.wav', '.mp3', '.flac', '.ogg'}
        return [
            f.stem for f in self.preset_audio_dir.iterdir()
            if f.suffix.lower() in audio_extensions
        ]
    
    def _start_scheduler(self) -> None:
        """Start the scheduler thread for delayed actions."""
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
    
    def _scheduler_loop(self) -> None:
        """Main loop for the scheduler."""
        while self._scheduler_running:
            current_time = time.time()
            actions_to_execute = []
            
            with self._scheduler_lock:
                # Find actions that are due
                remaining = []
                for scheduled in self._scheduled_actions:
                    if scheduled['execute_at'] <= current_time:
                        actions_to_execute.append(scheduled)
                    else:
                        remaining.append(scheduled)
                self._scheduled_actions = remaining
            
            # Execute due actions
            for scheduled in actions_to_execute:
                try:
                    logger.info(f"Executing scheduled actions")
                    self.execute_actions(scheduled['actions'], depth=0)
                except Exception as e:
                    logger.error(f"Error executing scheduled actions: {e}")
            
            time.sleep(0.5)  # Check every 500ms
    
    def stop(self) -> None:
        """Stop the action executor and scheduler."""
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2.0)
        self._executor.shutdown(wait=False)
    
    def execute_response(self, llm_response: str, depth: int = 0) -> List[ActionResult]:
        """
        Execute actions from an LLM response.
        
        Args:
            llm_response: JSON string from the LLM
            depth: Current nesting depth
            
        Returns:
            List of ActionResult objects
        """
        try:
            response_data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from LLM: {e}")
            return [ActionResult(success=False, error=f"Invalid JSON: {e}")]
        
        actions = response_data.get('actions', [])
        if not actions:
            logger.warning("No actions in LLM response")
            return [ActionResult(success=True, message="No actions to execute")]
        
        return self.execute_actions(actions, depth)
    
    def execute_actions(self, actions: List[dict], depth: int = 0) -> List[ActionResult]:
        """
        Execute a list of actions.
        
        Args:
            actions: List of action dictionaries
            depth: Current nesting depth
            
        Returns:
            List of ActionResult objects
        """
        if depth > self.max_nesting_depth:
            logger.error(f"Max nesting depth ({self.max_nesting_depth}) exceeded")
            return [ActionResult(success=False, error="Max nesting depth exceeded")]
        
        results = []
        for action in actions:
            try:
                result = self._execute_single_action(action, depth)
                results.append(result)
                
                # Stop on critical errors
                if not result.success and result.error:
                    logger.error(f"Action failed: {result.error}")
            except Exception as e:
                logger.error(f"Exception executing action: {e}")
                results.append(ActionResult(success=False, error=str(e)))
        
        return results
    
    def _execute_single_action(self, action: dict, depth: int) -> ActionResult:
        """Execute a single action with timeout."""
        action_type = action.get('type', '')
        params = action.get('params', {})
        
        logger.info(f"Executing action: {action_type} (depth={depth})")
        
        # Map action types to handlers
        handlers = {
            'speak': self._action_speak,
            'play_audio': self._action_play_audio,
            'delay': self._action_delay,
            'schedule': self._action_schedule,
            'execute_script': self._action_execute_script,
            'nested_action': lambda p: self._action_nested(p, depth),
        }
        
        handler = handlers.get(action_type)
        if not handler:
            return ActionResult(success=False, error=f"Unknown action type: {action_type}")
        
        # Execute with timeout
        try:
            future = self._executor.submit(handler, params)
            timeout = self.nested_action_timeout if action_type == 'nested_action' else self.action_timeout
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            return ActionResult(success=False, error=f"Action timed out after {timeout}s")
        except Exception as e:
            return ActionResult(success=False, error=str(e))
    
    def _action_speak(self, params: dict) -> ActionResult:
        """Execute speak action - TTS."""
        text = params.get('text', '')
        if not text:
            return ActionResult(success=False, error="No text provided for speak action")
        
        try:
            self.tts_callback(text)
            return ActionResult(success=True, message=f"Spoke: {text[:50]}...")
        except Exception as e:
            return ActionResult(success=False, error=f"TTS failed: {e}")
    
    def _action_play_audio(self, params: dict) -> ActionResult:
        """Execute play_audio action - play preset audio file."""
        file_name = params.get('file', '')
        if not file_name:
            return ActionResult(success=False, error="No file provided for play_audio action")
        
        # Find the audio file
        if self.preset_audio_dir:
            audio_extensions = ['.wav', '.mp3', '.flac', '.ogg']
            audio_path = None
            for ext in audio_extensions:
                candidate = self.preset_audio_dir / f"{file_name}{ext}"
                if candidate.exists():
                    audio_path = candidate
                    break
            
            if audio_path:
                try:
                    self.play_audio_callback(str(audio_path))
                    return ActionResult(success=True, message=f"Playing: {file_name}")
                except Exception as e:
                    return ActionResult(success=False, error=f"Playback failed: {e}")
        
        return ActionResult(success=False, error=f"Audio file not found: {file_name}")
    
    def _action_delay(self, params: dict) -> ActionResult:
        """Execute delay action - wait for specified duration."""
        seconds = params.get('seconds', 0)
        if seconds <= 0:
            return ActionResult(success=True, message="No delay")
        
        time.sleep(seconds)
        return ActionResult(success=True, message=f"Delayed {seconds}s")
    
    def _action_schedule(self, params: dict) -> ActionResult:
        """Execute schedule action - schedule actions for later execution."""
        delay_seconds = params.get('delay_seconds', 0)
        actions = params.get('actions', [])
        
        if delay_seconds <= 0:
            return ActionResult(success=False, error="Invalid delay_seconds")
        if not actions:
            return ActionResult(success=False, error="No actions to schedule")
        
        execute_at = time.time() + delay_seconds
        
        with self._scheduler_lock:
            self._scheduled_actions.append({
                'execute_at': execute_at,
                'actions': actions,
            })
        
        return ActionResult(
            success=True,
            message=f"Scheduled {len(actions)} action(s) for {delay_seconds}s from now"
        )
    
    def _action_execute_script(self, params: dict) -> ActionResult:
        """Execute a custom Python script."""
        script_name = params.get('script', '')
        args = params.get('args', {})
        
        if not script_name:
            return ActionResult(success=False, error="No script name provided")
        
        module = self._custom_scripts.get(script_name)
        if not module:
            return ActionResult(success=False, error=f"Script not found: {script_name}")
        
        # Look for an 'execute' function in the module
        if not hasattr(module, 'execute'):
            return ActionResult(success=False, error=f"Script {script_name} has no 'execute' function")
        
        try:
            result = module.execute(**args)
            return ActionResult(success=True, message=f"Script executed", data=result)
        except Exception as e:
            return ActionResult(success=False, error=f"Script error: {e}")
    
    def _action_nested(self, params: dict, depth: int) -> ActionResult:
        """Execute nested action - make another LLM call."""
        prompt = params.get('prompt', '')
        context = params.get('context', {})
        
        if not prompt:
            return ActionResult(success=False, error="No prompt for nested action")
        
        try:
            response = self.llm_callback(prompt, context)
            
            # Execute the response actions
            if isinstance(response, str):
                results = self.execute_response(response, depth + 1)
            elif isinstance(response, dict):
                actions = response.get('actions', [])
                results = self.execute_actions(actions, depth + 1)
            else:
                return ActionResult(success=False, error="Invalid nested response format")
            
            # Check if any nested action failed
            failed = [r for r in results if not r.success]
            if failed:
                return ActionResult(
                    success=False,
                    error=f"Nested action failed: {failed[0].error}",
                    data=results
                )
            
            return ActionResult(success=True, message="Nested actions completed", data=results)
        except Exception as e:
            return ActionResult(success=False, error=f"Nested action error: {e}")


# Example custom action script template
CUSTOM_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""
Custom action script: {script_name}

Description: {description}

Input parameters:
  - param1 (str): Description of param1
  - param2 (int): Description of param2

Output:
  Returns a dict with the result of the action.
"""


def execute(param1: str = "", param2: int = 0, **kwargs) -> dict:
    """
    Main execution function called by the action system.
    
    Args:
        param1: First parameter
        param2: Second parameter
        **kwargs: Additional parameters
        
    Returns:
        dict: Result of the action
    """
    # Your action logic here
    result = {{
        "status": "success",
        "message": f"Executed with param1={{param1}}, param2={{param2}}"
    }}
    return result
'''


def create_custom_script_template(script_dir: str, script_name: str, description: str = "") -> str:
    """
    Create a template for a custom action script.
    
    Args:
        script_dir: Directory to create the script in
        script_name: Name of the script (without .py extension)
        description: Description of what the script does
        
    Returns:
        Path to the created script
    """
    script_path = Path(script_dir) / f"{script_name}.py"
    content = CUSTOM_SCRIPT_TEMPLATE.format(
        script_name=script_name,
        description=description or "Custom action script"
    )
    
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(content)
    
    return str(script_path)
