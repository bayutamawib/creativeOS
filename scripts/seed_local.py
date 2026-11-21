"""Seed the running local stack. Generated credentials stay in an owner-only file."""
import json
import os
import secrets
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".local/demo-accounts.json"
destination.parent.mkdir(mode=0o700, exist_ok=True)
if not destination.exists():
    accounts = {f"{name}@example.com": secrets.token_urlsafe(24) for name in
                ("admin", "manager", "producer", "lead", "reviewer", "publisher", "editor")}
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        json.dump(accounts, out, indent=2)
with destination.open() as credentials:
    os.fchmod(credentials.fileno(), 0o600)
    subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-m", "app.seed"],
                   cwd=root, stdin=credentials, check=True)
print("Credentials: .local/demo-accounts.json")
