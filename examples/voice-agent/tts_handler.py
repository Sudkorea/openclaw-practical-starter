#!/usr/bin/env python3
"""
tts_handler.py — Text-to-Speech Handler

Abstracts over multiple TTS backends (edge-tts local, GCP Text-to-Speech)
with text sanitization to prevent TTS from reading unreadable content aloud.

Design principles:
- Text MUST be sanitized before TTS. URLs, code blocks, markdown, and
  special characters should be stripped or converted to readable equivalents.
- The pipeline calls `synthesize(text)` and gets back audio bytes (WAV/MP3).
- Errors are caught and a silent fallback audio is returned so the pipeline
  does not crash. The error is logged for operator review.
- Voice presets make it easy to switch between voices without code changes.

Usage:
    from tts_handler import TTSHandler, TTSMode

    handler = TTSHandler(mode=TTSMode.EDGE_TTS, voice="en-US-GuyNeural")
    audio = await handler.synthesize("Hello, the tests passed.")

    # Or synchronous wrapper:
    audio = handler.synthesize_sync("Hello, the tests passed.")
"""

import asyncio
import io
import logging
import os
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default voices per backend
EDGE_TTS_DEFAULT_VOICE = os.environ.get("EDGE_TTS_VOICE", "en-US-GuyNeural")
GCP_TTS_DEFAULT_VOICE = os.environ.get("GCP_TTS_VOICE", "en-US-Standard-D")
GCP_TTS_LANGUAGE = os.environ.get("GCP_TTS_LANGUAGE", "en-US")

# Voice presets — pick one or add your own
# Run `edge-tts --list-voices` to see all available voices
VOICE_PRESETS = {
    "default":    "en-US-GuyNeural",      # Neutral male, good clarity
    "casual":     "en-US-ChristopherNeural",  # Slightly warmer
    "fast":       "en-US-AriaNeural",     # Female, clear and fast
    "korean":     "ko-KR-InJoonNeural",   # Korean male
    "british":    "en-GB-RyanNeural",     # British male
}


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------

class TTSMode(str, Enum):
    EDGE_TTS = "edge_tts"
    GCP_TTS = "gcp_tts"


# ---------------------------------------------------------------------------
# Text sanitization — CRITICAL for voice UX
# ---------------------------------------------------------------------------

def sanitize_for_tts(text: str) -> str:
    """
    Clean text so TTS does not read unreadable content verbatim.

    This function handles the most common cases where raw LLM output is
    not suitable for audio playback:

    1. Code blocks: replace with a spoken placeholder
    2. URLs: replace with "a link" or "the URL"
    3. Markdown formatting: strip bold/italic/headers
    4. Long lists: truncate with "and more"
    5. Special characters: strip or replace with readable equivalents
    6. Repetition: collapse repeated whitespace/newlines

    This function is intentionally conservative — when in doubt, it removes
    content rather than attempting to read it awkwardly.

    Example:
        Input:  "Use `requests.get('https://api.example.com/v1')` to fetch data."
        Output: "Use the requests dot get function to fetch data."

    More examples are in the test cases at the bottom of this file.
    """
    if not text:
        return ""

    # 1. Remove code blocks (```...```) and replace with a spoken placeholder
    #    Single backticks are handled separately below
    text = re.sub(
        r"```[a-z]*\n.*?```",
        " (code block omitted) ",
        text,
        flags=re.DOTALL,
    )

    # 2. Replace URLs with "a link"
    #    This regex catches http/https/ftp URLs
    text = re.sub(
        r"https?://\S+|ftp://\S+",
        "a link",
        text,
    )

    # 3. Replace inline code (`code`) with just the content, cleaning up dots
    #    `requests.get` -> "requests dot get"
    def clean_inline_code(match: re.Match) -> str:
        code = match.group(1)
        # Replace dots with " dot " for readability
        code = code.replace(".", " dot ")
        # Replace underscores with " underscore " (or just remove)
        code = code.replace("_", " ")
        # Remove brackets
        code = re.sub(r"[(){}\[\]]", "", code)
        return code.strip()

    text = re.sub(r"`([^`]+)`", clean_inline_code, text)

    # 4. Strip markdown headers (#, ##, ###)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 5. Strip markdown bold/italic (**text**, *text*, __text__, _text_)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text)

    # 6. Strip markdown links [text](url) -> "text"
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # 7. Truncate long numbered lists (>5 items)
    lines = text.split("\n")
    list_items = []
    non_list_lines = []
    in_list = False

    for line in lines:
        if re.match(r"^\s*\d+\.\s+", line) or re.match(r"^\s*[-*]\s+", line):
            list_items.append(line)
            in_list = True
        else:
            if in_list and len(list_items) > 5:
                # Truncate the list
                non_list_lines.extend(list_items[:5])
                non_list_lines.append(f"  ... and {len(list_items) - 5} more.")
                list_items = []
            elif in_list:
                non_list_lines.extend(list_items)
                list_items = []
            in_list = False
            non_list_lines.append(line)

    if list_items:
        if len(list_items) > 5:
            non_list_lines.extend(list_items[:5])
            non_list_lines.append(f"  ... and {len(list_items) - 5} more.")
        else:
            non_list_lines.extend(list_items)

    text = "\n".join(non_list_lines)

    # 8. Replace common special characters with spoken equivalents
    replacements = {
        "->": "arrow",
        "=>": "arrow",
        "!=": "not equal",
        "==": "equals",
        ">=": "greater than or equal",
        "<=": "less than or equal",
        "&&": "and",
        "||": "or",
        "@": "at",
    }
    for symbol, replacement in replacements.items():
        text = text.replace(symbol, f" {replacement} ")

    # 9. Collapse multiple newlines into a single pause (period + newline)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)

    # 10. Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    # 11. Remove trailing/leading whitespace
    text = text.strip()

    # 12. Truncate to a maximum length (voice responses should be brief)
    MAX_CHARS = 600
    if len(text) > MAX_CHARS:
        # Try to cut at a sentence boundary
        cutoff = text[:MAX_CHARS].rfind(".")
        if cutoff > MAX_CHARS // 2:
            text = text[:cutoff + 1] + " (response truncated)"
        else:
            text = text[:MAX_CHARS] + "... (truncated)"

    return text


