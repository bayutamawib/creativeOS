"""One synthetic summary through the configured adapter, without a job or publication."""

from app.ai.contracts import GenerationFailure
from app.ai.reporting import VerifiedMetrics, summarize
from app.config import settings

metrics = VerifiedMetrics(
    period="Portfolio sample", completed_tasks=1, open_tasks=2, overdue_tasks=0
)
try:
    summary = summarize(metrics)
except GenerationFailure as error:
    raise SystemExit("Summary validation failed: " + error.code) from None
print(f"Validated {settings().ai_provider} / {settings().ai_model}")
print(summary.model_dump_json(indent=2))
