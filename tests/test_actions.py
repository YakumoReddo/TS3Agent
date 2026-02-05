#!/usr/bin/env python3
"""
Action System Test Utility

This script tests the action execution system by processing
LLM-style JSON action responses.

Usage:
    python tests/test_actions.py --action speak --params '{"text": "Hello"}'
    python tests/test_actions.py --json '{"actions": [{"type": "speak", "params": {"text": "Hi"}}]}'
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


class MockTTSCallback:
    """Mock TTS callback that records calls."""
    
    def __init__(self):
        self.calls = []
    
    def __call__(self, text: str):
        self.calls.append({"type": "tts", "text": text})
        print(f"    [TTS] Would speak: '{text}'")


class MockPlayAudioCallback:
    """Mock play audio callback that records calls."""
    
    def __init__(self):
        self.calls = []
    
    def __call__(self, file_path: str):
        self.calls.append({"type": "play_audio", "file": file_path})
        print(f"    [AUDIO] Would play: '{file_path}'")


class MockLLMCallback:
    """Mock LLM callback that returns a predefined response."""
    
    def __init__(self, response: str = None):
        self.response = response or json.dumps({
            "actions": [{"type": "speak", "params": {"text": "Nested response"}}]
        })
        self.calls = []
    
    def __call__(self, prompt: str, context: dict):
        self.calls.append({"prompt": prompt, "context": context})
        print(f"    [LLM] Nested call with prompt: '{prompt[:50]}...'")
        return self.response


def test_single_action(action_type: str, params: dict, verbose: bool = False) -> dict:
    """
    Test a single action.
    
    Args:
        action_type: Action type (speak, play_audio, delay, etc.)
        params: Action parameters
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("Action System Test - Single Action")
    print("=" * 60)
    
    print(f"\nAction: {action_type}")
    print(f"Params: {json.dumps(params, ensure_ascii=False)}")
    
    # Import ActionExecutor
    try:
        from actions import ActionExecutor
    except ImportError as e:
        print(f"\nError importing actions module: {e}")
        return {"success": False, "error": f"Import error: {e}"}
    
    # Create mock callbacks
    tts_callback = MockTTSCallback()
    play_audio_callback = MockPlayAudioCallback()
    llm_callback = MockLLMCallback()
    
    # Create executor
    executor = ActionExecutor(
        tts_callback=tts_callback,
        play_audio_callback=play_audio_callback,
        llm_callback=llm_callback,
        custom_actions_dir="actions_scripts",
        max_nesting_depth=3,
        action_timeout=30.0,
        nested_action_timeout=60.0,
    )
    
    # Execute action
    print(f"\nExecuting action...")
    action = {"type": action_type, "params": params}
    
    import time
    start_time = time.time()
    results = executor.execute_actions([action])
    elapsed_time = time.time() - start_time
    
    # Report results
    print(f"\n{'=' * 60}")
    print("Results")
    print("=" * 60)
    
    test_results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "action_results": [],
        "callbacks": {
            "tts": tts_callback.calls,
            "play_audio": play_audio_callback.calls,
            "llm": llm_callback.calls
        }
    }
    
    for i, result in enumerate(results):
        print(f"\nResult {i + 1}:")
        print(f"  Success: {result.success}")
        print(f"  Message: {result.message}")
        if result.error:
            print(f"  Error: {result.error}")
            test_results["success"] = False
        if result.data:
            print(f"  Data: {result.data}")
        
        test_results["action_results"].append({
            "success": result.success,
            "message": result.message,
            "error": result.error,
            "data": result.data
        })
    
    # Cleanup
    executor.stop()
    
    return test_results


