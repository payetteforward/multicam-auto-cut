"""
Complete Workflow System
Orchestrates the full multicam auto-cut workflow from FCPXML to final cut FCPXML.
"""

import os
import tempfile
import logging
import argparse
import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env file in parent directory (project root)
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")
except ImportError:
    pass  # dotenv not installed, will use system environment variables

# Import our modules
from ..processors import (
    FCPXMLParser,
    AudioExtractor,
    Transcriber,
    TranscriptCleaner,
    CutGenerator,
    TranscriptEditor
)

# Set up enhanced logging
try:
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)-15s%(reset)s %(message)s',
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))
    logger = colorlog.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(name)-15s %(message)s'
    )
    logger = logging.getLogger(__name__)

class MulticamAutoCutWorkflow:
    """
    Complete workflow orchestrator for the multicam auto-cut system.
    """

    def __init__(self, temp_dir: str = "./temp", cleaning_level: str = 'moderate', transcript_cache_dir: str = "./transcripts", edit_transcript: bool = True, editing_profile: str = "tutorial"):
        """
        Initialize the workflow.

        Args:
            temp_dir (str): Directory for temporary files
            cleaning_level (str): Level of transcript cleaning
            transcript_cache_dir (str): Directory for cached transcripts
            edit_transcript (bool): Whether to use Claude to edit transcripts
            editing_profile (str): Editing profile to use ("scripted", "tutorial", "rough", "podcast", "aggressive")
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_cache_dir = Path(transcript_cache_dir)
        self.transcript_cache_dir.mkdir(parents=True, exist_ok=True)
        self.cleaning_level = cleaning_level
        self.edit_transcript = edit_transcript

        # Initialize modules
        self.parser = FCPXMLParser()
        self.audio_extractor = AudioExtractor(temp_dir)
        self.transcriber = None  # Will be initialized based on method
        self.cleaner = TranscriptCleaner(cleaning_level)
        self.cut_generator = CutGenerator()

        # Initialize transcript editor if enabled
        self.transcript_editor = None
        self.editing_profile = editing_profile
        if self.edit_transcript:
            try:
                self.transcript_editor = TranscriptEditor(editing_profile=editing_profile)
                logger.info(f"✅ Transcript editing enabled with '{editing_profile}' profile")
            except ValueError as e:
                logger.warning(f"Transcript editing disabled: {e}")
                self.edit_transcript = False

        logger.info(f"Workflow initialized with {cleaning_level} cleaning level")
        logger.info(f"Transcript cache directory: {self.transcript_cache_dir}")

    def _get_file_hash(self, file_path: str) -> str:
        """Generate a hash for a file to use as cache key."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_transcript_cache_path(self, audio_file: str) -> Path:
        """Get the cache path for a transcript based on audio file hash."""
        file_hash = self._get_file_hash(audio_file)
        cache_filename = f"transcript_{file_hash}.json"
        return self.transcript_cache_dir / cache_filename

    def _load_cached_transcript(self, cache_path: Path) -> Optional[Dict]:
        """Load a cached transcript if it exists."""
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"✅ Loaded cached transcript from {cache_path.name}")
                    logger.info(f"   Created: {data.get('timestamp', 'Unknown')}")
                    return data['transcript']
            except Exception as e:
                logger.warning(f"Failed to load cached transcript: {e}")
        return None

    def _save_transcript_cache(self, cache_path: Path, transcript: Dict, audio_file: str):
        """Save a transcript to cache."""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'audio_file': audio_file,
                'transcript': transcript
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"💾 Transcript cached to {cache_path.name}")
        except Exception as e:
            logger.warning(f"Failed to cache transcript: {e}")

    def process_multicam_clip(self, input_fcpxml: str, output_fcpxml: str,
                            transcription_method: str = 'api',
                            api_key: Optional[str] = None,
                            keep_temp_files: bool = False,
                            use_cached_transcript: bool = True,
                            force_retranscribe: bool = False) -> Dict:
        """
        Process a complete multicam clip from input to output.

        Args:
            input_fcpxml (str): Path to input FCPXML file
            output_fcpxml (str): Path for output FCPXML file
            transcription_method (str): 'api' or 'local' or 'demo'
            api_key (str, optional): OpenAI API key for API method
            keep_temp_files (bool): Whether to keep temporary files
            use_cached_transcript (bool): Whether to use cached transcripts if available
            force_retranscribe (bool): Force re-transcription even if cache exists

        Returns:
            Dict: Results and statistics from the processing
        """
        logger.info("🚀 Starting multicam auto-cut workflow...")
        logger.info(f"Input: {input_fcpxml}")
        logger.info(f"Output: {output_fcpxml}")

        try:
            # Phase 1: Parse FCPXML
            logger.info("📄 Phase 1: Parsing FCPXML...")
            fcpxml_data = self.parser.parse_fcpxml(input_fcpxml)

            # Validate multicam structure
            if not fcpxml_data['multicam_clips']:
                raise ValueError("No multicam clips found in FCPXML")

            # Find mono audio track
            mono_track = self.parser.find_mono_audio_track(fcpxml_data)
            if not mono_track:
                raise ValueError("No mono audio track found - lav mic required")

            logger.info(f"✅ Found multicam clip with mono track: {mono_track['name']}")

            # Phase 2: Extract Audio
            logger.info("🎵 Phase 2: Extracting audio...")
            try:
                extracted_audio_path = self.audio_extractor.extract_audio_from_multicam(
                    fcpxml_data, mono_track
                )

                # Validate audio
                is_valid, message = self.audio_extractor.validate_audio_for_whisper(extracted_audio_path)
                if not is_valid:
                    raise ValueError(f"Audio validation failed: {message}")

                logger.info(f"✅ Audio extracted and validated: {Path(extracted_audio_path).name}")

            except Exception as e:
                logger.error(f"Audio extraction failed: {e}")
                raise  # Don't fall back to dummy file, let the error propagate

            # Phase 3: Transcription
            logger.info(f"🎤 Phase 3: Transcribing audio ({transcription_method})...")

            if transcription_method == 'demo':
                # Create demo transcript for testing
                transcription = self._create_demo_transcript()
                logger.info("Using demo transcript")
            else:
                # Check for cached transcript
                cache_path = self._get_transcript_cache_path(extracted_audio_path)
                transcription = None

                if use_cached_transcript and not force_retranscribe:
                    transcription = self._load_cached_transcript(cache_path)
                    if transcription:
                        logger.info("💰 Using cached transcript (avoiding API call)")
                        # Auto-accept cached transcript in non-interactive mode
                        transcription = transcription

                if transcription is None:
                    transcription = self._perform_transcription(
                        extracted_audio_path, transcription_method, api_key
                    )
                    # Save to cache
                    self._save_transcript_cache(cache_path, transcription, extracted_audio_path)

            # Phase 4: Clean Transcript
            logger.info("✨ Phase 4: Cleaning transcript...")
            cleaned_result = self.cleaner.clean_transcript(transcription)

            # Add FCPXML data to cleaned result for frame rate information
            cleaned_result['original_transcription']['fcpxml_data'] = fcpxml_data

            # Log cleaning statistics
            stats = cleaned_result['cleaning_stats']
            logger.info(f"✅ Cleaning complete:")
            logger.info(f"   Segments: {stats['original_segment_count']} → {stats['cleaned_segment_count']}")
            logger.info(f"   Duration: {stats['original_duration']:.1f}s → {stats['cleaned_duration']:.1f}s")
            logger.info(f"   Time saved: {stats['time_saved']:.1f}s ({stats['time_saved_percentage']:.1f}%)")

            # Phase 5: Edit Transcript (if enabled)
            edited_segments = None
            if self.edit_transcript and self.transcript_editor:
                logger.info("✏️  Phase 5: Editing transcript with Claude...")
                try:
                    # Get the cleaned segments from the cleaned_transcription
                    cleaned_trans = cleaned_result.get('cleaned_transcription', {})
                    segments = cleaned_trans.get('segments', [])
                    if segments:
                        # Get output directory from the output path
                        output_dir = str(Path(output_fcpxml).parent)

                        # Edit transcript and save debug file
                        edited_segments = self.transcript_editor.edit_transcript(segments, output_dir)

                        # Add edited transcript to results for reference
                        edited_text = " ".join(seg['text'] for seg in edited_segments if seg.get('keep', False))
                        cleaned_result['edited_transcript'] = edited_text

                        # Log editing statistics
                        kept_count = sum(1 for s in edited_segments if s.get('keep', False))
                        removed_count = len(segments) - kept_count
                        logger.info(f"📊 Edited transcript: keeping {kept_count}/{len(segments)} segments")
                        logger.info(f"   Removed {removed_count} segments with stutters/false starts")
                except Exception as e:
                    logger.warning(f"Transcript editing failed, using unedited version: {e}")
                    edited_segments = None

            # Phase 6: Generate Cuts
            logger.info("✂️  Phase 6: Generating cut FCPXML...")
            output_path = self.cut_generator.generate_cut_fcpxml(
                input_fcpxml, cleaned_result, output_fcpxml, edited_segments
            )

            # Phase 7: Cleanup
            if not keep_temp_files:
                logger.info("🧹 Phase 7: Cleaning up temporary files...")
                self.audio_extractor.cleanup_temp_files()

            # Compile results
            result = {
                'success': True,
                'input_file': input_fcpxml,
                'output_file': output_path,
                'original_duration': stats['original_duration'],
                'final_duration': stats['cleaned_duration'],
                'time_saved': stats['time_saved'],
                'time_saved_percentage': stats['time_saved_percentage'],
                'segments_removed': stats['segments_removed'],
                'take_groups_found': len(cleaned_result['take_groups']),
                'cleaning_level': self.cleaning_level
            }

            logger.info("✅ Workflow complete!")
            return result

        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            raise

    def _perform_transcription(self, audio_path: str, method: str, api_key: Optional[str] = None) -> Dict:
        """
        Perform audio transcription using the specified method.

        Args:
            audio_path (str): Path to audio file
            method (str): 'api' or 'local'
            api_key (str, optional): OpenAI API key for API method

        Returns:
            Dict: Transcription result with segments and text
        """
        try:
            # Initialize transcriber if needed
            if self.transcriber is None:
                self.transcriber = Transcriber(
                    api_key=api_key,
                    method='api' if method == 'api' else 'local'
                )

            logger.info("🎙️ Calling transcription API...")
            # Perform transcription
            result = self.transcriber.transcribe_audio(
                audio_path=audio_path,
                language='en',
                response_format='verbose_json'
            )

            logger.info(f"✅ Transcription successful: {len(result.get('segments', []))} segments")
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            if method == 'api':
                logger.info("💡 Tip: Check your OpenAI API key or try 'demo' mode")
            raise

    def _create_demo_transcript(self) -> Dict:
        """Create a realistic demo transcript for testing without API calls."""
        return {
            "text": "So, um, today we're going to talk about, uh, the new features in our product. "
                   "You know, like, the thing is, we've been working really hard on this. "
                   "Uh, basically, what we've done is, um, we've improved the user interface. "
                   "And, like, the performance is, you know, much better now. "
                   "So, uh, let me show you the first feature. "
                   "Um, this is the new dashboard, and, uh, it's really intuitive. "
                   "You know, users can now, like, access everything from one place. "
                   "Uh, the second thing is, um, we've added real-time collaboration. "
                   "So, like, multiple people can work on the same project simultaneously. "
                   "And, uh, finally, we've improved the search functionality. "
                   "It's, you know, much faster and more accurate now.",
            "segments": [
                {"id": 0, "start": 0.0, "end": 2.5, "text": "So, um, today we're going to talk about,"},
                {"id": 1, "start": 2.5, "end": 5.0, "text": " uh, the new features in our product."},
                {"id": 2, "start": 5.0, "end": 6.5, "text": " You know, like, the thing is,"},
                {"id": 3, "start": 6.5, "end": 9.0, "text": " we've been working really hard on this."},
                {"id": 4, "start": 9.0, "end": 11.0, "text": " Uh, basically, what we've done is,"},
                {"id": 5, "start": 11.0, "end": 13.5, "text": " um, we've improved the user interface."},
                {"id": 6, "start": 13.5, "end": 14.5, "text": " And, like,"},
                {"id": 7, "start": 14.5, "end": 17.0, "text": " the performance is, you know, much better now."},
                {"id": 8, "start": 17.0, "end": 19.5, "text": " So, uh, let me show you the first feature."},
                {"id": 9, "start": 19.5, "end": 21.0, "text": " Um, this is the new dashboard,"},
                {"id": 10, "start": 21.0, "end": 23.5, "text": " and, uh, it's really intuitive."},
                {"id": 11, "start": 23.5, "end": 24.5, "text": " You know,"},
                {"id": 12, "start": 24.5, "end": 27.0, "text": " users can now, like, access everything from one place."},
                {"id": 13, "start": 27.0, "end": 28.5, "text": " Uh, the second thing is,"},
                {"id": 14, "start": 28.5, "end": 31.0, "text": " um, we've added real-time collaboration."},
                {"id": 15, "start": 31.0, "end": 31.5, "text": " So, like,"},
                {"id": 16, "start": 31.5, "end": 35.0, "text": " multiple people can work on the same project simultaneously."},
                {"id": 17, "start": 35.0, "end": 36.0, "text": " And, uh,"},
                {"id": 18, "start": 36.0, "end": 38.5, "text": " finally, we've improved the search functionality."},
                {"id": 19, "start": 38.5, "end": 39.5, "text": " It's, you know,"},
                {"id": 20, "start": 39.5, "end": 42.0, "text": " much faster and more accurate now."}
            ],
            "language": "en",
            "duration": 42.0
        }

    def _create_dummy_audio_file(self) -> str:
        """Create a dummy audio file for demo purposes."""
        dummy_path = self.temp_dir / "dummy_audio.wav"
        # Create an empty file
        dummy_path.touch()
        return str(dummy_path)

