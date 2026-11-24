# CREATIVE OS — AI quality remediation plan

## Scope and evidence

Phase 2D is a read-only audit of the four completed Phase 2C Groq jobs for one fictional Morrow Orchard brief. No model request or application change was made for this audit. The canonical sanitized evidence is in `creativeOS-uat-evidence/phase2c/` inside this repository. The four baseline JSON files are immutable. Future Phase 2E-C evidence belongs in a separate `creativeOS-uat-evidence/phase2e-c/` subdirectory. Evidence must contain only synthetic, sanitized inputs, outputs, metadata, and assessments; exclude credentials, authorization headers, cookies, environment values, and sensitive transport logs before adding files to Git.

Baseline SHA-256 hashes (verified from the in-repository files):

| File | SHA-256 |
| --- | --- |
| `brief_analysis.json` | `375d508c1e6e598da11275f7f6c58ccbaca4566b7c7ef620db125edc5d3f22af` |
| `creative_strategy.json` | `1b23538c0e1354ed75a8451026a0ebde89bf30ac71063d8f221984b44016482c` |
| `content_plan.json` | `86a90eba6d471273ac6c3a4408cf2d815658c204e6375966ac2db22905bc77c0` |
| `copywriting.json` | `e494e454f5388a0cb02f1fa0e1550e772ed39e2d295d358950e760aad54914d4` |

The sample is one sequential run, one request per stage, with `openai/gpt-oss-20b` and prompt `creative-v1`. It establishes concrete failure modes, not a general model failure rate. The main application remains on fixture mode; the synthetic content item remains an unpublished internal draft.

| Stage | Job | Technical result | Human scores: relevance / specificity / grounding / distinctiveness / actionability | Editorial result |
| --- | --- | --- | --- | --- |
| Brief Analyzer | `8702d0e8-0ca9-48f4-8eb6-19196905b924` | Completed, attempt 1; schema valid | 5 / 3 / 2 / 2 / 3 | Requires revision: unsupported freshness and audience needs; generic pillar classification |
| Creative Strategist | `a1caf10c-18cc-436b-b82d-0eb81609cd02` | Completed, attempt 1; schema valid | 5 / 3 / 2 / 3 / 3 | Requires revision: inferred audience behaviors stated as facts; overlapping directions |
| Content Planner | `e4f342d1-019d-47ec-8f97-470c7209b46c` | Completed, attempt 1; schema, three-item count, and channels valid | 4 / 3 / 1 / 2 / 3 | Requires revision: invented apples, pears, and berries despite an explicit restriction |
| Copywriting Assistant | `5b165627-f79d-4ea8-9738-0845b8b8b852` | Completed, attempt 1; schema valid | 4 / 2 / 2 / 1 / 2 | Requires revision: verbatim caption and CTA; unsupported `#FarmFresh`; inaccurate revision note |

The four jobs used 5,462 input and 3,750 output tokens in total. These counts and the per-job latencies are recorded in the evidence files. All four passed technical validation; all four were marked `requires_revision`. Technical completion must remain distinct from editorial acceptance.

## Findings and causal path

1. **Grounding weakens across stages.** The analyzer introduced “fresh” and unsourced audience needs. The strategist turned audience hypotheses into statements about what Alder Vale home cooks prefer or do. The planner carried forward “Community Engagement” and invented exact fruit varieties in its caption. The copy output inherited the planner's unverified “link in bio” CTA and added `#FarmFresh`. The brief explicitly forbids claims about exact varieties and unknown product attributes. The evidence supports this propagation path; it does not show that any single upstream phrase alone caused the later invention.
2. **Structure passes while meaning fails.** `backend/app/ai/contracts.py` uses strict Pydantic models and, for `Plan`, enforces count and permitted channels. It does not check claim provenance, asset availability, CTA destination, whether content pillars are actually topics, or whether directions/items are meaningfully distinct. This is consistent with AI §11 and testing §10, which separate schema checks from human quality review.
3. **The copy contract produces one suggestion.** `Copy` has one headline, caption, CTA, hashtags list, revision notes, and risks; it has no variants array. `backend/app/services/studio.py` adds `target_count` to parameters for every generation kind from the brief's requested item count, but only `Plan` applies it as a count rule. Thus `target_count=3` in the copy job is misleading metadata, not a promise the current schema can satisfy. The approved AI §5.4 specification also describes one draft or revision. A multi-variant product requirement needs an explicit owner decision before any schema or API change.
4. **Copy input and tests favor repetition.** The copy job's context includes the selected plan item and the current revision, both carrying the plan's draft caption and CTA. Its output repeated those two strings verbatim while changing the headline and adding hashtags. The short `creative-v1` copy prompt asks for a suggestion but does not define when to preserve versus improve an existing revision or how to report a no-change result. More directly, `backend/app/ai/evaluation.py:assess` calls fixture copy grounded when its headline equals the plan title **and its caption equals the plan draft caption**. That deterministic check rewards the exact-copy behavior the live UAT found unhelpful. This is an evaluation-design issue, not evidence that the provider ignored a specific instruction.
5. **Self-reported compliance is unreliable.** Copy revision notes say restricted language was maintained even though `#FarmFresh` asserts an unsupported attribute. The current schema validates the presence and type of notes, not their truth. Hashtags and CTAs need the same claim review as visible prose.
6. **The human release boundary held.** A manager selected a direction and one plan item for synthetic testing, but no generated copy was saved as a new revision or published. The content item remained an internal draft with one revision. This boundary should be retained while quality rules change.