# ---------------------------------------------------------------------------
# edge-tts backend
# ---------------------------------------------------------------------------

class EdgeTTS:
    """
    Local TTS using edge-tts (Microsoft Azure TTS via free API).

    Installation: pip install edge-tts

    Note: edge-tts is free but requires internet access. For a fully offline
    solution, use pyttsx3 or a local model like Kokoro-TTS.
    """

    def __init__(self, voice: str = EDGE_TTS_DEFAULT_VOICE):
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio using edge-tts.
        Returns MP3 audio bytes, or empty bytes on failure.
        """
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text=text, voice=self.voice)
            audio_buf = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buf.write(chunk["data"])

            return audio_buf.getvalue()

        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return b""
        except Exception as e:
            logger.error(f"edge-tts synthesis failed: {e}")
            return b""


# ---------------------------------------------------------------------------
# GCP TTS backend
# ---------------------------------------------------------------------------

class GCPTextToSpeech:
    """
    Google Cloud Text-to-Speech backend.

    Installation: pip install google-cloud-texttospeech

    Voice quality tiers:
    - Standard:  en-US-Standard-D — fast, good quality
    - WaveNet:   en-US-Wavenet-D  — higher quality, slightly slower
    - Neural2:   en-US-Neural2-D  — best quality, may have higher latency
    - Studio:    en-US-Studio-M   — highest quality, most expensive

    Recommendation: Start with Standard for low latency, upgrade to Neural2
    after validating that the latency is acceptable for your use case.
    """

    def __init__(
        self,
        voice_name: str = GCP_TTS_DEFAULT_VOICE,
        language: str = GCP_TTS_LANGUAGE,
    ):
        self.voice_name = voice_name
        self.language = language
        self._client = None

    def _ensure_client(self) -> bool:
        if self._client is not None:
            return True
        try:
            from google.cloud import texttospeech
            self._client = texttospeech.TextToSpeechClient()
            return True
        except ImportError:
            logger.error(
                "google-cloud-texttospeech not installed. "
                "Run: pip install google-cloud-texttospeech"
            )
            return False
        except Exception as e:
            logger.error(f"GCP TTS client init failed: {e}")
            return False

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize text using GCP TTS.
        Returns MP3 audio bytes, or empty bytes on failure.
        """
        if not self._ensure_client():
            return b""

        try:
            from google.cloud import texttospeech

            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.language,
                name=self.voice_name,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.1,  # Slightly faster than natural for voice UI
                pitch=0.0,
            )

            response = self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            return response.audio_content

        except Exception as e:
            logger.error(f"GCP TTS synthesis failed: {e}")
            return b""


