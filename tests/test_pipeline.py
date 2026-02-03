#!/usr/bin/env python3
"""
Full Pipeline Test Utility

This script tests the complete AI Agent pipeline from audio file input
through wake word detection, ASR, LLM, and action execution.

Usage:
    python tests/test_pipeline.py --config config.yaml --audio command_audio.wav
"""

import os
import sys
import json
import wave
import struct
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "python-clients"))

import yaml


def test_pipeline(
    config_path: str,
    audio_path: str,
    skip_wake_word: bool = False,
    skip_asr: bool = False,
    skip_llm: bool = False,
    skip_actions: bool = False,
    mock_transcript: str = None,
    verbose: bool = False
) -> dict:
    """
    Test the full AI agent pipeline.
    
    Args:
        config_path: Path to config.yaml
        audio_path: Path to audio file
        skip_wake_word: Skip wake word detection
        skip_asr: Skip ASR (use mock_transcript instead)
        skip_llm: Skip LLM (show what would be sent)
        skip_actions: Skip action execution
        mock_transcript: Use this transcript instead of ASR
        verbose: Print verbose output
        
    Returns:
        Dict with test results for each stage
    """
    print("=" * 70)
    print("Full Pipeline Test")
    print("=" * 70)
    
    # Load config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"\nConfiguration: {config_path}")
    print(f"Audio file: {audio_path}")
    
    results = {
        "stages": {},
        "success": True
    }
    
    # Stage 1: Wake Word Detection
    print(f"\n{'=' * 70}")
    print("Stage 1: Wake Word Detection")
    print("=" * 70)
    
    if skip_wake_word:
        print("  [SKIPPED]")
        results["stages"]["wake_word"] = {"skipped": True}
    else:
        try:
            import pvporcupine
            
            wake_config = config.get('wake_word', {})
            access_key = wake_config.get('access_key')
            
            if not access_key:
                print("  Error: No Porcupine access key in config")
                results["stages"]["wake_word"] = {"error": "No access key"}
            else:
                keywords = wake_config.get('keywords')
                keyword_paths = wake_config.get('keyword_paths')
                sensitivity = wake_config.get('sensitivity', 0.5)
                
                if keyword_paths:
                    sensitivities = [sensitivity] * len(keyword_paths)
                    porcupine = pvporcupine.create(
                        access_key=access_key,
                        keyword_paths=keyword_paths,
                        sensitivities=sensitivities
                    )
                elif keywords:
                    sensitivities = [sensitivity] * len(keywords)
                    porcupine = pvporcupine.create(
                        access_key=access_key,
                        keywords=keywords,
                        sensitivities=sensitivities
                    )
                else:
                    print("  Error: No keywords configured")
                    results["stages"]["wake_word"] = {"error": "No keywords"}
                    porcupine = None
                
                if porcupine:
                    # Read audio and detect
                    wav_file = wave.open(audio_path, mode="rb")
                    channels = wav_file.getnchannels()
                    num_frames = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    
                    samples = wav_file.readframes(num_frames)
                    wav_file.close()
                    
                    frames = struct.unpack('h' * num_frames * channels, samples)
                    mono_samples = list(frames[::channels])
                    
                    # Check sample rate
                    if sample_rate != porcupine.sample_rate:
                        print(f"  Warning: Audio sample rate ({sample_rate}) != expected ({porcupine.sample_rate})")
                    
                    # Process frames
                    frame_length = porcupine.frame_length
                    num_processed = len(mono_samples) // frame_length
                    detections = []
                    
                    for i in range(num_processed):
                        frame = mono_samples[i * frame_length:(i + 1) * frame_length]
                        result = porcupine.process(frame)
                        if result >= 0:
                            time_offset = (i * frame_length) / porcupine.sample_rate
                            detections.append({"time": time_offset, "index": result})
                    
                    porcupine.delete()
                    
                    if detections:
                        print(f"  ✓ Wake word detected at {detections[0]['time']:.2f}s")
                        results["stages"]["wake_word"] = {
                            "detected": True,
                            "detections": detections
                        }
                    else:
                        print("  ✗ No wake word detected")
                        results["stages"]["wake_word"] = {"detected": False}
                        results["success"] = False
                        
        except ImportError:
            print("  Error: pvporcupine not installed")
            results["stages"]["wake_word"] = {"error": "pvporcupine not installed"}
        except Exception as e:
            print(f"  Error: {e}")
            results["stages"]["wake_word"] = {"error": str(e)}
    
    # Stage 2: ASR (Speech Recognition)
    print(f"\n{'=' * 70}")
    print("Stage 2: ASR (Speech Recognition)")
    print("=" * 70)
    
    transcript = None
    
    if skip_asr:
        if mock_transcript:
            print(f"  [SKIPPED - Using mock transcript]")
            transcript = mock_transcript
            results["stages"]["asr"] = {"skipped": True, "mock_transcript": transcript}
        else:
            print("  [SKIPPED]")
            results["stages"]["asr"] = {"skipped": True}
    else:
        try:
            import riva.client
            
            asr_config = config.get('riva_asr', {})
            api_keys = asr_config.get('api_keys', [])
            
            if not api_keys:
                print("  Error: No ASR API keys in config")
                results["stages"]["asr"] = {"error": "No API keys"}
            else:
                server = asr_config.get('server', 'grpc.nvcf.nvidia.com:443')
                api_key = api_keys[0]
                
                metadata = []
                function_id = asr_config.get('function_id')
                if function_id:
                    metadata.append(['function-id', function_id])
                metadata.append(['authorization', f'Bearer {api_key}'])
                
                auth = riva.client.Auth(
                    ssl_root_cert=None,
                    use_ssl=asr_config.get('use_ssl', True),
                    uri=server,
                    metadata_args=metadata,
                )
                
                asr_service = riva.client.ASRService(auth)
                
                recognition_config = riva.client.RecognitionConfig(
                    language_code=asr_config.get('language_code', 'zh-CN'),
                    max_alternatives=1,
                    enable_automatic_punctuation=True,
                )
                
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()
                
                response = asr_service.offline_recognize(audio_data, recognition_config)
                
                if response.results:
                    transcript = ""
                    for result in response.results:
                        if result.alternatives:
                            transcript += result.alternatives[0].transcript
                    transcript = transcript.strip()
                    
                    print(f"  ✓ Transcript: {transcript}")
                    results["stages"]["asr"] = {"success": True, "transcript": transcript}
                else:
                    print("  ✗ No transcript returned")
                    results["stages"]["asr"] = {"success": False, "error": "No results"}
                    results["success"] = False
                    
        except ImportError as e:
            print(f"  Error: Could not import riva.client: {e}")
            results["stages"]["asr"] = {"error": f"Import error: {e}"}
        except Exception as e:
            print(f"  Error: {e}")
            results["stages"]["asr"] = {"error": str(e)}
    
    # Stage 3: LLM Processing
    print(f"\n{'=' * 70}")
    print("Stage 3: LLM Processing")
    print("=" * 70)
    
    llm_response = None
    
    if not transcript:
        print("  [SKIPPED - No transcript available]")
        results["stages"]["llm"] = {"skipped": True, "reason": "No transcript"}
    elif skip_llm:
        print(f"  [SKIPPED - Would send: '{transcript}']")
        results["stages"]["llm"] = {"skipped": True, "would_send": transcript}
    else:
        try:
            import openai
            
            llm_config = config.get('llm', {})
            api_keys = llm_config.get('api_keys', [])
            
            if not api_keys:
                print("  Error: No LLM API keys in config")
                results["stages"]["llm"] = {"error": "No API keys"}
            else:
                client = openai.OpenAI(
                    api_key=api_keys[0],
                    base_url=llm_config.get('api_base', 'https://api.openai.com/v1')
                )
                
                # Load agent prompt
                prompt_file = config.get('agent', {}).get('prompt_file', 'Agent.md')
                prompt_path = Path(__file__).parent.parent / prompt_file
                agent_prompt = ""
                if prompt_path.exists():
                    agent_prompt = prompt_path.read_text(encoding='utf-8')
                    agent_prompt = agent_prompt.format(
                        user_id=1,
                        timestamp=datetime.now().isoformat(),
                        preset_audio_files="None",
                        custom_scripts="system_info, example_timer"
                    )
                
                response = client.chat.completions.create(
                    model=llm_config.get('model', 'gpt-4'),
                    messages=[
                        {"role": "system", "content": agent_prompt},
                        {"role": "user", "content": transcript}
                    ],
                    max_tokens=llm_config.get('max_tokens', 2048),
                    temperature=llm_config.get('temperature', 0.7),
                )
                
                llm_response = response.choices[0].message.content
                
                print(f"  ✓ Response received ({len(llm_response)} chars)")
                if verbose:
                    print(f"  Response: {llm_response[:200]}...")
                
                # Try to parse as JSON
                try:
                    json_str = llm_response
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()
                    
                    parsed = json.loads(json_str)
                    print(f"  ✓ Valid JSON with {len(parsed.get('actions', []))} action(s)")
                    results["stages"]["llm"] = {
                        "success": True,
                        "response": llm_response,
                        "parsed": parsed
                    }
                except json.JSONDecodeError as e:
                    print(f"  ⚠ Response is not valid JSON: {e}")
                    results["stages"]["llm"] = {
                        "success": True,
                        "response": llm_response,
                        "json_error": str(e)
                    }
                    
        except ImportError:
            print("  Error: openai package not installed")
            results["stages"]["llm"] = {"error": "openai not installed"}
        except Exception as e:
            print(f"  Error: {e}")
            results["stages"]["llm"] = {"error": str(e)}
    
    # Stage 4: Action Execution
    print(f"\n{'=' * 70}")
    print("Stage 4: Action Execution")
    print("=" * 70)
    
    if not llm_response:
        print("  [SKIPPED - No LLM response available]")
        results["stages"]["actions"] = {"skipped": True, "reason": "No LLM response"}
    elif skip_actions:
        print("  [SKIPPED - Would execute actions from LLM response]")
        results["stages"]["actions"] = {"skipped": True}
    else:
        try:
            from actions import ActionExecutor
            
            # Create mock callbacks for testing
            class MockCallback:
                def __init__(self):
                    self.calls = []
                def __call__(self, *args):
                    self.calls.append(args)
                    print(f"    [Callback] Args: {args}")
            
            tts_cb = MockCallback()
            audio_cb = MockCallback()
            llm_cb = MockCallback()
            
            executor = ActionExecutor(
                tts_callback=tts_cb,
                play_audio_callback=audio_cb,
                llm_callback=llm_cb,
            )
            
            action_results = executor.execute_response(llm_response)
            
            success_count = sum(1 for r in action_results if r.success)
            fail_count = len(action_results) - success_count
            
            print(f"  ✓ Executed {len(action_results)} action(s)")
            print(f"    Success: {success_count}, Failed: {fail_count}")
            
            for i, result in enumerate(action_results):
                status = "✓" if result.success else "✗"
                print(f"    {status} Action {i+1}: {result.message or result.error}")
            
            results["stages"]["actions"] = {
                "success": fail_count == 0,
                "total": len(action_results),
                "success_count": success_count,
                "fail_count": fail_count,
                "callbacks": {
                    "tts": len(tts_cb.calls),
                    "play_audio": len(audio_cb.calls)
                }
            }
            
            executor.stop()
            
        except ImportError as e:
            print(f"  Error: Could not import actions module: {e}")
            results["stages"]["actions"] = {"error": f"Import error: {e}"}
        except Exception as e:
            print(f"  Error: {e}")
            results["stages"]["actions"] = {"error": str(e)}
    
    # Summary
    print(f"\n{'=' * 70}")
    print("Pipeline Summary")
    print("=" * 70)
    
    for stage_name, stage_result in results["stages"].items():
        if stage_result.get("skipped"):
            status = "SKIPPED"
        elif stage_result.get("error"):
            status = f"ERROR: {stage_result['error'][:50]}"
        elif stage_result.get("success", True):
            status = "SUCCESS"
        else:
            status = "FAILED"
        print(f"  {stage_name}: {status}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test the full AI Agent pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test full pipeline
  python tests/test_pipeline.py --config config.yaml --audio command.wav
  
  # Test with mock transcript (skip ASR)
  python tests/test_pipeline.py --config config.yaml --audio command.wav \\
      --skip-asr --mock-transcript "播放音乐"
  
  # Test wake word detection only
  python tests/test_pipeline.py --config config.yaml --audio wake_test.wav \\
      --skip-asr --skip-llm --skip-actions
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to config.yaml"
    )
    parser.add_argument(
        "--audio", "-a",
        required=True,
        help="Path to audio file"
    )
    parser.add_argument(
        "--skip-wake-word",
        action="store_true",
        help="Skip wake word detection"
    )
    parser.add_argument(
        "--skip-asr",
        action="store_true",
        help="Skip ASR (use --mock-transcript instead)"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM processing"
    )
    parser.add_argument(
        "--skip-actions",
        action="store_true",
        help="Skip action execution"
    )
    parser.add_argument(
        "--mock-transcript",
        help="Use this transcript instead of ASR"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    
    results = test_pipeline(
        config_path=args.config,
        audio_path=args.audio,
        skip_wake_word=args.skip_wake_word,
        skip_asr=args.skip_asr,
        skip_llm=args.skip_llm,
        skip_actions=args.skip_actions,
        mock_transcript=args.mock_transcript,
        verbose=args.verbose
    )
    
    if results["success"]:
        print(f"\n✓ Pipeline test completed successfully")
        sys.exit(0)
    else:
        print(f"\n✗ Pipeline test had failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