## Proposed remediation, in order

### 1. Define claim and provenance rules before changing prompts

Create a small claim taxonomy for product facts, audience research, creative suggestions, and operational assumptions. For every stage, identify which brief/snapshot field can support each class. Treat unknown varieties, freshness, harvest provenance, pricing, nutrition, certification, availability, delivery, testimonials, and asset rights as unverified unless explicitly supplied. Check hashtags and CTAs as first-class copy. Record an open question instead of filling a gap. Keep candidate human review as the final editorial gate; deterministic checks should catch known prohibited patterns, not claim universal semantic proof.

**Acceptance:** The four preserved outputs are replayed through proposed checks. The planner's exact varieties and copy's `#FarmFresh` fail a critical grounding rule; a supported seasonal-variety phrase passes. No client-visible publication path is opened by a check result alone.

### 2. Improve stage instructions with versioned, bounded contracts

Propose a new prompt version that distinguishes supplied facts, hypotheses, and creative proposals; forbids unsupported specificity; makes CTA destination conditional; and requires copy revision notes to describe actual differences. For analysis, require content pillars to be content themes and missing information to focus on actionable gaps. For strategy, request different creative approaches rather than only different output formats and label audience insights as hypotheses when research is absent. For planning, require three differentiated items within the allowed channels without inventing fruit varieties or delivery details. For copy, define a measurable revision objective and allow an explicit “no safe improvement” outcome if the input cannot be improved without unsupported facts. Review prompt-injection and privacy boundaries when editing prompts.

**Acceptance:** Prompt versions and stored provenance remain traceable; the approved synthetic brief produces no unsupported product or audience claims in reviewed candidate outputs. Human reviewers can name a useful difference between each direction and plan item and between source revision and copy suggestion. No prompt wording alone is treated as proof of safety.

### 3. Correct copy parameter semantics and decide whether variants belong in scope

For the existing one-suggestion contract, stop presenting `target_count=3` as meaningful for copywriting; document that it applies to Content Planner only. Decide separately whether the product needs multiple copy variants. If approved, specify the maximum count, distinctness criteria, response schema, API behavior, persistence, UI selection, and backward compatibility before implementation. Do not infer a variants requirement from the current shared parameter.

**Acceptance:** Copy job metadata no longer implies three outputs when one is requested; tests cover count behavior by generation kind. Any future variants change has an approved contract and migration plan.

### 4. Replace copy-favoring fixture checks and add regression cases

Revise `backend/app/ai/evaluation.py:assess` so grounding tests verify support for factual claims instead of exact caption equality. Add synthetic negative controls from all four preserved failures: unsupported freshness/audience assertions, unconfirmed CTA, exact fruit varieties, `#FarmFresh`, false revision notes, and verbatim copy where an improvement was requested. Add positive controls for permissible seasonal-variety wording, faithful reuse when explicitly requested, and safe omission of unknown details. Test count/channel constraints and preserve the existing authorization, snapshot, direction-selection, revision, and unpublished-draft gates.

**Acceptance:** The negative controls fail for their intended reason, positive controls pass, and a copied caption cannot earn a quality pass merely by matching the input. Tests use fixture or recorded synthetic outputs and make no external API calls.

### 5. Re-evaluate with human review before another live rollout

Use the approved synthetic evaluation framework (AI §11; testing §10) and the existing five-dimension UAT rubric. Run versioned, reproducible offline checks first, then obtain separate approval for any bounded paid-provider comparison. Review each stage independently and as a chain; record critical failures and per-stage human acceptance. Compare prompt/model versions only on the same frozen inputs. Keep raw credentials and client data out of evaluation artifacts and never auto-publish generated content.

**Proposed release gate for owner approval:** zero critical unsupported claims in the reviewed synthetic set; all required schemas, counts, channels, and workflow gates pass; copy suggestions show a useful, documented change when revision is requested; no false compliance notes; and human reviewers accept the output without substantial rewriting. Record actual sample sizes, scores, latency, and usage rather than estimating quality from this one run.

## Owner decisions before implementation

- Confirm whether copywriting should remain one suggestion per request or support multiple variants.
- Approve the intended copy behavior for an existing draft: faithful polish, substantive alternative, or both as explicit modes.
- Approve the claim taxonomy and how strict deterministic blocking should be versus flagged human review.
- Approve any future paid live comparison separately; this audit authorizes no new provider requests.

