# Daily News

A small Python service that assembles a daily email newsletter from a set of
**sources** and delivers it with [Resend](https://resend.com). It runs every
morning via GitHub Actions (and can be triggered manually).

Each source returns the previous day's top items, the items are rendered into a
Hacker‑News‑style HTML template, and the result is emailed.

Out of the box there are two sources:

| Section | Source module | Backend |
| --- | --- | --- |
| **Top GitHub Repos** | `sources/top_github_repos.py` | GitHub REST search API (stdlib `urllib`) |
| **Product Hunt Launches** | `sources/product_hunt.py` | `product-hunt-mcp` MCP server (via [`fastmcp`](https://gofastmcp.com)) |

---

## How it works

```
sources/*.py  ──>  send_email.py  ──>  Jinja2 template  ──>  Resend  ──>  inbox
   (fetch)          (orchestrate)      (render HTML)         (send)
```

- **Sources** are independent modules. Each one exposes a function that returns
  a list of items shaped for the template:

  ```python
  [{"title": "...", "url": "https://..."}, ...]
  ```

  Each module also exposes `previous_day()` (yesterday's date in UK time, which
  is the window every source covers) and accepts an optional `day` so the
  subject line and all sections stay pinned to the same date.

- **`send_email.py`** declares the newsletter layout as an ordered list of
  `(heading, fetch_function)` pairs:

  ```python
  SOURCES = [
      ("Top GitHub Repos", repos_for_email),
      ("Product Hunt Launches", posts_for_email),
  ]
  ```

  It fetches each section (a failing source is logged and skipped), drops empty
  sections, renders `templates/template.html.jinja`, and sends via Resend. If
  **every** source is empty it exits non‑zero so a real outage is visible rather
  than silently sending nothing.

## Project structure

```
.
├── send_email.py                     # orchestrator + Resend send
├── sources/
│   ├── product_hunt.py               # MCP-backed source (Product Hunt)
│   └── top_github_repos.py           # HTTP-backed source (GitHub)
├── templates/
│   └── template.html.jinja           # newsletter HTML
├── .github/workflows/
│   └── product-hunt-daily.yml        # daily schedule + manual trigger
└── pyproject.toml                    # deps + ruff config (managed by uv)
```

---

## Setup

This project uses [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies into a managed virtualenv
uv sync

# 2. Install the Product Hunt MCP server as a standalone tool (on PATH)
uv tool install product-hunt-mcp
```

### Environment variables

| Variable | Required | Used by |
| --- | --- | --- |
| `RESEND_API_KEY` | ✅ | sending the email |
| `PRODUCT_HUNT_TOKEN` | ✅ (for the Product Hunt section) | `sources/product_hunt.py` |
| `GITHUB_TOKEN` | optional | `sources/top_github_repos.py` (raises the search rate limit) |

> Importing a source module never requires its token — clients/requests are
> built lazily, so the token is only needed when you actually fetch.

### Run locally

```bash
RESEND_API_KEY=re_xxx PRODUCT_HUNT_TOKEN=ph_xxx uv run send_email.py
```

You can also run a single source standalone to inspect its raw output:

```bash
uv run python sources/top_github_repos.py            # no token needed
PRODUCT_HUNT_TOKEN=ph_xxx uv run python sources/product_hunt.py
```

---

## Scheduled delivery (GitHub Actions)

`.github/workflows/product-hunt-daily.yml` runs at **05:00 UTC** (≈06:00 UK in
summer) and can be triggered manually from the **Actions** tab. Add these
**repository secrets** (Settings → Secrets and variables → Actions):

- `RESEND_API_KEY`
- `PRODUCT_HUNT_TOKEN`
- `GITHUB_TOKEN` is provided automatically by Actions — no setup needed.

Trigger a manual run:

```bash
gh workflow run "Daily Product Hunt Email"
```

---

## Adding a new source

A source is any module that exposes a function returning
`[{"title": "...", "url": "..."}, ...]`. To add one:

1. Create `sources/<name>.py` with a `..._for_email(count=20, day=None)` function.
2. Import it in `send_email.py` and add an entry to `SOURCES`:

   ```python
   from sources.my_source import items_for_email

   SOURCES = [
       ("My Section", items_for_email),
       # ...existing sources...
   ]
   ```

3. Add any required credential as an env var locally and as a repo secret +
   workflow `env:` entry.

For an HTTP/REST source, copy `sources/top_github_repos.py`. For one backed by
an **MCP server**, follow the steps below.

---

## Adding a new MCP server

Product Hunt is wired in through an MCP server that `fastmcp` launches as a
local subprocess and talks to over stdio. Adding another MCP-backed source means
**installing the server**, **writing a source module** that calls one of its
tools, and **wiring up credentials** locally and in CI.

### 1. Install the MCP server

MCP servers are separate programs. Install the server's CLI as a uv tool so it
is available on `PATH` (this is exactly how `product-hunt-mcp` is installed):

```bash
uv tool install <mcp-server-package>      # e.g. uv tool install product-hunt-mcp
uv tool list                              # confirm it installed
which <mcp-server-command>                # confirm it's on PATH
```

### 2. Find the server's command, tools, and credentials

You need three things from the server's docs:

- the **command** to launch it (e.g. `product-hunt-mcp`),
- the **environment variables** it needs (e.g. an API token),
- the **tool name and parameters** to call (e.g. `get_posts`).

### 3. Create the source module

Create `sources/<name>.py`. Build the `fastmcp` client **lazily inside a
function** so importing the module never requires the token or spawns the
server. Mirror the shape of `sources/product_hunt.py`:

```python
import asyncio
import os

from fastmcp import Client

from sources.product_hunt import previous_day  # reuse the shared UK "yesterday"


def _build_client() -> Client:
    """Create the MCP client lazily (token only needed when fetching)."""
    return Client(
        {
            "mcpServers": {
                "<server-name>": {
                    "command": "<mcp-server-command>",
                    "env": {"<SERVER_TOKEN>": os.environ["<SERVER_TOKEN>"]},
                }
            }
        }
    )


async def _fetch(count, day):
    async with _build_client() as client:
        result = await client.call_tool(
            "<tool_name>",
            {"count": count, "day": day.isoformat()},  # match the tool's params
        )
        # Prefer structured data; fall back to raw text blocks.
        if result.data is not None:
            return result.data
        return [getattr(b, "text", str(b)) for b in result.content]


def fetch_items(count: int = 20, day=None):
    """Raw response for `day` (default: yesterday, UK)."""
    return asyncio.run(_fetch(count, day or previous_day()))


def items_for_email(count: int = 20, day=None) -> list[dict]:
    """Return `[{"title", "url"}, ...]` for the email template."""
    items = []
    for entry in _extract(fetch_items(count, day)):   # write _extract for the server's shape
        title = entry.get("name") or entry.get("title")
        url = entry.get("url")
        if title and url:
            items.append({"title": title, "url": url})
    return items
```

> **Tip:** MCP tools often return data in a wrapper (e.g. GraphQL responses come
> back as `{"data": {"items": {"edges": [{"node": {...}}]}}}`). Inspect the real
> response first — run the module's `__main__` block or print
> `fetch_items()` — and write your `_extract()` to dig out the actual records.
> Getting this wrong yields an empty section, not an error.

### 4. Wire it into the newsletter

```python
# send_email.py
from sources.my_source import items_for_email

SOURCES = [
    ("My Section", items_for_email),
    ("Top GitHub Repos", repos_for_email),
    ("Product Hunt Launches", posts_for_email),
]
```

### 5. Provide credentials locally and in CI

- **Locally:** export the server's token before running.
- **CI:** add the token as a repository secret, then pass it in the workflow's
  `env:` block **and** install the server in a workflow step:

  ```yaml
  - name: Install MCP servers
    run: |
      uv tool install product-hunt-mcp
      uv tool install <mcp-server-package>
      echo "$(uv tool dir --bin)" >> "$GITHUB_PATH"

  - name: Send daily email
    env:
      RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
      PRODUCT_HUNT_TOKEN: ${{ secrets.PRODUCT_HUNT_TOKEN }}
      <SERVER_TOKEN>: ${{ secrets.<SERVER_TOKEN> }}
    run: uv run send_email.py
  ```

  The `uv tool dir --bin` line ensures the freshly installed server command is on
  `PATH` so `fastmcp` can launch it.

### 6. Verify

```bash
<SERVER_TOKEN>=... uv run python sources/my_source.py   # inspect raw output
<SERVER_TOKEN>=... RESEND_API_KEY=... uv run send_email.py
```

---

## Development

Linting and formatting use [ruff](https://docs.astral.sh/ruff/) (configured in
`pyproject.toml`):

```bash
uvx ruff check .          # lint
uvx ruff check --fix .    # lint + autofix
uvx ruff format .         # format
```

## Troubleshooting

- **`No content from any source; not sending an empty newsletter`** — every
  source failed or returned nothing. Usually a missing/expired token; check the
  per‑source "Skipping … section" lines above it.
- **`AUTHENTICATION_ERROR` / 401 from an MCP server** — the server's token is
  invalid or expired. Refresh it locally and in the repo secret.
- **A section is silently empty** — the source fetched fine but the response
  shape didn't match your extractor. Print the raw `fetch_*()` output and adjust.
