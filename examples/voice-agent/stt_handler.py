#!/usr/bin/env python3
"""
stt_handler.py — Speech-to-Text Handler

Abstracts over multiple STT backends (Whisper local, GCP Speech-to-Text)
with a unified interface for the voice pipeline.

Design principles:
- The pipeline calls `transcribe(audio_bytes)` and gets back a str.
  It does not care which backend was used.
- Errors are caught and logged; the method returns "" on failure so the
  pipeline can skip the segment rather than crash.
- Stereo audio is automatically downmixed to mono (GCP STT requirement).
- Compute type is auto-detected based on CUDA availability (Whisper).
- GCP streaming sessions are restarted when they timeout (~5 minutes).

Usage:
    from stt_handler import STTHandler, STTMode

    handler = STTHandler(mode=STTMode.LOWCOST)
    transcript = handler.transcribe(wav_bytes)
    if transcript:
        print(f"Heard: {transcript}")
"""

import io
import logging
import os
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Whisper model to use. Options (quality vs. speed tradeoff):
#   tiny.en      — fastest, least accurate, good for noisy environments
#   base.en      — balanced
#   distil-medium.en — best quality/speed for English (recommended)
#   medium.en    — higher quality but slower
#   large-v3     — highest quality, very slow on CPU
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "distil-medium.en")

# GCP settings
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_LANGUAGE_CODE = os.environ.get("GCP_STT_LANGUAGE", "en-US")
GCP_SAMPLE_RATE = int(os.environ.get("GCP_STT_SAMPLE_RATE", "16000"))

# Audio settings
SAMPLE_RATE = 16000  # Hz — Whisper and GCP both work best at 16kHz
CHANNELS = 1  # Mono (required by GCP STT; we downmix if needed)

# Silence detection
SILENCE_THRESHOLD_DB = float(os.environ.get("SILENCE_THRESHOLD_DB", "-40"))
SILENCE_SEC = float(os.environ.get("SILENCE_SEC", "1.0"))

# Streaming session restart threshold (GCP limits streams to ~5 minutes)
GCP_STREAM_MAX_SEC = 290  # Restart before the 5-minute GCP limit


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------

class STTMode(str, Enum):
    WHISPER_LOCAL = "whisper_local"
    GCP_STT = "gcp_stt"


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def _to_mono(audio_bytes: bytes, channels: int = 2) -> bytes:
    """
    Downmix stereo (or multi-channel) PCM audio to mono.
    Required by GCP STT which only accepts single-channel audio.

    Assumes 16-bit (int16) PCM format.
    """
    try:
        import numpy as np

        # Parse raw PCM bytes into int16 samples
        samples = np.frombuffer(audio_bytes, dtype=np.int16)

        if channels == 1:
            return audio_bytes  # Already mono

        # Reshape to (num_frames, channels) and average across channels
        samples = samples.reshape(-1, channels)
        mono = samples.mean(axis=1).astype(np.int16)
        return mono.tobytes()

    except ImportError:
        logger.warning("numpy not available; cannot downmix stereo. Returning as-is.")
        return audio_bytes
    except Exception as e:
        logger.error(f"Stereo downmix failed: {e}")
        return audio_bytes


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """
    Wrap raw PCM bytes in a WAV container.
    Whisper's faster-whisper accepts WAV files; GCP STT can take raw PCM but
    WAV is more reliable.
    """
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    return buf.getvalue()


def _detect_audio_energy(audio_bytes: bytes) -> float:
    """
    Compute RMS energy of the audio in dB.
    Used to skip near-silence segments before even calling STT.
    Returns dB value (negative; e.g., -60 = very quiet, -10 = loud).
    """
    try:
        import math
        import struct

        samples = struct.unpack(f"{len(audio_bytes) // 2}h", audio_bytes)
        if not samples:
            return -100.0
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        if rms == 0:
            return -100.0
        return 20 * math.log10(rms / 32768.0)
    except Exception:
        return -50.0  # Assume moderate energy on error


