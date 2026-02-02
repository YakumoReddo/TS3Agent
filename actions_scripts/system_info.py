#!/usr/bin/env python3
"""
Example custom action script: system_info

Description: Returns system information (time, date, etc.)
Useful for answering questions like "What time is it?" or "What's today's date?"

Input parameters:
  - info_type (str): Type of information to return ('time', 'date', 'datetime', 'all')

Output:
  Returns a dict with the requested system information.

Usage in LLM response:
{
    "type": "execute_script",
    "params": {
        "script": "system_info",
        "args": {
            "info_type": "datetime"
        }
    }
}
"""

from datetime import datetime
import platform


def execute(info_type: str = "all", **kwargs) -> dict:
    """
    Main execution function called by the action system.
    
    Args:
        info_type: Type of info to return ('time', 'date', 'datetime', 'all')
        **kwargs: Additional parameters (ignored)
        
    Returns:
        dict: System information
    """
    now = datetime.now()
    
    info = {
        "status": "success",
    }
    
    if info_type in ('time', 'all'):
        info["time"] = now.strftime("%H:%M:%S")
        info["time_12h"] = now.strftime("%I:%M %p")
    
    if info_type in ('date', 'all'):
        info["date"] = now.strftime("%Y-%m-%d")
        info["date_readable"] = now.strftime("%B %d, %Y")
        info["weekday"] = now.strftime("%A")
    
    if info_type in ('datetime', 'all'):
        info["datetime"] = now.isoformat()
    
    if info_type == 'all':
        info["platform"] = platform.system()
        info["hostname"] = platform.node()
    
    return info
