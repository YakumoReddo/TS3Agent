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


def test_doubao_tts(
    appid: str,
    access_token: str,
    cluster: str,
    voice_type: str,
    text: str,
    api_url: str = "https://openspeech.bytedance.com/api/v1/tts",
    encoding: str = "mp3",
    speed_ratio: float = 1.0,
    volume_ratio: float = 1.0,
    pitch_ratio: float = 1.0,
    output_file: str = None,
    verbose: bool = False
) -> dict:
    """
    Test Doubao (ByteDance) TTS synthesis with text input.
    
    Args:
        appid: Doubao application ID
        access_token: API access token
        cluster: Doubao cluster
        voice_type: Voice type ID
        text: Text to synthesize
        api_url: API endpoint URL
        encoding: Output format (mp3, wav, pcm)
        speed_ratio: Speed ratio (0.5-2.0)
        volume_ratio: Volume ratio (0.5-2.0)
        pitch_ratio: Pitch ratio (0.5-2.0)
        output_file: Path to save output file (optional)
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    import base64
    import uuid
    import requests
    
    print("=" * 60)
    print("Doubao TTS (Text-to-Speech) Test")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  - API URL: {api_url}")
    print(f"  - App ID: {appid}")
    print(f"  - Cluster: {cluster}")
    print(f"  - Voice Type: {voice_type}")
    print(f"  - Encoding: {encoding}")
    print(f"  - Speed Ratio: {speed_ratio}")
    print(f"  - Volume Ratio: {volume_ratio}")
    print(f"  - Pitch Ratio: {pitch_ratio}")
    
    print(f"\nInput Text: {text}")
    
    # Build request
    # Note: Authorization header uses "Bearer;" format per Doubao API specification
    header = {"Authorization": f"Bearer;{access_token}"}
    
    request_json = {
        "app": {
            "appid": appid,
            # Note: token field is a fixed string per Doubao API docs, not the actual access token
            "token": "access_token",
            "cluster": cluster
        },
        "user": {
            "uid": "test_user"
        },
        "audio": {
            "voice_type": voice_type,
            "encoding": encoding,
            "speed_ratio": speed_ratio,
            "volume_ratio": volume_ratio,
            "pitch_ratio": pitch_ratio,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "with_frontend": 1,
            "frontend_type": "unitTson"
        }
    }
    
    if verbose:
        print(f"\nRequest JSON: {request_json}")
    
    # Make request
    print(f"\nSending request to Doubao TTS...")
    import time
    start_time = time.time()
    
    try:
        resp = requests.post(api_url, json=request_json, headers=header, timeout=30)
        elapsed_time = time.time() - start_time
        print(f"  Response received in {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"\nDoubao TTS Error: {e}")
        return {"success": False, "error": f"Request error: {e}"}
    
    # Process response
    resp_json = resp.json()
    
    if verbose:
        print(f"\nResponse: {resp_json}")
    
    if "data" not in resp_json:
        error_msg = resp_json.get('message', 'No data in response')
        print(f"\nDoubao TTS Error: {error_msg}")
        return {"success": False, "error": error_msg}
    
    # Decode audio data
    audio_data = base64.b64decode(resp_json["data"])
    
    print(f"\n{'=' * 60}")
    print("Results")
    print("=" * 60)
    print(f"  Audio size: {len(audio_data)} bytes ({len(audio_data) / 1024:.1f} KB)")
    print(f"  Encoding: {encoding}")
    
    results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "audio_size": len(audio_data),
        "encoding": encoding
    }
    
    # Save to file if requested
    if output_file:
        # Determine file extension
        if not output_file.endswith(f'.{encoding}'):
            output_file = f"{output_file}.{encoding}"
        
        print(f"\nSaving to: {output_file}")
        try:
            with open(output_file, 'wb') as f:
                f.write(audio_data)
            print(f"  ✓ Saved successfully")
            results["output_file"] = output_file
        except Exception as e:
            print(f"  ✗ Failed to save: {e}")
    else:
        print(f"\nTip: Use --output to save the audio file")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test TTS with text input (supports Riva and Doubao)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test Riva TTS with config file
  python tests/test_tts.py --config config.yaml --text "你好，世界"
  
  # Test Doubao TTS with config file
  python tests/test_tts.py --config config.yaml --platform doubao --text "你好，世界"
  
  # Test and save output
  python tests/test_tts.py --config config.yaml --text "Hello, world" --output test_output.wav
  
  # Test with direct parameters (Riva)
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
        help="Output file path (optional)"
    )
    parser.add_argument(
        "--platform",
        choices=["riva", "doubao"],
        default=None,
        help="TTS platform to use (default: from config or 'riva')"
    )
    # Riva-specific arguments
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
    # Doubao-specific arguments
    parser.add_argument(
        "--doubao-appid",
        help="Doubao application ID"
    )
    parser.add_argument(
        "--doubao-cluster",
        help="Doubao cluster"
    )
    parser.add_argument(
        "--doubao-voice-type",
        help="Doubao voice type ID"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    
    # Determine platform
    platform = args.platform
    
    # Load config
    config = {}
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"Loaded configuration from: {args.config}")
        else:
            print(f"Warning: Config file not found: {args.config}")
    
    # Get platform from config if not specified
    if platform is None:
        platform = config.get('tts', {}).get('platform', 'riva')
    
    print(f"\nUsing TTS platform: {platform}")
    
    if platform == 'doubao':
        # Doubao TTS
        doubao_config = config.get('doubao_tts', {})
        
        appid = args.doubao_appid or doubao_config.get('appid', '')
        cluster = args.doubao_cluster or doubao_config.get('cluster', '')
        voice_type = args.doubao_voice_type or doubao_config.get('voice_type', '')
        api_url = doubao_config.get('api_url', 'https://openspeech.bytedance.com/api/v1/tts')
        encoding = doubao_config.get('encoding', 'mp3')
        speed_ratio = doubao_config.get('speed_ratio', 1.0)
        volume_ratio = doubao_config.get('volume_ratio', 1.0)
        pitch_ratio = doubao_config.get('pitch_ratio', 1.0)
        
        api_key = args.api_key
        if not api_key:
            api_keys = doubao_config.get('api_keys', [])
            if api_keys:
                api_key = api_keys[0]
        
        if not appid or not cluster or not voice_type:
            print("Error: Doubao TTS requires appid, cluster, and voice_type.")
            print("Use --doubao-appid, --doubao-cluster, --doubao-voice-type or specify in config file.")
            sys.exit(1)
        
        if not api_key:
            print("Error: API key not provided.")
            print("Use --api-key or specify in config file.")
            sys.exit(1)
        
        results = test_doubao_tts(
            appid=appid,
            access_token=api_key,
            cluster=cluster,
            voice_type=voice_type,
            text=args.text,
            api_url=api_url,
            encoding=encoding,
            speed_ratio=speed_ratio,
            volume_ratio=volume_ratio,
            pitch_ratio=pitch_ratio,
            output_file=args.output,
            verbose=args.verbose
        )
    else:
        # Riva TTS
        tts_config = config.get('riva_tts', {})
        
        server = args.server
        if not server:
            server = tts_config.get('server', 'grpc.nvcf.nvidia.com:443')
        
        api_key = args.api_key
        if not api_key:
            api_keys = tts_config.get('api_keys', [])
            if api_keys:
                api_key = api_keys[0]
        
        language_code = args.language
        if language_code is None:
            language_code = tts_config.get('language_code', 'zh-CN')
        
        voice_name = args.voice
        if not voice_name:
            voice_name = tts_config.get('voice_name')
        
        sample_rate_hz = args.sample_rate
        if sample_rate_hz is None:
            sample_rate_hz = tts_config.get('sample_rate_hz', 48000)
        
        use_ssl = not args.no_ssl
        if 'use_ssl' in tts_config and not args.no_ssl:
            use_ssl = tts_config.get('use_ssl', True)
        
        function_id = args.function_id
        if not function_id:
            function_id = tts_config.get('function_id')
        
        zero_shot_audio = args.zero_shot_audio
        if not zero_shot_audio:
            zero_shot_audio = tts_config.get('zero_shot_audio_prompt_file')
        
        zero_shot_quality = args.zero_shot_quality
        if args.zero_shot_quality == DEFAULT_ZERO_SHOT_QUALITY:
            zero_shot_quality = tts_config.get('zero_shot_quality', DEFAULT_ZERO_SHOT_QUALITY)
        
        if not server:
            print("Error: Server address not provided.")
            print("Use --server or specify in config file.")
            sys.exit(1)
        
        if not api_key:
            print("Error: API key not provided.")
            print("Use --api-key or specify in config file.")
            sys.exit(1)
        
        # Run Riva TTS test
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
