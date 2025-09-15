#!/usr/bin/env python3
"""
FCPXML Validator and Statistics Tool
Validates Final Cut Pro XML files and provides detailed statistics about the content.
"""

import xml.etree.ElementTree as ET
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import timedelta
from collections import defaultdict
import re

class FCPXMLValidator:
    """Validates and analyzes FCPXML files."""

    def __init__(self, verbose: bool = False):
        """
        Initialize the validator.

        Args:
            verbose: Whether to print verbose output
        """
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        self.stats = {}
        self.tree = None
        self.root = None

    def validate_file(self, file_path: str) -> Tuple[bool, Dict]:
        """
        Validate an FCPXML file and gather statistics.

        Args:
            file_path: Path to the FCPXML file

        Returns:
            Tuple of (is_valid, statistics_dict)
        """
        self.errors = []
        self.warnings = []
        self.stats = {
            'file_info': {},
            'structure': {},
            'resources': {},
            'timeline': {},
            'media': {},
            'effects': {},
            'frame_rates': {},
            'audio': {},
            'validation': {}
        }

        try:
            # Parse XML
            self.tree = ET.parse(file_path)
            self.root = self.tree.getroot()

            # Basic file info
            self.stats['file_info'] = {
                'path': str(Path(file_path).absolute()),
                'size_bytes': Path(file_path).stat().st_size,
                'size_mb': round(Path(file_path).stat().st_size / (1024 * 1024), 2)
            }

            # Validate structure
            self._validate_root()
            self._validate_version()
            self._validate_resources()
            self._validate_projects()
            self._validate_media_references()
            self._validate_timecode()
            self._validate_frame_rates()

            # Gather statistics
            self._gather_resource_stats()
            self._gather_timeline_stats()
            self._gather_media_stats()
            self._gather_effect_stats()
            self._gather_audio_stats()

            # Compile validation results
            self.stats['validation'] = {
                'valid': len(self.errors) == 0,
                'errors': self.errors,
                'warnings': self.warnings,
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }

            return len(self.errors) == 0, self.stats

        except ET.ParseError as e:
            self.errors.append(f"XML Parse Error: {e}")
            self.stats['validation'] = {
                'valid': False,
                'errors': self.errors,
                'warnings': self.warnings,
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }
            return False, self.stats
        except Exception as e:
            self.errors.append(f"Unexpected error: {e}")
            self.stats['validation'] = {
                'valid': False,
                'errors': self.errors,
                'warnings': self.warnings,
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }
            return False, self.stats

    def _validate_root(self):
        """Validate root element."""
        if self.root.tag != 'fcpxml':
            self.errors.append(f"Root element must be 'fcpxml', found '{self.root.tag}'")

        # Check for required version attribute
        version = self.root.get('version')
        if not version:
            self.errors.append("Missing 'version' attribute in fcpxml element")
        else:
            self.stats['structure']['fcpxml_version'] = version

    def _validate_version(self):
        """Validate FCPXML version."""
        version = self.root.get('version')
        if version:
            try:
                major, minor = version.split('.')
                major, minor = int(major), int(minor)
                if major != 1 or minor < 0 or minor > 11:
                    self.warnings.append(f"Unusual FCPXML version: {version}")
            except:
                self.errors.append(f"Invalid version format: {version}")

    def _validate_resources(self):
        """Validate resources section."""
        resources = self.root.find('resources')
        if resources is None:
            # Resources are optional but commonly present
            self.warnings.append("No resources section found")
            return

        # Check for formats
        formats = resources.findall('format')
        if not formats:
            self.warnings.append("No format definitions found in resources")

        # Validate each format
        for fmt in formats:
            fmt_id = fmt.get('id')
            if not fmt_id:
                self.errors.append("Format element missing 'id' attribute")

            frame_duration = fmt.get('frameDuration')
            if frame_duration:
                if not self._validate_time_value(frame_duration):
                    self.errors.append(f"Invalid frameDuration: {frame_duration}")

    def _validate_projects(self):
        """Validate project structure."""
        projects = self.root.findall('.//project')
        events = self.root.findall('.//event')

        if not projects and not events:
            self.errors.append("No project or event elements found")
            return

        # Validate each project
        for project in projects:
            name = project.get('name')
            if not name:
                self.warnings.append("Project missing 'name' attribute")

            # Check for sequences
            sequences = project.findall('.//sequence')
            if not sequences:
                self.warnings.append(f"Project '{name}' has no sequences")

    def _validate_media_references(self):
        """Validate media file references."""
        media_reps = self.root.findall('.//media-rep')

        for media in media_reps:
            src = media.get('src')
            if not src:
                self.errors.append("media-rep element missing 'src' attribute")
            elif not (src.startswith('file://') or src.startswith('http')):
                self.warnings.append(f"Unusual media source format: {src}")

    def _validate_timecode(self):
        """Validate timecode values."""
        # Check sequence timecodes
        sequences = self.root.findall('.//sequence')

        for seq in sequences:
            tc_start = seq.get('tcStart')
            if tc_start and not self._validate_time_value(tc_start):
                self.errors.append(f"Invalid tcStart value: {tc_start}")

            tc_format = seq.get('tcFormat')
            if tc_format and tc_format not in ['NDF', 'DF']:
                self.warnings.append(f"Unusual tcFormat: {tc_format}")

    def _validate_frame_rates(self):
        """Validate and check for mixed frame rates."""
        formats = self.root.findall('.//format')
        frame_rates = set()

        for fmt in formats:
            frame_duration = fmt.get('frameDuration')
            if frame_duration:
                # Parse frame duration (e.g., "1001/30000s")
                match = re.match(r'(\d+)/(\d+)s', frame_duration)
                if match:
                    num, den = int(match.group(1)), int(match.group(2))
                    fps = den / num
                    frame_rates.add(round(fps, 2))

        if len(frame_rates) > 1:
            self.warnings.append(f"Mixed frame rates detected: {sorted(frame_rates)}")

        self.stats['frame_rates']['detected_rates'] = list(frame_rates)
        self.stats['frame_rates']['mixed_rates'] = len(frame_rates) > 1

    def _validate_time_value(self, time_str: str) -> bool:
        """
        Validate a time value string.

        Args:
            time_str: Time string (e.g., "0s", "1001/30000s")

        Returns:
            bool: True if valid
        """
        # Simple validation for common formats
        if time_str.endswith('s'):
            time_part = time_str[:-1]

            # Check for fraction format (e.g., "1001/30000")
            if '/' in time_part:
                parts = time_part.split('/')
                if len(parts) == 2:
                    try:
                        num, den = int(parts[0]), int(parts[1])
                        return den != 0
                    except:
                        return False
            else:
                # Check for simple number
                try:
                    float(time_part)
                    return True
                except:
                    return False
        return False

    def _gather_resource_stats(self):
        """Gather statistics about resources."""
        resources = self.root.find('resources')
        if not resources:
            return

        stats = {
            'formats': len(resources.findall('format')),
            'assets': len(resources.findall('asset')),
            'effects': len(resources.findall('effect')),
            'media': len(resources.findall('media')),
            'multicam_clips': len(resources.findall('mc-clip')) + len(self.root.findall('.//mc-clip'))
        }

        # Asset details
        assets = resources.findall('asset')
        video_assets = 0
        audio_assets = 0

        for asset in assets:
            if asset.get('hasVideo') == '1':
                video_assets += 1
            if asset.get('hasAudio') == '1':
                audio_assets += 1

        stats['video_assets'] = video_assets
        stats['audio_assets'] = audio_assets

        self.stats['resources'] = stats

    def _gather_timeline_stats(self):
        """Gather timeline statistics."""
        sequences = self.root.findall('.//sequence')
        projects = self.root.findall('.//project')
        events = self.root.findall('.//event')

        timeline_stats = {
            'projects': len(projects),
            'events': len(events),
            'sequences': len(sequences),
            'total_duration': 0,
            'clips': 0,
            'gaps': 0,
            'transitions': 0,
            'markers': 0
        }

        # Count various timeline elements
        timeline_stats['clips'] = len(self.root.findall('.//clip')) + \
                                  len(self.root.findall('.//asset-clip')) + \
                                  len(self.root.findall('.//mc-clip')) + \
                                  len(self.root.findall('.//ref-clip')) + \
                                  len(self.root.findall('.//sync-clip')) + \
                                  len(self.root.findall('.//audition'))

        timeline_stats['gaps'] = len(self.root.findall('.//gap'))
        timeline_stats['transitions'] = len(self.root.findall('.//transition'))
        timeline_stats['markers'] = len(self.root.findall('.//marker'))

        # Calculate total duration
        for seq in sequences:
            duration = seq.get('duration')
            if duration:
                timeline_stats['total_duration'] += self._parse_time_to_seconds(duration)

        self.stats['timeline'] = timeline_stats

    def _gather_media_stats(self):
        """Gather media file statistics."""
        media_stats = {
            'total_files': 0,
            'file_types': defaultdict(int),
            'missing_files': [],
            'online_files': 0,
            'offline_files': 0
        }

        # Find all media references
        media_reps = self.root.findall('.//media-rep')

        for media in media_reps:
            src = media.get('src')
            if src:
                media_stats['total_files'] += 1

                # Extract file extension
                if src.startswith('file://'):
                    path = src[7:]  # Remove 'file://'
                    ext = Path(path).suffix.lower()
                    if ext:
                        media_stats['file_types'][ext] += 1

                    # Check if file exists (for local files)
                    if not Path(path).exists():
                        media_stats['missing_files'].append(path)
                        media_stats['offline_files'] += 1
                    else:
                        media_stats['online_files'] += 1

        media_stats['file_types'] = dict(media_stats['file_types'])
        self.stats['media'] = media_stats

    def _gather_effect_stats(self):
        """Gather effects and filters statistics."""
        effect_stats = {
            'video_filters': 0,
            'audio_filters': 0,
            'transitions': 0,
            'generators': 0,
            'titles': 0,
            'effect_names': []
        }

        # Video filters
        video_filters = self.root.findall('.//filter-video')
        effect_stats['video_filters'] = len(video_filters)

        # Audio filters
        audio_filters = self.root.findall('.//filter-audio')
        effect_stats['audio_filters'] = len(audio_filters)

        # Transitions
        transitions = self.root.findall('.//transition')
        effect_stats['transitions'] = len(transitions)

        # Titles
        titles = self.root.findall('.//title')
        effect_stats['titles'] = len(titles)

        # Collect effect names
        for elem in video_filters + audio_filters:
            name = elem.get('name')
            if name and name not in effect_stats['effect_names']:
                effect_stats['effect_names'].append(name)

        self.stats['effects'] = effect_stats

    def _gather_audio_stats(self):
        """Gather audio-specific statistics."""
        audio_stats = {
            'audio_channels': set(),
            'audio_rates': set(),
            'audio_roles': set(),
            'mono_tracks': 0,
            'stereo_tracks': 0,
            'surround_tracks': 0
        }

        # Find all audio assets
        assets = self.root.findall('.//asset[@hasAudio="1"]')

        for asset in assets:
            # Audio channels
            channels = asset.get('audioChannels')
            if channels:
                ch_count = int(channels)
                audio_stats['audio_channels'].add(ch_count)

                if ch_count == 1:
                    audio_stats['mono_tracks'] += 1
                elif ch_count == 2:
                    audio_stats['stereo_tracks'] += 1
                elif ch_count > 2:
                    audio_stats['surround_tracks'] += 1

            # Audio rate
            rate = asset.get('audioRate')
            if rate:
                audio_stats['audio_rates'].add(int(rate))

        # Find audio roles
        for elem in self.root.findall('.//*[@audioRole]'):
            role = elem.get('audioRole')
            if role:
                audio_stats['audio_roles'].add(role)

        # Convert sets to lists for JSON serialization
        audio_stats['audio_channels'] = list(audio_stats['audio_channels'])
        audio_stats['audio_rates'] = list(audio_stats['audio_rates'])
        audio_stats['audio_roles'] = list(audio_stats['audio_roles'])

        self.stats['audio'] = audio_stats

    def _parse_time_to_seconds(self, time_str: str) -> float:
        """
        Parse FCPXML time string to seconds.

        Args:
            time_str: Time string (e.g., "300s", "1001/30000s")

        Returns:
            float: Time in seconds
        """
        if not time_str.endswith('s'):
            return 0

        time_part = time_str[:-1]

        if '/' in time_part:
            # Fraction format
            parts = time_part.split('/')
            if len(parts) == 2:
                try:
                    return float(parts[0]) / float(parts[1])
                except:
                    return 0
        else:
            # Simple number
            try:
                return float(time_part)
            except:
                return 0

    def print_report(self, stats: Dict):
        """
        Print a formatted report of the validation results.

        Args:
            stats: Statistics dictionary
        """
        print("\n" + "=" * 60)
        print("FCPXML VALIDATION REPORT")
        print("=" * 60)

        # File Info
        print("\n📄 FILE INFORMATION:")
        if 'file_info' in stats:
            if 'path' in stats['file_info']:
                print(f"   Path: {stats['file_info']['path']}")
            if 'size_mb' in stats['file_info']:
                print(f"   Size: {stats['file_info']['size_mb']} MB")
        if 'structure' in stats and 'fcpxml_version' in stats['structure']:
            print(f"   Version: {stats['structure']['fcpxml_version']}")

        # Validation Status
        validation = stats.get('validation', {})
        if validation.get('valid'):
            print("\n✅ VALIDATION: PASSED")
        else:
            print("\n❌ VALIDATION: FAILED")

        if validation.get('error_count', 0) > 0:
            print(f"\n🔴 Errors ({validation['error_count']}):")
            for error in validation.get('errors', [])[:10]:  # Show first 10
                print(f"   • {error}")
            if validation['error_count'] > 10:
                print(f"   ... and {validation['error_count'] - 10} more errors")

        if validation.get('warning_count', 0) > 0:
            print(f"\n🟡 Warnings ({validation['warning_count']}):")
            for warning in validation.get('warnings', [])[:10]:  # Show first 10
                print(f"   • {warning}")
            if validation['warning_count'] > 10:
                print(f"   ... and {validation['warning_count'] - 10} more warnings")

        # Resources
        if 'resources' in stats:
            res = stats['resources']
            print("\n📦 RESOURCES:")
            print(f"   Formats: {res.get('formats', 0)}")
            print(f"   Assets: {res.get('assets', 0)} ({res.get('video_assets', 0)} video, {res.get('audio_assets', 0)} audio)")
            print(f"   Multicam Clips: {res.get('multicam_clips', 0)}")

        # Timeline
        if 'timeline' in stats:
            tl = stats['timeline']
            print("\n⏱️ TIMELINE:")
            print(f"   Projects: {tl.get('projects', 0)}")
            print(f"   Sequences: {tl.get('sequences', 0)}")
            print(f"   Total Clips: {tl.get('clips', 0)}")
            print(f"   Gaps: {tl.get('gaps', 0)}")
            print(f"   Transitions: {tl.get('transitions', 0)}")
            print(f"   Markers: {tl.get('markers', 0)}")
            if tl.get('total_duration', 0) > 0:
                duration = tl['total_duration']
                print(f"   Total Duration: {self._format_duration(duration)}")

        # Frame Rates
        if 'frame_rates' in stats:
            fr = stats['frame_rates']
            if fr.get('detected_rates'):
                print("\n🎬 FRAME RATES:")
                for rate in fr['detected_rates']:
                    print(f"   • {rate} fps")
                if fr.get('mixed_rates'):
                    print("   ⚠️  Mixed frame rates detected!")

        # Media
        if 'media' in stats:
            media = stats['media']
            print("\n🎞️ MEDIA FILES:")
            print(f"   Total Files: {media.get('total_files', 0)}")
            print(f"   Online: {media.get('online_files', 0)}")
            print(f"   Offline: {media.get('offline_files', 0)}")
            if media.get('file_types'):
                print("   File Types:")
                for ext, count in media['file_types'].items():
                    print(f"      • {ext}: {count}")
            if media.get('missing_files'):
                print(f"   ⚠️  Missing Files: {len(media['missing_files'])}")

        # Audio
        if 'audio' in stats:
            audio = stats['audio']
            print("\n🔊 AUDIO:")
            print(f"   Mono Tracks: {audio.get('mono_tracks', 0)}")
            print(f"   Stereo Tracks: {audio.get('stereo_tracks', 0)}")
            print(f"   Surround Tracks: {audio.get('surround_tracks', 0)}")
            if audio.get('audio_rates'):
                print(f"   Sample Rates: {', '.join(str(r) for r in audio['audio_rates'])} Hz")
            if audio.get('audio_roles'):
                print(f"   Audio Roles: {len(audio['audio_roles'])}")

        # Effects
        if 'effects' in stats:
            fx = stats['effects']
            total_effects = fx.get('video_filters', 0) + fx.get('audio_filters', 0)
            if total_effects > 0:
                print("\n✨ EFFECTS:")
                print(f"   Video Filters: {fx.get('video_filters', 0)}")
                print(f"   Audio Filters: {fx.get('audio_filters', 0)}")
                print(f"   Transitions: {fx.get('transitions', 0)}")
                print(f"   Titles: {fx.get('titles', 0)}")

        print("\n" + "=" * 60)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to readable string."""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        seconds = td.seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

def main():
    """Main entry point for the validator."""
    parser = argparse.ArgumentParser(
        description="FCPXML Validator - Validate and analyze Final Cut Pro XML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a file and show report
  python fcpxml_validator.py input.fcpxml

  # Save statistics to JSON
  python fcpxml_validator.py input.fcpxml --json stats.json

  # Verbose output
  python fcpxml_validator.py input.fcpxml -v

  # Quick validation only
  python fcpxml_validator.py input.fcpxml --quick
        """
    )

    parser.add_argument('input_file', help='FCPXML file to validate')
    parser.add_argument('--json', help='Save statistics to JSON file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--quick', action='store_true', help='Quick validation only (no detailed stats)')

    args = parser.parse_args()

    # Check if file exists
    if not Path(args.input_file).exists():
        print(f"❌ Error: File not found: {args.input_file}")
        return 1

    # Create validator
    validator = FCPXMLValidator(verbose=args.verbose)

    print(f"\n🔍 Validating: {args.input_file}")

    # Validate file
    is_valid, stats = validator.validate_file(args.input_file)

    # Print report
    if not args.quick:
        validator.print_report(stats)
    else:
        # Quick validation output
        if is_valid:
            print("✅ VALID FCPXML")
        else:
            print("❌ INVALID FCPXML")
            for error in stats['validation']['errors'][:5]:
                print(f"   • {error}")

    # Save JSON if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"\n📊 Statistics saved to: {args.json}")

    return 0 if is_valid else 1

if __name__ == "__main__":
    sys.exit(main())