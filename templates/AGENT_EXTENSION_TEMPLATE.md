# Airlock Record Template

<!--
USAGE: Copy this file and fill it in immediately after completing any agent task.
This is the Airlock-first record. One file per task session, stored under:
  ~/.openclaw/repos/obsidian-vault/airlock/daily/

Naming convention: YYYY-MM-DD-[agent-name]-[2-4 word slug].md
Example:           2026-02-18-api-agent-user-validation.md

Sections marked [REQUIRED] must be filled in. [OPTIONAL] sections can be removed
if not applicable, but err on the side of including them.
-->

---

## TL;DR

<!--
[REQUIRED] One sentence. What was accomplished (or attempted and failed)?
This is what the nightly orchestrator reads first to classify and index.

Good examples:
- "Added Pydantic input validation to POST /api/users endpoint."
- "Curated 8 study candidates from 12 airlock records for 2026-02-18."
- "Attempted to migrate DB schema; blocked by missing backup — escalated."
- "Research note on Vertex AI quota limits written to /notes/vertex-quota.md."

Bad examples (too vague):
- "Did some work on the API."
- "Research task."
-->

[CUSTOMIZE: One sentence summary of the outcome]

---

## Context

<!--
[REQUIRED] Why was this task run? What triggered it?
Include: who/what triggered the session, what the goal was, what state things were in before.
Keep it to 3-5 lines. This lets a future reader understand the task without reading the full log.
-->

**Triggered by:** [CUSTOMIZE: e.g., cron-agent nightly schedule / operator request / manual]
**Goal:** [CUSTOMIZE: e.g., Add input validation to the users endpoint to prevent empty name submissions]
**Pre-task state:** [CUSTOMIZE: e.g., Tests passing, no validation on POST /api/users, 44 existing tests]

**Relevant files at start:**
- [CUSTOMIZE: e.g., api/routes/users.py — no validation present]
- [CUSTOMIZE: e.g., api/tests/test_users.py — 44 tests, all passing]

---

## Problem / Acceptance

<!--
[REQUIRED] What was the acceptance criteria for this task?
Copy from the handoff packet if one was provided, or state it explicitly.
This is the definition of "done" — used to verify whether this record counts as complete.
-->

**Acceptance criteria:**
- [ ] [CUSTOMIZE: e.g., POST /api/users rejects empty name with 422 and clear error message]
- [ ] [CUSTOMIZE: e.g., All existing tests still pass]
- [ ] [CUSTOMIZE: e.g., At least 2 new tests cover the validation cases]
- [ ] [CUSTOMIZE: e.g., ruff lint passes with zero new warnings]

**Risk level:** [CUSTOMIZE: low | medium | high]

**Risk notes:** [CUSTOMIZE: e.g., Low — no DB changes, no schema migrations, pure validation layer]

---

## Execution Logs

<!--
[REQUIRED] What commands were run? What was the output?
Include: commands executed, key output lines, errors encountered, how errors were resolved.
Do NOT paste thousands of lines of test output — summarize and include only the critical lines.
-->

### Commands run and results

```
[CUSTOMIZE: paste or reconstruct the key commands and their outputs]
```

**Example format:**
```
$ pytest api/tests/ -q --tb=short     [BEFORE changes]
44 passed in 1.23s

$ ruff check api/
0 errors

[Made changes to api/routes/users.py and api/tests/test_users.py]

$ pytest api/tests/ -q --tb=short     [AFTER changes]
47 passed in 1.31s

$ ruff check api/
0 errors
```

### Errors encountered (if any)

<!--
[OPTIONAL] If errors occurred, log them here with resolution.
-->

| Error | Root cause | Resolution |
|-------|-----------|------------|
| [CUSTOMIZE: e.g., `ValidationError: field required`] | [CUSTOMIZE: e.g., Pydantic model missing default] | [CUSTOMIZE: e.g., Added default=None with Optional type] |

### Retries / pivots

<!--
[OPTIONAL] If you changed approach mid-task, explain why here.
This is valuable for the study queue — failed approaches are learning material.
-->

- [CUSTOMIZE: e.g., First tried using FastAPI's built-in validators, but they don't produce the custom error format required. Switched to Pydantic v2 model validators instead.]

---

## Changes

<!--
[REQUIRED] List every file that was modified, created, or deleted.
Be specific: note what changed, not just which file.
-->

### Modified
- `[CUSTOMIZE: e.g., api/routes/users.py]` — [CUSTOMIZE: e.g., Added UserCreateRequest Pydantic model with name: str validator (non-empty)]
- `[CUSTOMIZE: e.g., api/tests/test_users.py]` — [CUSTOMIZE: e.g., Added 3 test cases: empty name, whitespace-only name, valid name]

### Created
- `[CUSTOMIZE: e.g., api/models/requests.py]` — [CUSTOMIZE: e.g., New file: shared Pydantic request models]

### Deleted
- [CUSTOMIZE: e.g., None] — or list files with reason for deletion

### Dependencies added
- [CUSTOMIZE: e.g., None] — or list new packages with justification

### Config / environment changes
- [CUSTOMIZE: e.g., None] — or list changes to .env, config files, etc.

---

## Validation

