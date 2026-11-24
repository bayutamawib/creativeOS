# CREATIVE OS - AI Evaluation Report

## 1. Executive Summary

CREATIVE OS completed a bounded four-stage live evaluation on the synthetic Morrow Orchard brief. The latest evaluated chain used Groq `openai/gpt-oss-20b`, versioned prompts, strict JSON parsing, durable raw-output capture, deterministic lexical claim checks, and explicit human approval records. All four latest stage outputs passed their Pydantic schemas, but the chain did **not** achieve editorial production readiness. Stage 2 and Stage 3 contained unresolved critical findings; Stage 4 was deterministically clear but repeated its input caption and CTA and scored 2/5 for distinctiveness. No evaluated content was authorized for publication.

The latest chain consumed 6,090 input tokens and 4,465 output tokens with 7,423 ms recorded aggregate latency. These totals include the human-reviewed inputs used for Stage 3 and Stage 4 and do not imply a fully autonomous run.

## 2. System Architecture and Four-Stage Workflow

`Approved brief -> Brief Analyzer -> Creative Strategist -> Content Planner -> Copywriting Assistant -> human review`

FastAPI orchestrates versioned provider calls. Pydantic schemas validate outputs. A shared strict JSON boundary rejects duplicate object keys before schema validation. Raw responses are persisted before validation and claim checking. The narrow claim checker records `clear`, `review`, or `critical`; critical findings block existing selection/save gates. Human approval remains authoritative and publication requires a separate decision.

## 3. Evaluation Dataset and Methodology

The dataset is one frozen, synthetic Morrow Orchard campaign brief. Phase 2C provides a single sequential `creative-v1` baseline. Phase 2E contains historical failures, retries, prompt versions, human-reviewed handoffs, and approval records. Each stage was assessed on relevance, specificity, grounding, distinctiveness, and actionability using a 1-5 rubric. Technical/schema status, deterministic findings, and human editorial assessment are reported separately.

## 4. Acceptance Criteria and Scoring Rubric

Acceptance required every editorial dimension to score at least 3/5, zero unresolved critical claims, schema validity, required deliverable coverage, and preservation of human release gates. An editorial mean never overrides a failed individual dimension. `Clear` from the lexical checker is not proof of semantic grounding.

## 5. Baseline vs Latest Results

| Stage | Baseline grounding | Latest grounding | Baseline mean | Latest mean | Latest claims | Editorial disposition |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Brief Analyzer | 2 | 4 | 3 | 3.8 | clear | owner_review_required |
| Creative Strategist | 2 | 1 | 3.2 | 3 | critical | rejected_critical_claims |
| Content Planner | 1 | 2 | 2.6 | 3.6 | critical | rejected_critical_claim |
| Copywriting Assistant | 2 | 4 | 2.2 | 3.4 | clear | revision_required |

Stage 1 improved its recorded grounding score from 2 to 4. The latest model-generated Stage 2 (Run C) fell from the baseline grounding score of 2 to 1 and introduced exact fruit examples and sensory language. Stage 3 improved over its baseline but retained a critical freshness claim. Stage 4 improved grounding from 2 to 4 but remained below threshold on distinctiveness. Downstream score improvements followed human-reviewed handoffs and cannot be attributed solely to prompt optimization.

## 6. Historical Run Analysis

- **Phase 2C:** all four responses passed schemas; every stage required revision. Grounding weakened downstream, and Copy repeated planner text.
- **Initial Phase 2E Stage 1 attempt:** the provider returned a response, but a local `Response.body`/`Response.content` mismatch prevented raw-output preservation. It remains `not_evaluated`.
- **Stage 2 Run A Retry:** Groq emitted three repeated top-level `creative_directions` keys. Permissive parsing retained only the last direction. The historical `passed` field is not trustworthy under the strict parser.
- **Stage 2 Run B:** strict JSON passed; grounding remained 2/5 and the output assumed a signup mechanism and sensory/product language.
- **Stage 2 Run C:** `creative-v3` passed schema validation but received `critical` for unsupported sensory language and exact fruit varieties.
- **Stage 3 Run A:** a human-reviewed strategy handoff enabled planning, but the model reintroduced `fresh fruit`; editorial grounding was 2/5.
- **Stage 4 Run A:** deterministic checks were clear, but caption and CTA were copied verbatim and revision notes inaccurately claimed a caption refinement.