def test_json_response(json_str: str, verbose: bool = False) -> dict:
    """
    Test a full JSON action response.
    
    Args:
        json_str: JSON string containing actions
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("Action System Test - JSON Response")
    print("=" * 60)
    
    # Parse JSON
    try:
        parsed = json.loads(json_str)
        print(f"\nParsed JSON successfully")
        if verbose:
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        print(f"\nError parsing JSON: {e}")
        return {"success": False, "error": f"JSON parse error: {e}"}
    
    # Import ActionExecutor
    try:
        from actions import ActionExecutor
    except ImportError as e:
        print(f"\nError importing actions module: {e}")
        return {"success": False, "error": f"Import error: {e}"}
    
    # Create mock callbacks
    tts_callback = MockTTSCallback()
    play_audio_callback = MockPlayAudioCallback()
    llm_callback = MockLLMCallback()
    
    # Create executor
    executor = ActionExecutor(
        tts_callback=tts_callback,
        play_audio_callback=play_audio_callback,
        llm_callback=llm_callback,
        custom_actions_dir="actions_scripts",
        max_nesting_depth=3,
        action_timeout=30.0,
        nested_action_timeout=60.0,
    )
    
    # Execute
    print(f"\nExecuting response...")
    import time
    start_time = time.time()
    results = executor.execute_response(json_str)
    elapsed_time = time.time() - start_time
    
    # Report results
    print(f"\n{'=' * 60}")
    print("Results")
    print("=" * 60)
    
    test_results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "action_results": [],
        "callbacks": {
            "tts": tts_callback.calls,
            "play_audio": play_audio_callback.calls,
            "llm": llm_callback.calls
        }
    }
    
    for i, result in enumerate(results):
        print(f"\nResult {i + 1}:")
        print(f"  Success: {result.success}")
        print(f"  Message: {result.message}")
        if result.error:
            print(f"  Error: {result.error}")
            test_results["success"] = False
        
        test_results["action_results"].append({
            "success": result.success,
            "message": result.message,
            "error": result.error
        })
    
    # Print callback summary
    print(f"\n{'=' * 60}")
    print("Callback Summary")
    print("=" * 60)
    print(f"  TTS calls: {len(tts_callback.calls)}")
    for call in tts_callback.calls:
        print(f"    - '{call['text']}'")
    print(f"  Play audio calls: {len(play_audio_callback.calls)}")
    for call in play_audio_callback.calls:
        print(f"    - '{call['file']}'")
    print(f"  Nested LLM calls: {len(llm_callback.calls)}")
    
    # Cleanup
    executor.stop()
    
    return test_results


def test_schedule_action(delay_seconds: float, action_text: str, wait: bool = False) -> dict:
    """
    Test the schedule action.
    
    Args:
        delay_seconds: Delay before executing
        action_text: Text to speak after delay
        wait: Wait for the scheduled action to execute
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("Action System Test - Schedule Action")
    print("=" * 60)
    
    print(f"\nSchedule: Speak '{action_text}' after {delay_seconds} seconds")
    
    # Import ActionExecutor
    try:
        from actions import ActionExecutor
    except ImportError as e:
        print(f"\nError importing actions module: {e}")
        return {"success": False, "error": f"Import error: {e}"}
    
    # Create mock callbacks
    tts_callback = MockTTSCallback()
    play_audio_callback = MockPlayAudioCallback()
    llm_callback = MockLLMCallback()
    
    # Create executor
    executor = ActionExecutor(
        tts_callback=tts_callback,
        play_audio_callback=play_audio_callback,
        llm_callback=llm_callback,
        custom_actions_dir="actions_scripts",
        max_nesting_depth=3,
        action_timeout=30.0,
        nested_action_timeout=60.0,
    )
    
    # Create schedule action
    json_str = json.dumps({
        "actions": [{
            "type": "schedule",
            "params": {
                "delay_seconds": delay_seconds,
                "actions": [{
                    "type": "speak",
                    "params": {"text": action_text}
                }]
            }
        }]
    })
    
    # Execute
    print(f"\nScheduling action...")
    import time
    results = executor.execute_response(json_str)
    
    for result in results:
        print(f"  Schedule result: {result.success} - {result.message}")
    
    test_results = {
        "success": all(r.success for r in results),
        "scheduled": True
    }
    
    if wait and delay_seconds < 30:
        print(f"\nWaiting {delay_seconds + 1} seconds for scheduled action...")
        time.sleep(delay_seconds + 1)
        
        print(f"\nScheduled action callbacks:")
        print(f"  TTS calls: {len(tts_callback.calls)}")
        for call in tts_callback.calls:
            print(f"    - '{call['text']}'")
        
        test_results["executed"] = len(tts_callback.calls) > 0
        test_results["callbacks"] = {"tts": tts_callback.calls}
    
    # Cleanup
    executor.stop()
    
    return test_results


def main():
    parser = argparse.ArgumentParser(
        description="Test the action execution system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test speak action
  python tests/test_actions.py --action speak --params '{"text": "Hello, world"}'
  
  # Test delay action
  python tests/test_actions.py --action delay --params '{"seconds": 2}'
  
  # Test full JSON response
  python tests/test_actions.py --json '{"actions": [{"type": "speak", "params": {"text": "Hi"}}]}'
  
  # Test schedule action (with wait)
  python tests/test_actions.py --schedule --delay 3 --text "Reminder!" --wait
  
  # Test execute_script action
  python tests/test_actions.py --action execute_script --params '{"script": "system_info"}'
"""
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--action",
        help="Single action type to test (speak, play_audio, delay, execute_script)"
    )
    group.add_argument(
        "--json", "-j",
        help="Full JSON response to test"
    )
    group.add_argument(
        "--schedule",
        action="store_true",
        help="Test schedule action"
    )
    
    parser.add_argument(
        "--params", "-p",
        default="{}",
        help="Action parameters as JSON (for --action)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds (for --schedule)"
    )
    parser.add_argument(
        "--text",
        default="Scheduled message",
        help="Text to speak (for --schedule)"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for scheduled action to execute"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    
    # Run appropriate test
    if args.action:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error parsing params JSON: {e}")
            sys.exit(1)
        
        results = test_single_action(args.action, params, args.verbose)
    elif args.json:
        results = test_json_response(args.json, args.verbose)
    elif args.schedule:
        results = test_schedule_action(args.delay, args.text, args.wait)
    
    if results["success"]:
        print(f"\n✓ Action test completed successfully")
        sys.exit(0)
    else:
        print(f"\n✗ Action test failed: {results.get('error', 'Action execution failed')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
