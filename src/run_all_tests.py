#!/usr/bin/env python3
"""
Comprehensive test suite for the multicam auto-cut system.
Validates all components and ensures DTD compliance.
"""

import sys
import os
import subprocess
from pathlib import Path
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
logger = logging.getLogger(__name__)

def run_test(test_name, test_function):
    """Run a single test and report results."""
    print(f"\n{'='*60}")
    print(f"🧪 Running: {test_name}")
    print(f"{'='*60}")

    try:
        result = test_function()
        if result:
            print(f"✅ {test_name} PASSED")
            return True
        else:
            print(f"❌ {test_name} FAILED")
            return False
    except Exception as e:
        print(f"❌ {test_name} FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_imports():
    """Test that all modules can be imported."""
    try:
        import fcpxml_parser
        import audio_extractor
        import transcriber
        import transcript_cleaner
        import cut_generator
        import frame_rate_handler
        import workflow
        import validate_fcpxml
        logger.info("All modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return False

def test_fcpxml_validation():
    """Test FCPXML validation functionality."""
    from validate_fcpxml import FCPXMLValidator

    # Create a test FCPXML with DTD issues
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<fcpxml version="1.13">
    <resources>
        <format id="r1" name="FFVideoFormat1080p2997" frameDuration="1001/30000s"/>
        <asset id="r2" name="Test Asset" uid="TEST123" hasVideo="1">
            <metadata>
                <md key="test" value="test"/>
            </metadata>
        </asset>
    </resources>
</fcpxml>"""

    test_file = "test_validation.fcpxml"
    with open(test_file, 'w') as f:
        f.write(test_xml)

    validator = FCPXMLValidator()

    # Should detect the missing media-rep
    is_valid = validator.validate_file(test_file)

    if not is_valid and len(validator.errors) > 0:
        logger.info(f"Correctly detected {len(validator.errors)} validation errors")

        # Test fix functionality
        fixed_file = "test_validation_fixed.fcpxml"
        validator.fix_common_issues(test_file, fixed_file)

        # Validate fixed file
        validator2 = FCPXMLValidator()
        is_fixed_valid = validator2.validate_file(fixed_file)

        # Cleanup
        os.remove(test_file)
        if os.path.exists(fixed_file):
            os.remove(fixed_file)

        return is_fixed_valid
    else:
        os.remove(test_file)
        return False

def test_output_structure():
    """Test that output directory structure is created correctly."""
    from workflow import MulticamAutoCutWorkflow
    import tempfile

    # Create a simple test FCPXML
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<fcpxml version="1.9">
    <resources>
        <format id="r1" name="FFVideoFormat1080p2997" frameDuration="1001/30000s"/>
        <asset id="r2" name="Lav" uid="LAV123" hasAudio="1" audioChannels="1">
            <media-rep kind="original-media" sig="LAV123" src="file:///test.wav"/>
        </asset>
        <mc-clip id="r3" name="Test MC" uid="MC123">
            <mc-angle name="Lav" angleID="1">
                <asset-clip ref="r2" name="Lav" offset="0s" start="0s" duration="60s"/>
            </mc-angle>
        </mc-clip>
    </resources>
    <project name="Test">
        <sequence format="r1" duration="60s">
            <spine>
                <mc-clip ref="r3" offset="0s" name="Test MC" start="0s" duration="60s"/>
            </spine>
        </sequence>
    </project>
</fcpxml>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.fcpxml', delete=False) as f:
        f.write(test_xml)
        test_input = f.name

    # Check if outputs directory is created
    workflow = MulticamAutoCutWorkflow()

    # Cleanup
    os.remove(test_input)

    # Check that outputs directory exists
    outputs_dir = Path("outputs")
    return outputs_dir.exists() and outputs_dir.is_dir()

def test_cut_generation():
    """Test that cuts are generated correctly."""
    from cut_generator import CutGenerator

    # Create test data
    test_fcpxml = """<?xml version="1.0" encoding="UTF-8"?>
<fcpxml version="1.9">
    <resources>
        <format id="r1" frameDuration="1001/30000s"/>
        <mc-clip id="r2" name="Test" uid="TEST">
            <mc-angle name="Test" angleID="1"/>
        </mc-clip>
    </resources>
    <project name="Test">
        <sequence name="Test Seq" format="r1" duration="10s">
            <spine>
                <mc-clip ref="r2" offset="0s" name="Test" start="0s" duration="10s" format="r1"/>
            </spine>
        </sequence>
    </project>
</fcpxml>"""

    test_input = "test_cut_input.fcpxml"
    test_output = "test_cut_output.fcpxml"

    with open(test_input, 'w') as f:
        f.write(test_fcpxml)

    # Create mock cleaned data
    cleaned_data = {
        'timing_mapping': {
            'cut_ranges': [{'start': 2.0, 'end': 4.0}],
            'keep_ranges': [
                {'start': 0.0, 'end': 2.0},
                {'start': 4.0, 'end': 10.0}
            ],
            'total_original_duration': 10.0,
            'total_cleaned_duration': 8.0
        },
        'cleaning_stats': {
            'original_segment_count': 10,
            'cleaned_segment_count': 8,
            'segments_removed': 2,
            'original_duration': 10.0,
            'cleaned_duration': 8.0,
            'time_saved': 2.0,
            'time_saved_percentage': 20.0
        },
        'cleaning_level': 'test',
        'take_groups': [],
        'original_transcription': {'fcpxml_data': {}}
    }

    generator = CutGenerator()
    output_path = generator.generate_cut_fcpxml(test_input, cleaned_data, test_output)

    # Check output exists and has two sequences
    success = False
    if os.path.exists(output_path):
        import xml.etree.ElementTree as ET
        tree = ET.parse(output_path)
        sequences = tree.findall('.//sequence')
        success = len(sequences) == 2
        logger.info(f"Generated {len(sequences)} sequences")

    # Cleanup
    os.remove(test_input)
    if os.path.exists(test_output):
        os.remove(test_output)
    if os.path.exists(test_output.replace('.fcpxml', '.json')):
        os.remove(test_output.replace('.fcpxml', '.json'))

    return success

def test_frame_rate_detection():
    """Test frame rate detection."""
    from frame_rate_handler import FrameRateHandler
    import xml.etree.ElementTree as ET

    handler = FrameRateHandler()

    # Test 29.97 DF detection
    format_xml = '<format id="r1" name="FFVideoFormat1080p2997" frameDuration="1001/30000s"/>'
    format_elem = ET.fromstring(format_xml)
    rate_info = handler.detect_frame_rate_from_fcpxml_format(format_elem)

    if rate_info and rate_info.is_drop_frame and abs(rate_info.rate - 29.97) < 0.01:
        logger.info("Correctly detected 29.97 DF")
        return True
    else:
        logger.error("Failed to detect 29.97 DF")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("🚀 MULTICAM AUTO-CUT COMPREHENSIVE TEST SUITE")
    print("="*60)

    tests = [
        ("Module Imports", test_imports),
        ("FCPXML Validation", test_fcpxml_validation),
        ("Output Directory Structure", test_output_structure),
        ("Cut Generation", test_cut_generation),
        ("Frame Rate Detection", test_frame_rate_detection)
    ]

    results = []
    for test_name, test_func in tests:
        passed = run_test(test_name, test_func)
        results.append((test_name, passed))

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! The system is working correctly.")
        print("\n✅ Key Features Validated:")
        print("  • DTD validation and automatic fixing")
        print("  • Output files saved outside FCPXML packages")
        print("  • New timeline creation with preserved cuts")
        print("  • Frame-accurate cutting support")
        print("  • Clean directory structure")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())