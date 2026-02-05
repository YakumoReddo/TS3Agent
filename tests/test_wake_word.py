#!/usr/bin/env python3
"""
Wake Word Detection Test Utility

This script tests the Porcupine wake word detection component by processing
an audio file and reporting when/if the wake word is detected.

Usage:
    python tests/test_wake_word.py --config config.yaml --audio test_audio.wav
    python tests/test_wake_word.py --access-key YOUR_KEY --keywords porcupine --audio test_audio.wav
"""

import os
import sys
import wave
import struct
import time
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

try:
    import pvporcupine
except ImportError:
    print("Error: pvporcupine not installed. Install with: pip install pvporcupine")
    sys.exit(1)


def read_audio_file(file_path: str, target_sample_rate: int) -> tuple:
    """
    Read audio file and return samples.
    
    Args:
        file_path: Path to WAV audio file
        target_sample_rate: Expected sample rate (typically 16000 for Porcupine)
        
    Returns:
        Tuple of (samples as list of int16, sample_rate, duration_seconds)
    """
    wav_file = wave.open(file_path, mode="rb")
    channels = wav_file.getnchannels()
    sample_width = wav_file.getsampwidth()
    num_frames = wav_file.getnframes()
    sample_rate = wav_file.getframerate()
    
    print(f"Audio file info:")
    print(f"  - Channels: {channels}")
    print(f"  - Sample width: {sample_width} bytes ({sample_width * 8}-bit)")
    print(f"  - Sample rate: {sample_rate} Hz")
    print(f"  - Total frames: {num_frames}")
    print(f"  - Duration: {num_frames / sample_rate:.2f} seconds")
    
    if sample_rate != target_sample_rate:
        print(f"\nWarning: Audio file sample rate ({sample_rate}Hz) differs from expected ({target_sample_rate}Hz)")
        print("You may need to resample the audio file for accurate results.")
    
    if sample_width != 2:
        raise ValueError(f"Audio file should be 16-bit. Got {sample_width * 8}-bit")
    
    if channels == 2:
        print("\nNote: Stereo audio detected. Using left channel only for wake word detection.")
    
    samples = wav_file.readframes(num_frames)
    wav_file.close()
    
    # Unpack samples
    frames = struct.unpack('h' * num_frames * channels, samples)
    
    # Take only left channel if stereo
    mono_samples = list(frames[::channels])
    
    duration = num_frames / sample_rate
    return mono_samples, sample_rate, duration


