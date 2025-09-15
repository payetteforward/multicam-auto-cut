# Multicam Auto-Cut System

An intelligent Final Cut Pro workflow automation tool that automatically cuts multicam clips based on AI-powered transcript editing, removing stutters, false starts, and filler words while preserving substantive content.

## Features

- **Automatic Audio Extraction**: Extracts lav mic audio from multicam FCPXML projects
- **AI Transcription**: Uses OpenAI Whisper API for accurate speech-to-text conversion
- **Intelligent Editing**: Claude AI removes stutters and false starts while preserving meaning
- **Frame-Accurate Cutting**: Generates FCPXML with precise 29.97 Drop Frame alignment
- **Smart Caching**: Caches transcripts to avoid repeated API calls
- **Debug Output**: Saves detailed transcript edits with timestamps for review

## Prerequisites

- Python 3.8+
- Final Cut Pro (for importing generated FCPXML files)
- OpenAI API key (for transcription)
- Anthropic API key (for transcript editing)
- FFmpeg (for audio extraction)

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/payetteforward/multicam-auto-cut.git
cd multicam-auto-cut
```

2. Install the package:
```bash
pip install -e .  # Install in development mode
# or
pip install .     # Install normally
```

3. Set up your API keys:
```bash
cp .env.example .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=your-openai-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key
```

### For Development

```bash
pip install -e ".[dev]"  # Install with development dependencies
```

## Usage

### Command Line Interface

```bash
# Basic usage
autocut input.fcpxml

# With options
autocut input.fcpxml --cleaning light --no-edit
autocut input.fcpxml -o custom_output_dir --verbose

# Get help
autocut --help
```

### Python API

```python
from src import MulticamAutoCutWorkflow

workflow = MulticamAutoCutWorkflow(
    cleaning_level="moderate",
    edit_transcript=True
)

result = workflow.process_multicam_clip(
    input_fcpxml="path/to/input.fcpxml",
    output_fcpxml="path/to/output.fcpxml"
)
```

This will:
1. Parse the FCPXML and find the multicam clip with a mono audio track (lav mic)
2. Extract and compress the audio
3. Transcribe using OpenAI Whisper
4. Clean the transcript to remove fillers
5. Edit with Claude AI to remove stutters and false starts
6. Generate a new FCPXML with cuts applied
7. Save to `outputs/[timestamp]/[filename]_AutoCut.fcpxml`

### Output Files

Each run creates a timestamped output folder containing:
- `Info_AutoCut.fcpxml` - The Final Cut Pro project file with cuts
- `Info_AutoCut.json` - Metadata about the cuts
- `edited_transcript_debug.txt` - Detailed breakdown of edits
- `source_info.txt` - Information about the source file

### Configuration

Edit `.env` to configure:
- `CLEANING_LEVEL` - Amount of filler removal (light/moderate/aggressive)
- `USE_TRANSCRIPT_CACHE` - Cache transcripts to save API calls
- `TRANSCRIPTION_MODEL` - OpenAI model selection

## Project Structure

```
multicam-auto-cut/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # Command-line interface
│   ├── config/               # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py       # Application settings
│   ├── core/                 # Core workflow logic
│   │   ├── __init__.py
│   │   └── workflow.py       # Main workflow orchestrator
│   ├── processors/           # Processing modules
│   │   ├── __init__.py
│   │   ├── fcpxml_parser.py  # FCPXML parsing
│   │   ├── audio_extractor.py # Audio extraction
│   │   ├── transcriber.py    # OpenAI Whisper integration
│   │   ├── transcript_cleaner.py # Filler removal
│   │   ├── transcript_editor.py  # Claude AI editing
│   │   └── cut_generator.py  # FCPXML generation
│   └── utils/                # Utility modules
│       ├── __init__.py
│       ├── frame_rate_handler.py # Frame-rate handling
│       ├── fcpxml_validator.py   # FCPXML validation
│       └── logging_config.py     # Logging setup
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                    # Documentation
├── outputs/                 # Generated FCPXML files
├── transcripts/            # Cached transcripts
├── temp/                   # Temporary files
├── autocut.py             # Main entry point
├── setup.py               # Package setup
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── .gitignore           # Git ignore rules
├── LICENSE              # MIT License
└── README.md           # This file
```

## How It Works

1. **Multicam Analysis**: Parses FCPXML to identify multicam clips and mono audio tracks
2. **Audio Processing**: Extracts lav mic audio and compresses to MP3
3. **Transcription**: Sends audio to OpenAI Whisper for time-coded transcription
4. **Smart Cleaning**: Removes filler words and identifies repeated takes
5. **AI Editing**: Claude analyzes the transcript to intelligently remove stutters while preserving meaning
6. **Cut Generation**: Creates frame-accurate cuts at 29.97 Drop Frame boundaries
7. **FCPXML Export**: Generates a new project with all cuts pre-applied

## Key Features Explained

### Intelligent Transcript Editing
The system uses Claude AI with a carefully crafted prompt to:
- Keep ALL meaningful content
- Only remove pure filler words (um, uh, like)
- Fix repeated words (the the → the)
- Preserve the speaker's voice and style
- When in doubt, keep the content

### Frame-Accurate Cutting
All cuts are aligned to exact frame boundaries for 29.97 Drop Frame video:
- Each frame = 1001/30000 seconds
- Prevents "not on edit frame boundary" errors
- Ensures smooth playback in Final Cut Pro

### Debug Transcript
Every edit session saves a detailed debug file showing:
- Original vs edited transcript
- Segment-by-segment breakdown with timestamps
- Statistics on what was kept/removed
- Final compiled transcript with timing

## API Costs

- **OpenAI Whisper**: ~$0.006 per minute of audio
- **Claude 3.5 Sonnet**: ~$0.003 per 1K input tokens, $0.015 per 1K output tokens
- Typical 30-minute video: ~$0.20-0.30 total

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Ensure your `.env` file contains a valid Anthropic API key

### "No mono audio track found"
The system requires a lav mic (mono) track in your multicam clip

### DTD Validation Errors
The system automatically fixes common FCPXML issues, but complex projects may need manual adjustment

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built for content creators using Final Cut Pro
- Leverages OpenAI Whisper for transcription
- Uses Claude AI for intelligent editing
- Inspired by the need for faster video editing workflows