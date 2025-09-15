"""
FCPXML Parser Module
Handles parsing of Final Cut Pro X XML files to extract multicam clip structure and audio track information.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from ..utils import FrameRateHandler, FrameRateInfo

# Set up logging
logger = logging.getLogger(__name__)

class FCPXMLParser:
    """
    Parser for Final Cut Pro X XML files with focus on multicam clips.
    """
    
    def __init__(self):
        self.tree = None
        self.root = None
        self.resources = {}
        self.multicam_clips = []
        self.frame_rate_handler = FrameRateHandler()
        self.detected_frame_rates = {}
        self.primary_frame_rate = None
        
    def parse_fcpxml(self, file_path: str) -> Dict:
        """
        Parse an FCPXML file and extract relevant information.
        
        Args:
            file_path (str): Path to the FCPXML file
            
        Returns:
            Dict: Parsed FCPXML data structure
        """
        try:
            # Parse the XML file
            self.tree = ET.parse(file_path)
            self.root = self.tree.getroot()
            
            # Extract basic information
            fcpxml_data = {
                'version': self.root.get('version'),
                'file_path': file_path,
                'resources': self._parse_resources(),
                'projects': self._parse_projects(),
                'multicam_clips': self._find_multicam_clips(),
                'frame_rates': self._detect_and_validate_frame_rates(),
                'primary_frame_rate': self.primary_frame_rate.__dict__ if self.primary_frame_rate else None
            }
            
            logger.info(f"Successfully parsed FCPXML file: {file_path}")
            logger.info(f"Found {len(fcpxml_data['multicam_clips'])} multicam clips")
            logger.info(f"Primary frame rate: {self.primary_frame_rate.name if self.primary_frame_rate else 'Unknown'}")
            
            return fcpxml_data
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise
        except FileNotFoundError:
            logger.error(f"FCPXML file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing FCPXML: {e}")
            raise
    
    def _parse_resources(self) -> Dict:
        """
        Parse the resources section to get asset and format information.
        
        Returns:
            Dict: Resources information
        """
        resources = {}
        
        resources_element = self.root.find('resources')
        if resources_element is None:
            logger.warning("No resources section found in FCPXML")
            return resources
        
        # Parse assets (media files)
        for asset in resources_element.findall('asset'):
            asset_id = asset.get('id')
            resources[asset_id] = {
                'type': 'asset',
                'name': asset.get('name'),
                'uid': asset.get('uid'),
                'start': asset.get('start'),
                'duration': asset.get('duration'),
                'hasVideo': asset.get('hasVideo') == '1',
                'hasAudio': asset.get('hasAudio') == '1',
                'audioSources': int(asset.get('audioSources', 0)),
                'audioChannels': int(asset.get('audioChannels', 0)),
                'audioRate': asset.get('audioRate'),
                'media_path': self._extract_media_path(asset)
            }
        
        # Parse formats
        for format_elem in resources_element.findall('format'):
            format_id = format_elem.get('id')
            resources[format_id] = {
                'type': 'format',
                'name': format_elem.get('name'),
                'frameDuration': format_elem.get('frameDuration'),
                'width': format_elem.get('width'),
                'height': format_elem.get('height'),
                'colorSpace': format_elem.get('colorSpace')
            }
        
        # Parse multicam clips in resources
        for mc_clip in resources_element.findall('mc-clip'):
            mc_id = mc_clip.get('id')
            resources[mc_id] = {
                'type': 'multicam',
                'name': mc_clip.get('name'),
                'angles': self._parse_multicam_angles(mc_clip)
            }
        
        return resources
    
    def _extract_media_path(self, asset_element) -> Optional[str]:
        """
        Extract the file path from an asset element.
        
        Args:
            asset_element: XML element for the asset
            
        Returns:
            str: File path or None if not found
        """
        media_rep = asset_element.find('media-rep')
        if media_rep is not None:
            src = media_rep.get('src')
            if src and src.startswith('file://'):
                return src.replace('file://', '')
        return None
    
    def _parse_multicam_angles(self, mc_clip_element) -> List[Dict]:
        """
        Parse the angles within a multicam clip.
        
        Args:
            mc_clip_element: XML element for the multicam clip
            
        Returns:
            List[Dict]: List of angle information
        """
        angles = []
        
        for angle in mc_clip_element.findall('mc-angle'):
            angle_name = angle.get('name', f"Angle {len(angles) + 1}")
            angle_id = angle.get('angleID', str(len(angles) + 1))
            
            # Find assets within this angle
            angle_assets = []
            for asset_clip in angle.findall('.//asset-clip'):
                angle_assets.append({
                    'ref': asset_clip.get('ref'),
                    'name': asset_clip.get('name'),
                    'offset': asset_clip.get('offset'),
                    'start': asset_clip.get('start'),
                    'duration': asset_clip.get('duration')
                })
            
            angles.append({
                'name': angle_name,
                'id': angle_id,
                'assets': angle_assets
            })
        
        return angles
    
    def _parse_projects(self) -> List[Dict]:
        """
        Parse project information from the FCPXML.
        
        Returns:
            List[Dict]: List of projects
        """
        projects = []
        
        for project in self.root.findall('project'):
            projects.append({
                'name': project.get('name'),
                'uid': project.get('uid'),
                'modDate': project.get('modDate')
            })
        
        return projects
    
    def _find_multicam_clips(self) -> List[Dict]:
        """
        Find all multicam clips referenced in the timeline.
        
        Returns:
            List[Dict]: List of multicam clip references
        """
        multicam_clips = []
        
        # Look for mc-clip elements in the timeline
        for mc_clip in self.root.findall('.//mc-clip'):
            clip_ref = mc_clip.get('ref')
            clip_data = {
                'ref': clip_ref,
                'name': mc_clip.get('name'),
                'offset': mc_clip.get('offset'),
                'start': mc_clip.get('start'),
                'duration': mc_clip.get('duration'),
                'angles': self._parse_multicam_angles(mc_clip) if not clip_ref else None
            }
            multicam_clips.append(clip_data)
        
        return multicam_clips
    
    def _detect_and_validate_frame_rates(self) -> Dict[str, Dict]:
        """
        Detect all frame rates in the project and validate for mixed rates.
        
        Returns:
            Dict[str, Dict]: Frame rate information for each resource
        """
        logger.info("🎬 Detecting frame rates...")
        
        frame_rates = {}
        
        # Detect from format resources
        resources_element = self.root.find('resources')
        if resources_element is not None:
            for format_elem in resources_element.findall('format'):
                format_id = format_elem.get('id')
                rate_info = self.frame_rate_handler.detect_frame_rate_from_fcpxml_format(format_elem)
                if rate_info:
                    frame_rates[format_id] = rate_info.__dict__
                    self.detected_frame_rates[format_id] = rate_info
        
        # Detect from sequence elements
        for sequence in self.root.findall('.//sequence'):
            sequence_rate = self.frame_rate_handler.detect_frame_rate_from_sequence(sequence)
            if sequence_rate:
                sequence_format = sequence.get('format', 'sequence')
                frame_rates[f"sequence_{sequence_format}"] = sequence_rate.__dict__
                self.detected_frame_rates[f"sequence_{sequence_format}"] = sequence_rate
        
        # Determine primary frame rate
        if self.detected_frame_rates:
            self.primary_frame_rate = self.frame_rate_handler.get_primary_frame_rate(self.detected_frame_rates)
            logger.info(f"✅ Primary frame rate: {self.primary_frame_rate.name}")
            
            # Check for mixed frame rates
            unique_rates = set()
            for rate_info in self.detected_frame_rates.values():
                rate_key = f"{rate_info.rate}{'_df' if rate_info.is_drop_frame else ''}"
                unique_rates.add(rate_key)
            
            if len(unique_rates) > 1:
                logger.warning(f"⚠️  Mixed frame rates detected: {len(unique_rates)} different rates")
                for rate_id, rate_info in self.detected_frame_rates.items():
                    logger.info(f"   {rate_id}: {rate_info.name}")
        else:
            # Default to 29.97 drop frame if nothing detected
            logger.warning("No frame rates detected, defaulting to 29.97 Drop Frame")
            self.primary_frame_rate = self.frame_rate_handler.FRAME_RATES['29.97df']
            frame_rates['default'] = self.primary_frame_rate.__dict__
        
        return frame_rates
    
    def find_mono_audio_track(self, fcpxml_data: Dict) -> Optional[Dict]:
        """
        Find the mono audio track (likely the lav mic) in the multicam clip.
        
        Args:
            fcpxml_data (Dict): Parsed FCPXML data
            
        Returns:
            Dict: Information about the mono audio track, or None if not found
        """
        for resource_id, resource in fcpxml_data['resources'].items():
            if (resource.get('type') == 'asset' and 
                resource.get('hasAudio') and 
                resource.get('audioChannels') == 1):  # Mono track
                
                logger.info(f"Found mono audio track: {resource['name']}")
                return {
                    'resource_id': resource_id,
                    'name': resource['name'],
                    'media_path': resource['media_path'],
                    'duration': resource['duration'],
                    'audioRate': resource['audioRate']
                }
        
        logger.warning("No mono audio track found in FCPXML")
        return None
    
    def get_timeline_duration(self, fcpxml_data: Dict) -> Optional[str]:
        """
        Get the total duration of the timeline.
        
        Args:
            fcpxml_data (Dict): Parsed FCPXML data
            
        Returns:
            str: Duration in FCPXML time format
        """
        sequence = self.root.find('.//sequence')
        if sequence is not None:
            return sequence.get('duration')
        return None
    
    def rational_time_to_seconds(self, rational_time: str, 
                                context_format_id: Optional[str] = None) -> float:
        """
        Convert FCPXML rational time format to seconds using appropriate frame rate.
        
        Args:
            rational_time (str): Time in format like "3723/25s"
            context_format_id (str, optional): Format ID for frame rate context
            
        Returns:
            float: Time in seconds
        """
        if not rational_time or not rational_time.endswith('s'):
            return 0.0
        
        # Get frame rate context
        frame_rate_info = None
        if context_format_id and context_format_id in self.detected_frame_rates:
            frame_rate_info = self.detected_frame_rates[context_format_id]
        elif self.primary_frame_rate:
            frame_rate_info = self.primary_frame_rate
        
        # Use frame rate handler for conversion
        if frame_rate_info:
            return self.frame_rate_handler.rational_time_to_seconds(rational_time, frame_rate_info)
        else:
            # Fallback to simple conversion
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

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    parser = FCPXMLParser()
    print("FCPXML Parser with Frame Rate Support")
    print("=====================================")
    print("Ready to parse multicam FCPXML files with accurate frame rate handling!")
    print("Supports: 29.97 DF, 24p, 25p, 30p, and mixed frame rates")
