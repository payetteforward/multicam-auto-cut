#!/usr/bin/env python3
"""Analyze the differences between AI-generated cuts and manual edits."""

import xml.etree.ElementTree as ET
import re
from pathlib import Path

def extract_mc_clips(fcpxml_path):
    """Extract all multicam clip information from FCPXML."""
    tree = ET.parse(fcpxml_path)
    root = tree.getroot()

    clips = []

    # Find all mc-clip elements (both naming conventions)
    for mc_clip in root.findall('.//mc-clip'):
        name = mc_clip.get('name', '')
        # Include clips that match either naming pattern
        if 'ios26 off 1 multi' in name or 'ios 26 off' in name:
            # Get timing info
            offset = mc_clip.get('offset', '0s')
            start = mc_clip.get('start', '0s')
            duration = mc_clip.get('duration', '0s')

            # Convert rational time to seconds
            def to_seconds(time_str):
                if not time_str:
                    return 0
                # Remove 's' suffix
                time_str = time_str.rstrip('s')
                if '/' in time_str:
                    num, denom = time_str.split('/')
                    return float(num) / float(denom)
                return float(time_str)

            clip_info = {
                'offset_seconds': to_seconds(offset),
                'start_seconds': to_seconds(start),
                'duration_seconds': to_seconds(duration),
                'offset': offset,
                'start': start,
                'duration': duration
            }

            clips.append(clip_info)

    # Sort by offset
    clips.sort(key=lambda x: x['offset_seconds'])

    return clips

def analyze_differences():
    """Compare AI-generated cuts with manual edits."""

    # Paths
    ai_generated = "/Users/payetteforward/repos/claude/multicam-auto-cut/src/outputs/20250915_104759/Info_AutoCut.fcpxml"
    manual_edit = "/Users/payetteforward/repos/claude/multicam-auto-cut/src/fcpxml_exports/ios 26 settings to turn off.fcpxmld/Info.fcpxml"

    print("=" * 80)
    print("MULTICAM CLIP EDIT ANALYSIS")
    print("=" * 80)

    # Check if files exist
    if not Path(ai_generated).exists():
        print(f"AI-generated file not found: {ai_generated}")
        return

    if not Path(manual_edit).exists():
        print(f"Manual edit file not found: {manual_edit}")
        return

    # Extract clips
    print("\n📊 Extracting clips from AI-generated FCPXML...")
    ai_clips = extract_mc_clips(ai_generated)
    print(f"   Found {len(ai_clips)} clips")

    print("\n📊 Extracting clips from manually edited FCPXML...")
    manual_clips = extract_mc_clips(manual_edit)
    print(f"   Found {len(manual_clips)} clips")

    # Filter out intro/compound clips (first few seconds)
    print("\n🔍 Filtering out intro section...")
    # Skip clips that start before 60 seconds (intro section)
    manual_clips_filtered = [c for c in manual_clips if c['start_seconds'] > 60]
    print(f"   Filtered to {len(manual_clips_filtered)} main content clips")

    # Statistics
    print("\n📈 STATISTICS:")
    print("-" * 40)

    # Total duration of kept content
    ai_total_duration = sum(c['duration_seconds'] for c in ai_clips)
    manual_total_duration = sum(c['duration_seconds'] for c in manual_clips_filtered)

    print(f"AI-generated total duration: {ai_total_duration:.1f}s ({ai_total_duration/60:.1f} min)")
    print(f"Manual edit total duration: {manual_total_duration:.1f}s ({manual_total_duration/60:.1f} min)")
    print(f"Difference: {manual_total_duration - ai_total_duration:.1f}s")

    # Average clip length
    ai_avg_duration = ai_total_duration / len(ai_clips) if ai_clips else 0
    manual_avg_duration = manual_total_duration / len(manual_clips_filtered) if manual_clips_filtered else 0

    print(f"\nAverage clip duration:")
    print(f"  AI-generated: {ai_avg_duration:.1f}s")
    print(f"  Manual edit: {manual_avg_duration:.1f}s")

    # Clip length distribution
    print("\n📊 CLIP LENGTH DISTRIBUTION:")
    print("-" * 40)

    def get_distribution(clips):
        very_short = sum(1 for c in clips if c['duration_seconds'] < 2)
        short = sum(1 for c in clips if 2 <= c['duration_seconds'] < 5)
        medium = sum(1 for c in clips if 5 <= c['duration_seconds'] < 10)
        long = sum(1 for c in clips if 10 <= c['duration_seconds'] < 20)
        very_long = sum(1 for c in clips if c['duration_seconds'] >= 20)
        return very_short, short, medium, long, very_long

    ai_dist = get_distribution(ai_clips)
    manual_dist = get_distribution(manual_clips_filtered)

    print("                 <2s   2-5s  5-10s 10-20s  >20s")
    print(f"AI-generated:  {ai_dist[0]:4d}  {ai_dist[1]:4d}  {ai_dist[2]:5d}  {ai_dist[3]:5d}  {ai_dist[4]:4d}")
    print(f"Manual edit:   {manual_dist[0]:4d}  {manual_dist[1]:4d}  {manual_dist[2]:5d}  {manual_dist[3]:5d}  {manual_dist[4]:4d}")

    # Sample of clips
    print("\n📝 SAMPLE CLIPS (first 10 from each):")
    print("-" * 40)

    print("\nAI-generated clips:")
    for i, clip in enumerate(ai_clips[:10]):
        print(f"  {i+1:2d}. Duration: {clip['duration_seconds']:6.1f}s  Start: {clip['start_seconds']:7.1f}s")

    print("\nManual edit clips:")
    for i, clip in enumerate(manual_clips_filtered[:10]):
        print(f"  {i+1:2d}. Duration: {clip['duration_seconds']:6.1f}s  Start: {clip['start_seconds']:7.1f}s")

    # Key insights
    print("\n💡 KEY INSIGHTS:")
    print("-" * 40)

    retention_rate = (manual_total_duration / ai_total_duration * 100) if ai_total_duration > 0 else 0

    if retention_rate > 100:
        print(f"✅ Manual edit KEPT MORE content: {retention_rate:.1f}% of AI suggestion")
        print("   → The AI was too aggressive in cutting")
    else:
        print(f"✂️  Manual edit kept {retention_rate:.1f}% of AI suggestion")
        print("   → The AI was not aggressive enough")

    if manual_avg_duration > ai_avg_duration:
        print(f"📏 Manual clips are LONGER on average (+{manual_avg_duration - ai_avg_duration:.1f}s)")
        print("   → You prefer longer, uninterrupted segments")
    else:
        print(f"📏 Manual clips are SHORTER on average ({manual_avg_duration - ai_avg_duration:.1f}s)")
        print("   → You prefer tighter, more frequent cuts")

    # More short clips in manual?
    if manual_dist[0] + manual_dist[1] > ai_dist[0] + ai_dist[1]:
        print("🎬 Manual edit has MORE short clips (<5s)")
        print("   → You're willing to include brief moments the AI removed")

    # More long clips in manual?
    if manual_dist[4] > ai_dist[4]:
        print("🎞️  Manual edit has MORE long clips (>20s)")
        print("   → You keep longer takes that the AI might have split")

if __name__ == "__main__":
    analyze_differences()