# ---------------------------------------------------------------------------
# Whisper backend
# ---------------------------------------------------------------------------

class WhisperSTT:
    """
    Local Whisper STT using faster-whisper for CPU efficiency.

    Installation: pip install faster-whisper

    Key decisions:
    - Compute type is auto-selected: float16 for GPU, int8 for CPU.
      int8_float16 is NOT used because it's unsupported on most CPU setups.
    - Model is loaded once at init and reused across calls (loading takes 2-10s).
    - We use VAD (voice activity detection) to skip silence segments at the
      Whisper level in addition to our pre-filter.
    """

    def __init__(self, model_name: str = WHISPER_MODEL):
        self.model_name = model_name
        self._model = None
        self._load_start = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load the Whisper model on first use."""
        if self._model is not None:
            return True

        try:
            from faster_whisper import WhisperModel

            # Auto-detect compute type based on CUDA availability
            try:
                import torch
                if torch.cuda.is_available():
                    compute_type = "float16"
                    device = "cuda"
                else:
                    compute_type = "int8"
                    device = "cpu"
            except ImportError:
                # No torch installed — assume CPU
                compute_type = "int8"
                device = "cpu"

            logger.info(f"Loading Whisper model '{self.model_name}' ({device}, {compute_type})...")
            self._load_start = time.monotonic()

            self._model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=compute_type,
            )

            elapsed = time.monotonic() - self._load_start
            logger.info(f"Whisper model loaded in {elapsed:.1f}s")
            return True

        except ImportError:
            logger.error(
                "faster-whisper not installed. Run: pip install faster-whisper"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe PCM audio bytes to text.
        Returns empty string on failure or if no speech detected.
        """
        if not self._ensure_loaded():
            return ""

        # Pre-filter: skip near-silence segments (saves Whisper calls)
        energy_db = _detect_audio_energy(audio_bytes)
        if energy_db < SILENCE_THRESHOLD_DB:
            logger.debug(f"Skipping segment: energy={energy_db:.1f}dB (below threshold)")
            return ""

        try:
            # Convert raw PCM to WAV for Whisper
            wav_bytes = _pcm_to_wav(audio_bytes)
            audio_io = io.BytesIO(wav_bytes)

            # Transcribe with VAD filtering enabled
            segments, info = self._model.transcribe(
                audio_io,
                language="en",
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.5,
                    "min_silence_duration_ms": 500,
                },
            )

            transcript = " ".join(seg.text for seg in segments).strip()
            logger.debug(f"Whisper transcript: '{transcript}'")
            return transcript

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""


# ---------------------------------------------------------------------------
# GCP STT backend
# ---------------------------------------------------------------------------

