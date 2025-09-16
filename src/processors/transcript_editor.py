#!/usr/bin/env python3
"""Edit transcripts using Claude API to remove stutters and false starts."""

import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from ..config.editing_profiles import get_profile, EditingProfile

logger = logging.getLogger(__name__)

class TranscriptEditor:
    """Edit transcripts using Claude API"""

    def __init__(self, editing_profile: str = "tutorial"):
        """
        Initialize the transcript editor.

        Args:
            editing_profile: Name of the editing profile to use
                           ("scripted", "tutorial", "rough", "podcast", "aggressive")
        """
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

        self.profile = get_profile(editing_profile)
        logger.info(f"Using editing profile: {self.profile.name}")

    def edit_transcript(self, segments: List[Dict], output_dir: Optional[str] = None) -> List[Dict]:
        """
        Edit transcript segments to remove stutters and false starts.

        Args:
            segments: List of transcript segments with text and timing
            output_dir: Optional directory to save debug transcript

        Returns:
            List of edited segments with cleaned text
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        # Combine all text for editing
        full_text = " ".join(seg['text'].strip() for seg in segments)

        logger.info("Sending transcript to Claude for editing...")

        try:
            # Use Claude to edit the transcript with the selected profile
            prompt = self.profile.get_prompt(full_text)

            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            edited_text = message.content[0].text.strip()
            logger.info(f"Received edited transcript ({len(edited_text)} chars)")

            # Map edited text back to segments
            edited_segments = self._map_edited_to_segments(segments, edited_text)

            # Save debug transcript if output directory provided
            if output_dir:
                self._save_debug_transcript(edited_segments, full_text, edited_text, output_dir)

            return edited_segments

        except Exception as e:
            logger.error(f"Error editing transcript with Claude: {e}")
            # Return original segments if editing fails
            return segments

    def _map_edited_to_segments(self, original_segments: List[Dict], edited_text: str) -> List[Dict]:
        """
        Map edited text back to original segments, preserving timing.
        Segments that are completely removed get marked for deletion.

        Args:
            original_segments: Original transcript segments
            edited_text: Edited full transcript text

        Returns:
            List of segments with edited text and keep/remove flags
        """
        import difflib

        # Get original text for comparison
        original_words = []
        word_to_segment = []

        for i, seg in enumerate(original_segments):
            words = seg['text'].strip().split()
            original_words.extend(words)
            word_to_segment.extend([i] * len(words))

        # Split edited text into words
        edited_words = edited_text.split()

        # Use sequence matcher to align original and edited
        matcher = difflib.SequenceMatcher(None, original_words, edited_words)

        # Track which segments to keep and their edited text
        segment_edited_text = {i: [] for i in range(len(original_segments))}
        segments_to_keep = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal' or tag == 'replace':
                # These words are kept (possibly modified)
                for orig_idx, edit_idx in zip(range(i1, i2), range(j1, j2)):
                    if orig_idx < len(word_to_segment):
                        seg_idx = word_to_segment[orig_idx]
                        segments_to_keep.add(seg_idx)
                        if edit_idx < len(edited_words):
                            segment_edited_text[seg_idx].append(edited_words[edit_idx])
            elif tag == 'delete':
                # These segments are removed (false starts, stutters)
                pass
            elif tag == 'insert':
                # New words added - assign to nearest segment
                if i1 > 0:
                    seg_idx = word_to_segment[i1 - 1]
                    segments_to_keep.add(seg_idx)
                    for edit_idx in range(j1, j2):
                        if edit_idx < len(edited_words):
                            segment_edited_text[seg_idx].append(edited_words[edit_idx])

        # Build result segments
        result_segments = []
        for i, seg in enumerate(original_segments):
            if i in segments_to_keep and segment_edited_text[i]:
                # Keep this segment with edited text
                edited_seg = seg.copy()
                edited_seg['text'] = ' '.join(segment_edited_text[i])
                edited_seg['keep'] = True
                result_segments.append(edited_seg)
            else:
                # Mark segment for removal
                edited_seg = seg.copy()
                edited_seg['keep'] = False
                result_segments.append(edited_seg)

        # Log statistics
        kept_count = sum(1 for s in result_segments if s.get('keep', False))
        logger.info(f"Keeping {kept_count}/{len(original_segments)} segments after editing")

        return result_segments

    def _save_debug_transcript(self, edited_segments: List[Dict], original_text: str,
                              edited_text: str, output_dir: str):
        """
        Save debug transcript with timestamps for analysis.

        Args:
            edited_segments: Segments with keep/remove flags
            original_text: Original full transcript
            edited_text: Edited full transcript
            output_dir: Directory to save debug files
        """
        debug_path = Path(output_dir) / "edited_transcript_debug.txt"

        try:
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("TRANSCRIPT EDITING DEBUG FILE\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")

                # Write original transcript
                f.write("ORIGINAL TRANSCRIPT:\n")
                f.write("-" * 40 + "\n")
                f.write(original_text + "\n\n")

                # Write edited transcript
                f.write("EDITED TRANSCRIPT (from Claude):\n")
                f.write("-" * 40 + "\n")
                f.write(edited_text + "\n\n")

                # Write segment-by-segment breakdown
                f.write("SEGMENT-BY-SEGMENT BREAKDOWN:\n")
                f.write("-" * 40 + "\n")

                kept_segments = []
                removed_segments = []

                for seg in edited_segments:
                    timestamp = f"[{seg.get('start', 0):.2f} - {seg.get('end', 0):.2f}]"
                    if seg.get('keep', False):
                        status = "✅ KEPT"
                        kept_segments.append(seg)
                        f.write(f"{timestamp} {status}\n")
                        f.write(f"  Text: {seg.get('text', '')}\n\n")
                    else:
                        status = "❌ REMOVED"
                        removed_segments.append(seg)
                        f.write(f"{timestamp} {status}\n\n")

                # Write statistics
                f.write("\nSTATISTICS:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total segments: {len(edited_segments)}\n")
                f.write(f"Kept segments: {len(kept_segments)}\n")
                f.write(f"Removed segments: {len(removed_segments)}\n")

                if kept_segments:
                    total_kept_time = sum(s.get('end', 0) - s.get('start', 0) for s in kept_segments)
                    f.write(f"Total kept duration: {total_kept_time:.2f} seconds\n")

                if removed_segments:
                    total_removed_time = sum(s.get('end', 0) - s.get('start', 0) for s in removed_segments)
                    f.write(f"Total removed duration: {total_removed_time:.2f} seconds\n")

                # Write final compiled transcript
                f.write("\n" + "=" * 80 + "\n")
                f.write("FINAL COMPILED TRANSCRIPT (with timestamps):\n")
                f.write("-" * 40 + "\n")
                for seg in kept_segments:
                    timestamp = f"[{seg.get('start', 0):.2f}]"
                    f.write(f"{timestamp} {seg.get('text', '')}\n")

            logger.info(f"Debug transcript saved to: {debug_path}")

        except Exception as e:
            logger.warning(f"Failed to save debug transcript: {e}")