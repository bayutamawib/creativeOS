# CREATIVE OS AI Engineering Case Study

## Problem

Agency teams need to turn approved briefs into useful creative work while retaining traceability, factual caution, and human control over decisions sent downstream.

## Architecture and workflow

Next.js Creative Studio submits authenticated, idempotent jobs to FastAPI. PostgreSQL binds each job to an approved brief snapshot and stores provider/model, prompt version, status, attempts, token counts, latency, validated output, and quality findings. A Python worker claims jobs; Pydantic validates responses before proposals are persisted. The UI polls job state and shows findings and output.

The four stages are Brief Analysis → Creative Strategy → Content Plan → Copywriting. The analysis informs strategy; a human selects a direction before planning; a human selects a plan item before copy generation. Draft content remains subject to internal review, release, and client decision.

## Prompts, validation, and quality

Prompts are versioned with each job. The compatible HTTPS adapter requests JSON-object output, and generation-specific Pydantic contracts validate structure. A separate conservative lexical quality checker records findings; “clear” is not a factual guarantee or editorial-quality score. Human review remains required.

## Verified Aurora Vale live results

All four records below are persisted live Groq results for synthetic snapshot `3efde19a-7324-476f-9f25-b1f100362740`, model `openai/gpt-oss-20b`, prompt `creative-v5`:

| Stage | Status | Attempts | Input/output tokens | Latency | Quality |
|---|---:|---:|---:|---:|---|
| Brief Analysis | completed | 1 | 1,023 / 1,414 | 2,607 ms | clear |
| Creative Strategy | completed | 1 | 1,394 / 739 | 1,334 ms | clear |
| Content Plan | completed | 1 | 1,271 / 752 | 1,410 ms | review |
| Copywriting | completed | 2 | 1,518 / 1,097 | 1,806 ms | clear |

The plan’s review findings flag “Join the waitlist for early access” as an unconfirmed operational assumption. The copywriting record has two attempts; this case study does not infer the cause of its first attempt. These results establish successful persisted stages on this synthetic brief, not general model reliability or factual correctness.

## Engineering decisions and boundaries

- Fixture provider remains the normal local default; compatible live inference is explicit runtime configuration.
- A worker-mode setting can isolate AI consumption from outbox dispatch while preserving `all` as the default.
- Human selection and release gates remain application-authorized backend operations.
- Historical fixture and earlier prompt runs remain immutable evidence.
- A small synthetic sample cannot establish creative effectiveness. Quality findings are narrow and require human assessment.
- Local Compose is a development/portfolio setup, not a production deployment.
