# Study Agent Example

Learning queue curation and spaced repetition automation for OpenClaw.

## What This Agent Does

The study-agent automates the learning feedback loop that comes naturally from
working with AI agents every day:

1. **Curates study candidates** from the Airlock — every session where something
   was confusing, required multiple retries, or surfaced a new concept gets
   flagged as a learning opportunity.
2. **Applies spaced repetition scheduling** — items are queued for review at
   3-day, 7-day, and 21-day intervals to convert short-term exposure into
   long-term retention.
3. **Generates knowledge extractions** — for each queued item, it produces a
   short structured note: concept, why it matters, a self-check question.
4. **Integrates with RAG** — extracted knowledge can be indexed into a vector
   store so the agent (and you) can query "what do I know about X?" later.

## File Structure

```
study-agent/
    README.md                   <- this file
    AGENTS.md                   <- behavioral rules
    SOUL.md                     <- personality / tone
    study_queue_processor.py    <- core queue processing logic
    knowledge_extractor.py      <- extracts and formats knowledge from airlock records
    config/
        rag_config.json         <- RAG integration settings (Chroma / Weaviate / etc.)
        review_schedule.json    <- spaced repetition intervals
        study_profile.json      <- user learning preferences
```

## Quick Start

1. Copy this folder to your agent workspace:
   ```
   cp -r examples/study-agent/ ~/my-agents/study-agent/
   ```

2. Edit `config/study_profile.json` to set your learning preferences (topic
   priorities, daily item limit, etc.).

3. Register the agent in OpenClaw with these tools enabled:
   ```json
   {
     "tools": ["read", "write", "memory_search", "memory_get", "sessions_send", "message"]
   }
   ```
   Add `"web_search"` if you want the agent to fetch supplementary context.

4. The cron-agent will trigger this agent nightly. You can also run manually:
   ```
   python study_queue_processor.py --date today
   ```

## Spaced Repetition Schedule

The default review schedule (configurable in `config/review_schedule.json`):

| Review         | Interval | Goal                                   |
|----------------|----------|----------------------------------------|
| First review   | +3 days  | Encode into short-term memory          |
| Second review  | +7 days  | Transfer to medium-term memory         |
| Third review   | +21 days | Confirm long-term retention            |
| Maintenance    | +60 days | Keep rarely-used knowledge accessible  |

Items that fail a review are reset to the first review interval.

## Study Queue Item Format

Each item in the queue is a JSON object:

```json
{
  "id": "2026-02-18-vertex-quota-limits",
  "topic": "Vertex AI quota limits",
  "source_file": "/airlock/daily/2026-02-18-api-agent-vertex-error.md",
  "first_seen": "2026-02-18",
  "next_review": "2026-02-21",
  "review_count": 0,
  "priority": "high",
  "concept_summary": "Vertex AI enforces per-minute and per-day token quotas per project. Exceeding them returns 429. Solution: exponential backoff + quota increase request.",
  "self_check_question": "What HTTP status does Vertex AI return when you exceed the quota, and what is the recommended handling strategy?"
}
```

## RAG Integration

The study-agent can write extracted knowledge to a vector store for semantic
search. This enables queries like:

- "What do I know about Vertex AI quotas?"
- "Have I encountered connection timeout errors before?"
- "What debugging approaches have worked for async race conditions?"

See `config/rag_config.json` for the connection settings. Supported backends:

- **Chroma** (default, local) — zero setup, good for personal use
- **Weaviate** — better for team/shared knowledge bases
- **pgvector** — if you're already using PostgreSQL

The `knowledge_extractor.py` handles the extraction-to-indexing pipeline.

## State Tracking

The agent maintains three categories for each study item:

| State      | Meaning                                             |
|------------|-----------------------------------------------------|
| `unknown`  | Topic not yet studied — eligible for first review   |
| `learning` | In the review cycle — has a scheduled next_review   |
| `known`    | Completed all review intervals without failure      |
| `skipped`  | Operator marked as not worth studying               |

State is persisted in `study_queue/` JSON files. The agent never deletes items;
it only transitions their state. This preserves the history of what was learned and when.

## Duplicate Prevention

Before adding a new item to the queue, the agent checks:

1. Has this topic appeared in the queue within the last 7 days?
2. Is this topic already in `known` state?
3. Is this topic in the study profile's `skip_topics` list?

If any check is true, the item is not added (but a note is written to the Airlock
explaining the skip, so you can review the decision later).

## Cost Considerations

- The nightly curation pass should use a cheap model — it's mostly classification.
- The knowledge extraction step (generating concept summaries) can use a mid-tier
  model since quality matters here.
- RAG embedding calls are cheap but non-zero; batch them when indexing many items.
- Limit daily queue size (default: 10 items/day) to prevent overwhelm and token cost.

## Extending This Example

To integrate with a different note-taking system (Obsidian, Notion, etc.):

1. Modify the output path in `config/study_profile.json`.
2. Adjust the output format in `knowledge_extractor.py` (`format_for_output` function).
3. Notion integration requires the Notion API; add it as a tool or call it from a script.

See `docs/08-rag-studybot.md` for deeper context on the study bot design philosophy.
