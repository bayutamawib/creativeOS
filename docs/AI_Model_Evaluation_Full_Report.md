# CREATIVE OS — AI Model Evaluation & Grounding Report

**Project:** CREATIVE OS — AI-assisted agency operations and creative workflow automation  
**Model evaluated:** `openai/gpt-oss-20b` via Groq / compatible adapter  
**Evaluation material:** synthetic campaign briefs (Morrow Orchard and Aurora Vale)  
**Report date:** 25 November 2026  
**Evidence basis:** prior testing discussions and historical, repository-published evaluation records; no new inference or evaluation was executed to create this report.

> **Executive finding:** The system demonstrated successful structured generation and measurable improvement in some grounding scores, but technical success did **not** consistently translate into editorial acceptance. The historical Morrow Orchard evaluation contained unresolved critical claims and weak copy distinctiveness. A separate Aurora Vale `creative-v5` four-stage live chain completed, with one stage still requiring review. These are **two different evaluation cohorts**, not interchangeable measurements.

## 1. Scope and methodology

The evaluated workflow consists of four stages:

`Approved Brief → Brief Analysis → Creative Strategy → Content Plan → Copywriting → Human Review`

The **Morrow Orchard** assessment used one frozen synthetic campaign brief and a human editorial rubric with five dimensions, each scored from **1 (low) to 5 (high)**:

| Metric | What the assessment examined |
|---|---|
| **Relevance** | Alignment of the output with the requested campaign and stage objectives |
| **Specificity** | Useful, concrete detail rather than generic suggestions |
| **Grounding** | Whether factual or operational claims are supported by the approved brief/context |
| **Distinctiveness** | Meaningful differentiation between proposals or between a draft and revised copy |
| **Actionability** | Whether a human team can use the output to progress the creative workflow |

**Documented editorial acceptance criteria:** all five dimensions **≥ 3/5**, no unresolved **critical** claim findings, valid stage-specific schema, required deliverable/channel coverage, and intact human approval gates. The arithmetic mean alone cannot override a failed dimension.

**Technical checks were evaluated separately:** strict JSON/Pydantic schema validation, count/channel constraints, provenance, deterministic lexical claim checks (`clear`, `review`, `critical`), and state/authorization transitions. A `clear` lexical result does **not** certify semantic factual grounding.

## 2. Morrow Orchard — baseline vs latest evaluated stage results

The baseline was the sequential **Phase 2C `creative-v1`** live run. The “latest” historical comparison combines individually evaluated Phase 2E stages, **including human-reviewed handoffs for Content Plan and Copywriting**; it is **not** a single autonomous end-to-end chain.

| Stage | Baseline grounding | Latest grounding | Change | Baseline editorial mean | Latest editorial mean | Latest claim check | Latest editorial disposition |
|---|---:|---:|---:|---:|---:|---|---|
| Brief Analysis | 2/5 | **4/5** | +2 | 3.0/5 | **3.8/5** | `clear` | Owner review required |
| Creative Strategy | 2/5 | **1/5** | −1 | 3.2/5 | **3.0/5** | `critical` | Rejected: critical claims |
| Content Plan | 1/5 | **2/5** | +1 | 2.6/5 | **3.6/5** | `critical` | Rejected: critical claim |
| Copywriting | 2/5 | **4/5** | +2 | 2.2/5 | **3.4/5** | `clear` | Revision required |

**Interpretation:** The Brief Analysis score improved from 2 to 4. Creative Strategy deteriorated to 1/5 in the selected latest run. Content Plan and Copywriting improved on the reported grounding rubric but used **human-reviewed upstream handoffs**, preventing attribution of the improvement solely to model or prompt changes. Copywriting remained below threshold on distinctiveness.

### 2.1 Full five-dimension human ratings

Values below are ordered **Relevance / Specificity / Grounding / Distinctiveness / Actionability**.

| Stage | Baseline (`creative-v1`) | Latest historical assessment |
|---|---|---|
| Brief Analysis | **5 / 3 / 2 / 2 / 3** | **5 / 4 / 4 / 3 / 3** |
| Creative Strategy | **5 / 3 / 2 / 3 / 3** | **5 / 4 / 1 / 2 / 3** (`creative-v3`, Run C) |
| Content Plan | **4 / 3 / 1 / 2 / 3** | **5 / 4 / 2 / 3 / 4** (human-reviewed strategy handoff) |
| Copywriting | **4 / 2 / 2 / 1 / 2** | **5 / 3 / 4 / 2 / 3** (human-reviewed plan handoff) |

**Critical detail:** Latest Copywriting scored **2/5 distinctiveness** because the caption and CTA were repeated verbatim, despite a `clear` deterministic claim check. Its revision notes also overstated the changes made.

## 3. Historical runs and failure analysis

