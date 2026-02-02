#!/usr/bin/env python3
"""
Example custom action script: timer

Description: Sets a timer that prints a message after a specified duration.
This is a demonstration of how custom action scripts work.

Input parameters:
  - duration (int): Timer duration in seconds
  - message (str): Message to return when timer completes

Output:
  Returns a dict with the timer result.

Usage in LLM response:
{
    "type": "execute_script",
    "params": {
        "script": "example_timer",
        "args": {
            "duration": 10,
            "message": "Timer completed!"
        }
    }
}
"""

import time


def execute(duration: int = 5, message: str = "Timer finished!", **kwargs) -> dict:
    """
    Main execution function called by the action system.
    
    Args:
        duration: Timer duration in seconds
        message: Message to return when timer completes
        **kwargs: Additional parameters (ignored)
        
    Returns:
        dict: Result of the timer action
    """
    # Note: In a real implementation, you might want to use
    # async or threading for longer timers to avoid blocking
    
    if duration > 0:
        time.sleep(duration)
    
    result = {
        "status": "success",
        "message": message,
        "duration": duration,
        "timestamp": time.time()
    }
    
    return result
