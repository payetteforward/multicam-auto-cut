# Development Guide

## Architecture Overview

The Multicam Auto-Cut System follows a modular, pipeline-based architecture:

```
Input FCPXML → Parse → Extract Audio → Transcribe → Clean → Edit → Generate Cuts → Output FCPXML
```

## Module Responsibilities

### Core (`src/core/`)
- **workflow.py**: Orchestrates the entire pipeline, coordinates all processors

### Processors (`src/processors/`)
- **fcpxml_parser.py**: Parses FCPXML files, extracts multicam and audio track info
- **audio_extractor.py**: Extracts and compresses audio from video files
- **transcriber.py**: Interfaces with OpenAI Whisper API for transcription
- **transcript_cleaner.py**: Removes filler words and identifies repeated takes
- **transcript_editor.py**: Uses Claude AI to intelligently edit transcripts
- **cut_generator.py**: Creates frame-accurate FCPXML with cuts applied

### Utils (`src/utils/`)
- **frame_rate_handler.py**: Manages frame rate conversions and calculations
- **fcpxml_validator.py**: Validates and fixes FCPXML structure
- **logging_config.py**: Configures application-wide logging

### Config (`src/config/`)
- **settings.py**: Centralized configuration management using dataclasses

## Adding New Features

### 1. Adding a New Processor

Create a new processor in `src/processors/`:

```python
# src/processors/my_processor.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MyProcessor:
    """Description of what this processor does."""

    def __init__(self, config: Any = None):
        """Initialize the processor."""
        self.config = config

    def process(self, input_data: Dict) -> Dict:
        """
        Process the input data.

        Args:
            input_data: Input dictionary with required data

        Returns:
            Dict with processed results
        """
        logger.info("Processing data...")
        # Your processing logic here
        return {"result": "processed_data"}
```

### 2. Integrating with Workflow

Update `src/core/workflow.py` to use your processor:

```python
from ..processors import MyProcessor

# In __init__
self.my_processor = MyProcessor()

# In process_multicam_clip
result = self.my_processor.process(data)
```

### 3. Adding Configuration Options

Update `src/config/settings.py`:

```python
@dataclass
class AppSettings:
    # ... existing fields ...
    my_feature_enabled: bool = True
    my_feature_option: str = "default"
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_frame_rate_handler.py

# Run with coverage
pytest --cov=src tests/
```

### Writing Tests

Place unit tests in `tests/unit/` and integration tests in `tests/integration/`:

```python
# tests/unit/test_my_processor.py
import pytest
from src.processors import MyProcessor

class TestMyProcessor:
    def test_process(self):
        processor = MyProcessor()
        result = processor.process({"input": "data"})
        assert result["result"] == "expected_output"
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and returns
- Add docstrings to all classes and public methods
- Keep functions focused and under 50 lines
- Use meaningful variable names

### Formatting

```bash
# Format code
make format

# Check linting
make lint
```

## Error Handling

Always handle errors gracefully:

```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    # Return sensible default or re-raise
    return default_value
```

## Logging

Use appropriate log levels:

```python
logger.debug("Detailed information for debugging")
logger.info("General information about progress")
logger.warning("Something unexpected but handled")
logger.error("Error that needs attention")
```

## Performance Considerations

1. **Caching**: Use transcript caching to avoid repeated API calls
2. **Async Operations**: Consider async for I/O-bound operations
3. **Memory**: Stream large files instead of loading entirely into memory
4. **Batch Processing**: Group API calls when possible

## API Integration

When adding new AI services:

1. Add API key to `.env.example`
2. Update `AppSettings` in `src/config/settings.py`
3. Create a new processor in `src/processors/`
4. Handle rate limiting and retries
5. Add appropriate error handling

## Release Process

1. Update version in `setup.py` and `src/__init__.py`
2. Update CHANGELOG.md
3. Run full test suite
4. Create git tag: `git tag v1.0.0`
5. Push to GitHub: `git push origin main --tags`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Debugging Tips

- Use `--verbose` flag for detailed logging
- Check `outputs/*/edited_transcript_debug.txt` for transcript editing details
- Temporary files in `temp/` are kept with `--keep-temp` flag
- Use Python debugger: `import pdb; pdb.set_trace()`

## Common Issues

### Import Errors
Ensure you're running from the project root and have installed the package:
```bash
pip install -e .
```

### API Key Issues
Check that `.env` file exists and contains valid keys:
```bash
cat .env | grep API_KEY
```

### Frame Alignment Errors
All timecodes must align to frame boundaries for 29.97 DF:
- Each frame = 1001/30000 seconds
- Use `FrameRateHandler` for conversions