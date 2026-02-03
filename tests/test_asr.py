#!/usr/bin/env python3
"""
ASR (Automatic Speech Recognition) Test Utility

This script tests the Riva ASR component by transcribing an audio file.

Usage:
    python tests/test_asr.py --config config.yaml --audio test_audio.wav
    python tests/test_asr.py --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY --audio test.wav
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "python-clients"))

import yaml


def test_asr(
    server: str,
    api_key: str,
    audio_path: str,
    language_code: str = "zh-CN",
    use_ssl: bool = True,
    function_id: str = None,
    verbose: bool = False
) -> dict:
    """
    Test ASR transcription on an audio file.
    
    Args:
        server: Riva server address (e.g., 'grpc.nvcf.nvidia.com:443')
        api_key: API key for authentication
        audio_path: Path to audio file
        language_code: Language code (e.g., 'zh-CN', 'en-US')
        use_ssl: Use SSL connection
        function_id: NVCF function ID (optional)
        verbose: Print verbose output
        
    Returns:
        Dict with test results
    """
    print("=" * 60)
    print("ASR (Speech Recognition) Test")
    print("=" * 60)
    
    # Validate input file
    audio_file = Path(audio_path)
    if not audio_file.exists():
        print(f"Error: Audio file not found: {audio_path}")
        return {"success": False, "error": "File not found"}
    
    print(f"\nConfiguration:")
    print(f"  - Server: {server}")
    print(f"  - Language: {language_code}")
    print(f"  - SSL: {use_ssl}")
    print(f"  - Function ID: {function_id or 'None'}")
    print(f"  - Audio file: {audio_path}")
    
    # Get file info
    file_size = audio_file.stat().st_size
    print(f"  - File size: {file_size / 1024:.1f} KB")
    
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
        asr_service = riva.client.ASRService(auth)
        print(f"  Connected successfully")
    except Exception as e:
        print(f"\nError connecting to server: {e}")
        return {"success": False, "error": f"Connection error: {e}"}
    
    # Configure recognition
    config = riva.client.RecognitionConfig(
        language_code=language_code,
        max_alternatives=3,
        enable_automatic_punctuation=True,
    )
    
    # Read audio file
    print(f"\nReading audio file...")
    try:
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        print(f"  Read {len(audio_data)} bytes")
    except Exception as e:
        print(f"Error reading audio file: {e}")
        return {"success": False, "error": f"File read error: {e}"}
    
    # Perform recognition
    print(f"\nSending to ASR service...")
    import time
    start_time = time.time()
    
    try:
        response = asr_service.offline_recognize(audio_data, config)
        elapsed_time = time.time() - start_time
        print(f"  Response received in {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"\nASR Error: {e}")
        return {"success": False, "error": f"ASR error: {e}"}
    
    # Extract results
    print(f"\n{'=' * 60}")
    print("Results")
    print("=" * 60)
    
    results = {
        "success": True,
        "elapsed_time": elapsed_time,
        "transcripts": [],
        "alternatives": []
    }
    
    if response.results:
        for i, result in enumerate(response.results):
            print(f"\nResult {i + 1}:")
            
            if result.alternatives:
                for j, alt in enumerate(result.alternatives):
                    transcript = alt.transcript
                    confidence = getattr(alt, 'confidence', None)
                    
                    if j == 0:
                        results["transcripts"].append(transcript)
                        print(f"  [Best] {transcript}")
                        if confidence is not None:
                            print(f"         Confidence: {confidence:.3f}")
                    else:
                        results["alternatives"].append({
                            "transcript": transcript,
                            "confidence": confidence
                        })
                        if verbose:
                            print(f"  [Alt {j}] {transcript}")
                            if confidence is not None:
                                print(f"          Confidence: {confidence:.3f}")
        
        # Print final transcript
        final_transcript = " ".join(results["transcripts"])
        print(f"\n{'=' * 60}")
        print("Final Transcript:")
        print("=" * 60)
        print(final_transcript)
        results["final_transcript"] = final_transcript
    else:
        print("\nNo transcription results returned.")
        print("Possible reasons:")
        print("  - Audio file is empty or too short")
        print("  - Audio quality is too low")
        print("  - Wrong language code")
        print("  - Audio format not supported")
        results["success"] = False
        results["error"] = "No results returned"
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test Riva ASR with an audio file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with config file
  python tests/test_asr.py --config config.yaml --audio speech.wav
  
  # Test with direct parameters
  python tests/test_asr.py --server grpc.nvcf.nvidia.com:443 --api-key YOUR_KEY \\
      --language zh-CN --audio speech.wav
  
  # Test with verbose output
  python tests/test_asr.py --config config.yaml --audio speech.wav --verbose
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file"
    )
    parser.add_argument(
        "--audio", "-a",
        required=True,
        help="Path to audio file to transcribe"
    )
    parser.add_argument(
        "--server",
        help="Riva server address (e.g., grpc.nvcf.nvidia.com:443)"
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
        "--function-id",
        help="NVCF function ID"
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
    use_ssl = not args.no_ssl
    function_id = args.function_id
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            asr_config = config.get('riva_asr', {})
            
            if not server:
                server = asr_config.get('server', 'grpc.nvcf.nvidia.com:443')
            if not api_key:
                api_keys = asr_config.get('api_keys', [])
                if api_keys:
                    api_key = api_keys[0]
            if args.language is None:
                language_code = asr_config.get('language_code', 'zh-CN')
            if not function_id:
                function_id = asr_config.get('function_id')
            if 'use_ssl' in asr_config and not args.no_ssl:
                use_ssl = asr_config.get('use_ssl', True)
            
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
    results = test_asr(
        server=server,
        api_key=api_key,
        audio_path=args.audio,
        language_code=language_code,
        use_ssl=use_ssl,
        function_id=function_id,
        verbose=args.verbose
    )
    
    if results["success"]:
        print(f"\n✓ ASR test completed successfully")
        sys.exit(0)
    else:
        print(f"\n✗ ASR test failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
