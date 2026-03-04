# Cron Agent Example

Central scheduling and orchestration agent for the OpenClaw multi-agent system.

## What This Agent Does

The cron-agent acts as the **central orchestrator** in a multi-agent setup. It:

- Runs scheduled jobs at defined intervals (hourly, daily, weekly)
- Delegates work to domain agents (study-agent, voice-agent, finance-agent, etc.)
- Monitors job outcomes and escalates failures to the main notification channel
- Generates nightly summaries and routes artifacts to the Airlock

## Architecture Overview

```
cron-agent (orchestrator)
    |
    +-- study-agent       (learning queue / RAG curation)
    +-- voice-agent       (STT/TTS session management)
    +-- finance-agent     (cost / budget checks)
    +-- deals-agent       (deal tracking)
    +-- caine-agent       (code execution / file ops)
```

The cron-agent itself does NOT implement domain logic. It reads `cron_jobs.json`,
fires the right agent or script at the right time, and records outcomes.

## File Structure

```
cron-agent/
    README.md               <- this file
    AGENTS.md               <- behavioral rules loaded by the agent at startup
    SOUL.md                 <- personality / tone directives
    cron_jobs.json          <- schedule definitions (edit this to add/remove jobs)
    example_scripts/
        nightly_summary.py  <- generates a nightly ops summary
        health_check.py     <- pings all sub-agents and logs their status
        airlock_cleanup.py  <- archives old airlock records
        cost_report.py      <- pulls GCP billing snapshot
```

## Quick Start

1. Copy this folder to your agent workspace:
   ```
   cp -r examples/cron-agent/ ~/my-agents/cron-agent/
   ```

2. Edit `cron_jobs.json` to match your schedule and agent names.

3. Place `AGENTS.md` and `SOUL.md` at the root of the agent workspace so
   OpenClaw picks them up automatically on agent start.

4. Register the agent in OpenClaw with the cron tool enabled:
   ```json
   {
     "tools": ["cron", "sessions_send", "sessions_list", "message", "read", "write"]
   }
   ```

5. The agent will read `cron_jobs.json` on startup and register all jobs.

## Cron Job Configuration

Jobs are defined in `cron_jobs.json`. Each entry specifies:

- `id`: unique identifier used in logs
- `schedule`: cron expression (standard 5-field format)
- `action`: what to run — `script`, `agent_message`, or `agent_spawn`
- `target`: script path OR agent name
- `payload`: arguments / message body
- `on_failure`: `escalate` (alert main channel) or `log_only`
- `enabled`: set to `false` to disable without deleting

### Schedule Examples

| Expression      | Meaning                     |
|-----------------|-----------------------------|
| `0 * * * *`     | Every hour on the hour      |
| `0 9 * * *`     | Daily at 09:00              |
| `0 22 * * *`    | Daily at 22:00 (nightly)    |
| `0 9 * * 1`     | Every Monday at 09:00       |
| `*/15 * * * *`  | Every 15 minutes            |
| `0 9,17 * * *`  | At 09:00 and 17:00 daily    |

## Handoff Packet Standard

When delegating to a sub-agent, the cron-agent sends a handoff packet
conforming to `schemas/handoff_packet.schema.json`:

```json
{
  "objective": "Generate nightly study queue candidates from today's airlock",
  "scope": {
    "files": ["/airlock/daily/2026-02-18/"],
    "commands": []
  },
  "constraints": {
    "runtime": "5min",
    "budget": "low",
    "style": "append-only"
  },
  "acceptance": {
    "output_file": "/airlock/study_queue/2026-02-18.json",
    "format": "valid JSON"
  },
  "risk": "low"
}
```

## Failure Handling

Jobs that fail follow the `on_failure` policy:

- `escalate`: The agent posts to the main notification channel with a short
  summary of what failed, then logs the full error to Airlock.
- `log_only`: The error is written to Airlock only. No alert is sent.

Repeated failures (3+ times in one day) always escalate regardless of policy.

## Operational Rules

1. Do not run domain logic inside the cron-agent itself — delegate.
2. Log every job start and outcome to Airlock.
3. Never fire duplicate jobs for the same event within one window.
4. Verify sub-agent completion before marking a job done.
5. Keep the schedule file (`cron_jobs.json`) as the single source of truth.

## Cost Considerations

- The cron-agent itself should use a cheap/fast model for routing decisions.
- Reserve expensive models for the domain agents that do real reasoning.
- Each job invocation costs tokens; keep orchestration prompts short.
- Use `log_only` for low-stakes jobs to reduce message volume.

## Extending This Example

To add a new domain agent:

1. Add a new entry to `cron_jobs.json` with `action: "agent_message"`.
2. Make sure the target agent name matches its registered name in OpenClaw.
3. Define the handoff packet in the `payload` field.
4. Test with a manual trigger before enabling the schedule.

See `docs/06-multi-agent-architecture.md` and `docs/13-subagent-orchestration.md`
for deeper architecture guidance.
