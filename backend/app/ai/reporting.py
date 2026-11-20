"""CP5 can supply database-derived period metrics through this typed boundary."""

from pydantic import Field

from app.ai.contracts import PROMPT_VERSION, TEMPERATURES, Structured, Summary, Title, validate
from app.ai.providers import adapter
from app.config import settings


class VerifiedMetrics(Structured):
    period: Title
    completed_tasks: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)


def summarize(metrics: VerifiedMetrics) -> Summary:
    config = settings()
    response = adapter(config.ai_provider, PROMPT_VERSION).generate(
        "report_summary",
        config.ai_model,
        metrics.model_dump(),
        {
            "temperature": TEMPERATURES["report_summary"],
            "max_output_tokens": config.ai_max_output_tokens,
        },
    )
    return Summary.model_validate(validate("report_summary", response.content, {}))
