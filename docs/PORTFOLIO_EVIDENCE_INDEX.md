# Portfolio Evidence Index

This index distinguishes historical screenshots, persisted live-generation evidence, and targeted offline tests. It does not imply production readiness.

| Topic | Evidence | Boundary/status |
|---|---|---|
| Product screenshots | [`PORTFOLIO_SCREENSHOT_GALLERY.md`](PORTFOLIO_SCREENSHOT_GALLERY.md), [`PORTFOLIO_SCREENSHOT_INVENTORY.md`](PORTFOLIO_SCREENSHOT_INVENTORY.md), `docs/screenshots/current/` | 24 current captures visually inspected; 22 PASS and published, 2 REVIEW preserved but excluded |
| Live Groq stages | Current Aurora Vale snapshot metadata; sanitized earlier records in `creativeOS-uat-evidence/phase2c/` and `phase2e-c/` | Aurora live stages use `creative-v5`; plan has review findings; see [case study](PORTFOLIO_AI_CASE_STUDY.md) |
| Fixture workflow | `docs/IMPLEMENTATION_STATUS.md`, `docs/PORTFOLIO_DEMO.md`, backend/frontend tests | Synthetic workflow evidence; not live-model evaluation |
| Worker modes | `backend/app/worker.py`, `backend/tests/test_worker.py` | `ai`, `dispatch`, `all`; two targeted offline tests passed |
| Automation reliability | `backend/app/services/workflows.py`, `backend/tests/test_outbox.py`, `test_reminders.py`, `test_evaluation_monitoring.py` | Targeted isolated regression: 13 passed; bounded-lease residual risk remains |
| Attachment authorization | `backend/app/services/assets.py`, `reviews.py`, `backend/tests/test_media.py`, `test_reviews.py` | Targeted isolated regression: 12 passed; prior README vulnerability statement is stale |
| Human approvals/revisions | `docs/IMPLEMENTATION_STATUS.md`, `backend/tests/test_reviews.py`, `frontend/e2e/` | Synthetic role and revision flows; no claim of production use |
| Limitations | `README.md`, `docs/LOCAL_OPERATIONS.md`, `docs/AI_QUALITY_REMEDIATION_PLAN.md` | Security hardening, model-quality evaluation, integrations, and production readiness remain limited |

Keep the repository-local `creativeOS-uat-evidence/` directory intact. Never publish `.env`, `.local/demo-accounts.json`, credentials, session data, raw webhook headers, database dumps, or private customer information. Internal localhost URLs should be described as local development routes, not public services.