## 7. Failure Analysis

**Verified root causes.** Duplicate-key data loss occurred at permissive JSON parsing before Pydantic saw the object. The initial capture failure was caused by reading `response.body` although the provider contract exposes `response.content`.

**Observed failures.** Outputs introduced unsupported product and sensory claims, factualized audience assumptions, lost asset-rights qualifiers, reused format-driven concepts, repeated captions, and produced inaccurate revision notes.

**Research hypothesis.** Constraints appear to degrade across transformations, including after human-reviewed inputs. The evidence is one synthetic chain with interventions, so it does not establish a general causal mechanism.

## 8. Engineering Remediation

- Versioned prompts (`creative-v1`, `v2`, and strategy-only `v3`) preserve replayability.
- Strict recursive duplicate-key detection now precedes every shared schema validation call.
- Durable capture writes raw model text and usage before validation or claim checking.
- `claim-rules-v2` detects known varieties, freshness, sensory attributes, operational signup assumptions, notification priority, and unsupported asset provenance while allowing explicitly proposed visuals.
- Capture, provider, validation, and claim-check failures have separate diagnostic states and halt downstream execution.
- Regression tests cover prompt provenance, strict parsing, handoff approval, evidence integrity, and fail-fast behavior.

## 9. Human-in-the-Loop Review and Approval

Stage 2 and Stage 3 model outputs remained failed research evidence. Separate handoff proposals removed known critical claims without rewriting historical files. Separate owner approval records authorized only the next evaluation stage, did not authorize publication, and did not retroactively pass source model performance. Stage 3 used an approved human-reviewed strategy; Stage 4 used an approved human-reviewed plan.

## 10. Evidence Integrity and Provenance

The audit covered 17 JSON evidence, approval, handoff, summary, and backlog records plus 11 generation records in the scorecard. Approval proposal hashes, source hashes, and recorded provenance were checked. Existing JSON hashes were unchanged during package generation.

