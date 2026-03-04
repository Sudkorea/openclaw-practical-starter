# Voice Agent Example

STT/TTS voice interaction pipeline for OpenClaw — "code lying down."

## What This Agent Does

The voice-agent manages the full speech-to-text → LLM → text-to-speech pipeline:

1. **Receives audio** from Discord, a microphone stream, or a recorded file
2. **Transcribes with STT** (Whisper locally or GCP Speech-to-Text)
3. **Routes the transcript** to the LLM for a response
4. **Synthesizes speech** with TTS (edge-tts locally or GCP Text-to-Speech)
5. **Plays the audio** back to the user
6. **Handles failures** without dropping the session

The goal is to make working with AI agents feel like a conversation, not like
typing — especially useful when you're away from a keyboard.

## File Structure

```
voice-agent/
    README.md               <- this file
    AGENTS.md               <- behavioral rules
    SOUL.md                 <- voice personality / tone
    stt_handler.py          <- Speech-to-Text abstraction (Whisper + GCP)
    tts_handler.py          <- Text-to-Speech abstraction (edge-tts + GCP)
    voice_pipeline.py       <- Main orchestrator tying STT → LLM → TTS
```

## Quick Start

1. Copy this folder to your agent workspace:
   ```
   cp -r examples/voice-agent/ ~/my-agents/voice-agent/
   ```

2. Install dependencies:
   ```
   pip install faster-whisper edge-tts pyaudio sounddevice scipy numpy
   ```

3. For GCP STT/TTS (optional, higher quality):
   ```
   pip install google-cloud-speech google-cloud-texttospeech
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   ```

4. Start the pipeline in `lowcost` mode (local Whisper + edge-tts):
   ```
   python voice_pipeline.py --mode lowcost
   ```

5. Register the agent in OpenClaw with these tools:
   ```json
   {
     "tools": ["read", "write", "message", "sessions_send", "session_status"]
   }
   ```

## Operating Modes

| Mode           | STT                | TTS              | Cost  | Quality |
|----------------|--------------------|------------------|-------|---------|
| `lowcost`      | Local Whisper      | edge-tts (local) | Free  | Good    |
| `hybrid`       | Local Whisper      | GCP TTS          | Low   | Better  |
| `gcp-quality`  | GCP Speech-to-Text | GCP TTS          | Medium| Best    |
| `fallback-safe`| Local Whisper      | edge-tts (local) | Free  | Good    |

**Recommended starting point:** `lowcost` or `hybrid`.
Move to `gcp-quality` after you've validated latency and transcription quality.

## Architecture

```
[Microphone / Discord Audio]
         |
         v
   [stt_handler.py]
     - Silence detection
     - Audio segment extraction
     - Whisper or GCP STT call
     - Returns: transcript (str)
         |
         v
   [voice_pipeline.py]
     - Routes transcript to LLM
     - Handles session state
     - Text sanitization for TTS
         |
         v
   [tts_handler.py]
     - Sanitizes text (strips URLs, code blocks, markdown)
     - edge-tts or GCP TTS call
     - Returns: audio bytes
         |
         v
   [Audio output / Discord playback]
```

## Key Failure Modes and Mitigations

This is a production-relevant summary from real voice pipeline operation.
See `stt_handler.py` and `tts_handler.py` for implementation details.

### 1. Whisper compute type mismatch
**Symptom:** `ValueError: int8_float16 not supported on this device`
**Cause:** CUDA version mismatch or CPU-only environment
**Fix:** Use `compute_type="int8"` for CPU, `"float16"` for GPU, add auto-detection

### 2. GCP STT 400 error on stereo audio
**Symptom:** `google.api_core.exceptions.InvalidArgument: stereo audio`
**Cause:** GCP Speech-to-Text requires mono audio (1 channel)
**Fix:** Downmix stereo to mono before sending; see `stt_handler.py` `_to_mono()`

### 3. Streaming timeout (Audio Timeout Error)
**Symptom:** Session hangs after ~5 minutes of silence
**Cause:** GCP streaming STT has a 5-minute timeout per stream
**Fix:** Detect idle state and restart the stream; see `stt_handler.py` `_restart_stream()`

### 4. TTS reads URLs and code blocks aloud
**Symptom:** TTS says "https colon slash slash docs dot python dot org..."
**Fix:** Pre-sanitize text before TTS; see `tts_handler.py` `sanitize_for_tts()`

### 5. Dead worker (process hung, not responsive)
**Symptom:** Pipeline stops processing audio, no errors
**Cause:** STT worker thread crashed silently
**Fix:** Heartbeat monitor thread; see `voice_pipeline.py` `_watchdog()`

## Latency Optimization

E2E latency = time from end of utterance to start of audio playback.

**Priority P0 (biggest impact):**
- Tune `silence_sec` threshold (0.8-1.2s is typical; too low = false triggers)
- Reduce segment flush interval in streaming mode
- Use local Whisper instead of GCP for STT (saves ~500ms network round-trip)

**Priority P1:**
- Use `faster-whisper` with `distil-whisper` model (3x faster than base whisper)
- Limit LLM response length (short answers read faster)
- Use streaming TTS output (start playing before full synthesis is done)

**Priority P2:**
- GCP TTS WaveNet voices are slower to synthesize than standard voices
- Use Standard voice for low-latency; switch to WaveNet/Neural2 for quality

## Metrics to Track

| Metric                   | Target      | Notes                              |
|--------------------------|-------------|-------------------------------------|
| E2E latency p50          | < 2.5s      | Utterance end → audio start         |
| E2E latency p95          | < 5s        | 95th percentile                    |
| STT error rate           | < 5%        | Failed transcriptions per session  |
| Session timeouts / day   | < 3         | Streaming timeout restarts         |
| False trigger rate       | < 10%       | Audio segments with no actual speech|

See `voice_pipeline.py` for the metrics collection implementation.

## Session Lifecycle

```
[start_session]
     |
     v
[listening]  <--> silence detected, buffer segment
     |
     v
[transcribing]    call STT
     |
     v
[thinking]        LLM response
     |
     v
[speaking]        TTS synthesis + playback
     |
     v
[listening]  <--> repeat
     |
     v (on idle timeout or explicit end)
[session_end]     archive transcript to Airlock
```

Sessions idle-timeout after `SESSION_IDLE_TIMEOUT_SECONDS` (default: 3600s / 1 hour).

## Cost Considerations

- **Local Whisper:** Free. Uses CPU/GPU. `distil-whisper/medium.en` is the best
  quality/speed tradeoff for English.
- **GCP STT:** ~$0.006/15 seconds of audio. A 1-hour session costs ~$1.44.
- **edge-tts:** Free. Uses Microsoft's Azure TTS service under the hood.
- **GCP TTS:** ~$0.004/1000 characters (Standard), $0.016/1000 (WaveNet).
  A typical response of 200 characters costs ~$0.0008-$0.003.
- **LLM calls:** Dominant cost. Keep response length bounded (max 200 tokens
  for voice responses).

## Extending This Example

To add Discord voice channel support:
1. Install `discord.py[voice]` and `PyNaCl`.
2. Implement a Discord audio source that feeds audio frames to `stt_handler.py`.
3. Add a Discord sink that plays TTS audio back to the voice channel.
4. See `docs/09-discord-channel-bot-setup.md` for the Discord bot setup.

To add wake word detection:
1. Install `pvporcupine` (Picovoice Porcupine, free tier available).
2. Wrap `stt_handler.py` with a wake word listener that only activates on detection.
3. This eliminates false triggers from background noise.

See `docs/10-voice-coding-stt-tts.md` for the full voice coding guide.
