# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

A GitHub Actions workflow that runs daily, invoking `briefing.py` directly to fetch and summarise the day's news via OpenRouter (Gemini), then emails the result via the Resend API.

Two files drive everything:

- **`briefing.py`** — the full pipeline: fetch RSS feeds, Hacker News, and Reddit → call OpenRouter (Gemini) → convert markdown to HTML → send via Resend. Edit this to change sources, models, or output structure.
- **`prompt.txt`** — the system prompt sent to the model. Edit this to change topics, tone, or formatting rules.
- **`.github/workflows/daily-claude.yml`** — the GitHub Actions cron job that runs `briefing.py`.

## How to trigger the workflow

- **Scheduled**: fires at 09:30 UTC (10:30 BST / 09:30 GMT) daily via cron.
- **Manual**: `workflow_dispatch` — trigger from the GitHub Actions tab.

## Required secrets

| Secret | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Authenticates the OpenRouter API (model provider) |
| `RESEND_API_KEY` | Authenticates the Resend email API |

## Output pipeline

1. `briefing.py` fetches articles from RSS feeds, Hacker News (Algolia API), and Reddit (personal RSS).
2. The raw article list is sent to OpenRouter (model: `google/gemini-2.5-flash`) with the system prompt from `prompt.txt`.
3. The LLM response (markdown) is converted to inline-styled HTML by `md_to_html()`.
4. The HTML is wrapped in an email template and sent via Resend to `me@allisterantosik.com` from `reports@infinitywave.design`.

## Editing the prompt

Edit `prompt.txt` to change news sources, topics, or output structure. The raw article list is passed as the user message; the prompt is the system message.
