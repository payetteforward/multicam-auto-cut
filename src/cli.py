#!/usr/bin/env python3
"""
Command Line Interface for the Multicam Auto-Cut System.
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppSettings
from src.core import MulticamAutoCutWorkflow
from src.utils.logging_config import setup_logging


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-powered Final Cut Pro workflow automation for cutting multicam clips.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.fcpxml                    # Process with default settings
  %(prog)s input.fcpxml -o custom_output   # Custom output directory
  %(prog)s input.fcpxml --no-edit          # Skip AI transcript editing
  %(prog)s input.fcpxml --cleaning light   # Use light cleaning level
        """,
    )

    # Required arguments
    parser.add_argument(
        "input_fcpxml",
        type=str,
        help="Path to input FCPXML file",
    )

    # Optional arguments
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: outputs/timestamp)",
    )

    parser.add_argument(
        "--cleaning",
        type=str,
        choices=["light", "moderate", "aggressive"],
        default="moderate",
        help="Transcript cleaning level (default: moderate)",
    )

    parser.add_argument(
        "--profile",
        type=str,
        choices=["scripted", "tutorial", "rough", "podcast", "aggressive"],
        default="tutorial",
        help="Editing profile: scripted (minimal), tutorial (balanced), rough (more cuts), podcast (conversational), aggressive (maximum cuts)",
    )

    parser.add_argument(
        "--no-edit",
        action="store_true",
        help="Skip AI transcript editing with Claude",
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't use cached transcripts",
    )

    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary files after processing",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Load settings from environment
        settings = AppSettings.from_env()

        # Override with CLI arguments
        if args.cleaning:
            settings.cleaning_level = args.cleaning
        if args.no_edit:
            settings.edit_transcript = False
        if args.no_cache:
            settings.use_transcript_cache = False
        if args.keep_temp:
            settings.keep_temp_files = True
        if args.verbose:
            settings.verbose_logging = True

        # Validate settings
        settings.validate()

        # Initialize workflow
        workflow = MulticamAutoCutWorkflow(
            temp_dir=str(settings.temp_dir),
            cleaning_level=settings.cleaning_level,
            transcript_cache_dir=str(settings.transcript_cache_dir),
            edit_transcript=settings.edit_transcript,
            editing_profile=args.profile,
        )

        # Determine output path
        if args.output:
            output_dir = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = settings.output_dir / timestamp

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        input_path = Path(args.input_fcpxml)
        base_name = input_path.stem
        output_file = output_dir / f"{base_name}_AutoCut.fcpxml"

        print("\n🎬 MULTICAM AUTO-CUT SYSTEM")
        print("=" * 40)
        print(f"📄 Input:  {args.input_fcpxml}")
        print(f"📄 Output: {output_file}")
        print(f"🧹 Cleaning Level: {settings.cleaning_level}")
        print(f"✏️  Edit Transcript: {'Yes' if settings.edit_transcript else 'No'}")
        if settings.edit_transcript:
            print(f"📝 Editing Profile: {args.profile}")
        print(f"💾 Use Cache: {'Yes' if settings.use_transcript_cache else 'No'}")
        print()

        # Process the multicam clip
        result = workflow.process_multicam_clip(
            input_fcpxml=args.input_fcpxml,
            output_fcpxml=str(output_file),
            use_cached_transcript=settings.use_transcript_cache,
            keep_temp_files=settings.keep_temp_files,
        )

        if result["success"]:
            print("\n✅ Processing complete!")
            print(f"📄 Output saved to: {result['output_file']}")
            print(f"⏱️  Original: {result['original_duration']:.1f}s")
            print(f"⏱️  Final: {result['final_duration']:.1f}s")
            print(f"💾 Saved: {result['time_saved']:.1f}s ({result['time_saved_percentage']:.1f}%)")
            print("\n📝 Next Steps:")
            print("1. Open Final Cut Pro")
            print("2. Import the generated FCPXML file")
            print("3. Review and fine-tune the edits as needed")
            return 0
        else:
            logger.error("Processing failed")
            return 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())