def demo_workflow():
    """Run a demonstration of the complete workflow."""
    print("\n" + "=" * 50)
    print("🎬 MULTICAM AUTO-CUT WORKFLOW DEMO")
    print("=" * 50)

    # Create a sample FCPXML for testing
    sample_fcpxml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
    <resources>
        <format id="r1" name="FFVideoFormat1080p2997" frameDuration="1001/30000s" width="1920" height="1080"/>
        <asset id="r2" name="Camera_1" uid="ABC123" start="0s" duration="300s" hasVideo="1" hasAudio="1" format="r1" audioSources="1" audioChannels="2" audioRate="48000">
            <media-rep kind="original-media" sig="ABC123" src="file:///Camera1.mov"/>
        </asset>
        <asset id="r3" name="Lav_Mic" uid="DEF456" start="0s" duration="300s" hasAudio="1" audioSources="1" audioChannels="1" audioRate="48000">
            <media-rep kind="original-media" sig="DEF456" src="file:///LavMic.wav"/>
        </asset>
        <mc-clip id="r4" name="Interview_Multicam" uid="GHI789">
            <mc-angle name="Camera 1" angleID="1">
                <asset-clip ref="r2" name="Camera_1" offset="0s" start="0s" duration="300s" audioRole="dialogue.dialogue-1"/>
            </mc-angle>
            <mc-angle name="Lav Audio" angleID="2">
                <asset-clip ref="r3" name="Lav_Mic" offset="0s" start="0s" duration="300s" audioRole="dialogue.dialogue-1"/>
            </mc-angle>
        </mc-clip>
    </resources>
    <project name="Demo Project">
        <sequence format="r1" duration="300s" tcStart="0s" audioLayout="stereo" audioRate="48k">
            <spine>
                <mc-clip ref="r4" offset="0s" name="Interview_Multicam" start="0s" duration="300s"/>
            </spine>
        </sequence>
    </project>
