"""Probe the local foundation through its published HTTP interfaces."""
import json
import os
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1) for line in (root / ".env").read_text().splitlines()
    if line and not line.startswith("#")
)
def local_url(key, path):
    port = int(os.environ.get(key, values[key]))
    return f"http://127.0.0.1:{port}{path}"

for path, expected in [("/health/live", "alive"), ("/health/ready", "ready")]:
    with urlopen(local_url("API_PORT", path), timeout=8) as response:
        assert json.load(response)["status"] == expected, path
for key, path in [("WEB_PORT", "/"), ("N8N_PORT", "/healthz/readiness")]:
    with urlopen(local_url(key, path), timeout=8) as response:
        assert response.status == 200
print("PASS: API liveness, migrated database readiness, frontend and n8n")
