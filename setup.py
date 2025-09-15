"""Setup configuration for the Multicam Auto-Cut System."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="multicam-auto-cut",
    version="1.0.0",
    author="Payette Forward",
    description="AI-powered Final Cut Pro workflow automation for cutting multicam clips",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/payetteforward/multicam-auto-cut",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        "python-dotenv>=1.0.0",
        "pydub>=0.25.1",
        "requests>=2.31.0",
        "tqdm>=4.66.0",
        "colorlog>=6.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pre-commit>=3.3.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "autocut=src.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)