| Evidence record | SHA-256 |
| --- | --- |
| `creativeOS-uat-evidence/phase2c/brief_analysis.json` | `375d508c1e6e598da11275f7f6c58ccbaca4566b7c7ef620db125edc5d3f22af` |
| `creativeOS-uat-evidence/phase2c/content_plan.json` | `86a90eba6d471273ac6c3a4408cf2d815658c204e6375966ac2db22905bc77c0` |
| `creativeOS-uat-evidence/phase2c/copywriting.json` | `e494e454f5388a0cb02f1fa0e1550e772ed39e2d295d358950e760aad54914d4` |
| `creativeOS-uat-evidence/phase2c/creative_strategy.json` | `1b23538c0e1354ed75a8451026a0ebde89bf30ac71063d8f221984b44016482c` |
| `creativeOS-uat-evidence/phase2e-c/brief_analysis.json` | `bcfd694136264707983a60a3b733f75cd5868979ab13d30dcbf9b527e95b06b7` |
| `creativeOS-uat-evidence/phase2e-c/run-a-retry/brief_analysis.json` | `adb72931044d12b169de057f9b4ed0bbc66526a5a29b8759b21860117bf6416d` |
| `creativeOS-uat-evidence/phase2e-c/run-a-retry/creative_strategy.json` | `64e1fc261e5f147735ac5e9f62fc7e345a39981e8dec4b957816d74e6fe0766b` |
| `creativeOS-uat-evidence/phase2e-c/run-b/creative_strategy.json` | `c2e0fa9110294bff6e3909bcf9f413270c947760ec0c9acbcb3f50801ca08792` |
| `creativeOS-uat-evidence/phase2e-c/run-c/creative_strategy.json` | `5499db92b32599719625d7e351db14efd8be8ce857a656016c329f368b781efa` |
| `creativeOS-uat-evidence/phase2e-c/run_summary.json` | `1d4e77be82ed68c840703ed0af4e4c4d8f9284e4a5569245d9718405f926ad61` |
| `creativeOS-uat-evidence/phase2e-c/stage3-handoff/owner_approval.json` | `ba8ba70d247f22c5613e4f32f43496c2cfebd92f46dee70af4dbb9ae73780857` |
| `creativeOS-uat-evidence/phase2e-c/stage3-handoff/proposed_strategy_handoff.json` | `9e98123b7fbe8abeafdaff70309f1051fba4031f450b22e197352fa46eae41ff` |
| `creativeOS-uat-evidence/phase2e-c/stage3-handoff/research_backlog.json` | `a034d15335b4c33288ad48dd242951efde1427e8ae660891423516941ef12729` |
| `creativeOS-uat-evidence/phase2e-c/stage3-run-a/content_plan.json` | `143df5b114ccb5cae99ec22ab9390ce2a5f5d3ef013f7b982c7b058ac97b0090` |
| `creativeOS-uat-evidence/phase2e-c/stage4-handoff/owner_approval.json` | `f07b825117c8e9589492cdf225d1e9802b300770075d1c99b6f0e3c7fd21195b` |
| `creativeOS-uat-evidence/phase2e-c/stage4-handoff/proposed_content_plan_handoff.json` | `69f96a0a1bfab6ccf21ba5507989611103e89145d3772785be37a07a4b016104` |
| `creativeOS-uat-evidence/phase2e-c/stage4-run-a/copywriting.json` | `118a1469e948eb60cab46a73eeab36c154c1c9b1bd7dfdd50adf74dc02268828` |

## 11. Research Backlog and Proposed Experiments

### A. Grounding and claim provenance
Hypothesis: explicit claim-source annotations reduce unsupported attributes. Experiment: evaluate at least 20 synthetic briefs with adjudicated claim spans; measure critical claims per output and precision/recall of deterministic checks.

### B. Cross-stage constraint preservation
Hypothesis: a compact machine-readable constraint ledger passed unchanged between stages reduces downstream loss. Experiment: compare current prompts against ledger-assisted prompts across matched seeds; measure restriction retention and human grounding scores.

### C. Creative distinctiveness and transformation quality
Hypothesis: narrative-angle labels plus pairwise differentiation checks improve distinctiveness and reduce verbatim reuse. Experiment: blind-review three strategies and copy revisions per brief; measure minimum pairwise distinction and literal reuse rates.

### D. Evaluation methodology and regression coverage
Hypothesis: multi-seed, multi-brief evaluation changes conclusions drawn from the single historical run. Experiment: pre-register thresholds, run repeated samples, use two reviewers, report inter-rater agreement, latency, tokens, and confidence intervals.

## 12. Limitations and Production Readiness

This portfolio evaluation uses one fictional brief, one provider/model, few stochastic samples, and human interventions between stages. Lexical checks miss semantic paraphrases and may produce false positives. Historical scores were assigned by one review process; no inter-rater reliability was measured. The chain is **not production-ready**: critical findings recurred, no stage chain achieved complete editorial acceptance, and no content was approved for publication.

## 13. Conclusion

The project demonstrates traceable AI engineering: versioned prompts, strict structured-output validation, durable evidence, deterministic safety checks, approval-scoped handoffs, and honest preservation of failures. It also demonstrates that technical reliability is insufficient for creative quality. Future work should prioritize measured grounding and transformation quality rather than additional unbounded feature complexity.
