#!/usr/bin/env python3
"""
LLM (Large Language Model) Test Utility

This script tests the LLM component by sending a text prompt and
verifying the response format.

Usage:
    python tests/test_llm.py --config config.yaml --text "播放音乐"
    python tests/test_llm.py --api-base https://api.openai.com/v1 --api-key YOUR_KEY --text "Hello"
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


def load_agent_prompt(prompt_file: str = "Agent.md") -> str:
    """Load agent prompt from file."""
    prompt_path = Path(__file__).parent.parent / prompt_file
    if prompt_path.exists():
        return prompt_path.read_text(encoding='utf-8')
    
    # Try alternate paths
    for alt_path in [Path(prompt_file), Path(__file__).parent.parent / "Agent_zh.md"]:
        if alt_path.exists():
            return alt_path.read_text(encoding='utf-8')
    
    print(f"Warning: Agent prompt file not found: {prompt_file}")
    return ""


def test_llm(
    api_base: str,
    api_key: str,
    model: str,
    text: str,
    agent_prompt: str = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    user_id: int = 1,
    verbose: bool = False
) -> dict:
    """
    Test LLM with a text prompt.
    
    Args:
        api_base: API base URL
        api_key: API key
        model: Model name
        text: User input text
        agent_prompt: System prompt (optional)
        max_tokens: Max tokens in response
        temperature: Sampling temperature
        user_id: Simulated user ID
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("LLM (Language Model) Test")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  - API Base: {api_base}")
    print(f"  - Model: {model}")
    print(f"  - Max Tokens: {max_tokens}")
    print(f"  - Temperature: {temperature}")
    print(f"  - User ID: {user_id}")
    
    print(f"\nInput Text: {text}")
    
    # Import openai
    try:
        import openai
    except ImportError:
        print("\nError: openai package not installed. Install with: pip install openai")
        return {"success": False, "error": "openai not installed"}
    
    # Prepare system prompt
    if agent_prompt:
        system_prompt = agent_prompt.format(
            user_id=user_id,
            timestamp=datetime.now().isoformat(),
            preset_audio_files="test_audio, notification",
            custom_scripts="system_info, example_timer"
        )
    else:
        system_prompt = """You are an AI assistant. Respond in JSON format with actions.
Format:
{
    "actions": [
        {"type": "speak", "params": {"text": "your response"}}
    ]
}
"""
    
    if verbose:
        print(f"\nSystem Prompt (first 500 chars):")
        print(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
    
    # Create client
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )
    except Exception as e:
        print(f"\nError creating OpenAI client: {e}")
        return {"success": False, "error": f"Client error: {e}"}
    
    # Send request
    print(f"\nSending request to LLM...")
    import time
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        elapsed_time = time.time() - start_time
        print(f"  Response received in {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"\nLLM Error: {e}")
        return {"success": False, "error": f"LLM error: {e}"}
    
    # Extract response
    llm_response = response.choices[0].message.content
    
    print(f"\n{'=' * 60}")
    print("Raw Response")
    print("=" * 60)
    print(llm_response)
    
    # Parse and validate JSON
    print(f"\n{'=' * 60}")
    print("Response Validation")
    print("=" * 60)
    
    results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "raw_response": llm_response,
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
    }
    
    # Try to parse as JSON
    try:
        # Handle markdown code blocks
        json_str = llm_response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(json_str)
        results["parsed_json"] = parsed
        print(f"✓ Response is valid JSON")
        
        # Check for required fields
        if "actions" in parsed:
            print(f"✓ 'actions' field present")
            actions = parsed["actions"]
            print(f"  Number of actions: {len(actions)}")
            
            for i, action in enumerate(actions):
                action_type = action.get("type", "unknown")
                params = action.get("params", {})
                print(f"\n  Action {i + 1}:")
                print(f"    Type: {action_type}")
                print(f"    Params: {json.dumps(params, ensure_ascii=False)[:100]}...")
                
                # Validate action type
                valid_types = ["speak", "play_audio", "delay", "schedule", "execute_script", "nested_action"]
                if action_type in valid_types:
                    print(f"    ✓ Valid action type")
                else:
                    print(f"    ⚠ Unknown action type: {action_type}")
            
            results["actions"] = actions
        else:
            print(f"⚠ 'actions' field not found in response")
            results["success"] = False
            results["error"] = "Missing 'actions' field"
        
        if "thought" in parsed:
            print(f"\nThought: {parsed['thought'][:200]}...")
            results["thought"] = parsed["thought"]
            
    except json.JSONDecodeError as e:
        print(f"✗ Response is not valid JSON: {e}")
        results["success"] = False
        results["error"] = f"Invalid JSON: {e}"
    
    # Print usage stats
    print(f"\n{'=' * 60}")
    print("Usage Statistics")
    print("=" * 60)
    print(f"  Model: {response.model}")
    print(f"  Prompt tokens: {response.usage.prompt_tokens}")
    print(f"  Completion tokens: {response.usage.completion_tokens}")
    print(f"  Total tokens: {response.usage.total_tokens}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test LLM with a text prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with config file
  python tests/test_llm.py --config config.yaml --text "播放音乐"
  
  # Test with direct parameters
  python tests/test_llm.py --api-base https://api.openai.com/v1 \\
      --api-key YOUR_KEY --model gpt-4 --text "Hello"
  
  # Test with verbose output
  python tests/test_llm.py --config config.yaml --text "五分钟后提醒我" --verbose
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file"
    )
    parser.add_argument(
        "--text", "-t",
        required=True,
        help="Text prompt to send to LLM (simulates transcribed speech)"
    )
    parser.add_argument(
        "--api-base",
        help="API base URL"
    )
    parser.add_argument(
        "--api-key",
        help="API key"
    )
    parser.add_argument(
        "--model",
        help="Model name"
    )
    parser.add_argument(
        "--prompt-file",
        default="Agent.md",
        help="Path to agent prompt file (default: Agent.md)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max tokens in response"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="Simulated user ID (default: 1)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    
    # Load config
    api_base = args.api_base
    api_key = args.api_key
    model = args.model
    max_tokens = args.max_tokens or 2048
    temperature = args.temperature or 0.7
    prompt_file = args.prompt_file
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            llm_config = config.get('llm', {})
            
            if not api_base:
                api_base = llm_config.get('api_base', 'https://api.openai.com/v1')
            if not api_key:
                api_keys = llm_config.get('api_keys', [])
                if api_keys:
                    api_key = api_keys[0]
            if not model:
                model = llm_config.get('model', 'gpt-4')
            if args.max_tokens is None:
                max_tokens = llm_config.get('max_tokens', 2048)
            if args.temperature is None:
                temperature = llm_config.get('temperature', 0.7)
            
            # Get prompt file from config
            agent_config = config.get('agent', {})
            if 'prompt_file' in agent_config:
                prompt_file = agent_config.get('prompt_file', 'Agent.md')
            
            print(f"Loaded configuration from: {args.config}")
        else:
            print(f"Warning: Config file not found: {args.config}")
    
    if not api_base:
        api_base = "https://api.openai.com/v1"
        print(f"Using default API base: {api_base}")
    
    if not api_key:
        print("Error: API key not provided.")
        print("Use --api-key or specify in config file.")
        sys.exit(1)
    
    if not model:
        model = "gpt-4"
        print(f"Using default model: {model}")
    
    # Load agent prompt
    agent_prompt = load_agent_prompt(prompt_file)
    
    # Run test
    results = test_llm(
        api_base=api_base,
        api_key=api_key,
        model=model,
        text=args.text,
        agent_prompt=agent_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        user_id=args.user_id,
        verbose=args.verbose
    )
    
    if results["success"]:
        print(f"\n✓ LLM test completed successfully")
        sys.exit(0)
    else:
        print(f"\n✗ LLM test failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