</fcpxml>"""

    # Save sample FCPXML in a temp directory
    demo_dir = Path("outputs/demo")
    demo_dir.mkdir(parents=True, exist_ok=True)
    input_file = str(demo_dir / "demo_input.fcpxml")
    output_file = str(demo_dir / "demo_output_cut.fcpxml")

    with open(input_file, 'w') as f:
        f.write(sample_fcpxml)

    # Initialize workflow
    workflow = MulticamAutoCutWorkflow(
        temp_dir="./temp",
        cleaning_level='moderate'
    )

    # Process the sample
    result = workflow.process_multicam_clip(
        input_fcpxml=input_file,
        output_fcpxml=output_file,
        transcription_method='demo',  # Use demo mode - no API needed
        keep_temp_files=False
    )

    # Display results
    if result['success']:
        print("\n✅ DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print(f"📊 Results:")
        print(f"   Original Duration: {result['original_duration']:.1f} seconds")
        print(f"   Final Duration: {result['final_duration']:.1f} seconds")
        print(f"   Time Saved: {result['time_saved']:.1f} seconds ({result['time_saved_percentage']:.1f}%)")
        print(f"   Segments Removed: {result['segments_removed']}")
        print(f"   Take Groups: {result['take_groups_found']}")
        print(f"   Output File: {result['output_file']}")
        print("\n📝 Next Steps:")
        print("1. Import the generated FCPXML into Final Cut Pro")
        print("2. Review the automatic cuts")
        print("3. Fine-tune as needed")
        print("=" * 50 + "\n")

    # Cleanup demo files
    try:
        os.remove(input_file)
        print("Demo files cleaned up.")
    except:
        pass

    return result

def display_workflow_info():
    """Display information about the workflow system."""
    print("\n🎬 MULTICAM AUTO-CUT SYSTEM")
    print("=" * 50)
    print("\n📋 WORKFLOW STEPS:")
    print("1. Parse FCPXML to extract multicam structure")
    print("2. Extract mono audio track (lav mic)")
    print("3. Transcribe audio using OpenAI Whisper")
    print("4. Clean transcript (remove filler words)")
    print("5. Generate cut points and create new FCPXML")
    print("6. Output ready for Final Cut Pro import")
    print("\n✨ FEATURES:")
    print("• Supports 29.97 DF, 24p, 25p, and mixed frame rates")
    print("• Intelligent filler word removal")
    print("• Preserves natural speech patterns")
    print("• Take detection for multiple attempts")
    print("• Frame-accurate cutting")
    print("\n🔧 CLEANING LEVELS:")
    print("• Light: Minimal cleaning, preserves most speech")
    print("• Moderate: Balanced approach (recommended)")
    print("• Aggressive: Maximum filler removal")
    print("\n⚙️  REQUIREMENTS:")
    print("• Python 3.7+")
    print("• OpenAI API key (for transcription)")
    print("• Final Cut Pro X (for import/export)")
    print("=" * 50 + "\n")

def main():
    """Main entry point with command-line argument support."""
    parser = argparse.ArgumentParser(
        description="Multicam Auto-Cut System - Automatically cut multicam clips based on transcription",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a file with default settings
  python workflow.py input.fcpxml

  # Force re-transcription
  python workflow.py input.fcpxml --force-retranscribe

  # Use aggressive cleaning and keep temp files
  python workflow.py input.fcpxml -c aggressive --keep-temp

  # Run demo mode
  python workflow.py --demo
        """
    )

    parser.add_argument('input_file', nargs='?', help='Input FCPXML file path')
    parser.add_argument('-o', '--output', help='Output FCPXML file path (default: input_cut.fcpxml)')
    parser.add_argument('-c', '--cleaning-level', choices=['light', 'moderate', 'aggressive'],
                      default='moderate', help='Transcript cleaning level (default: moderate)')
    parser.add_argument('-m', '--method', choices=['api', 'local', 'demo'],
                      default='api', help='Transcription method (default: api)')
    parser.add_argument('--api-key', help='OpenAI API key (otherwise uses OPENAI_API_KEY env var)')
    parser.add_argument('--temp-dir', default='./temp', help='Temporary files directory')
    parser.add_argument('--transcript-dir', default='./transcripts', help='Transcript cache directory')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files after processing')
    parser.add_argument('--no-cache', action='store_true', help='Disable transcript caching')
    parser.add_argument('--force-retranscribe', action='store_true', help='Force re-transcription even if cached')
    parser.add_argument('--demo', action='store_true', help='Run demo mode with sample file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    print("\n🎬 MULTICAM AUTO-CUT SYSTEM")
    print("=" * 40)

    # Run demo mode if requested
    if args.demo:
        print("Running in demo mode...\n")
        demo_workflow()
        return 0

    # Check for input file
    if not args.input_file:
        parser.print_help()
        print("\n❌ Error: Input file required (or use --demo for demo mode)")
        return 1

    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"\n❌ Error: Input file not found: {args.input_file}")
        return 1

    # Determine output file with improved naming and directory structure
    if args.output:
        output_file = args.output
    else:
        # Create output directory structure outside of FCPXML packages
        input_path = Path(args.input_file)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = input_path.stem

        # Create outputs directory at project root if it doesn't exist
        outputs_dir = Path("outputs") / timestamp
        outputs_dir.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        output_file = str(outputs_dir / f"{base_name}_AutoCut.fcpxml")

        # Also save the input filename reference for user convenience
        with open(outputs_dir / "source_info.txt", "w") as f:
            f.write(f"Source file: {args.input_file}\n")
            f.write(f"Processed at: {datetime.now().isoformat()}\n")
            f.write(f"Cleaning level: {args.cleaning_level}\n")

    print(f"📄 Input:  {args.input_file}")
    print(f"📄 Output: {output_file}")
    print(f"🧹 Cleaning Level: {args.cleaning_level}")
    print(f"🎙️ Transcription Method: {args.method}")
    print(f"💾 Transcript Caching: {'Disabled' if args.no_cache else 'Enabled'}")
    if not args.no_cache and args.force_retranscribe:
        print(f"🔄 Force Re-transcribe: Yes")
    print()

    # Initialize workflow
    workflow = MulticamAutoCutWorkflow(
        temp_dir=args.temp_dir,
        cleaning_level=args.cleaning_level,
        transcript_cache_dir=args.transcript_dir
    )

    # Process the file
    try:
        result = workflow.process_multicam_clip(
            input_fcpxml=args.input_file,
            output_fcpxml=output_file,
            transcription_method=args.method,
            api_key=args.api_key,
            keep_temp_files=args.keep_temp,
            use_cached_transcript=not args.no_cache,
            force_retranscribe=args.force_retranscribe
        )

        print("\n✅ Processing complete!")
        print(f"📄 Output saved to: {output_file}")
        print("\n📝 Next Steps:")
        print("1. Open Final Cut Pro")
        print("2. Import the generated FCPXML file")
        print("3. A new timeline with your pre-cut multicam clip will be created")
        print("4. All cuts are already applied - ready for review")
        print("5. Fine-tune the edits as needed\n")
        print("✨ The new timeline preserves all your cuts while keeping the original intact!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Processing failed")
        return 1

    return 0