| Run | Prompt | Schema/technical outcome | Grounding | Claim findings | Assessment |
|---|---|---|---:|---|---|
| Phase 2C Brief Analysis | `creative-v1` | Passed | 2/5 | Claim check not stored in baseline | Requires revision |
| Phase 2C Creative Strategy | `creative-v1` | Passed | 2/5 | Claim check not stored in baseline | Requires revision |
| Phase 2C Content Plan | `creative-v1` | Passed (count/channels) | 1/5 | Claim check not stored in baseline | Requires revision |
| Phase 2C Copywriting | `creative-v1` | Passed | 2/5 | Claim check not stored in baseline | Requires revision |
| Phase 2E initial Brief Analysis | `creative-v2` | **Not evaluated:** local capture error | N/A | Not evaluated | Excluded from quality claims |
| Phase 2E Brief Analysis retry | `creative-v2` | Passed | 4/5 | `clear` | Owner review required |
| Phase 2E Strategy Run A retry | `creative-v2` | **Failed strict parsing:** duplicate `creative_directions` keys | 2/5* | Review on truncated historical output | Invalid strict JSON result |
| Phase 2E Strategy Run B | `creative-v2` | Passed | 2/5 | `review` (2) | Revision required |
| Phase 2E Strategy Run C | `creative-v3` | Passed | 1/5 | `critical` (2) | Rejected |
| Phase 2E Content Plan Run A | `creative-v2` | Passed; human-reviewed upstream handoff | 2/5 | `critical` (1) | Rejected |
| Phase 2E Copywriting Run A | `creative-v2` | Passed; human-reviewed upstream handoff | 4/5 | `clear` | Revision required |

\* The score for Strategy Run A reflects the **historical/truncated record**, not a valid strictly parsed complete response; it should not be treated as a successful structured generation.

### 3.1 Observed failure modes

1. **Unsupported claims propagated between stages.** Outputs introduced claims about freshness, exact fruit varieties, sensory qualities, presumed audience behaviors, and operational actions without sufficient brief support.
2. **Schema validity ≠ grounding.** Structurally valid JSON could contain factual inaccuracies or violate brief restrictions. The initial baseline passed all four schemas but all four outputs required editorial revision.
3. **Duplicate JSON keys.** One strategy response repeated the top-level `creative_directions` key. Permissive parsing could silently keep the last value; strict duplicate-key rejection later prevented this silent loss.
4. **Response capture failure.** A Groq response was received, but recorder logic accessed `response.body` rather than the adapter’s `Response.content`. The record must be treated as **not evaluated**, not as a model-quality failure. The pipeline was subsequently changed to capture raw output before schema validation.
5. **Copy reuse and misleading revision notes.** Copywriting sometimes repeated source caption/CTA exactly while claiming a substantive refinement.
6. **Limited lexical checking.** Pattern rules can flag known unsupported claims, but may miss paraphrases, cross-language claims, or nuanced semantic contradictions.

### 3.2 Mitigations implemented during testing

- Versioned prompts: `creative-v1`, `creative-v2`, later targeted `creative-v3`, and current `creative-v5` in the application.
- Strict JSON duplicate-key detection before Pydantic schema validation.
- Persistent raw response, token usage, and error capture before downstream validation.
- Distinct diagnostics for provider, capture, schema-validation, and claim-check failures.
- Versioned lexical quality findings with `critical`, `review`, and `clear` dispositions.
- Fail-closed downstream behavior for critical unsupported claims; human review/approval remains the final release gate.
- Immutable historical outputs, SHA-256 evidence records, and separately approved human handoffs.

## 4. Model usage and latency

These are **recorded provider-stage metrics**, not wall-clock end-to-end application latency.

| Evaluation cohort | Input tokens | Output tokens | Total tokens | Sum of recorded stage latencies |
|---|---:|---:|---:|---:|
| Morrow Orchard Phase 2C baseline (`creative-v1`, 4 stages) | 5,462 | 3,750 | **9,212** | **6,934 ms** |
| Morrow Orchard latest selected Phase 2E stages* | 6,090 | 4,465 | **10,555** | **7,423 ms** |
| Aurora Vale current four-stage live `creative-v5` | 5,206 | 4,002 | **9,208** | **7,157 ms** |

\* Includes Stage 3 and Stage 4 with **human-reviewed upstream handoffs**. This is an aggregation of selected recorded stage runs, not an autonomous single-pass measurement.

## 5. Aurora Vale — separate current live Groq verification (`creative-v5`)

A different frozen synthetic brief, **Aurora Vale Spring 2027 Digital Launch**, was run through the application’s four-stage browser/worker workflow. The following records are persisted live-provider results, not deterministic fixture outputs.

**Snapshot ID:** `3efde19a-7324-476f-9f25-b1f100362740`  
**Provider/model:** `compatible` / `openai/gpt-oss-20b`  
**Prompt version:** `creative-v5`

