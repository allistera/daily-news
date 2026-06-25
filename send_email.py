#!/usr/bin/env python3
"""Render the newsletter template with Jinja2 and send it via Resend.

Install (managed by uv):
    uv add resend jinja2

Run:
    RESEND_API_KEY=re_xxx uv run send_email.py
"""

import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

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

    subject = "Daily News Briefing — June 25, 2026"

    # Sample data — replace with your real newsletter content.
    data = {
        "Hacker News": [
            {
                "title": "The Verge",
                "url": 9.2,
            }
        ]
    }

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
