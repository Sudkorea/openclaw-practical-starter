#!/usr/bin/env python3
"""
voice_pipeline.py — Voice Pipeline Orchestrator

Ties together STT, LLM routing, and TTS into a single continuous voice session.
This is the main entry point for the voice-agent.

Architecture:
    Audio input -> STT -> LLM -> TTS -> Audio output

State machine:
    idle -> listening -> transcribing -> thinking -> speaking -> listening
    Any state -> error (logged, auto-recover) -> listening

Usage:
    # Start in lowcost mode (local Whisper + edge-tts)
    python voice_pipeline.py --mode lowcost

    # Start with GCP quality
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    python voice_pipeline.py --mode gcp-quality

    # Replay a recorded WAV file (for testing)
    python voice_pipeline.py --mode lowcost --input-file test.wav

Key design decisions:
- The pipeline is event-loop based (asyncio) for non-blocking I/O.
- Audio capture runs in a separate thread (blocking I/O) and posts segments
  to an asyncio Queue.
- The watchdog thread monitors the pipeline and restarts dead workers.
- Session state (turns, errors, latencies) is tracked and written to Airlock
  on session close.
- LLM responses are capped at 200 tokens to keep voice interactions brief.
"""

import argparse
import asyncio
import logging
import os
import queue
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from stt_handler import STTHandler, STTMode
from tts_handler import TTSHandler, TTSMode

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("voice_pipeline")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Audio capture settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024  # Frames per buffer
SILENCE_SEC = float(os.environ.get("SILENCE_SEC", "1.0"))

# Session settings
SESSION_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_IDLE_TIMEOUT", "3600"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT", "45"))
LLM_WARN_AT_SECONDS = float(os.environ.get("LLM_WARN_AT", "20"))
MAX_LLM_TOKENS = int(os.environ.get("MAX_LLM_TOKENS", "200"))

# Watchdog
WATCHDOG_INTERVAL_SECONDS = 5
MAX_CONSECUTIVE_STT_ERRORS = 5

# Airlock / output paths
VOICE_SESSION_DIR = Path(
    os.environ.get(
        "VOICE_SESSION_DIR",
        "~/.openclaw/voice/sessions/",
    )
)

AIRLOCK_DAILY_DIR = Path(
    os.environ.get(
        "AIRLOCK_DAILY_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/daily/",
    )
)


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

class PipelineState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    THINKING = auto()
    SPEAKING = auto()
    ERROR = auto()
    CLOSING = auto()


