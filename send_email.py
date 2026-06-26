#!/usr/bin/env python3
"""Render the newsletter template with Jinja2 and send it via Resend.

Install (managed by uv):
    uv add resend jinja2

Run:
    RESEND_API_KEY=re_xxx PRODUCT_HUNT_TOKEN=... uv run send_email.py
"""

import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sources.product_hunt import posts_for_email, previous_day
from sources.top_github_repos import repos_for_email

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "template.html.jinja"

# Newsletter sections in display order: (heading, fetch function). Each fetch
# returns a list of {"title", "url"} items for the previous day.
SOURCES = [
    ("Top GitHub Repos", repos_for_email),
    ("Product Hunt Launches", posts_for_email),
]


def render_html(sections: dict) -> str:
    """Render the email template to an HTML string.

    ``sections`` maps a section name to a list of items, each with
    ``title`` and ``url`` keys, e.g.::

        {"Hacker News": [{"title": "...", "url": "https://..."}]}
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(sections=sections)


def main() -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]

    day = previous_day()
    subject = f"Daily News Briefing — {day:%B} {day.day}, {day.year}"

    # Build each section. Don't let one source failing (e.g. a missing token)
    # block the whole newsletter.
    data = {}
    for heading, fetch in SOURCES:
        try:
            data[heading] = fetch()
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {heading} section: {exc}")

    # Drop empty sections and bail out rather than mailing a contentless email.
    data = {name: items for name, items in data.items() if items}
    if not data:
        print("No content to send — skipping email.")
        return

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allisteraall@gmail.com"],
        "subject": subject,
        "html": render_html(data),
    }

    email = resend.Emails.send(params)
    print(email)


if __name__ == "__main__":
    main()
