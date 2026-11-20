"""Generate missing local Compose secrets while preserving configured values."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
keys = (
    "POSTGRES_PASSWORD",
    "APP_DB_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "WEBHOOK_KEY",
    "WORKFLOW_KEY",
    "FORMS_KEY",
)
with os.fdopen(os.open(target, os.O_RDWR | os.O_CREAT, 0o600), "r+") as stream:
    content = stream.read() or (root / ".env.example").read_text()
    lines = content.splitlines()
    for key in keys:
        if not any(line.startswith(key + "=") for line in lines):
            lines.append(key + "=")
        lines = [line + secrets.token_hex(32) if line == key + "=" else line for line in lines]
    stream.seek(0)
    stream.write("\n".join(lines) + "\n")
    stream.truncate()
print("Local Compose environment ready")