class SessionMetrics:
    """Tracks per-session performance metrics."""

    def __init__(self):
        self.turn_count = 0
        self.stt_error_count = 0
        self.tts_error_count = 0
        self.timeout_count = 0
        self.latencies_ms: list[float] = []
        self.start_time = time.monotonic()

    @property
    def duration_seconds(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def latency_p50(self) -> Optional[float]:
        if not self.latencies_ms:
            return None
        sorted_lat = sorted(self.latencies_ms)
        return sorted_lat[len(sorted_lat) // 2]

    @property
    def latency_p95(self) -> Optional[float]:
        if not self.latencies_ms:
            return None
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]


class SessionTurn:
    """A single user-agent exchange in the session."""

    def __init__(self, user_text: str, agent_text: str, latency_ms: float):
        self.timestamp = datetime.now(timezone.utc)
        self.user_text = user_text
        self.agent_text = agent_text
        self.latency_ms = latency_ms


# ---------------------------------------------------------------------------
# LLM interface (stub — replace with your actual LLM API)
# ---------------------------------------------------------------------------

async def get_llm_response(transcript: str, session_context: list[SessionTurn]) -> str:
    """
    Route the transcript to an LLM and return the response.

    Real implementation: call OpenClaw's LLM API or use the agent's built-in
    response generation. The voice agent typically forwards to a general-purpose
    session or routes to a domain agent.

    Response must be:
    - Plain text (no markdown, no code blocks)
    - Maximum MAX_LLM_TOKENS tokens (~200 words)
    - Conversational, not documentation-style

    This stub returns a template response for testing.
    """
    # Real implementation example:
    # response = await openclaw_client.send_message(
    #     message=transcript,
    #     context=[{"role": "user" if i%2==0 else "assistant", "content": t.user_text if i%2==0 else t.agent_text}
    #              for i, t in enumerate(session_context[-6:])],  # Last 3 turns for context
    #     max_tokens=MAX_LLM_TOKENS,
    # )
    # return response.text

    # Stub: return a placeholder
    await asyncio.sleep(0.1)  # Simulate network latency
    return f"[stub] Received: {transcript[:50]}. Replace get_llm_response() with your LLM call."


# ---------------------------------------------------------------------------
# Audio capture (runs in a separate thread)
# ---------------------------------------------------------------------------

class AudioCapture:
    """
    Captures audio from the microphone and posts complete utterance segments
    to an asyncio queue.

    Silence detection algorithm:
    1. Continuously read audio chunks.
    2. Maintain a circular buffer of recent RMS energy values.
    3. When energy drops below threshold for SILENCE_SEC, emit the buffered audio.
    4. This approach avoids cutting off natural speech pauses.
    """

    def __init__(self, audio_queue: "asyncio.Queue[bytes]"):
        self._queue = audio_queue
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the capture thread."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _capture_loop(self) -> None:
        """
        Main audio capture loop. Reads from microphone and posts
        silence-delimited segments to the queue.
        """
        try:
            import sounddevice as sd
            import numpy as np

            buffer = []
            silent_frames = 0
            speaking_frames = 0
            SILENCE_FRAMES = int(SILENCE_SEC * SAMPLE_RATE / CHUNK_SIZE)
            MIN_SPEECH_FRAMES = 3  # Ignore very short segments (< ~200ms)

            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                dtype="int16",
                channels=1,
            ) as stream:
                logger.info("Microphone capture started")

                while self._running:
                    data, _ = stream.read(CHUNK_SIZE)
                    chunk = bytes(data)

                    # Compute RMS energy
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
                    energy_db = 20 * np.log10(max(rms, 1) / 32768.0)

                    is_speech = energy_db > -40  # Configurable via SILENCE_THRESHOLD_DB

                    if is_speech:
                        buffer.append(chunk)
                        speaking_frames += 1
                        silent_frames = 0
                    else:
                        silent_frames += 1
                        if buffer:
                            buffer.append(chunk)  # Include trailing silence

                        # If we've been silent long enough, emit the segment
                        if silent_frames >= SILENCE_FRAMES and speaking_frames >= MIN_SPEECH_FRAMES:
                            segment = b"".join(buffer)
                            # Post to queue (non-blocking; drop if queue is full)
                            try:
                                asyncio.get_event_loop().call_soon_threadsafe(
                                    self._queue.put_nowait, segment
                                )
                            except asyncio.QueueFull:
                                logger.warning("Audio queue full; dropping segment")

                            buffer = []
                            silent_frames = 0
                            speaking_frames = 0

        except ImportError:
            logger.error(
                "sounddevice not installed. Run: pip install sounddevice\n"
                "For file-based testing, use --input-file instead."
            )
        except Exception as e:
            logger.error(f"Audio capture error: {e}")
        finally:
            logger.info("Audio capture stopped")


class FileAudioCapture:
    """
    File-based audio source for testing without a microphone.
    Posts the entire WAV file as a single segment.
    """

    def __init__(self, audio_queue: "asyncio.Queue[bytes]", file_path: str):
        self._queue = audio_queue
        self._file_path = file_path

    def start(self) -> None:
        import wave

        with wave.open(self._file_path, "rb") as wf:
            audio_bytes = wf.readframes(wf.getnframes())
            asyncio.get_event_loop().call_soon_threadsafe(
                self._queue.put_nowait, audio_bytes
            )
        logger.info(f"Loaded audio from file: {self._file_path}")

    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Audio playback
# ---------------------------------------------------------------------------

def play_audio(audio_bytes: bytes) -> None:
    """
    Play audio bytes through the system audio output.
    Supports MP3 (edge-tts output) and WAV.
    """
    if not audio_bytes:
        return

    try:
        import sounddevice as sd
        import soundfile as sf
        import io

        with sf.SoundFile(io.BytesIO(audio_bytes)) as f:
            data = f.read(dtype="float32")
            sd.play(data, f.samplerate)
            sd.wait()

    except ImportError:
        # Fallback: write to a temp file and play with system command
        import tempfile, subprocess, os
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            # Try common audio players
            for player in ["mpg123", "ffplay", "aplay"]:
                try:
                    subprocess.run([player, "-q", tmp_path], check=True, timeout=30)
                    break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"Audio playback failed: {e}")


# ---------------------------------------------------------------------------
# Session archiving
# ---------------------------------------------------------------------------

def write_session_transcript(
    session_id: str,
    turns: list[SessionTurn],
) -> Path:
    """Write session transcript to a text file."""
    VOICE_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = VOICE_SESSION_DIR / f"{session_id}.txt"

    lines = []
    for turn in turns:
        ts = turn.timestamp.strftime("%H:%M:%S")
        lines.append(f"[{ts}] USER: {turn.user_text}")
        lines.append(f"[{ts}] AGENT: {turn.agent_text}")
        lines.append("")

    transcript_path.write_text("\n".join(lines))
    return transcript_path


