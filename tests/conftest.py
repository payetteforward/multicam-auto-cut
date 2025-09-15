"""Pytest configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path
import shutil

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)

@pytest.fixture
def sample_fcpxml():
    """Provide sample FCPXML content for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<fcpxml version="1.11">
    <resources>
        <format id="r1" name="FFVideoFormat3840x2160p2997"/>
        <media id="r2" name="Test Media">
            <multicam format="r1" tcStart="0s" tcFormat="DF">
                <mc-angle name="Test Angle" angleID="1">
                    <asset-clip ref="r3" lane="1" offset="0s"/>
                </mc-angle>
            </multicam>
        </media>
    </resources>
    <library>
        <event name="Test Event">
            <project name="Test Project">
                <sequence format="r1" tcStart="0s" tcFormat="DF" duration="30030/1001s">
                    <spine>
                        <mc-clip ref="r2" lane="1" offset="0s" name="Test Multicam" duration="30030/1001s"/>
                    </spine>
                </sequence>
            </project>
        </event>
    </library>
</fcpxml>"""

@pytest.fixture
def mock_settings(monkeypatch):
    """Mock application settings for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from src.config import AppSettings
    return AppSettings.from_env()