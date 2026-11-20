"""Check the CREATIVE OS specification documents using only the standard library."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_markdown(path):
    """Check local link targets, fenced JSON examples and Markdown table widths."""
    fence = None
    body = []
    width = None
    examples = 0
    for number, line in enumerate(path.read_text().splitlines(), 1):
        location = f"{path.name}:{number}"
        if line.startswith("```"):
            if fence == "json":
                try:
                    json.loads("\n".join(body))
                except ValueError as exc:
                    raise ValueError(f"{location} invalid JSON: {exc}") from exc
                examples += 1
            fence = line[3:].strip() if fence is None else None
            body.clear()
            width = None
        elif fence is not None:
            if fence == "json":
                body.append(line)
        else:
            if line.startswith("|"):
                require(line.endswith("|"), f"{location} incomplete table row")
                cells = len(re.split(r"(?<!\\)\|", line)) - 2
                if width is None:
                    width = cells
                require(cells == width, f"{location} table has {cells} columns, expected {width}")
            else:
                width = None
            for target in re.findall(r"\]\(([^)]+)\)", line):
                url = urlsplit(target)
                if url.path and not url.scheme and not url.netloc:
                    require((path.parent / unquote(url.path)).is_file(), f"{location} missing {target}")
    require(fence is None, f"{path.name} has an unclosed fence")
    return examples


def check_contracts(specs):
    db, api, ai, workflow = (p.read_text() for p in specs[2:6])
    # Workflow call examples must resolve to catalogued HTTP methods and paths.
    routes = set(re.findall(r"^\| (GET|POST|PATCH|DELETE|PUT) \| `([^`]+)` \|", api, re.M))
    for method, path in re.findall(r"(GET|POST|PATCH|DELETE|PUT) /api/v1(/[^\s`]+)", workflow):
        require((method, path) in routes, f"Workflow calls undocumented route {method} {path}")

    # Catch a truncated schema even when the cut happens between complete rows.
    for name in ("content_revisions", "content_approvals", "content_feedback",
                 "brief_snapshots", "creative_proposals", "client_invitations", "ai_generations",
                 "outbox_events", "processed_events", "workflow_runs", "notifications",
                 "reports", "activity_logs"):
        require(name in db.split("#### `content_items`", 1)[1], f"Missing database contract for {name}")

    state_section = ai.split("### 6.1 Execution states")[1].split("### 6.2")[0]
    states = set(re.findall(r"^- `(\w+)`$", state_section, re.M))
    poll_contract = api.split("Poll `GET /ai-generations/{generation_id}` for ")[1].split(".")[0]
    require(states == set(re.findall(r"\w+", poll_contract)) - {"or"}, "AI polling states disagree")

    catalog = workflow.split("## 28. Integration Contract Clarifications")[1].split("## 29.")[0]
    events = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", catalog))
    earlier_events = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", workflow.split("## 28.")[0]))
    require(earlier_events <= events, f"Unregistered workflow events: {earlier_events - events}")
    require(events and routes and states, "Empty contract catalog")


def check_permission_matrix(path):
    roles = ["Admin", "Manager", "Team Member", "Client Admin", "Client Member", "Delegated"]
    # Approved P1/P2 cases. Every unlisted role must be explicitly denied.
    allowed = {
        "Manage Team Member membership": {"Admin", "Manager"},
        "Manage Admin or Manager roles": {"Admin"},
        "Manage authentication or security settings": {"Admin"},
        "Manage agency-wide project assignments, tasks and workflows": {"Admin", "Manager"},
        "Manage agency operational settings": {"Admin", "Manager"},
        "Manage client approval delegations": {"Client Admin"},
        "Comment as client on released revision": {"Client Admin", "Client Member", "Delegated"},
        "Approve submitted revision as client": {"Client Admin", "Delegated"},
        "Request revision as client": {"Client Admin", "Delegated"},
    }
    header = "| " + " | ".join(["Operation", *roles]) + " |"
    lines = path.read_text().splitlines()
    require(lines.count(header) == 1, f"{path.name}: missing or duplicate permission matrix")
    seen = set()
    for line in lines[lines.index(header) + 2:]:
        if not line.startswith("|"):
            break
        action, *cells = [cell.strip() for cell in line.strip("|").split("|")]
        require(action in allowed and action not in seen, f"{path.name}: unexpected row {action}")
        require(len(cells) == len(roles), f"{path.name}: role count for {action}")
        for role, cell in zip(roles, cells):
            expected = "Allowed" if role in allowed[action] else "Denied"
            if role == "Manager" and action == "Manage Team Member membership":
                expected = "Team targets only"
            require(cell == expected, f"{path.name}: {role} / {action} must be {expected}")
        seen.add(action)
    require(seen == allowed.keys(), f"{path.name}: missing permission rows {allowed.keys() - seen}")
    return len(seen) * len(roles)


def main():
    specs = sorted(DOCS.glob("[0-9][0-9]_*.md"))
    require([p.name[:2] for p in specs] == [f"{n:02d}" for n in range(1, 10)], "Expected specs 01–09")
    instructions = [ROOT / "AGENTS.md", ROOT / "CODEX_EXECUTION_PROMPT.md"]
    for path in instructions:
        listed = re.findall(r"docs/(\d\d_[A-Z_]+\.md)", path.read_text())
        require(set(listed) == {p.name for p in specs}, f"{path.name} spec list differs from disk")
    documents = [*instructions, *specs, DOCS / "DECISIONS.md", DOCS / "IMPLEMENTATION_STATUS.md"]
    examples = sum(check_markdown(path) for path in documents)
    check_contracts(specs)
    matrix_cases = sum(check_permission_matrix(path) for path in (specs[3], specs[6]))
    print(f"PASS: 9 specification references, {len(documents)} Markdown files, {examples} JSON examples")
    print("PASS: workflow route references, database coverage, AI polling states and event registry")
    print(f"PASS: {matrix_cases} RBAC expectations across the API and frontend matrices")


if __name__ == "__main__":
    main()
