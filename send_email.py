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
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise SystemExit("RESEND_API_KEY is not set; cannot send the newsletter.")
    resend.api_key = api_key

    # Pin the subject date and every source to a single instant so they can't
    # disagree if the run happens to cross UK midnight.
    day = previous_day()
    subject = f"Daily News Briefing — {day:%B} {day.day}, {day.year}"

    # Build each section. Don't let one source failing (e.g. a missing token)
    # block the whole newsletter.
    data = {}
    for heading, fetch in SOURCES:
        try:
            data[heading] = fetch(day=day)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {heading} section: {exc}")

    # Drop empty sections. If every source failed or was empty, fail loudly so
    # the scheduled run is flagged rather than silently sending nothing.
    data = {name: items for name, items in data.items() if items}
    if not data:
        raise SystemExit("No content from any source; not sending an empty newsletter.")

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allisteraall@gmail.com"],
        "subject": subject,
        "html": render_html(data),
    }

    try:
        email = resend.Emails.send(params)
    except Exception as exc:
        raise SystemExit(f"Failed to send newsletter via Resend: {exc}") from exc
    print(email)


if __name__ == "__main__":
    main()