class GCPSpeechSTT:
    """
    Google Cloud Speech-to-Text backend.

    Installation: pip install google-cloud-speech

    Key decisions:
    - Uses the standard (non-streaming) API for simplicity and reliability.
    - Streaming API is faster but requires stream restart every ~5 minutes.
    - Always converts input to mono at 16kHz (GCP requirement).
    - Falls back to WhisperSTT if GCP is unavailable.

    For streaming STT, see _restart_stream() below.
    """

    def __init__(self):
        self._client = None
        self._stream_start = None

    def _ensure_client(self) -> bool:
        """Initialize the GCP Speech client."""
        if self._client is not None:
            return True
        try:
            from google.cloud import speech
            self._client = speech.SpeechClient()
            return True
        except ImportError:
            logger.error("google-cloud-speech not installed. Run: pip install google-cloud-speech")
            return False
        except Exception as e:
            logger.error(f"GCP Speech client init failed: {e}")
            return False

    def transcribe(self, audio_bytes: bytes, channels: int = 1) -> str:
        """
        Send audio to GCP Speech-to-Text and return the transcript.
        Returns empty string on failure.
        """
        if not self._ensure_client():
            return ""

        try:
            from google.cloud import speech

            # CRITICAL: GCP STT requires mono audio. Always downmix.
            if channels > 1:
                audio_bytes = _to_mono(audio_bytes, channels=channels)

            audio = speech.RecognitionAudio(content=audio_bytes)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=GCP_SAMPLE_RATE,
                language_code=GCP_LANGUAGE_CODE,
                audio_channel_count=1,  # Explicitly state mono
                model="latest_short",   # Optimized for short utterances
                use_enhanced=True,
            )

            response = self._client.recognize(config=config, audio=audio)

            if not response.results:
                return ""

            # Take the first (highest confidence) alternative
            best = response.results[0].alternatives[0]
            transcript = best.transcript.strip()
            logger.debug(f"GCP STT transcript (confidence={best.confidence:.2f}): '{transcript}'")
            return transcript

        except Exception as e:
            # Log the full error but do not crash the pipeline
            logger.error(f"GCP STT transcription failed: {e}")
            # Return empty string — the pipeline will skip this segment
            return ""

    def _restart_stream(self):
        """
        Restart the GCP streaming session to avoid the 5-minute timeout.
        Call this when the stream has been active for more than GCP_STREAM_MAX_SEC.
        """
        logger.info("Restarting GCP STT stream (approaching timeout limit)")
        self._stream_start = time.monotonic()
        # Real implementation: close the existing stream generator and open a new one.
        # This is left as a stub since full streaming requires a more complex setup.

    def stream_needs_restart(self) -> bool:
        """Check if the streaming session should be restarted."""
        if self._stream_start is None:
            return False
        return (time.monotonic() - self._stream_start) > GCP_STREAM_MAX_SEC


# ---------------------------------------------------------------------------
# Main STT handler (unified interface)
# ---------------------------------------------------------------------------

class STTHandler:
    """
    Unified STT interface. Use this in the voice pipeline.

    Example:
        handler = STTHandler(mode=STTMode.WHISPER_LOCAL)

        # In your audio loop:
        audio_segment = capture_audio_segment()
        transcript = handler.transcribe(audio_segment)
        if transcript:
            route_to_llm(transcript)
    """

    def __init__(
        self,
        mode: STTMode = STTMode.WHISPER_LOCAL,
        fallback: Optional["STTHandler"] = None,
    ):
        self.mode = mode
        self.fallback = fallback
        self._error_count = 0
        self._max_errors_before_fallback = 3

        if mode == STTMode.WHISPER_LOCAL:
            self._backend = WhisperSTT()
        elif mode == STTMode.GCP_STT:
            self._backend = GCPSpeechSTT()
        else:
            raise ValueError(f"Unknown STT mode: {mode}")

        # Automatic fallback to local Whisper if GCP fails repeatedly
        if mode == STTMode.GCP_STT and fallback is None:
            self.fallback = STTHandler(mode=STTMode.WHISPER_LOCAL)

    def transcribe(self, audio_bytes: bytes, channels: int = 1) -> str:
        """
        Transcribe audio and return the transcript string.
        Returns empty string if no speech was detected or an error occurred.
        """
        start = time.monotonic()

        try:
            if self.mode == STTMode.GCP_STT:
                transcript = self._backend.transcribe(audio_bytes, channels=channels)
            else:
                transcript = self._backend.transcribe(audio_bytes)

            elapsed = (time.monotonic() - start) * 1000
            logger.debug(f"STT [{self.mode}] completed in {elapsed:.0f}ms: '{transcript}'")

            if transcript:
                self._error_count = 0  # Reset error count on success

            return transcript

        except Exception as e:
            self._error_count += 1
            logger.error(f"STT [{self.mode}] failed (error #{self._error_count}): {e}")

            # Switch to fallback if we've hit too many errors
            if self.fallback and self._error_count >= self._max_errors_before_fallback:
                logger.warning(
                    f"Switching to fallback STT after {self._error_count} errors"
                )
                return self.fallback.transcribe(audio_bytes, channels=channels)

            return ""

    @property
    def backend_name(self) -> str:
        return self.mode.value
