#!/usr/bin/env python3
"""
TTS (Text-to-Speech) Test Utility

This script tests the Riva TTS component by synthesizing speech from text
and optionally saving the output to a WAV file.

Usage:
    python tests/test_tts.py --config config.yaml --text "你好，世界"
    python tests/test_tts.py --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY --text "Hello"
"""

import os
import sys
import wave
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "python-clients"))

import yaml

# Constants
DEFAULT_ZERO_SHOT_QUALITY = 20


def test_tts(
    server: str,
    api_key: str,
    text: str,
    language_code: str = "zh-CN",
    voice_name: str = None,
    sample_rate_hz: int = 48000,
    use_ssl: bool = True,
    function_id: str = None,
    zero_shot_audio_prompt_file: str = None,
    zero_shot_quality: int = 20,
    output_file: str = None,
    verbose: bool = False
) -> dict:
    """
    Test TTS synthesis with text input.
    
    Args:
        server: Riva server address
        api_key: API key for authentication
        text: Text to synthesize
        language_code: Language code
        voice_name: Voice name (optional)
        sample_rate_hz: Output sample rate
        use_ssl: Use SSL connection
        function_id: NVCF function ID (optional)
        zero_shot_audio_prompt_file: Path to zero-shot audio prompt
        zero_shot_quality: Zero-shot quality setting
        output_file: Path to save output WAV (optional)
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("TTS (Text-to-Speech) Test")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  - Server: {server}")
    print(f"  - Language: {language_code}")
    print(f"  - Voice: {voice_name or 'Default'}")
    print(f"  - Sample Rate: {sample_rate_hz} Hz")
    print(f"  - SSL: {use_ssl}")
    print(f"  - Function ID: {function_id or 'None'}")
    if zero_shot_audio_prompt_file:
        print(f"  - Zero-shot prompt: {zero_shot_audio_prompt_file}")
        print(f"  - Zero-shot quality: {zero_shot_quality}")
    
    print(f"\nInput Text: {text}")
    
    # Import riva client
    try:
        import riva.client
        from riva.client.proto.riva_audio_pb2 import AudioEncoding
    except ImportError as e:
        print(f"\nError: Could not import riva.client: {e}")
        print("Make sure riva-client is installed and python-clients is in the path.")
        return {"success": False, "error": f"Import error: {e}"}
    
    # Create metadata
    metadata = []
    if function_id:
        metadata.append(['function-id', function_id])
    metadata.append(['authorization', f'Bearer {api_key}'])
    
    if verbose:
        print(f"\nMetadata: {metadata}")
    
    # Create auth and service
    try:
        print(f"\nConnecting to Riva server...")
        auth = riva.client.Auth(
            ssl_root_cert=None,
            use_ssl=use_ssl,
            uri=server,
            metadata_args=metadata,
        )
        tts_service = riva.client.SpeechSynthesisService(auth)
        print(f"  Connected successfully")
    except Exception as e:
        print(f"\nError connecting to server: {e}")
        return {"success": False, "error": f"Connection error: {e}"}
    
    # Prepare zero-shot prompt if specified
    zero_shot_path = None
    if zero_shot_audio_prompt_file:
        zero_shot_path = Path(zero_shot_audio_prompt_file)
        if not zero_shot_path.exists():
            print(f"Warning: Zero-shot audio prompt file not found: {zero_shot_audio_prompt_file}")
            zero_shot_path = None
    
    # Synthesize
    print(f"\nSynthesizing speech...")
    import time
    start_time = time.time()
    
    try:
        response = tts_service.synthesize(
            text=text,
            voice_name=voice_name,
            language_code=language_code,
            encoding=AudioEncoding.LINEAR_PCM,
            sample_rate_hz=sample_rate_hz,
            zero_shot_audio_prompt_file=zero_shot_path,
            zero_shot_quality=zero_shot_quality,
        )
        elapsed_time = time.time() - start_time
        print(f"  Response received in {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"\nTTS Error: {e}")
        return {"success": False, "error": f"TTS error: {e}"}
    
    # Process results
    audio_data = response.audio
    
    print(f"\n{'=' * 60}")
    print("Results")
    print("=" * 60)
    
    # Calculate duration
    # PCM audio: sample_rate * channels * bytes_per_sample
    # Assuming mono (1 channel) and 16-bit (2 bytes)
    bytes_per_sample = 2
    channels = 1
    duration = len(audio_data) / (sample_rate_hz * channels * bytes_per_sample)
    
    print(f"  Audio size: {len(audio_data)} bytes ({len(audio_data) / 1024:.1f} KB)")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Sample rate: {sample_rate_hz} Hz")
    print(f"  Synthesis speed: {duration / elapsed_time:.1f}x real-time")
    
    results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "audio_size": len(audio_data),
        "duration": duration,
        "sample_rate": sample_rate_hz
    }
    
    # Save to file if requested
    if output_file:
        print(f"\nSaving to: {output_file}")
        try:
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(bytes_per_sample)
                wav_file.setframerate(sample_rate_hz)
                wav_file.writeframes(audio_data)
            print(f"  ✓ Saved successfully")
            results["output_file"] = output_file
        except Exception as e:
            print(f"  ✗ Failed to save: {e}")
    else:
        print(f"\nTip: Use --output to save the audio to a WAV file")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test Riva TTS with text input",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with config file
  python tests/test_tts.py --config config.yaml --text "你好，世界"
  
  # Test and save output
  python tests/test_tts.py --config config.yaml --text "Hello, world" --output test_output.wav
  
  # Test with direct parameters
  python tests/test_tts.py --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY \\
      --language en-US --text "Hello" --output output.wav
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file"
    )
    parser.add_argument(
        "--text", "-t",
        required=True,
        help="Text to synthesize"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output WAV file path (optional)"
    )
    parser.add_argument(
        "--server",
        help="Riva server address"
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication"
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language code (e.g., zh-CN, en-US)"
    )
    parser.add_argument(
        "--voice",
        help="Voice name"
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Output sample rate in Hz"
    )
    parser.add_argument(
        "--function-id",
        help="NVCF function ID"
    )
    parser.add_argument(
        "--zero-shot-audio",
        help="Path to zero-shot audio prompt file"
    )
    parser.add_argument(
        "--zero-shot-quality",
        type=int,
        default=DEFAULT_ZERO_SHOT_QUALITY,
        help=f"Zero-shot quality (1-40, default: {DEFAULT_ZERO_SHOT_QUALITY})"
    )
    parser.add_argument(
        "--no-ssl",
        action="store_true",
        help="Disable SSL"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    
    # Load config
    server = args.server
    api_key = args.api_key
    language_code = args.language or "zh-CN"
    voice_name = args.voice
    sample_rate_hz = args.sample_rate or 48000
    use_ssl = not args.no_ssl
    function_id = args.function_id
    zero_shot_audio = args.zero_shot_audio
    zero_shot_quality = args.zero_shot_quality
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            tts_config = config.get('riva_tts', {})
            
            if not server:
                server = tts_config.get('server', 'grpc.nvcf.nvidia.com:443')
            if not api_key:
                api_keys = tts_config.get('api_keys', [])
                if api_keys:
                    api_key = api_keys[0]
            if args.language is None:
                language_code = tts_config.get('language_code', 'zh-CN')
            if not voice_name:
                voice_name = tts_config.get('voice_name')
            if args.sample_rate is None:
                sample_rate_hz = tts_config.get('sample_rate_hz', 48000)
            if not function_id:
                function_id = tts_config.get('function_id')
            if 'use_ssl' in tts_config and not args.no_ssl:
                use_ssl = tts_config.get('use_ssl', True)
            if not zero_shot_audio:
                zero_shot_audio = tts_config.get('zero_shot_audio_prompt_file')
            if args.zero_shot_quality == DEFAULT_ZERO_SHOT_QUALITY:
                zero_shot_quality = tts_config.get('zero_shot_quality', DEFAULT_ZERO_SHOT_QUALITY)
            
            print(f"Loaded configuration from: {args.config}")
        else:
            print(f"Warning: Config file not found: {args.config}")
    
    if not server:
        print("Error: Server address not provided.")
        print("Use --server or specify in config file.")
        sys.exit(1)
    
    if not api_key:
        print("Error: API key not provided.")
        print("Use --api-key or specify in config file.")
        sys.exit(1)
    
    # Run test
    results = test_tts(
        server=server,
        api_key=api_key,
        text=args.text,
        language_code=language_code,
        voice_name=voice_name,
        sample_rate_hz=sample_rate_hz,
        use_ssl=use_ssl,
        function_id=function_id,
        zero_shot_audio_prompt_file=zero_shot_audio,
        zero_shot_quality=zero_shot_quality,
        output_file=args.output,
        verbose=args.verbose
    )
    
    if results["success"]:
        print(f"\n✓ TTS test completed successfully")
        sys.exit(0)
    else:
        print(f"\n✗ TTS test failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
