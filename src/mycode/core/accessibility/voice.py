"""Voice input support for MyCode."""
import threading
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class VoiceInputConfig:
    """Voice input configuration."""
    enabled: bool = False
    language: str = "en-US"
    continuous: bool = False
    engine: str = "speech_recognition"  # "speech_recognition" or "whisper"


class VoiceInput:
    """Speech-to-text input handler."""

    def __init__(self, on_transcript: Optional[Callable[[str], None]] = None):
        self.config = VoiceInputConfig()
        self.on_transcript = on_transcript
        self._listening = False
        self._thread: Optional[threading.Thread] = None

    def start_listening(self):
        """Start listening for voice input."""
        if self._listening:
            return
        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_listening(self):
        """Stop listening for voice input."""
        self._listening = False

    def _listen_loop(self):
        """Background listening loop."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()

            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)

            while self._listening:
                try:
                    with microphone as source:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=10)
                    text = recognizer.recognize_google(audio, language=self.config.language)
                    if text and self.on_transcript:
                        self.on_transcript(text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    break
                except Exception:
                    break
        except ImportError:
            pass  # speech_recognition not installed
        except Exception:
            pass

    def transcribe_file(self, audio_path: str) -> Optional[str]:
        """Transcribe an audio file."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
            return recognizer.recognize_google(audio)
        except Exception:
            return None