| Stage | Execution status | Attempts | Input tokens | Output tokens | Provider latency | Deterministic quality |
|---|---|---:|---:|---:|---:|---|
| Brief Analysis | Completed | 1 | 1,023 | 1,414 | 2,607 ms | `clear` |
| Creative Strategy | Completed | 1 | 1,394 | 739 | 1,334 ms | `clear` |
| Content Plan | Completed | 1 | 1,271 | 752 | 1,410 ms | `review` |
| Copywriting | Completed | 2 | 1,518 | 1,097 | 1,806 ms | `clear` |
| **Total** | **4/4 completed** | — | **5,206** | **4,002** | **7,157 ms** | **3 clear, 1 review** |

The Content Plan finding concerned the unconfirmed operational assumption **“Join the waitlist for early access”**. The Copywriting record completed on attempt 2; the available record does **not** establish why the first attempt did not complete.

**Important separation:** Aurora Vale's `clear`/`review` labels are **deterministic quality-check dispositions**, not 1–5 human editorial grounding scores. **Do not report an Aurora Vale grounding average, pass rate against the 3/5 human rubric, or improvement over Morrow Orchard unless those scores are separately recorded.** The current verified sample is only one four-stage synthetic chain.

## 6. Fixture-only regression evidence (not live model quality)

A separate historical deterministic fixture evaluation recorded:

- **50/50 synthetic outputs** passing the predefined schema, required-field, and fixture grounding contracts.
- **6/6 negative controls** rejected by the tested contract checks.

These outcomes demonstrate regression coverage for narrow deterministic rules. They **do not** establish 100% semantic grounding, general model reliability, or human editorial acceptance of real Groq outputs. The fixture provider `fixture-v1` must not be mixed into live-provider statistics.

## 7. Acceptance summary

| Criterion | Historical Morrow Orchard | Current Aurora Vale |
|---|---|---|
| Four-stage technical generation | Baseline 4/4 schema-valid | 4/4 completed live |
| Human grounding rubric | Recorded; latest ranged 1–4/5 | **Not recorded in cited four-stage case study** |
| Deterministic quality check | Latest included unresolved `critical` findings | 3 `clear`, 1 `review` |
| Creative distinctiveness | Latest copy 2/5 — below threshold | Not independently scored |
| Entire chain editorially accepted | **No** | **Not established** |
| Authorized for publication | **No** | Not established by generation completion |

**Overall conclusion:** CREATIVE OS provides traceable model orchestration, schema enforcement, claim checking, auditability, and human-governed workflow transitions. Historical experiments illustrate the **gap between format correctness and factual/editorial quality**. Later live `creative-v5` execution demonstrates a functioning four-stage integration, but should not be described as proof of broad grounding reliability or production readiness.

## 8. Recommended next evaluation design (not yet performed)

For a stronger hiring-team evaluation deliverable:

1. Freeze a multi-brief synthetic benchmark with labeled supported/unsupported claim spans and varied product restrictions.
2. Compare prompt versions using matched inputs; report per-stage **human grounding**, **critical claims/output**, **claim-check precision/recall**, **schema validity**, **latency**, and **tokens**.
3. Use at least two independent human reviewers; report agreement and adjudication rules.
4. Include multi-stage constraint-retention tests and copy-distinctiveness/reuse checks.
5. Report sample sizes and uncertainty; preserve all evaluated failures, not only successful examples.

These are **proposed tests**, not measured outcomes from the current evidence.

## 9. Sources and provenance

Primary repository: <https://github.com/bayutamawib/creativeOS>

- [`docs/AI_EVALUATION_REPORT.md`](https://github.com/bayutamawib/creativeOS/blob/main/docs/AI_EVALUATION_REPORT.md) — historical research evaluation, criteria, score comparison, failure analysis.
- [`creativeOS-uat-evidence/phase2e-c/evaluation_scorecard.csv`](https://github.com/bayutamawib/creativeOS/blob/main/creativeOS-uat-evidence/phase2e-c/evaluation_scorecard.csv) — eleven detailed historical scorecard records, usage, claim findings, and evidence SHA-256 values.
- [`docs/AI_QUALITY_REMEDIATION_PLAN.md`](https://github.com/bayutamawib/creativeOS/blob/main/docs/AI_QUALITY_REMEDIATION_PLAN.md) — Phase 2C audit and subsequent quality controls.
- [`creativeOS-uat-evidence/phase2c/`](https://github.com/bayutamawib/creativeOS/tree/main/creativeOS-uat-evidence/phase2c) — immutable synthetic baseline files.
- [`creativeOS-uat-evidence/phase2e-c/`](https://github.com/bayutamawib/creativeOS/tree/main/creativeOS-uat-evidence/phase2e-c) — phase-specific runs and human handoff records.
- [`docs/PORTFOLIO_AI_CASE_STUDY.md`](https://github.com/bayutamawib/creativeOS/blob/main/docs/PORTFOLIO_AI_CASE_STUDY.md) — persisted Aurora Vale `creative-v5` live execution table.

**Evidence limitations:** This report consolidates previously documented results; it does not independently rerun the model, adjudicate editorial scores, or claim that historical test outcomes apply unchanged to every subsequent application version.