def write_airlock_record(
    session_id: str,
    mode: str,
    metrics: SessionMetrics,
    turns: list[SessionTurn],
    transcript_path: Path,
    close_reason: str,
) -> Path:
    """Write a session summary to the Airlock."""
    AIRLOCK_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    short_id = session_id[:8]
    record_path = AIRLOCK_DAILY_DIR / f"{date_str}-voice-agent-session-{short_id}.md"

    duration = f"{metrics.duration_seconds:.0f}s"
    lat_p50 = f"{metrics.latency_p50:.0f}ms" if metrics.latency_p50 else "N/A"
    lat_p95 = f"{metrics.latency_p95:.0f}ms" if metrics.latency_p95 else "N/A"

    record = f"""## TL;DR
Voice session {short_id}: {metrics.turn_count} turns over {duration}. Close reason: {close_reason}.

## Session details
- Session ID: {session_id}
- Mode: {mode}
- Started: {datetime.now(timezone.utc).isoformat()}
- Duration: {duration}
- Turns: {metrics.turn_count}
- Close reason: {close_reason}

## Metrics
- E2E latency p50: {lat_p50}
- E2E latency p95: {lat_p95}
- STT errors: {metrics.stt_error_count}
- TTS errors: {metrics.tts_error_count}
- Timeouts: {metrics.timeout_count}

## Transcript
{transcript_path}

## Next action
DONE — voice sessions are self-contained.
"""

    record_path.write_text(record)
    return record_path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class VoicePipeline:
    """
    Main voice pipeline. Manages the session lifecycle and coordinates
    STT, LLM, and TTS.
    """

    def __init__(
        self,
        mode: str = "lowcost",
        input_file: Optional[str] = None,
    ):
        self.mode = mode
        self.session_id = str(uuid.uuid4())
        self.state = PipelineState.IDLE
        self.metrics = SessionMetrics()
        self.turns: list[SessionTurn] = []
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=10)
        self._last_activity = time.monotonic()
        self._close_reason = "unknown"
        self._consecutive_stt_errors = 0

        # Initialize STT and TTS based on mode
        if mode in ("lowcost", "fallback-safe"):
            self.stt = STTHandler(mode=STTMode.WHISPER_LOCAL)
            self.tts = TTSHandler(mode=TTSMode.EDGE_TTS)
        elif mode == "hybrid":
            self.stt = STTHandler(mode=STTMode.WHISPER_LOCAL)
            self.tts = TTSHandler(mode=TTSMode.GCP_TTS)
        elif mode == "gcp-quality":
            self.stt = STTHandler(mode=STTMode.GCP_STT)
            self.tts = TTSHandler(mode=TTSMode.GCP_TTS)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Initialize audio source
        if input_file:
            self.audio_capture = FileAudioCapture(self._audio_queue, input_file)
        else:
            self.audio_capture = AudioCapture(self._audio_queue)

    async def run(self) -> None:
        """Main session loop."""
        logger.info(f"Starting voice session {self.session_id[:8]} in {self.mode} mode")
        self.state = PipelineState.LISTENING
        self.audio_capture.start()

        # Announce session start
        welcome = await self.tts.synthesize("Session started. Listening.")
        play_audio(welcome)

        try:
            await asyncio.wait_for(
                self._process_loop(),
                timeout=SESSION_IDLE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            self._close_reason = "idle_timeout"
            logger.info(f"Session timed out after {SESSION_IDLE_TIMEOUT_SECONDS}s")
            closing_audio = await self.tts.synthesize("Session ended due to inactivity.")
            play_audio(closing_audio)
        except KeyboardInterrupt:
            self._close_reason = "user_interrupt"
        except Exception as e:
            self._close_reason = f"error: {e}"
            logger.error(f"Pipeline error: {e}", exc_info=True)
        finally:
            await self._close_session()

    async def _process_loop(self) -> None:
        """Continuously process audio segments until shutdown."""
        while self.state not in (PipelineState.CLOSING, PipelineState.ERROR):
            # Check idle timeout
            idle_time = time.monotonic() - self._last_activity
            if idle_time > SESSION_IDLE_TIMEOUT_SECONDS:
                break

            try:
                # Wait for next audio segment (1 second timeout to check idle)
                segment = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue

            await self._process_segment(segment)

    async def _process_segment(self, audio_bytes: bytes) -> None:
        """Process a single audio segment through the STT -> LLM -> TTS pipeline."""
        utterance_end = time.monotonic()

        # --- STT phase ---
        self.state = PipelineState.TRANSCRIBING
        transcript = self.stt.transcribe(audio_bytes)

        if not transcript:
            # Empty transcript = noise or silence; skip silently
            self._consecutive_stt_errors += 1
            if self._consecutive_stt_errors >= MAX_CONSECUTIVE_STT_ERRORS:
                logger.warning(
                    f"STT failed {MAX_CONSECUTIVE_STT_ERRORS} times consecutively"
                )
                self.metrics.stt_error_count += self._consecutive_stt_errors
                self._consecutive_stt_errors = 0
            self.state = PipelineState.LISTENING
            return

        self._consecutive_stt_errors = 0
        self._last_activity = time.monotonic()
        logger.info(f"Transcript: '{transcript}'")

        # Handle session-ending commands
        if any(cmd in transcript.lower() for cmd in ["close session", "stop session", "goodbye"]):
            self._close_reason = "user_command"
            self.state = PipelineState.CLOSING
            return

        # --- LLM phase ---
        self.state = PipelineState.THINKING
        llm_response = ""

        try:
            # Start a warning timer in case LLM is slow
            warn_task = asyncio.create_task(self._llm_slow_warning())

            llm_response = await asyncio.wait_for(
                get_llm_response(transcript, self.turns),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            warn_task.cancel()

        except asyncio.TimeoutError:
            self.metrics.timeout_count += 1
            logger.warning(f"LLM timed out after {LLM_TIMEOUT_SECONDS}s")
            llm_response = "I'm having trouble responding right now. Try again."
        except Exception as e:
            logger.error(f"LLM error: {e}")
            llm_response = "Something went wrong. Please try again."

        # --- TTS phase ---
        self.state = PipelineState.SPEAKING
        audio_start = time.monotonic()

        audio = await self.tts.synthesize(llm_response)
        if not audio:
            logger.warning("TTS returned empty audio. Speaking fallback.")
            self.metrics.tts_error_count += 1
            # Try to speak a short fallback message
            audio = await self.tts.synthesize("I had trouble speaking that. Please repeat.")

        play_audio(audio)

        # Record metrics
        e2e_latency_ms = (audio_start - utterance_end) * 1000
        self.metrics.latencies_ms.append(e2e_latency_ms)
        self.metrics.turn_count += 1

        self.turns.append(SessionTurn(
            user_text=transcript,
            agent_text=llm_response,
            latency_ms=e2e_latency_ms,
        ))

        logger.info(f"Turn {self.metrics.turn_count} complete | latency={e2e_latency_ms:.0f}ms")
        self.state = PipelineState.LISTENING

    async def _llm_slow_warning(self) -> None:
        """Speak a 'still thinking' message if LLM takes too long."""
        await asyncio.sleep(LLM_WARN_AT_SECONDS)
        warning_audio = await self.tts.synthesize("Still thinking.")
        play_audio(warning_audio)

    async def _close_session(self) -> None:
        """Archive session data and clean up."""
        self.state = PipelineState.CLOSING
        self.audio_capture.stop()

        logger.info(f"Closing session {self.session_id[:8]} ({self._close_reason})")

        if self.turns:
            transcript_path = write_session_transcript(self.session_id, self.turns)
            record_path = write_airlock_record(
                session_id=self.session_id,
                mode=self.mode,
                metrics=self.metrics,
                turns=self.turns,
                transcript_path=transcript_path,
                close_reason=self._close_reason,
            )
            logger.info(f"Airlock record: {record_path}")

        goodbye_audio = await self.tts.synthesize("Session ended. Goodbye.")
        play_audio(goodbye_audio)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw voice pipeline")
    parser.add_argument(
        "--mode",
        choices=["lowcost", "hybrid", "gcp-quality", "fallback-safe"],
        default=os.environ.get("VOICE_MODE", "lowcost"),
        help="Operating mode (default: lowcost)",
    )
    parser.add_argument(
        "--input-file",
        default=None,
        help="Path to a WAV file to use instead of microphone (for testing)",
    )
    args = parser.parse_args()

    pipeline = VoicePipeline(mode=args.mode, input_file=args.input_file)

    # Handle Ctrl+C gracefully
    def handle_sigint(sig, frame):
        logger.info("Interrupted. Closing session...")
        pipeline._close_reason = "keyboard_interrupt"
        pipeline.state = PipelineState.CLOSING
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
