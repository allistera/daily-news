#!/usr/bin/env python3
"""Render the newsletter template with Jinja2 and send it via Resend.

Install (managed by uv):
    uv add resend jinja2

Run:
    RESEND_API_KEY=re_xxx PRODUCT_HUNT_TOKEN=... uv run send_weekly_email.py
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sources.product_hunt import posts_for_email
from sources.quote import quote_for_email
from sources.top_github_repos import repos_for_email

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "template.html.jinja"
UK = ZoneInfo("Europe/London")

SOURCES = [
    {
        "name": "Top GitHub Repos",
        "subtitle": "by stars gained this week",
        "accent": "purple",
        "fetch": repos_for_email,
    },
    {
        "name": "Top Product Hunt Launches",
        "subtitle": "by upvotes this week",
        "accent": "orange",
        "fetch": posts_for_email,
    },
]

ITEMS_PER_SECTION = 7

def masthead_quote() -> tuple[str, str]:
    """The masthead epigraph, fetched live from API Ninjas."""
    if not os.environ.get("API_NINJAS_KEY"):
        print("API_NINJAS_KEY not set; masthead quote disabled.")
        return "", ""
    try:
        live = quote_for_email()
    except Exception as exc:  # noqa: BLE001
        print(f"Masthead quote request failed; omitting epigraph: {exc}")
        return "", ""
    if not live:
        print("Masthead quote response was empty; omitting epigraph.")
        return "", ""
    return live["quote"], live["author"]

def render_html(sections: list, quote: str, quote_author: str, date_line: str) -> str:
    """Render the email template to an HTML string."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(
        sections=sections,
        quote=quote,
        quote_author=quote_author,
        date_line=date_line,
    )

def previous_week():
    """Return a tuple of (start_day, end_day) for the last 7 days."""
    today = datetime.now(UK).date()
    return today - timedelta(days=7), today - timedelta(days=1)

def main() -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise SystemExit("RESEND_API_KEY is not set; cannot send the newsletter.")
    resend.api_key = api_key

    start_day, end_day = previous_week()
    subject = f"Weekly News Briefing — {start_day:%B} {start_day.day} to {end_day:%B} {end_day.day}, {end_day.year}"
    date_line = f"Week of {start_day:%B} {start_day.day}, {start_day.year}"
    quote, quote_author = masthead_quote()

    sections = []
    for source in SOURCES:
        try:
            items = source["fetch"](count=ITEMS_PER_SECTION, day=(start_day, end_day))
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {source['name']} section: {exc}")
            continue
        if items:
            sections.append({**source, "items": items})

    if not sections:
        raise SystemExit("No content from any source; not sending an empty newsletter.")

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allisteraall@gmail.com"],
        "subject": subject,
        "html": render_html(sections, quote, quote_author, date_line),
    }

    try:
        email = resend.Emails.send(params)
    except Exception as exc:
        raise SystemExit(f"Failed to send newsletter via Resend: {exc}") from exc
    print(email)

if __name__ == "__main__":
    main()
