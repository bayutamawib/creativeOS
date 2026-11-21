"""Check Git history, index and worktree without displaying credential values."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


patterns = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    rb"|(?:gh[pousr]_|github_pat_|sk-proj-|sk-live-|xox[baprs]-)[A-Za-z0-9_-]{20,}"
    rb"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}"
)
keys = set()
environment = ROOT / ".env"
if environment.is_file():
    for line in environment.read_text().splitlines():
        name, _, value = line.partition("=")
        if name.endswith(("_PASSWORD", "_KEY", "_TOKEN")) and value:
            keys.add(value.strip("\"'").encode())
accounts = ROOT / ".local/demo-accounts.json"
if accounts.is_file():
    keys.update(v.encode() for v in json.loads(accounts.read_text()).values() if v)

problems = set()


def check(path, data):
    p = Path(path)
    if (
        (p.name.startswith(".env") and p.name != ".env.example")
        or p.suffix.lower() in {".pem", ".p12", ".key", ".dump", ".sqlite", ".sqlite3"}
        or {".local", "pgdata", "uploads"}.intersection(p.parts)
    ):
        problems.add(path + " (private path)")
    if patterns.search(data) or any(k in data for k in keys):
        problems.add(path + " (credential match)")


blobs = {}
for commit in git("rev-list", "--all").splitlines():
    for row in git("ls-tree", "-rz", commit).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            blobs.setdefault(meta.split()[2], set()).add(name.decode())
for row in git("ls-files", "--stage", "-z").split(b"\0"):
    if row:
        meta, name = row.split(b"\t", 1)
        blobs.setdefault(meta.split()[1], set()).add(name.decode())
for oid, names in blobs.items():
    data = git("cat-file", "blob", oid)
    for name in names:
        check(name, data)
paths = [
    n.decode()
    for n in git("ls-files", "-co", "--exclude-standard", "-z").split(b"\0")
    if n
]
for name in paths:
    p = ROOT / name
    if p.is_file():
        check(name, p.read_bytes())
if problems:
    raise SystemExit("\n".join(sorted(problems)))
print(f"PASS: {len(blobs)} distinct Git blobs and {len(paths)} working paths checked.")
