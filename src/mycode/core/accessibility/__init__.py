"""Accessibility support for MyCode."""
from .screen_reader import ScreenReaderAnnouncer
from .voice import VoiceInput

__all__ = ["ScreenReaderAnnouncer", "VoiceInput"]
