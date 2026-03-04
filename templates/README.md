# Templates

This directory contains the core templates for configuring OpenClaw agents and
recording their work. Start here when creating a new agent or writing your first
Airlock record.

---

## What is in this directory

| File | Purpose | When to use |
|------|---------|-------------|
| `AGENT_TEMPLATE_CODE.md` | System prompt template for code agents | Creating an agent that writes, edits, or runs code |
| `AGENT_TEMPLATE_NONCODE.md` | System prompt template for non-code agents | Creating an agent for research, writing, analysis, curation |
| `AGENT_EXTENSION_TEMPLATE.md` | Airlock record template | After completing any agent task session |

---

## Deciding which agent template to use

The key question is: **what does this agent produce?**

Use `AGENT_TEMPLATE_CODE.md` when the agent:
- Writes, edits, or deletes source code files
- Runs tests, linters, or shell commands
- Manages dependencies, schemas, or migrations
- Produces diffs, patches, or build artifacts

Use `AGENT_TEMPLATE_NONCODE.md` when the agent:
- Produces research notes, summaries, reports, or digests
- Curates study queues or knowledge bases
- Transcribes, tags, or classifies content
- Monitors channels or feeds and produces structured output
- Does analysis without touching a codebase

If the agent does both (e.g., a PM agent that plans work and delegates code tasks),
start with the non-code template for the planning/routing logic, and use separate
code agents for execution.

---

## How to use AGENT_TEMPLATE_CODE.md

This template becomes the `AGENTS.md` file in your agent workspace. It is loaded
by OpenClaw as the agent's system prompt on every session start.

### Step 1: Copy the template

```bash
cp templates/AGENT_TEMPLATE_CODE.md \
   ~/.openclaw/workspace-my-agent/AGENTS.md
```

### Step 2: Fill in every [CUSTOMIZE] marker

Open the file and search for `[CUSTOMIZE]`. Each one is a required field.
The most important ones:

- **Role / Scope** — the one-line description and the in/out-of-scope lists.
  This is what keeps the agent from drifting. Be specific about file paths and
  programming languages.

- **Routing / Handoff** — the routing table. Map each task type to a specific
  agent name. If you only have one agent, point out-of-scope tasks to "human".

- **Execution Rules** — the test/lint commands for your specific stack.
  Replace `pytest api/tests/ -q` with your actual commands.

- **Output Policy** — the airlock path. Use an absolute path.

- **Local Constraints** — the runtime environment: Python version, virtualenv
  path, working directory.

### Step 3: Remove [OPTIONAL] sections that do not apply

Sections labeled `[OPTIONAL]` are safe to delete. A shorter, precise prompt
outperforms a long one with unused sections.

### Step 4: Add companion files (optional but recommended)

The agent workspace can also contain:

```
~/.openclaw/workspace-my-agent/
    AGENTS.md     <- the filled-in code template (required)
    SOUL.md       <- tone / personality (keep it short: 5-10 lines)
    IDENTITY.md   <- one-line identity ("I am X, responsible for Y")
    TOOLS.md      <- notes on tool-specific usage patterns
    USER.md       <- operator preferences / context the agent should know
```

See `docs/14-openclaw-prompt-setup-and-tools.md` for details on each file.

### Example: a Python API agent

```markdown
## Role / Scope

You are **api-agent**, a specialist code agent responsible for
**Python backend services in ~/project/api/**.

In scope:
- Writing and editing .py files under ~/project/api/
- Running pytest and ruff in the api/ directory
- Generating Pydantic models and FastAPI routes

Out of scope:
- Frontend (React) — route to frontend-agent
- Database migrations — route to db-agent
- Production deploys — escalate to human

Primary workspace: ~/project/api/
```

---

## How to use AGENT_TEMPLATE_NONCODE.md

Same copy-and-customize process as the code template, but with key differences:

### The Tool Selection Guidance section is critical

Non-code agents need explicit guidance on which tool to use for each task type.
Fill in the tool allowlist and budget carefully:

```
# Only grant tools the agent actually needs
read
write          # only if it writes files
web_search     # only if it needs current information
memory_search  # useful for avoiding duplicate work
sessions_send  # only if it hands off to other agents
message        # only for operator alerts
```

Granting tools the agent does not need increases cost and risk. A study curation
agent that only reads airlock files does not need `web_search` or `exec`.

### The upstream/downstream chain matters

Non-code agents usually sit in a pipeline. Fill in:
- **Upstream**: what triggers this agent and where its input comes from
- **Downstream**: where it sends its output and who acts on it

This prevents the agent from producing output that nobody reads, or waiting for
input that never arrives.

### Example: a study curation agent

