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

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "template.html.jinja"


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

    subject = f"Daily News Briefing — {previous_day():%B %-d, %Y}"

    # Sample data — replace with your real newsletter content.
    data = {}

    # Pull the previous day's top Product Hunt posts. Don't let one source
    # failing (e.g. a missing token) block the whole newsletter.
    try:
        data["Product Hunt"] = posts_for_email()
    except Exception as exc:  # noqa: BLE001
        print(f"Skipping Product Hunt section: {exc}")

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allistera@gmail.com"],
        "subject": subject,
        "html": render_html(data),
    }

    email = resend.Emails.send(params)
    print(email)


if __name__ == "__main__":
    main()
