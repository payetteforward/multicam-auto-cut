"""
Multicam Auto-Cut System

AI-powered Final Cut Pro workflow automation for cutting multicam clips.
"""

__version__ = "1.0.0"
__author__ = "Payette Forward"

from .core.workflow import MulticamAutoCutWorkflow

__all__ = ["MulticamAutoCutWorkflow"]