"""
Frame Rate Handler Module
Handles various frame rates including 29.97 drop frame, mixed frame rates, and accurate timing conversions.
"""

import re
import logging
from typing import Dict, Optional, Tuple, Union
from fractions import Fraction
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class FrameRateInfo:
    """Information about a specific frame rate."""
    rate: float                    # Actual frame rate (e.g., 29.97)
    timebase: int                 # Timebase denominator (e.g., 30000)
    timescale: int                # Timescale numerator (e.g., 1001) 
    is_drop_frame: bool           # True for drop frame timecode
    name: str                     # Human readable name
    fcpxml_duration_format: str   # Format string for FCPXML durations

class FrameRateHandler:
    """
    Handles frame rate detection, conversion, and timing calculations for multicam clips.
    """
    
    # Standard frame rate definitions
    FRAME_RATES = {
        # Non-drop frame rates
        '23.976': FrameRateInfo(23.976, 24000, 1001, False, '23.976 fps', '1001/24000s'),
        '24': FrameRateInfo(24.0, 24, 1, False, '24 fps', '1/24s'),
        '25': FrameRateInfo(25.0, 25, 1, False, '25 fps (PAL)', '1/25s'),
        '29.97': FrameRateInfo(29.97, 30000, 1001, False, '29.97 fps', '1001/30000s'),
        '30': FrameRateInfo(30.0, 30, 1, False, '30 fps', '1/30s'),
        '50': FrameRateInfo(50.0, 50, 1, False, '50 fps', '1/50s'),
        '59.94': FrameRateInfo(59.94, 60000, 1001, False, '59.94 fps', '1001/60000s'),
        '60': FrameRateInfo(60.0, 60, 1, False, '60 fps', '1/60s'),
        
        # Drop frame variants (primarily for 29.97)
        '29.97df': FrameRateInfo(29.97, 30000, 1001, True, '29.97 fps Drop Frame', '1001/30000s'),
        '59.94df': FrameRateInfo(59.94, 60000, 1001, True, '59.94 fps Drop Frame', '1001/60000s'),
    }
    
    def __init__(self):
        """Initialize the frame rate handler."""
        self.detected_rates = {}  # Cache for detected rates

    def get_primary_frame_rate(self, detected_rates: Dict) -> FrameRateInfo:
        """
        Determine the primary frame rate from detected rates.

        Args:
            detected_rates: Dictionary of detected frame rates

        Returns:
            FrameRateInfo: The primary frame rate to use
        """
        if not detected_rates:
            # Default to 29.97 DF if no rates detected
            return self.FRAME_RATES['29.97df']

        # Return the first detected rate as primary
        first_rate = list(detected_rates.values())[0]
        if isinstance(first_rate, FrameRateInfo):
            return first_rate
        elif isinstance(first_rate, dict):
            # Reconstruct FrameRateInfo from dict
            return FrameRateInfo(
                rate=first_rate.get('rate', 29.97),
                timebase=first_rate.get('timebase', 30000),
                timescale=first_rate.get('timescale', 1001),
                is_drop_frame=first_rate.get('is_drop_frame', True),
                name=first_rate.get('name', '29.97 fps Drop Frame'),
                fcpxml_duration_format=first_rate.get('fcpxml_duration_format', '1001/30000s')
            )
        else:
            # Fallback to 29.97 DF
            return self.FRAME_RATES['29.97df']

    def detect_frame_rate_from_fcpxml_format(self, format_element) -> Optional[FrameRateInfo]:
        """
        Detect frame rate from FCPXML format element.
        
        Args:
            format_element: XML format element from FCPXML
            
        Returns:
            FrameRateInfo: Detected frame rate information
        """
        if format_element is None:
            return None
            
        frame_duration = format_element.get('frameDuration')
        format_name = format_element.get('name', '')
        
        if not frame_duration:
            return None
            
        # Parse frame duration (e.g., "1001/30000s")
        rate_info = self._parse_frame_duration(frame_duration)
        if rate_info:
            # Check if it's drop frame based on format name or other indicators
            is_drop_frame = self._is_drop_frame_format(format_name)
            if is_drop_frame:
                rate_info.is_drop_frame = True
                rate_info.name += " Drop Frame"
            
            logger.info(f"Detected frame rate: {rate_info.name} from format '{format_name}'")
            return rate_info
            
        return None
    
    def detect_frame_rate_from_sequence(self, sequence_element) -> Optional[FrameRateInfo]:
        """
        Detect frame rate from FCPXML sequence element.
        
        Args:
            sequence_element: XML sequence element
            
        Returns:
            FrameRateInfo: Detected frame rate information
        """
        if sequence_element is None:
            return None
            
        # Check tcFormat for drop frame indication
        tc_format = sequence_element.get('tcFormat', '')
        is_drop_frame = tc_format == 'DF'
        
        # Get format reference
        format_ref = sequence_element.get('format')
        if format_ref and format_ref in self.detected_rates:
            rate_info = self.detected_rates[format_ref]
            if is_drop_frame and not rate_info.is_drop_frame:
                # Create drop frame variant
                rate_info = FrameRateInfo(
                    rate_info.rate,
                    rate_info.timebase,
                    rate_info.timescale,
                    True,
                    rate_info.name + " Drop Frame",
                    rate_info.fcpxml_duration_format
                )
            return rate_info
            
        return None
    
    def _parse_frame_duration(self, frame_duration: str) -> Optional[FrameRateInfo]:
        """
        Parse FCPXML frame duration string to determine frame rate.
        
        Args:
            frame_duration (str): Frame duration like "1001/30000s"
            
        Returns:
            FrameRateInfo: Frame rate information
        """
        if not frame_duration.endswith('s'):
            return None
            
        duration_part = frame_duration[:-1]  # Remove 's'
        
        try:
            if '/' in duration_part:
                numerator, denominator = duration_part.split('/')
                frame_time = float(numerator) / float(denominator)
                frame_rate = 1.0 / frame_time
                
                # Match to known frame rates
                for rate_key, rate_info in self.FRAME_RATES.items():
                    if abs(frame_rate - rate_info.rate) < 0.01:  # Allow small tolerance
                        return FrameRateInfo(
                            rate_info.rate,
                            int(denominator),
                            int(numerator),
                            False,  # Will be set later if drop frame
                            rate_info.name,
                            frame_duration
                        )
                
                # Create custom frame rate if not in standards
                return FrameRateInfo(
                    frame_rate,
                    int(denominator),
                    int(numerator),
                    False,
                    f"{frame_rate:.3f} fps",
                    frame_duration
                )
            else:
                frame_time = float(duration_part)
                frame_rate = 1.0 / frame_time
                return FrameRateInfo(
                    frame_rate,
                    1,
                    1,
                    False,
                    f"{frame_rate:.3f} fps",
                    frame_duration
                )
                
        except (ValueError, ZeroDivisionError):
            logger.warning(f"Could not parse frame duration: {frame_duration}")
            return None
    
    def _is_drop_frame_format(self, format_name: str) -> bool:
        """
        Determine if a format name indicates drop frame.
        
        Args:
            format_name (str): Format name from FCPXML
            
        Returns:
            bool: True if drop frame format
        """
        format_name_lower = format_name.lower()
        drop_indicators = ['2997', '5994', 'df', 'drop', 'dropframe']
        return any(indicator in format_name_lower for indicator in drop_indicators)
    
    def rational_time_to_seconds(self, rational_time: str, 
                                frame_rate_info: Optional[FrameRateInfo] = None) -> float:
        """
        Convert FCPXML rational time to seconds, accounting for frame rate.
        
        Args:
            rational_time (str): Time like "3723/25s" or "600s"
            frame_rate_info (FrameRateInfo, optional): Frame rate context
            
        Returns:
            float: Time in seconds
        """
        if not rational_time or not rational_time.endswith('s'):
            return 0.0
            
        time_part = rational_time[:-1]  # Remove 's'
        
        try:
            if '/' in time_part:
                numerator, denominator = time_part.split('/')
                seconds = float(numerator) / float(denominator)
            else:
                seconds = float(time_part)
            
            # Apply drop frame correction if needed
            if frame_rate_info and frame_rate_info.is_drop_frame:
                seconds = self._apply_drop_frame_correction(seconds, frame_rate_info)
            
            return seconds
            
        except (ValueError, ZeroDivisionError):
            logger.warning(f"Could not parse rational time: {rational_time}")
            return 0.0
    
    def seconds_to_rational_time(self, seconds: float, 
                               frame_rate_info: FrameRateInfo) -> str:
        """
        Convert seconds to FCPXML rational time format.
        
        Args:
            seconds (float): Time in seconds
            frame_rate_info (FrameRateInfo): Frame rate information
            
        Returns:
            str: Rational time format
        """
        # Apply drop frame correction if needed
        if frame_rate_info.is_drop_frame:
            seconds = self._reverse_drop_frame_correction(seconds, frame_rate_info)
        
        if frame_rate_info.timescale == 1:
            return f"{seconds}s"
        else:
            # Use the frame rate's specific timebase
            numerator = int(seconds * frame_rate_info.timebase)
            return f"{numerator}/{frame_rate_info.timebase}s"
    
    def _apply_drop_frame_correction(self, seconds: float, 
                                   frame_rate_info: FrameRateInfo) -> float:
        """
        Apply drop frame timecode correction to convert to real time.
        
        Args:
            seconds (float): Timecode seconds
            frame_rate_info (FrameRateInfo): Frame rate information
            
        Returns:
            float: Corrected real-time seconds
        """
        if not frame_rate_info.is_drop_frame:
            return seconds
            
        # Drop frame correction primarily applies to 29.97
        if abs(frame_rate_info.rate - 29.97) < 0.01:
            # 29.97 drop frame: 2 frames dropped every minute except every 10th minute
            # This creates a slight time compression
            total_frames = seconds * 29.97
            
            # Calculate minutes and apply drop frame formula
            minutes = int(total_frames / (29.97 * 60))
            dropped_frames = minutes * 2 - (minutes // 10) * 2
            
            # Convert back to real time
            real_frames = total_frames + dropped_frames
            return real_frames / 29.97
            
        # For other drop frame rates, apply similar logic
        elif abs(frame_rate_info.rate - 59.94) < 0.01:
            total_frames = seconds * 59.94
            minutes = int(total_frames / (59.94 * 60))
            dropped_frames = minutes * 4 - (minutes // 10) * 4  # 4 frames dropped for 59.94
            real_frames = total_frames + dropped_frames
            return real_frames / 59.94
            
        return seconds  # No correction for other rates
    
    def _reverse_drop_frame_correction(self, real_seconds: float, 
                                     frame_rate_info: FrameRateInfo) -> float:
        """
        Reverse drop frame correction to convert real time back to timecode.
        
        Args:
            real_seconds (float): Real time seconds
            frame_rate_info (FrameRateInfo): Frame rate information
            
        Returns:
            float: Timecode seconds
        """
        if not frame_rate_info.is_drop_frame:
            return real_seconds
            
        # This is the inverse of the drop frame correction
        # For 29.97 drop frame
        if abs(frame_rate_info.rate - 29.97) < 0.01:
            real_frames = real_seconds * 29.97
            # Estimate minutes and calculate dropped frames
            estimated_minutes = int(real_frames / (29.97 * 60))
            dropped_frames = estimated_minutes * 2 - (estimated_minutes // 10) * 2
            timecode_frames = real_frames - dropped_frames
            return timecode_frames / 29.97
            
        elif abs(frame_rate_info.rate - 59.94) < 0.01:
            real_frames = real_seconds * 59.94
            estimated_minutes = int(real_frames / (59.94 * 60))
            dropped_frames = estimated_minutes * 4 - (estimated_minutes // 10) * 4
            timecode_frames = real_frames - dropped_frames
            return timecode_frames / 59.94
            
        return real_seconds

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Frame Rate Handler Test")
    print("=" * 23)
    
    handler = FrameRateHandler()
    
    # Test frame rate detection
    test_durations = [
        "1001/30000s",  # 29.97 fps
        "1/24s",        # 24 fps
        "1/25s",        # 25 fps PAL
        "1001/24000s",  # 23.976 fps
        "1/30s",        # 30 fps
    ]
    
    print("Frame Rate Detection:")
    for duration in test_durations:
        rate_info = handler._parse_frame_duration(duration)
        if rate_info:
            print(f"  {duration} → {rate_info.name} ({rate_info.rate} fps)")
    
    print("\n✅ Frame rate handler is ready!")
    print("   Supports: 23.976, 24, 25, 29.97, 30, 50, 59.94, 60 fps")
    print("   Drop frame: 29.97 DF, 59.94 DF")
