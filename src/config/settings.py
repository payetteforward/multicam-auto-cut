"""
Configuration settings for the Multicam Auto-Cut System.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class AppSettings:
    """Application-wide settings."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Directories
    temp_dir: Path = Path("./temp")
    transcript_cache_dir: Path = Path("./transcripts")
    output_dir: Path = Path("./outputs")

    # Processing Options
    cleaning_level: str = "moderate"  # light, moderate, aggressive
    use_transcript_cache: bool = True
    edit_transcript: bool = True
    transcription_model: str = "auto"  # auto, whisper-1, etc

    # Frame Rate Settings
    default_frame_rate: str = "29.97df"

    # Audio Settings
    audio_sample_rate: int = 16000
    audio_compress_quality: int = 2  # 0-9, where 0 is best
    max_audio_size_mb: int = 25

    # Debug Options
    keep_temp_files: bool = False
    save_debug_transcript: bool = True
    verbose_logging: bool = False

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Create settings from environment variables."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            temp_dir=Path(os.getenv("TEMP_DIR", "./temp")),
            transcript_cache_dir=Path(os.getenv("TRANSCRIPT_CACHE_DIR", "./transcripts")),
            output_dir=Path(os.getenv("OUTPUT_DIR", "./outputs")),
            cleaning_level=os.getenv("CLEANING_LEVEL", "moderate"),
            use_transcript_cache=os.getenv("USE_TRANSCRIPT_CACHE", "true").lower() == "true",
            edit_transcript=os.getenv("EDIT_TRANSCRIPT", "true").lower() == "true",
            transcription_model=os.getenv("TRANSCRIPTION_MODEL", "auto"),
            keep_temp_files=os.getenv("KEEP_TEMP_FILES", "false").lower() == "true",
            save_debug_transcript=os.getenv("SAVE_DEBUG_TRANSCRIPT", "true").lower() == "true",
            verbose_logging=os.getenv("VERBOSE_LOGGING", "false").lower() == "true",
        )

    def validate(self) -> None:
        """Validate settings and raise errors if invalid."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")

        if self.edit_transcript and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when transcript editing is enabled")

        if self.cleaning_level not in ["light", "moderate", "aggressive"]:
            raise ValueError(f"Invalid cleaning level: {self.cleaning_level}")

        # Create directories if they don't exist
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)