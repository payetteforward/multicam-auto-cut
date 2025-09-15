#!/usr/bin/env python3
"""
Main entry point for the Multicam Auto-Cut System.

Usage:
    python autocut.py input.fcpxml
    python autocut.py input.fcpxml --no-edit
    python autocut.py input.fcpxml --cleaning light
"""

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())