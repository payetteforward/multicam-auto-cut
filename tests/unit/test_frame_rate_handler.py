"""Unit tests for the FrameRateHandler."""

import pytest
from src.utils import FrameRateHandler, FrameRateInfo


class TestFrameRateHandler:
    """Test frame rate handling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = FrameRateHandler()

    def test_detect_2997_drop_frame(self):
        """Test detection of 29.97 drop frame format."""
        info = self.handler.detect_frame_rate_from_format("FFVideoFormat3840x2160p2997")
        assert info is not None
        assert info.rate == pytest.approx(29.97, 0.01)
        assert info.is_drop_frame is True
        assert info.name == "29.97 fps Drop Frame"

    def test_seconds_to_rational_time_2997df(self):
        """Test conversion of seconds to rational time for 29.97 DF."""
        info = FrameRateInfo(
            rate=29.97,
            timebase="1001",
            timescale="30000",
            is_drop_frame=True,
            name="29.97 fps Drop Frame",
            fcpxml_duration_format="1001/30000s"
        )

        # Test exact frame boundary (1 frame = 1001/30000s)
        result = self.handler._seconds_to_rational_for_frame_rate(1001/30000, info)
        assert result == "1001/30000s"

        # Test 1 second (should be 30 frames in 29.97)
        result = self.handler._seconds_to_rational_for_frame_rate(1.0, info)
        assert result == "30030/30000s"

    def test_rational_time_to_seconds(self):
        """Test conversion of rational time to seconds."""
        handler = FrameRateHandler()

        # Test basic conversion
        assert handler.rational_time_to_seconds("30000/30000s") == 1.0
        assert handler.rational_time_to_seconds("1001/30000s") == pytest.approx(0.03336666, 0.0001)

        # Test invalid format
        assert handler.rational_time_to_seconds("invalid") == 0.0