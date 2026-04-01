# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

A GitHub Actions workflow that runs daily, invoking Claude Code via `anthropics/claude-code-base-action@beta` to fetch and summarise the day's news, then emails the result via the Resend API.

Two files drive everything:

- **`prompt.txt`** — the news brief instructions sent to Claude (topics, sources, formatting rules). Edit this to change what gets fetched or how it is structured.
- **`.github/workflows/daily-claude.yml`** — the full pipeline: dedup check → prompt assembly → Claude run → markdown-to-HTML conversion → Resend email delivery.

## How to trigger the workflow

- **Scheduled**: fires at 09:30 UTC (10:30 BST) and 10:30 UTC (10:30 GMT) daily. A `/tmp` marker file prevents double-sends during clock-change weeks — note this marker only works within the same runner instance and will not persist across runs, so double-sends are still possible on rare occasions.
- **Manual**: `workflow_dispatch` — trigger from the GitHub Actions tab.

## Required secrets

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Authenticates the Claude Code action |
| `RESEND_API_KEY` | Authenticates the Resend email API |

## Output pipeline

1. Claude writes its news summary as markdown to `/tmp/news_output.md`.
2. If that file is missing/empty, the send step falls back to extracting the longest assistant text block from the execution log (NDJSON).
3. The Python send step converts markdown to inline-styled HTML and POSTs to `https://api.resend.com/emails`, sending to `me@allisterantosik.com` from `reports@infinitywave.design`.

## Editing the prompt

`prompt.txt` is the only file you need to edit to change news sources, topics, or output structure. Formatting instructions (headline link format, section heading style, file output path) are appended to it at runtime inside the workflow — do not duplicate them in `prompt.txt`.