<!--
[REQUIRED] Proof that acceptance criteria were met (or not met).
Include the actual command output, not just "tests pass."
-->

### Test results
```
[CUSTOMIZE: paste the final test run output]
```

Example:
```
$ pytest api/tests/ -q --tb=short
47 passed in 1.31s
```

### Lint results
```
[CUSTOMIZE: paste the lint output]
```

### Manual validation (if applicable)
```
[CUSTOMIZE: describe any manual steps taken to verify behavior]
```

Example:
```
$ curl -X POST http://localhost:8000/api/users -d '{"name": ""}'
{"detail": "name must not be empty"}   ← expected 422 response confirmed
```

### Acceptance criteria outcome
- [x] [CUSTOMIZE: e.g., POST /api/users rejects empty name with 422] — PASS
- [x] [CUSTOMIZE: e.g., All existing tests pass] — PASS (47 total, 44 existing + 3 new)
- [x] [CUSTOMIZE: e.g., 2+ new tests added] — PASS (3 new tests)
- [x] [CUSTOMIZE: e.g., ruff lint clean] — PASS

---

## Rollback / Safety

<!--
[REQUIRED for risk=medium or high, OPTIONAL for risk=low]
How can this change be undone if something goes wrong?
-->

**Rollback steps:**
1. [CUSTOMIZE: e.g., `git revert HEAD` — changes are in a single commit]
2. [CUSTOMIZE: e.g., `pytest api/tests/ -q` — verify 44 tests pass after revert]

**Data safety:**
- [CUSTOMIZE: e.g., No database changes — rollback is purely a code revert]
- [CUSTOMIZE: e.g., No secrets were created, modified, or exposed]

**Blast radius if left in place with a bug:**
- [CUSTOMIZE: e.g., Users with empty names would be rejected — this is the intended behavior, so a bug here would cause false rejections. Monitoring: check 422 rate on /api/users for 24h after deploy.]

---

## Classification / Handoff

<!--
[REQUIRED] How should the nightly orchestrator classify this record?
What happens next after this task?
-->

**Category:** [CUSTOMIZE: code | research | analysis | curation | ops | voice | infra | other]

**Tags:** [CUSTOMIZE: e.g., python, api, validation, pydantic, fastapi]

**Study candidate:** [CUSTOMIZE: YES / NO]
- If YES, explain why: [CUSTOMIZE: e.g., First time using Pydantic v2 field validators — the migration from v1 validators was non-obvious and worth reviewing]

**Handoff:**
- [CUSTOMIZE: e.g., None — task is complete and self-contained]
- [CUSTOMIZE: e.g., Notify frontend-agent: POST /api/users now returns 422 with new error schema]
- [CUSTOMIZE: e.g., cron-agent: schedule nightly validation report to pick up from /airlock/daily/]

**Handoff packet (if handing off):**
```json
{
  "objective": "[CUSTOMIZE]",
  "scope": {
    "files": ["[CUSTOMIZE]"],
    "commands": ["[CUSTOMIZE]"]
  },
  "constraints": {
    "runtime": "[CUSTOMIZE]",
    "security": "[CUSTOMIZE]"
  },
  "acceptance": {
    "tests": "[CUSTOMIZE]",
    "manual": "[CUSTOMIZE]"
  },
  "risk": "[CUSTOMIZE: low | medium | high]"
}
```

---

## TODO

<!--
[OPTIONAL] Anything left undone, discovered during this session, or needing follow-up.
These become the seed for the next task or a study queue entry.
-->

### Remaining work
- [ ] [CUSTOMIZE: e.g., Add validation for the PATCH /api/users endpoint — same pattern applies]
- [ ] [CUSTOMIZE: e.g., Update API documentation to reflect new 422 error response format]

### Discovered issues (not blocking, but noted)
- [CUSTOMIZE: e.g., The existing GET /api/users endpoint has no rate limiting. Flagged for future sprint.]

### Questions / uncertainties
- [CUSTOMIZE: e.g., Should empty-string names be normalized to null at the DB level? Currently rejected at API layer only. Need product decision.]

### Performance notes (for extension/integration tasks)
<!--
[OPTIONAL] If this was a performance-sensitive task or integration, capture metrics here.
-->
- **Latency impact:** [CUSTOMIZE: e.g., Pydantic validation adds ~0.2ms per request — acceptable]
- **Memory impact:** [CUSTOMIZE: e.g., None measured]
- **Integration points:** [CUSTOMIZE: e.g., Frontend must update error handling to catch 422 in addition to 400]

---

<!--
INTEGRATION PATTERNS NOTE (for extension-type records):

If this airlock record documents an Extension (not a standalone agent session),
also capture the following to help the next person replicate or automate it:

## Extension Integration Pattern

**How it was invoked:**
[Describe the prompt or command used to trigger this Extension behavior]

**Context required:**
[What files/context did the model need to do this task? List them.]

**Reusability:**
[Could this be automated as an Agent? If yes, what would be needed?]
[If no, why is it best kept as an Extension?]

**Performance characteristics:**
- Tokens used: [estimate]
- Time to complete: [wall clock]
- Model used: [e.g., claude-sonnet-4-5]

This section is the bridge between Extension use and Agent promotion.
When the same Extension pattern appears 3+ times, promote it to an Agent.
-->
