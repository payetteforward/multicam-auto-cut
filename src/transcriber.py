"""
Transcription Module
Handles audio transcription using OpenAI's latest models with automatic file splitting for large files.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime
import math

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, will use system environment variables

# Set up logging
logger = logging.getLogger(__name__)

class Transcriber:
    """
    Handles audio transcription with timestamp information for precise cutting.
    Automatically splits large files to stay under the 25MB API limit.
    """

    # API limits
    MAX_FILE_SIZE_MB = 25
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    # Chunk settings for splitting (10 minutes with 30s overlap)
    CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 minutes in milliseconds
    OVERLAP_DURATION_MS = 30 * 1000  # 30 seconds overlap for context

    def __init__(self, api_key: Optional[str] = None, method: str = 'api', model: str = 'auto'):
        """
        Initialize the transcriber.

        Args:
            api_key (str, optional): OpenAI API key
            method (str): 'api' for OpenAI API or 'local' for local Whisper
            model (str): 'auto', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe', or 'whisper-1'
        """
        self.method = method
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.model = model

        if method == 'api' and not self.api_key:
            raise ValueError("OpenAI API key required for API transcription method")

        if method == 'api':
            self._setup_openai_client()
        elif method == 'local':
            self._setup_local_whisper()

    def _setup_openai_client(self):
        """Set up OpenAI client for API transcription."""
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI client initialized")
        except ImportError:
            raise ImportError("openai package required for API transcription. Install with: pip install openai")

    def _setup_local_whisper(self):
        """Set up local Whisper model."""
        try:
            import whisper
            logger.info("Loading local Whisper model...")
            self.local_model = whisper.load_model("base")
            logger.info("✅ Local Whisper model loaded")
        except ImportError:
            raise ImportError("whisper package required for local transcription. Install with: pip install openai-whisper")

    def _get_audio_duration_ms(self, audio_path: str) -> int:
        """
        Get audio duration in milliseconds using pydub.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in milliseconds
        """
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio)
        except ImportError:
            logger.warning("pydub not installed, cannot determine audio duration")
            return 0
        except Exception as e:
            logger.warning(f"Could not determine audio duration: {e}")
            return 0

    def _split_audio_file(self, audio_path: str) -> List[Tuple[str, float, float]]:
        """
        Split audio file into chunks under 25MB.

        Args:
            audio_path: Path to the audio file

        Returns:
            List of tuples (chunk_path, start_time, end_time)
        """
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError("pydub required for splitting large files. Install with: pip install pydub")

        logger.info(f"Splitting large audio file: {audio_path}")

        # Load audio
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)

        # Calculate chunk size based on file size
        file_size = Path(audio_path).stat().st_size
        if file_size <= self.MAX_FILE_SIZE_BYTES:
            logger.info("File is under 25MB, no splitting needed")
            return [(audio_path, 0.0, duration_ms / 1000.0)]

        # Calculate how many chunks we need
        size_ratio = file_size / self.MAX_FILE_SIZE_BYTES
        num_chunks = math.ceil(size_ratio)
        chunk_duration_ms = duration_ms // num_chunks + self.OVERLAP_DURATION_MS

        chunks = []
        temp_dir = Path(audio_path).parent / "temp_chunks"
        temp_dir.mkdir(exist_ok=True)

        for i in range(num_chunks):
            start_ms = max(0, i * (chunk_duration_ms - self.OVERLAP_DURATION_MS))
            end_ms = min(duration_ms, start_ms + chunk_duration_ms)

            # Extract chunk
            chunk = audio[start_ms:end_ms]

            # Save chunk
            chunk_path = temp_dir / f"chunk_{i:03d}.wav"
            chunk.export(chunk_path, format="wav")

            chunks.append((str(chunk_path), start_ms / 1000.0, end_ms / 1000.0))

            logger.info(f"Created chunk {i+1}/{num_chunks}: {start_ms/1000:.1f}s - {end_ms/1000:.1f}s")

        return chunks

    def _determine_model(self, need_timestamps: bool) -> str:
        """
        Determine which model to use based on requirements.

        Args:
            need_timestamps: Whether we need detailed timestamps

        Returns:
            Model name to use
        """
        if self.model != 'auto':
            return self.model

        # Use whisper-1 if we need timestamps (verbose_json)
        if need_timestamps:
            logger.info("Using whisper-1 for timestamp support")
            return 'whisper-1'

        # Otherwise use the better gpt-4o-transcribe model
        logger.info("Using gpt-4o-transcribe for better accuracy")
        return 'gpt-4o-transcribe'

    def transcribe_audio(self, audio_path: str, language: str = 'en',
                        response_format: str = 'verbose_json',
                        prompt: Optional[str] = None) -> Dict:
        """
        Transcribe audio file with automatic handling of large files.

        Args:
            audio_path (str): Path to audio file
            language (str): Language code
            response_format (str): Response format ('verbose_json', 'json', 'text')
            prompt (str, optional): Prompt to improve transcription quality

        Returns:
            Dict: Transcription result with segments and text
        """
        if self.method == 'local':
            return self._transcribe_local(audio_path, language)

        # Check file size
        file_size = Path(audio_path).stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Audio file size: {file_size_mb:.1f} MB")

        # Determine model based on requirements
        need_timestamps = response_format == 'verbose_json'
        model = self._determine_model(need_timestamps)

        # Adjust response format for gpt-4o models
        if model in ['gpt-4o-transcribe', 'gpt-4o-mini-transcribe'] and response_format == 'verbose_json':
            logger.warning(f"{model} doesn't support verbose_json, using whisper-1 instead")
            model = 'whisper-1'

        # Split if necessary
        if file_size > self.MAX_FILE_SIZE_BYTES:
            logger.info(f"File is {file_size_mb:.1f}MB, splitting into chunks...")
            return self._transcribe_chunked(audio_path, language, model, response_format, prompt)

        # Single file transcription
        return self._transcribe_single_file(audio_path, language, model, response_format, prompt)

    def _transcribe_single_file(self, audio_path: str, language: str,
                               model: str, response_format: str,
                               prompt: Optional[str] = None) -> Dict:
        """
        Transcribe a single audio file.

        Args:
            audio_path: Path to audio file
            language: Language code
            model: Model to use
            response_format: Response format
            prompt: Optional prompt

        Returns:
            Transcription result
        """
        logger.info(f"Transcribing with {model} (format: {response_format})")

        try:
            with open(audio_path, 'rb') as audio_file:
                # Prepare parameters
                params = {
                    'file': audio_file,
                    'model': model,
                    'language': language
                }

                # Add response format if not default
                if response_format != 'json':
                    params['response_format'] = response_format

                # Add prompt if provided
                if prompt:
                    params['prompt'] = prompt
                elif model == 'whisper-1':
                    # Default prompt for whisper-1 to improve quality
                    params['prompt'] = "This is an interview or presentation with natural speech patterns."

                # Make API call
                start_time = time.time()
                response = self.client.audio.transcriptions.create(**params)
                elapsed = time.time() - start_time

                logger.info(f"✅ Transcription completed in {elapsed:.1f} seconds")

                # Handle different response formats
                if response_format == 'verbose_json':
                    # Response is already a structured object
                    return response.model_dump()
                elif response_format == 'text':
                    # Convert text response to expected format
                    return {
                        'text': response,
                        'segments': [],
                        'language': language
                    }
                else:
                    # JSON response
                    if hasattr(response, 'model_dump'):
                        return response.model_dump()
                    else:
                        return {'text': response.text, 'segments': [], 'language': language}

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def _transcribe_chunked(self, audio_path: str, language: str,
                          model: str, response_format: str,
                          prompt: Optional[str] = None) -> Dict:
        """
        Transcribe audio in chunks and combine results.

        Args:
            audio_path: Path to audio file
            language: Language code
            model: Model to use
            response_format: Response format
            prompt: Optional prompt

        Returns:
            Combined transcription result
        """
        # Split audio into chunks
        chunks = self._split_audio_file(audio_path)

        all_segments = []
        all_text = []
        previous_transcript = ""

        for i, (chunk_path, start_time, end_time) in enumerate(chunks):
            logger.info(f"Transcribing chunk {i+1}/{len(chunks)}")

            # Use previous transcript as context for better continuity
            chunk_prompt = prompt or ""
            if previous_transcript and model == 'whisper-1':
                # Whisper only uses last 224 tokens of prompt
                chunk_prompt = previous_transcript[-500:] + " " + chunk_prompt

            # Transcribe chunk
            result = self._transcribe_single_file(
                chunk_path, language, model, response_format, chunk_prompt
            )

            # Adjust timestamps for segments
            if 'segments' in result and result['segments']:
                for segment in result['segments']:
                    # Adjust segment timestamps to account for chunk position
                    segment['start'] = segment.get('start', 0) + start_time
                    segment['end'] = segment.get('end', 0) + start_time
                    all_segments.append(segment)

            # Collect text
            if 'text' in result:
                all_text.append(result['text'])
                previous_transcript = result['text']

        # Clean up temp chunks
        self._cleanup_chunks(chunks)

        # Combine results
        combined_result = {
            'text': ' '.join(all_text),
            'segments': all_segments,
            'language': language,
            'duration': chunks[-1][2] if chunks else 0,
            'chunks_processed': len(chunks)
        }

        logger.info(f"✅ Combined {len(chunks)} chunks into final transcript")
        return combined_result

    def _cleanup_chunks(self, chunks: List[Tuple[str, float, float]]):
        """Clean up temporary chunk files."""
        for chunk_path, _, _ in chunks:
            try:
                if chunk_path and Path(chunk_path).exists():
                    Path(chunk_path).unlink()
            except Exception as e:
                logger.warning(f"Could not delete chunk file {chunk_path}: {e}")

        # Try to remove temp directory
        if chunks:
            temp_dir = Path(chunks[0][0]).parent
            if temp_dir.name == "temp_chunks":
                try:
                    temp_dir.rmdir()
                except:
                    pass

    def _transcribe_local(self, audio_path: str, language: str) -> Dict:
        """
        Transcribe using local Whisper model.

        Args:
            audio_path (str): Path to audio file
            language (str): Language code

        Returns:
            Dict: Transcription result
        """
        logger.info("Transcribing with local Whisper model...")

        result = self.local_model.transcribe(
            audio_path,
            language=language,
            verbose=False
        )

        logger.info(f"✅ Local transcription complete")
        return result

def create_demo_transcription() -> Dict:
    """
    Create a demo transcription for testing without API calls.

    Returns:
        Dict: Demo transcription with segments
    """
    return {
        "text": "So, um, today we're going to talk about, uh, the new features. "
               "You know, like, we've been working really hard on this. "
               "Uh, basically, what we've done is, um, improved the interface. "
               "And, like, the performance is, you know, much better now.",
        "segments": [
            {"start": 0.0, "end": 3.0, "text": "So, um, today we're going to talk about,"},
            {"start": 3.0, "end": 5.0, "text": " uh, the new features."},
            {"start": 5.0, "end": 6.5, "text": " You know, like,"},
            {"start": 6.5, "end": 9.0, "text": " we've been working really hard on this."},
            {"start": 9.0, "end": 11.0, "text": " Uh, basically, what we've done is,"},
            {"start": 11.0, "end": 13.5, "text": " um, improved the interface."},
            {"start": 13.5, "end": 14.5, "text": " And, like,"},
            {"start": 14.5, "end": 17.0, "text": " the performance is, you know, much better now."}
        ],
        "language": "en",
        "duration": 17.0
    }

if __name__ == "__main__":
    # Test the transcriber
    print("Transcriber Module")
    print("=" * 40)

    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        print("✅ OpenAI API key found")
    else:
        print("⚠️  No OpenAI API key found")
        print("Set OPENAI_API_KEY environment variable to use API transcription")

    # Show demo transcription
    print("\nDemo transcription:")
    demo = create_demo_transcription()
    print(f"Text: {demo['text'][:100]}...")
    print(f"Segments: {len(demo['segments'])}")
    print(f"Duration: {demo['duration']} seconds")