def test_wake_word(
    access_key: str,
    audio_path: str,
    keywords: list = None,
    keyword_paths: list = None,
    sensitivity: float = 0.5,
    simulate_realtime: bool = False
):
    """
    Test wake word detection on an audio file.
    
    Args:
        access_key: Porcupine access key
        audio_path: Path to audio file
        keywords: List of built-in keywords (e.g., ['porcupine'])
        keyword_paths: List of custom keyword file paths (.ppn files)
        sensitivity: Detection sensitivity (0.0 to 1.0)
        simulate_realtime: If True, process at real-time speed
    """
    print("=" * 60)
    print("Wake Word Detection Test")
    print("=" * 60)
    
    # Validate inputs
    if not keywords and not keyword_paths:
        print("Error: Either --keywords or --keyword-paths must be specified")
        return False
    
    if not Path(audio_path).exists():
        print(f"Error: Audio file not found: {audio_path}")
        return False
    
    # Get keyword paths
    if keyword_paths is None:
        keyword_paths = [pvporcupine.KEYWORD_PATHS[kw] for kw in keywords]
        keyword_names = keywords
    else:
        # Extract names from paths
        # Porcupine .ppn files follow naming convention: keyword_platform_version.ppn
        # e.g., "hey_siri_mac_v2_1_0.ppn" -> "hey siri"
        # Files with more than 6 underscore-separated parts have multi-word keywords
        keyword_names = []
        for p in keyword_paths:
            name_parts = os.path.basename(p).replace('.ppn', '').split('_')
            # Last 6 parts are typically: platform_major_minor_patch (e.g., mac_v2_1_0)
            # If more than 6 parts exist, the keyword is multi-word
            if len(name_parts) > 6:
                keyword_names.append(' '.join(name_parts[0:-6]))
            else:
                keyword_names.append(name_parts[0])
    
    print(f"\nKeywords to detect: {keyword_names}")
    print(f"Sensitivity: {sensitivity}")
    
    # Create Porcupine instance
    try:
        sensitivities = [sensitivity] * len(keyword_paths)
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=keyword_paths,
            sensitivities=sensitivities
        )
        print(f"Porcupine initialized successfully")
        print(f"  - Frame length: {porcupine.frame_length} samples")
        print(f"  - Sample rate: {porcupine.sample_rate} Hz")
    except Exception as e:
        print(f"Error initializing Porcupine: {e}")
        return False
    
    # Read audio file
    try:
        samples, file_sample_rate, duration = read_audio_file(audio_path, porcupine.sample_rate)
    except Exception as e:
        print(f"Error reading audio file: {e}")
        porcupine.delete()
        return False
    
    # Process audio
    print(f"\n{'=' * 60}")
    print("Processing audio...")
    print("=" * 60)
    
    frame_length = porcupine.frame_length
    num_frames = len(samples) // frame_length
    detections = []
    
    start_time = time.time()
    
    for i in range(num_frames):
        frame = samples[i * frame_length:(i + 1) * frame_length]
        
        if simulate_realtime:
            # Sleep to simulate real-time processing
            time.sleep(frame_length / porcupine.sample_rate)
        
        result = porcupine.process(frame)
        
        if result >= 0:
            time_offset = (i * frame_length) / porcupine.sample_rate
            detection = {
                'keyword': keyword_names[result],
                'keyword_index': result,
                'time_seconds': time_offset,
                'frame_index': i
            }
            detections.append(detection)
            print(f"  [DETECTED] '{keyword_names[result]}' at {time_offset:.2f} seconds (frame {i})")
    
    processing_time = time.time() - start_time
    
    # Cleanup
    porcupine.delete()
    
    # Report results
    print(f"\n{'=' * 60}")
    print("Test Results")
    print("=" * 60)
    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Processing time: {processing_time:.2f} seconds")
    print(f"Processing speed: {duration / processing_time:.1f}x real-time")
    print(f"Total frames processed: {num_frames}")
    print(f"Total detections: {len(detections)}")
    
    if detections:
        print(f"\nDetection summary:")
        for det in detections:
            print(f"  - '{det['keyword']}' at {det['time_seconds']:.2f}s")
        return True
    else:
        print(f"\nNo wake word detected in the audio file.")
        print("Possible reasons:")
        print("  - The wake word is not present in the audio")
        print("  - Audio quality is too low")
        print("  - Sensitivity is too low (try increasing it)")
        print("  - Sample rate mismatch (audio should be 16kHz)")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test wake word detection with an audio file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with config file
  python tests/test_wake_word.py --config config.yaml --audio wake_test.wav
  
  # Test with built-in keyword
  python tests/test_wake_word.py --access-key YOUR_KEY --keywords porcupine --audio wake_test.wav
  
  # Test with custom keyword file
  python tests/test_wake_word.py --access-key YOUR_KEY --keyword-paths /path/to/keyword.ppn --audio wake_test.wav
  
  # Test with higher sensitivity
  python tests/test_wake_word.py --config config.yaml --audio wake_test.wav --sensitivity 0.7
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file (will use wake_word settings from config)"
    )
    parser.add_argument(
        "--audio", "-a",
        required=True,
        help="Path to audio file to test (WAV format, 16kHz recommended)"
    )
    parser.add_argument(
        "--access-key",
        help="Porcupine access key (overrides config)"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        help=f"Built-in keywords to detect. Available: {', '.join(sorted(pvporcupine.KEYWORDS))}"
    )
    parser.add_argument(
        "--keyword-paths",
        nargs="+",
        help="Paths to custom keyword files (.ppn)"
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=None,
        help="Detection sensitivity (0.0 to 1.0, default: 0.5)"
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Process at real-time speed (for debugging timing)"
    )
    
    args = parser.parse_args()
    
    # Load config if provided
    access_key = args.access_key
    keywords = args.keywords
    keyword_paths = args.keyword_paths
    sensitivity = args.sensitivity if args.sensitivity is not None else 0.5
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            wake_config = config.get('wake_word', {})
            
            if not access_key:
                access_key = wake_config.get('access_key')
            if not keywords and not keyword_paths:
                keywords = wake_config.get('keywords')
                keyword_paths = wake_config.get('keyword_paths')
            if args.sensitivity is None:
                sensitivity = wake_config.get('sensitivity', 0.5)
            
            print(f"Loaded configuration from: {args.config}")
        else:
            print(f"Warning: Config file not found: {args.config}")
    
    if not access_key:
        print("Error: Porcupine access key not provided.")
        print("Use --access-key or specify in config file.")
        sys.exit(1)
    
    # Run test
    success = test_wake_word(
        access_key=access_key,
        audio_path=args.audio,
        keywords=keywords,
        keyword_paths=keyword_paths,
        sensitivity=sensitivity,
        simulate_realtime=args.realtime
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
