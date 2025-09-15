"""
Transcript Cleaning Module
Implements the "last take is best" logic and removes filler words, false starts, etc.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Set
from difflib import SequenceMatcher
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class CleaningSegment:
    """Represents a segment of transcript with timing information."""
    start_time: float
    end_time: float
    original_text: str
    cleaned_text: str
    confidence: float
    is_keeper: bool = False
    segment_id: Optional[int] = None

@dataclass
class TakeGroup:
    """Represents a group of similar takes (repeated attempts)."""
    segments: List[CleaningSegment]
    common_content: str
    best_take_index: int
    similarity_threshold: float

class TranscriptCleaner:
    """
    Cleans transcripts by removing filler words, false starts, and selecting best takes.
    """
    
    def __init__(self, cleaning_level: str = 'moderate'):
        """
        Initialize the transcript cleaner.
        
        Args:
            cleaning_level (str): 'light', 'moderate', or 'aggressive'
        """
        self.cleaning_level = cleaning_level
        self.filler_words = self._get_filler_words()
        self.false_start_patterns = self._get_false_start_patterns()
        
    def _get_filler_words(self) -> Set[str]:
        """Get set of filler words based on cleaning level."""
        base_fillers = {
            'um', 'uh', 'ah', 'er', 'hmm', 'mm', 'mhm', 'erm'
        }
        
        moderate_fillers = base_fillers | {
            'like', 'you know', 'i mean', 'sort of', 'kind of',
            'basically', 'actually', 'literally', 'so'
        }
        
        aggressive_fillers = moderate_fillers | {
            'well', 'okay', 'alright', 'right', 'yeah', 'yes',
            'totally', 'definitely', 'obviously', 'clearly'
        }
        
        if self.cleaning_level == 'light':
            return base_fillers
        elif self.cleaning_level == 'moderate':
            return moderate_fillers
        else:  # aggressive
            return aggressive_fillers
    
    def _get_false_start_patterns(self) -> List[str]:
        """Get regex patterns for detecting false starts."""
        return [
            r'\b(\w+)\s+\1\b',  # Repeated words: "the the"
            r'\b(\w+)\s+(\w+)\s+\1\s+\2\b',  # Repeated phrases: "in the in the"
            r'\b\w+\s*--\s*\w+',  # Self-corrections with dashes
            r'\b\w+\s*,\s*(?:i mean|actually|sorry)\b',  # Corrections with phrases
        ]
    
    def clean_transcript(self, transcription: Dict) -> Dict:
        """
        Main function to clean a complete transcription.
        
        Args:
            transcription (Dict): Original transcription with segments
            
        Returns:
            Dict: Cleaned transcription with timing mappings
        """
        logger.info(f"Cleaning transcript with {self.cleaning_level} level...")
        
        # Convert segments to CleaningSegments
        segments = self._convert_to_cleaning_segments(transcription['segments'])
        
        # Step 1: Clean individual segments
        logger.info("Step 1: Cleaning individual segments...")
        for segment in segments:
            segment.cleaned_text = self._clean_segment_text(segment.original_text)
        
        # Step 2: Identify take groups
        logger.info("Step 2: Identifying take groups...")
        take_groups = self._identify_take_groups(segments)
        
        # Step 3: Select best takes
        logger.info("Step 3: Selecting best takes...")
        for group in take_groups:
            self._select_best_take(group)
        
        # Step 4: Mark keeper segments
        logger.info("Step 4: Marking keeper segments...")
        keeper_segments = self._mark_keeper_segments(segments, take_groups)
        
        # Step 5: Generate cleaned transcription
        logger.info("Step 5: Generating cleaned transcription...")
        cleaned_transcription = self._generate_cleaned_transcription(
            transcription, keeper_segments
        )
        
        # Step 6: Create timing mapping
        timing_mapping = self._create_timing_mapping(segments, keeper_segments)
        
        result = {
            'original_transcription': transcription,
            'cleaned_transcription': cleaned_transcription,
            'timing_mapping': timing_mapping,
            'take_groups': [self._serialize_take_group(tg) for tg in take_groups],
            'cleaning_stats': self._generate_cleaning_stats(segments, keeper_segments),
            'cleaning_level': self.cleaning_level
        }
        
        logger.info(f"✅ Transcript cleaning completed")
        logger.info(f"   Original segments: {len(segments)}")
        logger.info(f"   Keeper segments: {len(keeper_segments)}")
        logger.info(f"   Take groups found: {len(take_groups)}")
        
        return result
    
    def _convert_to_cleaning_segments(self, segments: List[Dict]) -> List[CleaningSegment]:
        """Convert transcription segments to CleaningSegments."""
        cleaning_segments = []
        
        for i, segment in enumerate(segments):
            cleaning_segment = CleaningSegment(
                start_time=segment['start'],
                end_time=segment['end'],
                original_text=segment['text'].strip(),
                cleaned_text="",
                confidence=1.0 - segment.get('no_speech_prob', 0.0),
                segment_id=i
            )
            cleaning_segments.append(cleaning_segment)
        
        return cleaning_segments
    
    def _clean_segment_text(self, text: str) -> str:
        """Clean a single segment of text."""
        cleaned = text.strip()
        
        # Remove filler words
        words = cleaned.split()
        filtered_words = []
        
        for word in words:
            clean_word = re.sub(r'[^\w\s]', '', word.lower())
            if clean_word not in self.filler_words:
                filtered_words.append(word)
        
        cleaned = ' '.join(filtered_words)
        
        # Apply false start patterns
        for pattern in self.false_start_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _identify_take_groups(self, segments: List[CleaningSegment], 
                            similarity_threshold: float = 0.6,
                            time_window: float = 30.0) -> List[TakeGroup]:
        """Identify groups of segments that represent repeated takes."""
        take_groups = []
        used_segments = set()
        
        for i, segment in enumerate(segments):
            if i in used_segments or not segment.cleaned_text.strip():
                continue
            
            group_segments = [segment]
            used_segments.add(i)
            
            for j, other_segment in enumerate(segments[i+1:], start=i+1):
                if j in used_segments:
                    continue
                
                time_gap = other_segment.start_time - segment.end_time
                if time_gap > time_window:
                    break
                
                similarity = self._calculate_similarity(
                    segment.cleaned_text, other_segment.cleaned_text
                )
                
                if similarity >= similarity_threshold:
                    group_segments.append(other_segment)
                    used_segments.add(j)
            
            if len(group_segments) > 1:
                common_content = self._extract_common_content(
                    [seg.cleaned_text for seg in group_segments]
                )
                
                best_take_index = len(group_segments) - 1  # Last take is best
                
                take_group = TakeGroup(
                    segments=group_segments,
                    common_content=common_content,
                    best_take_index=best_take_index,
                    similarity_threshold=similarity_threshold
                )
                
                take_groups.append(take_group)
        
        return take_groups
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text segments."""
        if not text1.strip() or not text2.strip():
            return 0.0
        
        matcher = SequenceMatcher(None, text1.lower().split(), text2.lower().split())
        return matcher.ratio()
    
    def _extract_common_content(self, texts: List[str]) -> str:
        """Extract common content from multiple text versions."""
        if not texts:
            return ""
        
        if len(texts) == 1:
            return texts[0]
        
        # Find longest text as base
        longest_text = max(texts, key=len)
        return longest_text[:50] + "..." if len(longest_text) > 50 else longest_text
    
    def _select_best_take(self, take_group: TakeGroup):
        """Select the best take from a group using 'last take is best' logic."""
        segments = take_group.segments
        
        scores = []
        for i, segment in enumerate(segments):
            score = 0.0
            
            # Last take bonus (primary criterion)
            last_take_bonus = i / max(1, len(segments) - 1)
            score += last_take_bonus * 0.5
            
            # Length bonus
            max_length = max(len(seg.cleaned_text) for seg in segments)
            if max_length > 0:
                length_bonus = len(segment.cleaned_text) / max_length
                score += length_bonus * 0.3
            
            # Confidence bonus
            score += segment.confidence * 0.2
            
            scores.append(score)
        
        take_group.best_take_index = scores.index(max(scores))
    
    def _mark_keeper_segments(self, segments: List[CleaningSegment], 
                            take_groups: List[TakeGroup]) -> List[CleaningSegment]:
        """Mark which segments to keep in the final cut."""
        keeper_segments = []
        
        # Create mapping of segments in take groups
        grouped_segment_ids = set()
        for group in take_groups:
            for i, segment in enumerate(group.segments):
                if i == group.best_take_index:
                    segment.is_keeper = True
                    keeper_segments.append(segment)
                grouped_segment_ids.add(segment.segment_id)
        
        # Add segments that aren't part of any take group
        for segment in segments:
            if segment.segment_id not in grouped_segment_ids and segment.cleaned_text.strip():
                segment.is_keeper = True
                keeper_segments.append(segment)
        
        # Sort by start time
        keeper_segments.sort(key=lambda x: x.start_time)
        
        return keeper_segments
    
    def _generate_cleaned_transcription(self, original: Dict, 
                                      keeper_segments: List[CleaningSegment]) -> Dict:
        """Generate a new transcription with only keeper segments."""
        cleaned_segments = []
        cleaned_text_parts = []
        
        for segment in keeper_segments:
            cleaned_segments.append({
                'id': len(cleaned_segments),
                'start': segment.start_time,
                'end': segment.end_time,
                'text': segment.cleaned_text,
                'original_text': segment.original_text,
                'confidence': segment.confidence
            })
            
            if segment.cleaned_text.strip():
                cleaned_text_parts.append(segment.cleaned_text)
        
        cleaned_transcription = original.copy()
        cleaned_transcription.update({
            'text': ' '.join(cleaned_text_parts),
            'segments': cleaned_segments,
            'segment_count': len(cleaned_segments),
            'cleaning_applied': True
        })
        
        return cleaned_transcription
    
    def _create_timing_mapping(self, original_segments: List[CleaningSegment],
                             keeper_segments: List[CleaningSegment]) -> Dict:
        """Create mapping between original and cleaned timings for cuts."""
        cut_ranges = []
        keep_ranges = []
        
        if keeper_segments:
            current_start = keeper_segments[0].start_time
            current_end = keeper_segments[0].end_time
            
            for i in range(1, len(keeper_segments)):
                segment = keeper_segments[i]
                
                gap = segment.start_time - current_end
                if gap <= 1.0:  # Allow small gaps
                    current_end = segment.end_time
                else:
                    keep_ranges.append({
                        'start': current_start,
                        'end': current_end
                    })
                    current_start = segment.start_time
                    current_end = segment.end_time
            
            keep_ranges.append({
                'start': current_start,
                'end': current_end
            })
        
        # Calculate cut ranges
        if keep_ranges:
            if keep_ranges[0]['start'] > 0:
                cut_ranges.append({
                    'start': 0,
                    'end': keep_ranges[0]['start']
                })
            
            for i in range(len(keep_ranges) - 1):
                cut_ranges.append({
                    'start': keep_ranges[i]['end'],
                    'end': keep_ranges[i + 1]['start']
                })
            
            total_duration = max(seg.end_time for seg in original_segments)
            if keep_ranges[-1]['end'] < total_duration:
                cut_ranges.append({
                    'start': keep_ranges[-1]['end'],
                    'end': total_duration
                })
        
        return {
            'keep_ranges': keep_ranges,
            'cut_ranges': cut_ranges,
            'total_original_duration': max(seg.end_time for seg in original_segments) if original_segments else 0,
            'total_cleaned_duration': sum(r['end'] - r['start'] for r in keep_ranges)
        }
    
    def _serialize_take_group(self, take_group: TakeGroup) -> Dict:
        """Convert TakeGroup to serializable format."""
        return {
            'common_content': take_group.common_content,
            'best_take_index': take_group.best_take_index,
            'segment_count': len(take_group.segments)
        }
    
    def _generate_cleaning_stats(self, original_segments: List[CleaningSegment],
                               keeper_segments: List[CleaningSegment]) -> Dict:
        """Generate statistics about the cleaning process."""
        original_duration = sum(seg.end_time - seg.start_time for seg in original_segments)
        cleaned_duration = sum(seg.end_time - seg.start_time for seg in keeper_segments)
        
        original_word_count = sum(len(seg.original_text.split()) for seg in original_segments)
        cleaned_word_count = sum(len(seg.cleaned_text.split()) for seg in keeper_segments)
        
        return {
            'original_segment_count': len(original_segments),
            'cleaned_segment_count': len(keeper_segments),
            'segments_removed': len(original_segments) - len(keeper_segments),
            'original_duration': original_duration,
            'cleaned_duration': cleaned_duration,
            'time_saved': original_duration - cleaned_duration,
            'time_saved_percentage': ((original_duration - cleaned_duration) / original_duration * 100) if original_duration > 0 else 0,
            'original_word_count': original_word_count,
            'cleaned_word_count': cleaned_word_count,
            'words_removed': original_word_count - cleaned_word_count
        }

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Transcript Cleaning Module")
    print("=" * 26)
    
    # Test with sample data
    sample_transcription = {
        'text': 'Um, so today I want to talk about, uh, today I want to discuss the project.',
        'segments': [
            {'id': 0, 'start': 0.0, 'end': 2.5, 'text': 'Um, so today I want to talk about', 'no_speech_prob': 0.1},
            {'id': 1, 'start': 3.0, 'end': 6.0, 'text': 'uh, today I want to discuss the project', 'no_speech_prob': 0.05}
        ]
    }
    
    cleaner = TranscriptCleaner(cleaning_level='moderate')
    result = cleaner.clean_transcript(sample_transcription)
    
    print(f"Original: '{sample_transcription['text']}'")
    print(f"Cleaned:  '{result['cleaned_transcription']['text']}'")
    print(f"Stats: {result['cleaning_stats']['segments_removed']} segments removed")
    print("\n✅ Transcript cleaner is ready!")