```markdown
## Role / Scope

You are **study-agent**, a specialist agent responsible for
**curating daily study queue candidates from the Airlock**.

In scope:
- Reading files in ~/.openclaw/repos/obsidian-vault/airlock/daily/
- Selecting and scoring study candidates
- Writing study queue JSON to /airlock/study_queue/

Out of scope:
- Any code changes — route to api-agent
- Scheduling — handled by cron-agent

Read-only status: NO (writes to /airlock/study_queue/ only)

## Routing / Handoff

Upstream: triggered by cron-agent at 22:30 daily
Source data: /airlock/daily/ files from the past 24 hours

Downstream:
- Writes to /airlock/study_queue/YYYY-MM-DD.json
- Notifies cron-agent via sessions_send when complete
```

---

## How to use AGENT_EXTENSION_TEMPLATE.md

This is the **Airlock record template**. It is not an agent system prompt —
it is the file you (or an agent) fill in after completing a task. Think of it
as a structured work log.

### When to create a record

Create one Airlock record per task session when:
- Any file was modified, created, or deleted
- A test or command was run (pass or fail)
- A handoff was sent to another agent
- A task was attempted and failed (failures are especially valuable for the study queue)

Do NOT create a record for:
- Read-only exploration with no output
- A question answered in chat with no artifact written

### Naming and placement

```
~/.openclaw/repos/obsidian-vault/airlock/daily/
    YYYY-MM-DD-[agent-name]-[2-4 word slug].md
```

Examples:
```
2026-02-18-api-agent-user-validation.md
2026-02-18-study-agent-queue-curation.md
2026-02-18-cron-agent-nightly-run.md
```

### Filling in the record

Every record requires these sections (`[REQUIRED]`):

1. **TL;DR** — one sentence. The nightly orchestrator reads this to classify the record.
2. **Context** — what triggered the task and the pre-task state.
3. **Problem / Acceptance** — the acceptance criteria (definition of done).
4. **Execution Logs** — key commands and their output. Do not paste thousands of lines.
5. **Changes** — every file modified, created, or deleted.
6. **Validation** — proof that the acceptance criteria passed.
7. **Classification / Handoff** — category, tags, study candidate flag, next agent.

Optional sections (`[OPTIONAL]`):
- **Rollback / Safety** — required for `risk=medium` or `high`
- **TODO** — remaining work, discovered issues, open questions
- **Extension Integration Pattern** — only for Extension (not agent session) records

### The study candidate flag

Set `Study candidate: YES` when this session involved something non-obvious that
you or the agent had to figure out — a new library API, an unexpected failure
mode, a pattern that appeared for the first time. These entries are picked up
by the nightly orchestrator and added to the study queue.

Set `Study candidate: NO` for routine operations where everything went as expected.

---

## The Airlock loop: how these templates connect

```
[Agent runs a task]
        |
        v
[Fills in AGENT_EXTENSION_TEMPLATE.md]
[Saves to airlock/daily/YYYY-MM-DD-*.md]
        |
        v
[nightly cron-agent runs airlock_orchestrator.py]
        |
        +-- Reads TL;DR, Category, Tags
        +-- Classifies into bucket (ops / study / finance / etc.)
        +-- Identifies study candidates
        +-- Writes airlock/index/YYYY-MM-DD.json
        |
        v
[study-agent picks up study_queue candidates]
[operator reviews journal / KPI snapshot]
```

The Airlock record template is the entry point for this loop. Without it,
the orchestrator has nothing to classify and the study queue stays empty.

---

## Common mistakes and how to avoid them

**TL;DR is too vague.**
Bad: "Did some coding work."
Good: "Added Pydantic v2 validator to POST /api/users endpoint; all 47 tests pass."

**Acceptance criteria left blank.**
Fill in the Problem / Acceptance section before starting the task, not after.
This keeps the agent focused and makes the validation section easy to write.

**Study candidate always set to NO.**
If you or the agent had to look something up, pivot approaches, or hit an
unexpected error — that is a study candidate. Set it to YES and explain why
in one sentence.

**Tool allowlist too broad.**
Start with the minimum set of tools. Add tools only when a task genuinely
requires them. An agent with read-only access to airlock files does not need
`exec`, `web_search`, or `sessions_spawn`.

**One giant agent instead of specialized agents.**
If an agent's Role / Scope section lists more than 5-6 distinct task types,
split it. Role overlap is the most common source of context pollution and
incorrect handoffs.

---

## Related files

- `schemas/handoff_packet.schema.json` — JSON schema for inter-agent handoffs
- `schemas/airlock_index.schema.json` — JSON schema for airlock index files
- `docs/05-extension-vs-agent.md` — when to use an Extension vs a full Agent
- `docs/06-multi-agent-architecture.md` — recommended agent topology
- `docs/07-airlock-first-ops.md` — the daily Airlock operations loop
- `docs/13-subagent-orchestration.md` — routing chains and PM patterns
- `docs/14-openclaw-prompt-setup-and-tools.md` — complete prompt setup guide
