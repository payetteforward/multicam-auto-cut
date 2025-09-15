"""
Audio Extraction Module
Handles extracting specific audio tracks from multicam clips and preparing them for transcription.
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import unquote

# Set up logging
logger = logging.getLogger(__name__)

class AudioExtractor:
    """
    Extracts and processes audio from multicam clips for transcription.
    """
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        Initialize the audio extractor.
        
        Args:
            temp_dir (str): Directory for temporary files
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if ffmpeg is available
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg is required but not found in PATH. Please install ffmpeg.")
    
    def _check_ffmpeg(self) -> bool:
        """
        Check if ffmpeg is available in the system PATH.
        
        Returns:
            bool: True if ffmpeg is available
        """
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _clean_file_path(self, file_path: str) -> str:
        """
        Clean and normalize file paths from FCPXML.
        
        Args:
            file_path (str): Raw file path from FCPXML
            
        Returns:
            str: Cleaned file path
        """
        if not file_path:
            return ""
        
        # Remove file:// prefix if present
        if file_path.startswith('file://'):
            file_path = file_path[7:]
        
        # Handle localhost prefix
        if file_path.startswith('localhost/'):
            file_path = file_path[9:]
        
        # URL decode the path
        file_path = unquote(file_path)
        
        # Ensure it's an absolute path
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        return file_path
    
    def extract_audio_from_multicam(self, fcpxml_data: Dict, mono_track_info: Dict, 
                                   output_filename: Optional[str] = None) -> str:
        """
        Extract the mono audio track from multicam clip for transcription.
        
        Args:
            fcpxml_data (Dict): Parsed FCPXML data
            mono_track_info (Dict): Information about the mono audio track
            output_filename (str, optional): Custom output filename
            
        Returns:
            str: Path to the extracted audio file
        """
        logger.info("Extracting audio from multicam clip...")
        
        # Get the source audio file path
        source_path = self._clean_file_path(mono_track_info['media_path'])
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source audio file not found: {source_path}")
        
        # Generate output filename - use MP3 for size reduction
        if not output_filename:
            source_name = Path(source_path).stem
            output_filename = f"{source_name}_extracted.mp3"

        output_path = self.temp_dir / output_filename

        # Get source file size to determine if compression is needed
        source_size = Path(source_path).stat().st_size
        source_size_mb = source_size / (1024 * 1024)

        # Extract audio using ffmpeg
        logger.info(f"Extracting audio from: {source_path}")
        logger.info(f"Source size: {source_size_mb:.1f} MB")
        logger.info(f"Output path: {output_path}")

        try:
            # Build ffmpeg command - convert to MP3 at 56kbps for size reduction
            # This maintains adequate quality for transcription while significantly reducing file size
            cmd = [
                'ffmpeg',
                '-i', source_path,
                '-b:a', '56k',  # 56 kbps bitrate (reduces ~10x from WAV)
                '-ac', '1',  # Mono channel
                '-ar', '16000',  # 16kHz sample rate (optimal for Whisper)
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
            
            # Run ffmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"ffmpeg error: {result.stderr}")
                raise RuntimeError(f"Failed to extract audio: {result.stderr}")
            
            # Verify output file was created
            if not output_path.exists():
                raise RuntimeError("Audio extraction completed but output file not found")
            
            # Get file sizes for logging
            file_size = output_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            reduction_ratio = source_size / file_size if file_size > 0 else 0

            logger.info(f"✅ Audio extracted successfully: {output_path}")
            logger.info(f"   Original: {source_size_mb:.1f} MB → Compressed: {file_size_mb:.1f} MB")
            logger.info(f"   Size reduction: {reduction_ratio:.1f}x")

            # Verify file is under 25MB for API
            if file_size_mb > 25:
                logger.warning(f"Compressed file still {file_size_mb:.1f} MB - may need further compression")

            return str(output_path)
            
        except subprocess.TimeoutExpired:
            logger.error("Audio extraction timed out")
            raise RuntimeError("Audio extraction timed out after 5 minutes")
        except Exception as e:
            logger.error(f"Unexpected error during audio extraction: {e}")
            raise
    
    def validate_audio_for_whisper(self, audio_path: str) -> Tuple[bool, str]:
        """
        Validate that an audio file is suitable for Whisper transcription.
        
        Args:
            audio_path (str): Path to the audio file
            
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        if not os.path.exists(audio_path):
            return False, f"Audio file not found: {audio_path}"
        
        # Get audio information
        info = self.get_audio_info(audio_path)
        
        if not info:
            return False, "Could not read audio file information"
        
        # Note: File size check removed - transcriber handles splitting large files automatically
        file_size_mb = info.get('size', 0) / (1024 * 1024)
        logger.info(f"Audio file size: {file_size_mb:.1f}MB (will be split if >25MB)")
        
        # Check duration (reasonable limits)
        duration = info.get('duration', 0)
        if duration == 0:
            return False, "Audio file appears to have no duration"
        
        if duration > 3600:  # 1 hour
            logger.warning(f"Audio file is quite long: {duration/60:.1f} minutes")
        
        # Check sample rate
        sample_rate = info.get('sample_rate', 0)
        if sample_rate < 8000:
            return False, f"Sample rate too low: {sample_rate}Hz (minimum: 8kHz)"
        
        # Check channels
        channels = info.get('channels', 0)
        if channels == 0:
            return False, "No audio channels detected"
        
        logger.info(f"Audio validation passed:")
        logger.info(f"  Duration: {duration/60:.1f} minutes")
        logger.info(f"  Size: {file_size_mb:.1f}MB")
        logger.info(f"  Sample Rate: {sample_rate}Hz")
        logger.info(f"  Channels: {channels}")
        logger.info(f"  Codec: {info.get('codec', 'unknown')}")
        
        return True, "Audio file is valid for transcription"
    
    def get_audio_info(self, audio_path: str) -> Dict:
        """
        Get information about an audio file using ffprobe.
        
        Args:
            audio_path (str): Path to the audio file
            
        Returns:
            Dict: Audio file information
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"Could not get audio info: {result.stderr}")
                return {}
            
            import json
            probe_data = json.loads(result.stdout)
            
            # Extract relevant information
            audio_info = {
                'duration': float(probe_data['format'].get('duration', 0)),
                'size': int(probe_data['format'].get('size', 0)),
                'bitrate': int(probe_data['format'].get('bit_rate', 0)),
            }
            
            # Get audio stream info
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_info.update({
                        'sample_rate': int(stream.get('sample_rate', 0)),
                        'channels': int(stream.get('channels', 0)),
                        'codec': stream.get('codec_name', 'unknown')
                    })
                    break
            
            return audio_info
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Could not get audio info: {e}")
            return {}
    
    def cleanup_temp_files(self, keep_files: list = None):
        """
        Clean up temporary audio files.
        
        Args:
            keep_files (list, optional): List of files to keep
        """
        if keep_files is None:
            keep_files = []
        
        keep_files = [Path(f).name for f in keep_files]
        
        # Clean up both WAV and MP3 files
        for pattern in ["*.wav", "*.mp3"]:
            for file_path in self.temp_dir.glob(pattern):
                if file_path.name not in keep_files:
                    try:
                        file_path.unlink()
                        logger.debug(f"Deleted temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete temporary file {file_path}: {e}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Audio Extractor Module")
    print("=" * 22)
    
    try:
        extractor = AudioExtractor()
        print("✅ Audio extractor initialized successfully")
        print("✅ ffmpeg is available")
        print("\nReady to extract audio from multicam clips!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 Please install ffmpeg:")
        print("   macOS: brew install ffmpeg")