def create_sample_fcpxml_for_testing(output_path: str = "test_multicam.fcpxml"):
    """Create a comprehensive sample FCPXML file for testing."""
    sample_fcpxml = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
    <resources>
        <format id="r1" name="FFVideoFormat1080p2997DF" frameDuration="1001/30000s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>

        <!-- Camera 1 - Wide shot -->
        <asset id="r2" name="Camera_1_Wide_Shot" uid="12345-ABCD-6789" start="0s" duration="300s"
               hasVideo="1" hasAudio="1" format="r1" videoSources="1" audioSources="1" audioChannels="2" audioRate="48000">
            <media-rep kind="original-media" sig="12345-ABCD-6789" src="file:///Users/VideoProjects/Interview/Camera_1_Wide_Shot.mov"/>
        </asset>

        <!-- Camera 2 - Close-up -->
        <asset id="r3" name="Camera_2_Close_Up" uid="23456-BCDE-7890" start="0s" duration="300s"
               hasVideo="1" hasAudio="1" format="r1" videoSources="1" audioSources="1" audioChannels="2" audioRate="48000">
            <media-rep kind="original-media" sig="23456-BCDE-7890" src="file:///Users/VideoProjects/Interview/Camera_2_Close_Up.mov"/>
        </asset>

        <!-- Lav microphone - mono audio -->
        <asset id="r4" name="Interview_Lav_Mic" uid="34567-CDEF-8901" start="0s" duration="300s"
               hasAudio="1" audioSources="1" audioChannels="1" audioRate="48000">
            <media-rep kind="original-media" sig="34567-CDEF-8901" src="file:///Users/VideoProjects/Interview/Interview_Lav_Mic.wav"/>
        </asset>

        <!-- Multicam clip combining all angles -->
        <mc-clip id="r5" name="Interview_Multicam_29.97DF" uid="45678-DEFG-9012" start="0s" duration="300s" format="r1">
            <mc-angle name="Wide Shot" angleID="1">
                <asset-clip ref="r2" name="Camera_1_Wide_Shot" offset="0s" start="0s" duration="300s"/>
            </mc-angle>
            <mc-angle name="Close Up" angleID="2">
                <asset-clip ref="r3" name="Camera_2_Close_Up" offset="0s" start="0s" duration="300s"/>
            </mc-angle>
            <mc-angle name="Lav Audio" angleID="3">
                <asset-clip ref="r4" name="Interview_Lav_Mic" offset="0s" start="0s" duration="300s"/>
            </mc-angle>
        </mc-clip>
    </resources>

    <project name="Interview Project - 29.97 Drop Frame" uid="56789-EFGH-0123" modDate="2025-01-15 10:00:00 -0800">
        <sequence format="r1" duration="300s" tcStart="3600s" tcFormat="DF" audioLayout="stereo" audioRate="48k">
            <spine>
                <!-- The multicam clip in the timeline with 29.97 DF -->
                <mc-clip ref="r5" offset="3600s" name="Interview_Multicam_29.97DF" start="0s" duration="300s"/>
            </spine>
        </sequence>
    </project>
</fcpxml>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sample_fcpxml)

    logger.info(f"Sample FCPXML created: {output_path}")
    return output_path

def run_complete_workflow_demo():
    """Run a complete demonstration of the workflow."""
    print("🎬 MULTICAM AUTO-CUT SYSTEM DEMO")
    print("=" * 40)

    # Create sample input file
    sample_input = create_sample_fcpxml_for_testing("demo_input.fcpxml")
    sample_output = "demo_output_cut.fcpxml"

    # Initialize workflow
    workflow = MulticamAutoCutWorkflow(
        temp_dir="./demo_temp",
        cleaning_level='moderate'
    )

    # Process the sample file
    result = workflow.process_multicam_clip(
        input_fcpxml=sample_input,
        output_fcpxml=sample_output,
        transcription_method='demo',  # Use demo mode
        keep_temp_files=True
    )

    # Cleanup demo files
    try:
        os.remove(sample_input)
        logger.info("Demo input file cleaned up")
    except:
        pass

    return result

if __name__ == "__main__":
    sys.exit(main() or 0)