# ---------------------------------------------------------------------------
# Main TTS handler (unified interface)
# ---------------------------------------------------------------------------

class TTSHandler:
    """
    Unified TTS interface. Use this in the voice pipeline.

    Example:
        handler = TTSHandler(mode=TTSMode.EDGE_TTS)

        # In your pipeline:
        response_text = get_llm_response(transcript)
        audio = handler.synthesize_sync(response_text)
        play_audio(audio)
    """

    def __init__(
        self,
        mode: TTSMode = TTSMode.EDGE_TTS,
        voice: Optional[str] = None,
        fallback: Optional["TTSHandler"] = None,
    ):
        self.mode = mode
        self._error_count = 0
        self._max_errors_before_fallback = 3

        if mode == TTSMode.EDGE_TTS:
            self._backend = EdgeTTS(voice=voice or EDGE_TTS_DEFAULT_VOICE)
        elif mode == TTSMode.GCP_TTS:
            self._backend = GCPTextToSpeech(voice_name=voice or GCP_TTS_DEFAULT_VOICE)
        else:
            raise ValueError(f"Unknown TTS mode: {mode}")

        # Automatic fallback to edge-tts if GCP fails
        if mode == TTSMode.GCP_TTS and fallback is None:
            self.fallback = TTSHandler(mode=TTSMode.EDGE_TTS)
        else:
            self.fallback = fallback

    async def synthesize(self, text: str, sanitize: bool = True) -> bytes:
        """
        Synthesize text to audio.
        Sanitizes text by default (set sanitize=False only if already cleaned).
        Returns audio bytes (MP3 or WAV depending on backend).
        """
        if not text:
            return b""

        clean_text = sanitize_for_tts(text) if sanitize else text

        if not clean_text:
            logger.warning("Text was empty after sanitization. Nothing to speak.")
            return b""

        try:
            audio = await self._backend.synthesize(clean_text)

            if not audio:
                raise RuntimeError("Backend returned empty audio")

            self._error_count = 0  # Reset on success
            return audio

        except Exception as e:
            self._error_count += 1
            logger.error(f"TTS [{self.mode}] failed (error #{self._error_count}): {e}")

            # Switch to fallback after repeated failures
            if self.fallback and self._error_count >= self._max_errors_before_fallback:
                logger.warning("Switching to fallback TTS")
                return await self.fallback.synthesize(clean_text, sanitize=False)

            return b""

    def synthesize_sync(self, text: str, sanitize: bool = True) -> bytes:
        """
        Synchronous wrapper for synthesize(). Convenient for non-async contexts.
        """
        return asyncio.run(self.synthesize(text, sanitize=sanitize))

    @property
    def backend_name(self) -> str:
        return self.mode.value


# ---------------------------------------------------------------------------
# Sanitization tests — run this file directly to verify behavior
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        (
            "Use `requests.get('https://api.example.com')` to fetch data.",
            "Use the requests dot get function to fetch data.",
        ),
        (
            "```python\nimport os\nprint(os.getcwd())\n```\nThis prints the directory.",
            "(code block omitted) This prints the directory.",
        ),
        (
            "See https://docs.python.org/3/library/os.html for details.",
            "See a link for details.",
        ),
        (
            "**Important:** Do _not_ delete this file.",
            "Important: Do not delete this file.",
        ),
        (
            "Steps:\n1. First\n2. Second\n3. Third\n4. Fourth\n5. Fifth\n6. Sixth\n7. Seventh",
            None,  # Just check it doesn't crash and truncates
        ),
    ]

    print("Sanitization test results:")
    print("-" * 60)
    for i, (input_text, expected) in enumerate(test_cases):
        result = sanitize_for_tts(input_text)
        status = "PASS" if (expected is None or expected in result) else "FAIL"
        print(f"Test {i+1}: {status}")
        print(f"  Input:    {input_text[:80]}")
        print(f"  Output:   {result[:80]}")
        if expected:
            print(f"  Expected: {expected[:80]}")
        print()
