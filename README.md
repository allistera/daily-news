# Daily News Briefing

GitHub Actions runs [`briefing.py`](briefing.py) on a schedule: it pulls recent headlines from RSS, [Hacker News](https://hn.algolia.com/) (Algolia API), and a configurable Reddit RSS feed, sends that corpus to an LLM via [OpenRouter](https://openrouter.ai/), converts the reply to HTML, and emails it with [Resend](https://resend.com/).

## What to edit

| File | Role |
|------|------|
| [`prompt.txt`](prompt.txt) | Instructions for the model (tone, structure, formatting). This is passed as the **system** message. |
| [`briefing.py`](briefing.py) | RSS URLs (`FEEDS`), per-section caps (`FEED_LIMITS`), HN/Reddit counts, Reddit RSS URL (`REDDIT_RSS`), model id, and email copy. |

The assembled article list is the **user** message; the model returns the digest as markdown.

## Pipeline (current behaviour)

1. **Fetch** — Last ~24 hours (`CUTOFF_HOURS`): world/tech/product/smart-home RSS (see `FEEDS`), top HN stories by points, and Reddit items from `REDDIT_RSS` (subreddit, score, and comment counts are parsed from the RSS where possible).
2. **Summarise** — `POST https://openrouter.ai/api/v1/chat/completions` with model `google/gemini-2.5-flash` (see `MODEL` in `briefing.py`).
3. **Email** — Markdown is converted to inline-styled HTML and sent with `POST https://api.resend.com/emails` (from `reports@infinitywave.design` to `me@allisterantosik.com` — adjust in `send_email` if needed).

## GitHub Actions

Workflow: [`.github/workflows/daily-claude.yml`](.github/workflows/daily-claude.yml) (name: **Daily News Briefing**).

- **Schedule:** `09:30` and `10:30` UTC daily (aligned with UK 10:30 across BST/GMT).
- **Manual:** **Actions → Daily News Briefing → Run workflow**.

The job checks out the repo and runs `python3 briefing.py` (stdlib only; no extra install step).

### Secrets

| Secret | Purpose |
|--------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API access for the chat completion |
| `RESEND_API_KEY` | Resend API for sending email |

Optional: `RUN_URL` is set by the workflow to the current run page (footer link in the HTML email).

## Local run

From the repo root, with secrets in the environment:

```bash
export OPENROUTER_API_KEY=...
export RESEND_API_KEY=...
# optional: export RUN_URL=https://...
python3 briefing.py
```
