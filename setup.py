#!/usr/bin/env python3
"""
Setup script for Multicam Auto-Cut System
Helps users configure their environment and API keys.
"""

import os
import sys
from pathlib import Path
import shutil

def setup_environment():
    """Interactive setup for the environment."""
    print("\n🎬 MULTICAM AUTO-CUT SETUP")
    print("=" * 40)

    # Check if .env already exists
    env_file = Path('.env')
    env_example = Path('.env.example')

    if env_file.exists():
        response = input("\n⚠️  .env file already exists. Overwrite? [y/N]: ").strip().lower()
        if response != 'y':
            print("Keeping existing .env file.")
            return

    # Copy .env.example to .env
    if env_example.exists():
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
    else:
        print("❌ .env.example not found. Creating new .env file...")

    # Get OpenAI API key
    print("\n📝 OPENAI API KEY SETUP")
    print("-" * 40)
    print("Get your API key from: https://platform.openai.com/api-keys")
    api_key = input("Enter your OpenAI API key (or press Enter to skip): ").strip()

    if api_key:
        # Update .env file with the API key
        update_env_file('OPENAI_API_KEY', api_key)
        print("✅ API key saved to .env file")
    else:
        print("⚠️  No API key provided. You'll need to add it to .env manually.")

    # Ask about other settings
    print("\n⚙️  OPTIONAL SETTINGS")
    print("-" * 40)

    # Cleaning level
    print("\nTranscript cleaning level:")
    print("  1. light - Minimal cleaning")
    print("  2. moderate - Balanced (default)")
    print("  3. aggressive - Maximum cleaning")
    choice = input("Select [1-3, or Enter for default]: ").strip()

    if choice == '1':
        update_env_file('CLEANING_LEVEL', 'light')
    elif choice == '3':
        update_env_file('CLEANING_LEVEL', 'aggressive')

    # Create directories
    print("\n📁 Creating directories...")
    directories = [
        'temp',
        'transcripts',
        'fcpxml_exports',
        'fcpxml_outputs'
    ]

    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"  ✅ {dir_name}/")

    print("\n✅ SETUP COMPLETE!")
    print("=" * 40)
    print("\n📝 Next steps:")
    print("1. Make sure your .env file contains your OpenAI API key")
    print("2. Export your multicam clip from Final Cut Pro to fcpxml_exports/")
    print("3. Run: python src/workflow.py fcpxml_exports/your_file.fcpxmld/Info.fcpxml")
    print("\n")

def update_env_file(key, value):
    """Update a key in the .env file."""
    env_file = Path('.env')

    if not env_file.exists():
        # Create new .env file
        with open(env_file, 'w') as f:
            f.write(f"{key}={value}\n")
        return

    # Read existing content
    lines = []
    key_found = False

    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}\n")
                key_found = True
            else:
                lines.append(line)

    # Add key if not found
    if not key_found:
        lines.append(f"{key}={value}\n")

    # Write back
    with open(env_file, 'w') as f:
        f.writelines(lines)

def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n🔍 Checking dependencies...")

    # Check Python packages
    required_packages = {
        'openai': 'OpenAI API client',
        'pydub': 'Audio processing',
        'dotenv': 'Environment variables'
    }

    missing = []
    for package, description in required_packages.items():
        try:
            if package == 'dotenv':
                import dotenv
            else:
                __import__(package)
            print(f"  ✅ {package} ({description})")
        except ImportError:
            print(f"  ❌ {package} ({description})")
            missing.append(package)

    # Check ffmpeg
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("  ✅ ffmpeg (Audio/video processing)")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  ❌ ffmpeg (Audio/video processing)")
        print("\n⚠️  ffmpeg is required but not found!")
        print("Install with:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")

    if missing:
        print(f"\n⚠️  Missing Python packages: {', '.join(missing)}")
        print("Install with: pip install -r requirements.txt")
        return False

    return True

if __name__ == "__main__":
    print("Welcome to Multicam Auto-Cut Setup!")

    # Check dependencies first
    deps_ok = check_dependencies()

    if not deps_ok:
        response = input("\nContinue with setup anyway? [y/N]: ").strip().lower()
        if response != 'y':
            print("Setup cancelled. Please install dependencies first.")
            sys.exit(1)

    # Run setup
    setup_environment()

    print("Happy editing! 🎬")