No implementation, prompt, schema, provider, Docker, database, or deployment change is included in Phase 2D.

## Phase 2E-A implementation record — P0 claim checks

This bounded slice adds `backend/app/ai/quality.py` with versioned lexical claim categories and separate `critical`, `review`, or `clear` findings. It checks assertive fields in analysis, directions, plans, and copy, including headlines, captions, CTAs, and hashtags. Missing-information, risk, and constraint lists are excluded from claim detection because they can mention prohibited topics without asserting them. A clear result means only that these known patterns were not found; it is not a semantic grounding certificate.

Completed generations retain their original output and technical status. Findings are stored in a separate nullable `ai_generations.quality_findings` JSONB field through additive migration `0016_quality_findings` and are exposed on the authorized generation view. An approved proposal or generated copy suggestion with a **critical** finding cannot pass the existing manager proposal-selection or copy-save gate; review-only findings remain for human judgment. The plan-item draft creation path rechecks critical claims. Historical jobs with no stored findings are evaluated against their frozen approved snapshot at these gates. The original approved brief fields, rather than upstream AI prose, supply the fact baseline.

The four preserved Phase 2C outputs were evaluated offline after implementation: Brief Analyzer `critical`, Creative Strategist `review`, Content Planner `critical`, and Copywriting Assistant `critical`. The planner's invented varieties and copy's `#FarmFresh` are critical; unconfirmed link-in-bio instructions are review flags; neutral seasonal-variety copy is clear. The strategist's “fresh ideas” is not treated as a product freshness claim. No historical output or evidence file was changed.

Verification used a disposable database in the isolated Compose project, leaving the existing UAT and main databases intact. Ruff and mypy passed; Alembic upgraded the disposable database to `0016_quality_findings` and reported no model drift; the full backend suite passed **84 tests** with one existing Starlette deprecation warning. No live provider request was made. The migration has **not** been applied to the main fixture stack.

Known limits: lexical checks can miss paraphrases, multilingual claims, and claims that require external context; they can also flag a legitimate phrase without richer provenance. The rules do not score originality, usefulness, or whether the copy made a meaningful revision. Existing human review and publication controls remain authoritative. The next bounded slice is versioned prompt and evaluation work, including removing the fixture evaluator's exact-copy reward and clarifying one-suggestion copy semantics; these changes need separate owner approval.

## Phase 2E-B implementation record — versioned prompts and copy evaluation

`backend/app/ai/contracts.py` now retains the exact `creative-v1` prompt set and adds `creative-v2` for Brief Analyzer, Creative Strategist, Content Planner, and Copywriting Assistant. New creative jobs record `creative-v2`; the compatible adapter resolves the system instruction from each **persisted job's** prompt version, so a historical v1 job still uses v1 if executed later. Report summaries and the frozen `creative-eval-v1` fixture baseline remain on v1. The Copy schema and API response shapes remain unchanged.

The v2 instructions explicitly distinguish brief facts from hypotheses and proposals, carry restrictions forward, require differentiated directions and plan purposes, keep CTAs destination-neutral when no destination is confirmed, treat visual assets as proposed, and require truthful copy revision notes. They ask for one safe Copy suggestion; no variants array was added. Only Content Planner now receives `target_count` in new job parameters. Existing persisted job inputs, outputs, parameters, and version labels were not rewritten; old copy jobs may still contain the former shared count parameter.

`backend/app/ai/evaluation.py` no longer uses exact caption equality as a grounding condition for copy. Grounding uses the approved synthetic brief through the narrow claim checker. A separate offline comparison records whether caption and CTA were reused, whether improvement or preservation was requested, and whether checkable revision-note claims match the actual changes. Exact reuse under an explicit preservation request is not marked as a change failure. These checks detect literal behavior and known unsupported claims; they do not prove editorial value, creativity, or complete factuality. A simple strategy comparison flags duplicate rationale/audience text for human review without claiming semantic distinctness. The v1 fixture baseline remains reproducible, with the new diagnostic fields reported separately from its original pass calculation.

Offline regression tests cover v1/v2 prompt selection and transport payloads without network access; four historical synthetic outputs; unsupported hashtags and audience claims; plan count and channels; copy reuse, requested improvement, faithful preservation, and checkable revision notes; and creative-job prompt provenance. Ruff, strict mypy, Alembic upgrade/check on a disposable isolated test database, and the full backend suite passed: **89 tests**, one existing Starlette deprecation warning. The evidence was mounted read-only for that run. No Groq call or main-stack migration was performed; `0016_quality_findings` remains unapplied to the main fixture database.

Remaining limits: prompt changes are unverified against a live model; the offline copy comparison detects change but cannot decide whether it is useful; duplicate strategy text is only a narrow warning. A future bounded slice should evaluate v2 on frozen synthetic inputs with human scoring and explicit owner approval for any paid live comparison, while retaining the existing unpublished-draft and human-release gates.
