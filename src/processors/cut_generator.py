"""
Cut Generator Module
Generates FCPXML files with blade cuts applied based on cleaned transcript timing mappings.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timezone
from ..utils import FrameRateHandler, FrameRateInfo

# Set up logging
logger = logging.getLogger(__name__)

class CutGenerator:
    """
    Generates FCPXML files with blade cuts applied to remove unwanted sections.
    """
    
    def __init__(self):
        """Initialize the cut generator."""
        self.original_fcpxml = None
        self.original_tree = None
        self.cut_ranges = []
        self.keep_ranges = []
        self.frame_rate_handler = FrameRateHandler()
        self.project_frame_rates = {}
        self.primary_frame_rate = None
    
    def generate_cut_fcpxml(self, original_fcpxml_path: str,
                           cleaned_transcript_data: Dict,
                           output_path: str,
                           edited_segments: Optional[List[Dict]] = None) -> str:
        """
        Generate a new FCPXML file with blade cuts applied.

        Args:
            original_fcpxml_path (str): Path to original FCPXML
            cleaned_transcript_data (Dict): Result from transcript cleaner
            output_path (str): Path for output FCPXML
            edited_segments (Optional[List[Dict]]): Edited transcript segments with keep flags

        Returns:
            str: Path to generated FCPXML file
        """
        logger.info("Generating cut FCPXML...")

        # Load original FCPXML
        self._load_original_fcpxml(original_fcpxml_path)

        # Extract frame rate information
        self._extract_frame_rate_info(cleaned_transcript_data)

        # Extract timing information
        timing_mapping = cleaned_transcript_data['timing_mapping']
        self.cut_ranges = timing_mapping['cut_ranges']
        self.keep_ranges = timing_mapping['keep_ranges']

        # If we have edited segments, filter keep_ranges based on which segments to keep
        if edited_segments:
            self.keep_ranges = self._filter_ranges_by_edited_segments(
                self.keep_ranges, edited_segments
            )
        
        logger.info(f"Applying {len(self.cut_ranges)} cuts to multicam clip")
        logger.info(f"Keeping {len(self.keep_ranges)} ranges")
        logger.info(f"Project frame rate: {self.primary_frame_rate.name if self.primary_frame_rate else 'Unknown'}")
        
        # Generate the modified FCPXML
        modified_tree = self._apply_cuts_to_fcpxml()
        
        # Save the result
        self._save_fcpxml(modified_tree, output_path)
        
        # Add metadata about the cuts
        self._add_cut_metadata(output_path, cleaned_transcript_data)
        
        logger.info(f"✅ Cut FCPXML generated: {output_path}")
        return output_path
    
    def _load_original_fcpxml(self, fcpxml_path: str):
        """Load and parse the original FCPXML file."""
        self.original_tree = ET.parse(fcpxml_path)
        self.original_fcpxml = self.original_tree.getroot()
        logger.debug(f"Loaded original FCPXML: {fcpxml_path}")
    
    def _extract_frame_rate_info(self, cleaned_transcript_data: Dict):
        """Extract frame rate information from the cleaned transcript data."""
        # Get frame rate info from the original parsing
        original_data = cleaned_transcript_data.get('original_transcription', {})
        fcpxml_data = original_data.get('fcpxml_data', {})
        
        if 'frame_rates' in fcpxml_data:
            # Convert dict back to FrameRateInfo objects
            for resource_id, rate_dict in fcpxml_data['frame_rates'].items():
                rate_info = FrameRateInfo(
                    rate=rate_dict['rate'],
                    timebase=rate_dict['timebase'],
                    timescale=rate_dict['timescale'],
                    is_drop_frame=rate_dict['is_drop_frame'],
                    name=rate_dict['name'],
                    fcpxml_duration_format=rate_dict['fcpxml_duration_format']
                )
                self.project_frame_rates[resource_id] = rate_info
        
        # Set primary frame rate
        primary_rate_dict = fcpxml_data.get('primary_frame_rate')
        if primary_rate_dict:
            self.primary_frame_rate = FrameRateInfo(
                rate=primary_rate_dict['rate'],
                timebase=primary_rate_dict['timebase'],
                timescale=primary_rate_dict['timescale'],
                is_drop_frame=primary_rate_dict['is_drop_frame'],
                name=primary_rate_dict['name'],
                fcpxml_duration_format=primary_rate_dict['fcpxml_duration_format']
            )
        else:
            # Fallback to detecting from XML directly
            self._detect_frame_rates_from_xml()
    
    def _detect_frame_rates_from_xml(self):
        """Fallback method to detect frame rates directly from XML."""
        logger.info("Detecting frame rates from XML...")
        
        # Find format elements
        for format_elem in self.original_fcpxml.findall('.//format'):
            format_id = format_elem.get('id')
            rate_info = self.frame_rate_handler.detect_frame_rate_from_fcpxml_format(format_elem)
            if rate_info:
                self.project_frame_rates[format_id] = rate_info
        
        # Set primary rate
        if self.project_frame_rates:
            self.primary_frame_rate = self.frame_rate_handler.get_primary_frame_rate(self.project_frame_rates)
        else:
            # Ultimate fallback
            self.primary_frame_rate = self.frame_rate_handler.FRAME_RATES['29.97df']
    
    def _apply_cuts_to_fcpxml(self) -> ET.ElementTree:
        """Apply the blade cuts to the FCPXML structure by creating a new project."""
        # Create a copy of the original tree
        new_root = self._deep_copy_element(self.original_fcpxml)
        new_tree = ET.ElementTree(new_root)

        # Find the original sequence to use as a template
        original_sequence = new_root.find('.//sequence')
        if original_sequence is None:
            logger.error("No sequence found in original FCPXML")
            return new_tree

        # Find the event element to add new project to
        event = new_root.find('.//event')
        if event is None:
            # If no event, check if we're in library directly
            library = new_root.find('library')
            if library is not None:
                # Create an event if none exists
                event = ET.Element('event')
                event.set('name', 'Auto-Cut Events')
                event.set('uid', f'auto-cut-event-{datetime.now().strftime("%Y%m%d%H%M%S")}')
                library.append(event)
            else:
                logger.error("No event or library found in FCPXML")
                return new_tree

        # Find the original project for reference
        original_project = new_root.find('.//project')

        # Create a NEW project for the cut version
        cut_project = ET.Element('project')
        original_project_name = original_project.get('name', 'Project') if original_project else 'Project'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cut_project.set('name', f"{original_project_name}_AutoCut_{timestamp}")
        cut_project.set('uid', f'auto-cut-{timestamp}')
        # Ensure modDate has proper timezone format (e.g., "2025-09-15 06:18:30 -0400")
        cut_project.set('modDate', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %z'))

        # Create a new sequence for the cut version
        cut_sequence = self._create_cut_sequence(original_sequence)

        # Process multicam clips in the cut sequence
        mc_clips = cut_sequence.findall('.//mc-clip')
        for mc_clip in mc_clips:
            logger.debug(f"Processing multicam clip: {mc_clip.get('name', 'unnamed')}")
            self._apply_cuts_to_multicam_clip_new(mc_clip, cut_sequence)

        # Add the cut sequence to the NEW project
        cut_project.append(cut_sequence)

        # Add the new project to the event
        event.append(cut_project)

        logger.info(f"Created new project: {cut_project.get('name')}")

        return new_tree

    def _create_cut_sequence(self, original_sequence) -> ET.Element:
        """Create a new sequence for the cut version."""
        # Create a deep copy of the original sequence
        cut_sequence = self._deep_copy_element(original_sequence)

        # Remove name attribute if it exists (sequences don't have names in DTD)
        if 'name' in cut_sequence.attrib:
            del cut_sequence.attrib['name']

        # Update the duration based on actual cuts
        total_duration = sum(kr['end'] - kr['start'] for kr in self.keep_ranges)
        format_ref = cut_sequence.get('format')
        cut_sequence.set('duration', self._seconds_to_rational_time(total_duration, format_ref))

        logger.info(f"Created new sequence for auto-cut project")
        logger.info(f"Total duration after cuts: {total_duration:.2f} seconds")

        return cut_sequence

    def _apply_cuts_to_multicam_clip_new(self, mc_clip_element, parent_sequence):
        """Apply cuts to a multicam clip in the new sequence."""
        # Get original clip timing and format
        original_offset = mc_clip_element.get('offset', '0s')
        original_start = mc_clip_element.get('start', '0s')
        original_duration = mc_clip_element.get('duration', '0s')
        format_ref = mc_clip_element.get('format')

        # Convert to seconds using frame rate context
        offset_seconds = self._rational_time_to_seconds(original_offset, format_ref)
        start_seconds = self._rational_time_to_seconds(original_start, format_ref)
        duration_seconds = self._rational_time_to_seconds(original_duration, format_ref)

        logger.debug(f"Original clip: offset={offset_seconds}s, start={start_seconds}s, duration={duration_seconds}s")

        # Find the spine element in the sequence
        spine = parent_sequence.find('.//spine')
        if spine is None:
            logger.error("No spine found in sequence")
            return

        # Clear the spine and add cut segments
        spine.clear()

        # Track cumulative offset for positioning segments
        cumulative_offset = 0.0

        # Create new multicam clips for each keep range
        for i, keep_range in enumerate(self.keep_ranges):
            new_clip = self._create_sequential_cut_clip(
                mc_clip_element, keep_range, cumulative_offset, i, format_ref
            )
            if new_clip is not None:
                spine.append(new_clip)
                # Update cumulative offset for next segment
                cumulative_offset += (keep_range['end'] - keep_range['start'])

    def _create_sequential_cut_clip(self, original_clip, keep_range: Dict,
                                   timeline_offset: float, segment_index: int,
                                   format_ref: Optional[str] = None):
        """Create a multicam clip segment positioned sequentially in the new timeline."""
        # Create a copy of the original clip
        new_clip = self._deep_copy_element(original_clip)

        # Calculate timing for this segment
        range_start = keep_range['start']
        range_end = keep_range['end']
        range_duration = range_end - range_start

        # Convert times to rational format
        # The offset in the new timeline is the cumulative position
        new_offset_rational = self._seconds_to_rational_time(timeline_offset, format_ref)
        # The start time references the source position in the original clip
        new_start_rational = self._seconds_to_rational_time(range_start, format_ref)
        # Duration is the length of this segment
        new_duration_rational = self._seconds_to_rational_time(range_duration, format_ref)

        # Update clip attributes
        new_clip.set('offset', new_offset_rational)
        new_clip.set('start', new_start_rational)
        new_clip.set('duration', new_duration_rational)

        # Update name to indicate it's a cut segment
        original_name = new_clip.get('name', 'Multicam Clip')
        new_clip.set('name', f"{original_name} - Cut {segment_index + 1}")

        logger.debug(f"Created sequential cut {segment_index + 1}:")
        logger.debug(f"  Timeline offset={new_offset_rational} ({timeline_offset:.3f}s)")
        logger.debug(f"  Source start={new_start_rational} ({range_start:.3f}s)")
        logger.debug(f"  Duration={new_duration_rational} ({range_duration:.3f}s)")

        return new_clip

    def _apply_cuts_to_multicam_clip(self, mc_clip_element):
        """Apply cuts to a specific multicam clip by splitting it into segments."""
        # Get original clip timing and format
        original_offset = mc_clip_element.get('offset', '0s')
        original_start = mc_clip_element.get('start', '0s')
        original_duration = mc_clip_element.get('duration', '0s')
        format_ref = mc_clip_element.get('format')
        
        # Convert to seconds using frame rate context
        offset_seconds = self._rational_time_to_seconds(original_offset, format_ref)
        start_seconds = self._rational_time_to_seconds(original_start, format_ref)
        duration_seconds = self._rational_time_to_seconds(original_duration, format_ref)
        
        logger.debug(f"Original clip: offset={offset_seconds}s, start={start_seconds}s, duration={duration_seconds}s")
        logger.debug(f"Format reference: {format_ref}")
        
        # Find the parent element to replace the multicam clip
        parent = self._find_parent_element(mc_clip_element)
        if parent is None:
            logger.error("Could not find parent element for multicam clip")
            return
        
        # Remove the original multicam clip
        parent.remove(mc_clip_element)
        
        # Create new multicam clips for each keep range with frame-accurate timing
        for i, keep_range in enumerate(self.keep_ranges):
            new_clip = self._create_cut_multicam_clip(
                mc_clip_element, keep_range, offset_seconds, i, format_ref
            )
            if new_clip is not None:
                parent.append(new_clip)
    
    def _create_cut_multicam_clip(self, original_clip, keep_range: Dict, 
                                 timeline_offset: float, segment_index: int,
                                 format_ref: Optional[str] = None):
        """Create a new multicam clip for a specific keep range with frame-accurate timing."""
        # Create a copy of the original clip
        new_clip = self._deep_copy_element(original_clip)
        
        # Calculate new timing
        range_start = keep_range['start']
        range_end = keep_range['end']
        range_duration = range_end - range_start
        
        # Convert times to rational format using frame rate context
        new_offset = timeline_offset + range_start
        new_offset_rational = self._seconds_to_rational_time(new_offset, format_ref)
        new_start_rational = self._seconds_to_rational_time(range_start, format_ref)
        new_duration_rational = self._seconds_to_rational_time(range_duration, format_ref)
        
        # Update clip attributes with frame-accurate timing
        new_clip.set('offset', new_offset_rational)
        new_clip.set('start', new_start_rational)
        new_clip.set('duration', new_duration_rational)
        
        # Update name to indicate it's a cut segment
        original_name = new_clip.get('name', 'Multicam Clip')
        new_clip.set('name', f"{original_name} - Segment {segment_index + 1}")
        
        logger.debug(f"Created cut segment {segment_index + 1}:")
        logger.debug(f"  offset={new_offset_rational} ({new_offset:.3f}s)")
        logger.debug(f"  start={new_start_rational} ({range_start:.3f}s)")
        logger.debug(f"  duration={new_duration_rational} ({range_duration:.3f}s)")
        
        return new_clip
    
    def _find_parent_element(self, element) -> Optional[ET.Element]:
        """Find the parent element of a given element."""
        for parent in self.original_tree.iter():
            for child in parent:
                if child == element:
                    return parent
        return None
    
    def _deep_copy_element(self, element) -> ET.Element:
        """Create a deep copy of an XML element."""
        new_element = ET.Element(element.tag, element.attrib.copy())
        new_element.text = element.text
        new_element.tail = element.tail
        
        for child in element:
            new_child = self._deep_copy_element(child)
            new_element.append(new_child)
        
        return new_element
    
    def _rational_time_to_seconds(self, rational_time: str, context_format_id: Optional[str] = None) -> float:
        """Convert FCPXML rational time format to seconds using frame rate context."""
        if not rational_time or not rational_time.endswith('s'):
            return 0.0
        
        # Get frame rate context
        frame_rate_info = None
        if context_format_id and context_format_id in self.project_frame_rates:
            frame_rate_info = self.project_frame_rates[context_format_id]
        elif self.primary_frame_rate:
            frame_rate_info = self.primary_frame_rate
        
        if frame_rate_info:
            return self.frame_rate_handler.rational_time_to_seconds(rational_time, frame_rate_info)
        else:
            # Fallback conversion
            time_part = rational_time[:-1]  # Remove 's'
            try:
                if '/' in time_part:
                    numerator, denominator = time_part.split('/')
                    return float(numerator) / float(denominator)
                else:
                    return float(time_part)
            except (ValueError, ZeroDivisionError):
                logger.warning(f"Could not parse rational time: {rational_time}")
                return 0.0
    
    def _filter_ranges_by_edited_segments(self, keep_ranges: List[Dict],
                                          edited_segments: List[Dict]) -> List[Dict]:
        """
        Filter keep_ranges based on which segments are marked to keep after editing.

        Args:
            keep_ranges: Original keep ranges from transcript cleaner
            edited_segments: Edited segments with 'keep' flags

        Returns:
            Filtered list of keep ranges
        """
        filtered_ranges = []

        for keep_range in keep_ranges:
            # Check if any segment in this range should be kept
            range_start = keep_range['start']
            range_end = keep_range['end']

            # Find segments that overlap with this range
            should_keep = False
            for segment in edited_segments:
                seg_start = segment.get('start', 0)
                seg_end = segment.get('end', 0)

                # Check if segment overlaps with this range and is marked to keep
                if (seg_start < range_end and seg_end > range_start and
                    segment.get('keep', False)):
                    should_keep = True
                    break

            if should_keep:
                filtered_ranges.append(keep_range)

        logger.info(f"Filtered {len(keep_ranges)} ranges to {len(filtered_ranges)} based on edited transcript")
        return filtered_ranges

    def _seconds_to_rational_time(self, seconds: float, context_format_id: Optional[str] = None) -> str:
        """Convert seconds to FCPXML rational time format using frame rate context."""
        # Get frame rate context
        frame_rate_info = None
        if context_format_id and context_format_id in self.project_frame_rates:
            frame_rate_info = self.project_frame_rates[context_format_id]
        elif self.primary_frame_rate:
            frame_rate_info = self.primary_frame_rate

        if frame_rate_info:
            # For 29.97 DF, ensure frame alignment
            if frame_rate_info.is_drop_frame and abs(frame_rate_info.rate - 29.97) < 0.01:
                # Convert to frames first, then round to nearest frame
                total_frames = round(seconds * 29.97)
                # Convert frames to rational time (each frame is 1001/30000s)
                numerator = total_frames * 1001
                denominator = 30000
                return f"{numerator}/{denominator}s"
            else:
                return self.frame_rate_handler.seconds_to_rational_time(seconds, frame_rate_info)
        else:
            return f"{seconds}s"
    
    def _fix_dtd_validation_issues(self, root):
        """Fix common DTD validation issues in the FCPXML structure."""
        # Find all asset elements
        for asset in root.findall('.//asset'):
            # Check if asset has a media-rep element
            media_rep = asset.find('media-rep')
            if media_rep is None:
                # Asset must have at least one media-rep element according to DTD
                # Create a placeholder media-rep if missing
                logger.warning(f"Asset {asset.get('id', 'unknown')} missing media-rep, adding placeholder")

                # Create a minimal media-rep element
                media_rep = ET.Element('media-rep')
                media_rep.set('kind', 'original-media')
                media_rep.set('sig', asset.get('uid', 'placeholder'))
                media_rep.set('src', 'file:///placeholder')

                # Insert media-rep as the first child (before metadata if it exists)
                metadata = asset.find('metadata')
                if metadata is not None:
                    # Insert before metadata
                    asset.insert(0, media_rep)
                else:
                    # Just append it
                    asset.append(media_rep)

        # Remove invalid 'name' attributes from sequences (not allowed by DTD)
        for sequence in root.findall('.//sequence'):
            if 'name' in sequence.attrib:
                logger.debug(f"Removing invalid 'name' attribute from sequence")
                del sequence.attrib['name']

        # Fix any project structure issues
        project = root.find('.//project')
        if project is None:
            # If no project exists, try to find library/event and create project there
            event = root.find('.//event')
            if event is not None:
                logger.info("No project found, creating one in event")
                project = ET.Element('project')
                project.set('name', 'Auto-Cut Project')
                project.set('uid', 'auto-generated')
                project.set('modDate', datetime.now().strftime('%Y-%m-%d %H:%M:%S %z'))

                # Move any sequences from event to project
                for sequence in event.findall('sequence'):
                    event.remove(sequence)
                    project.append(sequence)

                event.append(project)

    def _save_fcpxml(self, tree: ET.ElementTree, output_path: str):
        """Save the modified FCPXML tree to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Fix any DTD validation issues before saving
        self._fix_dtd_validation_issues(tree.getroot())

        # Format the XML nicely
        self._indent_xml(tree.getroot())

        # Write the file with proper XML declaration
        with open(output_path, 'wb') as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding='UTF-8', xml_declaration=False)

        logger.debug(f"Saved FCPXML to: {output_path}")
    
    def _indent_xml(self, element, level: int = 0):
        """Add proper indentation to XML for readability."""
        indent = "  " * level
        if len(element):
            if not element.text or not element.text.strip():
                element.text = f"\n{indent}  "
            if not element.tail or not element.tail.strip():
                element.tail = f"\n{indent}"
            for child in element:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = f"\n{indent}"
        else:
            if level and (not element.tail or not element.tail.strip):
                element.tail = f"\n{indent}"
    
    def _add_cut_metadata(self, fcpxml_path: str, cleaned_data: Dict):
        """Add metadata to the FCPXML file about the cuts that were applied."""
        try:
            metadata_path = Path(fcpxml_path).with_suffix('.json')
            
            metadata = {
                'generated_by': 'Multicam Auto-Cut System',
                'generation_time': datetime.now().isoformat(),
                'original_duration': cleaned_data['timing_mapping']['total_original_duration'],
                'cleaned_duration': cleaned_data['timing_mapping']['total_cleaned_duration'],
                'time_saved': cleaned_data['timing_mapping']['total_original_duration'] - 
                             cleaned_data['timing_mapping']['total_cleaned_duration'],
                'cuts_applied': len(cleaned_data['timing_mapping']['cut_ranges']),
                'segments_kept': len(cleaned_data['timing_mapping']['keep_ranges']),
                'cleaning_stats': cleaned_data['cleaning_stats'],
                'cleaning_level': cleaned_data['cleaning_level'],
                'take_groups': len(cleaned_data['take_groups'])
            }
            
            import json
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Cut metadata saved to: {metadata_path}")
            
        except Exception as e:
            logger.warning(f"Could not save cut metadata: {e}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Cut Generator Module")
    print("=" * 20)
    print("Ready to generate frame-accurate FCPXML cuts!")
    print("Supports 29.97 DF, 24p, 25p, and mixed frame rates")
